"""Stdlib-only process wrapper for a bounded local Market OS service."""
from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class DeploymentConfigError(ValueError):
    """Configuration cannot satisfy the paper-only local deployment boundary."""


@dataclass(frozen=True)
class DeploymentConfig:
    repo_root: Path
    runtime_root: Path
    state_root: Path
    log_root: Path
    host: str = "127.0.0.1"
    port: int = 8787
    startup_timeout: float = 5.0
    request_timeout: float = 2.0
    shutdown_timeout: float = 3.0
    force_timeout: float = 2.0
    paper_only: bool = True
    cpu_limit_seconds: int | None = None
    memory_limit_bytes: int | None = None

    def validate(self) -> None:
        if not self.repo_root.is_absolute() or not self.runtime_root.is_absolute() or not self.state_root.is_absolute() or not self.log_root.is_absolute():
            raise DeploymentConfigError("repo_root, runtime_root, state_root, and log_root must be absolute paths")
        repo = self.repo_root.resolve()
        runtime = self.runtime_root.resolve()
        state = self.state_root.resolve()
        logs = self.log_root.resolve()
        if not repo.is_dir():
            raise DeploymentConfigError(f"repo_root does not exist: {repo}")
        if self.host not in {"127.0.0.1", "localhost", "::1"}:
            raise DeploymentConfigError("deployment wrapper only permits loopback hosts")
        if not 1 <= self.port <= 65535:
            raise DeploymentConfigError("port must be between 1 and 65535")
        for name, value in (("startup_timeout", self.startup_timeout), ("request_timeout", self.request_timeout), ("shutdown_timeout", self.shutdown_timeout), ("force_timeout", self.force_timeout)):
            if value <= 0:
                raise DeploymentConfigError(f"{name} must be positive")
        if not self.paper_only:
            raise DeploymentConfigError("live execution is disabled in the deployment wrapper")
        if self.cpu_limit_seconds is not None or self.memory_limit_bytes is not None:
            raise DeploymentConfigError("host CPU/memory limits require an external supervisor")
        if not _within(runtime, state) or not _within(runtime, logs):
            raise DeploymentConfigError("state_root and log_root must stay under runtime_root")


@dataclass(frozen=True)
class ShutdownResult:
    requested: str
    forced: bool
    raw_exit_code: int | None
    normalized_exit_code: int


def _within(root: Path, child: Path) -> bool:
    try:
        child.relative_to(root)
    except ValueError:
        return False
    return True


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class BoundedService:
    """Own one paper-only service process and its bounded lifecycle."""

    def __init__(self, config: DeploymentConfig, *, python_executable: str | Path | None = None) -> None:
        config.validate()
        self.config = config
        self.python_executable = str(python_executable or sys.executable)
        self.process: subprocess.Popen[str] | None = None
        self._log_handle: Any = None
        self._log_path = config.log_root.resolve() / "deployment.jsonl"

    def start(self) -> None:
        if self.process is not None and self.process.poll() is None:
            raise RuntimeError("service is already running")
        self.config.state_root.resolve().mkdir(parents=True, exist_ok=True)
        self.config.log_root.resolve().mkdir(parents=True, exist_ok=True)
        self._log_handle = (self.config.log_root.resolve() / "service.log").open("a", encoding="utf-8")
        env = os.environ.copy()
        env.update({
            "MARKET_OS_HOST": self.config.host,
            "MARKET_OS_PORT": str(self.config.port),
            "MARKET_OS_STORE_ROOT": str(self.config.state_root.resolve()),
            "MARKET_OS_PAPER_ONLY": "1",
        })
        command = [self.python_executable, "-m", "market_os.cli", "serve", "--host", self.config.host, "--port", str(self.config.port), "--store-root", str(self.config.state_root.resolve())]
        flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        self.process = subprocess.Popen(command, cwd=self.config.repo_root.resolve(), env=env, stdout=self._log_handle, stderr=subprocess.STDOUT, text=True, creationflags=flags)
        self._record("started", {"pid": self.process.pid, "host": self.config.host, "port": self.config.port})
        if not self.wait_ready():
            self._record("startup_failed", {"returncode": self.process.poll()})
            self.stop()
            raise TimeoutError("service readiness timeout")
        self._record("ready", {})

    def wait_ready(self) -> bool:
        deadline = time.monotonic() + self.config.startup_timeout
        while time.monotonic() < deadline:
            if self.process is None or self.process.poll() is not None:
                return False
            try:
                request = urllib.request.Request(f"http://{self.config.host}:{self.config.port}/readyz")
                with urllib.request.urlopen(request, timeout=self.config.request_timeout) as response:
                    payload = json.loads(response.read())
                if response.status == 200 and payload.get("status") == "ready":
                    return True
            except (OSError, urllib.error.URLError, json.JSONDecodeError):
                time.sleep(0.05)
        return False

    def stop(self, *, force: bool = False) -> ShutdownResult:
        process = self.process
        if process is None:
            return ShutdownResult("stop", force, None, 0)
        forced = force
        if process.poll() is None:
            self._record("stop_requested", {"forced": force})
            if force:
                process.kill()
            else:
                try:
                    process.send_signal(signal.CTRL_BREAK_EVENT if os.name == "nt" else signal.SIGTERM)
                except (OSError, ValueError):
                    forced = True
                    process.kill()
        try:
            raw = process.wait(timeout=self.config.force_timeout if force else self.config.shutdown_timeout)
        except subprocess.TimeoutExpired:
            forced = True
            process.kill()
            raw = process.wait(timeout=self.config.force_timeout)
        result = ShutdownResult("stop", forced, raw, 0 if raw is not None else 1)
        self._record("stopped", {"forced": forced, "raw_exit_code": raw, "normalized_exit_code": result.normalized_exit_code})
        if self._log_handle is not None:
            self._log_handle.close()
            self._log_handle = None
        self.process = None
        return result

    def _record(self, event: str, details: dict[str, Any]) -> None:
        record = {"timestamp": datetime.now(timezone.utc).isoformat(), "event": event, "details": details}
        with self._log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def config_from_environment(*, repo_root: str | Path) -> DeploymentConfig:
    """Build a configuration only when all approved runtime paths are explicit."""
    runtime = os.environ.get("MARKET_OS_RUNTIME_ROOT")
    state = os.environ.get("MARKET_OS_STORE_ROOT")
    logs = os.environ.get("MARKET_OS_LOG_ROOT")
    if not runtime or not state or not logs:
        raise DeploymentConfigError("MARKET_OS_RUNTIME_ROOT, MARKET_OS_STORE_ROOT, and MARKET_OS_LOG_ROOT are required")
    return DeploymentConfig(
        repo_root=Path(repo_root),
        runtime_root=Path(runtime),
        state_root=Path(state),
        log_root=Path(logs),
        host=os.environ.get("MARKET_OS_HOST", "127.0.0.1"),
        port=int(os.environ.get("MARKET_OS_PORT", "8787")),
        startup_timeout=float(os.environ.get("MARKET_OS_STARTUP_TIMEOUT", "5")),
        request_timeout=float(os.environ.get("MARKET_OS_REQUEST_TIMEOUT", "2")),
        shutdown_timeout=float(os.environ.get("MARKET_OS_SHUTDOWN_TIMEOUT", "3")),
        force_timeout=float(os.environ.get("MARKET_OS_FORCE_TIMEOUT", "2")),
        paper_only=os.environ.get("MARKET_OS_PAPER_ONLY", "1") == "1",
    )
