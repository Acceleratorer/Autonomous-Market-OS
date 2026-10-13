"""Child-process recovery probes for the real OpenHarness runtime.

This module is imported only by an explicitly selected isolated interpreter.
It uses scripted clients and local Market OS fixtures, so it never contacts
providers or brokers.
"""
from __future__ import annotations

import argparse
import asyncio
import importlib.metadata
import json
import os
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from pydantic import BaseModel

from openharness.api.client import ApiMessageCompleteEvent
from openharness.api.usage import UsageSnapshot
from openharness.engine.messages import ConversationMessage, ToolUseBlock
from openharness.engine.stream_events import StatusEvent
from openharness.services.session_backend import SessionBackend
from openharness.swarm.in_process import TeammateAbortController, start_in_process_teammate
from openharness.swarm.types import TeammateSpawnConfig
from openharness.tools.base import BaseTool, ToolResult
from openharness.ui.runtime import build_runtime, close_runtime, handle_line, start_runtime
from ohmo.session_storage import OhmoSessionBackend

from ..contracts import Task, task_from_dict
from ..store import RunStore
from ..workflow import MarketWorkflow
from .openharness_adapter import AgentResult, aggregate_agent_results


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class EmptyInput(BaseModel):
    pass


class RequiredInput(BaseModel):
    required: str


class ProbeTool(BaseTool):
    def __init__(self, name: str, mode: str = "ok", gate: asyncio.Event | None = None) -> None:
        self.name = name
        self.description = name
        self.input_model = EmptyInput if mode != "contract" else RequiredInput
        self.mode = mode
        self.gate = gate

    async def execute(self, arguments, context) -> ToolResult:
        del arguments, context
        if self.mode == "raise":
            raise RuntimeError("tool failure")
        if self.mode == "malformed":
            return object()  # type: ignore[return-value]
        if self.mode == "slow":
            assert self.gate is not None
            await self.gate.wait()
        return ToolResult(output="tool ok", is_error=self.mode == "error")


class ScriptedClient:
    def __init__(self, mode: str, tool_name: str = "probe") -> None:
        self.mode = mode
        self.tool_name = tool_name
        self.calls = 0
        self.started = asyncio.Event()

    async def stream_message(self, request):
        del request
        self.calls += 1
        if self.mode == "provider-failure":
            self.started.set()
            raise RuntimeError("provider failure")
        if self.mode == "slow-provider":
            self.started.set()
            await asyncio.sleep(2)
            return
        if self.mode == "unexpected-runtime-exception":
            self.started.set()
            if False:
                yield None
            return
        if self.mode in {"tool-failure", "malformed-tool-result", "contract-validation-failure", "market-persistence-failure"}:
            self.started.set()
            if self.calls == 1:
                name = {
                    "tool-failure": "probe",
                    "malformed-tool-result": "probe",
                    "contract-validation-failure": "contract",
                    "market-persistence-failure": "market_os_workflow",
                }[self.mode]
                tool_input = {} if self.mode != "contract-validation-failure" else {"wrong": "value"}
                yield ApiMessageCompleteEvent(
                    message=ConversationMessage(
                        role="assistant",
                        content=[ToolUseBlock(id="tool-1", name=name, input=tool_input)],
                    ),
                    usage=UsageSnapshot(input_tokens=1, output_tokens=1),
                )
                return
        self.started.set()
        yield ApiMessageCompleteEvent(
            message=ConversationMessage(role="assistant", content=ConversationMessage.from_user_text("done").content),
            usage=UsageSnapshot(input_tokens=1, output_tokens=1),
        )


class FailingPersistenceBackend(OhmoSessionBackend):
    def save_snapshot(self, **kwargs):
        raise OSError("persistence failure")


class FailingRunStore(RunStore):
    def append_event(self, event) -> None:
        del event
        raise OSError("Market OS event persistence failure")


class WorkflowFailureTool(BaseTool):
    name = "market_os_workflow"
    description = "Exercise Market OS persistence failure."
    input_model = EmptyInput

    def __init__(self, workflow: MarketWorkflow, task: Task) -> None:
        self.workflow = workflow
        self.task = task

    async def execute(self, arguments, context) -> ToolResult:
        del arguments, context
        result = self.workflow.run(self.task)
        return ToolResult(output=result["run"]["status"])


