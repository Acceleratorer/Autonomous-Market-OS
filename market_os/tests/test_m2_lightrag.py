from __future__ import annotations

import hashlib
import json
import os
import subprocess
import threading
from pathlib import Path

import pytest

from market_os import cli
from market_os.adapters.lightrag import LightRAGFixtureAdapter, LightRAGUnavailable
from market_os.api import make_handler
from market_os.provider_selection import ProviderSelectionError, selected_workflow
from market_os.providers import DocumentRecord, LicenseMetadata, ProviderCancelled, ProviderDeadline, Provenance, RetrievedPassage, RetrievalResult
from market_os.store import RunStore
from market_os.workflow import MarketWorkflow


CORPUS = Path(__file__).parent / "fixtures" / "lightrag" / "corpus.json"
REFERENCE_ROOT = Path(os.environ.get("MARKET_OS_LIGHTRAG_ROOT", "D:/Code/Github/company-projects/LightRAG"))


def _lightrag_python() -> str | None:
    configured = os.environ.get("MARKET_OS_LIGHTRAG_PYTHON")
    candidates = [
        configured,
        "C:/Users/goddt/AppData/Local/Temp/market-os-m2.2-lightrag-venv/Scripts/python.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            check = subprocess.run(
                [candidate, "-c", "import lightrag, httpx, nano_vectordb"],
                env={**os.environ, "PYTHONPATH": str(REFERENCE_ROOT)},
                check=False,
            )
            if check.returncode == 0:
                return candidate
    return None


def test_document_fixture_normalizes_metadata_and_hashes() -> None:
    adapter = LightRAGFixtureAdapter(CORPUS, REFERENCE_ROOT, _lightrag_python() or "python")
    documents = adapter.documents_for(("SPY",))
    assert {document.document_id for document in documents} == {"doc-spy-factsheet", "doc-market-commentary", "doc-risk-policy"}
    assert all(document.provenance.provider == "lightrag" for document in documents)
    assert all(document.license.classification == "synthetic-internal" for document in documents)
    assert all(document.content_ref.startswith("fixture:m2.2") for document in documents)


@pytest.mark.parametrize("mutation", ["duplicate", "hash", "media", "content"])
def test_document_fixture_rejects_invalid_corpus(tmp_path: Path, mutation: str) -> None:
    payload = json.loads(CORPUS.read_text(encoding="utf-8"))
    if mutation == "duplicate":
        payload["documents"].append(dict(payload["documents"][0]))
    elif mutation == "hash":
        payload["documents"][0]["content_hash"] = "0" * 64
    elif mutation == "media":
        payload["documents"][0]["media_type"] = "application/octet-stream"
    else:
        payload["documents"][0]["content"] = ""
    path = tmp_path / f"{mutation}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        LightRAGFixtureAdapter(path, REFERENCE_ROOT, _lightrag_python() or "python")


def test_document_contract_rejects_bad_timestamp_and_provenance() -> None:
    with pytest.raises(ValueError, match="published_at"):
        DocumentRecord(
            "doc", "title", "publisher", "fixture:doc", "not-a-time", "2026-01-10T00:00:00+00:00",
            ("SPY",), "text/plain", "0" * 64, LicenseMetadata("fixture-only"),
            Provenance("fixture", "fixture:doc", "2026-01-10T00:00:00+00:00"),
        )
    with pytest.raises(ValueError, match="source_ref"):
        Provenance("fixture", "", "2026-01-10T00:00:00+00:00")


def test_retrieval_contract_rejects_unknown_citation() -> None:
    content_hash = hashlib.sha256(b"text").hexdigest()
    passage = RetrievedPassage(
        "passage-1", "doc-1", "text", 1, "citation-1", "fixture:doc-1", content_hash
    )
    with pytest.raises(ValueError, match="citations"):
        RetrievalResult(
            "query", ("doc-1",), (passage,), ("missing-citation",), "lightrag", "v1",
            "2026-01-10T00:00:00+00:00", "0" * 64, (content_hash,)
        )


def test_lightrag_selection_requires_explicit_backtest_provider(tmp_path: Path) -> None:
    with pytest.raises(ProviderSelectionError, match="retrieval-only"):
        selected_workflow(MarketWorkflow(RunStore(tmp_path)), "lightrag")


def test_lightrag_unavailable_is_actionable(tmp_path: Path) -> None:
    adapter = LightRAGFixtureAdapter(CORPUS, tmp_path / "missing", "missing-python")
    documents = adapter.documents_for(("SPY",))
    with pytest.raises(LightRAGUnavailable, match="provider_unavailable"):
        adapter.retrieve_documents("What is SPY?", documents)


def test_lightrag_cancellation_before_launch(tmp_path: Path) -> None:
    adapter = LightRAGFixtureAdapter(CORPUS, tmp_path / "missing", "missing-python")
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(ProviderCancelled, match="before launch"):
        adapter.retrieve_documents("What is SPY?", adapter.documents_for(("SPY",)), cancel_event=cancel)


def test_lightrag_deadline_is_enforced_by_local_child(tmp_path: Path) -> None:
    python_executable = _lightrag_python()
    if python_executable is None or not REFERENCE_ROOT.is_dir():
        pytest.skip("set MARKET_OS_LIGHTRAG_PYTHON and MARKET_OS_LIGHTRAG_ROOT for actual execution")
    adapter = LightRAGFixtureAdapter(CORPUS, REFERENCE_ROOT, python_executable, tmp_path / "runs")
    with pytest.raises(LightRAGUnavailable, match="deadline_exceeded"):
        adapter.retrieve_documents(
            "What is SPY?", adapter.documents_for(("SPY",)), deadline=ProviderDeadline(0.001)
        )


