# BTC UTC clock error qualification

**Checked:** 2026-11-23

**Scope:** Official timekeeping specifications and platform documentation, plus bounded local diagnostics. The later authorized observation temporarily started W32Time and restored its initial stopped/manual state. No manual resynchronization or time-service configuration change was requested by that runner.

## Current status

The BTC capture path has no qualified UTC error bound. Keep its receipt availability unknown and B3.1 eligibility false until a bounded, fresh estimate can be recorded with each receipt. A scheduler such as n8n controls when a job starts; it does not establish the accuracy of the host clock.

## Local read-only preflight — 2026-11-22

On the Windows workspace host, the local W32Time service query reported
`Stopped`, `Manual`, and service exit code `1077`. `w32tm /query /status`
returned `0x80070426` because the service was not started. No time server was
queried, and no service or clock configuration was changed. There is no active
source state or root-distance evidence to turn into an error estimate; the
capture must continue to record `clock_error_bound_ms: null` and
`packet_eligible: false`.

## Follow-up diagnostics — 2026-11-23

The authorized observation window completed as a 10-minute W32Time status
window followed by a 50-minute unprivileged comparison of the local UTC wall
clock with a monotonic clock. W32Time remained stopped/manual. The relative
wall/monotonic samples showed no interval at or above the diagnostic 250 ms
step threshold. The follow-up did not query a time source, market-data service,
or Jev, and did not start or configure W32Time.

A separate, bounded `w32tm /stripchart` diagnostic against the configured peer
recorded offset and round-trip samples, but W32Time could not be started or
resynchronized from the current process and root dispersion was unavailable.
Those samples therefore do not establish a defensible UTC error bound. The
full local samples remain in ignored `.market_os/clock/` files and are not
committed.

**Result:** keep `clock_error_bound_ms: null` and `packet_eligible: false`.
Relative stability against a monotonic clock is not evidence of absolute UTC
accuracy. No BTC data was captured during this observation.

### Authorized elevated retry — completed

The subsequent elevated W32Time observation ran from `2026-11-23T12:53:44Z`
to `2026-11-23T13:43:44Z`: 3,000 seconds, 100 status samples at 30-second
intervals, and no reported runner failure. Its final record confirms restoration
to the original `Stopped` service state and `Manual` start mode.

The first sample was unsynchronized (leap 3, stratum 0). The final sample
reported leap 0, stratum 5, root delay `0.0512878 s`, root dispersion
`7.8498412 s`, and phase offset `0.0797699 s`. No wall/monotonic interval
reached the diagnostic 250 ms threshold. These observations show a transition
to reported synchronization; they do not establish a continuous, capture-time
UTC error qualification. The runner's bound remains `null` and packet
eligibility remains `false`. Its local evidence is
`.market_os/clock/w32time-observation-50m-20261123.json`; raw telemetry remains
ignored and is not uploaded. The runner made no BTC or Jev request.

## Receipt-linked diagnostics

New realtime captures record bounded, read-only W32Time status queries before
and after each Binance adapter call in `polls.jsonl`. Each query retains its
wall/monotonic start and finish, source identity, synchronization fields and
typed failure status. The existing artifact hash covers these records. Source
identity stays in local capture storage, outside chart responses and CLI summaries.
Non-Windows hosts report `unsupported_platform`; this implementation does not
start a service, change configuration, resynchronize, or query an external server.

The local observation script previously omitted the final `Time` in the
documented `Time since Last Good Sync Time` label; all 100 historical samples
therefore lack that parsed field. The new collector uses the full label. Existing
observations are not retroactively repaired or qualified.

These snapshots remain diagnostics: they do not exclude a clock step, suspend,
or synchronization loss between samples. `adapter_returned_at` and its monotonic
marker describe the return from parsing the response, not the transport receipt.
The older per-candle `received_monotonic_ns` is sampled during persistence and
must not be paired with transport `received_at` as a simultaneous clock reading.
No numeric error bound is inferred; packet eligibility remains false.

## What an NTP estimate means

NTPv4 defines synchronization distance as root dispersion plus half the root delay (`epsilon + delta / 2`) and presents it as the maximum-error estimate within the protocol's clock model. chrony reports the estimated maximum system-clock error as root distance plus the remaining system-clock correction. A capture-time estimate should also account for clock drift during holdover and become stale after a configured age. See [RFC 5905](https://www.rfc-editor.org/rfc/rfc5905.html) and the [chrony FAQ](https://chrony-project.org/faq.html).

Treat this as an **operational uncertainty estimate under stated assumptions**, not an unconditional hard guarantee. It depends on truthful time-source statistics, the source's own accuracy, network-delay assumptions, local oscillator behavior, and a host that has not stepped, suspended, or lost synchronization since qualification. NTS can authenticate the server and protect NTP packets against modification and replay; it does not prove that the authenticated server keeps correct time ([RFC 8915](https://www.rfc-editor.org/rfc/rfc8915.html)). If inputs are missing, stale, or inconsistent, report the bound as unknown and fail closed for packet eligibility.

## Read-only diagnostics to collect

Do not change time-service configuration as part of this inspection.

**Windows:**

```powershell
w32tm /query /status /verbose
w32tm /query /peers
w32tm /query /configuration /verbose
```

Record the selected source, last successful synchronization, stratum, leap state, root delay/dispersion when exposed, peer reachability, and provider configuration. Microsoft documents `w32tm` as the preferred W32Time diagnostic tool and specifies separate requirements for supported high-accuracy targets; ordinary status output alone is not a guarantee ([W32Time tools](https://learn.microsoft.com/en-us/windows-server/networking/windows-time-service/windows-time-service-tools-and-settings?tabs=ntpserver), [high-accuracy support boundary](https://learn.microsoft.com/en-us/troubleshoot/windows-server/active-directory/support-boundary-high-accuracy-time)).

**Linux with chrony:**

```sh
chronyc tracking
chronyc sources -v
```

Record the active source, leap/synchronization state, system-time correction, root delay, root dispersion, and source selection. If chrony is not the active time service, identify the actual provider before interpreting the host clock.

These diagnostics establish what the installed service reports; they do not by themselves qualify a capture. A follow-up design must define the accepted uncertainty threshold, freshness window, drift allowance, and invalidation behavior for clock steps, suspend/resume, or synchronization loss, then store that qualification with each local receipt.

The next qualification attempt must obtain fresh synchronization-quality data
from an approved time source, including enough source, sync, root-distance,
and holdover information to calculate a stated operational uncertainty. Do
not repeat a relative-clock observation as a substitute. If the required
fields or assumptions are unavailable, retain the unknown bound and keep
packet eligibility false.
