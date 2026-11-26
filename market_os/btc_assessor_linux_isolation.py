"""Launch and verify the Linux-only BTC assessor execution boundary."""
from __future__ import annotations

import os
from pathlib import Path, PurePosixPath
import secrets
import socket
import struct
import subprocess
import sys
from typing import Any


SCOPE_ENV = "MARKET_OS_BTC_SCOPE_UNIT"
PARENT_NETNS_ENV = "MARKET_OS_BTC_PARENT_NETNS_INODE"
MAX_CPU_PERCENT = 25
MAX_MEMORY_BYTES = 6 * 1024**3
MAX_TASKS = 128
_SIOCGIFFLAGS = 0x8913
_SIOCSIFFLAGS = 0x8914
_IFF_UP = 0x1


class LinuxAssessorIsolationError(RuntimeError):
    """Raised when the Linux assessor boundary cannot be proven."""


def _cgroup_path(pid: int) -> PurePosixPath:
    rows = [line.split("::", 1)[1] for line in Path(f"/proc/{pid}/cgroup").read_text(encoding="ascii").splitlines() if "::" in line]
    if len(rows) != 1 or not rows[0].startswith("/"):
        raise LinuxAssessorIsolationError("unified cgroup v2 membership was not found")
    return PurePosixPath(rows[0])


def _net_namespace_inode(path: str) -> int:
    return os.stat(path).st_ino


def _resource_limits(cgroup_root: Path, cgroup: PurePosixPath, scope_unit: str) -> dict[str, Any]:
    if cgroup.name != scope_unit:
        raise LinuxAssessorIsolationError("assessor is not in its named systemd scope")
    root = cgroup_root.resolve(strict=True)
    directory = (root / Path(*cgroup.parts[1:])).resolve(strict=True)
    if not directory.is_relative_to(root):
        raise LinuxAssessorIsolationError("assessor cgroup escaped the unified hierarchy")
    cpu_fields = (directory / "cpu.max").read_text(encoding="ascii").split()
    if len(cpu_fields) != 2 or cpu_fields[0] == "max":
        raise LinuxAssessorIsolationError("assessor CPU quota is not finite")
    quota, period = map(int, cpu_fields)
    if quota <= 0 or period <= 0 or quota * 100 > MAX_CPU_PERCENT * period:
        raise LinuxAssessorIsolationError("assessor CPU quota exceeds its 25% cap")
    memory_max = int((directory / "memory.max").read_text(encoding="ascii").strip())
    tasks_max = int((directory / "pids.max").read_text(encoding="ascii").strip())
    if not 0 < memory_max <= MAX_MEMORY_BYTES:
        raise LinuxAssessorIsolationError("assessor memory limit is missing or exceeds 6 GiB")
    if not 0 < tasks_max <= MAX_TASKS:
        raise LinuxAssessorIsolationError("assessor task limit is missing or exceeds 128")
    return {
        "status": "enforced",
        "supervisor": "systemd user scope / cgroup v2",
        "cpu_hard_cap_percent": quota * 100 / period,
        "memory_max_bytes": memory_max,
        "task_max_count": tasks_max,
    }


def _route_devices(path: Path, *, ipv6: bool) -> set[str]:
    lines = path.read_text(encoding="ascii").splitlines()
    entries = lines if ipv6 else lines[1:]
    devices = set()
    for line in entries:
        fields = line.split()
        if fields:
            devices.add(fields[-1] if ipv6 else fields[0])
    if devices - {"lo"}:
        raise LinuxAssessorIsolationError("assessor network namespace has a non-loopback route")
    return devices


def _loopback_is_up() -> bool:
    import fcntl

    request = bytearray(struct.pack("256s", b"lo"))
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as control:
        current = fcntl.ioctl(control.fileno(), _SIOCGIFFLAGS, bytes(request))
        return bool(struct.unpack_from("H", current, 16)[0] & _IFF_UP)


def _raise_loopback() -> None:
    import fcntl

    request = bytearray(struct.pack("256s", b"lo"))
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as control:
        current = fcntl.ioctl(control.fileno(), _SIOCGIFFLAGS, bytes(request))
        flags = struct.unpack_from("H", current, 16)[0]
        updated = bytearray(current)
        struct.pack_into("H", updated, 16, flags | _IFF_UP)
        fcntl.ioctl(control.fileno(), _SIOCSIFFLAGS, bytes(updated))


