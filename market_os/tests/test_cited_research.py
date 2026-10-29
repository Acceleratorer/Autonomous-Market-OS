from __future__ import annotations

import hashlib
import json
import threading
import urllib.error
import urllib.request
from dataclasses import asdict
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from market_os import cli
from market_os.api import make_handler
from market_os.contracts import Evidence
from market_os.providers import RetrievedPassage, RetrievalResult
from market_os.research import DeterministicResearchSynthesizer
from market_os.store import RunStore
from market_os.workflow import MarketWorkflow


def _document(document_id: str, text: str):
    from market_os.adapters.lightrag import LightRAGFixtureAdapter

    adapter = LightRAGFixtureAdapter(
        Path(__file__).parent / "fixtures" / "lightrag" / "corpus.json",
        Path("D:/Code/Github/company-projects/LightRAG"),
        "missing-python",
    )
    return next(document for document in adapter.records if document.document_id == document_id)


def _retrieval(texts: list[tuple[str, str]]) -> RetrievalResult:
    docs = {document.document_id: document for document in (_document("doc-spy-factsheet", ""), _document("doc-risk-policy", ""))}
    passages = tuple(
        RetrievedPassage(
            f"{document_id}:chunk-{index}",
            document_id,
            text,
            index,
            f"citation:{document_id}:chunk-{index}",
            docs[document_id].source_ref,
            hashlib.sha256(text.encode()).hexdigest(),
        )
        for index, (document_id, text) in enumerate(texts, 1)
    )
    return RetrievalResult(
        "What does the risk policy say?",
        tuple(dict.fromkeys(document_id for document_id, _ in texts)) or ("doc-risk-policy",),
        passages,
        tuple(passage.citation_ref for passage in passages),
        "lightrag",
        "m2.2-lightrag-naive-v1",
        "2026-01-10T00:00:00+00:00",
        "1" * 64,
        tuple(dict.fromkeys(passage.content_hash for passage in passages)),
    )


def test_synthesis_emits_exact_quote_supported_claims_and_fingerprint() -> None:
    from market_os.adapters.lightrag import LightRAGFixtureAdapter

    adapter = LightRAGFixtureAdapter(
        Path(__file__).parent / "fixtures" / "lightrag" / "corpus.json",
        Path("D:/Code/Github/company-projects/LightRAG"),
        "missing-python",
    )
    docs = adapter.documents_for(("SPY",))
    passage_text = "SPY is a synthetic ETF fixture representing a broad US equity basket."
    retrieval = _retrieval([("doc-spy-factsheet", passage_text)])
    first = DeterministicResearchSynthesizer().synthesize(
        "What is SPY?", docs, retrieval,
        retrieval_artifact_id="artifact-retrieval",
        document_artifact_id="artifact-documents",
        evidence_artifact_id="artifact-evidence",
    )
    second = DeterministicResearchSynthesizer().synthesize(
        "What is SPY?", docs, retrieval,
        retrieval_artifact_id="artifact-retrieval",
        document_artifact_id="artifact-documents",
        evidence_artifact_id="artifact-evidence",
    )
    assert first == second
    assert first.claims[0].claim_text == passage_text
    assert first.supports[0].quote == passage_text
    assert first.citations[0].passage_id == first.passages[0].passage_id
    assert first.claims[0].document_ids == ("doc-spy-factsheet",)
    assert first.coverage.coverage_ratio == 1.0
    assert first.synthesis_fingerprint == second.synthesis_fingerprint


def test_synthesis_marks_no_retrieval_as_unsupported() -> None:
    from market_os.adapters.lightrag import LightRAGFixtureAdapter

    adapter = LightRAGFixtureAdapter(
        Path(__file__).parent / "fixtures" / "lightrag" / "corpus.json",
        Path("D:/Code/Github/company-projects/LightRAG"),
        "missing-python",
    )
    retrieval = RetrievalResult(
        "unsupported query", ("doc-spy-factsheet",), (), (), "lightrag",
        "m2.2-lightrag-naive-v1", "2026-01-10T00:00:00+00:00",
        "2" * 64, (), error="no_results",
    )
    synthesis = DeterministicResearchSynthesizer().synthesize(
        "Unsupported requested statement", adapter.documents_for(("SPY",)), retrieval,
        retrieval_artifact_id="artifact-retrieval",
        document_artifact_id="artifact-documents",
        evidence_artifact_id="artifact-evidence",
    )
    assert not synthesis.claims
    assert synthesis.unsupported_claims[0].status == "unsupported"
    assert synthesis.coverage.coverage_ratio == 0.0
    assert synthesis.coverage.unsupported_claims == 1


