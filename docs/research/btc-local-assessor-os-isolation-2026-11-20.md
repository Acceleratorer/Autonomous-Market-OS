# BTC Local Assessor OS Isolation Readiness

**Checked:** 2026-11-20
**Status:** Linux rootless boundary is implemented and unit-checked; no Linux target-host verification or host policy change has occurred.
**Scope:** OS-enforced egress and resource limits for the local Qwen assessor.

## Current result

| Launch path | Resource boundary | Network boundary | Readiness |
|---|---|---|---|
| Windows `btc-paper local-assessor` CLI | The pinned `llama-server` child is assigned to a Windows Job Object before it is resumed. The current limits are a 6 GiB process/job commit cap and 25% CPU hard cap. CUDA fit is adaptive, not a VRAM quota. | ActiveStore has no enabled outbound block rule matching the Python executable, the pinned `llama-server.exe`, or `Any`; all profiles default to outbound `Allow`. A read-only ActiveStore verifier and opt-in per-program installer now exist, but the installer has not been run. | Health remains `degraded`; zero egress is unproved. |
| Linux `btc-paper local-assessor health/assess` CLI | The CLI re-executes in a transient `systemd --user` scope with `CPUQuota=25%`, `MemoryMax=6 GiB`, and `TasksMax=128`. It verifies the active cgroup-v2 files for both Python and `llama-server`. | `unshare --user --map-root-user --net` creates a separate network namespace. A small stdlib wrapper raises only `lo`; verification requires a distinct namespace inode, exactly the loopback interface, loopback-only IPv4/IPv6 routes, and matching Python/server cgroup and namespace membership. | Code and mocked boundary tests exist. No Linux host or live scope was available here, so deployment remains unverified and fails closed until target-host health passes. |
| U5.5 system services | `market-os-python.service` and `market-os-next.service` have no explicit CPU or memory quota. | Both unit files configure `IPAddressDeny=any` with loopback allows. The package is disabled and the policy has not been verified on a target host. | Even when installed and supported, the policy covers those service processes, not a separate shell-launched CLI. |

The latest read-only health run is recorded in
[`btc-local-assessor-os-isolation-2026-11-20.json`](../evidence/btc-local-assessor-os-isolation-2026-11-20.json).
The repository evidence records the Windows Job Object smoke and its limits in
[`btc-local-assessor-resource-guard-2026-11-20.json`](../evidence/btc-local-assessor-resource-guard-2026-11-20.json).
On 2026-11-20, CPython 3.11.18 was installed at the locked runtime path and
passed `--verify-only`. The assessor install manifest was regenerated from
already-present, hash-verified model and llama.cpp archives; no artifact was
downloaded. Health then returned HTTP 200 under the 25% CPU and 6 GiB Job
Object limits, but remained `degraded` because matching executable-scoped
ActiveStore firewall rules are absent. No model inference or packet assessment
ran. See
[`btc-assessor-cpython-3.11.18-local-health-2026-11-20.json`](../evidence/btc-assessor-cpython-3.11.18-local-health-2026-11-20.json).
The initial feasibility run used the shared CPython 3.12 executable. Its
project-local venv remains at `.market_os/runtimes/btc-assessor-py312`; it uses
`--system-site-packages` and is not the release runtime. A Windows CPython 3.11.9
embeddable runtime was installed under `.market_os/runtimes/btc-assessor-py311`
for the prior U6.4 baseline. DuckDB 2.0.0 and PyArrow 26.0.1 were installed
from Windows CPython 3.11 wheels, with their wheel hashes recorded. That
interpreter imported CPython, DuckDB, PyArrow, and `market_os.cli`; a local
health smoke started the pinned `llama-server`, received HTTP 200 on loopback,
and observed the existing 25% CPU and 6 GiB Job Object limits. Overall status
remained `degraded` because the ActiveStore egress rules are absent. No model
inference, packet assessment, or firewall policy change occurred. Historical
provenance is in
[`btc-assessor-cpython-3.11-runtime-2026-11-20.json`](../evidence/btc-assessor-cpython-3.11-runtime-2026-11-20.json).

