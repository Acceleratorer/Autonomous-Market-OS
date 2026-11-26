# BTC UTC clock error qualification

**Checked:** 2026-11-26

**Scope:** Official timekeeping specifications and platform documentation, plus bounded local diagnostics. The 2026-11-23 elevated observation temporarily started W32Time and restored its initial stopped/manual state; that runner made no resynchronization or time-service configuration change.

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

### Authorized elevated retry — 2026-11-24

The next elevated observation ran from `2026-11-24T13:31:38Z` to
`2026-11-24T14:21:38Z` (3,000 seconds). It recorded 100 successful status
queries at approximately 30-second intervals; the final result and progress
record each contain 100 samples, with all sample numbers and timestamps
aligned. Every sample remained unsynchronized (leap 3, stratum 0). The final
sample reported a last-good-sync age of `2970.2889382s`, root delay
`0.0000000s`, and root dispersion `0.0000000s` while unsynchronized. The
maximum absolute wall/monotonic interval delta was `2.202 ms`; no interval
reached the diagnostic 250 ms threshold. This relative comparison does not
establish absolute UTC accuracy. No matching W32Time event IDs were recorded
in the observation window. The runner restored the original `Stopped`/`Manual`
state and made no BTC or Jev request.

Read-only local registry inspection found `Type=NTP`, the NtpClient provider
enabled, `NtpServer=time.windows.com,0x9`, `SpecialPollInterval=16384s`,
`MinPollInterval=10`, and `MaxPollInterval=15` (log2-second exponents); there
was no policy override.
A peer query during the run reported `Pending` and `Time Remaining` of
`14852.4045960s`. Microsoft documents `0x1` as `SpecialInterval` and `0x8` as
client mode, so `0x9` enables both; when that flag is set, the configured
`SpecialPollInterval` controls the polling interval. **Inference:** the pending
time is consistent with the configured 16,384-second poll, which is longer
than this 3,000-second observation. The passive run therefore did not test
whether a fresh NTP request could reach or synchronize with the peer. No
resync or registry change was made. See [Microsoft's W32Time settings
reference](https://learn.microsoft.com/en-us/windows-server/networking/windows-time-service/windows-time-service-tools-and-settings?tabs=ntpserver)
and [SpecialPollInterval troubleshooting](https://learn.microsoft.com/en-us/troubleshoot/windows-server/identity/w32time-sync-specialpollinterval-ignored).

The full local result is
`.market_os/clock/w32time-observation-50m-20261124/w32time-observation-50m-20261124-133137-779.json`
(SHA-256 `FE3F2F7CF4BB2E3300DBB2C3A5482819603114DAD4380352A6E2885F71B8543D`);
its per-sample progress record is
`.market_os/clock/w32time-observation-50m-20261124/w32time-observation-50m-20261124-133137-779.progress.json`
(SHA-256 `2DD086650F1A97CF4D91F152EDB3AA6224D574F77CE5CA4CF8D8B5BD2E1D9EBA`)
and is also local and ignored by Git. Keep
`clock_error_bound_ms: null` and `packet_eligible: false`. That passive
observation did not authorize an active resynchronization or polling change;
the separately approved one-shot resync and follow-up are documented below.

### Owner-authorized elevated status retry — 2026-11-25

After the owner explicitly requested a retry, a temporary elevated W32Time
status observation ran for 3,001.074 monotonic seconds. It recorded 100 status
samples at 30-second intervals and 10 local peer snapshots; all status queries
succeeded. Every sample remained unsynchronized (leap 3, stratum 0, source
`Local CMOS Clock`, no last successful sync). Root delay and dispersion were
reported as zero in this unsynchronized state; those values do not establish
zero clock error.

The first peer snapshot reported `time.windows.com,0x9` as Active with
16,383.641 seconds remaining. The last snapshot, at sample 90, reported it
Pending with 13,683.708 seconds remaining. No fresh poll or synchronization
was observed. This is consistent with the previously recorded 16,384-second
special polling interval, but the countdown alone does not establish peer
reachability. Microsoft documents polling flags and interval behavior in its
[W32Time settings reference](https://learn.microsoft.com/en-us/windows-server/networking/windows-time-service/windows-time-service-tools-and-settings?tabs=ntpserver)
and [SpecialPollInterval troubleshooting note](https://learn.microsoft.com/en-us/troubleshoot/windows-server/identity/w32time-sync-specialpollinterval-ignored).
No forced resynchronization or configuration change was made.
The service returned to its original Stopped/Manual state. No BTC market-data,
Jev, or model-provider request was made; no packet capture was run, so normal
W32Time network traffic was not measured.

The sanitized evidence is
[btc-w32time-observation-50m-2026-11-25.json](../evidence/btc-w32time-observation-50m-2026-11-25.json).
The 78,555-byte raw trace remains local and ignored at
`.market_os/clock/w32time-50m-20261125-163340.jsonl` (SHA-256
`C57185AD9071931624C8ED2A403F76224340552503390A7075FA527B0F819796`).
The local runner is retained beside it (SHA-256
`2CDB49600D517F0A46F0BDDD0172CEB4FD59852176C51A3D6533517EEF3423FE`).
Keep `clock_error_bound_ms: null` and `packet_eligible: false`. Do not repeat
another passive 50-minute window as a substitute for synchronization-quality
data. The separately approved active resync and post-resync observation are
recorded below.

### Explicitly approved resync and follow-up — 2026-11-25

After explicit user approval, W32Time was started in its existing `Manual`
start mode and the elevated `w32tm /resync` command completed successfully at
approximately `2026-11-25T11:34:41Z`. No time-service configuration or polling
settings were changed. A status query at `2026-11-25T11:37:29Z` reported source
`time.windows.com,0x9`, leap indicator 0, stratum 5, root delay `0.0471320 s`,
and root dispersion `8.1246595 s`. Root dispersion plus half root delay gives
an NTP synchronization-distance estimate of `8.1482255 s` (`8148.2255 ms`).
This is an operational estimate under the time service's model, not a qualified
capture-time hard guarantee. Source accuracy, network-path assumptions,
holdover drift, freshness, and invalidation behavior remain unqualified.

The post-resync observation completed `3000.022` monotonic seconds from
`2026-11-25T11:42:13.9623036Z`. It recorded 100/100 synchronized status
samples (leap 0, stratum 5), zero query failures, and 10 successful peer
snapshots. Every peer snapshot remained `Pending`; no fresh scheduled poll was
observed. Root delay and dispersion stayed at `0.0471320 s` and `8.1246595 s`,
for an NTP synchronization-distance estimate of `8.1482255 s` (`8148.2255 ms`).
The age of the last successful sync grew from `452.454 s` to `3422.658 s`.

Using the trace's monotonic values rounded to milliseconds, the derived
wall/monotonic offset changed by about `195.3 ms` relative to sample 0; the
largest adjacent-sample change was about `4.7 ms`, below the diagnostic
`250 ms` threshold. This measures relative clock behavior only. It
does not establish absolute UTC accuracy. W32Time remained `Running/Manual` at
the end, with no service or polling configuration change during the window.
No BTC market-data, Jev, or model-provider request was made. The sanitized
[observation evidence](../evidence/btc-w32time-post-resync-observation-2026-11-25.json)
records the result and the limits of the local trace. Keep
`clock_error_bound_ms: null` and `packet_eligible: false` until a defensible
capture-time qualification, freshness, holdover, and invalidation rules are
defined and satisfied.

### Owner-authorized 50-minute retry — 2026-11-25

The later retry recorded 100 status samples and 10 peer snapshots over a
configured 3,000-second window. Its raw status series spans 2,970.009 monotonic
seconds from sample 0 to sample 99; the runner was configured to hold until
3,000 seconds, and the observer process was absent at the next poll, but its
final stdout and exit code were not retained. All 100 status commands succeeded
and reported leap 0 / stratum 5. However, `Last Sync Error: 2` appeared in 73
samples, beginning at sample 27 (810.033 monotonic seconds), while the peer
was Pending in the final four snapshots (samples 60–90). The sampled age of
the last good sync grew from `234.868 s` to `3204.955 s`.

Root delay was `0.0747092 s` and root dispersion `7.9045297 s`, for an estimated
root distance of `7.9418843 s`. The raw UTC trace and monotonic counter differed
by at most `70.990 ms` relative to sample 0, with a maximum adjacent interval
difference of `2.726 ms`; that is a relative-stability diagnostic only. The
peer's final remaining-time estimate was `13448.948 s`, and no fresh poll was
observed. These results show that leap/stratum fields alone can look
synchronized while the status reports stale data. They do not establish a
capture-time UTC error bound. Keep `clock_error_bound_ms: null` and
`packet_eligible: false`. See the
[retry evidence](../evidence/btc-w32time-post-resync-retry-2026-11-25.json);
the raw trace remains local and ignored.

### First owner-requested passive retry — 2026-11-26 02:50 +07:00

The repeat observation completed its configured 3,000-second window with 100
successful status queries and no query failures. W32Time remained `Running` in
`Manual` mode, as it was before the observation; no resync, clock adjustment,
or time-service configuration change was performed. The last successful sync
time stayed at `2026-11-26 02:31:48` local while its reported age increased from
`1118.479 s` to `4088.532 s`. The service reported leap 0 / stratum 5, root
delay `0.0482767 s`, and root dispersion `7.9242334 s`. Root dispersion plus
half root delay gives a `7.94837175 s` root-distance estimate under the NTP
model. No relative wall/monotonic step indication reached `250 ms`.

A separate read-only status snapshot at `2026-11-25T21:09:32Z` still reported
the same last successful sync time and root dispersion. This confirms that the
passive retry did not refresh the source. The root-distance estimate
is not a qualified packet timestamp bound: source accuracy, freshness policy,
holdover drift, and invalidation after clock steps, suspend/resume, or sync
loss remain unverified. No Binance, Jev, or model-provider request was made;
normal W32Time service traffic was not measured. Keep
`clock_error_bound_ms: null` and `packet_eligible: false`. See the
[sanitized retry evidence](../evidence/btc-w32time-observation-50m-retry-2026-11-26.json);
the raw report remains local and ignored.

### Second owner-requested passive retry — 2026-11-26 04:58 +07:00

W32Time was already `Running/Manual`, so the observer did not start or stop the
service and required no elevation. It made no resync, clock adjustment,
polling change, BTC request, Jev request, or model-provider request. The run
completed its configured 3,000-second wall window (`3,000.036` seconds) and
recorded 100 successful status samples over a `2,969.997`-second monotonic
sample span. There were no W32Time event IDs and no query failures.

Leap remained 0 and stratum 5, with root delay `0.0482767 s` and root
dispersion `7.9242334 s`. Their derived root-distance estimate is
`7.94837175 s`, not a qualified capture-time bound. The last successful sync
was still `2026-11-26 02:31:48 +07:00`; its reported age increased from
`8,811.304 s` at the start to `11,781.320 s` at the end, so no fresh sync was
observed. The maximum absolute adjacent wall/monotonic delta was `1.001 ms`,
with no interval at or above the `250 ms` diagnostic threshold. This reflects
relative behavior only and cannot establish absolute UTC accuracy.

Keep `clock_error_bound_ms: null` and `packet_eligible: false`. A later passive
window can observe a new synchronization report, but that does not replace
source-accuracy, holdover-drift, freshness, and invalidation rules. See the
[btc-w32time-observation-50m-retry-2026-11-26-045839.json](../evidence/btc-w32time-observation-50m-retry-2026-11-26-045839.json).
The raw trace remains local and ignored at
`.market_os/clock/w32time-observation-50m-retry-20261126-045839.json` with
SHA-256 `9B23EEA6AE369CBDD0EBC9DB32ABEA2A309189FA1E6F24E8C10FE80BF6FFA787`.

### Third owner-requested passive retry — 2026-11-26 06:29 +07:00

The observer ran from `06:29:24.721` to `07:19:24.784 +07:00`, for
`3,000.063` wall seconds. It recorded 100/100 successful status queries over
a `2,969.964`-second monotonic sample span, with no W32Time event IDs or query
failures. W32Time was already `Running/Manual`; the observer needed no
elevation and did not start or stop the service, issue `w32tm /resync`, change
the clock or polling configuration, or make a market-data, Jev, or model
provider request.

The initial last-successful-sync time was `02:31:48 +07:00`, with a reported
age of `14,255.915 s`. At sample 72, W32Time reported a new last-successful
sync time of `07:04:53 +07:00`, with age `1.564 s`. The last sample, at
`07:18:54.766 +07:00`, reported age `841.599 s`; the window ended at
`07:19:24.784 +07:00`, about 30 seconds later. Leap remained 0 and stratum 5.
The final root delay was `0.0448849 s`, root dispersion `4.0988124 s`, and
derived root-distance estimate `4.12125485 s`. The maximum absolute adjacent
wall/monotonic delta was `2.357 ms`, with no interval at or above the
`250 ms` diagnostic threshold. No resync was requested; ordinary W32Time
service traffic was not measured.

This is evidence that W32Time reported a successful synchronization during
the observation. It does not establish the source's own accuracy, bound
holdover drift after the reported sync, or define freshness and invalidation
rules for suspend, clock steps, or synchronization loss. The root-distance
estimate remains conditional and is not a capture-time error bound. Keep
`clock_error_bound_ms: null` and `packet_eligible: false`. Sanitized evidence
is in [btc-w32time-observation-50m-retry-2026-11-26-062923.json](../evidence/btc-w32time-observation-50m-retry-2026-11-26-062923.json).
The raw report remains local and ignored at
`.market_os/clock/w32time-observation-50m-retry-20261126-062923.json` with
SHA-256 `5E9CB8DC00B1BA43F4CB28E5DC2FBE364C1413A254F853F356FD63CC73CD413F`.

### Read-only status retry — 2026-11-26 about 08:16 +07:00

A later unprivileged status query still reported the last successful sync at
`07:04:53 +07:00`, now aged `4,278.583 s`, with `Last Sync Error: 2` (stale
time data). Leap remained 0 and stratum 5. Root delay was `0.0448849 s` and
root dispersion `4.0988124 s`, for the same conditional root-distance estimate
of `4.12125485 s`. The peer remained `Active` and reported `12,105.070 s`
until its next poll. These fields still do not establish source accuracy,
holdover drift, or a capture-time UTC error bound.

The unprivileged `w32tm /query /configuration /verbose` call returned
`Access is denied`. The owner-authorized read-only elevation attempt was
canceled before the elevated process started. W32Time remained `Running/Manual`;
no service, clock, or polling configuration was changed, and no BTC market-data
request was made. Keep `clock_error_bound_ms: null` and
`packet_eligible: false`; another passive 50-minute window would not provide
the missing source-accuracy or holdover guarantees.

### Owner-requested retry after canceled elevation — 2026-11-26 08:51 +07:00

The passive observer ran from `08:51:31.435` to `09:41:31.467 +07:00`, exactly
3,000 wall seconds. It completed 100/100 successful status queries, with no
timeouts, query failures, or W32Time event IDs. The monotonic sample span was
`2,970.004 s`. W32Time remained `Running/Manual`; the observer did not start or
stop the service, resynchronize, or adjust the system clock.

The last successful sync remained `07:04:53 +07:00`, and its reported age grew
from `6,398.259 s` to `9,368.287 s`. Leap remained 0 and stratum 5. The final
root delay was `0.0448849 s`, root dispersion `4.0988124 s`, and derived root
distance estimate `4.12125485 s`. The maximum absolute adjacent
wall/monotonic delta was `1.224 ms`, with no interval at or above `250 ms`.
The unprivileged configuration query returned `Access is denied`; the second
owner-authorized elevated retry was canceled before the process launched, so
no privileged configuration facts were collected.

These readings show relative clock behavior and the service's reported sync
age only. They do not establish the time source's accuracy, holdover drift,
freshness criteria, or invalidation behavior. No BTC, Jev, or model-provider
request was made. Keep `clock_error_bound_ms: null` and
`packet_eligible: false`; further passive windows cannot replace the missing
qualification inputs. See the [sanitized evidence](../evidence/btc-w32time-observation-50m-retry-2026-11-26-085131.json).

### Owner-requested retry after elevation was canceled again — 2026-11-26 10:17 +07:00

The passive observer ran from `10:17:27.739` to `11:07:27.812 +07:00`, a
`3,000.073 s` wall span. It completed 100/100 successful status queries with
no timeouts, query failures, or W32Time event IDs. The monotonic sample span
was `2,970.017 s`. W32Time remained `Running/Manual`; the observer did not
start or stop the service, resynchronize, or adjust the system clock.

The last successful sync remained `07:04:53 +07:00`, and its reported age grew
from `11,554.568 s` to `14,524.605 s`. Leap remained 0 and stratum 5. Root
delay was `0.0448849 s`, root dispersion `4.0988124 s`, and derived root
distance estimate `4.12125485 s`. The maximum absolute adjacent
wall/monotonic delta was `1.224 ms`, with no interval at or above `250 ms`.
The unprivileged configuration query returned `Access is denied`; Windows
returned `operation was canceled by the user` before the elevated process
launched, so no privileged configuration facts were collected.

These readings remain relative diagnostics and do not establish source
accuracy, holdover drift, freshness criteria, or invalidation behavior. No BTC,
Jev, model-provider, or explicit time-source request was made. Keep
`clock_error_bound_ms: null` and `packet_eligible: false`; another passive
window cannot replace the missing qualification inputs. See the
[sanitized evidence](../evidence/btc-w32time-observation-50m-retry-2026-11-26-101323.json).

### Owner-authorized retry after accepted elevation — 2026-11-26 14:36 +07:00

The passive observer ran from `14:36:11.368` to `15:26:11.393 +07:00`, a
`3,000.025 s` wall span and `2,970.007 s` monotonic sample span. It completed
100/100 successful status queries, with no timeouts, query failures, or
W32Time event IDs. W32Time remained `Running/Manual`; the observer did not
start or stop the service, resynchronize, adjust the clock, or change the
time-service configuration.

The owner accepted the UAC prompt for the elevated read-only
`w32tm /query /configuration /verbose` command. It completed with exit code 0;
peer identity and configuration values are omitted from committed evidence.
The last successful sync remained `11:37:57 +07:00`, and its reported age grew
from `10,694.002 s` to `13,664.034 s`. Leap remained 0 and stratum 5. Root
delay was `0.0479012 s`, root dispersion `7.8723382 s`, and derived root
distance estimate `7.8962888 s`. The maximum absolute adjacent
wall/monotonic delta was `2.005 ms`, with no interval at or above the `250 ms`
diagnostic threshold. No fresh synchronization was observed.

This confirms only the service's reported status and relative wall/monotonic
behavior. The conditional root-distance estimate is not a capture-time UTC
error bound; source accuracy, holdover drift, freshness criteria, and
invalidation behavior remain unqualified. No BTC, Jev, model-provider, or
explicit time-source request was made. Ordinary W32Time service traffic was
not measured. Keep `clock_error_bound_ms: null` and `packet_eligible: false`,
and do not repeat passive windows as a substitute for time-source
qualification. Sanitized evidence is in
[btc-w32time-observation-50m-retry-2026-11-26-143611.json](../evidence/btc-w32time-observation-50m-retry-2026-11-26-143611.json).
The raw report remains local and ignored at
`.market_os/clock/w32time-passive-observation-20261126-143540.json` (SHA-256
`D192287D46194439214A9FCDD07D424243DE1CAE7E91D11D97B28088D067C8B2`).

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
The transport now samples a monotonic counter on both sides of the millisecond
UTC receipt timestamp after reading the response body. It stores the midpoint as
`received_monotonic_ns` and the half-span plus one millisecond of timestamp
quantization as `received_pair_uncertainty_ns`. Realtime capture copies these to
`response_received_monotonic_ns` and
`response_received_pair_uncertainty_ns` in both poll and candle records. Replay
checks the receipt marker falls between request start and adapter return and
validates the paired values; older captures without these fields remain valid.
This uncertainty only describes the wall/monotonic sampling pair. The older
per-candle `received_monotonic_ns` is still sampled during persistence and must
not be paired with transport `received_at`. No absolute UTC error bound is
inferred; `clock_error_bound_ms` remains null and packet eligibility remains
false.

On 2026-11-26 the owner requested retry of the elevated read-only
`w32tm /query /configuration`; it returned exit code 0. The query did not
resynchronize W32Time, alter service or clock configuration, or contact market
or Jev APIs. Configuration output is not committed. This local query does not
change the clock qualification decision or replace fresh synchronization
quality and holdover evidence from an approved time source.

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
