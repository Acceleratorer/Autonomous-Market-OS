"""Run a no-network OpenHarness runtime probe in an isolated interpreter."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openharness.api.client import ApiMessageCompleteEvent
from openharness.api.usage import UsageSnapshot
from openharness.engine.messages import ConversationMessage, ToolUseBlock
from openharness.tools.base import BaseTool, ToolResult
from openharness.ui.runtime import build_runtime, close_runtime, handle_line, start_runtime
from ohmo.session_storage import OhmoSessionBackend
from pydantic import BaseModel

from ..contracts import Task, task_from_dict
from ..store import RunStore
from ..workflow import MarketWorkflow


class _EmptyInput(BaseModel):
    pass


class _WorkflowTool(BaseTool):
    name = "market_os_workflow"
    description = "Run the deterministic Market OS paper workflow."
    input_model = _EmptyInput

    def __init__(self, workflow: MarketWorkflow, task: Task) -> None:
        self.workflow = workflow
        self.task = task
        self.results: list[dict[str, Any]] = []

    async def execute(self, arguments: _EmptyInput, context) -> ToolResult:
        del arguments, context
        result = self.workflow.run(self.task)
        self.results.append(result)
        return ToolResult(output=f"workflow status: {result['run']['status']}")


class _ScriptedClient:
    def __init__(self) -> None:
        self.calls = 0

    async def stream_message(self, request):
        del request
        self.calls += 1
        if self.calls % 2 == 1:
            message = ConversationMessage(
                role="assistant",
                content=[ToolUseBlock(id=f"toolu_probe_{self.calls}", name="market_os_workflow", input={})],
            )
        else:
            message = ConversationMessage.from_user_text("workflow complete")
            message = ConversationMessage(role="assistant", content=message.content)
        yield ApiMessageCompleteEvent(message=message, usage=UsageSnapshot(input_tokens=1, output_tokens=1))


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    workspace = Path(args.workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    config = workspace / "config"
    data = workspace / "data"
    logs = workspace / "logs"
    ohmo_workspace = workspace / "ohmo"
    os.environ.update(
        {
            "OPENHARNESS_CONFIG_DIR": str(config),
            "OPENHARNESS_DATA_DIR": str(data),
            "OPENHARNESS_LOGS_DIR": str(logs),
            "OHMO_WORKSPACE": str(ohmo_workspace),
        }
    )
    task = task_from_dict(json.loads(Path(args.task).read_text(encoding="utf-8")))
    workflow = MarketWorkflow(RunStore(args.store_root))
    tool = _WorkflowTool(workflow, task)
    skill_root = workspace / "skills"
    skill = skill_root / "runtime-probe" / "SKILL.md"
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text("# Runtime probe\nA runtime verification skill.\n", encoding="utf-8")
    client = _ScriptedClient()
    backend = OhmoSessionBackend(ohmo_workspace)
    bundle = await build_runtime(
        cwd=str(workspace),
        api_client=client,
        max_turns=3,
        permission_mode="full_auto",
        session_backend=backend,
        extra_skill_dirs=[skill_root],
        include_project_memory=False,
    )
    bundle.tool_registry.register(tool)
    events: list[dict[str, Any]] = []

    async def print_system(value: str) -> None:
        del value

    async def render_event(value: object) -> None:
        events.append({"event_id": f"runtime-event-{len(events) + 1}", "session_id": bundle.session_id, "name": type(value).__name__, "timestamp": _timestamp(), "payload": {}})

    async def clear_output() -> None:
        return None

    events.append({"event_id": "runtime-session-started", "session_id": bundle.session_id, "name": "session.started", "timestamp": _timestamp(), "payload": {}})
    await start_runtime(bundle)
    await handle_line(bundle, "run the paper workflow", print_system=print_system, render_event=render_event, clear_output=clear_output)
    first_result = tool.results[-1]
    await handle_line(bundle, "replay the paper workflow", print_system=print_system, render_event=render_event, clear_output=clear_output)
    replay_result = tool.results[-1]
    events.append({"event_id": "runtime-session-completed", "session_id": bundle.session_id, "name": "session.completed", "timestamp": _timestamp(), "payload": {}})
    snapshot = backend.load_by_id(str(workspace), bundle.session_id)
    await close_runtime(bundle)
    checks = [
        {"name": "session-lifecycle", "status": "match", "detail": "build/start/handle/close completed"},
        {"name": "tool-invocation", "status": "match", "detail": f"workflow tool invoked {len(tool.results)} times"},
        {"name": "skill-loading", "status": "match" if "runtime-probe" in bundle.engine.system_prompt else "mismatch", "detail": "extra skill appears in the runtime prompt"},
        {"name": "memory-behavior", "status": "match" if snapshot else "mismatch", "detail": "ohmo session snapshot persisted"},
        {"name": "restart-inspection", "status": "match" if snapshot and snapshot.get("session_id") == bundle.session_id else "mismatch", "detail": "session snapshot reloads by ID"},
        {"name": "idempotent-replay", "status": "match" if first_result == replay_result else "mismatch", "detail": "second runtime turn returned the persisted workflow result"},
        {"name": "multi-agent-coordination", "status": "unsupported", "detail": "agent coordination tool was not exercised by the no-network probe"},
        {"name": "failure-propagation", "status": "unsupported", "detail": "failure scenario requires a separate runtime probe"},
        {"name": "cancellation", "status": "unsupported", "detail": "cancellation scenario requires a separate runtime probe"},
    ]
    return {"workflow_result": first_result, "runtime": {"events": events, "checks": checks, "session_id": bundle.session_id, "api_calls": client.calls}}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--store-root", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = asyncio.run(_run(args))
    Path(args.output).write_text(json.dumps(result, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
