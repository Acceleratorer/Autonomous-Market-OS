# BTC Local Assessor OS Isolation Readiness

**Checked:** 2026-11-20
**Status:** Research note; no host firewall or service policy was changed.
**Scope:** OS-enforced egress and resource limits for the local Qwen assessor.

## Current result

| Launch path | Resource boundary | Network boundary | Readiness |
|---|---|---|---|
| Windows `btc-paper local-assessor` CLI | The pinned `llama-server` child is assigned to a Windows Job Object before it is resumed. The current limits are a 6 GiB process/job commit cap and 25% CPU hard cap. CUDA fit is adaptive, not a VRAM quota. | ActiveStore has no enabled outbound block rule matching the Python executable, the pinned `llama-server.exe`, or `Any`; all profiles default to outbound `Allow`. A read-only ActiveStore verifier and opt-in per-program installer now exist, but the installer has not been run. | Health remains `degraded`; zero egress is unproved. |
| Linux `btc-paper local-assessor` CLI | The runtime starts `llama-server` with `Popen`; Linux health reports resource limits as `unmanaged`. | Loopback bind and offline environment variables do not block other sockets. Health reports egress isolation as `unverified`. | Not resource-bounded or network-isolated by this runtime. |
| U5.5 system services | `market-os-python.service` and `market-os-next.service` have no explicit CPU or memory quota. | Both unit files configure `IPAddressDeny=any` with loopback allows. The package is disabled and the policy has not been verified on a target host. | Even when installed and supported, the policy covers those service processes, not a separate shell-launched CLI. |

The latest read-only health run is recorded in
[`btc-local-assessor-os-isolation-2026-11-20.json`](../evidence/btc-local-assessor-os-isolation-2026-11-20.json).
The repository evidence records the Windows Job Object smoke and its limits in
[`btc-local-assessor-resource-guard-2026-11-20.json`](../evidence/btc-local-assessor-resource-guard-2026-11-20.json).
The current CLI originally used the shared CPython 3.12 executable. A project-
local venv now exists at `.market_os/runtimes/btc-assessor-py312` and resolves
the project, DuckDB, and PyArrow without downloads. A health run through that
interpreter started the pinned server and returned HTTP 200; the Windows Job
Object reported its 6 GiB and 25% CPU limits as enforced, while overall health
remained degraded because egress isolation is unverified. The venv uses
`--system-site-packages` and is only a local feasibility harness, not the
target-native, hash-pinned CPython 3.11 release runtime. A future per-program
rule must target a dedicated application interpreter so enabling it does not
block unrelated Python workloads.
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
and egress for sockets created by processes in a unit. The systemd guidance
states these controls are available for **system services**, not per-user
services, and may have no effect when the kernel or container lacks cgroup BPF
support. `CPUQuota=` is a hard ceiling expressed relative to one CPU, while
`MemoryMax=` controls the unit's cgroup memory limit. Therefore, a user scope
or a static unit-file review alone cannot prove runtime isolation; the actual
assessor must run inside a supported system service and its effective cgroup
controls must be checked. See the [systemd resource-control documentation](https://www.freedesktop.org/software/systemd/man/latest/systemd.resource-control.html).

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

## Next implementation gate

1. For Linux, place the assessor execution path inside a **system** service with
   loopback-only `IPAddress*` policy and explicit cgroup CPU/memory/process
   limits. Verify the active unit properties and effective cgroup files on the
   target host, and confirm a non-loopback probe is denied while loopback IPC
   still works. Keep health degraded if systemd or cgroup BPF support is
   missing.
2. For Windows, use the opt-in firewall installer only after the pinned,
   project-local CPython 3.11 runtime and the locked llama.cpp target are
   installed. From an elevated PowerShell session at the repository root, set
   the paths and run the installer with a process-scoped execution-policy
   override:

   ```powershell
   $project = (Resolve-Path .).Path
   $python = Join-Path $project ".market_os\runtimes\btc-assessor-py311\Scripts\python.exe"
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
