from __future__ import annotations

import json
from pathlib import Path
from dataclasses import asdict

import pytest

from market_os.btc_b31 import (
    AGREEMENT_LABELS,
    B31_ABSTENTION_SCHEMA_ID,
    B31_AGREEMENT_CONTRADICTION_SCHEMA_ID,
    B31_EVIDENCE_SUPPORT_SCHEMA_ID,
    B31Status,
    B31_ABSTENTION_ID,
    B31_AGREEMENT_CONTRADICTION_ID,
    B31_EVIDENCE_PACKET_PROFILE_ID,
    B31_EVIDENCE_SUPPORT_ID,
    B31_NORMALIZED_ASSESSMENT_ID,
    B31EvidencePacketProfile,
    B31Timestamps,
    diagnostic_ranking,
    normalize_b31_assessment,
    parse_evidence_support_result,
    validate_future_free_packet,
)


FIXTURE = Path(__file__).parent / "fixtures" / "btc_b31" / "recorded_assessments.json"


def _timestamps(*, received: int | None = 120, use: int = 120, fresh: int = 200, deadline: int = 150) -> B31Timestamps:
    return B31Timestamps(
        decision_eligible_at_ms=100,
        packet_available_at_ms=100,
        packet_ready_at_ms=110,
        request_started_at_ms=110,
        response_deadline_at_ms=deadline,
        response_received_at_ms=received,
        available_at_ms=received,
        fresh_until_ms=fresh,
        declared_assessment_use_time_ms=use,
        max_response_latency_ms=40,
    )


def _packet(ids: tuple[str, ...] = ("h1",), **kwargs: object) -> B31EvidencePacketProfile:
    return B31EvidencePacketProfile(
        observation_id="obs-1",
        packet_fingerprint="packet-1",
        stable_hypothesis_ids=ids,
        timestamps=_timestamps(**kwargs),
        hypothesis_evidence_groups={item: (f"group-{item}",) for item in ids},
    )


def _support(hypothesis_id: str, *, selected: str = "supported", probabilities: dict[str, float] | None = None, **kwargs: object) -> dict[str, object]:
    return {
        "schema_id": B31_EVIDENCE_SUPPORT_SCHEMA_ID,
        "version": "v1",
        "observation_id": "obs-1",
        "packet_fingerprint": "packet-1",
        "hypothesis_id": hypothesis_id,
        "selected_label": selected,
        "probabilities": probabilities or {"supported": 0.7, "mixed": 0.1, "unknown": 0.1, "unsupported": 0.1},
        "response_received_at_ms": kwargs.get("response_received_at_ms", 120),
        "available_at_ms": kwargs.get("available_at_ms", 120),
    }


def _agreement(hypothesis_id: str, *, selected: str = "unknown", comparison: tuple[str, ...] = (), groups: tuple[str, ...] = (), probabilities: dict[str, float] | None = None, **kwargs: object) -> dict[str, object]:
    return {
        "schema_id": B31_AGREEMENT_CONTRADICTION_SCHEMA_ID,
        "version": "v1",
        "observation_id": "obs-1",
        "packet_fingerprint": "packet-1",
        "hypothesis_id": hypothesis_id,
        "comparison_hypothesis_ids": list(comparison),
        "comparison_evidence_group_ids": list(groups),
        "selected_label": selected,
        "probabilities": probabilities or {"agreement": 0.1, "mixed": 0.1, "contradiction": 0.1, "unknown": 0.7},
        "response_received_at_ms": kwargs.get("response_received_at_ms", 120),
        "available_at_ms": kwargs.get("available_at_ms", 120),
    }


def _abstention(*, selected: str = "answerable", status: str | None = None, probabilities: dict[str, float] | None = None, **kwargs: object) -> dict[str, object]:
    result: dict[str, object] = {
        "schema_id": B31_ABSTENTION_SCHEMA_ID,
        "version": "v1",
        "observation_id": "obs-1",
        "packet_fingerprint": "packet-1",
        "selected_label": selected,
        "probabilities": probabilities or {"answerable": 0.8, "abstain": 0.2},
        "response_received_at_ms": kwargs.get("response_received_at_ms", 120),
        "available_at_ms": kwargs.get("available_at_ms", 120),
    }
    if status is not None:
        result["status"] = status
    return result