def test_cli_dispatches_lightrag_selection(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    calls: list[tuple[str, str | None]] = []

    def select(workflow, provider, backtest_provider=None):
        calls.append((provider, backtest_provider))
        return workflow

    monkeypatch.setattr("market_os.provider_selection.selected_workflow", select)
    monkeypatch.setattr(cli, "MarketWorkflow", lambda: MarketWorkflow(RunStore(tmp_path)))
    assert cli.main([
        "research", "Cited research", "--symbols", "SPY", "--provider", "lightrag", "--backtest-provider", "vibe-trading"
    ]) == 0
    assert json.loads(capsys.readouterr().out)["run"]["status"] == "completed"
    assert calls == [("lightrag", "vibe-trading")]


def test_api_dispatches_lightrag_selection(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[tuple[str, str | None]] = []

    def select(workflow, provider, backtest_provider=None):
        calls.append((provider, backtest_provider))
        return workflow

    monkeypatch.setattr("market_os.provider_selection.selected_workflow", select)
    from http.server import ThreadingHTTPServer
    from urllib.request import Request, urlopen

    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(MarketWorkflow(RunStore(tmp_path))))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        payload = json.dumps({
            "objective": "API cited research",
            "symbols": ["SPY"],
            "start": "2026-01-02",
            "end": "2026-01-06",
            "provider": "lightrag",
            "backtest_provider": "vibe-trading",
        }).encode()
        response = json.loads(urlopen(Request(
            f"http://127.0.0.1:{server.server_port}/v1/tasks",
            data=payload,
            headers={"Content-Type": "application/json"},
        ), timeout=5).read())
        assert response["run"]["status"] == "completed"
    finally:
        server.shutdown()
        thread.join(timeout=2)
    assert calls == [("lightrag", "vibe-trading")]


@pytest.mark.integration
def test_actual_lightrag_retrieval_is_cited_and_reproducible(tmp_path: Path) -> None:
    python_executable = _lightrag_python()
    if python_executable is None or not REFERENCE_ROOT.is_dir():
        pytest.skip("set MARKET_OS_LIGHTRAG_PYTHON and MARKET_OS_LIGHTRAG_ROOT for actual execution")
    adapter = LightRAGFixtureAdapter(CORPUS, REFERENCE_ROOT, python_executable, tmp_path / "runs")
    documents = adapter.documents_for(("SPY",))
    first = adapter.retrieve_documents("What does the SPY risk policy limit?", documents)
    second = adapter.retrieve_documents("What does the SPY risk policy limit?", documents)
    assert isinstance(first, RetrievalResult)
    assert first.citations
    assert all(passage.document_id in {document.document_id for document in documents} for passage in first.passages)
    assert first.query_fingerprint == second.query_fingerprint
    assert first.passages == second.passages


@pytest.mark.integration
def test_actual_lightrag_workflow_persists_documents_retrieval_and_lineage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    python_executable = _lightrag_python()
    if python_executable is None or not REFERENCE_ROOT.is_dir():
        pytest.skip("set MARKET_OS_LIGHTRAG_PYTHON and MARKET_OS_LIGHTRAG_ROOT for actual execution")
    monkeypatch.setenv("MARKET_OS_LIGHTRAG_ROOT", str(REFERENCE_ROOT))
    monkeypatch.setenv("MARKET_OS_LIGHTRAG_PYTHON", python_executable)
    monkeypatch.setenv("MARKET_OS_VIBE_TRADING_ROOT", os.environ.get("MARKET_OS_VIBE_TRADING_ROOT", "D:/Code/Github/company-projects/Vibe-Trading"))
    monkeypatch.setenv("MARKET_OS_VIBE_TRADING_PYTHON", os.environ.get("MARKET_OS_VIBE_TRADING_PYTHON", "C:/Users/goddt/AppData/Local/Temp/market-os-m2.1-vibe-venv/Scripts/python.exe"))
    workflow = selected_workflow(MarketWorkflow(RunStore(tmp_path / "store")), "lightrag", "vibe-trading")
    task = workflow.create_task("Cited SPY research", ["SPY"], "2026-01-02", "2026-01-09", idempotency_key="m2.2-actual")
    result = workflow.run(task)
    assert result["run"]["status"] == "completed"
    assert result["order_plan"]["mode"] == "paper"
    assert result["retrieval"]["citations"]
    assert set(result["retrieval"]["citations"]).issubset(result["research"]["citations"])
    assert result["cited_research"]["claims"]
    assert result["cited_research"]["coverage"]["coverage_ratio"] == 1.0
    assert {item["kind"] for item in result["artifacts"]} >= {"documents", "retrieval", "evidence", "cited-research", "research", "backtest"}
    assert any(item["kind"] == "retrieval" and item["lineage"] for item in result["artifacts"])
    assert workflow.run(workflow.create_task("Cited SPY research", ["SPY"], "2026-01-02", "2026-01-09", idempotency_key="m2.2-actual")) == result
    restarted = selected_workflow(MarketWorkflow(RunStore(tmp_path / "store")), "lightrag", "vibe-trading")
    inspection = restarted.inspect_run(result["run"]["run_id"])
    cited_artifact = next(item for item in inspection["artifacts"] if item["kind"] == "cited-research")
    cited_payload = json.loads(Path(cited_artifact["path"]).read_text(encoding="utf-8"))
    assert cited_payload["synthesis_fingerprint"] == result["cited_research"]["synthesis_fingerprint"]
    assert cited_payload["coverage"]["coverage_ratio"] == 1.0
