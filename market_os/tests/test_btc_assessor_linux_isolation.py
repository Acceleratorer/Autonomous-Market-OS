from __future__ import annotations

from pathlib import Path, PurePosixPath
from types import SimpleNamespace

import pytest

from market_os.btc_assessor_linux_isolation import (
    PARENT_NETNS_ENV,
    SCOPE_ENV,
    LinuxAssessorIsolationError,
    _build_scope_command,
    _resource_limits,
    run_assessor_in_isolation,
    verify_linux_isolation,
)


def test_linux_scope_command_contains_native_cgroup_and_namespace_controls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("market_os.btc_assessor_linux_isolation._trusted_tool", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr("market_os.btc_assessor_linux_isolation.sys.executable", "/runtime/bin/python3.11")

    command = _build_scope_command(
        ["btc-paper", "local-assessor", "assess", "--packet", "path with spaces.json"],
        "market-os-btc-assessor-0123456789abcdef.scope",
    )

    assert command[:5] == [
        "/usr/bin/systemd-run", "--user", "--scope", "--quiet",
        "--unit=market-os-btc-assessor-0123456789abcdef.scope",
    ]
    assert "--property=CPUQuota=25%" in command
    assert "--property=MemoryMax=6442450944" in command
    assert "--property=TasksMax=128" in command
    assert "--map-root-user" in command and "--net" in command and "--kill-child=SIGTERM" in command
    assert command[-1] == "path with spaces.json"
    assert "/bin/sh" not in command


def test_linux_cgroup_v2_limits_must_be_finite_and_within_the_caps(tmp_path: Path) -> None:
    scope = "market-os-btc-assessor-0123456789abcdef.scope"
    directory = tmp_path / "user.slice" / scope
    directory.mkdir(parents=True)
    (directory / "cpu.max").write_text("25000 100000\n", encoding="ascii")
    (directory / "memory.max").write_text("6442450944\n", encoding="ascii")
    (directory / "pids.max").write_text("128\n", encoding="ascii")

    limits = _resource_limits(tmp_path, PurePosixPath(f"/user.slice/{scope}"), scope)

    assert limits == {
        "status": "enforced",
        "supervisor": "systemd user scope / cgroup v2",
        "cpu_hard_cap_percent": 25.0,
        "memory_max_bytes": 6442450944,
        "task_max_count": 128,
    }
    (directory / "cpu.max").write_text("26000 100000\n", encoding="ascii")
    with pytest.raises(LinuxAssessorIsolationError, match="CPU quota exceeds"):
        _resource_limits(tmp_path, PurePosixPath(f"/user.slice/{scope}"), scope)


def test_linux_isolation_requires_a_distinct_network_namespace_and_loopback_only(monkeypatch: pytest.MonkeyPatch) -> None:
    scope = "market-os-btc-assessor-0123456789abcdef.scope"
    cgroup = PurePosixPath(f"/user.slice/{scope}")
    monkeypatch.setattr("market_os.btc_assessor_linux_isolation.sys.platform", "linux")
    monkeypatch.setenv(SCOPE_ENV, scope)
    monkeypatch.setenv(PARENT_NETNS_ENV, "11")
    monkeypatch.setattr("market_os.btc_assessor_linux_isolation.os.getpid", lambda: 7)
    monkeypatch.setattr("market_os.btc_assessor_linux_isolation._cgroup_path", lambda _pid: cgroup)
    monkeypatch.setattr(
        "market_os.btc_assessor_linux_isolation._resource_limits",
        lambda *_args: {"status": "enforced"},
    )
    monkeypatch.setattr("market_os.btc_assessor_linux_isolation._net_namespace_inode", lambda _path: 22)
    monkeypatch.setattr("market_os.btc_assessor_linux_isolation.socket.if_nameindex", lambda: [(1, "lo")])
    monkeypatch.setattr("market_os.btc_assessor_linux_isolation._loopback_is_up", lambda: True)
    monkeypatch.setattr(
        "market_os.btc_assessor_linux_isolation._route_devices",
        lambda *_args, **kwargs: {"lo"} if not kwargs["ipv6"] else {"lo"},
    )

    result = verify_linux_isolation(process_pid=42)

    assert result["status"] == "enforced"
    assert result["network_isolation"]["interfaces"] == ["lo"]
    assert result["resource_limits"]["status"] == "enforced"

    monkeypatch.setattr("market_os.btc_assessor_linux_isolation.socket.if_nameindex", lambda: [(1, "lo"), (2, "eth0")])
    result = verify_linux_isolation(process_pid=42)
    assert result["status"] == "unverified"
    assert "only an active loopback" in result["reason"]


def test_local_assessor_cli_is_moved_into_a_scope_once(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("market_os.btc_assessor_linux_isolation.sys.platform", "linux")
    monkeypatch.delenv(SCOPE_ENV, raising=False)
    monkeypatch.setattr("market_os.btc_assessor_linux_isolation.secrets.token_hex", lambda _count: "a" * 16)
    monkeypatch.setattr("market_os.btc_assessor_linux_isolation._trusted_tool", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr("market_os.btc_assessor_linux_isolation._net_namespace_inode", lambda _path: 987)
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("market_os.btc_assessor_linux_isolation.subprocess.run", run)

    exit_code = run_assessor_in_isolation(["btc-paper", "local-assessor", "assess", "--packet", "fixture.json"])

    assert exit_code == 0
    command, kwargs = calls[0]
    assert command[0] == "/usr/bin/systemd-run"
    assert kwargs["shell"] is False
    assert kwargs["env"][SCOPE_ENV] == "market-os-btc-assessor-aaaaaaaaaaaaaaaa.scope"
    assert kwargs["env"][PARENT_NETNS_ENV] == "987"
    assert command[-1] == "fixture.json"

    assert run_assessor_in_isolation(["btc-paper", "local-assessor", "replay", "run-1"]) is None