def _complete(ids: tuple[str, ...] = ("h1",), *, packet: B31EvidencePacketProfile | None = None):
    packet = packet or _packet(ids)
    support = [_support(item) for item in ids]
    agreement = [_agreement(item, comparison=(ids[1],) if len(ids) > 1 and item == ids[0] else (), groups=("group-independent",) if len(ids) > 1 and item == ids[0] else ()) for item in ids]
    if len(ids) > 1:
        agreement[1] = _agreement(ids[1], comparison=(ids[0],))
    return packet, support, agreement, _abstention()


def test_fixture_catalog_is_synthetic_and_complete() -> None:
    catalog = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert {item["kind"] for item in catalog["cases"]} >= {
        "valid", "malformed", "unsupported", "inconsistent", "stale", "late",
        "unavailable", "abstaining", "disagreement", "concentrated_valid", "partial", "cardinality",
    }


def test_canonical_identities_are_separate_from_symbolic_names() -> None:
    assert B31_EVIDENCE_PACKET_PROFILE_ID == "market-os.b3-1.evidence-packet-profile@v1"
    assert B31_EVIDENCE_SUPPORT_ID == "market-os.b3-1.question.evidence-support@v1"
    assert B31_AGREEMENT_CONTRADICTION_ID == "market-os.b3-1.question.agreement-contradiction@v1"
    assert B31_ABSTENTION_ID == "market-os.b3-1.question.abstention@v1"
    assert B31_NORMALIZED_ASSESSMENT_ID == "market-os.b3-1.normalized-assessment@v1"
    assert _packet().question_ids == (
        B31_EVIDENCE_SUPPORT_ID,
        B31_AGREEMENT_CONTRADICTION_ID,
        B31_ABSTENTION_ID,
    )


def test_recorded_fixture_cases_normalize_to_declared_statuses() -> None:
    catalog = json.loads((Path(__file__).parent / "fixtures" / "btc_b31" / "recorded_assessments.json").read_text(encoding="utf-8"))
    for case in catalog["cases"]:
        result = normalize_b31_assessment(
            case["packet"], case["support_results"], case["agreement_results"], case["abstention_result"]
        )
        assert result.status == case["expected_status"], case["case_id"]


def test_fixture_cases_include_unsupported_configuration_stale_response_and_unavailable_response() -> None:
    catalog = json.loads((Path(__file__).parent / "fixtures" / "btc_b31" / "recorded_assessments.json").read_text(encoding="utf-8"))
    cases = {case["case_id"]: case for case in catalog["cases"]}
    assert cases["unsupported"]["support_results"][0]["assessment_configuration_id"].endswith("@v9")
    assert cases["stale"]["support_results"][0]["fresh_until_ms"] == 119
    assert cases["unavailable"]["support_results"] == []


@pytest.mark.parametrize("ids", [(), ("h1",), ("h1", "h2", "h3")])
def test_cardinality_rules(ids: tuple[str, ...]) -> None:
    packet = _packet(ids)
    support = [_support(item) for item in ids]
    agreement = [_agreement(item, comparison=(ids[1],) if len(ids) > 1 and item == ids[0] else (), groups=("group-independent",) if len(ids) > 1 and item == ids[0] else ()) for item in ids]
    if len(ids) > 1:
        agreement[1:] = [_agreement(item, comparison=(ids[0],)) for item in ids[1:]]
    abstain = _abstention(selected="abstain", probabilities={"answerable": 0.2, "abstain": 0.8}) if not ids else _abstention()
    result = normalize_b31_assessment(packet, support, agreement, abstain)
    assert len(result.support_results) == len(ids)
    assert len(result.agreement_results) == len(ids)
    assert result.abstention_result is not None
    assert result.status == (B31Status.ABSTAINED.value if not ids else B31Status.USABLE.value)


