"""Build a future-free B3.1 evidence packet from B2 and cited retrieval.

This module joins source lineage; it does not run Jev, make a market
prediction, calibrate probabilities, or create a trading decision.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from typing import Any, Mapping, Sequence

from .btc_features import B2_FEATURE_VERSION, B2_RUN_SCHEMA, B2_TARGET_VERSION
from .btc_question_evaluation import (
    B31_ABSTENTION_ID,
    B31_AGREEMENT_CONTRADICTION_ID,
    B31_EVIDENCE_PACKET_PROFILE_ID,
    B31_EVIDENCE_PACKET_PROFILE_SCHEMA_ID,
    B31_EVIDENCE_SUPPORT_ID,
    B31_NORMALIZED_ASSESSMENT_ID,
    B31_NORMALIZED_ASSESSMENT_SCHEMA_ID,
    B31Status,
    B31_VERSION,
    B31EvidencePacketProfile,
    B31NormalizedAssessment,
)
from .providers import DocumentRecord, RetrievalResult


_UTC = timezone.utc
_FEATURE_KEYS = {"close", "log_return_1m", "log_return_5m", "range_pct", "log_volume"}


class EvidencePacketError(ValueError):
    """A candidate observation cannot form a leakage-safe cited packet."""


@dataclass(frozen=True)
class SourceTimeBounds:
    """Event, availability, publication-status, and correlation lineage for one source."""

    event_start_ms: int
    event_end_ms: int
    dependency_group_id: str
    available_at_ms: int | None = None
    publication_time_status: str = "recorded"

    def __post_init__(self) -> None:
        for name in ("event_start_ms", "event_end_ms"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{name} must be an integer UTC millisecond timestamp")
        if self.event_start_ms > self.event_end_ms:
            raise ValueError("source event range is reversed")
        if self.available_at_ms is not None and (
            isinstance(self.available_at_ms, bool) or not isinstance(self.available_at_ms, int)
        ):
            raise ValueError("available_at_ms must be an integer UTC millisecond timestamp")
        if self.publication_time_status not in {"recorded", "unknown-not-captured"}:
            raise ValueError("publication_time_status must be recorded or unknown-not-captured")
        if not self.dependency_group_id.strip():
            raise ValueError("dependency_group_id is required")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _timestamp_ms(value: str, field: str) -> int:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError) as exc:
        raise EvidencePacketError(f"{field} must be an ISO-8601 UTC timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise EvidencePacketError(f"{field} must use UTC")
    return int(parsed.timestamp() * 1000)


def _validate_feature(feature: Mapping[str, Any]) -> tuple[str, int, int]:
    if feature.get("feature_version") != B2_FEATURE_VERSION or feature.get("status") != "eligible":
        raise EvidencePacketError("only an eligible row from the frozen B2 feature version can form a packet")
    if feature.get("decision_eligible") is not True:
        raise EvidencePacketError("B2 row is not marked decision_eligible")
    dataset_revision = feature.get("dataset_revision")
    fingerprint = feature.get("input_fingerprint")
    if not isinstance(dataset_revision, str) or not dataset_revision.strip():
        raise EvidencePacketError("B2 dataset_revision is required")
    if not isinstance(fingerprint, str) or len(fingerprint) != 64 or any(c not in "0123456789abcdef" for c in fingerprint):
        raise EvidencePacketError("B2 input_fingerprint must be a lowercase SHA-256 digest")
    fingerprint_projection = dict(feature)
    fingerprint_projection.pop("input_fingerprint", None)
    if _sha({"dataset_revision": dataset_revision, "feature": fingerprint_projection}) != fingerprint:
        raise EvidencePacketError("B2 input_fingerprint does not match the supplied feature row")
    close_ms = feature.get("close_time_ms")
    if isinstance(close_ms, bool) or not isinstance(close_ms, int):
        raise EvidencePacketError("B2 close_time_ms must be an integer UTC millisecond timestamp")
    if _timestamp_ms(feature.get("close_time", ""), "B2 close_time") != close_ms:
        raise EvidencePacketError("B2 close_time and close_time_ms disagree")
    decision_ms = _timestamp_ms(feature.get("decision_eligible_at", ""), "B2 decision_eligible_at")
    if decision_ms < close_ms:
        raise EvidencePacketError("B2 decision eligibility cannot precede the feature close")
    values = feature.get("values")
    if not isinstance(values, Mapping) or set(values) != _FEATURE_KEYS:
        raise EvidencePacketError("B2 numerical values do not match the frozen feature set")
    for name, value in values.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise EvidencePacketError(f"B2 feature {name} must be finite")
    refs = feature.get("input_refs")
    if not isinstance(refs, list) or len(refs) != 6:
        raise EvidencePacketError("B2 packet requires the current candle and five lookback references")
    if any(not isinstance(ref, Mapping) for ref in refs):
        raise EvidencePacketError("B2 input references must be objects")
    expected_open_times = [close_ms - 60_000, *range(close_ms - 360_000, close_ms - 60_000, 60_000)]
    if refs[0].get("role") != "current" or [ref.get("open_time_ms") for ref in refs] != expected_open_times:
        raise EvidencePacketError("B2 candle references do not match the current row and five contiguous lookbacks")
    for index, ref in enumerate(refs):
        if ref.get("role") != ("current" if index == 0 else "lookback"):
            raise EvidencePacketError("B2 candle reference roles are invalid")
        if ref.get("close_time_ms") != ref["open_time_ms"] + 60_000:
            raise EvidencePacketError("B2 candle reference close time is inconsistent")
        if ref.get("canonical_fingerprint") is None:
            raise EvidencePacketError("B2 input reference is missing canonical candle lineage")
        digest = str(ref["canonical_fingerprint"])
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise EvidencePacketError("B2 candle fingerprint must be a lowercase SHA-256 digest")
        if ref["close_time_ms"] > close_ms:
            raise EvidencePacketError("B2 input reference contains an event after the observation close")
        if _timestamp_ms(str(ref.get("availability_timestamp", "")), "B2 input availability") > decision_ms:
            raise EvidencePacketError("B2 input candle was unavailable at feature decision eligibility")
    return dataset_revision, close_ms, decision_ms


def observation_id_for_b2_feature(feature: Mapping[str, Any]) -> str:
    """Return the stable observation key shared by B2 controls and B3.1 packets."""
    dataset_revision, close_ms, _ = _validate_feature(feature)
    return f"btc:{dataset_revision}:{close_ms}:{feature['input_fingerprint'][:16]}"


def build_b31_evidence_packet(
    feature: Mapping[str, Any],
    retrieval: RetrievalResult,
    documents: Sequence[DocumentRecord],
    source_time_bounds: Mapping[str, SourceTimeBounds],
    *,
    hypothesis_claim: str,
    packet_ready_at_ms: int | None = None,
    target_definition_id: str = "btc.b2.close-return-5m",
    independent_evidence_group_ids: Sequence[str] = (),
) -> dict[str, Any]:
    """Create a canonical B3.1 packet for one point-in-time BTC feature row.

    ``source_time_bounds`` supplies each retrieved document's event-time span
    and correlation group. A source may support a packet only if its event
    range ends by the B2 observation close and it was available by packet
    readiness. Independent groups must be named explicitly by the caller.
    """
    dataset_revision, close_ms, feature_decision_ms = _validate_feature(feature)
    if not isinstance(hypothesis_claim, str) or not hypothesis_claim.strip():
        raise EvidencePacketError("hypothesis_claim is required")
    if retrieval.provider != "minirag":
        raise EvidencePacketError("BTC evidence packets require the MiniRAG retrieval path")
    if retrieval.error or not retrieval.passages:
        raise EvidencePacketError("MiniRAG must return at least one cited passage")
    if retrieval.query_fingerprint == "" or not retrieval.content_fingerprints:
        raise EvidencePacketError("MiniRAG retrieval lineage is incomplete")
    retrieval_ms = _timestamp_ms(retrieval.retrieved_at, "MiniRAG retrieved_at")
    documents_by_id = {document.document_id: document for document in documents}
    if len(documents_by_id) != len(documents):
        raise EvidencePacketError("document IDs must be unique")
    if len(retrieval.document_ids) != len(documents_by_id) or set(retrieval.document_ids) != set(documents_by_id):
        raise EvidencePacketError("MiniRAG retrieval and packet documents do not share the same document set")
    if len(retrieval.content_fingerprints) != len(retrieval.document_ids):
        raise EvidencePacketError("MiniRAG content fingerprints do not cover every input document")
    for document_id, content_fingerprint in zip(retrieval.document_ids, retrieval.content_fingerprints):
        document = documents_by_id.get(document_id)
        if document is None or document.content_hash != content_fingerprint:
            raise EvidencePacketError("MiniRAG content fingerprints disagree with document lineage")

    passage_evidence: list[dict[str, Any]] = []
    dependency_groups: set[str] = set()
    source_refs: list[str] = []
    source_availability_times = [feature_decision_ms]
    seen_passages: set[str] = set()
    for passage in retrieval.passages:
        if passage.citation_ref in seen_passages:
            raise EvidencePacketError(f"duplicate MiniRAG citation: {passage.citation_ref}")
        if passage.citation_ref not in retrieval.citations:
            raise EvidencePacketError(f"MiniRAG passage is missing from retrieval citations: {passage.citation_ref}")
        seen_passages.add(passage.citation_ref)
        document = documents_by_id.get(passage.document_id)
        source_time = source_time_bounds.get(passage.document_id)
        if document is None or not isinstance(source_time, SourceTimeBounds):
            raise EvidencePacketError(f"missing source metadata for passage {passage.citation_ref}")
        if passage.source_ref != document.provenance.source_ref:
            raise EvidencePacketError(f"MiniRAG passage source reference disagrees with its document: {passage.citation_ref}")
        if source_time.event_end_ms > close_ms:
            raise EvidencePacketError(f"future event-time evidence is prohibited: {passage.citation_ref}")
        if source_time.publication_time_status != "recorded":
            raise EvidencePacketError(
                f"source publication time is unknown under strict recorded availability: {passage.citation_ref}"
            )
        published_ms = _timestamp_ms(document.published_at, "document published_at")
        if published_ms > close_ms:
            raise EvidencePacketError(f"evidence published after the observation close is prohibited: {passage.citation_ref}")
        document_available_ms = _timestamp_ms(document.retrieved_at, "document retrieved_at")
        source_available_ms = source_time.available_at_ms if source_time.available_at_ms is not None else 0
        available_ms = max(published_ms, document_available_ms, source_available_ms)
        if available_ms > feature_decision_ms:
            raise EvidencePacketError(
                f"evidence was unavailable at B2 decision eligibility: {passage.citation_ref}"
            )
        if available_ms > retrieval_ms:
            raise EvidencePacketError(f"passage was unavailable when MiniRAG ran: {passage.citation_ref}")
        source_availability_times.append(available_ms)
        dependency_groups.add(source_time.dependency_group_id)
        source_refs.extend((document.source_ref, passage.source_ref, passage.citation_ref))
        passage_evidence.append({
            "source_id": passage.document_id,
            "source_ref": document.source_ref,
            "passage_id": passage.passage_id,
            "citation_ref": passage.citation_ref,
            "text": passage.text,
            "content_hash": passage.content_hash,
            "document_content_hash": document.content_hash,
            "published_at": document.published_at,
            "available_at_ms": available_ms,
            "event_start_ms": source_time.event_start_ms,
            "event_end_ms": source_time.event_end_ms,
            "dependency_group_id": source_time.dependency_group_id,
            "retrieval": {
                "provider": retrieval.provider,
                "provider_version": retrieval.provider_version,
                "query_fingerprint": retrieval.query_fingerprint,
                "rank": passage.rank,
                "content_fingerprints": list(retrieval.content_fingerprints),
            },
        })

    # Keep the original B2 decision clock; later source arrival cannot move it.
    eligible_at_ms = feature_decision_ms
    packet_available_at_ms = max(source_availability_times)
    ready_at_ms = packet_ready_at_ms if packet_ready_at_ms is not None else retrieval_ms
    independent_groups = tuple(dict.fromkeys(independent_evidence_group_ids))
    if any(not isinstance(group, str) or not group.strip() for group in independent_groups):
        raise EvidencePacketError("independent evidence group IDs must be non-empty strings")
    if set(independent_groups) - dependency_groups:
        raise EvidencePacketError("independent evidence groups must be present in retrieved source lineage")

    observation_id = observation_id_for_b2_feature(feature)
    hypothesis_id = "hypothesis-" + _sha({
        "observation_id": observation_id,
        "target_definition_id": target_definition_id,
        "claim": hypothesis_claim,
    })[:24]
    feature_input = {
        "feature_version": B2_FEATURE_VERSION,
        "dataset_revision": dataset_revision,
        "close_time_ms": close_ms,
        "close_time": feature["close_time"],
        "decision_eligible_at": feature["decision_eligible_at"],
        "input_fingerprint": feature["input_fingerprint"],
        "values": dict(feature["values"]),
        "input_refs": [dict(ref) for ref in feature["input_refs"]],
    }
    source_refs.extend(
        f"binance-vision-candle:{ref['canonical_fingerprint']}"
        for ref in feature["input_refs"]
    )
    unique_source_refs = list(dict.fromkeys(source_refs))
    core: dict[str, Any] = {
        "schema_id": B31_EVIDENCE_PACKET_PROFILE_SCHEMA_ID,
        "version": B31_VERSION,
        "identity": B31_EVIDENCE_PACKET_PROFILE_ID,
        "observation_id": observation_id,
        "stable_hypothesis_ids": [hypothesis_id],
        "timestamps": {
            "decision_eligible_at_ms": eligible_at_ms,
            "packet_available_at_ms": packet_available_at_ms,
            "packet_ready_at_ms": ready_at_ms,
            "declared_assessment_use_time_ms": ready_at_ms,
            "max_response_latency_ms": 0,
        },
        "target_definition_id": target_definition_id,
        "target_version": B2_TARGET_VERSION,
        "assessment_configuration_id": B31_NORMALIZED_ASSESSMENT_ID,
        "question_ids": [B31_EVIDENCE_SUPPORT_ID, B31_AGREEMENT_CONTRADICTION_ID, B31_ABSTENTION_ID],
        "market": {"venue": "binance", "symbol": "BTCUSDT", "market_type": "spot", "interval": "1m"},
        "hypotheses": [{
            "hypothesis_id": hypothesis_id,
            "claim": hypothesis_claim,
            "target_definition_id": target_definition_id,
            "target_version": B2_TARGET_VERSION,
            "horizon_minutes": 5,
            "observation_close_time_ms": close_ms,
        }],
        "numerical_context": feature_input,
        "evidence": passage_evidence,
        "hypothesis_evidence_groups": {hypothesis_id: sorted(dependency_groups)},
        "independent_evidence_groups": list(independent_groups),
        "provenance": {
            "complete": True,
            "source_refs": unique_source_refs,
            "dataset_revision": dataset_revision,
            "feature_fingerprint": feature["input_fingerprint"],
            "retrieval_query_fingerprint": retrieval.query_fingerprint,
        },
        "quality": {
            "valid": True,
            "source_event_time_violations": 0,
            "unavailable_source_count": 0,
        },
        "lineage": {
            "b2_feature_version": B2_FEATURE_VERSION,
            "b2_target_version": B2_TARGET_VERSION,
            "dataset_revision": dataset_revision,
            "feature_fingerprint": feature["input_fingerprint"],
            "retrieval_provider": retrieval.provider,
            "retrieval_provider_version": retrieval.provider_version,
            "retrieval_query_fingerprint": retrieval.query_fingerprint,
        },
    }
    if packet_ready_at_ms is None:
        # Sample readiness after assembling and validating the packet inputs.
        ready_at_ms = max(retrieval_ms, int(datetime.now(_UTC).timestamp() * 1000))
    if (
        isinstance(ready_at_ms, bool)
        or not isinstance(ready_at_ms, int)
        or ready_at_ms < max(packet_available_at_ms, retrieval_ms)
    ):
        raise EvidencePacketError(
            "packet_ready_at_ms must be at or after source availability and retrieval completion"
        )
    core["timestamps"]["packet_ready_at_ms"] = ready_at_ms
    core["timestamps"]["declared_assessment_use_time_ms"] = ready_at_ms
    packet = {**core, "packet_fingerprint": _sha(core)}
    try:
        B31EvidencePacketProfile.from_dict(packet)
    except (TypeError, ValueError) as exc:
        raise EvidencePacketError(f"generated B3.1 packet failed its contract: {exc}") from exc
    return packet


def packet_fingerprint(packet: Mapping[str, Any]) -> str:
    """Return the canonical packet fingerprint after verifying its envelope."""
    supplied = packet.get("packet_fingerprint")
    core = {key: value for key, value in packet.items() if key != "packet_fingerprint"}
    computed = _sha(core)
    if supplied != computed:
        raise EvidencePacketError("packet_fingerprint does not match canonical packet content")
    return computed


def align_recorded_b31_assessments_to_b2(
    b2_run: Mapping[str, Any],
    packets: Sequence[Mapping[str, Any]],
    assessments: Sequence[B31NormalizedAssessment | Mapping[str, Any]],
    *,
    baseline_name: str,
    recorded_fixture_id: str,
) -> dict[str, Any]:
    """Align recorded B3.1 semantics to one B2 test baseline by observation.

    The result measures only matching and usable coverage. It intentionally
    computes no market metrics and never converts Jev label probabilities into
    return probabilities.
    """
    if not isinstance(b2_run, Mapping):
        raise EvidencePacketError("alignment requires a persisted B2 run contract")
    if b2_run.get("schema") != B2_RUN_SCHEMA:
        raise EvidencePacketError("alignment requires a persisted B2 run contract")
    run_id = b2_run.get("run_id")
    dataset_revision = b2_run.get("dataset_revision")
    feature_fingerprint = b2_run.get("feature_fingerprint")
    if not all(isinstance(value, str) and value.strip() for value in (run_id, dataset_revision, feature_fingerprint)):
        raise EvidencePacketError("B2 run identity and fingerprints are required")
    baselines = b2_run.get("baselines")
    if not isinstance(baseline_name, str) or not isinstance(baselines, (list, tuple)) or baseline_name not in baselines:
        raise EvidencePacketError("baseline_name must identify a baseline in this B2 run")
    if not isinstance(recorded_fixture_id, str) or not recorded_fixture_id.strip():
        raise EvidencePacketError("recorded_fixture_id is required")

    calibration_by_baseline = b2_run.get("calibration")
    if not isinstance(calibration_by_baseline, Mapping):
        raise EvidencePacketError("B2 run is missing calibration metadata")
    calibration = calibration_by_baseline.get(baseline_name)
    if not isinstance(calibration, Mapping) or calibration.get("status") not in {"measured", "unavailable"}:
        raise EvidencePacketError("B2 baseline calibration metadata is invalid")
    calibration_status = calibration["status"]
    calibration_method = calibration.get("method")
    calibration_n = calibration.get("n")
    if not isinstance(calibration_method, str) or not calibration_method.strip():
        raise EvidencePacketError("B2 baseline calibration method is missing")
    if isinstance(calibration_n, bool) or not isinstance(calibration_n, int) or calibration_n < 0:
        raise EvidencePacketError("B2 baseline calibration sample count is invalid")
    if (calibration_status == "measured") != (calibration_n > 0):
        raise EvidencePacketError("B2 baseline calibration status and sample count disagree")

    features = b2_run.get("features")
    predictions = b2_run.get("predictions")
    if not isinstance(features, list) or not isinstance(predictions, list):
        raise EvidencePacketError("B2 run is missing feature or prediction rows")
    feature_by_close: dict[int, Mapping[str, Any]] = {}
    for feature in features:
        if not isinstance(feature, Mapping) or feature.get("status") != "eligible":
            continue
        _validate_feature(feature)
        close_ms = feature["close_time_ms"]
        if close_ms in feature_by_close:
            raise EvidencePacketError("B2 run contains duplicate eligible feature close times")
        feature_by_close[close_ms] = feature

    packet_by_observation: dict[str, Mapping[str, Any]] = {}
    for packet in packets:
        if not isinstance(packet, Mapping):
            raise EvidencePacketError("B3.1 packets must be objects")
        observation_id = packet.get("observation_id")
        if not isinstance(observation_id, str) or not observation_id.strip():
            raise EvidencePacketError("B3.1 packet is missing observation_id")
        try:
            packet_fingerprint(packet)
        except (TypeError, ValueError) as exc:
            raise EvidencePacketError(f"B3.1 packet fingerprint is invalid: {exc}") from exc
        try:
            profile = B31EvidencePacketProfile.from_dict(packet)
        except (TypeError, ValueError) as exc:
            raise EvidencePacketError(f"B3.1 packet profile is invalid: {exc}") from exc
        if profile.timestamps.decision_eligible_at_ms is None:
            raise EvidencePacketError("B3.1 packet decision_eligible_at_ms is required for alignment")
        if profile.timestamps.packet_ready_at_ms is None:
            raise EvidencePacketError("B3.1 packet packet_ready_at_ms is required for alignment")
        if observation_id in packet_by_observation:
            raise EvidencePacketError(f"duplicate B3.1 packet observation: {observation_id}")
        provenance = packet.get("provenance")
        if not isinstance(provenance, Mapping) or provenance.get("dataset_revision") != dataset_revision:
            raise EvidencePacketError("packet dataset_revision does not match the B2 run")
        if not isinstance(packet.get("numerical_context"), Mapping):
            raise EvidencePacketError("B3.1 packet numerical_context must be an object")
        packet_by_observation[observation_id] = packet

    assessment_by_observation: dict[str, Mapping[str, Any]] = {}
    for assessment_value in assessments:
        if isinstance(assessment_value, B31NormalizedAssessment):
            assessment = assessment_value.as_dict()
        elif isinstance(assessment_value, Mapping):
            assessment = dict(assessment_value)
        else:
            raise EvidencePacketError("assessments must be normalized recorded results")
        if (
            assessment.get("schema_id") != B31_NORMALIZED_ASSESSMENT_SCHEMA_ID
            or assessment.get("version") != B31_VERSION
            or assessment.get("assessment_configuration_id") != B31_NORMALIZED_ASSESSMENT_ID
        ):
            raise EvidencePacketError("assessment has an unsupported normalized B3.1 identity")
        observation_id = assessment.get("observation_id")
        if not isinstance(observation_id, str) or not observation_id.strip():
            raise EvidencePacketError("normalized B3.1 assessment is missing observation_id")
        packet_fp = assessment.get("packet_fingerprint")
        if not isinstance(packet_fp, str) or len(packet_fp) != 64 or any(c not in "0123456789abcdef" for c in packet_fp):
            raise EvidencePacketError("normalized B3.1 assessment packet_fingerprint must be a lowercase SHA-256 digest")
        assessment_status = assessment.get("status")
        if not isinstance(assessment_status, str) or assessment_status not in {item.value for item in B31Status}:
            raise EvidencePacketError("normalized B3.1 assessment status is invalid")
        if assessment_status == B31Status.USABLE.value:
            support_results = assessment.get("support_results")
            agreement_results = assessment.get("agreement_results")
            abstention_result = assessment.get("abstention_result")
            concentration = assessment.get("concentration")
            timestamps = assessment.get("timestamps")
            if (
                not isinstance(support_results, (list, tuple)) or not support_results
                or not isinstance(agreement_results, (list, tuple)) or not agreement_results
                or not isinstance(abstention_result, Mapping)
                or not isinstance(concentration, Mapping)
                or not isinstance(timestamps, Mapping)
                or not isinstance(assessment.get("evidence_disagreement"), bool)
            ):
                raise EvidencePacketError("usable B3.1 assessment is missing normalized semantic results")
            semantic_results = (*support_results, *agreement_results, abstention_result)
            for result in semantic_results:
                if (
                    not isinstance(result, Mapping)
                    or result.get("status") != B31Status.USABLE.value
                    or not isinstance(result.get("selected_label"), str)
                    or not result["selected_label"].strip()
                    or not isinstance(result.get("probabilities"), Mapping)
                    or not result["probabilities"]
                    or result["selected_label"] not in result["probabilities"]
                ):
                    raise EvidencePacketError("usable B3.1 assessment contains an incomplete semantic result")
                for value in result["probabilities"].values():
                    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
                        raise EvidencePacketError("B3.1 semantic probabilities must be finite values in [0, 1]")
            for value in concentration.values():
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
                    raise EvidencePacketError("B3.1 concentration values must be finite probabilities")
        reasons = assessment.get("reasons", ())
        if not isinstance(reasons, (list, tuple)) or any(not isinstance(item, str) for item in reasons):
            raise EvidencePacketError("normalized B3.1 assessment reasons must be strings")
        if observation_id in assessment_by_observation:
            raise EvidencePacketError(f"duplicate B3.1 assessment observation: {observation_id}")
        assessment_by_observation[observation_id] = assessment

    selected_predictions: list[tuple[int, Mapping[str, Any]]] = []
    for prediction in predictions:
        if not isinstance(prediction, Mapping):
            raise EvidencePacketError("B2 predictions must be objects")
        if prediction.get("model") != baseline_name or prediction.get("split") != "test":
            continue
        close_ms = prediction.get("feature_close_time_ms")
        if isinstance(close_ms, bool) or not isinstance(close_ms, int):
            raise EvidencePacketError("B2 baseline test predictions need integer close times")
        selected_predictions.append((close_ms, prediction))
    selected_predictions.sort(key=lambda item: item[0])
    rows: list[dict[str, Any]] = []
    seen_close_times: set[int] = set()
    for close_ms, prediction in selected_predictions:
        if close_ms in seen_close_times:
            raise EvidencePacketError("B2 baseline test predictions need unique integer close times")
        seen_close_times.add(close_ms)
        feature = feature_by_close.get(close_ms)
        if feature is None:
            raise EvidencePacketError("B2 test prediction has no eligible feature row")
        observation_id = observation_id_for_b2_feature(feature)
        raw_probability = prediction.get("raw_probability_up")
        calibrated_probability = prediction.get("calibrated_probability_up")
        for name, value in (("raw_probability_up", raw_probability), ("calibrated_probability_up", calibrated_probability)):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
                raise EvidencePacketError(f"B2 {name} must be a finite probability")

        packet = packet_by_observation.get(observation_id)
        assessment = assessment_by_observation.get(observation_id)
        b2_decision_ms = _timestamp_ms(feature["decision_eligible_at"], "B2 decision_eligible_at")
        assessment_status = "unavailable"
        reason = "no matching packet or recorded assessment"
        semantic_result: dict[str, Any] | None = None
        matched_packet_fingerprint: str | None = None
        assessment_available_at_ms: int | None = None
        assessment_use_time_ms: int | None = None
        if packet is not None:
            numerical_context = packet["numerical_context"]
            provenance = packet["provenance"]
            if numerical_context.get("input_fingerprint") != feature.get("input_fingerprint"):
                raise EvidencePacketError("packet B2 feature fingerprint does not match the numerical control")
            if provenance.get("feature_fingerprint") != feature.get("input_fingerprint"):
                raise EvidencePacketError("packet provenance feature fingerprint does not match the B2 feature")
            if numerical_context.get("decision_eligible_at") != feature.get("decision_eligible_at"):
                raise EvidencePacketError("packet B2 decision clock does not match the numerical control")
            packet_decision_ms = packet["timestamps"]["decision_eligible_at_ms"]
            if packet_decision_ms != b2_decision_ms:
                raise EvidencePacketError("packet decision_eligible_at_ms does not match the B2 decision clock")
            matched_packet_fingerprint = str(packet["packet_fingerprint"])
        if assessment is not None:
            timestamps = assessment.get("timestamps")
            if timestamps is None:
                timestamps = {}
            elif not isinstance(timestamps, Mapping):
                raise EvidencePacketError("normalized B3.1 assessment timestamps must be an object")
            assessment_available_at_ms = timestamps.get("available_at_ms")
            assessment_use_time_ms = timestamps.get("declared_assessment_use_time_ms")
            for name, value in (
                ("available_at_ms", assessment_available_at_ms),
                ("declared_assessment_use_time_ms", assessment_use_time_ms),
            ):
                if value is not None and (isinstance(value, bool) or not isinstance(value, int)):
                    raise EvidencePacketError(
                        f"normalized B3.1 assessment {name} must be an integer millisecond timestamp"
                    )
            if packet is None:
                assessment_status = "internally_inconsistent"
                reason = "assessment has no matching evidence packet"
            elif assessment.get("packet_fingerprint") != packet["packet_fingerprint"]:
                assessment_status = "internally_inconsistent"
                reason = "assessment packet fingerprint does not match the packet"
            else:
                assessment_status = str(assessment.get("status", "unavailable"))
                reasons = assessment.get("reasons", ())
                reason = "; ".join(str(item) for item in reasons) if reasons else None
                if assessment_status == "usable":
                    semantic_result = {
                        "probability_semantics": "probabilities over question labels; never a BTC return probability",
                        "support_results": [dict(item) for item in assessment["support_results"]],
                        "agreement_results": [dict(item) for item in assessment["agreement_results"]],
                        "abstention_result": dict(assessment["abstention_result"]),
                        "evidence_disagreement": assessment["evidence_disagreement"],
                        "concentration": dict(assessment["concentration"]),
                    }
        rows.append({
            "observation_id": observation_id,
            "feature_close_time_ms": close_ms,
            "dataset_revision": dataset_revision,
            "feature_fingerprint": feature.get("input_fingerprint"),
            "baseline_name": baseline_name,
            "evidence_timing": {
                "b2_decision_eligible_at_ms": b2_decision_ms,
                "packet_ready_at_ms": packet["timestamps"]["packet_ready_at_ms"] if packet is not None else None,
                "packet_ready_by_b2_decision": (
                    packet["timestamps"]["packet_ready_at_ms"] <= b2_decision_ms
                    if packet is not None else None
                ),
                "assessment_available_at_ms": assessment_available_at_ms,
                "assessment_available_by_b2_decision": (
                    assessment_available_at_ms <= b2_decision_ms
                    if assessment_available_at_ms is not None else None
                ),
                "assessment_use_time_ms": assessment_use_time_ms,
            },
            "b2_control": {
                "raw_probability_up": float(raw_probability),
                "probability_up_after_calibration_step": float(calibrated_probability),
                "calibration_status": calibration_status,
                "probability_semantics": "B2 probability of positive five-minute log return",
            },
            "packet_fingerprint": matched_packet_fingerprint,
            "recorded_fixture_id": recorded_fixture_id,
            "assessment_status": assessment_status,
            "assessment_reason": reason,
            "jev_semantic_assessment": semantic_result,
        })

    status_counts: dict[str, int] = {}
    matched_ids: list[str] = []
    for row in rows:
        status = row["assessment_status"]
        status_counts[status] = status_counts.get(status, 0) + 1
        if status == "usable":
            matched_ids.append(row["observation_id"])
    alignment_core = {
        "schema": "market-os.btc-b31-b2-alignment.v1",
        "mode": "offline-recorded-only",
        "eligibility": "alignment-only-no-market-metrics",
        "b2_run_id": run_id,
        "dataset_revision": dataset_revision,
        "b2_feature_fingerprint": feature_fingerprint,
        "baseline_name": baseline_name,
        "calibration": {
            "status": calibration_status,
            "method": calibration_method,
            "n": calibration_n,
            "probability_falls_back_to_raw_when_unavailable": calibration_status == "unavailable",
        },
        "recorded_fixture_id": recorded_fixture_id,
        "candidate_n": len(rows),
        "matched_usable_n": len(matched_ids),
        "coverage": len(matched_ids) / len(rows) if rows else None,
        "assessment_status_counts": dict(sorted(status_counts.items())),
        "matched_observation_ids": matched_ids,
        "rows": rows,
    }
    return {**alignment_core, "alignment_fingerprint": _sha(alignment_core)}
