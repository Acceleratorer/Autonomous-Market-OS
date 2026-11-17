"""Regenerate the U7 evidence catalog and report reproducibility drift."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping

from .research_brief import render_research_brief_files
from .synthetic_economic_report import render_synthetic_economic_report
from .tool_registry_report import render_tool_registry_report
from .u7_evidence_catalog import CANONICAL_BOUNDARY, build_catalog_from_files
from .u7_evidence_register import render_register

REPRODUCIBILITY_SCHEMA = "market-os.u7-p-evidence-reproducibility@v1"


class EvidenceReproducibilityError(ValueError):
    """Raised when a reproducibility input cannot be read or validated."""


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _source_sha256(raw: bytes) -> str:
    normalized = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(normalized).hexdigest()


def _read_object(path: str | Path, label: str) -> Mapping[str, Any]:
    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EvidenceReproducibilityError(f"cannot read {label}: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise EvidenceReproducibilityError(f"{label} must be an object")
    return payload


def _require_catalog_baseline(payload: Mapping[str, Any]) -> str:
    if payload.get("schema") != "market-os.u7-o-evidence-catalog@v1":
        raise EvidenceReproducibilityError("committed catalog schema is invalid")
    if payload.get("status") != "passed":
        raise EvidenceReproducibilityError("committed catalog status is invalid")
    fingerprint = payload.get("catalog_fingerprint")
    if not isinstance(fingerprint, str) or len(fingerprint) != 64 or any(character not in "0123456789abcdef" for character in fingerprint):
        raise EvidenceReproducibilityError("committed catalog fingerprint is invalid")
    return fingerprint


def _catalog_body(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key != "catalog_fingerprint"}


def _source_artifacts(paths: Mapping[str, str | Path], sources: Mapping[str, bytes]) -> list[dict[str, str]]:
    return [
        {"id": key, "artifact": Path(path).name, "sha256": _source_sha256(sources[key])}
        for key, path in paths.items()
    ]


def _same_path(left: str | Path, right: str | Path) -> bool:
    left_path = Path(left).resolve()
    right_path = Path(right).resolve()
    if left_path == right_path:
        return True
    try:
        return left_path.samefile(right_path)
    except OSError:
        return False


def _validate_output_paths(
    markdown_path: str | Path,
    json_path: str | Path,
    source_paths: Mapping[str, str | Path],
) -> None:
    if _same_path(markdown_path, json_path):
        raise EvidenceReproducibilityError("Markdown and JSON outputs must use different paths")
    for output in (markdown_path, json_path):
        if any(_same_path(output, source) for source in source_paths.values()):
            raise EvidenceReproducibilityError("report outputs must not overwrite source evidence")


def _stage_output(path: Path, contents: bytes) -> Path:
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(contents)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return temporary


def _publish_reports(markdown: Path, markdown_contents: bytes, output: Path, json_contents: bytes) -> None:
    targets = ((markdown, markdown_contents), (output, json_contents))
    for path, _ in targets:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and not path.is_file():
            raise EvidenceReproducibilityError(f"report output is not a file: {path}")
    previous = {path: path.read_bytes() if path.exists() else None for path, _ in targets}
    staged: dict[Path, Path] = {}
    published: list[Path] = []
    try:
        for path, contents in targets:
            staged[path] = _stage_output(path, contents)
        try:
            for path, _ in targets:
                os.replace(staged[path], path)
                published.append(path)
        except OSError as publish_error:
            rollback_error: OSError | None = None
            for path in reversed(published):
                try:
                    old_contents = previous[path]
                    if old_contents is None:
                        path.unlink(missing_ok=True)
                    else:
                        backup = _stage_output(path, old_contents)
                        try:
                            os.replace(backup, path)
                        finally:
                            backup.unlink(missing_ok=True)
                except OSError as exc:
                    rollback_error = exc
            if rollback_error is not None:
                raise EvidenceReproducibilityError("report publication failed and rollback was incomplete") from publish_error
            raise
    finally:
        for temporary in staged.values():
            temporary.unlink(missing_ok=True)


def _regenerate_catalogs(
    register_path: str | Path,
    drift_path: str | Path,
    economic_fixture: str | Path,
    tools_fixture: str | Path,
    research_fixture: str | Path,
) -> list[dict[str, Any]]:
    catalogs: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="market-os-u7-p-") as temporary:
        root = Path(temporary)
        for index in range(2):
            run_root = root / str(index)
            run_root.mkdir()
            register = run_root / "u7-n-unified-evidence-register.json"
            render_register(
                register_path,
                drift_path,
                markdown_path=run_root / "u7-n-unified-evidence-register.md",
                json_path=register,
            )
            economic = run_root / "u7-j-synthetic-economic-report.json"
            render_synthetic_economic_report(
                economic_fixture,
                markdown_path=run_root / "u7-j-synthetic-economic-report.md",
                json_path=economic,
            )
            tools = run_root / "u7-k-cli-tool-registry-report.json"
            render_tool_registry_report(
                tools_fixture,
                markdown_path=run_root / "u7-k-cli-tool-registry-report.md",
                json_path=tools,
            )
            research = run_root / "u7-l-research-brief-evidence.json"
            render_research_brief_files(
                research_fixture,
                run_root / "u7-l-research-brief.md",
                research,
            )
            catalogs.append(
                build_catalog_from_files(
                    {"register": register, "economic": economic, "tools": tools, "research": research}
                )
            )
    return catalogs


def build_reproducibility_report(
    *,
    catalog: str | Path,
    pack: str | Path,
    drift: str | Path,
    economic: str | Path,
    tools: str | Path,
    research: str | Path,
) -> dict[str, Any]:
    """Regenerate U7-N/J/K/L twice and compare both runs with U7-O."""
    source_paths = {
        "catalog": catalog,
        "pack": pack,
        "drift": drift,
        "economic_fixture": economic,
        "tools_fixture": tools,
        "research_fixture": research,
    }
    sources: dict[str, bytes] = {}
    for key, path in source_paths.items():
        try:
            sources[key] = Path(path).read_bytes()
        except OSError as exc:
            raise EvidenceReproducibilityError(f"cannot read source artifact {key}: {exc}") from exc
    with tempfile.TemporaryDirectory(prefix="market-os-u7-p-inputs-") as temporary:
        snapshot_root = Path(temporary)
        snapshots: dict[str, Path] = {}
        for key, path in source_paths.items():
            snapshot = snapshot_root / key / Path(path).name
            snapshot.parent.mkdir()
            snapshot.write_bytes(sources[key])
            snapshots[key] = snapshot
        committed = _read_object(snapshots["catalog"], "committed U7-O catalog")
        committed_fingerprint = _require_catalog_baseline(committed)
        committed_fingerprint_valid = _fingerprint(_catalog_body(committed)) == committed_fingerprint
        try:
            generated = _regenerate_catalogs(
                snapshots["pack"],
                snapshots["drift"],
                snapshots["economic_fixture"],
                snapshots["tools_fixture"],
                snapshots["research_fixture"],
            )
            regeneration_error: str | None = None
        except (OSError, KeyError, TypeError, ValueError) as exc:
            generated = []
            regeneration_error = type(exc).__name__
    run_fingerprints = [str(item["catalog_fingerprint"]) for item in generated]
    catalog_fingerprint_match = (
        committed_fingerprint_valid
        and bool(generated)
        and all(value == committed_fingerprint for value in run_fingerprints)
    )
    deterministic_runs = len(generated) == 2 and generated[0] == generated[1]
    catalog_body_match = len(generated) == 2 and all(
        _canonical(_catalog_body(item)) == _canonical(_catalog_body(committed)) for item in generated
    )
    boundary_safe = (
        len(generated) == 2
        and all(_canonical(item.get("boundary")) == _canonical(CANONICAL_BOUNDARY) for item in generated)
        and _canonical(committed.get("boundary")) == _canonical(CANONICAL_BOUNDARY)
    )
    checks = {
        "sources_hashes_present": all(len(_source_sha256(raw)) == 64 for raw in sources.values()),
        "regenerated_catalogs_valid": len(generated) == 2 and all(
            item.get("schema") == "market-os.u7-o-evidence-catalog@v1" and item.get("status") == "passed"
            for item in generated
        ),
        "committed_catalog_fingerprint_valid": committed_fingerprint_valid,
        "catalog_fingerprint_match": catalog_fingerprint_match,
        "deterministic_runs": deterministic_runs,
        "catalog_body_match": catalog_body_match,
        "boundaries_consistent": boundary_safe,
        "private_read_only_paper_only": boundary_safe,
        "no_provider_network_credentials": boundary_safe,
        "no_mutation_or_live_execution": boundary_safe,
    }
    mismatches: list[str] = []
    if regeneration_error is not None:
        mismatches.append("catalog_regeneration")
    else:
        if not committed_fingerprint_valid:
            mismatches.append("committed_catalog_fingerprint")
        if not catalog_fingerprint_match:
            mismatches.append("catalog_fingerprint")
        if not deterministic_runs:
            mismatches.append("deterministic_runs")
        if not catalog_body_match:
            mismatches.append("catalog_body")
        if not boundary_safe:
            mismatches.append("boundary")
    report: dict[str, Any] = {
        "schema": REPRODUCIBILITY_SCHEMA,
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "boundary": dict(CANONICAL_BOUNDARY),
        "committed_catalog_fingerprint": committed_fingerprint,
        "run_catalog_fingerprints": run_fingerprints,
        "source_artifacts": _source_artifacts(source_paths, sources),
        "mismatches": mismatches,
        "interpretation": (
            "U7-N/J/K/L evidence could not be regenerated into the committed U7-O catalog."
            if regeneration_error is not None
            else "U7-N/J/K/L evidence regenerates deterministically into the committed U7-O catalog without network, provider, mutation, or live-execution access."
        ),
        "next_gate": "Select the next bounded local, offline, synthetic, paper-only product after U7-P.",
    }
    if regeneration_error is not None:
        report["regeneration_error_type"] = regeneration_error
    report["reproducibility_fingerprint"] = _fingerprint(report)
    return report


def render_markdown(report: Mapping[str, Any]) -> str:
    sources = [f"| {item['id']} | `{item['artifact']}` | `{item['sha256']}` |" for item in report["source_artifacts"]]
    checks = [f"| {key} | {'PASS' if value else 'FAIL'} |" for key, value in report["checks"].items()]
    runs = [f"- Run {index}: `{fingerprint}`" for index, fingerprint in enumerate(report["run_catalog_fingerprints"], start=1)]
    mismatches = "\n".join(f"- `{item}`" for item in report["mismatches"]) or "- None"
    return "\n".join([
        "# U7-P Evidence Reproducibility Audit",
        "",
        f"- Status: **{report['status'].upper()}**",
        f"- Reproducibility fingerprint: `{report['reproducibility_fingerprint']}`",
        f"- Committed U7-O catalog: `{report['committed_catalog_fingerprint']}`",
        "",
        "## Regenerated catalogs",
        "",
        *runs,
        "",
        "## Audit checks",
        "",
        "| Check | Result |",
        "| --- | --- |",
        *checks,
        "",
        "## Source artifacts",
        "",
        "| Source | Artifact | SHA-256 |",
        "| --- | --- | --- |",
        *sources,
        "",
        "## Mismatches",
        "",
        mismatches,
        "",
        report["interpretation"],
        "",
    ])


def render_reproducibility_report(
    *,
    markdown_path: str | Path,
    json_path: str | Path,
    **paths: str | Path,
) -> dict[str, Any]:
    markdown = Path(markdown_path)
    output = Path(json_path)
    _validate_output_paths(markdown, output, paths)
    report = build_reproducibility_report(**paths)
    _publish_reports(
        markdown,
        render_markdown(report).encode("utf-8"),
        output,
        (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit U7 evidence reproducibility")
    for name in ("catalog", "pack", "drift", "economic", "tools", "research"):
        parser.add_argument(f"--{name}", required=True)
    parser.add_argument("--markdown", required=True)
    parser.add_argument("--json", dest="json_path", required=True)
    args = parser.parse_args(argv)
    try:
        report = render_reproducibility_report(
            catalog=args.catalog,
            pack=args.pack,
            drift=args.drift,
            economic=args.economic,
            tools=args.tools,
            research=args.research,
            markdown_path=args.markdown,
            json_path=args.json_path,
        )
    except (EvidenceReproducibilityError, KeyError, OSError, TypeError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps({"schema": report["schema"], "status": report["status"], "reproducibility_fingerprint": report["reproducibility_fingerprint"]}, sort_keys=True))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "EvidenceReproducibilityError",
    "REPRODUCIBILITY_SCHEMA",
    "build_reproducibility_report",
    "main",
    "render_markdown",
    "render_reproducibility_report",
]
