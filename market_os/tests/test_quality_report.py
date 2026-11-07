from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from market_os import cli
from market_os.quality_benchmark import _report_fingerprint, run_quality_benchmark
from market_os.quality_report import render_quality_report


FIXTURE = Path(__file__).parent / "fixtures" / "quality" / "benchmark.json"


def test_u7_g_quality_report_is_stable_and_explicitly_not_promoted(tmp_path: Path) -> None:
    benchmark = run_quality_benchmark(tmp_path / "store", FIXTURE)
    first = render_quality_report(
        benchmark,
        markdown_path=tmp_path / "first.md",
        json_path=tmp_path / "first.json",
    )
    second = render_quality_report(
        benchmark,
        markdown_path=tmp_path / "second.md",
        json_path=tmp_path / "second.json",
    )

    assert first == second
    assert first["schema"] == "market-os.u7-g-quality-benchmark-report@v1"
    assert first["status"] == "passed"
    assert first["promotion"]["status"].startswith("Not ready")
    assert first["promotion"]["estimated_cost"] is None
    assert "latency_ms_p95" not in first["metrics"]
    assert json.loads((tmp_path / "first.json").read_text(encoding="utf-8")) == first
    assert (tmp_path / "first.md").read_text(encoding="utf-8").startswith("# U7-G Deterministic Quality Benchmark Report")


def test_u7_g_rejects_tampered_fingerprint_and_unsafe_safety(tmp_path: Path) -> None:
    benchmark = run_quality_benchmark(tmp_path / "store", FIXTURE)

    tampered = copy.deepcopy(benchmark)
    tampered["cases"][0]["lineage"] = ["fixture:tampered"]
    with pytest.raises(ValueError, match="benchmark fingerprint mismatch"):
        render_quality_report(tampered)

    unsafe = copy.deepcopy(benchmark)
    unsafe["safety"]["external_provider_called"] = True
    unsafe["benchmark_fingerprint"] = _report_fingerprint(unsafe)
    unsafe["replay"]["fingerprint"] = unsafe["benchmark_fingerprint"]
    with pytest.raises(ValueError, match="safety boundary is unsafe"):
        render_quality_report(unsafe)


def test_u7_g_cli_writes_json_and_markdown(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main([
        "benchmark",
        "report",
        "--store-root",
        str(tmp_path / "store"),
        "--fixture",
        str(FIXTURE),
        "--markdown",
        str(tmp_path / "report.md"),
        "--json",
        str(tmp_path / "report.json"),
    ]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["schema"] == "market-os.u7-g-quality-benchmark-report@v1"
    assert json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))["status"] == "passed"
    assert (tmp_path / "report.md").is_file()
