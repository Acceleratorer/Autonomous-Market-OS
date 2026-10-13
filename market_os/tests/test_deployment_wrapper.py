from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest

from market_os.deployment.wrapper import BoundedService, DeploymentConfig, DeploymentConfigError, config_from_environment


def _config(tmp_path: Path) -> DeploymentConfig:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = int(sock.getsockname()[1])
    repo_root = Path(__file__).resolve().parents[2]
    return DeploymentConfig(repo_root, tmp_path / "runtime", tmp_path / "runtime" / "state", tmp_path / "runtime" / "logs", port=port)


def test_wrapper_rejects_non_loopback_and_outside_paths(tmp_path: Path) -> None:
    config = _config(tmp_path)
    with pytest.raises(DeploymentConfigError):
        DeploymentConfig(config.repo_root, config.runtime_root, tmp_path / "outside", config.log_root).validate()
    with pytest.raises(DeploymentConfigError):
        DeploymentConfig(config.repo_root, config.runtime_root, config.state_root, config.log_root, host="0.0.0.0").validate()
    with pytest.raises(DeploymentConfigError):
        DeploymentConfig(config.repo_root, Path("runtime"), Path("runtime/state"), Path("runtime/logs")).validate()


def test_wrapper_rejects_unbounded_host_limits_and_live_mode(tmp_path: Path) -> None:
    config = _config(tmp_path)
    with pytest.raises(DeploymentConfigError):
        DeploymentConfig(**{**config.__dict__, "memory_limit_bytes": 1024}).validate()
    with pytest.raises(DeploymentConfigError):
        DeploymentConfig(**{**config.__dict__, "paper_only": False}).validate()


def test_wrapper_requires_explicit_runtime_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for name in ("MARKET_OS_RUNTIME_ROOT", "MARKET_OS_STORE_ROOT", "MARKET_OS_LOG_ROOT"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(DeploymentConfigError):
        config_from_environment(repo_root=tmp_path)


def test_wrapper_starts_and_logs_bounded_service(tmp_path: Path) -> None:
    config = _config(tmp_path)
    service = BoundedService(config)
    service.start()
    assert service.wait_ready()
    result = service.stop()
    assert result.normalized_exit_code == 0
    records = [json.loads(line) for line in (config.log_root / "deployment.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [record["event"] for record in records] == ["started", "ready", "stop_requested", "stopped"]
