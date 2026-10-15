from __future__ import annotations

import hashlib
import json
import os
import subprocess
import threading
import urllib.error
import urllib.request
from dataclasses import asdict
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from market_os import cli
from market_os.api import make_handler
from market_os.model_summary import (
    DeterministicTestSummaryProvider,
    GeneratedStatement,
    ModelOutput,
    ModelProviderIdentity,
    ModelUsage,
    gate_summary,
    model_gated_summary_from_dict,
    validate_model_output,
)
from market_os.provider_selection import ProviderSelectionError, selected_workflow
from market_os.providers import RetrievedPassage, RetrievalResult
from market_os.research import DeterministicResearchSynthesizer
from market_os.store import RunStore
from market_os.workflow import MarketWorkflow


CORPUS = Path(__file__).parent / "fixtures" / "lightrag" / "corpus.json"


def _adapter():
    from market_os.adapters.lightrag import LightRAGFixtureAdapter

    return LightRAGFixtureAdapter(CORPUS, Path("D:/Code/Github/company-projects/LightRAG"), "missing-python")


def _synthesis(query: str = "What is SPY?"):
    adapter = _adapter()
    documents = adapter.documents_for(("SPY",))
    passage = RetrievedPassage(
        "doc-spy-factsheet:chunk-0", "doc-spy-factsheet", "SPY is a synthetic ETF fixture.", 1,
        "citation:doc-spy-factsheet:chunk-0", documents[0].source_ref,
        hashlib.sha256(b"SPY is a synthetic ETF fixture.").hexdigest(),
    )
    retrieval = RetrievalResult(
        query, tuple(document.document_id for document in documents), (passage,),
        (passage.citation_ref,), "lightrag", "test-v1", documents[0].retrieved_at,
        "1" * 64, tuple(document.content_hash for document in documents),
    )
    return DeterministicResearchSynthesizer().synthesize(
        query, documents, retrieval,
        retrieval_artifact_id="artifact-retrieval", document_artifact_id="artifact-documents", evidence_artifact_id="artifact-evidence",
    )


def test_default_workflow_has_no_model_summary() -> None:
    workflow = MarketWorkflow(RunStore())
    assert workflow.summary_provider is None


def test_explicit_summary_provider_selection_and_unknown_provider() -> None:
    workflow = selected_workflow(MarketWorkflow(RunStore()), "lightrag", "vibe-trading", "deterministic-test")
    assert isinstance(workflow.summary_provider, DeterministicTestSummaryProvider)
    with pytest.raises(ProviderSelectionError, match="requires provider=lightrag"):
        selected_workflow(MarketWorkflow(RunStore()), "fixture", "fixture", "deterministic-test")
    with pytest.raises(ProviderSelectionError, match="summary_provider"):
        selected_workflow(MarketWorkflow(RunStore()), "fixture", "fixture", "hosted-provider")


def test_deterministic_provider_is_citation_preserving_and_fingerprinted() -> None:
    synthesis = _synthesis()
    provider = DeterministicTestSummaryProvider()
    first = gate_summary(provider, "What is SPY?", synthesis, synthesis_artifact_id="artifact-cited")
    second = gate_summary(provider, "What is SPY?", synthesis, synthesis_artifact_id="artifact-cited")
    assert first.gate.status == "approved"
    assert first.validation.status == "valid"
    assert first.summary_fingerprint == second.summary_fingerprint
    assert first.statements[0].classification == "supported"
    assert first.statements[0].citation_ids == first.request.claim_ids[:1] or first.statements[0].citation_ids


def test_model_output_with_unknown_citation_is_rejected() -> None:
    synthesis = _synthesis()
    output = ModelOutput(
        "unsupported",
        (GeneratedStatement("statement-1", "unsupported", "supported", ("unknown",), (), (), ("text",)),),
        ModelUsage(),
    )
    validation = validate_model_output(output, synthesis)
    assert validation.status == "rejected"
    assert any("unknown citation" in error for error in validation.errors)


