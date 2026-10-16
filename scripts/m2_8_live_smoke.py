"""Prepare or execute the single approval-gated M2.8 synthetic smoke."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from market_os.adapters.openai_summary import OpenAIConfig, OpenAIResponsesSummaryProvider  # noqa: E402
from market_os.model_summary import gate_summary, make_summary_request  # noqa: E402
from market_os.providers import RetrievedPassage, RetrievalResult  # noqa: E402
from market_os.research import DeterministicResearchSynthesizer  # noqa: E402

CORPUS = ROOT / "market_os" / "tests" / "fixtures" / "lightrag" / "corpus.json"
EVIDENCE = ROOT / "docs" / "evidence" / "m2.8-live-smoke.json"
LIVE_SMOKE_APPROVAL = "MARKET_OS_M2_8_LIVE_SMOKE_APPROVED"
LIVE_SMOKE_BUDGET_USD = 0.02
OBJECTIVE = (
    "Produce a short synthetic ETF research summary. Preserve exact citations, "
    "label every inference, and do not provide investment advice or trading authorization."
)


def _synthesis():
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    document = corpus["documents"][0]
    text = document["content"]
    passage = RetrievedPassage(
        "doc-spy-factsheet:chunk-0",
        document["document_id"],
        text,
        1,
        "citation:doc-spy-factsheet:chunk-0",
        document["source_ref"],
        hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )
    retrieval = RetrievalResult(
        OBJECTIVE,
        (document["document_id"],),
        (passage,),
        (passage.citation_ref,),
        "synthetic-fixture",
        "m2.8-v1",
        document["retrieved_at"],
        hashlib.sha256(OBJECTIVE.encode("utf-8")).hexdigest(),
        (document["content_hash"],),
    )
    from market_os.providers import DocumentRecord, LicenseMetadata, Provenance

    record = DocumentRecord(
        document["document_id"],
        document["title"],
        document["publisher"],
        document["source_ref"],
        document["published_at"],
        document["retrieved_at"],
        tuple(document["symbols"]),
        document["media_type"],
        document["content_hash"],
        LicenseMetadata("synthetic-internal", "internal fixture", "Market OS", ("not for redistribution",)),
        Provenance("synthetic-fixture", document["source_ref"], document["retrieved_at"]),
    )
    return DeterministicResearchSynthesizer().synthesize(
        OBJECTIVE,
        (record,),
        retrieval,
        retrieval_artifact_id="artifact-m2-8-retrieval",
        document_artifact_id="artifact-m2-8-documents",
        evidence_artifact_id="artifact-m2-8-evidence",
    )


def _config_values(*, execute: bool) -> dict[str, str]:
    values = dict(os.environ)
    defaults = {
        "OPENAI_API_KEY": "offline-validation-placeholder",
        "MARKET_OS_OPENAI_LIVE_APPROVED": "1",
        "MARKET_OS_OPENAI_MODEL": "gpt-6.1-sol",
        "MARKET_OS_OPENAI_MAX_REQUESTS": "1",
        "MARKET_OS_OPENAI_MAX_OUTPUT_TOKENS": "512",
        "MARKET_OS_OPENAI_MAX_INPUT_BYTES": "16000",
        "MARKET_OS_OPENAI_MAX_SPEND_USD": f"{LIVE_SMOKE_BUDGET_USD:.2f}",
        "MARKET_OS_OPENAI_REQUEST_TIMEOUT_SECONDS": "20",
        "MARKET_OS_OPENAI_MAX_RETRIES": "0",
        "MARKET_OS_OPENAI_DATA_RETENTION_ACK": "1",
        "MARKET_OS_NON_PRODUCTION": "1",
        "MARKET_OS_PAPER_ONLY": "1",
    }
    if execute:
        required = set(defaults) - {"OPENAI_API_KEY"}
        required.add("OPENAI_API_KEY")
        missing = sorted(name for name in required if not values.get(name))
        if missing:
            if LIVE_SMOKE_APPROVAL not in values or values.get(LIVE_SMOKE_APPROVAL) != "1":
                raise ValueError(f"{LIVE_SMOKE_APPROVAL}=1 is required for the live smoke")
            raise ValueError("live execution configuration is missing: " + ", ".join(missing))
        if values.get(LIVE_SMOKE_APPROVAL) != "1":
            raise ValueError(f"{LIVE_SMOKE_APPROVAL}=1 is required for the live smoke")
        if values.get("OPENAI_API_KEY") == "offline-validation-placeholder":
            raise ValueError("offline validation placeholder cannot be used for live execution")
    else:
        for name, value in defaults.items():
            values.setdefault(name, value)
    if values.get("MARKET_OS_OPENAI_MAX_REQUESTS") != "1":
        raise ValueError("M2.8 requires MARKET_OS_OPENAI_MAX_REQUESTS=1")
    if values.get("MARKET_OS_OPENAI_MAX_RETRIES") != "0":
        raise ValueError("M2.8 requires MARKET_OS_OPENAI_MAX_RETRIES=0")
    try:
        timeout = float(values["MARKET_OS_OPENAI_REQUEST_TIMEOUT_SECONDS"])
    except (KeyError, ValueError) as exc:
        raise ValueError("M2.8 timeout must be numeric") from exc
    if not math.isfinite(timeout) or not 0 < timeout <= 20:
        raise ValueError("M2.8 timeout must be greater than zero and at most 20 seconds")
    try:
        spend_limit = float(values["MARKET_OS_OPENAI_MAX_SPEND_USD"])
    except (KeyError, ValueError) as exc:
        raise ValueError("M2.8 spend limit must be numeric") from exc
    if not math.isfinite(spend_limit) or not 0 < spend_limit <= LIVE_SMOKE_BUDGET_USD:
        raise ValueError(f"M2.8 spend limit must be greater than zero and at most ${LIVE_SMOKE_BUDGET_USD:.2f}")
    return values


def _prepared_evidence(synthesis, payload: dict[str, Any], encoded: bytes, config: OpenAIConfig) -> dict[str, Any]:
    return {
        "schema": "market-os.m2.8.live-smoke.v1",
        "date": datetime.now(timezone.utc).date().isoformat(),
        "status": "pending-approval",
        "live_smoke_run": False,
        "provider": "OpenAI Responses API",
        "endpoint": "https://api.openai.com/v1/responses",
        "model": "gpt-6.1-sol",
        "data_class": "synthetic-internal",
        "request_count": 0,
        "retry_count": 0,
        "max_input_bytes": config.max_input_bytes,
        "max_output_tokens": config.max_output_tokens,
        "max_spend_usd": config.max_spend_usd,
        "estimated_worst_case_cost_usd": (
            len(encoded) * 2.0 / 1_000_000
            + config.max_output_tokens * 10.0 / 1_000_000
        ),
        "timeout_seconds": config.timeout_seconds,
        "approval": {"adapter": True, "m2_8_execution": False},
        "execution_reserved": False,
        "store": False,
        "tools": [],
        "payload_bytes": len(encoded),
        "payload_sha256": hashlib.sha256(encoded).hexdigest(),
        "synthesis_fingerprint": synthesis.synthesis_fingerprint,
        "citation_ids": [item.citation_id for item in synthesis.citations],
        "passage_ids": [item.passage_id for item in synthesis.passages],
        "redaction": {"api_key": "omitted", "raw_request": "omitted", "raw_response": "omitted"},
        "grounding": "pending-live-response",
        "citation_validation": "pending-live-response",
        "fallback": "deterministic M2.3 synthesis preserved on provider failure or gate rejection",
        "persisted_response": False,
        "retention_policy": "store=false; account-specific eligibility must be confirmed before execution",
        "official_sources": [
            "https://developers.openai.com/api/docs/models/gpt-6.1-sol",
            "https://developers.openai.com/api/docs/guides/your-data",
            "https://developers.openai.com/api/docs/guides/rate-limits",
            "https://developers.openai.com/api/reference/resources/responses/methods/create",
        ],
    }


def _write_evidence(path: Path, evidence: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _reserve_execution(path: Path, payload_sha256: str, synthesis_fingerprint: str) -> None:
    if path.resolve() != EVIDENCE.resolve():
        raise ValueError("live execution is restricted to the prepared M2.8 evidence path")
    if not path.exists():
        raise ValueError("run offline preparation first; no pending M2.8 evidence exists")
    try:
        evidence = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("existing M2.8 evidence is unreadable") from exc
    marker = path.with_name(path.name + ".execution-reserved")
    if (
        evidence.get("status") != "pending-approval"
        or evidence.get("request_count") != 0
        or evidence.get("execution_reserved") is True
        or evidence.get("payload_sha256") != payload_sha256
        or evidence.get("synthesis_fingerprint") != synthesis_fingerprint
    ):
        raise ValueError("M2.8 live-smoke execution has already been consumed or does not match prepared evidence")
    try:
        with marker.open("x", encoding="utf-8") as handle:
            json.dump({"payload_sha256": payload_sha256, "synthesis_fingerprint": synthesis_fingerprint}, handle)
    except FileExistsError as exc:
        raise ValueError("M2.8 live-smoke execution has already been consumed") from exc
    evidence.update(
        {
            "execution_reserved": True,
            "execution_reserved_at": datetime.now(timezone.utc).isoformat(),
            "approval": {"adapter": True, "m2_8_execution": True},
            "status": "execution-reserved",
        }
    )
    _write_evidence(path, evidence)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="run the one live request after both approval gates are set")
    parser.add_argument("--evidence", type=Path, default=EVIDENCE)
    args = parser.parse_args(argv)

    synthesis = _synthesis()
    values = _config_values(execute=args.execute)
    values.setdefault("MARKET_OS_OPENAI_MAX_REQUESTS", "1")
    values.setdefault("MARKET_OS_OPENAI_MAX_RETRIES", "0")
    values.setdefault("MARKET_OS_OPENAI_MAX_SPEND_USD", f"{LIVE_SMOKE_BUDGET_USD:.2f}")
    values.setdefault("MARKET_OS_OPENAI_MAX_OUTPUT_TOKENS", "512")
    values.setdefault("MARKET_OS_OPENAI_MAX_INPUT_BYTES", "16000")
    values.setdefault("MARKET_OS_OPENAI_REQUEST_TIMEOUT_SECONDS", "20")
    config = OpenAIConfig.from_mapping(values)
    provider = OpenAIResponsesSummaryProvider(config)
    request = make_summary_request(OBJECTIVE, synthesis, provider.prompt_version)
    payload = provider._request_payload(request, synthesis)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if len(encoded) > config.max_input_bytes:
        raise ValueError("synthetic smoke payload exceeds configured input bound")
    estimated_worst_case_cost = (
        len(encoded) * 2.0 / 1_000_000
        + config.max_output_tokens * 10.0 / 1_000_000
    )
    if config.max_spend_usd < estimated_worst_case_cost:
        raise ValueError("configured spend ceiling is below the bounded request estimate")
    if not args.execute:
        if args.evidence.with_name(args.evidence.name + ".execution-reserved").exists():
            raise ValueError("M2.8 live-smoke execution has already been consumed")
        if args.evidence.exists():
            try:
                existing = json.loads(args.evidence.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ValueError("existing M2.8 evidence is unreadable") from exc
            if existing.get("status") != "pending-approval" or existing.get("request_count") != 0 or existing.get("execution_reserved") is True:
                raise ValueError("M2.8 live-smoke execution has already been consumed")
        evidence = _prepared_evidence(synthesis, payload, encoded, config)
        _write_evidence(args.evidence, evidence)
        print(json.dumps({"status": evidence["status"], "payload_bytes": len(encoded), "payload_sha256": evidence["payload_sha256"]}, sort_keys=True))
        return 0

    _reserve_execution(args.evidence, hashlib.sha256(encoded).hexdigest(), synthesis.synthesis_fingerprint)
    request_started = datetime.now(timezone.utc)
    summary = gate_summary(provider, OBJECTIVE, synthesis, synthesis_artifact_id="artifact-m2-8-cited-research")
    request_finished = datetime.now(timezone.utc)
    evidence = _prepared_evidence(synthesis, payload, encoded, config)
    evidence.update(
        {
            "status": (
                "Passed — one approved synthetic smoke completed and validated"
                if summary.gate.status == "approved"
                else "Passed with fallback — transport completed but deterministic fallback was required"
                if provider.last_response_metadata is not None
                else "Failed safely — request was rejected or failed without unsafe side effects"
                if provider.attempts > 0
                else "Blocked — provider/configuration/approval requirements incomplete"
            ),
            "live_smoke_run": provider.attempts == 1,
            "request_count": provider.attempts,
            "retry_count": max(0, provider.attempts - 1),
            "request_started_at": request_started.isoformat(),
            "request_finished_at": request_finished.isoformat(),
            "response_received_at": provider.last_response_received_at,
            "approval": {"adapter": True, "m2_8_execution": True},
            "execution_reserved": True,
            "elapsed_seconds": (request_finished - request_started).total_seconds(),
            "response_metadata": provider.last_response_metadata,
            "error_metadata": provider.last_error_metadata,
            "usage": {
                "input_tokens": summary.usage.input_units,
                "output_tokens": summary.usage.output_units,
                "estimated_cost_usd": summary.usage.estimated_cost,
            },
            "grounding": summary.gate.status,
            "citation_validation": summary.validation.status,
            "fallback": summary.gate.deterministic_fallback,
        }
    )
    _write_evidence(args.evidence, evidence)
    print(json.dumps({"status": evidence["status"], "request_count": evidence["request_count"], "retry_count": evidence["retry_count"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
