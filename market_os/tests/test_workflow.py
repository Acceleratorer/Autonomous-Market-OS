from __future__ import annotations

import json
import threading
import threading as thread_module
import urllib.request
from pathlib import Path

import pytest

from market_os.providers import default_providers
from market_os.store import RunStore
from market_os.workflow import MarketWorkflow
from market_os.api import make_handler
from http.server import ThreadingHTTPServer


def test_vertical_slice_persists_citations_backtest_paper_plan_and_events(tmp_path: Path) -> None:
    workflow = MarketWorkflow(RunStore(tmp_path))
    task = workflow.create_task("Compare diversified low-risk candidates", ["SPY", "QQQ"], "2026-01-02", "2026-01-06")
    result = workflow.run(task)
    assert result["run"]["status"] == "completed"
    assert result["research"]["citations"] == ["market-SPY", "market-QQQ", "document-policy"]
    assert result["order_plan"]["mode"] == "paper"
    assert result["risk"]["status"] == "approved"
    assert {event.kind for event in RunStore(tmp_path).events_for(result["run"]["run_id"])} >= {"run.started", "evidence.retrieved", "backtest.completed", "run.completed"}


def test_restart_can_inspect_persisted_run(tmp_path: Path) -> None:
    workflow = MarketWorkflow(RunStore(tmp_path))
    task = workflow.create_task("Inspect", ["SPY"], "2026-01-02", "2026-01-06")
    result = workflow.run(task)
    restarted = MarketWorkflow(RunStore(tmp_path))
    inspected = restarted.inspect_run(result["run"]["run_id"])
    assert inspected["run"]["status"] == "completed"
    assert {item["kind"] for item in inspected["artifacts"]} >= {"evidence", "research", "backtest", "order-plan", "risk-decision"}


def test_cancellation_is_terminal_and_durable(tmp_path: Path) -> None:
    market, backtest = default_providers()
    workflow = MarketWorkflow(RunStore(tmp_path), market, backtest)
    task = workflow.create_task("Cancel", ["SPY"], "2026-01-02", "2026-01-06")
    cancel = threading.Event()
    cancel.set()
    result = workflow.run(task, cancel)
    assert result["run"]["status"] == "cancelled"
    assert any(event.kind == "run.cancelled" for event in RunStore(tmp_path).events_for(result["run"]["run_id"]))


def test_failure_is_recorded(tmp_path: Path) -> None:
    class Broken:
        def retrieve(self, *_args):
            raise RuntimeError("provider unavailable")

    workflow = MarketWorkflow(RunStore(tmp_path), Broken(), default_providers()[1])
    task = workflow.create_task("Fail", ["SPY"], "2026-01-02", "2026-01-06")
    with pytest.raises(RuntimeError, match="provider unavailable"):
        workflow.run(task)
    events = list(RunStore(tmp_path).events.read_text(encoding="utf-8").splitlines())
    assert any(json.loads(line)["kind"] == "run.failed" for line in events)


def test_idempotency_replays_same_result_and_live_mode_is_rejected(tmp_path: Path) -> None:
    workflow = MarketWorkflow(RunStore(tmp_path))
    task = workflow.create_task("Compare", ["SPY"], "2026-01-02", "2026-01-06", idempotency_key="same-request")
    first = workflow.run(task)
    retry = workflow.run(workflow.create_task("Compare", ["SPY"], "2026-01-02", "2026-01-06", idempotency_key="same-request"))
    assert first == retry
    with pytest.raises(ValueError, match="live execution"):
        workflow.create_task("Live", ["SPY"], "2026-01-02", "2026-01-06", execution_mode="live")


def test_service_api_uses_same_workflow_and_exposes_run_events(tmp_path: Path) -> None:
    workflow = MarketWorkflow(RunStore(tmp_path))
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(workflow))
    thread = thread_module.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        payload = json.dumps({"objective": "Compare", "symbols": ["SPY"], "start": "2026-01-02", "end": "2026-01-06"}).encode()
        request = urllib.request.Request(f"http://127.0.0.1:{server.server_port}/v1/tasks", data=payload, headers={"Content-Type": "application/json"}, method="POST")
        result = json.loads(urllib.request.urlopen(request, timeout=2).read())
        run_id = result["run"]["run_id"]
        inspected = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{server.server_port}/v1/runs/{run_id}", timeout=2).read())
        assert inspected["events"][-1]["kind"] == "run.completed"
    finally:
        server.shutdown()
        thread.join(timeout=2)