def test_packet_abstain_label_normalizes_child_status_and_reason() -> None:
    packet, support, agreement, _ = _complete()
    abstain = _abstention(
        selected="abstain",
        probabilities={"answerable": 0.2, "abstain": 0.8},
    )
    result = normalize_b31_assessment(packet, support, agreement, abstain)
    assert result.status == B31Status.ABSTAINED.value
    assert result.abstention_result is not None
    assert result.abstention_result.status == B31Status.ABSTAINED.value
    assert result.abstention_result.reason == "selected_abstain"

    answerable = normalize_b31_assessment(packet, support, agreement, _abstention())
    assert answerable.status == B31Status.USABLE.value
    assert answerable.abstention_result is not None
    assert answerable.abstention_result.status == B31Status.USABLE.value


def test_h1_agreement_must_be_unknown_and_unknown_support_is_usable() -> None:
    packet, support, _, abstain = _complete()
    agreement = [_agreement("h1", selected="agreement", comparison=("h1",))]
    result = normalize_b31_assessment(packet, support, agreement, abstain)
    assert result.status == B31Status.INTERNALLY_INCONSISTENT.value
    agreement = [_agreement("h1")]
    support = [_support("h1", selected="unknown", probabilities={"supported": 0.1, "mixed": 0.1, "unknown": 0.7, "unsupported": 0.1})]
    result = normalize_b31_assessment(packet, support, agreement, abstain)
    assert result.status == B31Status.USABLE.value


def test_no_self_corroboration_and_distinct_comparison_required() -> None:
    packet, support, _, abstain = _complete(("h1", "h2"))
    result = normalize_b31_assessment(packet, support, [_agreement("h1", selected="agreement", comparison=("h1",)) , _agreement("h2", comparison=("h1",))], abstain)
    assert result.status == B31Status.INTERNALLY_INCONSISTENT.value


def test_status_precedence_all_terminal_levels() -> None:
    packet, support, agreement, abstain = _complete()
    cases = [
        ("schema_invalid", {"schema_id": B31_EVIDENCE_SUPPORT_SCHEMA_ID, "version": "v1"}),
        ("unsupported", dict(support[0], version="v9")),
        ("internally_inconsistent", dict(support[0], selected_label="mixed")),
    ]
    for expected, invalid in cases:
        assert normalize_b31_assessment(packet, [invalid], agreement, abstain).status == expected
    stale = _packet(fresh=119, use=120)
    assert normalize_b31_assessment(stale, support, agreement, abstain).status == "stale"
    late = _packet()
    late = B31EvidencePacketProfile(
        observation_id=late.observation_id,
        packet_fingerprint=late.packet_fingerprint,
        stable_hypothesis_ids=late.stable_hypothesis_ids,
        timestamps=B31Timestamps(
            decision_eligible_at_ms=100, packet_available_at_ms=100, packet_ready_at_ms=110,
            request_started_at_ms=110, response_deadline_at_ms=115, response_received_at_ms=120,
            available_at_ms=120, fresh_until_ms=200, declared_assessment_use_time_ms=120,
            max_response_latency_ms=5,
        ),
        hypothesis_evidence_groups=late.hypothesis_evidence_groups,
    )
    assert normalize_b31_assessment(late, support, agreement, abstain).status == "unavailable"
    refused = dict(support[0], selected_label=None, probabilities=None, status="abstained", reason="explicit_refusal")
    assert normalize_b31_assessment(packet, [refused], agreement, abstain).status == "abstained"


def test_identity_conflict_and_result_timestamp_order_are_inconsistent() -> None:
    packet, support, agreement, abstain = _complete()
    conflict = dict(support[0], identity=B31_EVIDENCE_SUPPORT_SCHEMA_ID + "@v1", schema_id=B31_EVIDENCE_SUPPORT_SCHEMA_ID, version="v2")
    assert normalize_b31_assessment(packet, [conflict], agreement, abstain).status == "internally_inconsistent"
    bad_time = dict(support[0], request_started_at_ms=130, response_deadline_at_ms=170)
    assert normalize_b31_assessment(packet, [bad_time], agreement, abstain).status == "internally_inconsistent"
    malformed_market = dict(packet=packet, support_results=support, agreement_results=agreement, abstention_result=abstain)
    malformed_market["packet"] = {**malformed_market["packet"].__dict__, "market": []}
    assert normalize_b31_assessment(malformed_market["packet"], support, agreement, abstain).status == "schema_invalid"