Python.org's latest 3.11 security patch is 3.11.18 and is source-only; the
updated BTC-specific runtime lock builds this source on both Windows and Linux.
Windows uses the official `PCbuild` plus `PC/layout` embeddable-layout flow;
Linux uses the source `configure`/`make` flow. The U6.4/Electron runtime
baseline remains unchanged. The old workstation 3.11.9 tree is preserved as
historical evidence; Visual Studio C++ build tools are absent locally, so the
Windows source build itself remains unverified on this host. Both target-native
CPython 3.11.18 builds passed in [GitHub Actions CI run 44644535859](https://github.com/Acceleratorer/Autonomous-Market-OS/actions/runs/44644535859),
triggered by PR #54. The Windows and Linux jobs uploaded runtime evidence
artifacts with exact runner image, archive SHA-256, runtime-manifest/tree
hashes, and dependency wheels. The CI build does not verify the Linux
isolation boundary on a target host; live cgroup, namespace, loopback, and GPU
verification remain open. A future Windows per-program firewall rule must
target the new dedicated interpreter so it does not block unrelated Python
workloads. See
the [Python 3.11.18 release](https://www.python.org/downloads/release/python-31118/),
CPython's [Windows build instructions](https://github.com/python/cpython/blob/v3.11.18/PCbuild/readme.txt),
and the [3.11.18 embed layout options](https://github.com/python/cpython/blob/v3.11.18/PC/layout/support/options.py).
The Linux assessment path now uses a transient user scope plus a user/network
namespace. The scope is synchronous and applies only to one `health` or
`assess` invocation; replay remains local file inspection. It fails closed if
`systemd-run`, delegated cgroup-v2 CPU/memory/pids controls, rootless user
namespaces, loopback setup, or any membership check is unavailable. In
particular, the Windows workstation has no WSL distribution, so no live Linux
run, actual `llama-server` loopback check, GPU device-access check, or target
cgroup observation has been recorded. The scope does not rely on
`IPAddressDeny`: systemd documents that IP address filtering is available only
for system services, while a user scope can still carry resource controls.
The network namespace provides separate IPv4/IPv6 stacks and routing tables.
See [`systemd-run --scope`](https://freedesktop.org/software/systemd/man/latest/systemd-run.html),
[`systemd.resource-control`](https://www.freedesktop.org/software/systemd/man/latest/systemd.resource-control),
and [`unshare(1)`](https://www.man7.org/linux/man-pages/man1/unshare.1.html).
The implementation and focused test evidence are in
[`btc-assessor-runtime-isolation-implementation-2026-11-20.json`](../evidence/btc-assessor-runtime-isolation-implementation-2026-11-20.json).

The Windows firewall helper at
[`btc_assessor_firewall.ps1`](../../market_os/btc_assessor_firewall.ps1)
supports read-only `Verify` and explicit elevated `Install` modes. Install adds
two executable-scoped outbound block rules for non-loopback IPv4/IPv6 traffic;
the address filters leave `127.0.0.0/8` and `::1` available for the current
HTTP loopback IPC. Install refuses executable paths outside the project-local
`.market_os/runtimes` and `.market_os/local-evidence-runtime` directories and
does not change profile defaults. Health reports Windows isolation as
`enforced` only when the exact Python and pinned server paths have matching
enabled rules in `ActiveStore`, every associated traffic filter is unrestricted
except for the intended remote-address ranges, and all three firewall profiles
are enabled. This is policy evidence, not a non-loopback socket-denial probe, so
overall assessor health remains `degraded` pending target-host verification. No
firewall rule was installed during this work. The PowerShell helper is included
as package data.

The implementation and deployment files are
[`market_os/btc_local_assessor.py`](../../market_os/btc_local_assessor.py),
[`market_os/tests/test_btc_local_assessor.py`](../../market_os/tests/test_btc_local_assessor.py),
[`market-os-python.service`](../../deploy/u5-5/market-os-python.service), and
[`market-os-next.service`](../../deploy/u5-5/market-os-next.service).

## Pinned CLI alternative probe

The installed Windows `llama-cli` build (`b12478-8d1599fca`) was tried with a
synthetic prompt/schema, the local pinned model, offline environment flags,
and the same 6 GiB / 25% Windows Job Object limits as the current runtime. In
single-turn chat mode, the process exited with code 0 but emitted no valid
JSON and logged `Failed to initialize samplers: Unexpected empty grammar
stack after accepting piece: <|im_start|>`. A second constrained invocation
left its requested output file empty. Do not treat this CLI path as a drop-in
replacement based on the help text or exit code alone. Keep the existing
loopback `llama-server` adapter until a pinned build produces and validates a
schema-conforming response through a bounded smoke. No network trace was
collected during this local probe.

## Platform findings

Linux systemd `IPAddressDeny=` and `IPAddressAllow=` filter IPv4/IPv6 ingress
and egress for sockets created by processes in a unit, but systemd documents
these controls for **system services**, not per-user services. The standalone
CLI therefore uses a separate user/network namespace instead of claiming that
a per-user `IPAddressDeny` rule works. systemd `CPUQuota=`, `MemoryMax=`, and
`TasksMax=` map to cgroup controller limits; runtime health reads the actual
v2 `cpu.max`, `memory.max`, and `pids.max` files for the transient scope.
`unshare --user --map-root-user --net` gives the process a separate network
stack and routing tables and grants namespace-local capabilities to configure
loopback without host elevation. These configured limits are not deployment
evidence until a supported Linux host confirms them at runtime. See the
[systemd resource-control documentation](https://www.freedesktop.org/software/systemd/man/latest/systemd.resource-control.html),
[`systemd-run`](https://freedesktop.org/software/systemd/man/latest/systemd-run.html),
and [`unshare(1)`](https://www.man7.org/linux/man-pages/man1/unshare.1.html).

Windows Job Objects support CPU-rate and committed-memory limits for assigned
processes, matching the current runtime's resource controls. They do not
provide the IP allow/deny boundary needed here; Windows Firewall's default is
to allow outbound traffic unless a matching block rule exists. AppContainer is
a possible stronger process boundary: without a network capability, it denies
network access. Launching it requires an AppContainer profile, process
attributes, and appropriate file/registry ACLs. AppContainer loopback is
restricted by default and requires a loopback exemption for local TCP
client/server IPC, so the current `llama-server` HTTP loopback design needs
explicit treatment. See Microsoft's [Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects),
[AppContainer isolation](https://learn.microsoft.com/en-us/windows/win32/secauthz/appcontainer-isolation),
[AppContainer launch steps](https://learn.microsoft.com/en-us/windows/win32/secauthz/implementing-an-appcontainer),
[loopback guidance](https://learn.microsoft.com/en-us/windows/security/operating-system-security/network-security/windows-firewall/troubleshooting-uwp-firewall),
and [Windows Firewall defaults](https://learn.microsoft.com/en-us/windows/security/operating-system-security/network-security/windows-firewall).

## Next verification gate

1. On a supported Linux x64 host, install the pinned Linux runtime and run
   `btc-paper local-assessor health` plus a synthetic-only assessment. Confirm
   the emitted health shows the requested cgroup-v2 limits, Python and server
   share the scope and network namespace, loopback IPC succeeds, and no
   non-loopback interface or route exists. Also confirm the target user's GPU
   device permissions still allow the pinned CUDA runtime; otherwise use the
   locked CPU build or keep Linux health degraded. Do not call a mocked test or
   CI source build live target-host isolation evidence.
2. For Windows, use the opt-in firewall installer only after the pinned,
   project-local CPython 3.11 runtime and the locked llama.cpp target are
   installed. From an elevated PowerShell session at the repository root, set
   the paths and run the installer with a process-scoped execution-policy
   override:

   ```powershell
   $project = (Resolve-Path .).Path
   $python = Join-Path $project ".market_os\runtimes\btc-assessor-py311\python.exe"
   $installRoot = Join-Path $project ".market_os\local-evidence-runtime\windows-x64-cuda-13.5"
   $manifest = Get-Content (Join-Path $installRoot "install-manifest.json") -Raw | ConvertFrom-Json
   $server = Join-Path $installRoot $manifest.runtime.server_relative_path
   & "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
     -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass `
     -File (Join-Path $project "market_os\btc_assessor_firewall.ps1") `
     -Mode Install -ProjectRoot $project -PythonExecutable $python -ServerExecutable $server
   ```

   The Python path must identify the installed, dedicated target interpreter;
   adjust it if the pinned runtime manifest uses a different directory. The
   installer is idempotent: if interrupted after creating one rule, rerunning
   the same `Install` command verifies the existing rule and creates the
   missing rule. Assessment startup fails closed until both rules verify. If
   organizational Group Policy blocks script execution, the process-scoped
   override cannot supersede it and the command reports the policy error.
   After installation, run health against the same Python and server path, then
   perform an actual bounded non-loopback denial probe while confirming
   loopback IPC. Until that target-host verification, overall health remains
   `degraded`. The installer has not been run and no host policy has been
   changed here.
3. Keep the assessor health `degraded` until one of these boundaries is
   installed and its enforcement is observed on the actual launch path.

This is independent of the capture clock gate: on the same Windows host,
`w32tm /query /status` reported an unsynchronized `Local CMOS Clock`, Stratum 0,
and no successful sync time. That snapshot cannot supply the UTC error bound
required by [the prospective capture proposal](../BTC-PROSPECTIVE-CAPTURE-PROPOSAL.md);
it does not change the owner's accepted local-receipt availability rule in
[ADR-0057](../decisions/ADR-0057-btc-strict-recorded-availability.md).
