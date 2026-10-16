"""Explicit model-gated, citation-preserving summary contracts."""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass
from typing import Literal, Protocol

from .research import ResearchSynthesis

MODEL_SUMMARY_API_VERSION = "market-os.model-summary.v1"
MAX_MODEL_OUTPUT_CHARS = 16_384
_SECRET_LIKE_RE = re.compile(r"(?:api[_-]?key|secret|access[_-]?token|password)\s*=", re.IGNORECASE)


def _text(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _is_digest(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(
        character in "0123456789abcdef" for character in value
    )


def _fingerprint(value: str, field: str) -> None:
    if not _is_digest(value):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")


def _summary_fingerprint(
    request: "SummaryRequest",
    provider: "ModelProviderIdentity",
    output_fingerprint: str,
    validation: "SummaryValidation",
    gate: "GateDecision",
) -> str:
    return _digest(
        {
            "request": asdict(request),
            "provider": asdict(provider),
            "output": output_fingerprint,
            "validation": asdict(validation),
            "gate": asdict(gate),
        }
    )


def _render_statements(statements: tuple["GeneratedStatement", ...]) -> str:
    labels = {
        "supported": "",
        "inference": "Inference: ",
        "unsupported": "Unsupported (ungrounded): ",
        "rejected": "Rejected: ",
    }
    return " ".join(labels[statement.classification] + statement.text for statement in statements)


def render_summary_text(statements: tuple["GeneratedStatement", ...]) -> str:
    """Render only classified statement text for the publishable summary."""
    return _render_statements(statements)


def _output_fingerprint(
    summary_text: str | None,
    statements: tuple["GeneratedStatement", ...],
    usage: "ModelUsage",
    validation: "SummaryValidation",
    failure: "ModelFailure | None" = None,
) -> str:
    return _digest(
        {
            "summary_text": summary_text,
            "statements": [asdict(statement) for statement in statements],
            "usage": asdict(usage),
            "validation": asdict(validation),
            "failure": asdict(failure) if failure is not None else None,
        }
    )


@dataclass(frozen=True)
class ModelProviderIdentity:
    provider: str
    model: str
    version: str
    api_version: str = MODEL_SUMMARY_API_VERSION

    def __post_init__(self) -> None:
        for value, field in ((self.provider, "provider"), (self.model, "model"), (self.version, "version")):
            _text(value, field)
        if self.api_version != MODEL_SUMMARY_API_VERSION:
            raise ValueError(f"unsupported model-summary version: {self.api_version}")


@dataclass(frozen=True)
class ModelUsage:
    input_units: int | None = None
    output_units: int | None = None
    estimated_cost: float | None = None
    api_version: str = MODEL_SUMMARY_API_VERSION

    def __post_init__(self) -> None:
        for value, field in ((self.input_units, "input_units"), (self.output_units, "output_units")):
            if value is not None and (
                not isinstance(value, int) or isinstance(value, bool) or value < 0
            ):
                raise ValueError(f"{field} must be a non-negative integer or null")
        if self.estimated_cost is not None and (
            not math.isfinite(self.estimated_cost) or self.estimated_cost < 0
        ):
            raise ValueError("estimated_cost must be finite and non-negative")
        if self.api_version != MODEL_SUMMARY_API_VERSION:
            raise ValueError(f"unsupported model-summary version: {self.api_version}")


@dataclass(frozen=True)
class ModelFailure:
    kind: Literal["error", "timeout"]
    error_type: str
    api_version: str = MODEL_SUMMARY_API_VERSION

    def __post_init__(self) -> None:
        if self.kind not in {"error", "timeout"}:
            raise ValueError("invalid model failure kind")
        _text(self.error_type, "error_type")
        if self.api_version != MODEL_SUMMARY_API_VERSION:
            raise ValueError(f"unsupported model-summary version: {self.api_version}")


@dataclass(frozen=True)
class SummaryRequest:
    objective: str
    synthesis_fingerprint: str
    input_fingerprint: str
    prompt_fingerprint: str
    prompt_version: str
    claim_ids: tuple[str, ...]
    passage_ids: tuple[str, ...]
    api_version: str = MODEL_SUMMARY_API_VERSION

    def __post_init__(self) -> None:
        for value, field in (
            (self.objective, "objective"),
            (self.synthesis_fingerprint, "synthesis_fingerprint"),
            (self.input_fingerprint, "input_fingerprint"),
            (self.prompt_fingerprint, "prompt_fingerprint"),
            (self.prompt_version, "prompt_version"),
        ):
            _text(value, field)
        _fingerprint(self.synthesis_fingerprint, "synthesis_fingerprint")
        _fingerprint(self.input_fingerprint, "input_fingerprint")
        _fingerprint(self.prompt_fingerprint, "prompt_fingerprint")
        if self.api_version != MODEL_SUMMARY_API_VERSION:
            raise ValueError(f"unsupported model-summary version: {self.api_version}")


@dataclass(frozen=True)
class GeneratedStatement:
    statement_id: str
    text: str
    classification: Literal["supported", "inference", "unsupported", "rejected"]
    citation_ids: tuple[str, ...] = ()
    support_ids: tuple[str, ...] = ()
    document_ids: tuple[str, ...] = ()
    evidence_quotes: tuple[str, ...] = ()
    confidence: float | None = None
    api_version: str = MODEL_SUMMARY_API_VERSION

    def __post_init__(self) -> None:
        _text(self.statement_id, "statement_id")
        _text(self.text, "text")
        if self.classification not in {"supported", "inference", "unsupported", "rejected"}:
            raise ValueError("invalid generated statement classification")
        if self.confidence is not None and (
            not math.isfinite(self.confidence) or not 0 <= self.confidence <= 1
        ):
            raise ValueError("statement confidence must be between 0 and 1")
        if self.api_version != MODEL_SUMMARY_API_VERSION:
            raise ValueError(f"unsupported model-summary version: {self.api_version}")


@dataclass(frozen=True)
class ModelOutput:
    summary_text: str
    statements: tuple[GeneratedStatement, ...]
    usage: ModelUsage = ModelUsage()
    api_version: str = MODEL_SUMMARY_API_VERSION

    def __post_init__(self) -> None:
        _text(self.summary_text, "summary_text")
        if not self.statements:
            raise ValueError("model output needs statements")
        if len({statement.statement_id for statement in self.statements}) != len(self.statements):
            raise ValueError("model output statement IDs must be unique")
        if self.api_version != MODEL_SUMMARY_API_VERSION:
            raise ValueError(f"unsupported model-summary version: {self.api_version}")


@dataclass(frozen=True)
class SummaryValidation:
    status: Literal["valid", "rejected"]
    errors: tuple[str, ...]
    supported_count: int
    inference_count: int
    unsupported_count: int
    rejected_count: int
    validated_citation_ids: tuple[str, ...]
    evidence_coverage: float
    api_version: str = MODEL_SUMMARY_API_VERSION

    def __post_init__(self) -> None:
        if self.status not in {"valid", "rejected"}:
            raise ValueError("invalid summary validation status")
        counts = (self.supported_count, self.inference_count, self.unsupported_count, self.rejected_count)
        if any(not isinstance(count, int) or isinstance(count, bool) or count < 0 for count in counts):
            raise ValueError("summary validation counts must be non-negative")
        total = self.supported_count + self.inference_count + self.unsupported_count + self.rejected_count
        expected = self.supported_count / total if total else 0.0
        if not math.isclose(self.evidence_coverage, expected, rel_tol=0, abs_tol=1e-12):
            raise ValueError("summary evidence coverage does not match statement counts")
        if self.status == "valid" and self.errors:
            raise ValueError("valid summary validation cannot contain errors")
        if self.status == "rejected" and not self.errors:
            raise ValueError("rejected summary validation needs errors")
        if len(set(self.validated_citation_ids)) != len(self.validated_citation_ids):
            raise ValueError("validated citation IDs must be unique")
        if self.api_version != MODEL_SUMMARY_API_VERSION:
            raise ValueError(f"unsupported model-summary version: {self.api_version}")


@dataclass(frozen=True)
class GateDecision:
    status: Literal["approved", "rejected", "fallback"]
    reason: str
    deterministic_fallback: bool
    api_version: str = MODEL_SUMMARY_API_VERSION

    def __post_init__(self) -> None:
        _text(self.reason, "reason")
        if self.status not in {"approved", "rejected", "fallback"}:
            raise ValueError("invalid gate status")
        if self.api_version != MODEL_SUMMARY_API_VERSION:
            raise ValueError(f"unsupported model-summary version: {self.api_version}")


@dataclass(frozen=True)
class ModelGatedSummary:
    summary_id: str
    request: SummaryRequest
    provider: ModelProviderIdentity
    summary_text: str | None
    statements: tuple[GeneratedStatement, ...]
    validation: SummaryValidation
    gate: GateDecision
    usage: ModelUsage
    input_fingerprint: str
    output_fingerprint: str
    summary_fingerprint: str
    deterministic_fallback_fingerprint: str
    synthesis_lineage_artifact_id: str
    failure: ModelFailure | None = None
    api_version: str = MODEL_SUMMARY_API_VERSION

    def __post_init__(self) -> None:
        for value, field in (
            (self.summary_id, "summary_id"),
            (self.input_fingerprint, "input_fingerprint"),
            (self.output_fingerprint, "output_fingerprint"),
            (self.summary_fingerprint, "summary_fingerprint"),
            (self.deterministic_fallback_fingerprint, "deterministic_fallback_fingerprint"),
            (self.synthesis_lineage_artifact_id, "synthesis_lineage_artifact_id"),
        ):
            _text(value, field)
        for value, field in (
            (self.input_fingerprint, "input_fingerprint"),
            (self.output_fingerprint, "output_fingerprint"),
            (self.summary_fingerprint, "summary_fingerprint"),
            (self.deterministic_fallback_fingerprint, "deterministic_fallback_fingerprint"),
        ):
            _fingerprint(value, field)
        if self.failure is not None and not isinstance(self.failure, ModelFailure):
            raise ValueError("failure must be a ModelFailure")
        if self.input_fingerprint != self.request.input_fingerprint:
            raise ValueError("input_fingerprint does not match summary request")
        if self.deterministic_fallback_fingerprint != self.request.synthesis_fingerprint:
            raise ValueError("deterministic fallback fingerprint does not match synthesis")
        expected_output_fingerprint = _output_fingerprint(
            self.summary_text,
            self.statements,
            self.usage,
            self.validation,
            self.failure,
        )
        if self.output_fingerprint != expected_output_fingerprint:
            raise ValueError("output_fingerprint does not match summary output")
        actual_counts = {
            classification: sum(
                statement.classification == classification for statement in self.statements
            )
            for classification in ("supported", "inference", "unsupported", "rejected")
        }
        expected_counts = {
            "supported": self.validation.supported_count,
            "inference": self.validation.inference_count,
            "unsupported": self.validation.unsupported_count,
            "rejected": self.validation.rejected_count,
        }
        if actual_counts != expected_counts:
            raise ValueError("summary validation counts do not match statements")
        expected_summary_fingerprint = _summary_fingerprint(
            self.request,
            self.provider,
            self.output_fingerprint,
            self.validation,
            self.gate,
        )
        if self.summary_fingerprint != expected_summary_fingerprint:
            raise ValueError("summary_fingerprint does not match summary content")
        if self.summary_id != "summary-" + self.summary_fingerprint[:16]:
            raise ValueError("summary_id does not match summary_fingerprint")
        if self.gate.status == "approved":
            if self.validation.status != "valid":
                raise ValueError("approved summary needs valid validation")
            if self.gate.deterministic_fallback:
                raise ValueError("approved summary cannot use deterministic fallback")
            if not isinstance(self.summary_text, str) or not self.summary_text.strip():
                raise ValueError("approved summary needs text")
            if self.summary_text != _render_statements(self.statements):
                raise ValueError("approved summary text does not match classified statements")
            if self.failure is not None:
                raise ValueError("approved summary cannot contain a model failure")
        else:
            if self.validation.status != "rejected":
                raise ValueError("rejected or fallback summary needs rejected validation")
            if not self.gate.deterministic_fallback:
                raise ValueError("rejected or fallback summary must preserve deterministic fallback")
            if self.summary_text is not None:
                raise ValueError("rejected or fallback summary cannot publish model text")
            if self.gate.status == "fallback" and self.failure is None:
                raise ValueError("fallback summary needs a model failure")
            if self.gate.status == "rejected" and self.failure is not None:
                raise ValueError("rejected summary cannot contain a provider failure")
        if self.api_version != MODEL_SUMMARY_API_VERSION:
            raise ValueError(f"unsupported model-summary version: {self.api_version}")


class SummaryModelProvider(Protocol):
    identity: ModelProviderIdentity

    def generate(self, request: SummaryRequest, synthesis: ResearchSynthesis) -> ModelOutput: ...


def make_summary_request(objective: str, synthesis: ResearchSynthesis, prompt_version: str) -> SummaryRequest:
    input_fingerprint = _digest(asdict(synthesis))
    prompt_fingerprint = _digest({"objective": objective, "prompt_version": prompt_version, "input": input_fingerprint})
    return SummaryRequest(
        objective,
        synthesis.synthesis_fingerprint,
        input_fingerprint,
        prompt_fingerprint,
        prompt_version,
        tuple(claim.claim_id for claim in synthesis.claims)
        + tuple(claim.claim_id for claim in synthesis.unsupported_claims),
        tuple(passage.passage_id for passage in synthesis.passages),
    )


class DeterministicTestSummaryProvider:
    """Opt-in test model double; it emits only existing grounded statements."""

    identity = ModelProviderIdentity("deterministic-test", "market-os-test-model", "m2.4-v1")
    prompt_version = "m2.4-deterministic-prompt-v1"

    def generate(self, request: SummaryRequest, synthesis: ResearchSynthesis) -> ModelOutput:
        statements = [
            GeneratedStatement(
                f"statement-{claim.claim_id}",
                claim.claim_text,
                "supported",
                claim.citation_ids,
                claim.support_ids,
                claim.document_ids,
                tuple(support.quote for support in synthesis.supports if support.support_id in claim.support_ids),
                claim.confidence,
            )
            for claim in synthesis.claims
        ]
        statements.extend(
            GeneratedStatement(f"statement-{claim.claim_id}", claim.claim_text, "unsupported")
            for claim in synthesis.unsupported_claims
        )
        return ModelOutput(
            _render_statements(tuple(statements)),
            tuple(statements),
            ModelUsage(len(request.input_fingerprint), sum(len(statement.text) for statement in statements)),
        )


def validate_model_output(
    output: ModelOutput,
    synthesis: ResearchSynthesis,
    *,
    check_summary_text: bool = True,
) -> SummaryValidation:
    citations = {citation.citation_id: citation for citation in synthesis.citations}
    supports = {support.support_id: support for support in synthesis.supports}
    passages = {passage.passage_id: passage for passage in synthesis.passages}
    documents = {document.document_id: document for document in synthesis.documents}
    errors: list[str] = []
    if len(output.summary_text) > MAX_MODEL_OUTPUT_CHARS:
        errors.append("summary output exceeds maximum length")
    if _SECRET_LIKE_RE.search(output.summary_text):
        errors.append("summary output contains secret-like material")
    counts = {"supported": 0, "inference": 0, "unsupported": 0, "rejected": 0}
    validated: list[str] = []
    for statement in output.statements:
        counts[statement.classification] += 1
        if len(statement.text) > MAX_MODEL_OUTPUT_CHARS:
            errors.append(f"{statement.statement_id}: statement output exceeds maximum length")
        if _SECRET_LIKE_RE.search(statement.text):
            errors.append(f"{statement.statement_id}: statement contains secret-like material")
        if statement.classification == "rejected":
            errors.append(f"{statement.statement_id}: rejected classification")
        for document_id in statement.document_ids:
            if document_id not in documents:
                errors.append(f"{statement.statement_id}: unknown document {document_id}")
        statement_citation_claims: set[str] = set()
        statement_support_claims: set[str] = set()
        statement_documents: set[str] = set()
        for citation_id in statement.citation_ids:
            citation = citations.get(citation_id)
            if citation is None:
                errors.append(f"{statement.statement_id}: unknown citation {citation_id}")
                continue
            passage = passages.get(citation.passage_id)
            if passage is None or citation.document_id not in documents:
                errors.append(f"{statement.statement_id}: citation lineage is incomplete")
                continue
            if (
                citation.lineage_artifact_id != synthesis.lineage_artifact_id
                or passage.lineage_artifact_id != synthesis.lineage_artifact_id
            ):
                errors.append(f"{statement.statement_id}: citation lineage is outside synthesis")
                continue
            if citation.content_hash != passage.content_hash or citation.source_ref != passage.source_ref:
                errors.append(f"{statement.statement_id}: citation provenance mismatch")
                continue
            if citation.document_id != passage.document_id:
                errors.append(f"{statement.statement_id}: citation document does not match passage")
                continue
            validated.append(citation_id)
            statement_citation_claims.add(citation.claim_id)
            statement_documents.add(citation.document_id)
        for support_id in statement.support_ids:
            support = supports.get(support_id)
            if support is None:
                errors.append(f"{statement.statement_id}: unknown support {support_id}")
            elif support.claim_id not in {claim.claim_id for claim in synthesis.claims}:
                errors.append(f"{statement.statement_id}: support claim is outside synthesis")
            else:
                if support.lineage_artifact_id != synthesis.lineage_artifact_id:
                    errors.append(f"{statement.statement_id}: support lineage is outside synthesis")
                    continue
                statement_support_claims.add(support.claim_id)
                statement_documents.add(support.document_id)
        if statement.classification == "supported":
            if not statement.citation_ids or not statement.support_ids or not statement.evidence_quotes:
                errors.append(f"{statement.statement_id}: supported statement lacks evidence")
            if len(statement_citation_claims) != 1 or len(statement_support_claims) != 1 or statement_citation_claims != statement_support_claims:
                errors.append(f"{statement.statement_id}: support or citation belongs to a different claim")
            if set(statement.document_ids) != statement_documents:
                errors.append(f"{statement.statement_id}: document lineage does not match evidence")
            support_quotes = {supports[support_id].quote for support_id in statement.support_ids if support_id in supports}
            if statement.text not in support_quotes:
                errors.append(f"{statement.statement_id}: supported statement is not an exact evidence quote")
            if not support_quotes.issubset(set(statement.evidence_quotes)):
                errors.append(f"{statement.statement_id}: support quote is missing from evidence quotes")
            expected_citations = {
                supports[support_id].citation_id
                for support_id in statement.support_ids
                if support_id in supports
            }
            if set(statement.citation_ids) != expected_citations:
                errors.append(f"{statement.statement_id}: citations do not match claim supports")
            allowed_quotes = {passages[citations[citation_id].passage_id].text for citation_id in statement.citation_ids if citation_id in citations and citations[citation_id].passage_id in passages}
            if any(quote not in allowed_quotes for quote in statement.evidence_quotes):
                errors.append(f"{statement.statement_id}: quote does not match cited passage")
        if statement.classification == "unsupported" and (
            statement.citation_ids
            or statement.support_ids
            or statement.document_ids
            or statement.evidence_quotes
        ):
            errors.append(f"{statement.statement_id}: unsupported statement contains citation or support evidence")
        if statement.classification == "inference" and statement.evidence_quotes:
            allowed_quotes = {
                passages[citations[citation_id].passage_id].text
                for citation_id in statement.citation_ids
                if citation_id in citations and citations[citation_id].passage_id in passages
            }
            if any(quote not in allowed_quotes for quote in statement.evidence_quotes):
                errors.append(f"{statement.statement_id}: inference quote does not match cited passage")
        if statement.classification == "inference" and statement.document_ids and set(statement.document_ids) != statement_documents:
            errors.append(f"{statement.statement_id}: inference document lineage does not match evidence")
    if check_summary_text and output.summary_text != _render_statements(output.statements):
        errors.append("summary text does not match its classified statements")
    total = len(output.statements)
    return SummaryValidation(
        "valid" if not errors else "rejected",
        tuple(errors),
        counts["supported"],
        counts["inference"],
        counts["unsupported"],
        counts["rejected"],
        tuple(dict.fromkeys(validated)),
        counts["supported"] / total if total else 0.0,
    )


def validate_persisted_summary(summary: ModelGatedSummary, synthesis: ResearchSynthesis) -> None:
    """Re-resolve persisted statement references against the cited synthesis."""
    if not summary.statements:
        return
    validation = validate_model_output(
        ModelOutput(render_summary_text(summary.statements), summary.statements, summary.usage),
        synthesis,
        check_summary_text=False,
    )
    stored = summary.validation
    structural_errors = tuple(error for error in stored.errors if error != "summary text does not match its classified statements")
    if (
        validation.errors != structural_errors
        or validation.supported_count != stored.supported_count
        or validation.inference_count != stored.inference_count
        or validation.unsupported_count != stored.unsupported_count
        or validation.rejected_count != stored.rejected_count
        or validation.validated_citation_ids != stored.validated_citation_ids
        or validation.evidence_coverage != stored.evidence_coverage
    ):
        raise ValueError("model summary citation validation does not match cited research")
    if stored.status != ("rejected" if stored.errors else "valid"):
        raise ValueError("model summary validation status does not match cited research")
    if summary.gate.status == "approved" and validation.status != "valid":
        raise ValueError("approved model summary has unverifiable citations")


def _rejected_validation(
    statements: tuple[GeneratedStatement, ...],
    error: str,
) -> SummaryValidation:
    counts = {
        classification: sum(statement.classification == classification for statement in statements)
        for classification in ("supported", "inference", "unsupported", "rejected")
    }
    total = len(statements)
    return SummaryValidation(
        "rejected",
        (error,),
        counts["supported"],
        counts["inference"],
        counts["unsupported"],
        counts["rejected"],
        (),
        counts["supported"] / total if total else 0.0,
    )


def gate_summary(
    provider: SummaryModelProvider,
    objective: str,
    synthesis: ResearchSynthesis,
    *,
    synthesis_artifact_id: str,
) -> ModelGatedSummary:
    request = make_summary_request(objective, synthesis, getattr(provider, "prompt_version", "m2.4-prompt-v1"))
    try:
        output = provider.generate(request, synthesis)
    except Exception as exc:
        validation = SummaryValidation("rejected", (f"model_error:{type(exc).__name__}",), 0, 0, 0, 0, (), 0.0)
        gate = GateDecision("fallback", "model provider failed; deterministic synthesis preserved", True)
        summary_text = None
        statements = ()
        usage = ModelUsage()
        failure = ModelFailure("timeout" if isinstance(exc, TimeoutError) else "error", type(exc).__name__)
        output_fingerprint = _output_fingerprint(summary_text, statements, usage, validation, failure)
    else:
        try:
            if not isinstance(output, ModelOutput):
                raise TypeError("provider returned a non-ModelOutput value")
            validation = validate_model_output(output, synthesis)
        except Exception as exc:
            statements = tuple(output.statements) if isinstance(output, ModelOutput) else ()
            usage = output.usage if isinstance(output, ModelOutput) else ModelUsage()
            validation = _rejected_validation(
                statements,
                f"malformed_model_output:{type(exc).__name__}",
            )
        gate = GateDecision(
            "approved" if validation.status == "valid" else "rejected",
            "model output validated" if validation.status == "valid" else "citation/support validation failed",
            validation.status != "valid",
        )
        summary_text = output.summary_text if validation.status == "valid" else None
        statements = output.statements if isinstance(output, ModelOutput) else ()
        usage = output.usage if isinstance(output, ModelOutput) else ModelUsage()
        failure = None
        output_fingerprint = _output_fingerprint(summary_text, statements, usage, validation, failure)
    summary_fingerprint = _summary_fingerprint(request, provider.identity, output_fingerprint, validation, gate)
    return ModelGatedSummary(
        "summary-" + summary_fingerprint[:16],
        request,
        provider.identity,
        summary_text,
        tuple(statements),
        validation,
        gate,
        usage,
        request.input_fingerprint,
        output_fingerprint,
        summary_fingerprint,
        synthesis.synthesis_fingerprint,
        synthesis_artifact_id,
        failure,
    )


def model_gated_summary_from_dict(payload: dict) -> ModelGatedSummary:
    """Validate and decode a persisted model-gated summary."""
    try:
        values = dict(payload)
        request = dict(values["request"])
        request["claim_ids"] = tuple(request.get("claim_ids", ()))
        request["passage_ids"] = tuple(request.get("passage_ids", ()))
        values["request"] = SummaryRequest(**request)
        values["provider"] = ModelProviderIdentity(**values["provider"])
        values["statements"] = tuple(
            GeneratedStatement(
                **{
                    **item,
                    "citation_ids": tuple(item.get("citation_ids", ())),
                    "support_ids": tuple(item.get("support_ids", ())),
                    "document_ids": tuple(item.get("document_ids", ())),
                    "evidence_quotes": tuple(item.get("evidence_quotes", ())),
                }
            )
            for item in values.get("statements", ())
        )
        validation = dict(values["validation"])
        validation["errors"] = tuple(validation.get("errors", ()))
        validation["validated_citation_ids"] = tuple(validation.get("validated_citation_ids", ()))
        values["validation"] = SummaryValidation(**validation)
        values["gate"] = GateDecision(**values["gate"])
        values["usage"] = ModelUsage(**values["usage"])
        if values.get("failure") is not None:
            values["failure"] = ModelFailure(**values["failure"])
        return ModelGatedSummary(**values)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"model summary artifact is malformed: {exc}") from exc
