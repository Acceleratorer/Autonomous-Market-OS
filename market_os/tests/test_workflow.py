from __future__ import annotations

import json
import threading
import threading as thread_module
import urllib.request
from pathlib import Path

import pytest

import market_os.api as api
from market_os.providers import default_providers
from market_os.contracts import Run, RunEvent
from market_os.store import RunStore
from market_os.workflow import MarketWorkflow
from market_os.api import make_handler, serve
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


def test_event_persistence_failure_terminalizes_run_and_records_recovery_metadata(tmp_path: Path) -> None:
    class FailRunStartedOnce(RunStore):
        def __init__(self, root: Path) -> None:
            super().__init__(root)
            self.failed = False

        def append_event(self, event) -> None:
            if event.kind == "run.started" and not self.failed:
                self.failed = True
                raise OSError("event index unavailable")
            super().append_event(event)

    workflow = MarketWorkflow(FailRunStartedOnce(tmp_path))
    task = workflow.create_task("Persist", ["SPY"], "2026-01-02", "2026-01-06")
    with pytest.raises(OSError, match="event index unavailable"):
        workflow.run(task)

    runs = [json.loads(line) for line in RunStore(tmp_path).runs.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert runs[-1]["status"] == "failed"
    assert runs[-1]["error"].startswith("persistence_error:")
    events = RunStore(tmp_path).events_for(runs[-1]["run_id"])
    assert events[-1].kind == "run.failed"
    assert events[-1].provenance["recovery"]["operation"] == "event.append"


def test_artifact_persistence_cancellation_is_terminal_and_partial_artifact_is_auditable(tmp_path: Path) -> None:
    class CancelDuringArtifactStore(RunStore):
        def __init__(self, root: Path, cancel: threading.Event) -> None:
            super().__init__(root)
            self.cancel = cancel

        def write_artifact(self, run_id, kind, payload, lineage=()):
            artifact = super().write_artifact(run_id, kind, payload, lineage)
            if kind == "evidence":
                self.cancel.set()
            return artifact

    cancel = threading.Event()
    store = CancelDuringArtifactStore(tmp_path, cancel)
    workflow = MarketWorkflow(store)
    task = workflow.create_task("Cancel persistence", ["SPY"], "2026-01-02", "2026-01-06")
    result = workflow.run(task, cancel)

    assert result["run"]["status"] == "cancelled"
    assert {artifact.kind for artifact in store.artifacts_for(result["run"]["run_id"])} == {"evidence"}
    assert store.events_for(result["run"]["run_id"])[-1].kind == "run.cancelled"


def test_cancellation_during_artifact_index_update_is_terminal(tmp_path: Path) -> None:
    class CancelAtIndexStore(RunStore):
        def __init__(self, root: Path, cancel: threading.Event) -> None:
            super().__init__(root)
            self.cancel = cancel

        def _append_artifact_index(self, artifact) -> None:
            if artifact.kind == "research":
                self.cancel.set()
            super()._append_artifact_index(artifact)

    cancel = threading.Event()
    store = CancelAtIndexStore(tmp_path, cancel)
    workflow = MarketWorkflow(store)
    task = workflow.create_task("Cancel index", ["SPY"], "2026-01-02", "2026-01-06")
    result = workflow.run(task, cancel)

    assert result["run"]["status"] == "cancelled"
    assert store.recovery_for(result["run"]["run_id"])[-1]["terminal_status"] == "cancelled"


def test_cancellation_before_run_finalization_cannot_complete(tmp_path: Path) -> None:
    class CancelAfterRiskEventStore(RunStore):
        def __init__(self, root: Path, cancel: threading.Event) -> None:
            super().__init__(root)
            self.cancel = cancel

        def append_event(self, event) -> None:
            super().append_event(event)
            if event.kind == "risk.checked":
                self.cancel.set()

    cancel = threading.Event()
    store = CancelAfterRiskEventStore(tmp_path, cancel)
    workflow = MarketWorkflow(store)
    task = workflow.create_task("Cancel finalization", ["SPY"], "2026-01-02", "2026-01-06")
    result = workflow.run(task, cancel)

    assert result["run"]["status"] == "cancelled"
    assert store.latest_run(result["run"]["run_id"])["status"] == "cancelled"


@pytest.mark.parametrize("failure_point", ["run", "artifact", "artifact-index"])
def test_transient_storage_failures_are_terminal_and_retryable(tmp_path: Path, failure_point: str) -> None:
    class TransientStore(RunStore):
        def __init__(self, root: Path) -> None:
            super().__init__(root)
            self.failed = False

        def save_run(self, run) -> None:
            if failure_point == "run" and not self.failed and run.status == "running":
                self.failed = True
                raise OSError("run index unavailable")
            super().save_run(run)

        def write_artifact(self, run_id, kind, payload, lineage=()):
            if failure_point == "artifact" and kind == "research" and not self.failed:
                self.failed = True
                raise OSError("artifact storage unavailable")
            return super().write_artifact(run_id, kind, payload, lineage)

        def append_event(self, event) -> None:
            super().append_event(event)

        def _append_artifact_index(self, artifact) -> None:
            if failure_point == "artifact-index" and artifact.kind == "research" and not self.failed:
                self.failed = True
                raise OSError("artifact index unavailable")
            super()._append_artifact_index(artifact)

    store = TransientStore(tmp_path)
    workflow = MarketWorkflow(store)
    task = workflow.create_task("Transient storage", ["SPY"], "2026-01-02", "2026-01-06", idempotency_key="retry-me")
    with pytest.raises(OSError):
        workflow.run(task)

    failed_runs = [json.loads(line) for line in store.runs.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert failed_runs[-1]["status"] == "failed"
    assert store.recovery_for(failed_runs[-1]["run_id"])[-1]["terminal_status"] == "failed"

    retry = workflow.run(task)
    assert retry["run"]["status"] == "completed"


def test_restart_marks_inflight_run_failed_without_resume(tmp_path: Path) -> None:
    store = RunStore(tmp_path)
    workflow = MarketWorkflow(store)
    task = workflow.create_task("Interrupted", ["SPY"], "2026-01-02", "2026-01-06")
    from market_os.contracts import Run

    running = Run("run-abandoned", task.task_id, "running", task.created_at)
    store.save_run(running)
    workflow._event(running, "run.started", {"task": task.__dict__})

    recovered = MarketWorkflow(RunStore(tmp_path)).recover_inflight_runs()

    assert recovered[0]["status"] == "failed"
    assert recovered[0]["error"] == "restart_interrupted:resume_unsupported"
    inspection = MarketWorkflow(RunStore(tmp_path)).inspect_run("run-abandoned")
    assert inspection["recovery"][-1]["operation"] == "process.restart"


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


def test_service_health_and_readiness_endpoints(tmp_path: Path) -> None:
    workflow = MarketWorkflow(RunStore(tmp_path))
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(workflow))
    thread = thread_module.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        for path, expected in (("/healthz", "ok"), ("/readyz", "ready")):
            response = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{server.server_port}{path}", timeout=2).read())
            assert response["status"] == expected
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_service_writes_structured_request_audit_log(tmp_path: Path) -> None:
    workflow = MarketWorkflow(RunStore(tmp_path / "state"))
    log_path = tmp_path / "logs" / "service.jsonl"
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(workflow, service_log_path=log_path))
    thread = thread_module.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        response = urllib.request.urlopen(f"http://127.0.0.1:{server.server_port}/healthz", timeout=2)
        assert response.status == 200
    finally:
        server.shutdown()
        thread.join(timeout=2)

    records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert records[-1]["method"] == "GET"
    assert records[-1]["path"] == "/healthz"
    assert records[-1]["status"] == 200