def test_status_precedence_and_selected_distribution_validation() -> None:
    packet, support, agreement, abstain = _complete()
    bad = dict(support[0], selected_label="mixed")
    result = normalize_b31_assessment(packet, [bad], agreement, abstain)
    assert result.status == B31Status.INTERNALLY_INCONSISTENT.value
    bad = dict(support[0], schema_id="market-os.b3-1.question.evidence-support", version="v9")
    result = normalize_b31_assessment(packet, [bad], agreement, abstain)
    assert result.status == B31Status.UNSUPPORTED.value
    bad = dict(support[0], probabilities={"supported": 0.5, "mixed": 0.5, "unknown": 0.0, "unsupported": 0.0}, selected_label=None, status="abstained", reason="tied_maximum")
    result = normalize_b31_assessment(packet, [bad], agreement, abstain)
    assert result.status == B31Status.ABSTAINED.value


def test_timestamps_deadline_stale_late_and_recorded_availability() -> None:
    with pytest.raises(ValueError, match="response_deadline_at_ms"):
        B31Timestamps(request_started_at_ms=10, response_deadline_at_ms=12, max_response_latency_ms=5)
    packet, support, agreement, abstain = _complete()
    late = dict(support[0], response_received_at_ms=151, available_at_ms=151)
    result = normalize_b31_assessment(packet, [late], agreement, abstain)
    assert result.status == B31Status.UNAVAILABLE.value
    stale_packet = _packet(fresh=119, use=120)
    packet, support, agreement, abstain = _complete(packet=stale_packet)
    result = normalize_b31_assessment(packet, support, agreement, abstain)
    assert result.status == B31Status.STALE.value
    assert B31Timestamps(request_started_at_ms=10, response_received_at_ms=10, available_at_ms=10).available_at_ms == 10


def test_partial_results_are_unavailable_and_ranking_is_deterministic() -> None:
    packet = _packet(("b", "a"))
    result = normalize_b31_assessment(packet, [_support("a")], [_agreement("a", comparison=("b",)), _agreement("b", comparison=("a",))], _abstention())
    assert result.status == B31Status.UNAVAILABLE.value
    assert diagnostic_ranking(result) == ()
    packet, support, agreement, abstain = _complete(("b", "a"))
    support[0] = _support("b", probabilities={"supported": 0.7, "mixed": 0.1, "unknown": 0.1, "unsupported": 0.1})
    support[1] = _support("a", probabilities={"supported": 0.7, "mixed": 0.1, "unknown": 0.1, "unsupported": 0.1})
    result = normalize_b31_assessment(packet, support, agreement, abstain)
    assert result.status == B31Status.USABLE.value
    assert diagnostic_ranking(result) == ("a", "b")


def test_concentrated_output_and_valid_disagreement_remain_usable() -> None:
    packet = _packet(("h1", "h2"))
    support = [_support("h1", probabilities={"supported": 0.99, "mixed": 0.005, "unknown": 0.003, "unsupported": 0.002}), _support("h2", selected="mixed", probabilities={"supported": 0.1, "mixed": 0.8, "unknown": 0.05, "unsupported": 0.05})]
    agreement = [_agreement("h1", selected="contradiction", comparison=("h2",), probabilities={"agreement": 0.01, "mixed": 0.01, "contradiction": 0.97, "unknown": 0.01}), _agreement("h2", selected="contradiction", comparison=("h1",), probabilities={"agreement": 0.01, "mixed": 0.01, "contradiction": 0.97, "unknown": 0.01})]
    result = normalize_b31_assessment(packet, support, agreement, _abstention())
    assert result.status == B31Status.USABLE.value
    assert result.evidence_disagreement is True


