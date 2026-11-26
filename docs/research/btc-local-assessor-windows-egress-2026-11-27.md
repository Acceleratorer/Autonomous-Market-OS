# Windows BTC Assessor Egress — Live Contradiction (2026-11-27)

## Result

The Windows egress boundary is **unverified**. The current ActiveStore rule
inspection reports an outbound block rule for the pinned Python executable as
`OK` and `Enforced`, but a direct TCP connect from that executable to
`1.1.1.1:443` completed. It sent no application payload, but a TCP handshake
completed, so this is positive evidence that the current checkout cannot claim
zero egress.

The initial branch revision added a bounded TCP preflight to
`1.1.1.1:443`. It returned `active_egress_probe_connected`, so the health
command returned `unavailable` with typed startup failure
`network_isolation_unverified`. `llama-server` was not launched (zero matching
processes before and after); no model inference, BTC packet assessment, Jev
request, or model-provider request occurred. That runtime probe could itself
send outbound traffic when the boundary is defective, so it has since been
removed from the current branch revision. The current Windows verifier returns
`network_isolation_unverified` if matching ActiveStore policy is the only
available proof, without opening a socket.

## Evidence

- The pinned CPython 3.11.18 executable and current `btc_assessor_firewall.ps1`
  SHA-256 hashes are recorded in the
  [sanitized evidence](../evidence/btc-local-assessor-windows-egress-2026-11-27.json).
- ActiveStore reported the exact Python program path, outbound `Block`,
  `PrimaryStatus=OK`, and `EnforcementStatus={ProfileInactive, Enforced}`.
  The rule's remote address ranges include `1.1.1.1`. Domain, Private, and
  Public profiles were enabled; their default outbound action was `Allow`.
- `MpsSvc` and `BFE` were running. The probe used a numeric IP, one bounded TCP
  connect, and no application payload.
- The initial health preflight reported the policy metadata as enforced while
  separately reporting the behavioral probe and overall network isolation as
  unverified. The resource supervisor remained `not_running`. A focused
  regression test now verifies that matching Windows policy metadata remains
  unverified and that this check opens no socket.
- A same-host private-interface connection also completed, but it remained on
  the machine and is not used as evidence about Internet egress.
- The scoped `netsh wfp show filters` diagnostic was not obtained. The
  non-elevated query returned access denied; the UAC launch was canceled before
  the read-only command started. No firewall policy changed.

## Decision

Do not run the Windows local assessor or send any BTC packet content until the
egress policy is reconciled with the successful connect, or a stronger local
process-isolation boundary is installed and verified. The current preflight
does not probe the public network and therefore does not create network traffic
while checking this condition. It remains `unverified`; it does not establish
zero egress.

The behavioral check covers Python. The `llama-server` executable is still
checked against ActiveStore policy metadata only; behavior for that image has
not been independently probed. The WFP filter table or a stronger sandbox must
resolve the discrepancy before claiming that both executables have zero
egress. Linux remains unavailable on this workstation because WSL is not
installed, and the Linux target host has not been verified.

Keep `clock_error_bound_ms: null` and B3.1 packet eligibility false. This
finding does not change ADR-0058: hosted Jev remains connectivity-only and BTC
packets remain local.
