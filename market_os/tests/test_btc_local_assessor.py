from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
import time
from typing import Any

from market_os.btc_local_assessor import LocalAssessorError, LocalB31Assessor
from market_os.btc_local_assessor_store import LocalAssessmentStore, LocalAssessmentStoreError
from market_os.btc_question_evaluation import B31Status


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _packet() -> dict[str, Any]:
    now = time.time_ns() // 1_000_000
    core: dict[str, Any] = {
        "schema_id": "market-os.b3-1.evidence-packet-profile",
        "version": "v1",
        "observation_id": "synthetic-btc-observation-001",
        "stable_hypothesis_ids": ["h-up", "h-nonpositive"],
        "timestamps": {
            "decision_eligible_at_ms": now - 1_000,
            "packet_available_at_ms": now - 1_000,
            "packet_ready_at_ms": now - 500,
            "declared_assessment_use_time_ms": now - 500,
            "fresh_until_ms": now + 300_000,
            "expires_at_ms": now + 300_000,
            "max_response_latency_ms": 0,
        },
        "target_definition_id": "btc.b2.close-return-5m",
        "target_version": "v1",
        "assessment_configuration_id": "market-os.b3-1.normalized-assessment@v1",
        "question_ids": [
            "market-os.b3-1.question.evidence-support@v1",
            "market-os.b3-1.question.agreement-contradiction@v1",
            "market-os.b3-1.question.abstention@v1",
        ],
        "market": {"venue": "binance", "symbol": "BTCUSDT", "market_type": "spot", "interval": "1m"},
        "hypotheses": [
            {
                "hypothesis_id": "h-up",
                "claim": "Synthetic fixture hypothesis: supplied evidence is compatible with a positive five-minute BTC return claim.",
                "target_definition_id": "btc.b2.close-return-5m",
                "target_version": "v1",
                "horizon_minutes": 5,
                "observation_close_time_ms": now - 120_000,
            },
            {
                "hypothesis_id": "h-nonpositive",
                "claim": "Synthetic fixture hypothesis: supplied evidence is compatible with a non-positive five-minute BTC return claim.",
                "target_definition_id": "btc.b2.close-return-5m",
                "target_version": "v1",
                "horizon_minutes": 5,
                "observation_close_time_ms": now - 120_000,
            },
        ],
        "numerical_context": {"data_status": "synthetic_fixture", "baseline_score": 0.52},
        "evidence": [
            {
                "citation_ref": "fixture:citation-a",
                "source_ref": "fixture:source-a",
                "text": "Synthetic fixture source A describes a positive directional indicator. It is not a real observation.",
                "published_at": "2026-11-19T00:00:00Z",
                "available_at_ms": now - 1_000,
                "event_start_ms": now - 120_000,
                "event_end_ms": now - 60_000,
                "dependency_group_id": "group-a",
            },
            {
                "citation_ref": "fixture:citation-b",
                "source_ref": "fixture:source-b",
                "text": "Synthetic fixture source B describes a conflicting directional indicator. It is not a real observation.",
                "published_at": "2026-11-19T00:00:00Z",
                "available_at_ms": now - 1_000,
                "event_start_ms": now - 120_000,
                "event_end_ms": now - 60_000,
                "dependency_group_id": "group-b",
            },
        ],
        "hypothesis_evidence_groups": {"h-up": ["group-a"], "h-nonpositive": ["group-b"]},
        "independent_evidence_groups": ["group-a", "group-b"],
        "provenance": {"complete": True, "source_refs": ["fixture:source-a", "fixture:source-b"]},
        "quality": {"valid": True},
        "lineage": {"dataset_revision": "synthetic-only", "feature_fingerprint": "not-a-market-observation"},
    }
    core["packet_fingerprint"] = hashlib.sha256(_canonical(core)).hexdigest()
    return core


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
