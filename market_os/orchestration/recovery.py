"""Recovery probes for the OpenHarness adapter boundary.

The dependency-free Market OS workflow remains the reference path.  When an
isolated OpenHarness interpreter is available, the probe runner asks the child
runtime to exercise its own query, tool, session, cancellation, and in-process
teammate paths.  Results keep runtime evidence separate from source or fixture
evidence so a missing capability cannot look verified by accident.
"""
from __future__ import annotations

import json
import os
import platform
import subprocess
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..contracts import Task
from ..store import RunStore
from ..workflow import MarketWorkflow
from .openharness_adapter import OpenHarnessAdapter


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_version(python_executable: str | None) -> str:
    if not python_executable:
        return f"market-os-python:{platform.python_version()}"
    try:
        completed = subprocess.run(
            [python_executable, "--version"], capture_output=True, text=True, check=False
        )
    except OSError:
        return "unavailable"
    return (completed.stdout or completed.stderr).strip() or "unknown"


@dataclass(frozen=True)
class RecoveryProbeResult:
    probe_name: str
    runtime_version: str
    environment_id: str
    started_at: str
    finished_at: str
    expected_behavior: str
    observed_behavior: str
    event_trace: tuple[dict[str, Any], ...] = ()
    artifacts: tuple[dict[str, Any], ...] = ()
    error_details: dict[str, Any] | None = None
    recovery_result: dict[str, Any] | None = None
    passed: bool = False
    runtime_verified: bool = False


@dataclass(frozen=True)
class RecoveryReport:
    runtime_verified: bool
    probes: tuple[RecoveryProbeResult, ...]
    blockers: tuple[str, ...]
    promotion_status: str

    @property
    def promotable(self) -> bool:
        return self.promotion_status == "Accepted" and not self.blockers

    def to_dict(self) -> dict[str, Any]:
        return {
            "runtime_verified": self.runtime_verified,
            "promotable": self.promotable,
            "promotion_status": self.promotion_status,
            "blockers": list(self.blockers),
            "probes": [asdict(probe) for probe in self.probes],
        }

    def write_json(self, path: str | Path) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return destination


_REQUIRED_PROBES = (
    "provider-failure",
    "tool-failure",
    "malformed-tool-result",
    "contract-validation-failure",
    "persistence-failure",
    "market-os-persistence-failure",
    "unexpected-runtime-exception",
    "cancellation-before-task-start",
    "cancellation-during-provider-work",
    "cancellation-during-tool-execution",
    "cancellation-during-artifact-persistence",
    "cancellation-after-completion",
    "repeated-cancellation",
    "cancellation-after-restart",
    "multi-agent-coordination",
    "multi-agent-partial-failure",
    "multi-agent-timeout",
    "multi-agent-duplicate-result",
    "multi-agent-final-aggregation",
    "restart-during-running-task",
    "idempotent-replay",
    "duplicate-request",
    "artifact-lineage",
    "event-trace-completeness",
    "terminal-status-correctness",
    "paper-only-enforcement",
)


def run_recovery_probes(
    root: str | Path,
    task: Task,
    *,
    openharness_python: str | Path | None = None,
    output_path: str | Path | None = None,
) -> RecoveryReport:
    """Run isolated OpenHarness recovery probes and persist a JSON report.

    Without an isolated interpreter, the reference adapter is still exercised
    for baseline sanity, but every result is marked ``runtime_verified=False``.
    """
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    executable = str(openharness_python or os.environ.get("OPENHARNESS_PYTHON", "")) or None
    probes: list[RecoveryProbeResult] = []
    if executable and Path(executable).exists():
        probes.extend(_run_isolated(root, task, executable))
    else:
        probes.extend(_reference_baseline(root, task, _runtime_version(executable)))

    by_name = {probe.probe_name: probe for probe in probes}
    blockers = [
        name
        for name in _REQUIRED_PROBES
        if name not in by_name or not by_name[name].passed or not by_name[name].runtime_verified
    ]
    # Deployment and dependency review are deliberately not inferred from a
    # local probe. They remain a promotion blocker until recorded separately.
    blockers.append("deployment-and-dependency-review")
    report = RecoveryReport(
        runtime_verified=any(probe.runtime_verified for probe in probes),
        probes=tuple(probes),
        blockers=tuple(dict.fromkeys(blockers)),
        promotion_status="Accepted" if not blockers else "Provisional",
    )
    if output_path is not None:
        report.write_json(output_path)
    return report


def _run_isolated(root: Path, task: Task, executable: str) -> list[RecoveryProbeResult]:
    environment_id = f"openharness-recovery-{uuid.uuid4().hex[:12]}"
    task_path = root / "task.json"
    output_path = root / "openharness-recovery.json"
    task_path.write_text(json.dumps(task.__dict__, sort_keys=True), encoding="utf-8")
    repo_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [str(repo_root), str(repo_root / "OpenHarness" / "src"), str(repo_root / "OpenHarness")]
    )
    command = [
        executable,
        "-m",
        "market_os.orchestration.openharness_recovery_probe",
        "--task",
        str(task_path),
        "--store-root",
        str(root / "store"),
        "--workspace",
        str(root / "workspace"),
        "--output",
        str(output_path),
        "--environment-id",
        environment_id,
    ]
    completed = subprocess.run(command, env=env, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        now = _now()
        return [
            RecoveryProbeResult(
                probe_name="isolated-runtime-launch",
                runtime_version=_runtime_version(executable),
                environment_id=environment_id,
                started_at=now,
                finished_at=now,
                expected_behavior="isolated recovery probe exits successfully",
                observed_behavior="child probe failed to launch or complete",
                error_details={
                    "returncode": completed.returncode,
                    "stderr": completed.stderr[-4000:],
                    "stdout": completed.stdout[-4000:],
                },
                passed=False,
                runtime_verified=False,
            )
        ]
    if not output_path.exists():
        return []
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    return [RecoveryProbeResult(**item) for item in payload.get("probes", [])]


def _reference_baseline(root: Path, task: Task, runtime_version: str) -> list[RecoveryProbeResult]:
    """Exercise the reference workflow without mislabeling it as runtime proof."""
    started = _now()
    adapter = OpenHarnessAdapter(store=RunStore(root / "reference"))
    result = adapter.run(task)
    finished = _now()
    run = result["run"]
    return [
        RecoveryProbeResult(
            probe_name="reference-paper-workflow",
            runtime_version=runtime_version,
            environment_id="reference-market-os",
            started_at=started,
            finished_at=finished,
            expected_behavior="reference workflow completes with paper-only artifacts",
            observed_behavior=f"reference workflow ended with {run['status']}",
            event_trace=tuple(result.get("events", ())),
            artifacts=tuple(result.get("artifacts", ())),
            recovery_result={"run_id": run["run_id"], "status": run["status"]},
            passed=run["status"] == "completed" and result["task"]["execution_mode"] == "paper",
            runtime_verified=False,
        )
    ]


def recovery_parity_checks(root: str | Path, task: Task, *, openharness_python: str | Path | None = None) -> dict[str, Any]:
    """Small parity.py-friendly wrapper used by CLI and future promotion gates."""
    return run_recovery_probes(root, task, openharness_python=openharness_python).to_dict()
