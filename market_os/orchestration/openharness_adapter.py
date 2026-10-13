"""Dependency-light OpenHarness boundary and fixture runtime.

The real OpenHarness package is intentionally optional. The fixture runtime
models its session/tool event shape and delegates domain work to the existing
MarketWorkflow so parity can be tested without provider credentials or extra
dependencies.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import threading
import hashlib
from dataclasses import dataclass
from pathlib import Path
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


@dataclass(frozen=True)
class OpenHarnessRuntimeEvidence:
    """Machine-readable evidence returned by an isolated runtime probe."""

    events: tuple[OpenHarnessEvent, ...] = ()
    checks: tuple[dict[str, str], ...] = ()
    raw: dict[str, Any] | None = None


@dataclass(frozen=True)
class AgentResult:
    """Versioned, runtime-neutral result emitted by one coordinating agent."""

    agent_id: str
    task_id: str
    run_id: str
    sequence: int
    status: str
    payload: dict[str, Any] | None = None
    error: dict[str, str] | None = None
    artifacts: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    api_version: str = "market-os.multi-agent.v1"

    def __post_init__(self) -> None:
        if not self.agent_id.strip() or not self.task_id.strip() or not self.run_id.strip():
            raise ValueError("agent, task, and run identities are required")
        if self.sequence < 0:
            raise ValueError("agent result sequence must be non-negative")
        if self.status not in {"completed", "failed", "timed_out", "cancelled"}:
            raise ValueError("invalid agent result status")
        if self.api_version != "market-os.multi-agent.v1":
            raise ValueError("unsupported multi-agent result version")
        if self.status == "completed" and not isinstance(self.payload, dict):
            raise ValueError("completed agent results require an object payload")
        if self.status != "completed" and (not isinstance(self.error, dict) or not self.error.get("message")):
            raise ValueError("non-completed agent results require an error")

    @classmethod
    def success(cls, agent_id: str, task_id: str, run_id: str, sequence: int, payload: dict[str, Any], *, artifacts: tuple[str, ...] = (), evidence_refs: tuple[str, ...] = ()) -> "AgentResult":
        return cls(agent_id, task_id, run_id, sequence, "completed", dict(payload), None, artifacts, evidence_refs)

    @classmethod
    def failed(cls, agent_id: str, task_id: str, run_id: str, sequence: int, message: str) -> "AgentResult":
        return cls(agent_id, task_id, run_id, sequence, "failed", None, {"code": "agent_failed", "message": message})

    @classmethod
    def timed_out(cls, agent_id: str, task_id: str, run_id: str, sequence: int, message: str = "agent timed out") -> "AgentResult":
        return cls(agent_id, task_id, run_id, sequence, "timed_out", None, {"code": "agent_timeout", "message": message})

    @classmethod
    def cancelled(cls, agent_id: str, task_id: str, run_id: str, sequence: int, message: str = "agent cancelled") -> "AgentResult":
        return cls(agent_id, task_id, run_id, sequence, "cancelled", None, {"code": "agent_cancelled", "message": message})

    @property
    def fingerprint(self) -> str:
        value = {"agent_id": self.agent_id, "task_id": self.task_id, "run_id": self.run_id, "status": self.status, "payload": self.payload, "error": self.error, "artifacts": self.artifacts, "evidence_refs": self.evidence_refs}
        return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class AgentAggregate:
    task_id: str
    run_id: str
    status: str
    results: tuple[AgentResult, ...]
    duplicates: tuple[dict[str, Any], ...] = ()
    conflicts: tuple[dict[str, Any], ...] = ()
    artifacts: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    api_version: str = "market-os.multi-agent.v1"

    def to_dict(self) -> dict[str, Any]:
        return {"api_version": self.api_version, "task_id": self.task_id, "run_id": self.run_id, "status": self.status, "results": [item.__dict__ | {"fingerprint": item.fingerprint} for item in self.results], "duplicates": list(self.duplicates), "conflicts": list(self.conflicts), "artifacts": list(self.artifacts), "evidence_refs": list(self.evidence_refs)}


def aggregate_agent_results(values: list[AgentResult | dict[str, Any]] | tuple[AgentResult | dict[str, Any], ...]) -> AgentAggregate:
    if not values:
        raise ValueError("at least one agent result is required")
    normalized = [AgentResult(**item) if isinstance(item, dict) else item for item in values]
    identities = {(item.task_id, item.run_id) for item in normalized}
    if len(identities) != 1:
        raise ValueError("all agent results must share task and run identity")
    ordered = sorted(normalized, key=lambda item: (item.sequence, item.agent_id))
    accepted: list[AgentResult] = []
    duplicates: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    seen: dict[tuple[str, str, str], AgentResult] = {}
    for item in ordered:
        key = (item.agent_id, item.task_id, item.run_id)
        previous = seen.get(key)
        if previous is not None:
            if previous.fingerprint == item.fingerprint:
                duplicates.append({"agent_id": item.agent_id, "fingerprint": item.fingerprint, "sequence": item.sequence})
                continue
            conflicts.append({"agent_id": item.agent_id, "first_fingerprint": previous.fingerprint, "conflicting_fingerprint": item.fingerprint, "sequence": item.sequence})
            continue
        seen[key] = item
        accepted.append(item)
    status = "failed" if conflicts or not any(item.status == "completed" for item in accepted) else "partial" if any(item.status != "completed" for item in accepted) else "completed"
    artifacts = tuple(dict.fromkeys(ref for item in accepted for ref in item.artifacts))
    evidence_refs = tuple(dict.fromkeys(ref for item in accepted for ref in item.evidence_refs))
    return AgentAggregate(accepted[0].task_id, accepted[0].run_id, status, tuple(accepted), tuple(duplicates), tuple(conflicts), artifacts, evidence_refs)


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
    events_already_persisted = False

    def execute(
        self,
        task: Task,
        workflow: MarketWorkflow,
        cancel_event: threading.Event | None,
    ) -> dict[str, Any]:
        return workflow.run(task, cancel_event)


class IsolatedOpenHarnessRuntime:
    """Run the real child runtime in a separate Python environment.

    The child process owns only the OpenHarness session. The Market OS workflow
    remains the domain reference and writes to the supplied run store.
    """

    events_already_persisted = True

    def __init__(self, python_executable: str | Path | None = None) -> None:
        self.python_executable = str(python_executable or os.environ.get("OPENHARNESS_PYTHON", ""))
        self._runtime_verified = False
        self.evidence = OpenHarnessRuntimeEvidence()

    @property
    def runtime_verified(self) -> bool:
        return self._runtime_verified

    def execute(
        self,
        task: Task,
        workflow: MarketWorkflow,
        cancel_event: threading.Event | None,
    ) -> dict[str, Any]:
        del cancel_event
        if not self.python_executable:
            raise RuntimeError("OPENHARNESS_PYTHON is required for isolated runtime verification")
        executable = Path(self.python_executable)
        if not executable.exists():
            raise RuntimeError(f"OpenHarness runtime interpreter does not exist: {executable}")

        with tempfile.TemporaryDirectory(prefix="market-os-openharness-") as temp_dir:
            temp = Path(temp_dir)
            task_path = temp / "task.json"
            output_path = temp / "probe.json"
            task_path.write_text(json.dumps(task.__dict__, sort_keys=True), encoding="utf-8")
            env = os.environ.copy()
            repo_root = Path(__file__).resolve().parents[2]
            env["PYTHONPATH"] = os.pathsep.join(
                [str(repo_root), *openharness_python_paths()]
            )
            command = [
                str(executable),
                "-m",
                "market_os.orchestration.openharness_probe",
                "--task",
                str(task_path),
                "--store-root",
                str(self_store_root(workflow)),
                "--workspace",
                str(temp / "workspace"),
                "--output",
                str(output_path),
            ]
            completed = subprocess.run(command, env=env, capture_output=True, text=True, check=False)
            if completed.returncode != 0:
                detail = completed.stderr.strip() or completed.stdout.strip() or "unknown runtime error"
                raise RuntimeError(f"OpenHarness runtime probe failed: {detail}")
            if not output_path.exists():
                raise RuntimeError("OpenHarness runtime probe produced no result file")
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.evidence = _runtime_evidence_from_dict(
                payload.get("runtime", {}), run_id=payload["workflow_result"]["run"]["run_id"]
            )
            self._runtime_verified = True
            return payload["workflow_result"]

    def runtime_events_for(self, run_id: str) -> list[OpenHarnessEvent]:
        return [event for event in self.evidence.events if event.session_id == run_id]


def self_store_root(workflow: MarketWorkflow) -> Path:
    return Path(workflow.store.root)


def openharness_python_paths() -> tuple[str, ...]:
    """Return existing OpenHarness source roots without assuming a checkout layout."""
    repo_root = Path(__file__).resolve().parents[2]
    candidates = (
        repo_root / "company-projects" / "OpenHarness",
        repo_root.parent / "company-projects" / "OpenHarness",
        repo_root.parent / "HKUDS" / "OpenHarness",
    )
    paths: list[str] = []
    for candidate in candidates:
        for path in (candidate / "src", candidate):
            if path.exists():
                paths.append(str(path))
    return tuple(dict.fromkeys(paths))


def _runtime_evidence_from_dict(
    payload: dict[str, Any], *, run_id: str
) -> OpenHarnessRuntimeEvidence:
    events = tuple(
        OpenHarnessEvent(
            str(item["event_id"]),
            run_id,
            str(item["name"]),
            str(item["timestamp"]),
            {**dict(item.get("payload", {})), "runtime_session_id": str(item["session_id"])},
        )
        for item in payload.get("events", [])
    )
    checks = tuple(dict(item) for item in payload.get("checks", []))
    return OpenHarnessRuntimeEvidence(events=events, checks=checks, raw=payload)


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
            "recovery": self.store.recovery_for(run_id),
        }

    def probe_recovery(
        self,
        task: Task,
        *,
        root: str | Path,
        openharness_python: str | Path | None = None,
        output_path: str | Path | None = None,
    ) -> dict[str, Any]:
        """Run recovery evidence without importing OpenHarness into contracts."""
        from .recovery import run_recovery_probes

        return run_recovery_probes(
            root,
            task,
            openharness_python=openharness_python,
            output_path=output_path,
        ).to_dict()

    def runtime_events_for(self, run_id: str) -> list[OpenHarnessEvent]:
        runtime_events = self.capture_store.runtime_events_for(run_id)
        if runtime_events:
            return runtime_events
        provider = getattr(self.runtime, "runtime_events_for", None)
        if provider is None:
            return []
        return list(provider(run_id))

    def _persist_runtime_events(self, run_id: str | None) -> None:
        if not run_id:
            return
        if getattr(self.runtime, "events_already_persisted", False):
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
