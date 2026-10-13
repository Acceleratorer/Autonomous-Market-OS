from __future__ import annotations

import json
from pathlib import Path

from market_os.contracts import Task, from_json
from market_os.orchestration.openharness_adapter import OpenHarnessAdapter, OpenHarnessEvent, map_openharness_event
from market_os.orchestration.parity import ParityCheck, compare_results, run_parity_harness
from market_os.store import RunStore


FIXTURE = Path(__file__).parent / "fixtures" / "contracts" / "task.json"


def task_fixture() -> Task:
    return from_json(FIXTURE.read_text(encoding="utf-8"), Task)


def test_openharness_fixture_parity_matches_reference(tmp_path: Path) -> None:
    report = run_parity_harness(tmp_path, task_fixture())

    assert report.runtime_verified is False
    assert report.mismatches == ()
    assert [check.name for check in report.matches] == [
        "result.research",
        "result.backtest",
        "result.order_plan",
        "result.risk",
        "paper-only",
        "completion",
        "event-order",
        "event-timestamps",
        "artifact-content-addressing",
        "artifact-lineage",
        "evidence-citations",
        "risk-decision",
        "contract-serialization",
        "cli-api-shape",
        "cancellation",
        "failure-normalization",
        "idempotency",
        "restart-inspection",
        "paper-only-enforcement",
    ]
    assert {check.name for check in report.translations} == {"task-creation", "event-mapping"}
    assert {check.name for check in report.unsupported} == {"runtime-execution"}
    assert report.promotable is False


def test_adapter_persists_translated_events_and_supports_restart(tmp_path: Path) -> None:
    adapter = OpenHarnessAdapter(store=RunStore(tmp_path))
    result = adapter.run(task_fixture())
    run_id = result["run"]["run_id"]

    runtime_events = adapter.runtime_events_for(run_id)
    assert runtime_events[0].name == "session.started"
    assert runtime_events[-1].name == "session.completed"
    assert adapter.inspect_run(run_id)["events"][-1]["actor"] == "openharness"

    restarted = OpenHarnessAdapter(store=RunStore(tmp_path))
    inspected = restarted.inspect_run(run_id)
    assert inspected["run"]["status"] == "completed"
    assert inspected["events"][-1]["kind"] == "run.completed"


def test_openharness_event_mapping_preserves_market_os_kind() -> None:
    event = map_openharness_event(
        OpenHarnessEvent(
            "event-1",
            "run-1",
            "session.completed",
            "2026-10-13T00:00:00+00:00",
            {"market_os_kind": "run.completed", "artifact_ids": ["artifact-1"]},
        )
    )
    assert event.kind == "run.completed"
    assert event.actor == "openharness"
    assert event.payload == {"artifact_ids": ["artifact-1"]}


def test_parity_mismatch_reporting_is_explicit() -> None:
    reference = {
        "research": {"citations": ["evidence-1"]},
        "backtest": {"return_pct": 1.0},
        "order_plan": {"mode": "paper"},
        "risk": {"status": "approved"},
        "task": {"execution_mode": "paper"},
    }
    candidate = json.loads(json.dumps(reference))
    candidate["risk"]["status"] = "rejected"

    checks = compare_results(reference, candidate)

    assert ParityCheck("result.risk", "mismatch", "risk payload differs") in checks
    assert all(check.status != "unsupported" for check in checks)