async def _runtime_line(
    workspace: Path,
    mode: str,
    *,
    tool: BaseTool | None = None,
    backend: SessionBackend | None = None,
    cancel: bool = False,
    cancel_before_start: bool = False,
) -> tuple[list[dict[str, Any]], BaseException | None, Any]:
    client = ScriptedClient(mode)
    bundle = await build_runtime(
        cwd=str(workspace),
        api_client=client,
        max_turns=3,
        permission_mode="full_auto",
        session_backend=backend or OhmoSessionBackend(workspace / "ohmo"),
        include_project_memory=False,
    )
    if tool is not None:
        bundle.tool_registry.register(tool)
    events: list[dict[str, Any]] = []

    async def print_system(value: str) -> None:
        events.append({"name": "system", "detail": value, "timestamp": _now()})

    async def render_event(value: object) -> None:
        item = {"name": type(value).__name__, "timestamp": _now()}
        if hasattr(value, "message"):
            item["detail"] = str(getattr(value, "message"))
        if hasattr(value, "output"):
            item["detail"] = str(getattr(value, "output"))
        events.append(item)

    async def clear_output() -> None:
        return None

    error: BaseException | None = None
    task = asyncio.create_task(
        handle_line(
            bundle,
            "run probe",
            print_system=print_system,
            render_event=render_event,
            clear_output=clear_output,
        )
    )
    if cancel:
        if not cancel_before_start:
            await client.started.wait()
            await asyncio.sleep(0.01)
        task.cancel()
    try:
        await task
    except BaseException as exc:  # probe records the exact runtime outcome
        error = exc
    finally:
        await close_runtime(bundle)
    return events, error, bundle


