"""Root-owned orchestration protocol shared by runtimes and adapters."""
from __future__ import annotations

import threading
from typing import Any, Protocol

from ..contracts import Task


class OrchestrationAdapter(Protocol):
    """Minimal surface a runtime adapter must expose to Market OS."""

    runtime_name: str
    runtime_verified: bool

    def create_task(
        self,
        objective: str,
        symbols: list[str],
        start: str,
        end: str,
        *,
        execution_mode: str = "paper",
        idempotency_key: str | None = None,
    ) -> Task: ...

    def run(self, task: Task, cancel_event: threading.Event | None = None) -> dict[str, Any]: ...

    def inspect_run(self, run_id: str) -> dict[str, Any]: ...
