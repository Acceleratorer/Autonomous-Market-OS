# BTC UTC Receipt-Time Source Qualification — 2026-11-27

**Result:** The current Windows status supports a conditional NTP operational-distance estimate of **1.06610145 seconds (1,066.10145 ms)**. This single status snapshot does not establish an end-to-end UTC error bound suitable for B3.1 eligibility. Keep clock_error_bound_ms null and packet eligibility false.

## Local status snapshot

The read-only w32tm /query /status output available for this review reports:

- Source: time.windows.com,0x9; leap indicator 0; stratum 5.
- Root delay: 0.0413353 s.
- Root dispersion: 1.0454338 s.
- Last successful sync: 2026-11-27 01:17:10 local.
- Poll interval: 11, displayed as 2,048 s.
- The unprivileged w32tm /query /configuration command returned Access denied. The 2026-11-27 elevated retry was canceled at the UAC step before the query process started. No time-service configuration or clock changes were made.

Applying RFC 5905’s synchronization-distance formula to the reported fields gives:

root dispersion + (root delay / 2) = 1.0454338 + (0.0413353 / 2) = 1.06610145 s.

This is arithmetic over W32Time’s displayed values. It is a conditional estimate under the NTP model, not an independent measurement of UTC error at every later candle receipt.

## Read-only configuration fallback and peer state

At approximately 01:40 +07:00 on 2026-11-27, the elevated configuration-query launch was canceled at the UAC step before the process ran. Non-elevated registry reads and read-only W32Time commands provided this partial snapshot:

- `HKLM\SYSTEM\CurrentControlSet\Services\W32Time\Parameters`: `Type=NTP`, `NtpServer=time.windows.com,0x9`.
- `HKLM\SYSTEM\CurrentControlSet\Services\W32Time\TimeProviders\NtpClient`: `Enabled=1`, `SpecialPollInterval=16384` seconds. The queried W32Time policy registry paths were absent.
- `sc.exe qc w32time` reported `START_TYPE: DEMAND_START`.
- `w32tm /query /peers` reported the configured peer active, Mode 3, stratum 4, 1,024-second host/peer poll intervals, and 15,237 seconds remaining at that snapshot.
- `w32tm /query /status` still reported stratum 5, root delay 0.0413353 seconds, root dispersion 1.0454338 seconds, and the same source and last-successful-sync time listed above.

These registry and peer reads expose useful settings but do not replace the unavailable effective-configuration output. They do not verify the root source’s UTC accuracy, network asymmetry, or behavior between polls.

## What the primary sources establish

[RFC 5905](https://www.rfc-editor.org/rfc/rfc5905.html) defines root synchronization distance as root dispersion plus half root delay and describes it as the protocol’s maximum-error estimate. It also says dispersion grows with time at the clock-frequency tolerance, typically 15 ppm, and that root distance is a synchronization-quality metric. The formula therefore provides a useful operational uncertainty estimate when the time-source statistics and model assumptions are trustworthy.

Microsoft says W32Time accuracy depends on the accuracy of the root source, network conditions, hardware clock, and CPU/network resources. Its [high-accuracy support boundary](https://learn.microsoft.com/en-us/troubleshoot/windows-server/active-directory/support-boundary-high-accuracy-time) requires a highly accurate, stable root source and documented configuration for supported targets; it specifically warns that network asymmetry harms accuracy. For a supported 1-second target, Microsoft also lists a qualifying Windows version, an NTP hierarchy ending in a highly accurate source, documented configuration, and cumulative one-way latency no greater than 100 ms. The available status output does not establish those conditions. Microsoft also documents time.windows.com as the default source for some standalone or infrequently synchronized systems, while stating that accuracy cannot be guaranteed for intermittent or disconnected systems in [How the Windows Time Service Works](https://learn.microsoft.com/en-us/windows-server/networking/windows-time-service/how-the-windows-time-service-works). These sources do not provide a measured accuracy guarantee for this particular host’s selected source or path.

[NTS](https://www.rfc-editor.org/rfc/rfc8915.html) authenticates server identity and protects synchronization packets against modification and replay. **Inference:** those security guarantees do not attest to the server’s UTC accuracy. RFC 8915 also describes how asymmetric packet delay can still produce an inaccurate estimate. Authentication can strengthen source identity; it cannot replace source-accuracy evidence.

## Why B3.1 remains fail-closed

The snapshot does not establish the complete assumptions needed to interpret 1.06610145 seconds as a receipt-time UTC bound:

- The accuracy and reference-clock chain behind the reported source are unknown.
- Network delay asymmetry and one-way latency to the authoritative source were not measured.
- The effective-configuration query remains unavailable: the unprivileged command was denied and the elevated retry was canceled at the UAC step before execution. Registry reads expose the values above, but do not verify the source’s UTC accuracy or the complete effective configuration.
- A point-in-time status result does not prove continued synchronization or bound clock drift through a later receipt.
- No capture-time policy currently defines maximum bound, freshness, holdover drift, or invalidation after a clock step, suspend/resume, source loss, or resynchronization.

RFC 5905’s estimate is useful as a model-based operational metric, but these missing inputs prevent it from satisfying the project’s strict recorded-availability gate. A leap indicator of zero and stratum 5 report the service’s current synchronization state; they do not close those evidence gaps.

## Decision and next qualification gate

- Continue local code work, synthetic assessments, and read-only capture diagnostics.
- For any future capture without a qualified bound, retain the receipt for diagnostics but leave availability unknown and the packet ineligible.
- Before using receipt time for B3.1, obtain evidence for a known, accurate source and its synchronization path; verify the active configuration; define an accepted uncertainty threshold and maximum freshness; account for holdover growth; and invalidate eligibility on clock step, suspend/resume, synchronization loss, or missing telemetry.
- Keep clock_error_bound_ms null until that qualification is implemented and evidence exists for the capture interval.
- This review queried no time server, did not resynchronize or change Windows settings, and made no Binance, Jev, or model-provider request. A prospective market-data capture still requires its separate date-bound approval under the existing project gate.

This note is a technical evidence assessment, not a claim of an unconditional hard UTC guarantee.
