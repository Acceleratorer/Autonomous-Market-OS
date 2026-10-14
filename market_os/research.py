"""Versioned, deterministic cited-research contracts and synthesis."""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Literal

from .providers import DocumentRecord, RetrievedPassage, RetrievalResult

RESEARCH_API_VERSION = "market-os.research.v1"


def _utc(value: str, field: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(None):
        raise ValueError(f"{field} must include a UTC offset")


def _text(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _synthesis_fingerprint(
    objective: str,
    query: str,
    retrieval_fingerprint: str,
    claims: tuple["ResearchClaim", ...],
    unsupported_claims: tuple["UnsupportedClaim", ...],
    coverage: "EvidenceCoverage",
    supports: tuple["ClaimSupport", ...],
    citations: tuple["Citation", ...],
    documents: tuple["DocumentReference", ...],
    passages: tuple["PassageReference", ...],
) -> str:
    return _digest(
        {
            "objective": objective,
            "query": query,
            "retrieval_fingerprint": retrieval_fingerprint,
            "claims": [asdict(claim) for claim in claims],
            "unsupported_claims": [asdict(claim) for claim in unsupported_claims],
            "coverage": asdict(coverage),
            "supports": [asdict(support) for support in supports],
            "citations": [asdict(citation) for citation in citations],
            "documents": [asdict(document) for document in documents],
            "passages": [asdict(passage) for passage in passages],
        }
    )


@dataclass(frozen=True)
class DocumentReference:
    document_id: str
    title: str
    publisher: str
    source_ref: str
    published_at: str
    retrieved_at: str
    content_hash: str
    license_classification: str
    provider: str
    provenance_source_ref: str
    lineage_artifact_id: str
    content_ref: str | None = None
    api_version: str = RESEARCH_API_VERSION

    def __post_init__(self) -> None:
        for value, field in (
            (self.document_id, "document_id"),
            (self.title, "title"),
            (self.publisher, "publisher"),
            (self.source_ref, "source_ref"),
            (self.content_hash, "content_hash"),
            (self.license_classification, "license_classification"),
            (self.provider, "provider"),
            (self.provenance_source_ref, "provenance_source_ref"),
            (self.lineage_artifact_id, "lineage_artifact_id"),
        ):
            _text(value, field)
        _utc(self.published_at, "published_at")
        _utc(self.retrieved_at, "retrieved_at")
        if len(self.content_hash) != 64 or any(char not in "0123456789abcdef" for char in self.content_hash):
            raise ValueError("content_hash must be a lowercase SHA-256 digest")
        if self.content_ref is not None:
            _text(self.content_ref, "content_ref")
        if self.api_version != RESEARCH_API_VERSION:
            raise ValueError(f"unsupported research contract version: {self.api_version}")


@dataclass(frozen=True)
class PassageReference:
    passage_id: str
    document_id: str
    text: str
    rank: int
    citation_ref: str
    source_ref: str
    provider: str
    provider_version: str
    published_at: str
    retrieved_at: str
    content_hash: str
    lineage_artifact_id: str
    api_version: str = RESEARCH_API_VERSION

    def __post_init__(self) -> None:
        for value, field in (
            (self.passage_id, "passage_id"),
            (self.document_id, "document_id"),
            (self.text, "text"),
            (self.citation_ref, "citation_ref"),
            (self.source_ref, "source_ref"),
            (self.provider, "provider"),
            (self.provider_version, "provider_version"),
            (self.content_hash, "content_hash"),
            (self.lineage_artifact_id, "lineage_artifact_id"),
        ):
            _text(value, field)
        if self.rank < 1:
            raise ValueError("rank must be positive")
        _utc(self.published_at, "published_at")
        _utc(self.retrieved_at, "retrieved_at")
        if len(self.content_hash) != 64 or any(char not in "0123456789abcdef" for char in self.content_hash):
            raise ValueError("content_hash must be a lowercase SHA-256 digest")
        if hashlib.sha256(self.text.encode("utf-8")).hexdigest() != self.content_hash:
            raise ValueError("content_hash does not match passage text")
        if self.api_version != RESEARCH_API_VERSION:
            raise ValueError(f"unsupported research contract version: {self.api_version}")


@dataclass(frozen=True)
class Citation:
    citation_id: str
    claim_id: str
    passage_id: str
    document_id: str
    citation_ref: str
    source_ref: str
    published_at: str
    retrieved_at: str
    content_hash: str
    lineage_artifact_id: str
    api_version: str = RESEARCH_API_VERSION

    def __post_init__(self) -> None:
        for value, field in (
            (self.citation_id, "citation_id"),
            (self.claim_id, "claim_id"),
            (self.passage_id, "passage_id"),
            (self.document_id, "document_id"),
            (self.citation_ref, "citation_ref"),
            (self.source_ref, "source_ref"),
            (self.content_hash, "content_hash"),
            (self.lineage_artifact_id, "lineage_artifact_id"),
        ):
            _text(value, field)
        _utc(self.published_at, "published_at")
        _utc(self.retrieved_at, "retrieved_at")
        if len(self.content_hash) != 64 or any(char not in "0123456789abcdef" for char in self.content_hash):
            raise ValueError("content_hash must be a lowercase SHA-256 digest")
        if self.api_version != RESEARCH_API_VERSION:
            raise ValueError(f"unsupported research contract version: {self.api_version}")


@dataclass(frozen=True)
class ClaimSupport:
    support_id: str
    claim_id: str
    passage_id: str
    citation_id: str
    document_id: str
    quote: str
    support_status: Literal["supported"]
    source_provider: str
    source_ref: str
    published_at: str
    retrieved_at: str
    content_hash: str
    lineage_artifact_id: str
    api_version: str = RESEARCH_API_VERSION

    def __post_init__(self) -> None:
        for value, field in (
            (self.support_id, "support_id"),
            (self.claim_id, "claim_id"),
            (self.passage_id, "passage_id"),
            (self.citation_id, "citation_id"),
            (self.document_id, "document_id"),
            (self.quote, "quote"),
            (self.source_provider, "source_provider"),
            (self.source_ref, "source_ref"),
            (self.content_hash, "content_hash"),
            (self.lineage_artifact_id, "lineage_artifact_id"),
        ):
            _text(value, field)
        if self.support_status != "supported":
            raise ValueError("claim support must be supported or omitted")
        _utc(self.published_at, "published_at")
        _utc(self.retrieved_at, "retrieved_at")
        if len(self.content_hash) != 64 or any(char not in "0123456789abcdef" for char in self.content_hash):
            raise ValueError("content_hash must be a lowercase SHA-256 digest")
        if self.api_version != RESEARCH_API_VERSION:
            raise ValueError(f"unsupported research contract version: {self.api_version}")


@dataclass(frozen=True)
class ResearchClaim:
    claim_id: str
    claim_text: str
    status: Literal["supported"]
    support_ids: tuple[str, ...]
    citation_ids: tuple[str, ...]
    document_ids: tuple[str, ...]
    confidence: float
    api_version: str = RESEARCH_API_VERSION

    def __post_init__(self) -> None:
        _text(self.claim_id, "claim_id")
        _text(self.claim_text, "claim_text")
        if self.status != "supported" or not self.support_ids or not self.citation_ids or not self.document_ids:
            raise ValueError("supported claims need support, citation, and document references")
        if not math.isfinite(self.confidence) or not 0 <= self.confidence <= 1:
            raise ValueError("claim confidence must be between 0 and 1")
        if self.api_version != RESEARCH_API_VERSION:
            raise ValueError(f"unsupported research contract version: {self.api_version}")


@dataclass(frozen=True)
class UnsupportedClaim:
    claim_id: str
    claim_text: str
    reason: str
    status: Literal["unsupported"] = "unsupported"
    api_version: str = RESEARCH_API_VERSION

    def __post_init__(self) -> None:
        _text(self.claim_id, "claim_id")
        _text(self.claim_text, "claim_text")
        _text(self.reason, "reason")
        if self.api_version != RESEARCH_API_VERSION:
            raise ValueError(f"unsupported research contract version: {self.api_version}")


@dataclass(frozen=True)
class EvidenceCoverage:
    total_claims: int
    supported_claims: int
    unsupported_claims: int
    retrieved_passages: int
    supported_passages: int
    coverage_ratio: float
    definition: str = "supported claims divided by all claims"
    api_version: str = RESEARCH_API_VERSION

    def __post_init__(self) -> None:
        if min(self.total_claims, self.supported_claims, self.unsupported_claims, self.retrieved_passages, self.supported_passages) < 0:
            raise ValueError("coverage counts must be non-negative")
        if self.supported_claims + self.unsupported_claims != self.total_claims:
            raise ValueError("coverage claim counts do not add up")
        expected = self.supported_claims / self.total_claims if self.total_claims else 0.0
        if not math.isclose(self.coverage_ratio, expected, rel_tol=0, abs_tol=1e-12):
            raise ValueError("coverage_ratio does not match claim counts")
        if self.supported_passages > self.retrieved_passages:
            raise ValueError("supported passages exceed retrieved passages")
        if self.api_version != RESEARCH_API_VERSION:
            raise ValueError(f"unsupported research contract version: {self.api_version}")


@dataclass(frozen=True)
class ResearchSynthesis:
    synthesis_id: str
    objective: str
    query: str
    summary: str
    claims: tuple[ResearchClaim, ...]
    unsupported_claims: tuple[UnsupportedClaim, ...]
    supports: tuple[ClaimSupport, ...]
    citations: tuple[Citation, ...]
    documents: tuple[DocumentReference, ...]
    passages: tuple[PassageReference, ...]
    coverage: EvidenceCoverage
    retrieval_fingerprint: str
    synthesis_fingerprint: str
    lineage_artifact_id: str
    evidence_artifact_id: str
    api_version: str = RESEARCH_API_VERSION

    def __post_init__(self) -> None:
        for value, field in (
            (self.synthesis_id, "synthesis_id"),
            (self.objective, "objective"),
            (self.query, "query"),
            (self.summary, "summary"),
            (self.retrieval_fingerprint, "retrieval_fingerprint"),
            (self.synthesis_fingerprint, "synthesis_fingerprint"),
            (self.lineage_artifact_id, "lineage_artifact_id"),
            (self.evidence_artifact_id, "evidence_artifact_id"),
        ):
            _text(value, field)
        if not self.claims and not self.unsupported_claims:
            raise ValueError("research synthesis needs claims or unsupported claims")
        if any(
            len(value) != 64 or any(char not in "0123456789abcdef" for char in value)
            for value in (self.retrieval_fingerprint, self.synthesis_fingerprint)
        ):
            raise ValueError("synthesis fingerprints must be SHA-256 digests")
        claim_ids = {claim.claim_id for claim in self.claims}
        unsupported_ids = {claim.claim_id for claim in self.unsupported_claims}
        passage_ids = {passage.passage_id for passage in self.passages}
        document_ids = {document.document_id for document in self.documents}
        citation_ids = {citation.citation_id for citation in self.citations}
        support_ids = {support.support_id for support in self.supports}
        supports_by_id = {support.support_id: support for support in self.supports}
        citations_by_id = {citation.citation_id: citation for citation in self.citations}
        if claim_ids.intersection(unsupported_ids):
            raise ValueError("claim cannot be both supported and unsupported")
        if any(claim_id not in claim_ids for claim_id in (support.claim_id for support in self.supports)):
            raise ValueError("claim support references an unknown claim")
        if any(support.passage_id not in passage_ids for support in self.supports):
            raise ValueError("claim support references an unknown passage")
        if any(support.citation_id not in citation_ids for support in self.supports):
            raise ValueError("claim support references an unknown citation")
        if any(citation.claim_id not in claim_ids for citation in self.citations):
            raise ValueError("citation references an unknown claim")
        if any(citation.passage_id not in passage_ids for citation in self.citations):
            raise ValueError("citation references an unknown passage")
        if any(citation.document_id not in document_ids for citation in self.citations):
            raise ValueError("citation references an unknown document")
        if any(support_id not in support_ids for claim in self.claims for support_id in claim.support_ids):
            raise ValueError("claim references an unknown support")
        for claim in self.claims:
            if any(supports_by_id[support_id].claim_id != claim.claim_id for support_id in claim.support_ids):
                raise ValueError("claim support belongs to a different claim")
            if any(citations_by_id[citation_id].claim_id != claim.claim_id for citation_id in claim.citation_ids):
                raise ValueError("claim citation belongs to a different claim")
        passages_by_id = {passage.passage_id: passage for passage in self.passages}
        citations_by_id = {citation.citation_id: citation for citation in self.citations}
        for support in self.supports:
            passage = passages_by_id[support.passage_id]
            citation = citations_by_id[support.citation_id]
            document = next(document for document in self.documents if document.document_id == passage.document_id)
            if support.quote != passage.text or support.document_id != passage.document_id:
                raise ValueError("claim support quote or document does not match passage")
            if hashlib.sha256(support.quote.encode("utf-8")).hexdigest() != support.content_hash:
                raise ValueError("claim support content_hash does not match quote")
            if support.content_hash != passage.content_hash or support.source_ref != passage.source_ref:
                raise ValueError("claim support provenance does not match passage")
            if citation.passage_id != passage.passage_id or citation.document_id != passage.document_id:
                raise ValueError("citation does not match passage")
            if citation.content_hash != passage.content_hash or citation.source_ref != passage.source_ref:
                raise ValueError("citation provenance does not match passage")
            if passage.source_ref != document.source_ref or passage.published_at != document.published_at:
                raise ValueError("passage provenance does not match document")
            if citation.published_at != document.published_at or citation.retrieved_at != passage.retrieved_at:
                raise ValueError("citation timestamps do not match source passage")
            if support.source_provider != passage.provider or support.retrieved_at != passage.retrieved_at:
                raise ValueError("claim support provider metadata does not match passage")
        expected_fingerprint = _synthesis_fingerprint(
            self.objective,
            self.query,
            self.retrieval_fingerprint,
            self.claims,
            self.unsupported_claims,
            self.coverage,
            self.supports,
            self.citations,
            self.documents,
            self.passages,
        )
        if self.synthesis_fingerprint != expected_fingerprint:
            raise ValueError("synthesis_fingerprint does not match synthesis content")
        if self.api_version != RESEARCH_API_VERSION:
            raise ValueError(f"unsupported research contract version: {self.api_version}")


class DeterministicResearchSynthesizer:
    """Turn retrieved passages into exact-quote claims without adding facts."""

    provider_version = "market-os-deterministic-synthesis-v1"

    def synthesize(
        self,
        objective: str,
        documents: tuple[DocumentRecord, ...],
        retrieval: RetrievalResult,
        *,
        retrieval_artifact_id: str,
        document_artifact_id: str,
        evidence_artifact_id: str,
    ) -> ResearchSynthesis:
        document_refs = tuple(
            DocumentReference(
                document.document_id,
                document.title,
                document.publisher,
                document.source_ref,
                document.published_at,
                document.retrieved_at,
                document.content_hash,
                document.license.classification,
                document.provenance.provider,
                document.provenance.source_ref,
                document_artifact_id,
                document.content_ref,
            )
            for document in documents
        )
        by_id = {document.document_id: document for document in documents}
        passages: list[PassageReference] = []
        citations: list[Citation] = []
        supports: list[ClaimSupport] = []
        claims: list[ResearchClaim] = []
        for passage in retrieval.passages:
            document = by_id[passage.document_id]
            passage_ref = PassageReference(
                passage.passage_id,
                passage.document_id,
                passage.text,
                passage.rank,
                passage.citation_ref,
                passage.source_ref,
                retrieval.provider,
                retrieval.provider_version,
                document.published_at,
                retrieval.retrieved_at,
                passage.content_hash,
                retrieval_artifact_id,
            )
            passages.append(passage_ref)
            claim_id = "claim-" + _digest({"query": retrieval.query, "passage": passage.passage_id})[:16]
            citation_id = "citation-" + _digest({"claim": claim_id, "passage": passage.passage_id})[:16]
            support_id = "support-" + _digest({"claim": claim_id, "quote": passage.text})[:16]
            citations.append(
                Citation(
                    citation_id,
                    claim_id,
                    passage.passage_id,
                    passage.document_id,
                    passage.citation_ref,
                    passage.source_ref,
                    document.published_at,
                    retrieval.retrieved_at,
                    passage.content_hash,
                    retrieval_artifact_id,
                )
            )
            supports.append(
                ClaimSupport(
                    support_id,
                    claim_id,
                    passage.passage_id,
                    citation_id,
                    passage.document_id,
                    passage.text,
                    "supported",
                    retrieval.provider,
                    passage.source_ref,
                    document.published_at,
                    retrieval.retrieved_at,
                    passage.content_hash,
                    retrieval_artifact_id,
                )
            )
            claims.append(ResearchClaim(claim_id, passage.text, "supported", (support_id,), (citation_id,), (passage.document_id,), 1.0))
        unsupported: tuple[UnsupportedClaim, ...] = ()
        if not claims:
            unsupported = (UnsupportedClaim("claim-unsupported-" + _digest(objective)[:16], objective, "retrieval returned no passages"),)
        coverage = EvidenceCoverage(
            len(claims) + len(unsupported),
            len(claims),
            len(unsupported),
            len(retrieval.passages),
            len({passage.passage_id for passage in retrieval.passages}),
            len(claims) / (len(claims) + len(unsupported)) if claims or unsupported else 0.0,
        )
        synthesis_fingerprint = _synthesis_fingerprint(
            objective,
            retrieval.query,
            retrieval.query_fingerprint,
            tuple(claims),
            unsupported,
            coverage,
            tuple(supports),
            tuple(citations),
            document_refs,
            tuple(passages),
        )
        return ResearchSynthesis(
            "synthesis-" + synthesis_fingerprint[:16],
            objective,
            retrieval.query,
            f"Deterministic grounded synthesis: {len(claims)} supported claims, {len(unsupported)} unsupported claims, {coverage.coverage_ratio:.0%} evidence coverage.",
            tuple(claims),
            unsupported,
            tuple(supports),
            tuple(citations),
            document_refs,
            tuple(passages),
            coverage,
            retrieval.query_fingerprint,
            synthesis_fingerprint,
            retrieval_artifact_id,
            evidence_artifact_id,
        )


def research_synthesis_from_dict(payload: dict) -> ResearchSynthesis:
    """Validate a persisted synthesis payload before inspection."""
    values = dict(payload)
    values["claims"] = tuple(
        ResearchClaim(
            **{
                **item,
                "support_ids": tuple(item.get("support_ids", ())),
                "citation_ids": tuple(item.get("citation_ids", ())),
                "document_ids": tuple(item.get("document_ids", ())),
            }
        )
        for item in values.get("claims", ())
    )
    values["unsupported_claims"] = tuple(UnsupportedClaim(**item) for item in values.get("unsupported_claims", ()))
    values["supports"] = tuple(ClaimSupport(**item) for item in values.get("supports", ()))
    values["citations"] = tuple(Citation(**item) for item in values.get("citations", ()))
    values["documents"] = tuple(DocumentReference(**item) for item in values.get("documents", ()))
    values["passages"] = tuple(PassageReference(**item) for item in values.get("passages", ()))
    values["coverage"] = EvidenceCoverage(**values["coverage"])
    try:
        return ResearchSynthesis(**values)
    except TypeError as exc:
        raise ValueError("research synthesis artifact is malformed") from exc
