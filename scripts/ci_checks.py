"""Small dependency-free checks used by the fusion repository CI workflows."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs" / "evidence"
SCAN_ROOTS = (ROOT / "market_os", ROOT / "scripts", ROOT / ".github")
SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
)


def validate_evidence() -> None:
    paths = sorted(EVIDENCE.glob("*.json"))
    if not paths:
        raise SystemExit("no evidence JSON files found")
    for path in paths:
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SystemExit(f"invalid evidence JSON: {path}: {exc}") from exc
    print(f"validated {len(paths)} evidence JSON files")


def validate_m2_8_evidence() -> None:
    path = EVIDENCE / "m2.8-live-smoke.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "schema", "status", "live_smoke_run", "provider", "endpoint", "model",
        "data_class", "request_count", "retry_count", "max_input_bytes",
        "max_output_tokens", "max_spend_usd", "timeout_seconds", "store",
        "payload_bytes", "payload_sha256", "synthesis_fingerprint", "redaction", "execution_reserved",
        "grounding", "citation_validation", "fallback", "persisted_response", "approval",
    }
    missing = sorted(required.difference(payload))
    if missing:
        raise SystemExit("M2.8 evidence missing fields: " + ", ".join(missing))
    if payload["schema"] != "market-os.m2.8.live-smoke.v1":
        raise SystemExit("unexpected M2.8 evidence schema")
    if payload["data_class"] != "synthetic-internal" or payload["request_count"] not in {0, 1}:
        raise SystemExit("M2.8 evidence has unsafe data class or request count")
    if payload["retry_count"] != 0:
        raise SystemExit("M2.8 smoke evidence records a retry")
    if payload["max_input_bytes"] > 16000 or payload["max_output_tokens"] > 512 or payload["max_spend_usd"] > 0.02 or payload["timeout_seconds"] > 20:
        raise SystemExit("M2.8 evidence exceeds approved bounds")
    if payload["store"] is not False or payload["persisted_response"] is not False:
        raise SystemExit("M2.8 response storage is not disabled")
    if payload["approval"].get("adapter") is not True:
        raise SystemExit("M2.8 evidence is missing adapter approval")
    if payload["request_count"] == 0:
        pending = payload["status"] == "pending-approval" and payload["approval"].get("m2_8_execution") is False and payload["execution_reserved"] is False
        reserved = payload["status"] == "execution-reserved" and payload["approval"].get("m2_8_execution") is True and payload["execution_reserved"] is True
        if payload["live_smoke_run"] or not (pending or reserved):
            raise SystemExit("M2.8 zero-request evidence has an invalid approval or reservation state")
    elif payload["status"] not in {
        "Passed — one approved synthetic smoke completed and validated",
        "Passed with fallback — transport completed but deterministic fallback was required",
        "Failed safely — request was rejected or failed without unsafe side effects",
    } or not payload["live_smoke_run"] or payload["approval"].get("m2_8_execution") is not True or payload["execution_reserved"] is not True:
        raise SystemExit("M2.8 executed evidence is missing its approval or live-request status")
    if payload["redaction"].get("api_key") != "omitted" or payload["redaction"].get("raw_response") != "omitted":
        raise SystemExit("M2.8 evidence redaction is incomplete")
    print("validated M2.8 live-smoke evidence")


def _tracked_text_files() -> list[Path]:
    """Scan executable/project inputs, excluding historical evidence and probes."""
    paths: list[Path] = []
    for scan_root in SCAN_ROOTS:
        if not scan_root.exists():
            continue
        paths.extend(path for path in scan_root.rglob("*") if path.is_file())
    return paths


def secret_scan() -> None:
    findings: list[str] = []
    for path in _tracked_text_files():
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                findings.append(str(path.relative_to(ROOT)))
                break
    if findings:
        raise SystemExit("high-confidence secret-like material found: " + ", ".join(findings))
    print("secret scan passed")


def main(argv: list[str] | None = None) -> int:
    command = (argv or sys.argv[1:])[:1]
    if command == ["validate-evidence"]:
        validate_evidence()
        return 0
    if command == ["secret-scan"]:
        secret_scan()
        return 0
    if command == ["validate-m2-8-evidence"]:
        validate_m2_8_evidence()
        return 0
    raise SystemExit("usage: python scripts/ci_checks.py validate-evidence|validate-m2-8-evidence|secret-scan")


if __name__ == "__main__":
    raise SystemExit(main())