def test_future_target_fields_are_rejected() -> None:
    for field in ("realized_label", "future_target_row", "future_return", "fills", "account_state", "target_return", "target_fingerprint"):
        with pytest.raises(ValueError, match="future-derived"):
            validate_future_free_packet({field: "future"})
    validate_future_free_packet({"target_definition_id": "btc.b2.close-return-5m.v1", "target_version": "v1"})


def test_normalized_artifact_retains_timestamps_and_concentration_diagnostics() -> None:
    packet, support, agreement, abstain = _complete()
    result = normalize_b31_assessment(packet, support, agreement, abstain)
    assert result.timestamps == packet.timestamps
    assert result.concentration == {"h1": 0.7}


def test_packet_quality_and_provenance_gates_are_deterministic() -> None:
    packet, support, agreement, abstain = _complete()
    raw = asdict(packet)
    raw["provenance_complete"] = False
    raw["quality_valid"] = True
    assert normalize_b31_assessment(raw, support, agreement, abstain).status == B31Status.INTERNALLY_INCONSISTENT.value


def test_no_external_transport_symbols_or_requests() -> None:
    import market_os.btc_b31 as module
    assert not hasattr(module, "request")
    assert not hasattr(module, "fetch")
    assert not hasattr(module, "urlopen")


def test_duplicate_and_foreign_hypothesis_ids_are_inconsistent() -> None:
    packet, support, agreement, abstain = _complete(("h1", "h2"))
    duplicate = normalize_b31_assessment(packet, support + [support[0]], agreement, abstain)
    assert duplicate.status == B31Status.INTERNALLY_INCONSISTENT.value
    foreign = normalize_b31_assessment(packet, [_support("foreign"), support[1]], agreement, abstain)
    assert foreign.status == B31Status.INTERNALLY_INCONSISTENT.value


def test_late_response_reason_is_preserved_and_stale_wins() -> None:
    packet = _packet()
    packet = B31EvidencePacketProfile(
        observation_id=packet.observation_id,
        packet_fingerprint=packet.packet_fingerprint,
        stable_hypothesis_ids=packet.stable_hypothesis_ids,
        timestamps=B31Timestamps(
            decision_eligible_at_ms=100, packet_available_at_ms=100, packet_ready_at_ms=110,
            request_started_at_ms=110, response_deadline_at_ms=115, response_received_at_ms=120,
            available_at_ms=120, fresh_until_ms=200, declared_assessment_use_time_ms=120,
            max_response_latency_ms=5,
        ),
        hypothesis_evidence_groups=packet.hypothesis_evidence_groups,
    )
    support = [_support("h1", response_received_at_ms=120, available_at_ms=120)]
    result = normalize_b31_assessment(packet, support, [_agreement("h1")], _abstention())
    assert result.status == B31Status.UNAVAILABLE.value
    assert "late" in result.reasons
    stale_packet = B31EvidencePacketProfile(
        observation_id=packet.observation_id,
        packet_fingerprint=packet.packet_fingerprint,
        stable_hypothesis_ids=packet.stable_hypothesis_ids,
        timestamps=B31Timestamps(
            decision_eligible_at_ms=100, packet_available_at_ms=100, packet_ready_at_ms=110,
            request_started_at_ms=110, response_deadline_at_ms=115, response_received_at_ms=120,
            available_at_ms=120, fresh_until_ms=119, declared_assessment_use_time_ms=120,
            max_response_latency_ms=5,
        ),
        hypothesis_evidence_groups=packet.hypothesis_evidence_groups,
    )
    result = normalize_b31_assessment(stale_packet, support, [_agreement("h1")], _abstention())
    assert result.status == B31Status.STALE.value


def test_result_clock_must_match_packet_clock() -> None:
    packet, support, agreement, abstain = _complete()
    support[0]["request_started_at_ms"] = 111
    support[0]["response_deadline_at_ms"] = 151
    result = normalize_b31_assessment(packet, support, agreement, abstain)
    assert result.status == B31Status.INTERNALLY_INCONSISTENT.value
