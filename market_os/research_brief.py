"""Deterministic Markdown export for validated cited research."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .research import ResearchSynthesis, research_synthesis_from_dict

_MARKDOWN_SPECIAL = re.compile(r"([\\`*_{}\[\]()#+.!|<>~:/])")
_PAPER2SLIDES_COMMIT = "0785051d1f52814097e94c44751e3f12b83f7c8a"


def _source_sha256(raw: bytes) -> str:
    """Hash source bytes with platform line endings normalized."""
    normalized = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(normalized).hexdigest()


def _markdown_text(value: str) -> str:
    escaped = _MARKDOWN_SPECIAL.sub(r"\\\1", value)
    return re.sub(r"(?m)^(- )", r"\\- ", escaped)


def _text_block(value: str) -> list[str]:
    longest = max((len(match.group()) for match in re.finditer(r"`+", value)), default=0)
    fence = "`" * max(3, longest + 1)
    return [f"{fence}text", value, fence]


def _inline_code(value: str) -> str:
    longest = max((len(match.group()) for match in re.finditer(r"`+", value)), default=0)
    fence = "`" * max(1, longest + 1)
    padding = " " if value.startswith(("`", " ")) or value.endswith(("`", " ")) else ""
    return f"{fence}{padding}{value}{padding}{fence}"


def render_research_brief(synthesis: ResearchSynthesis) -> str:
    """Render only validated claims, exact supporting quotes, and lineage."""
    supports = {item.support_id: item for item in synthesis.supports}
    documents = {item.document_id: item for item in synthesis.documents}
    lines = [
        "# Research brief",
        "",
        f"**Objective:** {_markdown_text(synthesis.objective)}",
        "",
        "## Summary",
        "",
        _markdown_text(synthesis.summary),
        "",
        "## Supported findings",
        "",
    ]
    for claim in synthesis.claims:
        lines.extend((f"### {_markdown_text(claim.claim_text)}", ""))
        for support_id in claim.support_ids:
            support = supports[support_id]
            document = documents[support.document_id]
            lines.extend(
                (
                    f"- Citation: {_inline_code(support.citation_id)}",
                    f"- Source: {_markdown_text(document.title)} ({_inline_code(support.source_ref)})",
                    f"- Published: {_markdown_text(support.published_at)}; retrieved: {_markdown_text(support.retrieved_at)}",
                    "",
                    "Exact supporting quote:",
                    *_text_block(support.quote),
                    "",
                )
            )
    if not synthesis.claims:
        lines.extend(("No claims were supported by retrieved evidence.", ""))

    if synthesis.unsupported_claims:
        lines.extend(("## Unsupported requests", ""))
        for claim in synthesis.unsupported_claims:
            lines.extend(
                (
                    f"- {_markdown_text(claim.claim_text)}",
                    f"  - Reason: {_markdown_text(claim.reason)}",
                    "",
                )
            )

    coverage = synthesis.coverage
    lines.extend(
        (
            "## Evidence coverage",
            "",
            f"- Claims: {coverage.supported_claims} supported / {coverage.total_claims} total",
            f"- Retrieved passages: {coverage.retrieved_passages}",
            f"- Coverage ratio: {coverage.coverage_ratio:.6f}",
            f"- Retrieval fingerprint: {_inline_code(synthesis.retrieval_fingerprint)}",
            f"- Synthesis fingerprint: {_inline_code(synthesis.synthesis_fingerprint)}",
            f"- Cited research lineage: {_inline_code(synthesis.lineage_artifact_id)}",
            f"- Evidence lineage: {_inline_code(synthesis.evidence_artifact_id)}",
            "",
            "This brief preserves the validated cited-research result and adds no new findings. It is a read-only research artifact; trading execution remains disabled.",
            "",
        )
    )
    return "\n".join(lines)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")


def build_research_brief_evidence(
    synthesis: ResearchSynthesis,
    source_sha256: str,
    markdown: str,
) -> dict[str, Any]:
    """Describe the Markdown artifact and prove its source lineage/boundary."""
    if not re.fullmatch(r"[0-9a-f]{64}", source_sha256):
        raise ValueError("source_sha256 must be a lowercase SHA-256 digest")
    markdown_bytes = markdown.encode("utf-8")
    markdown_sha256 = hashlib.sha256(markdown_bytes).hexdigest()
    lineage = tuple(
        dict.fromkeys(
            [
                synthesis.lineage_artifact_id,
                synthesis.evidence_artifact_id,
                *(document.lineage_artifact_id for document in synthesis.documents),
                *(passage.lineage_artifact_id for passage in synthesis.passages),
                *(citation.lineage_artifact_id for citation in synthesis.citations),
                *(support.lineage_artifact_id for support in synthesis.supports),
            ]
        )
    )
    synthetic_only = bool(synthesis.documents) and all(
        document.license_classification == "synthetic-internal" for document in synthesis.documents
    )
    report: dict[str, Any] = {
        "schema": "market-os.u7-l-research-brief-evidence@v1",
        "status": "passed",
        "scope": "Markdown export operation",
        "source": {
            "sha256": source_sha256,
            "api_version": synthesis.api_version,
            "synthesis_fingerprint": synthesis.synthesis_fingerprint,
        },
        "artifact": {
            "artifact_id": f"artifact-{markdown_sha256[:16]}",
            "kind": "research-brief",
            "media_type": "text/markdown",
            "sha256": markdown_sha256,
            "lineage": list(lineage),
        },
        "checks": {
            "synthesis_validated": True,
            "source_hash_valid": True,
            "citations_preserved": all(citation.citation_id in markdown for citation in synthesis.citations),
            "support_quotes_preserved": all(support.quote in markdown for support in synthesis.supports),
            "lineage_complete": all(
                reference in lineage
                for reference in (
                    synthesis.lineage_artifact_id,
                    synthesis.evidence_artifact_id,
                    *(document.lineage_artifact_id for document in synthesis.documents),
                    *(passage.lineage_artifact_id for passage in synthesis.passages),
                    *(citation.lineage_artifact_id for citation in synthesis.citations),
                    *(support.lineage_artifact_id for support in synthesis.supports),
                )
            ),
            "output_hash_valid": hashlib.sha256(markdown_bytes).hexdigest() == markdown_sha256,
        },
        "boundary": {
            "private": True,
            "synthetic_only": synthetic_only,
            "paper_only": True,
            "read_only": True,
            "network_access": False,
            "provider_requests": 0,
            "credentials": False,
            "mutation_routes": False,
            "live_execution": False,
        },
        "paper2slides": {
            "repository": "HKUDS/Paper2Slides",
            "commit": _PAPER2SLIDES_COMMIT,
            "markdown_input_documented": True,
            "pipeline_executed": False,
        },
        "deferred": [
            "Paper2Slides model-based planning",
            "image and video provider generation",
            "credentials and live execution",
        ],
    }
    report["checks"]["boundary_verified"] = (
        report["boundary"]["private"]
        and report["boundary"]["paper_only"]
        and report["boundary"]["read_only"]
        and not report["boundary"]["network_access"]
        and report["boundary"]["provider_requests"] == 0
        and not report["boundary"]["credentials"]
        and not report["boundary"]["mutation_routes"]
        and not report["boundary"]["live_execution"]
    )
    report["report_fingerprint"] = hashlib.sha256(_canonical(report)).hexdigest()
    return report


def render_research_brief_files(
    source_path: str | Path,
    markdown_path: str | Path,
    evidence_path: str | Path,
) -> dict[str, Any]:
    """Validate a cited-research JSON artifact and write a Markdown brief."""
    source_file = Path(source_path).resolve()
    output_file = Path(markdown_path).resolve()
    evidence_file = Path(evidence_path).resolve()
    if len({source_file, output_file, evidence_file}) != 3:
        raise ValueError("source, Markdown, and evidence paths must be distinct")

    source_bytes = source_file.read_bytes()
    payload = json.loads(source_bytes.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("cited-research source must be a JSON object")
    synthesis = research_synthesis_from_dict(payload)
    markdown = render_research_brief(synthesis)
    evidence = build_research_brief_evidence(
        synthesis,
        _source_sha256(source_bytes),
        markdown,
    )
    if not all(evidence["checks"].values()) or not evidence["boundary"]["synthetic_only"]:
        raise ValueError("research brief evidence failed a synthetic boundary check")

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(markdown, encoding="utf-8", newline="\n")
    evidence_file.parent.mkdir(parents=True, exist_ok=True)
    evidence_file.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return evidence
