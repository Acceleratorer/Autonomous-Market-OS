from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
import json
import time
from typing import Any

from market_os.btc_evidence_packet import SourceTimeBounds, build_b31_evidence_packet
from market_os.btc_features import B2_FEATURE_VERSION
from market_os.btc_local_assessor import LocalAssessorError, LocalB31Assessor
from market_os.btc_local_assessor_store import LocalAssessmentStore, LocalAssessmentStoreError
from market_os.btc_question_evaluation import B31Status
from market_os.providers import DocumentRecord, LicenseMetadata, Provenance, RetrievedPassage, RetrievalResult


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _iso_ms(value: int) -> str:
    return datetime.fromtimestamp(value / 1000, timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _packet() -> dict[str, Any]:
    now = time.time_ns() // 1_000_000
    close_ms = now - 120_000
    decision_ms = close_ms + 50
    dataset_revision = "btc-local-assessor-synthetic-v1"
    input_refs = []
    for index, open_ms in enumerate([close_ms - 60_000, *range(close_ms - 360_000, close_ms - 60_000, 60_000)]):
        candle_close_ms = open_ms + 60_000
        source_ms = candle_close_ms
        received_ms = candle_close_ms + 50
        input_refs.append({
            "role": "current" if index == 0 else "lookback",
            "open_time_ms": open_ms,
            "close_time_ms": candle_close_ms,
            "source_timestamp": _iso_ms(source_ms),
            "received_at": _iso_ms(received_ms),
            "availability_timestamp": _iso_ms(received_ms),
            "canonical_fingerprint": hashlib.sha256(f"candle-{open_ms}".encode()).hexdigest(),
        })
    feature: dict[str, Any] = {
        "feature_version": B2_FEATURE_VERSION,
        "dataset_revision": dataset_revision,
        "close_time_ms": close_ms,
        "close_time": _iso_ms(close_ms),
        "source_timestamp": _iso_ms(close_ms),
        "received_at": _iso_ms(decision_ms),
        "availability_timestamp": _iso_ms(decision_ms),
        "decision_eligible_at": _iso_ms(decision_ms),
        "decision_eligible": True,
        "status": "eligible",
        "reason": None,
        "values": {"close": 100_000.0, "log_return_1m": 0.001, "log_return_5m": 0.002, "range_pct": 0.001, "log_volume": 1.0},
        "input_refs": input_refs,
    }
    feature["input_fingerprint"] = hashlib.sha256(_canonical({"dataset_revision": dataset_revision, "feature": feature})).hexdigest()

    receipt_ms = decision_ms - 25
    retrieval_ms = decision_ms + 10
    ready_ms = decision_ms + 20
    source_texts = (
        ("doc-a", "fixture:source-a", "fixture:citation-a", "group-a", "Synthetic fixture source A describes a positive directional indicator. It is not a real observation."),
        ("doc-b", "fixture:source-b", "fixture:citation-b", "group-b", "Synthetic fixture source B describes a conflicting directional indicator. It is not a real observation."),
    )
    documents = []
    passages = []
    source_times = {}
    for document_id, source_ref, citation_ref, group, text in source_texts:
        content_hash = hashlib.sha256(text.encode()).hexdigest()
        documents.append(DocumentRecord(
            document_id=document_id,
            title=f"Synthetic BTC evidence {document_id}",
            publisher="Market OS test fixture",
            source_ref=source_ref,
            published_at=_iso_ms(close_ms - 300_000),
            retrieved_at=_iso_ms(receipt_ms),
            symbols=("BTCUSDT",),
            media_type="text/plain",
            content_hash=content_hash,
            license=LicenseMetadata("synthetic_fixture"),
            provenance=Provenance("fixture", source_ref, _iso_ms(receipt_ms)),
        ))
        passages.append(RetrievedPassage(
            passage_id=f"passage-{document_id}",
            document_id=document_id,
            text=text,
            rank=len(passages) + 1,
            citation_ref=citation_ref,
            source_ref=source_ref,
            content_hash=content_hash,
        ))
        source_times[document_id] = SourceTimeBounds(
            event_start_ms=close_ms - 120_000,
            event_end_ms=close_ms,
            dependency_group_id=group,
            available_at_ms=receipt_ms,
            publication_time_status="recorded",
            clock_error_bound_ms=0,
        )
    retrieval = RetrievalResult(
        query="synthetic BTC evidence fixture",
        document_ids=tuple(document.document_id for document in documents),
        passages=tuple(passages),
        citations=tuple(passage.citation_ref for passage in passages),
        provider="minirag",
        provider_version="synthetic-fixture-v1",
        retrieved_at=_iso_ms(retrieval_ms),
        query_fingerprint=hashlib.sha256(b"synthetic-query").hexdigest(),
        content_fingerprints=tuple(document.content_hash for document in documents),
    )
    packet = build_b31_evidence_packet(
        feature,
        retrieval,
        documents,
        source_times,
        hypothesis_claim="Synthetic fixture hypothesis: supplied evidence is compatible with a positive five-minute BTC return claim.",
        packet_ready_at_ms=ready_ms,
        independent_evidence_group_ids=("group-a", "group-b"),
    )
    first = {**packet["hypotheses"][0], "hypothesis_id": "h-up"}
    second = {
        **first,
        "hypothesis_id": "h-nonpositive",
        "claim": "Synthetic fixture hypothesis: supplied evidence is compatible with a non-positive five-minute BTC return claim.",
    }
    packet["stable_hypothesis_ids"] = ["h-up", "h-nonpositive"]
    packet["hypotheses"] = [first, second]
    packet["hypothesis_evidence_groups"] = {"h-up": ["group-a"], "h-nonpositive": ["group-b"]}
    packet.pop("packet_fingerprint")
    packet["packet_fingerprint"] = hashlib.sha256(_canonical(packet)).hexdigest()
    return packet


def _usable_response(*, bad_citation: bool = False, self_comparison: bool = False) -> dict[str, Any]:
    agreement_up = {
        "hypothesis_id": "h-up",
        "label": "contradiction",
        "evidence_refs": ["fixture:citation-a", "fixture:citation-b"],
    }
    if self_comparison:
        agreement_up["comparison_hypothesis_ids"] = ["h-up"]
    return {
        "support": [
            {"hypothesis_id": "h-up", "label": "supported", "evidence_refs": ["fixture:outside"] if bad_citation else ["fixture:citation-a"]},
            {"hypothesis_id": "h-nonpositive", "label": "unsupported", "evidence_refs": ["fixture:citation-b"]},
        ],
        "agreement": [
            agreement_up,
            {
                "hypothesis_id": "h-nonpositive",
                "label": "contradiction",
                "evidence_refs": ["fixture:citation-a", "fixture:citation-b"],
            },
        ],
        "abstention": {
            "label": "answerable",
            "basis_hypothesis_ids": ["h-up", "h-nonpositive"],
            "evidence_refs": ["fixture:citation-a", "fixture:citation-b"],
        },
    }


@dataclass
class FakeRuntime:
    response: dict[str, Any]
    provider: str = "local_qwen_evidence_assessor"
    model: str = "Qwen/Qwen3-4B-GGUF"
    model_version: str = "synthetic-runtime-model-v1"
    runtime_version: str = "fake-local-runtime"
    manifest_fingerprint: str = "a" * 64

    def complete(self, messages: list[dict[str, str]], schema: dict[str, Any], *, timeout_seconds: float) -> tuple[dict[str, Any], int]:
        assert messages[0]["role"] == "system"
        assert schema["type"] == "object"
        assert 1 <= timeout_seconds <= 300
        return {"choices": [{"message": {"content": json.dumps(self.response)}}]}, 5


def test_local_assessor_normalizes_typed_results_without_claiming_jev() -> None:
    record = LocalB31Assessor(FakeRuntime(_usable_response())).assess(_packet())

    assert record.outcome == "usable"
    assert record.provider == "local_qwen_evidence_assessor"
    assert record.model != "Jev"
    assert record.calibration_status == "uncalibrated_hard_labels_one_hot_serialization"
    assert record.assessment is not None
    assert record.assessment["status"] == B31Status.USABLE.value
    assert record.assessment["agreement_results"][0]["selected_label"] == "contradiction"
    assert record.assessment["agreement_results"][0]["comparison_hypothesis_ids"] == ("h-nonpositive",)
    assert record.assessment["agreement_results"][0]["comparison_evidence_group_ids"] == ("group-b",)
    assert record.assessment["support_results"][0]["probabilities"] == {"supported": 1.0, "mixed": 0.0, "unknown": 0.0, "unsupported": 0.0}
    assert "market_probability_up" not in record.assessment


def test_local_assessor_rejects_model_citations_outside_the_packet() -> None:
    record = LocalB31Assessor(FakeRuntime(_usable_response(bad_citation=True))).assess(_packet())

    assert record.outcome == "rejected"
    assert record.failure is not None
    assert record.failure["code"] == "invalid_response"
    assert record.assessment is None


def test_self_comparison_is_rejected_before_normalization() -> None:
    record = LocalB31Assessor(FakeRuntime(_usable_response(self_comparison=True))).assess(_packet())

    assert record.outcome == "rejected"
    assert record.failure is not None
    assert record.failure["code"] == "invalid_response"


def test_model_abstention_remains_a_terminal_advisory_result() -> None:
    response = _usable_response()
    response["abstention"]["label"] = "abstain"
    record = LocalB31Assessor(FakeRuntime(response)).assess(_packet())

    assert record.outcome == "abstained"
    assert record.assessment is not None
    assert record.assessment["abstention_result"]["status"] == B31Status.ABSTAINED.value
    assert record.assessment["abstention_result"]["reason"] == "model_recommended_abstention"


def test_local_assessment_store_replays_without_calling_an_inference_runtime(tmp_path) -> None:
    packet = _packet()
    record = LocalB31Assessor(FakeRuntime(_usable_response())).assess(packet)
    store = LocalAssessmentStore(tmp_path)

    path = store.persist(packet, record)
    replay = store.replay(record.run_id)

    assert path.is_file()
    assert replay["status"] == "verified"
    assert replay["verification"] == "offline-packet-gates-and-response-normalization"
    assert replay["inference_calls"] == 0
    assert replay["network_requests"] == 0
    assert replay["packet_fingerprint"] == record.packet_fingerprint
    assert store.persist(packet, record) == path


def test_local_assessment_store_does_not_accept_a_jev_identity(tmp_path) -> None:
    packet = _packet()
    record = LocalB31Assessor(FakeRuntime(_usable_response())).assess(packet)

    try:
        LocalAssessmentStore(tmp_path).persist(packet, replace(record, provider="typesafe", model="jev-1.14.0"))
    except LocalAssessmentStoreError as exc:
        assert "pinned local Qwen" in str(exc)
    else:
        raise AssertionError("local assessment store accepted a hosted Jev identity")


def test_local_assessment_store_replays_typed_runtime_start_failure(tmp_path) -> None:
    class StartFailureRuntime(FakeRuntime):
        def start(self) -> None:
            raise LocalAssessorError("startup_timeout", "synthetic startup failure", retryable=True)

    packet = _packet()
    record = LocalB31Assessor(StartFailureRuntime(_usable_response())).assess(packet)
    store = LocalAssessmentStore(tmp_path)
    store.persist(packet, record)

    replay = store.replay(record.run_id)

    assert record.outcome == "unavailable"
    assert record.failure is not None
    assert record.failure["code"] == "startup_timeout"
    assert replay["status"] == "verified"


def test_local_assessment_store_rejects_modified_run_bundles(tmp_path) -> None:
    packet = _packet()
    record = LocalB31Assessor(FakeRuntime(_usable_response())).assess(packet)
    store = LocalAssessmentStore(tmp_path)
    path = store.persist(packet, record)
    bundle = json.loads(path.read_text(encoding="utf-8"))
    bundle["record"]["provider"] = "tampered-provider"
    path.write_text(json.dumps(bundle), encoding="utf-8")

    try:
        store.replay(record.run_id)
    except LocalAssessmentStoreError as exc:
        assert "fingerprint mismatch" in str(exc)
    else:
        raise AssertionError("modified local assessment run was accepted")