class CitedFixtureProvider:
    def __init__(self):
        from market_os.adapters.lightrag import LightRAGFixtureAdapter

        self.adapter = LightRAGFixtureAdapter(
            Path(__file__).parent / "fixtures" / "lightrag" / "corpus.json",
            Path("D:/Code/Github/company-projects/LightRAG"),
            "missing-python",
        )
        self.last_documents = ()
        self.last_document_payload = []
        self.last_retrieval_result = None

    def retrieve(self, objective: str, symbols: tuple[str, ...], start: str, end: str):
        del start, end
        docs = self.adapter.documents_for(symbols)
        passages = tuple(
            RetrievedPassage(
                f"{doc.document_id}:fixture-passage",
                doc.document_id,
                self.adapter._contents[doc.document_id],
                rank,
                f"citation:{doc.document_id}:fixture-passage",
                doc.source_ref,
                doc.content_hash,
            )
            for rank, doc in enumerate(docs, 1)
        )
        self.last_retrieval_result = RetrievalResult(
            objective,
            tuple(doc.document_id for doc in docs),
            passages,
            tuple(passage.citation_ref for passage in passages),
            "lightrag",
            "test-double-v1",
            docs[0].retrieved_at,
            "3" * 64,
            tuple(doc.content_hash for doc in docs),
        )
        self.last_documents = docs
        self.last_document_payload = [
            {"document": asdict(doc), "content": self.adapter._contents[doc.document_id]}
            for doc in docs
        ]
        market = [Evidence("market-SPY", "market", "SPY bars", "fixture:market", "2026-01-06T00:00:00+00:00", "2026-01-06=102.00", ("SPY",))]
        return market + [
            Evidence(p.citation_ref, "document", p.passage_id, p.source_ref, docs[index].retrieved_at, p.text, docs[index].symbols)
            for index, p in enumerate(passages)
        ]

    def provider_metadata(self):
        return {"documents": {"provider": "lightrag", "provider_version": "test-double-v1"}}


class UnsupportedFixtureProvider(CitedFixtureProvider):
    def retrieve(self, objective: str, symbols: tuple[str, ...], start: str, end: str):
        del objective, start, end
        docs = self.adapter.documents_for(symbols)
        self.last_documents = docs
        self.last_document_payload = [
            {"document": asdict(doc), "content": self.adapter._contents[doc.document_id]}
            for doc in docs
        ]
        self.last_retrieval_result = RetrievalResult(
            "unsupported request", tuple(doc.document_id for doc in docs), (), (),
            "lightrag", "test-double-v1", docs[0].retrieved_at, "4" * 64,
            tuple(doc.content_hash for doc in docs), error="no_results",
        )
        return [Evidence("market-SPY", "market", "SPY bars", "fixture:market", "2026-01-06T00:00:00+00:00", "2026-01-06=102.00", ("SPY",))]


def test_workflow_inspection_reads_persisted_cited_research_without_provider_call(tmp_path: Path) -> None:
    provider = CitedFixtureProvider()
    workflow = MarketWorkflow(RunStore(tmp_path), evidence_provider=provider)
    task = workflow.create_task("Inspect research", ["SPY"], "2026-01-02", "2026-01-06", idempotency_key="inspect-research")
    result = workflow.run(task)
    assert result["run"]["status"] == "completed"
    assert result["cited_research"]["coverage"]["coverage_ratio"] == 1.0
    calls_before = provider.last_retrieval_result

    restarted = MarketWorkflow(RunStore(tmp_path))
    docs = restarted.inspect_resource(result["run"]["run_id"], "documents")
    passages = restarted.inspect_resource(result["run"]["run_id"], "passages")
    claims = restarted.inspect_resource(result["run"]["run_id"], "claims")
    claim_id = claims["claims"][0]["claim_id"]
    citations = restarted.inspect_resource(result["run"]["run_id"], "citations", claim_id)
    passage_claims = restarted.inspect_resource(result["run"]["run_id"], "passage-claims", passages["passages"][0]["passage_id"])
    lineage = restarted.inspect_resource(result["run"]["run_id"], "lineage", next(a["artifact_id"] for a in result["artifacts"] if a["kind"] == "cited-research"))
    assert docs["documents"]
    assert passages["passages"]
    assert citations["citations"]
    assert passage_claims["claims"]
    assert lineage["lineage"]
    assert provider.last_retrieval_result is calls_before


