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
    raise SystemExit("usage: python scripts/ci_checks.py validate-evidence|secret-scan")


if __name__ == "__main__":
    raise SystemExit(main())
