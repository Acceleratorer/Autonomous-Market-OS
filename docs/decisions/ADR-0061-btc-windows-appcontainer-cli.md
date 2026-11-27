# ADR-0061: Windows AppContainer CLI for Local BTC Evidence Assessment

- **Status:** Accepted
- **Date:** 2026-11-27
- **Scope:** Windows local Qwen runtime for BTC evidence assessment

## Context

The Windows loopback `llama-server` path depended on firewall metadata that
did not prove runtime egress denial: a prior direct TCP handshake completed
despite matching ActiveStore block-rule metadata. AppContainer requires
explicit process attributes and has restricted network access unless network
capabilities are granted. The existing Linux namespace path is separate and
remains unchanged.

## Decision

1. On Windows x64, run the pinned `llama-cli` once per completion in a Windows
   AppContainer with no capabilities. Do not start `llama-server`, open a
   loopback port, or rely on firewall rule metadata for this path.
2. Stage only lock-verified runtime files and the lock-verified Qwen model in
   the AppContainer profile data directory. Reject unexpected package files;
   cap total staging at 3 GiB and keep the staged files local until explicit
   deletion.
3. Apply the existing 25% CPU and 6 GiB process/job commit limits before the
   suspended inference process resumes. Use CPU execution, a 128 KiB prompt
   cap, a 1 MiB combined stdout/stderr pipe cap, and the existing bounded
   completion timeout.
4. Verify `TokenIsAppContainer` and zero token capabilities for each process.
   Report that token evidence accurately; do not claim a packet-capture or
   external-denial probe that was not performed.
5. Preserve the existing `CompletionRuntime` contract and Market OS response
   validation. Qwen remains a distinct, uncalibrated evidence assessor, never
   Jev; Market OS remains responsible for math, probabilities, calibration,
   stability, risk, and paper decisions. Hosted Jev remains connectivity-only
   under ADR-0058.

## Consequences

- The first Windows startup copies about 2.55 GB of pinned model/runtime files
  into the local AppContainer profile and retains them for later use. Existing
  or modified package contents that do not match the lock fail closed.
- Per-completion process startup is slower than a resident loopback server,
  and the runtime revalidates staged file hashes before each completion.
- A 2026-11-27 synthetic smoke returned the expected JSON with a 6,516 ms
  `llama-cli` process latency (excluding first-use staging and artifact hash
  revalidation), healthy status, zero token capabilities, and the requested
  Job Object caps.
  No BTC packet, market data, Jev API, model-provider request, outbound probe,
  or packet capture was used. This does not establish Qwen calibration or
  B3.1 eligibility.
- Windows AppContainer behavior is verified on this workstation only. Linux
  target-host isolation and GPU resource ceilings remain unverified. Clock
  qualification remains an independent gate.

## References

- [ADR-0058: Jev connectivity-only and local BTC packet assessment](ADR-0058-btc-jev-connectivity-only-local-assessor.md)
- [Windows local assessor isolation notes](../research/btc-local-assessor-os-isolation-2026-11-20.md)
- [Sanitized Windows AppContainer smoke evidence](../evidence/btc-local-assessor-windows-appcontainer-smoke-2026-11-27.json)
- [Microsoft: Launch an AppContainer](https://learn.microsoft.com/en-us/windows/win32/secauthz/implementing-an-appcontainer)
- [Microsoft: UpdateProcThreadAttribute](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-updateprocthreadattribute)
- [Microsoft: TOKEN_GROUPS](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-token_groups)