def test_workflow_persists_and_inspects_unsupported_claims(tmp_path: Path) -> None:
    workflow = MarketWorkflow(RunStore(tmp_path), evidence_provider=UnsupportedFixtureProvider())
    result = workflow.run(workflow.create_task("Unsupported request", ["SPY"], "2026-01-02", "2026-01-06"))
    assert result["cited_research"]["unsupported_claims"]
    assert result["cited_research"]["coverage"]["coverage_ratio"] == 0.0
    unsupported = workflow.inspect_resource(result["run"]["run_id"], "unsupported-claims")
    assert unsupported["unsupported_claims"]


@pytest.mark.parametrize("resource,item_id", [("documents", "missing-doc"), ("passages", "missing-passage"), ("claims", "missing-claim")])
def test_inspection_rejects_unknown_research_items(tmp_path: Path, resource: str, item_id: str) -> None:
    workflow = MarketWorkflow(RunStore(tmp_path), evidence_provider=CitedFixtureProvider())
    result = workflow.run(workflow.create_task("Inspect", ["SPY"], "2026-01-02", "2026-01-06"))
    with pytest.raises(KeyError):
        workflow.inspect_resource(result["run"]["run_id"], resource, item_id)


def test_inspection_detects_tampered_document_and_missing_lineage(tmp_path: Path) -> None:
    workflow = MarketWorkflow(RunStore(tmp_path), evidence_provider=CitedFixtureProvider())
    result = workflow.run(workflow.create_task("Integrity", ["SPY"], "2026-01-02", "2026-01-06"))
    document_artifact = next(item for item in result["artifacts"] if item["kind"] == "documents")
    path = Path(document_artifact["path"])
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload[0]["content"] = "tampered"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="content hash mismatch"):
        workflow.inspect_resource(result["run"]["run_id"], "documents")

    lineage_root = tmp_path / "lineage"
    lineage_workflow = MarketWorkflow(RunStore(lineage_root), evidence_provider=CitedFixtureProvider())
    lineage_result = lineage_workflow.run(lineage_workflow.create_task("Lineage", ["SPY"], "2026-01-02", "2026-01-06"))
    retrieval_artifact = next(item for item in lineage_result["artifacts"] if item["kind"] == "retrieval")
    index_path = RunStore(lineage_root).artifact_index
    entries = [json.loads(line) for line in index_path.read_text(encoding="utf-8").splitlines() if line]
    for entry in entries:
        if entry["artifact_id"] == retrieval_artifact["artifact_id"]:
            entry["lineage"] = ["artifact-missing-parent"]
    index_path.write_text("\n".join(json.dumps(item, sort_keys=True) for item in entries) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="lineage is incomplete"):
        lineage_workflow.inspect_resource(lineage_result["run"]["run_id"], "passages")


def test_cli_inspects_document_resource(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    workflow = MarketWorkflow(RunStore(tmp_path), evidence_provider=CitedFixtureProvider())
    result = workflow.run(workflow.create_task("CLI inspect", ["SPY"], "2026-01-02", "2026-01-06"))
    monkeypatch.setattr(cli, "MarketWorkflow", lambda store=None: MarketWorkflow(store or tmp_path))
    assert cli.main(["inspect", result["run"]["run_id"], "--store-root", str(tmp_path), "--resource", "documents"]) == 0
    assert json.loads(capsys.readouterr().out)["documents"]


def test_api_inspects_claim_citations_read_only(tmp_path: Path) -> None:
    workflow = MarketWorkflow(RunStore(tmp_path), evidence_provider=CitedFixtureProvider())
    result = workflow.run(workflow.create_task("API inspect", ["SPY"], "2026-01-02", "2026-01-06"))
    claim_id = result["cited_research"]["claims"][0]["claim_id"]
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(MarketWorkflow(RunStore(tmp_path))))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/v1/runs/{result['run']['run_id']}/research/citations/{claim_id}"
        response = json.loads(urllib.request.urlopen(url, timeout=5).read())
        assert response["citations"]
    finally:
        server.shutdown()
        thread.join(timeout=2)
