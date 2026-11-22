# BTC UTC clock error qualification

**Checked:** 2026-11-22

**Scope:** Official timekeeping specifications and platform documentation only. No workstation clock measurement, time-server request, or runtime configuration change was made.

## Current status

The BTC capture path has no measured UTC error bound. Keep its receipt availability and B3.1 eligibility unknown until the host time service is inspected and a bounded, fresh estimate can be recorded. A scheduler such as n8n controls when a job starts; it does not establish the accuracy of the host clock.

## Local read-only preflight — 2026-11-22

On the Windows workspace host, the local W32Time service query reported
`Stopped`, `Manual`, and service exit code `1077`. `w32tm /query /status`
returned `0x80070426` because the service was not started. No time server was
queried, and no service or clock configuration was changed. There is no active
source state or root-distance evidence to turn into an error estimate; the
capture must continue to record `clock_error_bound_ms: null` and
`packet_eligible: false`.

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