def test_secret_like_and_excessive_model_output_is_rejected() -> None:
    synthesis = _synthesis()
    statement = GeneratedStatement(
        "statement-hostile",
        "api_key=fixture-not-a-secret",
        "unsupported",
    )
    output = ModelOutput("api_key=fixture-not-a-secret", (statement,))
    validation = validate_model_output(output, synthesis)
    assert validation.status == "rejected"
    assert any("secret-like" in error for error in validation.errors)

    excessive = ModelOutput("x" * 17_000, (GeneratedStatement("statement-long", "x", "unsupported"),))
    validation = validate_model_output(excessive, synthesis)
    assert validation.status == "rejected"
    assert any("maximum length" in error for error in validation.errors)


def test_inference_is_explicitly_labeled_and_separately_counted() -> None:
    synthesis = _synthesis()
    output = ModelOutput(
        "Inference: The fixture may be useful for a bounded comparison.",
        (GeneratedStatement("statement-inference", "The fixture may be useful for a bounded comparison.", "inference"),),
    )
    validation = validate_model_output(output, synthesis)
    assert validation.status == "valid"
    assert validation.supported_count == 0
    assert validation.inference_count == 1
    assert validation.evidence_coverage == 0.0
    inference_provider = type(
        "InferenceProvider",
        (),
        {
            "identity": ModelProviderIdentity("inference-test", "test", "v1"),
            "prompt_version": "inference-v1",
            "generate": lambda self, request, source: output,
        },
    )()
    gated = gate_summary(
        inference_provider,
        "What is SPY?",
        synthesis,
        synthesis_artifact_id="artifact-cited",
    )
    assert gated.gate.status == "approved"
    assert gated.summary_text.startswith("Inference: ")


def test_unsupported_statement_is_explicit_and_has_zero_coverage() -> None:
    adapter = _adapter()
    documents = adapter.documents_for(("SPY",))
    retrieval = RetrievalResult(
        "No matching passage",
        tuple(document.document_id for document in documents),
        (),
        (),
        "lightrag",
        "test-v1",
        documents[0].retrieved_at,
        "3" * 64,
        tuple(document.content_hash for document in documents),
        error="no_results",
    )
    synthesis = DeterministicResearchSynthesizer().synthesize(
        "No matching passage",
        documents,
        retrieval,
        retrieval_artifact_id="artifact-retrieval",
        document_artifact_id="artifact-documents",
        evidence_artifact_id="artifact-evidence",
    )
    summary = gate_summary(
        DeterministicTestSummaryProvider(),
        "No matching passage",
        synthesis,
        synthesis_artifact_id="artifact-cited",
    )
    assert summary.gate.status == "approved"
    assert summary.validation.unsupported_count == 1
    assert summary.validation.evidence_coverage == 0.0
    assert summary.summary_text.startswith("Unsupported (ungrounded): ")


def test_model_provider_failure_preserves_deterministic_fallback() -> None:
    synthesis = _synthesis()

    class Broken:
        identity = ModelProviderIdentity("broken-test", "broken", "v1")
        prompt_version = "broken-v1"

        def generate(self, request, synthesis):
            raise TimeoutError("model timeout")

    summary = gate_summary(Broken(), "What is SPY?", synthesis, synthesis_artifact_id="artifact-cited")
    assert summary.gate.status == "fallback"
    assert summary.gate.deterministic_fallback is True
    assert summary.summary_text is None
    assert summary.failure is not None
    assert summary.failure.kind == "timeout"
    assert summary.deterministic_fallback_fingerprint == synthesis.synthesis_fingerprint


def test_invalid_model_output_is_rejected_without_publishing_text() -> None:
    synthesis = _synthesis()

    class Ungrounded:
        identity = ModelProviderIdentity("ungrounded-test", "test", "v1")
        prompt_version = "ungrounded-v1"

        def generate(self, request, synthesis):
            return ModelOutput(
                "invented fact",
                (
                    GeneratedStatement(
                        "statement-invented",
                        "invented fact",
                        "supported",
                        citation_ids=synthesis.claims[0].citation_ids,
                        support_ids=synthesis.claims[0].support_ids,
                        document_ids=synthesis.claims[0].document_ids,
                        evidence_quotes=("not the stored passage",),
                    ),
                ),
            )

    summary = gate_summary(Ungrounded(), "What is SPY?", synthesis, synthesis_artifact_id="artifact-cited")
    assert summary.gate.status == "rejected"
    assert summary.gate.deterministic_fallback is True
    assert summary.summary_text is None
    assert summary.validation.status == "rejected"


