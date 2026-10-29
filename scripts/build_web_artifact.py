"""Validate and package the static, read-only web preview."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "apps" / "web" / "public"
LEGACY = ROOT / "docs" / "hosting" / "market-os"
FILES = ("index.html", ".htaccess", "DEPLOYMENT.txt")
FORBIDDEN_INDEX_MARKERS = (
    re.compile(rb"<\s*script\b", re.IGNORECASE),
    re.compile(rb"<\s*form\b", re.IGNORECASE),
    re.compile(rb"\b(?:fetch|XMLHttpRequest|WebSocket)\s*\(", re.IGNORECASE),
    re.compile(rb"https?://", re.IGNORECASE),
    re.compile(rb"\b(?:password|api[_-]?key|secret|credential)\b", re.IGNORECASE),
)


def _validate_source() -> None:
    source_entries = list(SOURCE.iterdir())
    if any(not path.is_file() for path in source_entries):
        raise SystemExit("web preview source contains a non-file entry")
    source_names = {path.name for path in source_entries}
    expected = set(FILES)
    if source_names != expected:
        raise SystemExit(f"web preview source file set differs: {sorted(source_names)}")
    legacy_entries = list(LEGACY.iterdir())
    if any(not path.is_file() for path in legacy_entries):
        raise SystemExit("legacy web preview contains a non-file entry")
    legacy_names = {path.name for path in legacy_entries}
    if legacy_names != expected:
        raise SystemExit(f"legacy web preview file set differs: {sorted(legacy_names)}")
    for name in FILES:
        source = (SOURCE / name).read_bytes()
        legacy = (LEGACY / name).read_bytes()
        if source != legacy:
            raise SystemExit(f"web preview copies differ: {name}")
        if name == "index.html":
            for marker in FORBIDDEN_INDEX_MARKERS:
                if marker.search(source):
                    raise SystemExit(f"static preview contains forbidden marker: {marker.pattern!r}")


def _validate_output(output: Path) -> None:
    entries = list(output.iterdir())
    if any(not path.is_file() for path in entries):
        raise SystemExit("packaged web preview contains a non-file entry")
    names = {path.name for path in entries}
    if names != set(FILES):
        raise SystemExit(f"packaged web preview file set differs: {sorted(names)}")
    for name in FILES:
        if (output / name).read_bytes() != (SOURCE / name).read_bytes():
            raise SystemExit(f"packaged web preview differs: {name}")


def _manifest_payload(root: Path) -> dict[str, object]:
    files = [
        {"path": name, "sha256": hashlib.sha256((root / name).read_bytes()).hexdigest(), "size_bytes": (root / name).stat().st_size}
        for name in FILES
    ]
    return {
        "schema": "market-os.web-static-artifact@v1",
        "source": "apps/web/public",
        "files": files,
        "artifact_fingerprint": hashlib.sha256(json.dumps(files, separators=(",", ":"), sort_keys=True).encode("utf-8")).hexdigest(),
        "boundary": {
            "synthetic_only": True,
            "paper_only": True,
            "read_only": True,
            "public_deployment": True,
            "authentication": False,
            "mutation_routes": False,
            "providers": False,
            "credentials": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    _validate_source()
    if args.check:
        if args.manifest is not None:
            parser.error("--manifest requires --output")
        return 0
    if args.output is None:
        parser.error("--output is required unless --check is set")
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        parser.error("output directory must be absent or empty")
    output.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        shutil.copyfile(SOURCE / name, output / name)
    _validate_output(output)
    if args.manifest is not None:
        manifest = args.manifest.resolve()
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps(_manifest_payload(output), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
