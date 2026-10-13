from __future__ import annotations

import os
from pathlib import Path

import pytest

from market_os.contracts import from_json, Task
from market_os.orchestration.openharness_adapter import IsolatedOpenHarnessRuntime, _runtime_evidence_from_dict
from market_os.orchestration.parity import run_parity_harness


FIXTURE = Path(__file__).parent / "fixtures" / "contracts" / "task.json"


def task_fixture() -> Task:
    return from_json(FIXTURE.read_text(encoding="utf-8"), Task)


def test_isolated_runtime_requires_explicit_interpreter(tmp_path: Path) -> None:
    runtime = IsolatedOpenHarnessRuntime(tmp_path / "missing-python.exe")

    with pytest.raises(RuntimeError, match="interpreter does not exist"):
        runtime.execute(task_fixture(), _workflow(tmp_path), None)


def test_runtime_evidence_binds_child_session_to_market_run() -> None:
    evidence = _runtime_evidence_from_dict(
        {
            "events": [
                {
                    "event_id": "event-1",
                    "session_id": "session-1",
                    "name": "session.started",
                    "timestamp": "2026-10-13T00:00:00+00:00",
                    "payload": {},
                }
            ],
            "checks": [{"name": "session-lifecycle", "status": "match", "detail": "ok"}],
        },
        run_id="run-1",
    )

    assert evidence.events[0].session_id == "run-1"
    assert evidence.events[0].payload["runtime_session_id"] == "session-1"
    assert evidence.checks[0]["status"] == "match"


@pytest.mark.skipif(
    not os.environ.get("OPENHARNESS_PYTHON"),
    reason="set OPENHARNESS_PYTHON to the isolated OpenHarness interpreter for runtime parity",
)
def test_real_openharness_runtime_parity(tmp_path: Path) -> None:
    runtime = IsolatedOpenHarnessRuntime()
    report = run_parity_harness(tmp_path, task_fixture(), runtime=runtime)

    assert report.runtime_verified is True
    assert report.mismatches == ()
    assert any(check.name == "runtime-execution" for check in report.matches)


def _workflow(tmp_path: Path):
    from market_os.store import RunStore
    from market_os.workflow import MarketWorkflow

    return MarketWorkflow(RunStore(tmp_path / "store"))