def verify_linux_isolation(process_pid: int | None = None) -> dict[str, Any]:
    """Verify this process and an optional child share enforced boundaries."""
    try:
        if not sys.platform.startswith("linux"):
            raise LinuxAssessorIsolationError("Linux isolation was requested on a non-Linux host")
        scope_unit = os.environ.get(SCOPE_ENV, "")
        parent_netns = int(os.environ.get(PARENT_NETNS_ENV, ""))
        if not scope_unit.startswith("market-os-btc-assessor-") or not scope_unit.endswith(".scope"):
            raise LinuxAssessorIsolationError("assessor systemd scope identity is missing")
        current_cgroup = _cgroup_path(os.getpid())
        process_cgroup = _cgroup_path(process_pid) if process_pid is not None else current_cgroup
        if process_cgroup != current_cgroup:
            raise LinuxAssessorIsolationError("assessor and llama-server are in different cgroups")
        resources = _resource_limits(Path("/sys/fs/cgroup"), current_cgroup, scope_unit)
        resources["scope_unit"] = scope_unit
        resources["cgroup_path"] = str(current_cgroup)
        resources["process_cgroup_path"] = str(process_cgroup)

        current_netns = _net_namespace_inode("/proc/self/ns/net")
        process_netns = _net_namespace_inode(f"/proc/{process_pid}/ns/net") if process_pid is not None else current_netns
        if current_netns == parent_netns or process_netns != current_netns:
            raise LinuxAssessorIsolationError("assessor is not in its isolated network namespace")
        interfaces = sorted(name for _, name in socket.if_nameindex())
        if interfaces != ["lo"] or not _loopback_is_up():
            raise LinuxAssessorIsolationError("assessor network namespace must expose only an active loopback interface")
        ipv4_routes = _route_devices(Path("/proc/net/route"), ipv6=False)
        ipv6_routes = _route_devices(Path("/proc/net/ipv6_route"), ipv6=True)
        return {
            "status": "enforced",
            "resource_limits": resources,
            "network_isolation": {
                "status": "enforced",
                "supervisor": "unshare user and network namespaces",
                "current_namespace_inode": current_netns,
                "parent_namespace_inode": parent_netns,
                "process_namespace_inode": process_netns,
                "interfaces": interfaces,
                "ipv4_route_devices": sorted(ipv4_routes),
                "ipv6_route_devices": sorted(ipv6_routes),
            },
        }
    except (LinuxAssessorIsolationError, OSError, ValueError, IndexError, struct.error) as exc:
        reason = str(exc) or "Linux assessor isolation could not be verified"
        return {
            "status": "unverified",
            "reason": reason,
            "resource_limits": {"status": "unmanaged", "supervisor": None, "reason": reason},
            "network_isolation": {"status": "unverified", "supervisor": None, "reason": reason},
        }


def _trusted_tool(name: str) -> str | None:
    for directory in (Path("/usr/bin"), Path("/bin")):
        path = directory / name
        if path.is_file():
            return str(path)
    return None


def _build_scope_command(argv: list[str], scope_unit: str) -> list[str]:
    systemd_run = _trusted_tool("systemd-run")
    unshare = _trusted_tool("unshare")
    if not systemd_run or not unshare:
        raise LinuxAssessorIsolationError("Linux assessor requires systemd-run and unshare")
    return [
        systemd_run, "--user", "--scope", "--quiet", f"--unit={scope_unit}",
        f"--property=CPUQuota={MAX_CPU_PERCENT}%",
        f"--property=MemoryMax={MAX_MEMORY_BYTES}",
        f"--property=TasksMax={MAX_TASKS}", "--",
        unshare, "--user", "--map-root-user", "--net", "--kill-child=SIGTERM", "--",
        sys.executable, "-m", "market_os.btc_assessor_linux_isolation", "--",
        sys.executable, "-m", "market_os.cli", *argv,
    ]


def run_assessor_in_isolation(argv: list[str]) -> int | None:
    """Re-run local assessor health/assessment inside its Linux boundary."""
    if not sys.platform.startswith("linux") or os.environ.get(SCOPE_ENV):
        return None
    if len(argv) < 3 or argv[:2] != ["btc-paper", "local-assessor"] or argv[2] not in {"health", "assess", "isolation"}:
        return None
    scope_unit = f"market-os-btc-assessor-{secrets.token_hex(8)}.scope"
    environment = os.environ.copy()
    environment[SCOPE_ENV] = scope_unit
    environment[PARENT_NETNS_ENV] = str(_net_namespace_inode("/proc/self/ns/net"))
    package_root = str(Path(__file__).resolve().parents[1])
    environment["PYTHONPATH"] = os.pathsep.join(filter(None, (package_root, environment.get("PYTHONPATH", ""))))
    try:
        return subprocess.run(_build_scope_command(argv, scope_unit), env=environment, shell=False, check=False).returncode
    except (OSError, LinuxAssessorIsolationError) as exc:
        print(f"BTC local assessor requires an enforced Linux isolation scope: {exc}", file=sys.stderr)
        return 2


def main() -> int:
    if not sys.platform.startswith("linux"):
        print("Linux assessor isolation wrapper cannot run on this platform", file=sys.stderr)
        return 2
    if len(sys.argv) < 3 or sys.argv[1] != "--":
        print("Linux assessor isolation wrapper requires a command after --", file=sys.stderr)
        return 2
    command = sys.argv[2:]
    try:
        _raise_loopback()
    except OSError as exc:
        print(f"BTC local assessor could not enable isolated loopback: {exc}", file=sys.stderr)
        return 2
    result = verify_linux_isolation()
    if result["status"] != "enforced":
        print(f"BTC local assessor isolation verification failed: {result['reason']}", file=sys.stderr)
        return 2
    try:
        os.execv(command[0], command)
    except OSError as exc:
        print(f"BTC local assessor command could not start: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