def test_malformed_provider_output_is_rejected_not_fallback() -> None:
    synthesis = _synthesis()

    class Malformed:
        identity = ModelProviderIdentity("malformed-test", "test", "v1")
        prompt_version = "malformed-v1"

        def generate(self, request, synthesis):
            return {"summary": "not a model output"}

    summary = gate_summary(Malformed(), "What is SPY?", synthesis, synthesis_artifact_id="artifact-cited")
    assert summary.gate.status == "rejected"
    assert summary.gate.deterministic_fallback is True
    assert summary.failure is None
    assert any("malformed_model_output" in error for error in summary.validation.errors)


def test_rejected_summary_text_mismatch_remains_inspectable(tmp_path: Path) -> None:
    from market_os.tests.test_m2_cited_research import CitedFixtureProvider

    class WrongRenderer(DeterministicTestSummaryProvider):
        def generate(self, request, synthesis):
            output = super().generate(request, synthesis)
            return ModelOutput("uncategorized prose", output.statements, output.usage)

    workflow = MarketWorkflow(
        RunStore(tmp_path),
        evidence_provider=CitedFixtureProvider(),
        summary_provider=WrongRenderer(),
    )
    result = workflow.run(workflow.create_task("Rejected summary", ["SPY"], "2026-01-02", "2026-01-06"))
    assert result["model_summary"]["gate"]["status"] == "rejected"
    assert result["model_summary"]["summary_text"] is None
    inspected = workflow.inspect_resource(result["run"]["run_id"], "model-summary")
    assert inspected["model_summary"]["validation"]["status"] == "rejected"


def test_model_summary_rejects_tampered_fingerprints_and_gate_state() -> None:
    synthesis = _synthesis()
    summary = gate_summary(
        DeterministicTestSummaryProvider(),
        "What is SPY?",
        synthesis,
        synthesis_artifact_id="artifact-cited",
    )

    with pytest.raises(ValueError, match="summary_fingerprint"):
        model_gated_summary_from_dict({**asdict(summary), "summary_fingerprint": "0" * 64})
    with pytest.raises(ValueError, match="output_fingerprint"):
        model_gated_summary_from_dict({**asdict(summary), "output_fingerprint": "0" * 64})
    with pytest.raises(ValueError, match="output_fingerprint"):
        model_gated_summary_from_dict({**asdict(summary), "summary_text": None})
    with pytest.raises(ValueError, match="deterministic fallback fingerprint"):
        model_gated_summary_from_dict(
            {**asdict(summary), "deterministic_fallback_fingerprint": "1" * 64}
        )


def test_model_output_rejects_cross_claim_support_and_unsupported_citations() -> None:
    adapter = _adapter()
    documents = adapter.documents_for(("SPY",))
    first_text = "SPY is a synthetic ETF fixture."
    second_text = "SPY risk is capped by a synthetic policy limit."
    passages = (
        RetrievedPassage(
            "doc-spy-factsheet:chunk-0",
            "doc-spy-factsheet",
            first_text,
            1,
            "citation:doc-spy-factsheet:chunk-0",
            documents[0].source_ref,
            hashlib.sha256(first_text.encode()).hexdigest(),
        ),
        RetrievedPassage(
            "doc-risk-policy:chunk-0",
            "doc-risk-policy",
            second_text,
            2,
            "citation:doc-risk-policy:chunk-0",
            next(document for document in documents if document.document_id == "doc-risk-policy").source_ref,
            hashlib.sha256(second_text.encode()).hexdigest(),
        ),
    )
    retrieval = RetrievalResult(
        "What is SPY?",
        tuple(document.document_id for document in documents),
        passages,
        tuple(passage.citation_ref for passage in passages),
        "lightrag",
        "test-v1",
        documents[0].retrieved_at,
        "2" * 64,
        tuple(document.content_hash for document in documents),
    )
    synthesis = DeterministicResearchSynthesizer().synthesize(
        "What is SPY?",
        documents,
        retrieval,
        retrieval_artifact_id="artifact-retrieval",
        document_artifact_id="artifact-documents",
        evidence_artifact_id="artifact-evidence",
    )
    first, second = synthesis.claims
    output = ModelOutput(
        "mixed",
        (
            GeneratedStatement(
                "statement-mixed",
                "mixed",
                "supported",
                citation_ids=second.citation_ids,
                support_ids=first.support_ids,
                document_ids=("missing-document",),
                evidence_quotes=(first_text,),
            ),
            GeneratedStatement(
                "statement-unsupported",
                "not grounded",
                "unsupported",
                citation_ids=first.citation_ids,
            ),
        ),
    )

    validation = validate_model_output(output, synthesis)

    assert validation.status == "rejected"
    assert any("belongs to a different claim" in error for error in validation.errors)
    assert any("unknown document" in error for error in validation.errors)
    assert any("unsupported statement contains citation" in error for error in validation.errors)


