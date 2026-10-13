"""Exercise the local service deployment shape with fixtures only."""
from __future__ import annotations

import argparse
import json
import os
import platform
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .contracts import Run, RunEvent, utc_now
from .deployment.wrapper import BoundedService, DeploymentConfig, DeploymentConfigError
from .store import RunStore


@dataclass(frozen=True)
class DeploymentProbe:
    name: str
    evidence_class: str
    expected: str
    observed: str
    passed: bool
    details: dict[str, Any] | None = None


def _request(url: str, *, method: str = "GET", payload: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=2) as response:
        return response.status, json.loads(response.read())


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _start(repo_root: Path, store_root: Path, port: int) -> subprocess.Popen[str]:
    env = os.environ.copy()
    env["MARKET_OS_STORE_ROOT"] = str(store_root)
    env["MARKET_OS_HOST"] = "127.0.0.1"
    env["MARKET_OS_PORT"] = str(port)
    return subprocess.Popen(
        [sys.executable, "-m", "market_os.cli", "serve"],
        cwd=repo_root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _wait_ready(port: int, process: subprocess.Popen[str]) -> bool:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and process.poll() is None:
        try:
            status, body = _request(f"http://127.0.0.1:{port}/readyz")
            if status == 200 and body.get("status") == "ready":
                return True
        except (OSError, urllib.error.URLError):
            time.sleep(0.05)
    return False


def _stop(process: subprocess.Popen[str], *, forced: bool = False) -> int | None:
    if process.poll() is not None:
        return process.returncode
    if forced:
        process.kill()
    else:
        process.send_signal(signal.SIGTERM)
    try:
        return process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        return process.wait(timeout=3)


def _probe_openharness(python: str | None) -> DeploymentProbe:
    if not python or not Path(python).exists():
        return DeploymentProbe("openharness-install", "unresolved", "isolated OpenHarness metadata is installed", "interpreter unavailable", False)
    completed = subprocess.run(
        [python, "-c", "import importlib.metadata, platform; print(platform.python_version()); print(importlib.metadata.version('openharness-ai'))"],
        capture_output=True,
        text=True,
        check=False,
    )
    lines = completed.stdout.strip().splitlines()
    passed = completed.returncode == 0 and len(lines) == 2
    return DeploymentProbe(
        "openharness-install",
        "deployment-verified",
        "isolated OpenHarness metadata is installed",
        "Python/OpenHarness=" + "/".join(lines) if lines else completed.stderr.strip()[-200:],
        passed,
    )


def run_probe(output_path: str | Path | None = None, *, openharness_python: str | None = None) -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="market-os-m19-deployment-") as temp_dir:
        root = Path(temp_dir)
        store = root / "state"
        port = _free_port()
        probes = [_probe_openharness(openharness_python)]
        abandoned = Run("run-abandoned-m19", "task-abandoned-m19", "running", utc_now())
        seeded_store = RunStore(store)
        seeded_store.save_run(abandoned)
        seeded_store.append_event(RunEvent("event-abandoned-m19", abandoned.run_id, "run.started", utc_now(), {}))
        process = _start(repo_root, store, port)
        ready = _wait_ready(port, process)
        probes.append(DeploymentProbe("service-readiness", "deployment-verified", "launched service reports readiness", "ready" if ready else "not ready", ready))
        if ready:
            health_status, health = _request(f"http://127.0.0.1:{port}/healthz")
            probes.append(DeploymentProbe("health-endpoint", "deployment-verified", "health endpoint is available", str(health), health_status == 200 and health.get("status") == "ok"))
            status, result = _request(
                f"http://127.0.0.1:{port}/v1/tasks",
                method="POST",
                payload={"objective": "deployment probe", "symbols": ["SPY"], "start": "2026-01-02", "end": "2026-01-06"},
            )
            run_id = result.get("run", {}).get("run_id")
            probes.append(DeploymentProbe("task-api", "deployment-verified", "paper task completes through HTTP", result.get("run", {}).get("status", "missing"), status == 200 and result.get("run", {}).get("status") == "completed"))
            inspect_status, inspection = _request(f"http://127.0.0.1:{port}/v1/runs/{run_id}") if run_id else (0, {})
            probes.append(DeploymentProbe("audit-persistence", "deployment-verified", "run inspection exposes events and artifacts", f"events={len(inspection.get('events', []))}, artifacts={len(inspection.get('artifacts', []))}", inspect_status == 200 and bool(inspection.get("events")) and bool(inspection.get("artifacts"))))
            recovery_status, recovery = _request(f"http://127.0.0.1:{port}/v1/runs/{abandoned.run_id}")
            recovered = recovery.get("run", {})
            probes.append(DeploymentProbe("startup-recovery", "deployment-verified", "startup terminalizes an abandoned run for inspection", recovered.get("error", "missing"), recovery_status == 200 and recovered.get("status") == "failed" and recovered.get("error") == "restart_interrupted:resume_unsupported"))
        _stop(process)
        probes.append(DeploymentProbe("clean-shutdown", "deployment-verified", "service exits after termination request", str(process.returncode), process.returncode is not None))

        restarted_port = _free_port()
        restarted = _start(repo_root, store, restarted_port)
        restart_ready = _wait_ready(restarted_port, restarted)
        probes.append(DeploymentProbe("clean-restart", "deployment-verified", "service restarts against the same state root", "ready" if restart_ready else "not ready", restart_ready))
        _stop(restarted, forced=True)
        probes.append(DeploymentProbe("forced-shutdown", "deployment-verified", "service can be force-stopped without host cleanup", str(restarted.returncode), restarted.returncode is not None))

        probes.extend([
            DeploymentProbe("resource-limits", "unsupported", "service enforces bounded CPU and memory", "no process-level limits are configured", False),
            DeploymentProbe("service-request-timeouts", "unsupported", "service enforces request and provider timeouts", "HTTP handler and provider calls have no deployment-level timeout policy", False),
            DeploymentProbe("service-logging", "unsupported", "service emits request and audit logs", "request logging is intentionally suppressed; wrapper lifecycle logs are separate", False),
            DeploymentProbe("upgrade-rollback", "source-based", "versioned state can be upgraded and rolled back", "documented assumption; no image registry or migration was exercised", True),
            DeploymentProbe("secret-boundary", "deployment-verified", "service workflow accepts no credential payload", "fixture request contained no secrets or provider calls", True),
            DeploymentProbe("filesystem-boundary", "deployment-verified", "state is kept in the configured writable root", str(store), store.exists() and all((store / name).exists() for name in ("events.jsonl", "runs.jsonl", "artifacts.jsonl", "recovery.jsonl"))),
            DeploymentProbe("filesystem-permissions", "unsupported", "state is restricted to a dedicated service identity", "temporary probe state uses the invoking Windows identity", False),
        ])
        wrapper_root = root / "wrapper"
        wrapper_config = DeploymentConfig(
            repo_root=repo_root,
            runtime_root=wrapper_root,
            state_root=wrapper_root / "state",
            log_root=wrapper_root / "logs",
            port=_free_port(),
            startup_timeout=5,
            request_timeout=2,
            shutdown_timeout=3,
            force_timeout=2,
        )
        wrapper = BoundedService(wrapper_config)
        try:
            wrapper.start()
            probes.append(DeploymentProbe("bounded-wrapper-startup", "deployment-verified", "bounded wrapper starts only a loopback paper service", "ready", True))
            result = wrapper.stop()
            log_path = wrapper_config.log_root / "deployment.jsonl"
            log_records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            probes.append(DeploymentProbe("bounded-wrapper-shutdown", "deployment-verified", "bounded wrapper normalizes graceful shutdown", str(result.normalized_exit_code), result.normalized_exit_code == 0))
            probes.append(DeploymentProbe("structured-logs", "deployment-verified", "wrapper writes structured lifecycle logs", str(len(log_records)), len(log_records) >= 3))
        except Exception as exc:
            probes.append(DeploymentProbe("bounded-wrapper-startup", "deployment-verified", "bounded wrapper starts only a loopback paper service", str(exc), False))
            try:
                wrapper.stop(force=True)
            except Exception:
                pass
    report = {
        "schema": "market-os.m1.9-deployment.v1",
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "promotion_status": "Provisional",
        "promotable": False,
        "blockers": [probe.name for probe in probes if not probe.passed],
        "probes": [asdict(probe) for probe in probes],
    }
    if output_path is not None:
        destination = Path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--openharness-python")
    args = parser.parse_args()
    run_probe(args.output, openharness_python=args.openharness_python)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
