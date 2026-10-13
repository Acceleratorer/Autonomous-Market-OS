from __future__ import annotations

import json
from pathlib import Path

from market_os.contracts import Task, from_json
from market_os.orchestration.recovery import RecoveryReport, run_recovery_probes
from market_os.orchestration.openharness_adapter import OpenHarnessAdapter
from market_os.store import RunStore


FIXTURE = Path(__file__).parent / "fixtures" / "contracts" / "task.json"


def task_fixture() -> Task:
    return from_json(FIXTURE.read_text(encoding="utf-8"), Task)


def test_reference_recovery_is_explicitly_not_runtime_verified(tmp_path: Path) -> None:
    report = run_recovery_probes(tmp_path, task_fixture(), openharness_python=tmp_path / "missing-python")

    assert report.runtime_verified is False
    assert report.promotion_status == "Provisional"
    assert report.probes[0].runtime_verified is False
    assert "deployment-and-dependency-review" in report.blockers


def test_recovery_report_is_machine_readable(tmp_path: Path) -> None:
    output = tmp_path / "recovery.json"
    report = run_recovery_probes(tmp_path, task_fixture(), output_path=output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["promotion_status"] == report.promotion_status
    assert {"probe_name", "runtime_version", "event_trace", "passed", "runtime_verified"} <= set(payload["probes"][0])


def test_adapter_exposes_recovery_boundary(tmp_path: Path) -> None:
    adapter = OpenHarnessAdapter(store=RunStore(tmp_path / "store"))
    report = adapter.probe_recovery(task_fixture(), root=tmp_path / "probe")

    assert report["promotion_status"] == "Provisional"
    assert report["runtime_verified"] is False