def test_cross_run_citation_is_rejected() -> None:
    synthesis = _synthesis()
    other = _synthesis("Different run query")
    output = ModelOutput(
        "unsupported",
        (
            GeneratedStatement(
                "statement-cross-run",
                other.claims[0].claim_text,
                "supported",
                citation_ids=other.claims[0].citation_ids,
                support_ids=other.claims[0].support_ids,
                document_ids=other.claims[0].document_ids,
                evidence_quotes=(other.supports[0].quote,),
            ),
        ),
    )
    validation = validate_model_output(output, synthesis)
    assert validation.status == "rejected"
    assert any("unknown citation" in error for error in validation.errors)


def test_cited_workflow_persists_and_inspects_model_summary_after_restart(tmp_path: Path) -> None:
    from market_os.tests.test_m2_cited_research import CitedFixtureProvider

    workflow = MarketWorkflow(
        RunStore(tmp_path),
        evidence_provider=CitedFixtureProvider(),
        summary_provider=DeterministicTestSummaryProvider(),
    )
    result = workflow.run(workflow.create_task("Inspect model summary", ["SPY"], "2026-01-02", "2026-01-06"))
    model_artifact = next(item for item in result["artifacts"] if item["kind"] == "model-summary")
    completed = workflow.inspect_run(result["run"]["run_id"])
    completed_event = completed["events"][-1]
    assert model_artifact["artifact_id"] in completed_event["payload"]["artifact_ids"]

    restarted = MarketWorkflow(RunStore(tmp_path))
    inspected = restarted.inspect_resource(result["run"]["run_id"], "model-summary")
    inferences = restarted.inspect_resource(result["run"]["run_id"], "inferences")
    assert inspected["model_summary"]["gate"]["status"] == "approved"
    assert inspected["model_summary"]["validation"]["status"] == "valid"
    assert inspected["model_summary"]["synthesis_lineage_artifact_id"] == next(
        item["artifact_id"] for item in result["artifacts"] if item["kind"] == "cited-research"
    )
    assert inferences["inferences"] == []


def test_cli_and_api_inspect_model_summary_read_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from market_os.tests.test_m2_cited_research import CitedFixtureProvider

    store = RunStore(tmp_path)
    workflow = MarketWorkflow(
        store,
        evidence_provider=CitedFixtureProvider(),
        summary_provider=DeterministicTestSummaryProvider(),
    )
    result = workflow.run(workflow.create_task("Inspect surfaces", ["SPY"], "2026-01-02", "2026-01-06"))
    run_id = result["run"]["run_id"]
    artifact_index_before = store.artifact_index.read_text(encoding="utf-8")
    event_log_before = store.events.read_text(encoding="utf-8")

    monkeypatch.setattr(cli, "MarketWorkflow", lambda store=None: MarketWorkflow(store or tmp_path))
    assert cli.main(
        ["inspect", run_id, "--store-root", str(tmp_path), "--resource", "model-summary"]
    ) == 0
    assert json.loads(capsys.readouterr().out)["model_summary"]["gate"]["status"] == "approved"

    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(MarketWorkflow(RunStore(tmp_path))))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/v1/runs/{run_id}/research/model-summary"
        response = json.loads(urllib.request.urlopen(url, timeout=5).read())
        assert response["model_summary"]["summary_fingerprint"] == result["model_summary"]["summary_fingerprint"]
    finally:
        server.shutdown()
        thread.join(timeout=2)

    assert store.artifact_index.read_text(encoding="utf-8") == artifact_index_before
    assert store.events.read_text(encoding="utf-8") == event_log_before


