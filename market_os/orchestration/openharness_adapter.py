"""Dependency-light OpenHarness boundary and fixture runtime.

The real OpenHarness package is intentionally optional. The fixture runtime
models its session/tool event shape and delegates domain work to the existing
MarketWorkflow so parity can be tested without provider credentials or extra
dependencies.
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from typing import Any, Protocol

from ..contracts import RunEvent, Task
from ..providers import BacktestProvider, EvidenceProvider
from ..store import RunStore
from ..workflow import MarketWorkflow


@dataclass(frozen=True)
class OpenHarnessEvent:
    """Internal event shape; never crosses the Market OS contract boundary."""

    event_id: str
    session_id: str
    name: str
    timestamp: str
    payload: dict[str, Any]


class OpenHarnessRuntime(Protocol):
    runtime_verified: bool

    def execute(
        self,
        task: Task,
        workflow: MarketWorkflow,
        cancel_event: threading.Event | None,
    ) -> dict[str, Any]: ...


class FixtureOpenHarnessRuntime:
    """Test double for an OpenHarness session runner.

    It is source/fixture verified only. The real child runtime is not imported
    or executed in the dependency-light fusion environment.
    """

    runtime_verified = False

    def execute(
        self,
        task: Task,
        workflow: MarketWorkflow,
        cancel_event: threading.Event | None,
    ) -> dict[str, Any]:
        return workflow.run(task, cancel_event)


class _OpenHarnessCaptureStore(RunStore):
    """Persist runs/artifacts normally while capturing events as runtime events."""

    def __init__(self, root: str) -> None:
        super().__init__(root)
        self.market_events: list[RunEvent] = []
        self.runtime_events: list[OpenHarnessEvent] = []

    def append_event(self, event: RunEvent) -> None:
        self.market_events.append(event)
        self.runtime_events.append(_to_openharness_event(event))

    def events_for(self, run_id: str) -> list[RunEvent]:
        return [event for event in self.market_events if event.run_id == run_id]

    def runtime_events_for(self, run_id: str) -> list[OpenHarnessEvent]:
        return [event for event in self.runtime_events if event.session_id == run_id]


_RUNTIME_NAMES = {
    "run.started": "session.started",
    "evidence.retrieved": "tool.completed",
    "research.completed": "tool.completed",
    "backtest.completed": "tool.completed",
    "risk.checked": "tool.completed",
    "run.completed": "session.completed",
    "run.rejected": "session.rejected",
    "run.cancelled": "session.cancelled",
    "run.failed": "session.failed",
}
_TERMINAL_NAMES = {
    "session.started": "run.started",
    "session.completed": "run.completed",
    "session.rejected": "run.rejected",
    "session.cancelled": "run.cancelled",
    "session.failed": "run.failed",
}
_STREAM_EVENT_KINDS = {
    "ToolExecutionStarted": "tool.started",
    "ToolExecutionCompleted": "tool.completed",
    "AssistantTurnComplete": "agent.turn.completed",
    "ErrorEvent": "agent.error",
    "StatusEvent": "runtime.status",
    "CompactProgressEvent": "runtime.progress",
}


def _to_openharness_event(event: RunEvent) -> OpenHarnessEvent:
    payload = dict(event.payload)
    payload["market_os_kind"] = event.kind
    return OpenHarnessEvent(
        event_id=event.event_id,
        session_id=event.run_id,
        name=_RUNTIME_NAMES.get(event.kind, "tool.completed"),
        timestamp=event.timestamp,
        payload=payload,
    )


def map_openharness_event(event: OpenHarnessEvent) -> RunEvent:
    """Translate one internal runtime event into a validated RunEvent."""
    kind = event.payload.get("market_os_kind")
    if not isinstance(kind, str):
        kind = _TERMINAL_NAMES.get(event.name, _STREAM_EVENT_KINDS.get(event.name, "runtime.event"))
    payload = {key: value for key, value in event.payload.items() if key != "market_os_kind"}
    return RunEvent(event.event_id, event.session_id, kind, event.timestamp, payload, actor="openharness")


class OpenHarnessAdapter:
    """Market OS adapter for OpenHarness-shaped lifecycle events."""

    runtime_name = "openharness"

    def __init__(
        self,
        store: RunStore | None = None,
        evidence_provider: EvidenceProvider | None = None,
        backtest_provider: BacktestProvider | None = None,
        *,
        initial_cash: float = 10_000.0,
        max_notional: float = 10_000.0,
        max_symbols: int = 10,
        runtime: OpenHarnessRuntime | None = None,
    ) -> None:
        self.store = store or RunStore()
        self.capture_store = _OpenHarnessCaptureStore(str(self.store.root))
        self.workflow = MarketWorkflow(
            store=self.capture_store,
            evidence_provider=evidence_provider,
            backtest_provider=backtest_provider,
            initial_cash=initial_cash,
            max_notional=max_notional,
            max_symbols=max_symbols,
        )
        self.runtime = runtime or FixtureOpenHarnessRuntime()

    @property
    def runtime_verified(self) -> bool:
        return bool(self.runtime.runtime_verified)

    def create_task(
        self,
        objective: str,
        symbols: list[str],
        start: str,
        end: str,
        *,
        execution_mode: str = "paper",
        idempotency_key: str | None = None,
    ) -> Task:
        return self.workflow.create_task(
            objective,
            symbols,
            start,
            end,
            execution_mode=execution_mode,
            idempotency_key=idempotency_key,
        )

    def run(self, task: Task, cancel_event: threading.Event | None = None) -> dict[str, Any]:
        if task.idempotency_key and self.store.idempotent_result(task.idempotency_key):
            return self.store.idempotent_result(task.idempotency_key) or {}
        try:
            result = self.runtime.execute(task, self.workflow, cancel_event)
        except Exception:
            self._persist_runtime_events(self._run_id_for_task(task))
            raise
        self._persist_runtime_events(result["run"]["run_id"])
        return result

    def inspect_run(self, run_id: str) -> dict[str, Any]:
        events = self.store.events_for(run_id)
        if not events:
            raise KeyError(run_id)
        return {
            "run": self.store.latest_run(run_id),
            "run_id": run_id,
            "events": [event.__dict__ for event in events],
            "artifacts": [artifact.__dict__ for artifact in self.store.artifacts_for(run_id)],
        }

    def runtime_events_for(self, run_id: str) -> list[OpenHarnessEvent]:
        return self.capture_store.runtime_events_for(run_id)

    def _persist_runtime_events(self, run_id: str | None) -> None:
        if not run_id:
            return
        for event in self.capture_store.runtime_events_for(run_id):
            mapped = map_openharness_event(event)
            if not any(existing.event_id == mapped.event_id for existing in self.store.events_for(run_id)):
                self.store.append_event(mapped)

    def _run_id_for_task(self, task: Task) -> str | None:
        latest: str | None = None
        for line in self.store.runs.read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line)
                if item.get("task_id") == task.task_id:
                    latest = item.get("run_id")
        return latest