def test_service_request_id_is_correlated_without_logging_query_values(tmp_path: Path) -> None:
    workflow = MarketWorkflow(RunStore(tmp_path / "state"))
    log_path = tmp_path / "logs" / "service.jsonl"
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(workflow, service_log_path=log_path))
    thread = thread_module.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        response = urllib.request.urlopen(f"http://127.0.0.1:{server.server_port}/healthz", timeout=2)
        request_id = response.headers["X-Request-ID"]
        assert request_id and len(request_id) == 32
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    record = json.loads(log_path.read_text(encoding="utf-8").splitlines()[-1])
    assert record["request_id"] == request_id
    assert record["path"] == "/healthz"
    assert "request_id" in log_path.read_text(encoding="utf-8")


def test_service_audit_log_omits_query_string(tmp_path: Path) -> None:
    workflow = MarketWorkflow(RunStore(tmp_path / "state"))
    log_path = tmp_path / "logs" / "service.jsonl"
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(workflow, service_log_path=log_path))
    thread = thread_module.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        response = urllib.request.urlopen(
            f"http://127.0.0.1:{server.server_port}/v1/btc/history/readiness?cutoff-ms=1704067200000&token=fixture-secret",
            timeout=2,
        )
        assert response.status == 200
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert records[-1]["path"] == "/v1/btc/history/readiness"
    assert "fixture-secret" not in log_path.read_text(encoding="utf-8")


@pytest.mark.parametrize("method", ["GET", "POST"])
@pytest.mark.parametrize("host", ["attacker.example", "evil@localhost", "localhost#attacker", "localhost:99999", "[invalid"])
def test_service_rejects_untrusted_host_header(tmp_path: Path, method: str, host: str) -> None:
    workflow = MarketWorkflow(RunStore(tmp_path))
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(workflow))
    thread = thread_module.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = urllib.request.Request(
            f"http://127.0.0.1:{server.server_port}/healthz",
            headers={"Host": host},
            method=method,
        )
        with pytest.raises(urllib.error.HTTPError) as response:
            urllib.request.urlopen(request, timeout=2)
        assert response.value.code == 403
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_service_rejects_non_loopback_bind(tmp_path: Path) -> None:
    workflow = MarketWorkflow(RunStore(tmp_path))
    with pytest.raises(ValueError, match="loopback-only"):
        serve(workflow, host="0.0.0.0")


def test_service_recovers_before_opening_listener(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class BrokenRecovery:
        def recover_inflight_runs(self) -> None:
            raise RuntimeError("recovery failed")

    opened = []
    monkeypatch.setattr(api, "ThreadingHTTPServer", lambda *args, **kwargs: opened.append((args, kwargs)))

    with pytest.raises(RuntimeError, match="recovery failed"):
        api.serve(BrokenRecovery(), host="127.0.0.1", port=0)

    assert opened == []


def test_service_startup_recovers_abandoned_run(tmp_path: Path) -> None:
    store = RunStore(tmp_path)
    abandoned = Run("run-abandoned-service", "task-abandoned-service", "running", "2026-01-01T00:00:00+00:00")
    store.save_run(abandoned)
    store.append_event(RunEvent("event-abandoned-service", abandoned.run_id, "run.started", "2026-01-01T00:00:00+00:00", {}))
    workflow = MarketWorkflow(RunStore(tmp_path))
    workflow.recover_inflight_runs()
    assert workflow.inspect_run(abandoned.run_id)["run"]["error"] == "restart_interrupted:resume_unsupported"