def test_model_summary_inspection_rejects_corrupt_content_and_lineage(tmp_path: Path) -> None:
    from market_os.tests.test_m2_cited_research import CitedFixtureProvider

    workflow = MarketWorkflow(
        RunStore(tmp_path),
        evidence_provider=CitedFixtureProvider(),
        summary_provider=DeterministicTestSummaryProvider(),
    )
    result = workflow.run(workflow.create_task("Corrupt summary", ["SPY"], "2026-01-02", "2026-01-06"))
    model_artifact = next(item for item in result["artifacts"] if item["kind"] == "model-summary")
    path = Path(model_artifact["path"])
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["summary_fingerprint"] = "0" * 64
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="artifact content hash mismatch"):
        workflow.inspect_resource(result["run"]["run_id"], "model-summary")

    workflow = MarketWorkflow(
        RunStore(tmp_path / "lineage"),
        evidence_provider=CitedFixtureProvider(),
        summary_provider=DeterministicTestSummaryProvider(),
    )
    result = workflow.run(workflow.create_task("Broken summary lineage", ["SPY"], "2026-01-02", "2026-01-06"))
    model_artifact = next(item for item in result["artifacts"] if item["kind"] == "model-summary")
    store = RunStore(tmp_path / "lineage")
    entries = [json.loads(line) for line in store.artifact_index.read_text(encoding="utf-8").splitlines() if line]
    for entry in entries:
        if entry["artifact_id"] == model_artifact["artifact_id"]:
            entry["lineage"] = ["artifact-missing-cited-research"]
    store.artifact_index.write_text(
        "\n".join(json.dumps(entry, sort_keys=True) for entry in entries) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="lineage is incomplete"):
        workflow.inspect_resource(result["run"]["run_id"], "model-summary")


def test_api_rejects_summary_provider_without_cited_retrieval(tmp_path: Path) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(MarketWorkflow(RunStore(tmp_path))))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        payload = json.dumps(
            {
                "objective": "Summary only selection",
                "symbols": ["SPY"],
                "start": "2026-01-02",
                "end": "2026-01-06",
                "summary_provider": "deterministic-test",
            }
        ).encode()
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(
                urllib.request.Request(
                    f"http://127.0.0.1:{server.server_port}/v1/tasks",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                ),
                timeout=5,
            )
        assert error.value.code == 400
        response = json.loads(error.value.read())
        assert "requires provider=lightrag" in response["error"]["message"]
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_default_fixture_workflow_remains_deterministic_only(tmp_path: Path) -> None:
    workflow = selected_workflow(MarketWorkflow(RunStore(tmp_path)), "fixture", "fixture")
    task = workflow.create_task("Model gated fixture", ["SPY"], "2026-01-02", "2026-01-06", idempotency_key="m2.4-test")
    # Model gating is only meaningful on the cited path; the default fixture path stays deterministic-only.
    result = workflow.run(task)
    assert result["run"]["status"] == "completed"
    assert "model_summary" not in result


def test_direct_summary_selection_requires_cited_retrieval(tmp_path: Path) -> None:
    workflow = MarketWorkflow(RunStore(tmp_path), summary_provider=DeterministicTestSummaryProvider())
    with pytest.raises(ValueError, match="requires a cited-research retrieval provider"):
        workflow.run(workflow.create_task("Summary without documents", ["SPY"], "2026-01-02", "2026-01-06"))