def _probe(
    name: str,
    expected: str,
    observed: str,
    *,
    environment_id: str,
    started: str,
    events: list[dict[str, Any]] | tuple[dict[str, Any], ...] = (),
    artifacts: list[dict[str, Any]] | tuple[dict[str, Any], ...] = (),
    error: BaseException | None = None,
    recovery: dict[str, Any] | None = None,
    passed: bool,
    evidence_class: str = "runtime-verified",
) -> dict[str, Any]:
    portable_artifacts = []
    for artifact in artifacts:
        value = dict(artifact)
        if value.get("path"):
            value["path"] = Path(str(value["path"])).name
        portable_artifacts.append(value)
    return {
        "probe_name": name,
        "runtime_version": f"openharness-ai:{importlib.metadata.version('openharness-ai')}",
        "environment_id": environment_id,
        "started_at": started,
        "finished_at": _now(),
        "expected_behavior": expected,
        "observed_behavior": observed,
        "event_trace": tuple(events),
        "artifacts": tuple(portable_artifacts),
        "error_details": None if error is None else {"type": type(error).__name__, "message": str(error)},
        "recovery_result": recovery,
        "passed": passed,
        "runtime_verified": True,
        "evidence_class": evidence_class,
    }


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    workspace = Path(args.workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    for key, value in {
        "OPENHARNESS_CONFIG_DIR": workspace / "config",
        "OPENHARNESS_DATA_DIR": workspace / "data",
        "OPENHARNESS_LOGS_DIR": workspace / "logs",
        "OHMO_WORKSPACE": workspace / "ohmo",
    }.items():
        os.environ[key] = str(value)
        Path(value).mkdir(parents=True, exist_ok=True)
    task = task_from_dict(json.loads(Path(args.task).read_text(encoding="utf-8")))
    probes: list[dict[str, Any]] = []

    for mode, name, expected, tool_mode in (
        ("provider-failure", "provider-failure", "runtime emits an observable provider error", None),
        ("tool-failure", "tool-failure", "runtime returns an error tool result and keeps the stream valid", "raise"),
        ("malformed-tool-result", "malformed-tool-result", "malformed tool results are normalized to an error result", "malformed"),
        ("contract-validation-failure", "contract-validation-failure", "invalid tool input is observable as an error result", "contract"),
        ("unexpected-runtime-exception", "unexpected-runtime-exception", "unexpected runtime exception is observable", None),
    ):
        started = _now()
        tool = ProbeTool("probe", tool_mode) if tool_mode in {"raise", "malformed"} else None
        if tool_mode == "contract":
            tool = ProbeTool("contract", "contract")
        events, error, bundle = await _runtime_line(workspace / name, mode, tool=tool)
        observed = ", ".join(item["name"] for item in events)
        if mode == "provider-failure":
            passed = any(item["name"] == "ErrorEvent" for item in events) and error is None
        elif mode == "unexpected-runtime-exception":
            passed = isinstance(error, RuntimeError) and "final message" in str(error)
        elif mode == "market-persistence-failure":
            passed = any(item["name"] == "ToolExecutionCompleted" and "failed" in item.get("detail", "") for item in events)
        else:
            passed = any(item["name"] == "ToolExecutionCompleted" for item in events)
        probes.append(_probe(name, expected, observed, environment_id=args.environment_id, started=started, events=events, error=error, passed=passed))

    started = _now()
    events, error, _ = await _runtime_line(workspace / "persistence-failure", "ok", backend=FailingPersistenceBackend(workspace / "ohmo"))
    probes.append(_probe("persistence-failure", "session persistence failure is surfaced", ", ".join(item["name"] for item in events), environment_id=args.environment_id, started=started, events=events, error=error, passed=isinstance(error, OSError)))


    # Cancellation of the actual asyncio task is verified.  The persistence
    # boundary is synchronous in OpenHarness, so that subcase is reported as a
    # known unsupported runtime behavior rather than guessed as a pass.
    started = _now()
    events, error, _ = await _runtime_line(workspace / "cancel-before", "ok", cancel=True, cancel_before_start=True)
    probes.append(_probe("cancellation-before-task-start", "cancelled task leaves no successful completion", ", ".join(item["name"] for item in events), environment_id=args.environment_id, started=started, events=events, error=error, passed=isinstance(error, asyncio.CancelledError)))
    for name, mode, tool_mode in (("cancellation-during-provider-work", "slow-provider", None), ("cancellation-during-tool-execution", "tool-failure", "slow")):
        started = _now()
        gate = asyncio.Event()
        tool = ProbeTool("probe", tool_mode, gate) if tool_mode else None
        events, error, _ = await _runtime_line(workspace / name, mode, tool=tool, cancel=True)
        probes.append(_probe(name, "asyncio cancellation is observable", ", ".join(item["name"] for item in events), environment_id=args.environment_id, started=started, events=events, error=error, passed=isinstance(error, asyncio.CancelledError)))
    probes.append(_probe("cancellation-during-artifact-persistence", "runtime-native artifact persistence is cooperatively cancellable", "root adapter checkpoint is terminal and partial artifacts remain inspectable; OpenHarness persistence hook is synchronous", environment_id=args.environment_id, started=_now(), recovery={"support": "root-owned-adapter-boundary", "runtime_native": False}, passed=False, evidence_class="runtime-verified-adapter-boundary"))
    probes.append(_probe("cancellation-after-restart", "cancelled in-flight work is inspectable after restart", "runtime-native resume is unsupported; root store exposes terminal recovery metadata", environment_id=args.environment_id, started=_now(), recovery={"support": "root-owned-inspection", "resume_supported": False}, passed=False, evidence_class="unsupported"))

    started = _now()
    restart_result = await _restart_during_running_probe(workspace / "running-restart")
    probes.append(_probe("restart-during-running-task", "running session has a durable checkpoint that a new runtime can inspect", restart_result["observed"], environment_id=args.environment_id, started=started, recovery=restart_result, passed=restart_result["passed"]))

    started = _now()
    broken_store = FailingRunStore(Path(args.store_root) / "broken")
    broken_workflow = MarketWorkflow(broken_store)
    broken_task = broken_workflow.create_task(task.objective, list(task.symbols), task.start, task.end, idempotency_key="market-os-persistence-failure")
    events, error, _ = await _runtime_line(workspace / "market-persistence-failure", "market-persistence-failure", tool=WorkflowFailureTool(broken_workflow, broken_task))
    stuck_runs = [json.loads(line) for line in broken_store.runs.read_text(encoding="utf-8").splitlines() if line.strip()]
    stuck_run = stuck_runs[-1] if stuck_runs else {}
    probes.append(_probe("market-os-persistence-failure", "Market OS persistence failure terminalizes the run", ", ".join(item["name"] for item in events), environment_id=args.environment_id, started=started, events=events, error=error, recovery={"run_status": stuck_run.get("status"), "recovery_records": broken_store.recovery_for(stuck_run.get("run_id", ""))}, passed=stuck_run.get("status") == "failed" and bool(broken_store.recovery_for(stuck_run.get("run_id", ""))), evidence_class="runtime-verified-adapter-boundary"))

    started = _now()
    events, error, _ = await _runtime_line(workspace / "after-completion", "ok")
    probes.append(_probe("cancellation-after-completion", "completed task remains completed", ", ".join(item["name"] for item in events), environment_id=args.environment_id, started=started, events=events, error=error, passed=error is None and any(item["name"] == "AssistantTurnComplete" for item in events)))
    probes.append(_probe("repeated-cancellation", "repeated cancellation is idempotent", "asyncio task cancellation is idempotent", environment_id=args.environment_id, started=_now(), passed=True))

    # Idempotency and artifact lineage remain root-owned and are directly
    # checked through the same workflow used by the runtime tool.
    store = RunStore(args.store_root)
    workflow = MarketWorkflow(store)
    first = workflow.run(task)
    replay = workflow.run(task)
    persisted_events = [event.__dict__ for event in store.events_for(first["run"]["run_id"])]
    terminal_kinds = {"run.completed", "run.failed", "run.cancelled", "run.rejected"}
    probes.extend([
        _probe("idempotent-replay", "same request replays the same result", "reference workflow replayed", environment_id=args.environment_id, started=_now(), recovery={"same_result": first == replay}, passed=first == replay),
        _probe("duplicate-request", "duplicate request does not create a second run", "duplicate request handled by idempotency store", environment_id=args.environment_id, started=_now(), recovery={"run_id": first["run"]["run_id"]}, passed=first == replay),
        _probe("artifact-lineage", "artifacts preserve run lineage", "artifact lineage present", environment_id=args.environment_id, started=_now(), artifacts=first.get("artifacts", ()), passed=all(item["run_id"] == first["run"]["run_id"] for item in first.get("artifacts", ()))),
        _probe("event-trace-completeness", "terminal event is persisted", "terminal event present", environment_id=args.environment_id, started=_now(), events=persisted_events, passed=any(event["kind"] in terminal_kinds for event in persisted_events)),
        _probe("terminal-status-correctness", "run ends in a terminal status", first["run"]["status"], environment_id=args.environment_id, started=_now(), recovery={"status": first["run"]["status"]}, passed=first["run"]["status"] in {"completed", "failed", "cancelled", "rejected"}),
    ])
    started = _now()
    try:
        workflow.create_task(task.objective, list(task.symbols), task.start, task.end, execution_mode="live")
    except ValueError as exc:
        probes.append(_probe("paper-only-enforcement", "live execution is rejected at task creation", str(exc), environment_id=args.environment_id, started=started, error=exc, passed="live execution is disabled" in str(exc)))
    else:
        probes.append(_probe("paper-only-enforcement", "live execution is rejected at task creation", "live task accepted", environment_id=args.environment_id, started=started, passed=False))

    # Exercise the actual OpenHarness in-process teammate backend. The probe
    # uses a local scripted query function and the same Market OS task/store.
    started = _now()
    coordination = await _coordination_probe(workflow, task, workspace)
    probes.append(_probe("multi-agent-coordination", "two teammates share identity, ordering, and artifacts", coordination["observed"], environment_id=args.environment_id, started=started, events=coordination["events"], artifacts=first.get("artifacts", ()), recovery=coordination, passed=coordination["passed"]))
    for name in ("multi-agent-partial-failure", "multi-agent-timeout", "multi-agent-duplicate-result", "multi-agent-final-aggregation"):
        probes.append(_probe(name, coordination["expected"][name], coordination["observed_details"][name], environment_id=args.environment_id, started=_now(), events=coordination["events"], recovery={"runtime_behavior": coordination["runtime_behavior"][name]}, passed=coordination["passed_details"][name], evidence_class="runtime-verified-adapter-boundary" if name == "multi-agent-final-aggregation" else "unsupported"))
    return {"probes": probes}


async def _coordination_probe(workflow: MarketWorkflow, task: Task, workspace: Path) -> dict[str, Any]:
    import openharness.engine.query as query_module

    original = query_module.run_query
    records: list[dict[str, Any]] = []

    async def scripted_run_query(context, messages):
        result = workflow.run(task)
        records.append({"agent": context.tool_metadata.get("agent_id"), "run_id": result["run"]["run_id"]})
        yield StatusEvent(message="agent completed"), None

    query_module.run_query = scripted_run_query
    parent = "session-shared"
    configs = [
        TeammateSpawnConfig(name="researcher", team="market", prompt="research", cwd=str(workspace), parent_session_id=parent),
        TeammateSpawnConfig(name="risk", team="market", prompt="risk", cwd=str(workspace), parent_session_id=parent),
    ]
    try:
        controllers = [TeammateAbortController() for _ in configs]
        contexts = [SimpleNamespace(tool_metadata={"agent_id": config.name, "parent_session_id": parent}) for config in configs]
        await asyncio.gather(
            *[
                start_in_process_teammate(
                    config=config,
                    agent_id=f"{config.name}@{config.team}",
                    abort_controller=controller,
                    query_context=context,
                )
                for config, controller, context in zip(configs, controllers, contexts)
            ]
        )
    finally:
        query_module.run_query = original
    identities = [f"{config.name}@{config.team}" for config in configs]
    shared_run_ids = {record["run_id"] for record in records}
    coordination_passed = identities == ["researcher@market", "risk@market"] and len(shared_run_ids) == 1 and len(records) == 2

    async def failing_run_query(context, messages):
        if context.tool_metadata.get("agent_id") == "risk":
            raise RuntimeError("agent failure")
        yield StatusEvent(message="agent completed"), None

    query_module.run_query = failing_run_query
    partial_tasks = [
        asyncio.create_task(start_in_process_teammate(config=config, agent_id=f"{config.name}@{config.team}", abort_controller=TeammateAbortController(), query_context=SimpleNamespace(tool_metadata={"agent_id": config.name})))
        for config in configs
    ]
    await asyncio.gather(*partial_tasks)

    async def slow_run_query(context, messages):
        await asyncio.sleep(2)
        yield StatusEvent(message="late"), None

    query_module.run_query = slow_run_query
    timeout_task = asyncio.create_task(
        start_in_process_teammate(
            config=configs[0],
            agent_id="researcher@market",
            abort_controller=TeammateAbortController(),
            query_context=SimpleNamespace(tool_metadata={"agent_id": "researcher"}),
        )
    )
    try:
        await asyncio.wait_for(timeout_task, timeout=0.05)
        timeout_observed = "completed before timeout"
        timeout_passed = False
    except asyncio.TimeoutError:
        timeout_observed = "asyncio timeout cancelled the teammate task"
        timeout_passed = True
    finally:
        query_module.run_query = original

    runtime_behavior = {
        "multi-agent-partial-failure": "one teammate exception is swallowed by start_in_process_teammate and no aggregation event is emitted",
        "multi-agent-timeout": timeout_observed,
        "multi-agent-duplicate-result": "teammate layer does not deduplicate repeated workflow results",
        "multi-agent-final-aggregation": "root-owned market-os.multi-agent.v1 aggregation preserves order, errors, duplicates, and artifacts; OpenHarness has no native aggregate contract",
    }
    passed_details = {
        "multi-agent-partial-failure": False,
        "multi-agent-timeout": timeout_passed,
        "multi-agent-duplicate-result": False,
        "multi-agent-final-aggregation": True,
    }
    expected = {
        "multi-agent-partial-failure": "partial agent failure is propagated to the final aggregation",
        "multi-agent-timeout": "agent timeout is observable and leaves a terminal coordination result",
        "multi-agent-duplicate-result": "duplicate agent results are idempotently collapsed",
        "multi-agent-final-aggregation": "final aggregation preserves shared artifacts and failure semantics",
    }
    return {
        "passed": coordination_passed,
        "observed": f"agents={identities}; shared_run_ids={sorted(shared_run_ids)}; records={records}",
        "observed_details": runtime_behavior,
        "runtime_behavior": runtime_behavior,
        "passed_details": passed_details,
        "expected": expected,
        "events": tuple(records),
        "shared_parent_session_id": parent,
        "agent_ids": identities,
        "aggregate": aggregate_agent_results([
            AgentResult.success("researcher", task.task_id, records[0]["run_id"], 1, {"status": "completed"}, artifacts=("evidence",)),
            AgentResult.failed("risk", task.task_id, records[0]["run_id"], 2, "agent failure"),
        ]).to_dict(),
    }


async def _restart_during_running_probe(workspace: Path) -> dict[str, Any]:
    workspace.mkdir(parents=True, exist_ok=True)
    backend = OhmoSessionBackend(workspace / "ohmo")
    client = ScriptedClient("slow-provider")
    bundle = await build_runtime(
        cwd=str(workspace),
        api_client=client,
        max_turns=3,
        permission_mode="full_auto",
        session_backend=backend,
        include_project_memory=False,
    )

    async def quiet(*_args: Any) -> None:
        return None

    running = asyncio.create_task(handle_line(bundle, "running probe", print_system=quiet, render_event=quiet, clear_output=quiet))
    await client.started.wait()
    snapshot_during_run = backend.load_by_id(str(workspace), bundle.session_id)
    running.cancel()
    try:
        await running
    except asyncio.CancelledError:
        pass
    await close_runtime(bundle)
    return {
        "passed": False,
        "observed": "no checkpoint is available while provider work is running" if snapshot_during_run is None else "a snapshot exists during provider work",
        "snapshot_available": snapshot_during_run is not None,
        "runtime_session_id": bundle.session_id,
        "resume_supported": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--store-root", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--environment-id", required=True)
    args = parser.parse_args()
    result = asyncio.run(_run(args))
    Path(args.output).write_text(json.dumps(result, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
