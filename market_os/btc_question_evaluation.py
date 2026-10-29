"""Offline B3.1 question contracts and deterministic normalization.

This module is deliberately fixture-only.  It contains no provider, network,
market-data, execution, or model-inference code.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass, replace
from enum import Enum
import math
from typing import Any, Mapping


# Symbolic names are intentionally separate from schema IDs and versions.
B31_EVIDENCE_PACKET_PROFILE = "B31_EVIDENCE_PACKET_PROFILE"
B31_EVIDENCE_SUPPORT_QUESTION = "B31_EVIDENCE_SUPPORT_QUESTION"
B31_AGREEMENT_CONTRADICTION_QUESTION = "B31_AGREEMENT_CONTRADICTION_QUESTION"
B31_ABSTENTION_QUESTION = "B31_ABSTENTION_QUESTION"
B31_NORMALIZED_ASSESSMENT = "B31_NORMALIZED_ASSESSMENT"

B31_VERSION = "v1"
B31_EVIDENCE_PACKET_PROFILE_SCHEMA_ID = "market-os.b3-1.evidence-packet-profile"
B31_EVIDENCE_SUPPORT_SCHEMA_ID = "market-os.b3-1.question.evidence-support"
B31_AGREEMENT_CONTRADICTION_SCHEMA_ID = "market-os.b3-1.question.agreement-contradiction"
B31_ABSTENTION_SCHEMA_ID = "market-os.b3-1.question.abstention"
B31_NORMALIZED_ASSESSMENT_SCHEMA_ID = "market-os.b3-1.normalized-assessment"
B31_EVIDENCE_PACKET_PROFILE_ID = f"{B31_EVIDENCE_PACKET_PROFILE_SCHEMA_ID}@{B31_VERSION}"
B31_EVIDENCE_SUPPORT_ID = f"{B31_EVIDENCE_SUPPORT_SCHEMA_ID}@{B31_VERSION}"
B31_AGREEMENT_CONTRADICTION_ID = f"{B31_AGREEMENT_CONTRADICTION_SCHEMA_ID}@{B31_VERSION}"
B31_ABSTENTION_ID = f"{B31_ABSTENTION_SCHEMA_ID}@{B31_VERSION}"
B31_NORMALIZED_ASSESSMENT_ID = f"{B31_NORMALIZED_ASSESSMENT_SCHEMA_ID}@{B31_VERSION}"
B31_EVIDENCE_PACKET_PROFILE_VERSION = B31_VERSION
B31_EVIDENCE_SUPPORT_VERSION = B31_VERSION
B31_AGREEMENT_CONTRADICTION_VERSION = B31_VERSION
B31_ABSTENTION_VERSION = B31_VERSION
B31_NORMALIZED_ASSESSMENT_VERSION = B31_VERSION

SUPPORT_LABELS = ("supported", "mixed", "unknown", "unsupported")
AGREEMENT_LABELS = ("agreement", "mixed", "contradiction", "unknown")
ABSTENTION_LABELS = ("answerable", "abstain")
STATUS_PRECEDENCE = (
    "schema_invalid",
    "unsupported",
    "internally_inconsistent",
    "stale",
    "unavailable",
    "abstained",
    "usable",
)
STATUS_RANK = {value: index for index, value in enumerate(STATUS_PRECEDENCE)}
SUPPORT_RANK = {"supported": 0, "mixed": 1, "unknown": 2, "unsupported": 3}


class B31Status(str, Enum):
    SCHEMA_INVALID = "schema_invalid"
    UNSUPPORTED = "unsupported"
    INTERNALLY_INCONSISTENT = "internally_inconsistent"
    STALE = "stale"
    UNAVAILABLE = "unavailable"
    ABSTAINED = "abstained"
    USABLE = "usable"


class SupportLabel(str, Enum):
    SUPPORTED = "supported"
    MIXED = "mixed"
    UNKNOWN = "unknown"
    UNSUPPORTED = "unsupported"


class AgreementLabel(str, Enum):
    AGREEMENT = "agreement"
    MIXED = "mixed"
    CONTRADICTION = "contradiction"
    UNKNOWN = "unknown"


class AbstentionLabel(str, Enum):
    ANSWERABLE = "answerable"
    ABSTAIN = "abstain"


AssessmentStatus = B31Status


class B31ContractError(ValueError):
    """A validation error with the terminal status it should produce."""

    def __init__(self, status: str, reason: str) -> None:
        super().__init__(reason)
        self.status = status
        self.reason = reason


class _B31ShapeError(ValueError):
    """Malformed serialized shape, distinct from a semantic inconsistency."""


def _status(value: str | B31Status) -> str:
    return value.value if isinstance(value, B31Status) else str(value)


def _as_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str) or not isinstance(value, (list, tuple, set)):
        raise _B31ShapeError("expected an array of identifiers")
    if any(not isinstance(item, str) for item in value):
        raise _B31ShapeError("identifier arrays must contain strings")
    return tuple(value)


def _int_ms(value: Any, field_name: str, *, allow_none: bool = True) -> int | None:
    if value is None and allow_none:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer millisecond timestamp")
    return value


def _finite_probability(value: Any, field_name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a finite probability")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a finite probability") from exc
    if not math.isfinite(result) or not 0 <= result <= 1:
        raise ValueError(f"{field_name} must be a finite probability")
    return result


def _fingerprint(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _identity(value: Any) -> tuple[str, str] | None:
    if not isinstance(value, str) or "@" not in value:
        return None
    schema_id, version = value.rsplit("@", 1)
    return schema_id, version


def _mapping(value: Any) -> dict[str, Any]:
    if is_dataclass(value):
        return asdict(value)
    if not isinstance(value, Mapping):
        raise B31ContractError("schema_invalid", "expected an object")
    return dict(value)


def _contains_future_fields(value: Any, path: str = "") -> str | None:
    """Reject target/outcome state while allowing target identity fields."""
    forbidden = {
        "realized_label", "realized_labels", "future_return", "future_returns",
        "target_return", "target_returns", "future_target", "future_target_row",
        "target_row", "target_fingerprint", "fills", "fill", "account_state",
        "account", "portfolio", "position", "positions", "orders", "trade",
        "trades", "execution", "future_rows", "realized_outcome", "future_outcome",
        "realized", "target_label", "target_labels",
    }
    if isinstance(value, Mapping):
        for key, child in value.items():
            name = str(key).lower()
            if name in forbidden or (name.startswith("target_") and name not in {"target_definition_id", "target_version"}) or ("future" in name and name not in {"future_free"}):
                return f"future-derived field is prohibited: {path + name}"
            if name == "target":
                return f"future-derived target object is prohibited: {path + name}"
            found = _contains_future_fields(child, path + name + ".")
            if found:
                return found
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            found = _contains_future_fields(child, f"{path}{index}.")
            if found:
                return found
    return None


@dataclass(frozen=True)
class B31Timestamps:
    decision_eligible_at_ms: int | None = None
    packet_available_at_ms: int | None = None
    packet_ready_at_ms: int | None = None
    request_started_at_ms: int | None = None
    response_deadline_at_ms: int | None = None
    response_received_at_ms: int | None = None
    available_at_ms: int | None = None
    fresh_until_ms: int | None = None
    expires_at_ms: int | None = None
    declared_assessment_use_time_ms: int | None = None
    max_response_latency_ms: int = 30_000

    def __post_init__(self) -> None:
        for name in (
            "decision_eligible_at_ms", "packet_available_at_ms", "packet_ready_at_ms",
            "request_started_at_ms", "response_deadline_at_ms", "response_received_at_ms",
            "available_at_ms", "fresh_until_ms", "expires_at_ms",
            "declared_assessment_use_time_ms",
        ):
            _int_ms(getattr(self, name), name)
        if isinstance(self.max_response_latency_ms, bool) or not isinstance(self.max_response_latency_ms, int) or self.max_response_latency_ms < 0:
            raise ValueError("max_response_latency_ms must be a non-negative integer")
        if self.request_started_at_ms is not None:
            expected = self.request_started_at_ms + self.max_response_latency_ms
            if self.response_deadline_at_ms is None:
                object.__setattr__(self, "response_deadline_at_ms", expected)
            elif self.response_deadline_at_ms != expected:
                raise ValueError("response_deadline_at_ms must equal request_started_at_ms + max_response_latency_ms")
        elif self.response_deadline_at_ms is not None:
            raise ValueError("response_deadline_at_ms requires request_started_at_ms")
        if self.available_at_ms != self.response_received_at_ms:
            if self.available_at_ms is not None or self.response_received_at_ms is not None:
                raise ValueError("available_at_ms must equal response_received_at_ms for recorded responses")
        if self.response_received_at_ms is not None and self.request_started_at_ms is None:
            raise ValueError("response_received_at_ms requires request_started_at_ms")
        self.validate_order()

    def validate_order(self) -> None:
        pairs = (
            (self.packet_available_at_ms, self.decision_eligible_at_ms, "packet availability cannot follow decision eligibility"),
            (self.decision_eligible_at_ms, self.packet_ready_at_ms, "decision eligibility cannot follow packet readiness"),
            (self.packet_ready_at_ms, self.request_started_at_ms, "request cannot start before packet readiness"),
            (self.request_started_at_ms, self.response_received_at_ms, "response cannot arrive before request start"),
            (self.response_received_at_ms, self.available_at_ms, "availability cannot precede response receipt"),
        )
        for earlier, later, message in pairs:
            if earlier is not None and later is not None and earlier > later:
                raise ValueError(message)


@dataclass(frozen=True)
class B31EvidencePacketProfile:
    schema_id: str = B31_EVIDENCE_PACKET_PROFILE_SCHEMA_ID
    version: str = B31_VERSION
    observation_id: str = ""
    packet_fingerprint: str = ""
    stable_hypothesis_ids: tuple[str, ...] = ()
    timestamps: B31Timestamps = field(default_factory=B31Timestamps)
    target_definition_id: str | None = None
    target_version: str | None = None
    assessment_configuration_id: str = B31_NORMALIZED_ASSESSMENT_ID
    question_ids: tuple[str, ...] = (
        B31_EVIDENCE_SUPPORT_ID,
        B31_AGREEMENT_CONTRADICTION_ID,
        B31_ABSTENTION_ID,
    )
    venue: str = "binance"
    symbol: str = "BTCUSDT"
    market_type: str = "spot"
    interval: str = "1m"
    hypothesis_evidence_groups: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    independent_evidence_groups: tuple[str, ...] = ()
    provenance_complete: bool = True
    source_refs: tuple[str, ...] = ()
    quality_valid: bool = True
    raw_packet: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.schema_id != B31_EVIDENCE_PACKET_PROFILE_SCHEMA_ID or self.version != B31_VERSION:
            raise ValueError("unsupported B3.1 evidence-packet profile identity")
        if self.assessment_configuration_id != B31_NORMALIZED_ASSESSMENT_ID:
            raise ValueError("unsupported B3.1 assessment configuration")
        if tuple(self.question_ids) != (
            B31_EVIDENCE_SUPPORT_ID,
            B31_AGREEMENT_CONTRADICTION_ID,
            B31_ABSTENTION_ID,
        ):
            raise ValueError("unsupported B3.1 question set")
        object.__setattr__(self, "question_ids", tuple(self.question_ids))
        if (self.venue, self.symbol, self.market_type, self.interval) != ("binance", "BTCUSDT", "spot", "1m"):
            raise ValueError("B3.1 is restricted to BTCUSDT Spot 1m")
        if not self.observation_id.strip() or not self.packet_fingerprint.strip():
            raise ValueError("observation_id and packet_fingerprint are required")
        ids = tuple(self.stable_hypothesis_ids)
        if any(not isinstance(item, str) for item in ids):
            raise ValueError("stable hypothesis IDs must be strings")
        if len(set(ids)) != len(ids) or any(not item.strip() for item in ids):
            raise ValueError("stable hypothesis IDs must be unique and non-empty")
        groups = {str(key): tuple(value) for key, value in self.hypothesis_evidence_groups.items()}
        if set(groups) - set(ids):
            raise ValueError("hypothesis evidence groups contain a foreign hypothesis ID")
        object.__setattr__(self, "stable_hypothesis_ids", ids)
        object.__setattr__(self, "hypothesis_evidence_groups", groups)
        object.__setattr__(self, "independent_evidence_groups", tuple(self.independent_evidence_groups))
        object.__setattr__(self, "source_refs", tuple(self.source_refs))
        if self.raw_packet is not None:
            found = _contains_future_fields(self.raw_packet)
            if found:
                raise ValueError(found)

    @property
    def identity(self) -> str:
        return f"{self.schema_id}@{self.version}"

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "B31EvidencePacketProfile":
        raw = _mapping(payload)
        found = _contains_future_fields(raw)
        if found:
            raise B31ContractError("internally_inconsistent", found)
        identity = raw.get("identity")
        schema_id = raw.get("schema_id")
        version = raw.get("version")
        if identity is not None and _identity(identity) is None:
            raise B31ContractError("schema_invalid", "packet profile identity must be schema_id@version")
        parsed_identity = _identity(identity) if identity is not None else None
        if parsed_identity and schema_id is None:
            schema_id, version = parsed_identity
        elif parsed_identity and (schema_id, version) != parsed_identity:
            raise B31ContractError("internally_inconsistent", "packet profile identity disagrees with schema_id/version")
        elif schema_id is None and raw.get("schema") is not None:
            schema_id = raw.get("schema")
            if isinstance(schema_id, str) and "@" in schema_id:
                schema_id, version = _identity(schema_id) or (schema_id, version)
        if schema_id is None or version is None:
            raise B31ContractError("schema_invalid", "packet profile is missing schema identity")
        if not isinstance(schema_id, str) or not isinstance(version, str):
            raise B31ContractError("schema_invalid", "packet profile schema identity must use strings")
        if schema_id != B31_EVIDENCE_PACKET_PROFILE_SCHEMA_ID or version != B31_VERSION:
            raise B31ContractError("unsupported", "unsupported B3.1 packet profile identity or version")
        ids = raw.get("stable_hypothesis_ids", raw.get("hypothesis_ids", ()))
        timestamp_payload = raw.get("timestamps", raw)
        if not isinstance(timestamp_payload, Mapping):
            raise B31ContractError("schema_invalid", "timestamps must be an object")
        try:
            if not str(raw.get("observation_id", "")).strip() or not str(raw.get("packet_fingerprint", raw.get("input_fingerprint", ""))).strip():
                raise B31ContractError("schema_invalid", "observation_id and packet_fingerprint are required")
            market = raw.get("market", {})
            if market is None:
                market = {}
            if not isinstance(market, Mapping):
                raise _B31ShapeError("market must be an object")
            provenance = raw.get("provenance", {})
            if provenance is None:
                provenance = {}
            if not isinstance(provenance, Mapping):
                raise _B31ShapeError("provenance must be an object")
            quality = raw.get("quality", {})
            if quality is None:
                quality = {}
            if not isinstance(quality, Mapping):
                raise _B31ShapeError("quality must be an object")
            provenance_complete = bool(provenance.get("complete", provenance.get("source_refs", True)))
            source_refs = provenance.get("source_refs", ())
            quality_valid = bool(quality.get("valid", not bool(quality.get("stale", False))))
            timestamps = B31Timestamps(**{
                key: timestamp_payload[key]
                for key in B31Timestamps.__dataclass_fields__
                if key in timestamp_payload
            })
            return cls(
                schema_id=schema_id,
                version=version,
                observation_id=str(raw.get("observation_id", "")),
                packet_fingerprint=str(raw.get("packet_fingerprint", raw.get("input_fingerprint", ""))),
                stable_hypothesis_ids=_as_tuple(ids),
                timestamps=timestamps,
                target_definition_id=raw.get("target_definition_id"),
                target_version=raw.get("target_version"),
                assessment_configuration_id=str(raw.get("assessment_configuration_id", B31_NORMALIZED_ASSESSMENT_ID)),
                question_ids=_as_tuple(raw.get("question_ids", (
                    B31_EVIDENCE_SUPPORT_ID,
                    B31_AGREEMENT_CONTRADICTION_ID,
                    B31_ABSTENTION_ID,
                ))),
                venue=str(market.get("venue", raw.get("venue", "binance"))),
                symbol=str(market.get("symbol", raw.get("symbol", "BTCUSDT"))),
                market_type=str(market.get("market_type", raw.get("market_type", "spot"))),
                interval=str(market.get("interval", raw.get("interval", "1m"))),
                hypothesis_evidence_groups=raw.get("hypothesis_evidence_groups", {}),
                independent_evidence_groups=_as_tuple(raw.get("independent_evidence_groups", ())),
                provenance_complete=provenance_complete,
                source_refs=_as_tuple(source_refs),
                quality_valid=quality_valid,
                raw_packet=raw,
            )
        except B31ContractError:
            raise
        except _B31ShapeError as exc:
            raise B31ContractError("schema_invalid", str(exc)) from exc
        except ValueError as exc:
            if str(exc).startswith("unsupported") or "restricted to BTCUSDT" in str(exc):
                raise B31ContractError("unsupported", str(exc)) from exc
            raise B31ContractError("internally_inconsistent", str(exc)) from exc
        except TypeError as exc:
            raise B31ContractError("internally_inconsistent", str(exc)) from exc


@dataclass(frozen=True)
class _B31ResultBase:
    schema_id: str = ""
    version: str = ""
    assessment_configuration_id: str = B31_NORMALIZED_ASSESSMENT_ID
    observation_id: str = ""
    packet_fingerprint: str = ""
    decision_eligible_at_ms: int | None = None
    packet_ready_at_ms: int | None = None
    request_started_at_ms: int | None = None
    response_deadline_at_ms: int | None = None
    selected_label: str | None = None
    probabilities: Mapping[str, float] | None = None
    status: str | None = None
    reason: str | None = None
    evidence_refs: tuple[str, ...] = ()
    response_fingerprint: str | None = None
    response_received_at_ms: int | None = None
    available_at_ms: int | None = None
    fresh_until_ms: int | None = None
    expires_at_ms: int | None = None
    declared_assessment_use_time_ms: int | None = None

    def __post_init__(self) -> None:
        if self.status is not None:
            object.__setattr__(self, "status", _status(self.status))
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))
        expected = {
            EvidenceSupportResult: B31_EVIDENCE_SUPPORT_SCHEMA_ID,
            AgreementContradictionResult: B31_AGREEMENT_CONTRADICTION_SCHEMA_ID,
            PacketAbstentionResult: B31_ABSTENTION_SCHEMA_ID,
        }.get(type(self))
        if expected is None or self.schema_id != expected or self.version != B31_VERSION:
            raise ValueError("unsupported B3.1 question result identity")
        if self.assessment_configuration_id != B31_NORMALIZED_ASSESSMENT_ID:
            raise ValueError("unsupported B3.1 assessment configuration")
        if not self.observation_id.strip() or not self.packet_fingerprint.strip():
            raise ValueError("question result packet identity is required")
        if self.status is not None and self.status not in STATUS_PRECEDENCE:
            raise ValueError("unsupported B3.1 question result status")
        for name in (
            "decision_eligible_at_ms", "packet_ready_at_ms", "request_started_at_ms",
            "response_deadline_at_ms", "response_received_at_ms", "available_at_ms",
            "fresh_until_ms", "expires_at_ms", "declared_assessment_use_time_ms",
        ):
            _int_ms(getattr(self, name), name)
        if self.request_started_at_ms is not None:
            if self.response_deadline_at_ms is None:
                raise ValueError("response_deadline_at_ms is required with request_started_at_ms")
            if self.response_deadline_at_ms < self.request_started_at_ms:
                raise ValueError("response_deadline_at_ms cannot precede request_started_at_ms")
        elif self.response_deadline_at_ms is not None:
            raise ValueError("response_deadline_at_ms requires request_started_at_ms")
        if self.decision_eligible_at_ms is not None and self.packet_ready_at_ms is not None and self.decision_eligible_at_ms > self.packet_ready_at_ms:
            raise ValueError("decision eligibility cannot follow packet readiness")
        if self.packet_ready_at_ms is not None and self.request_started_at_ms is not None and self.packet_ready_at_ms > self.request_started_at_ms:
            raise ValueError("request cannot start before packet readiness")
        if self.request_started_at_ms is not None and self.response_received_at_ms is not None and self.request_started_at_ms > self.response_received_at_ms:
            raise ValueError("response cannot arrive before request start")
        if self.available_at_ms != self.response_received_at_ms:
            if self.available_at_ms is not None or self.response_received_at_ms is not None:
                raise ValueError("available_at_ms must equal response_received_at_ms")
        labels = (
            SUPPORT_LABELS if isinstance(self, EvidenceSupportResult)
            else AGREEMENT_LABELS if isinstance(self, AgreementContradictionResult)
            else ABSTENTION_LABELS
        )
        if self.probabilities is None:
            if self.status not in {B31Status.ABSTAINED.value, B31Status.UNAVAILABLE.value, B31Status.STALE.value}:
                raise ValueError("question result probabilities are required")
        else:
            if set(self.probabilities) != set(labels):
                raise ValueError("question result probabilities must cover the closed label set")
            probabilities = {label: _finite_probability(self.probabilities[label], f"probabilities.{label}") for label in labels}
            if not math.isclose(sum(probabilities.values()), 1.0, abs_tol=1e-9):
                raise ValueError("question result probabilities must sum to one")
            object.__setattr__(self, "probabilities", probabilities)
            maximum = max(probabilities.values())
            maxima = [label for label, value in probabilities.items() if math.isclose(value, maximum, rel_tol=0.0, abs_tol=1e-12)]
            if len(maxima) > 1:
                if self.selected_label is not None or self.status != B31Status.ABSTAINED.value or self.reason != "tied_maximum":
                    raise ValueError("tied maximum requires abstention with reason tied_maximum")
            elif self.selected_label is None and self.status not in {B31Status.ABSTAINED.value, B31Status.UNAVAILABLE.value, B31Status.STALE.value}:
                raise ValueError("selected_label is required for a non-terminal result")
            elif self.selected_label is not None and self.selected_label not in labels:
                raise ValueError("selected_label is outside the closed label set")
            elif self.selected_label is not None and self.status != B31Status.ABSTAINED.value and self.selected_label != maxima[0]:
                raise ValueError("selected_label disagrees with its distribution")
        if self.status == B31Status.ABSTAINED.value and not self.reason:
            raise ValueError("abstention requires a reason")


@dataclass(frozen=True)
class EvidenceSupportResult(_B31ResultBase):
    schema_id: str = B31_EVIDENCE_SUPPORT_SCHEMA_ID
    version: str = B31_VERSION
    hypothesis_id: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        if not isinstance(self.hypothesis_id, str) or not self.hypothesis_id.strip():
            raise ValueError("support result hypothesis_id is required")

    @property
    def identity(self) -> str:
        return f"{self.schema_id}@{self.version}"


@dataclass(frozen=True)
class AgreementContradictionResult(_B31ResultBase):
    schema_id: str = B31_AGREEMENT_CONTRADICTION_SCHEMA_ID
    version: str = B31_VERSION
    hypothesis_id: str = ""
    comparison_hypothesis_ids: tuple[str, ...] = ()
    comparison_evidence_group_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "comparison_hypothesis_ids", tuple(self.comparison_hypothesis_ids))
        object.__setattr__(self, "comparison_evidence_group_ids", tuple(self.comparison_evidence_group_ids))
        super().__post_init__()
        if not isinstance(self.hypothesis_id, str) or not self.hypothesis_id.strip():
            raise ValueError("agreement result hypothesis_id is required")
        if any(not isinstance(item, str) or not item.strip() for item in self.comparison_hypothesis_ids):
            raise ValueError("agreement comparison hypothesis IDs must be non-empty strings")
        if any(not isinstance(item, str) or not item.strip() for item in self.comparison_evidence_group_ids):
            raise ValueError("agreement comparison evidence group IDs must be non-empty strings")
        if len(set(self.comparison_hypothesis_ids)) != len(self.comparison_hypothesis_ids):
            raise ValueError("agreement comparison hypothesis IDs must be unique")
        if len(set(self.comparison_evidence_group_ids)) != len(self.comparison_evidence_group_ids):
            raise ValueError("agreement comparison evidence group IDs must be unique")

    @property
    def identity(self) -> str:
        return f"{self.schema_id}@{self.version}"


@dataclass(frozen=True)
class PacketAbstentionResult(_B31ResultBase):
    schema_id: str = B31_ABSTENTION_SCHEMA_ID
    version: str = B31_VERSION
    basis_hypothesis_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "basis_hypothesis_ids", tuple(self.basis_hypothesis_ids))
        super().__post_init__()
        if len(set(self.basis_hypothesis_ids)) != len(self.basis_hypothesis_ids):
            raise ValueError("abstention basis hypothesis IDs must be unique")
        if any(not isinstance(item, str) or not item.strip() for item in self.basis_hypothesis_ids):
            raise ValueError("abstention basis hypothesis IDs must be non-empty strings")

    @property
    def identity(self) -> str:
        return f"{self.schema_id}@{self.version}"


@dataclass(frozen=True)
class B31NormalizedAssessment:
    schema_id: str = B31_NORMALIZED_ASSESSMENT_SCHEMA_ID
    version: str = B31_VERSION
    status: str = B31Status.SCHEMA_INVALID.value
    assessment_configuration_id: str = B31_NORMALIZED_ASSESSMENT_ID
    observation_id: str = ""
    packet_fingerprint: str = ""
    timestamps: B31Timestamps | None = None
    support_results: tuple[EvidenceSupportResult, ...] = ()
    agreement_results: tuple[AgreementContradictionResult, ...] = ()
    abstention_result: PacketAbstentionResult | None = None
    ranked_hypothesis_ids: tuple[str, ...] = ()
    missing_hypothesis_ids: tuple[str, ...] = ()
    abstaining_hypothesis_ids: tuple[str, ...] = ()
    evidence_disagreement: bool = False
    concentration: Mapping[str, float] = field(default_factory=dict)
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", _status(self.status))
        if self.schema_id != B31_NORMALIZED_ASSESSMENT_SCHEMA_ID or self.version != B31_VERSION:
            raise ValueError("unsupported B3.1 normalized-assessment identity")
        if self.assessment_configuration_id != B31_NORMALIZED_ASSESSMENT_ID:
            raise ValueError("unsupported B3.1 normalized-assessment configuration")
        if self.status not in STATUS_PRECEDENCE:
            raise ValueError("unsupported B3.1 normalized-assessment status")
        for key, value in self.concentration.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError("concentration keys must be non-empty strings")
            _finite_probability(value, f"concentration.{key}")

    @property
    def identity(self) -> str:
        return f"{self.schema_id}@{self.version}"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _default_result_fields(raw: Mapping[str, Any]) -> dict[str, Any]:
    timestamps = raw.get("timestamps", raw)
    if not isinstance(timestamps, Mapping):
        raise B31ContractError("schema_invalid", "result timestamps must be an object")
    values: dict[str, Any] = {
        "assessment_configuration_id": raw.get("assessment_configuration_id", raw.get("configuration", B31_NORMALIZED_ASSESSMENT_ID)),
        "observation_id": str(raw.get("observation_id", "")),
        "packet_fingerprint": str(raw.get("packet_fingerprint", "")),
        "decision_eligible_at_ms": timestamps.get("decision_eligible_at_ms"),
        "packet_ready_at_ms": timestamps.get("packet_ready_at_ms"),
        "request_started_at_ms": timestamps.get("request_started_at_ms"),
        "response_deadline_at_ms": timestamps.get("response_deadline_at_ms"),
        "selected_label": raw.get("selected_label"),
        "probabilities": raw.get("probabilities", raw.get("distribution")),
        "status": raw.get("status"),
        "reason": raw.get("reason"),
        "evidence_refs": _as_tuple(raw.get("evidence_refs", ())),
        "response_fingerprint": raw.get("response_fingerprint"),
        "response_received_at_ms": timestamps.get("response_received_at_ms"),
        "available_at_ms": timestamps.get("available_at_ms"),
        "fresh_until_ms": timestamps.get("fresh_until_ms"),
        "expires_at_ms": timestamps.get("expires_at_ms"),
        "declared_assessment_use_time_ms": timestamps.get("declared_assessment_use_time_ms"),
    }
    return values


def _parse_result(raw_value: Any, kind: str) -> tuple[_B31ResultBase | None, tuple[str, str] | None]:
    try:
        raw = _mapping(raw_value)
        found = _contains_future_fields(raw)
        if found:
            return None, ("internally_inconsistent", found)
        expected_schema, expected_labels, result_type = {
            "support": (B31_EVIDENCE_SUPPORT_SCHEMA_ID, SUPPORT_LABELS, EvidenceSupportResult),
            "agreement": (B31_AGREEMENT_CONTRADICTION_SCHEMA_ID, AGREEMENT_LABELS, AgreementContradictionResult),
            "abstention": (B31_ABSTENTION_SCHEMA_ID, ABSTENTION_LABELS, PacketAbstentionResult),
        }[kind]
        identity = raw.get("identity")
        schema_id = raw.get("schema_id")
        version = raw.get("version")
        if identity is not None and _identity(identity) is None:
            return None, ("schema_invalid", f"{kind} identity must be schema_id@version")
        parsed_identity = _identity(identity) if identity is not None else None
        if parsed_identity and schema_id is None:
            schema_id, version = parsed_identity
        elif parsed_identity and (schema_id, version) != parsed_identity:
            return None, ("internally_inconsistent", f"{kind} identity disagrees with schema_id/version")
        elif schema_id is None and raw.get("schema") is not None:
            schema_id = raw.get("schema")
            if isinstance(schema_id, str) and "@" in schema_id:
                schema_id, version = _identity(schema_id) or (schema_id, version)
        if schema_id is None or version is None:
            return None, ("schema_invalid", f"{kind} result is missing schema identity")
        if schema_id != expected_schema or version != B31_VERSION:
            return None, ("unsupported", f"unsupported {kind} question identity or version")
        values = _default_result_fields(raw)
        if values["assessment_configuration_id"] != B31_NORMALIZED_ASSESSMENT_ID:
            return None, ("unsupported", "unsupported B3.1 assessment configuration")
        if not values["observation_id"].strip() or not values["packet_fingerprint"].strip():
            return None, ("schema_invalid", f"{kind} result is missing packet identity")
        if values["status"] is not None and _status(values["status"]) not in STATUS_PRECEDENCE:
            return None, ("unsupported", f"unsupported {kind} result status")
        if kind == "support":
            if not isinstance(raw.get("hypothesis_id"), str) or not raw["hypothesis_id"].strip():
                return None, ("internally_inconsistent", "support result is missing hypothesis_id")
            values["hypothesis_id"] = raw["hypothesis_id"]
        elif kind == "agreement":
            if not isinstance(raw.get("hypothesis_id"), str) or not raw["hypothesis_id"].strip():
                return None, ("internally_inconsistent", "agreement result is missing hypothesis_id")
            values["hypothesis_id"] = raw["hypothesis_id"]
            values["comparison_hypothesis_ids"] = _as_tuple(raw.get("comparison_hypothesis_ids", raw.get("comparison_hypothesis_id", ())))
            values["comparison_evidence_group_ids"] = _as_tuple(raw.get("comparison_evidence_group_ids", raw.get("comparison_evidence_group_id", ())))
        else:
            values["basis_hypothesis_ids"] = _as_tuple(raw.get("basis_hypothesis_ids", ()))
        if values["response_fingerprint"] is not None:
            _fingerprint(values["response_fingerprint"], "response_fingerprint")
        for name in (
            "decision_eligible_at_ms", "packet_ready_at_ms", "request_started_at_ms",
            "response_deadline_at_ms", "response_received_at_ms", "available_at_ms",
            "fresh_until_ms", "expires_at_ms", "declared_assessment_use_time_ms",
        ):
            values[name] = _int_ms(values[name], name)
        if values["available_at_ms"] != values["response_received_at_ms"]:
            if values["available_at_ms"] is not None or values["response_received_at_ms"] is not None:
                return None, ("internally_inconsistent", "available_at_ms must equal response_received_at_ms")
        probabilities = values["probabilities"]
        selected = values["selected_label"]
        status = _status(values["status"]) if values["status"] is not None else None
        values["status"] = status
        explicit_abstention = status == B31Status.ABSTAINED.value
        if probabilities is None:
            if not explicit_abstention and status not in {B31Status.UNAVAILABLE.value, B31Status.STALE.value}:
                return None, ("schema_invalid", f"{kind} result is missing probabilities")
        else:
            if not isinstance(probabilities, Mapping):
                return None, ("schema_invalid", f"{kind} probabilities must be an object")
            keys = set(probabilities)
            if any(label not in expected_labels for label in keys):
                return None, ("unsupported", f"{kind} probabilities contain an unsupported label")
            if keys != set(expected_labels):
                return None, ("schema_invalid", f"{kind} probabilities must cover every label")
            try:
                probabilities = {label: _finite_probability(probabilities[label], f"probabilities.{label}") for label in expected_labels}
            except ValueError as exc:
                return None, ("schema_invalid", str(exc))
            if not math.isclose(sum(probabilities.values()), 1.0, abs_tol=1e-9):
                return None, ("internally_inconsistent", f"{kind} probabilities must sum to one")
            values["probabilities"] = probabilities
            maximum = max(probabilities.values())
            maxima = [label for label, probability in probabilities.items() if math.isclose(probability, maximum, rel_tol=0.0, abs_tol=1e-12)]
            if len(maxima) > 1:
                if selected is not None or (status not in {None, B31Status.ABSTAINED.value}) or values["reason"] != "tied_maximum":
                    return None, ("internally_inconsistent", f"{kind} tied maximum must abstain with reason tied_maximum")
                values["status"] = B31Status.ABSTAINED.value
                values["selected_label"] = None
            else:
                if selected is None:
                    if explicit_abstention and values["reason"]:
                        pass
                    else:
                        return None, ("internally_inconsistent", f"{kind} selected_label is required")
                elif selected not in expected_labels:
                    return None, ("unsupported", f"{kind} selected_label is outside the closed label set")
                elif selected != maxima[0] and not explicit_abstention:
                    return None, ("internally_inconsistent", f"{kind} selected_label disagrees with its distribution")
                elif explicit_abstention and selected is not None:
                    return None, ("internally_inconsistent", f"{kind} explicit abstention cannot select a semantic label")
        if explicit_abstention and not values["reason"]:
            return None, ("schema_invalid", f"{kind} abstention requires a reason")
        if status == B31Status.USABLE.value and values["response_received_at_ms"] is None:
            return None, ("unavailable", f"{kind} has no recorded response")
        return result_type(schema_id=schema_id, version=version, **values), None
    except B31ContractError as exc:
        return None, (exc.status, exc.reason)
    except _B31ShapeError as exc:
        return None, ("schema_invalid", str(exc))
    except ValueError as exc:
        return None, ("internally_inconsistent", str(exc))
    except (KeyError, TypeError) as exc:
        return None, ("schema_invalid", str(exc))


def _effective_status(result: _B31ResultBase, packet: B31EvidencePacketProfile, use_time_ms: int) -> tuple[str, str | None]:
    deadline = packet.timestamps.response_deadline_at_ms
    received = result.response_received_at_ms
    fresh_until = result.fresh_until_ms if result.fresh_until_ms is not None else packet.timestamps.fresh_until_ms
    expires_at = result.expires_at_ms if result.expires_at_ms is not None else packet.timestamps.expires_at_ms
    if fresh_until is not None and use_time_ms > fresh_until:
        return B31Status.STALE.value, "response freshness expired"
    if expires_at is not None and use_time_ms > expires_at:
        return B31Status.STALE.value, "assessment expiry passed"
    declared = _status(result.status) if result.status else None
    if declared in {
        B31Status.SCHEMA_INVALID.value,
        B31Status.UNSUPPORTED.value,
        B31Status.INTERNALLY_INCONSISTENT.value,
    }:
        return declared, result.reason or f"recorded {declared} result"
    if declared == B31Status.STALE.value:
        return B31Status.STALE.value, result.reason or "recorded stale response"
    if received is not None and fresh_until is not None and received > fresh_until:
        return B31Status.STALE.value, "response was received after freshness expiry"
    if received is None:
        return B31Status.UNAVAILABLE.value, result.reason or "response unavailable"
    if deadline is not None and received > deadline:
        return B31Status.UNAVAILABLE.value, "late"
    if declared == B31Status.UNAVAILABLE.value:
        return B31Status.UNAVAILABLE.value, result.reason or "response unavailable"
    if isinstance(result, PacketAbstentionResult) and result.selected_label == "abstain":
        return B31Status.ABSTAINED.value, result.reason or "selected_abstain"
    if declared == B31Status.ABSTAINED.value:
        return B31Status.ABSTAINED.value, result.reason or "explicit abstention"
    return B31Status.USABLE.value, None


def _validate_result_clock(result: _B31ResultBase, packet: B31EvidencePacketProfile) -> tuple[str, str] | None:
    packet_time = packet.timestamps
    pairs = (
        (result.decision_eligible_at_ms, packet_time.decision_eligible_at_ms, "result decision eligibility disagrees with packet"),
        (result.packet_ready_at_ms, packet_time.packet_ready_at_ms, "result packet readiness disagrees with packet"),
        (result.request_started_at_ms, packet_time.request_started_at_ms, "result request start disagrees with packet"),
        (result.response_deadline_at_ms, packet_time.response_deadline_at_ms, "result response deadline disagrees with packet"),
    )
    for result_value, packet_value, message in pairs:
        if result_value is not None and packet_value is not None and result_value != packet_value:
            return B31Status.INTERNALLY_INCONSISTENT.value, message
    if result.request_started_at_ms is not None and result.response_received_at_ms is not None and result.response_received_at_ms < result.request_started_at_ms:
        return B31Status.INTERNALLY_INCONSISTENT.value, "response cannot precede request start"
    if result.response_received_at_ms is not None and result.available_at_ms != result.response_received_at_ms:
        return B31Status.INTERNALLY_INCONSISTENT.value, "available_at_ms must equal response_received_at_ms"
    return None


def _best_status(items: list[tuple[str, str]]) -> tuple[str, tuple[str, ...]]:
    if not items:
        return B31Status.USABLE.value, ()
    rank = min(STATUS_RANK.get(status, 0) for status, _ in items)
    chosen = [reason for status, reason in items if STATUS_RANK.get(status, 0) == rank and reason]
    return STATUS_PRECEDENCE[rank], tuple(dict.fromkeys(chosen))


def _result_for_id(results: list[_B31ResultBase], expected_ids: tuple[str, ...], family: str) -> tuple[list[_B31ResultBase], list[str], list[tuple[str, str]]]:
    errors: list[tuple[str, str]] = []
    seen: set[str] = set()
    parsed: list[_B31ResultBase] = []
    for result in results:
        key = getattr(result, "hypothesis_id", "")
        if key in seen:
            errors.append((B31Status.INTERNALLY_INCONSISTENT.value, f"duplicate {family} hypothesis_id: {key}"))
        seen.add(key)
        if key not in expected_ids:
            errors.append((B31Status.INTERNALLY_INCONSISTENT.value, f"foreign {family} hypothesis_id: {key}"))
        parsed.append(result)
    missing = [key for key in expected_ids if key not in seen]
    return parsed, missing, errors


def _packet_from_any(packet: B31EvidencePacketProfile | Mapping[str, Any]) -> tuple[B31EvidencePacketProfile | None, tuple[str, str] | None]:
    if isinstance(packet, B31EvidencePacketProfile):
        return packet, None
    try:
        return B31EvidencePacketProfile.from_dict(packet), None
    except B31ContractError as exc:
        return None, (exc.status, exc.reason)
    except (TypeError, ValueError) as exc:
        return None, ("schema_invalid", str(exc))


def _normal_result_value(value: Any, kind: str) -> tuple[_B31ResultBase | None, tuple[str, str] | None]:
    if isinstance(value, (_B31ResultBase,)):
        expected = {
            "support": EvidenceSupportResult,
            "agreement": AgreementContradictionResult,
            "abstention": PacketAbstentionResult,
        }[kind]
        if not isinstance(value, expected):
            return None, ("unsupported", f"wrong result type for {kind}")
        return _parse_result(asdict(value), kind)
    return _parse_result(value, kind)


def parse_b31_result(value: Any, kind: str) -> _B31ResultBase:
    """Parse one recorded result and raise a typed terminal-status error."""
    result, error = _normal_result_value(value, kind)
    if error:
        raise B31ContractError(*error)
    assert result is not None
    return result


def parse_evidence_support_result(value: Any) -> EvidenceSupportResult:
    result = parse_b31_result(value, "support")
    assert isinstance(result, EvidenceSupportResult)
    return result


def parse_agreement_contradiction_result(value: Any) -> AgreementContradictionResult:
    result = parse_b31_result(value, "agreement")
    assert isinstance(result, AgreementContradictionResult)
    return result


def parse_packet_abstention_result(value: Any) -> PacketAbstentionResult:
    result = parse_b31_result(value, "abstention")
    assert isinstance(result, PacketAbstentionResult)
    return result


def normalize_b31_assessment(
    packet: B31EvidencePacketProfile | Mapping[str, Any],
    support_results: Any = (),
    agreement_results: Any = (),
    abstention_result: Any = None,
    *,
    assessment_use_time_ms: int | None = None,
) -> B31NormalizedAssessment:
    """Parse, validate, and normalize one recorded B3.1 fixture assessment."""
    parsed_packet, packet_error = _packet_from_any(packet)
    all_errors: list[tuple[str, str]] = []
    if packet_error:
        all_errors.append(packet_error)
        return B31NormalizedAssessment(status=packet_error[0], reasons=(packet_error[1],))
    assert parsed_packet is not None
    profile = parsed_packet
    if not profile.provenance_complete:
        all_errors.append((B31Status.INTERNALLY_INCONSISTENT.value, "packet provenance is incomplete"))
    if not profile.quality_valid:
        all_errors.append((B31Status.INTERNALLY_INCONSISTENT.value, "packet quality gates are invalid"))
    if isinstance(profile.raw_packet, Mapping):
        if profile.raw_packet.get("provenance_complete") is False or profile.raw_packet.get("quality_valid") is False:
            all_errors.append((B31Status.INTERNALLY_INCONSISTENT.value, "packet provenance or quality gate is invalid"))
    use_time = assessment_use_time_ms if assessment_use_time_ms is not None else profile.timestamps.declared_assessment_use_time_ms
    if use_time is None:
        all_errors.append((B31Status.SCHEMA_INVALID.value, "declared assessment use time is required"))
        use_time = 0
    else:
        try:
            _int_ms(use_time, "assessment_use_time_ms", allow_none=False)
        except ValueError as exc:
            all_errors.append((B31Status.SCHEMA_INVALID.value, str(exc)))
            use_time = 0
    if profile.packet_fingerprint == "" or profile.observation_id == "":
        all_errors.append((B31Status.SCHEMA_INVALID.value, "packet identity is required"))
    try:
        if profile.timestamps.fresh_until_ms is not None and use_time > profile.timestamps.fresh_until_ms:
            all_errors.append((B31Status.STALE.value, "packet freshness expired"))
        if profile.timestamps.expires_at_ms is not None and use_time > profile.timestamps.expires_at_ms:
            all_errors.append((B31Status.STALE.value, "packet expiry passed"))
    except (TypeError, ValueError) as exc:
        all_errors.append((B31Status.SCHEMA_INVALID.value, str(exc)))

    def parse_many(values: Any, kind: str) -> list[_B31ResultBase]:
        if values is None:
            return []
        if isinstance(values, Mapping) or isinstance(values, _B31ResultBase):
            values = [values]
        if isinstance(values, (str, bytes)) or not isinstance(values, (list, tuple)):
            all_errors.append((B31Status.SCHEMA_INVALID.value, f"{kind}_results must be an array"))
            return []
        parsed: list[_B31ResultBase] = []
        for value in values:
            result, error = _normal_result_value(value, kind)
            if error:
                all_errors.append(error)
            elif result is not None:
                parsed.append(result)
        return parsed

    support = parse_many(support_results, "support")
    agreement = parse_many(agreement_results, "agreement")
    abstention_values = [] if abstention_result is None else ([*abstention_result] if isinstance(abstention_result, (list, tuple)) else [abstention_result])
    abstentions: list[PacketAbstentionResult] = []
    for value in abstention_values:
        result, error = _normal_result_value(value, "abstention")
        if error:
            all_errors.append(error)
        elif isinstance(result, PacketAbstentionResult):
            abstentions.append(result)

    expected_ids = tuple(profile.stable_hypothesis_ids)
    support_typed, missing_support, support_errors = _result_for_id(support, expected_ids, "support")
    agreement_typed, missing_agreement, agreement_errors = _result_for_id(agreement, expected_ids, "agreement")
    all_errors.extend(support_errors)
    all_errors.extend(agreement_errors)
    if len(support) != len(expected_ids) and not support_errors:
        all_errors.append((B31Status.UNAVAILABLE.value, f"missing support hypothesis IDs: {','.join(missing_support)}"))
    if len(agreement) != len(expected_ids) and not agreement_errors:
        all_errors.append((B31Status.UNAVAILABLE.value, f"missing agreement hypothesis IDs: {','.join(missing_agreement)}"))
    if not expected_ids and (support or agreement):
        all_errors.append((B31Status.INTERNALLY_INCONSISTENT.value, "H=0 requires zero per-hypothesis results"))
    if len(abstentions) == 0:
        all_errors.append((B31Status.UNAVAILABLE.value, "exactly one packet-level abstention result is required"))
    elif len(abstentions) > 1:
        all_errors.append((B31Status.INTERNALLY_INCONSISTENT.value, "duplicate packet-level abstention results"))
    abstention = abstentions[0] if abstentions else None
    if expected_ids and len(support) == len(expected_ids) and len(agreement) == len(expected_ids) and len(abstentions) == 1:
        pass
    if not expected_ids and abstention is not None and abstention.selected_label != "abstain":
        all_errors.append((B31Status.INTERNALLY_INCONSISTENT.value, "H=0 packet abstention must select abstain"))

    effective_support: list[EvidenceSupportResult] = []
    effective_agreement: list[AgreementContradictionResult] = []
    abstaining_ids: list[str] = []
    for result in support_typed:
        if result.observation_id != profile.observation_id or result.packet_fingerprint != profile.packet_fingerprint:
            all_errors.append((B31Status.INTERNALLY_INCONSISTENT.value, "support result packet identity mismatch"))
        clock_error = _validate_result_clock(result, profile)
        if clock_error:
            all_errors.append(clock_error)
        status, reason = _effective_status(result, profile, use_time)
        if status != B31Status.USABLE.value:
            all_errors.append((status, reason or "support result is not usable"))
            if status == B31Status.ABSTAINED.value:
                abstaining_ids.append(result.hypothesis_id)
        effective_support.append(replace(result, status=status, reason=reason or result.reason))
    for result in agreement_typed:
        if result.observation_id != profile.observation_id or result.packet_fingerprint != profile.packet_fingerprint:
            all_errors.append((B31Status.INTERNALLY_INCONSISTENT.value, "agreement result packet identity mismatch"))
        clock_error = _validate_result_clock(result, profile)
        if clock_error:
            all_errors.append(clock_error)
        status, reason = _effective_status(result, profile, use_time)
        if status != B31Status.USABLE.value:
            all_errors.append((status, reason or "agreement result is not usable"))
            if status == B31Status.ABSTAINED.value:
                abstaining_ids.append(result.hypothesis_id)
        label = result.selected_label
        if len(expected_ids) == 1 and label is not None and label != "unknown":
            all_errors.append((B31Status.INTERNALLY_INCONSISTENT.value, "H=1 agreement must select unknown"))
        if label in {"agreement", "mixed", "contradiction"}:
            comparisons = set(result.comparison_hypothesis_ids)
            if len(result.comparison_hypothesis_ids) != len(comparisons) or result.hypothesis_id in comparisons or comparisons - set(expected_ids):
                all_errors.append((B31Status.INTERNALLY_INCONSISTENT.value, "agreement comparison IDs are self or foreign"))
            own_groups = set(profile.hypothesis_evidence_groups.get(result.hypothesis_id, ()))
            independent = set(result.comparison_evidence_group_ids) & set(profile.independent_evidence_groups)
            independent_comparisons = {
                hypothesis_id
                for hypothesis_id in comparisons - {result.hypothesis_id}
                if not (set(profile.hypothesis_evidence_groups.get(hypothesis_id, ())) & own_groups)
            }
            if not (independent_comparisons or (independent - own_groups)):
                all_errors.append((B31Status.INTERNALLY_INCONSISTENT.value, "agreement requires distinct non-correlated comparison evidence"))
        effective_agreement.append(replace(result, status=status, reason=reason or result.reason))
    if abstention is not None:
        if abstention.observation_id != profile.observation_id or abstention.packet_fingerprint != profile.packet_fingerprint:
            all_errors.append((B31Status.INTERNALLY_INCONSISTENT.value, "abstention result packet identity mismatch"))
        clock_error = _validate_result_clock(abstention, profile)
        if clock_error:
            all_errors.append(clock_error)
        if set(abstention.basis_hypothesis_ids) - set(expected_ids):
            all_errors.append((B31Status.INTERNALLY_INCONSISTENT.value, "abstention basis contains a foreign hypothesis ID"))
        status, reason = _effective_status(abstention, profile, use_time)
        if status != B31Status.USABLE.value:
            all_errors.append((status, reason or "packet abstention is not usable"))
        abstention = replace(abstention, status=status, reason=reason or abstention.reason)

    status, reasons = _best_status(all_errors)
    ranking: tuple[str, ...] = ()
    if status == B31Status.USABLE.value and len(support_typed) == len(expected_ids) and len(agreement_typed) == len(expected_ids) and abstention is not None:
        ranked = [
            (SUPPORT_RANK[result.selected_label], -float(result.probabilities[result.selected_label]), result.hypothesis_id)
            for result in effective_support
            if result.selected_label in SUPPORT_RANK and result.probabilities is not None
        ]
        ranking = tuple(item[2] for item in sorted(ranked))
    disagreement = any(result.selected_label in {"mixed", "contradiction"} for result in effective_agreement)
    return B31NormalizedAssessment(
        status=status,
        assessment_configuration_id=B31_NORMALIZED_ASSESSMENT_ID,
        observation_id=profile.observation_id,
        packet_fingerprint=profile.packet_fingerprint,
        timestamps=profile.timestamps,
        support_results=tuple(effective_support),
        agreement_results=tuple(effective_agreement),
        abstention_result=abstention,
        ranked_hypothesis_ids=ranking,
        missing_hypothesis_ids=tuple(dict.fromkeys(missing_support + missing_agreement)),
        abstaining_hypothesis_ids=tuple(dict.fromkeys(abstaining_ids)),
        evidence_disagreement=disagreement,
        concentration={
            result.hypothesis_id: float(result.probabilities[result.selected_label])
            for result in effective_support
            if result.status == B31Status.USABLE.value
            and result.selected_label is not None
            and result.probabilities is not None
        },
        reasons=reasons,
    )


# Short aliases make the internal fixture API easy to discover.
normalize_assessment = normalize_b31_assessment
normalize_b31 = normalize_b31_assessment

# Friendly internal names; the canonical identities remain the constants above.
EvidencePacketProfile = B31EvidencePacketProfile
NormalizedAssessment = B31NormalizedAssessment
TimestampContract = B31Timestamps


def diagnostic_ranking(assessment: B31NormalizedAssessment) -> tuple[str, ...]:
    """Return only the approved display ranking projection."""
    return assessment.ranked_hypothesis_ids if assessment.status == B31Status.USABLE.value else ()


def validate_future_free_packet(packet: Mapping[str, Any]) -> None:
    found = _contains_future_fields(packet)
    if found:
        raise ValueError(found)