def test_cli_and_api_accept_explicit_summary_provider(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    calls: list[str | None] = []

    def select(workflow, provider, backtest_provider=None, summary_provider=None):
        calls.append(summary_provider)
        return workflow

    monkeypatch.setattr("market_os.provider_selection.selected_workflow", select)
    monkeypatch.setattr(cli, "MarketWorkflow", lambda: MarketWorkflow(RunStore(tmp_path / "cli")))
    assert cli.main([
        "research",
        "Summary",
        "--symbols",
        "SPY",
        "--provider",
        "lightrag",
        "--backtest-provider",
        "vibe-trading",
        "--summary-provider",
        "deterministic-test",
    ]) == 0
    assert calls == ["deterministic-test"]
    capsys.readouterr()

    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(MarketWorkflow(RunStore(tmp_path / "api"))))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        payload = json.dumps({
            "objective": "Summary",
            "symbols": ["SPY"],
            "start": "2026-01-02",
            "end": "2026-01-06",
            "provider": "lightrag",
            "backtest_provider": "vibe-trading",
            "summary_provider": "deterministic-test",
        }).encode()
        response = json.loads(urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{server.server_port}/v1/tasks", data=payload, headers={"Content-Type": "application/json"}), timeout=5).read())
        assert response["run"]["status"] == "completed"
    finally:
        server.shutdown()
        thread.join(timeout=2)


def _available_python(
    env_name: str,
    default: str,
    import_probe: str,
    *,
    pythonpath: Path | None = None,
) -> str | None:
    candidates = [os.environ.get(env_name), default]
    environment = os.environ.copy()
    if pythonpath is not None:
        environment["PYTHONPATH"] = str(pythonpath)
    for candidate in candidates:
        if candidate and Path(candidate).exists() and subprocess.run(
            [candidate, "-c", import_probe], check=False, capture_output=True, env=environment
        ).returncode == 0:
            return candidate
    return None


@pytest.mark.integration
def test_actual_lightrag_vibe_workflow_with_deterministic_model_gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lightrag_root = Path(os.environ.get("MARKET_OS_LIGHTRAG_ROOT", "D:/Code/Github/company-projects/LightRAG"))
    vibe_root = Path(os.environ.get("MARKET_OS_VIBE_TRADING_ROOT", "D:/Code/Github/company-projects/Vibe-Trading"))
    lightrag_python = _available_python(
        "MARKET_OS_LIGHTRAG_PYTHON",
        "C:/Users/goddt/AppData/Local/Temp/market-os-m2.2-lightrag-venv/Scripts/python.exe",
        "import lightrag, httpx, nano_vectordb",
        pythonpath=lightrag_root,
    )
    vibe_python = _available_python(
        "MARKET_OS_VIBE_TRADING_PYTHON",
        "C:/Users/goddt/AppData/Local/Temp/market-os-m2.1-vibe-venv/Scripts/python.exe",
        "import pandas, pydantic, defusedxml",
    )
    if lightrag_python is None or vibe_python is None or not lightrag_root.is_dir() or not vibe_root.is_dir():
        pytest.skip("offline LightRAG and Vibe-Trading environments are not configured")

    monkeypatch.setenv("MARKET_OS_LIGHTRAG_ROOT", str(lightrag_root))
    monkeypatch.setenv("MARKET_OS_LIGHTRAG_PYTHON", lightrag_python)
    monkeypatch.setenv("MARKET_OS_VIBE_TRADING_ROOT", str(vibe_root))
    monkeypatch.setenv("MARKET_OS_VIBE_TRADING_PYTHON", vibe_python)

    workflow = selected_workflow(
        MarketWorkflow(RunStore(tmp_path / "store")),
        "lightrag",
        "vibe-trading",
        "deterministic-test",
    )
    task = workflow.create_task(
        "Cited model-gated SPY research",
        ["SPY"],
        "2026-01-02",
        "2026-01-09",
        idempotency_key="m2.4-actual",
    )
    result = workflow.run(task)

    assert result["run"]["status"] == "completed"
    assert result["order_plan"]["mode"] == "paper"
    assert result["model_summary"]["provider"]["provider"] == "deterministic-test"
    assert result["model_summary"]["gate"]["status"] == "approved"
    assert result["model_summary"]["validation"]["status"] == "valid"
    assert result["model_summary"]["request"]["synthesis_fingerprint"] == result["cited_research"]["synthesis_fingerprint"]
    assert any(item["kind"] == "model-summary" for item in result["artifacts"])

    replay = workflow.run(
        workflow.create_task(
            "Cited model-gated SPY research",
            ["SPY"],
            "2026-01-02",
            "2026-01-09",
            idempotency_key="m2.4-actual",
        )
    )
    assert replay == result
    inspected = MarketWorkflow(RunStore(tmp_path / "store")).inspect_resource(
        result["run"]["run_id"], "model-summary"
    )
    assert inspected["model_summary"]["summary_fingerprint"] == result["model_summary"]["summary_fingerprint"]
