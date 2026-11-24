# BTC Local Assessor OS Isolation — 2026-11-21

**Checked:** 2026-11-21
**Status:** Windows x64 egress and resource enforcement verified on this workstation; Linux target-host isolation remains unverified.
**Scope:** Local Qwen assessment and replay. No BTC market packet, market-data request, Jev request, or trading operation.

## Windows verification

The pinned CPython 3.11.18 runtime and llama.cpp b12478 were already installed
and hash-verified. The elevated installer created executable-scoped Windows
Firewall outbound block rules for both processes. The health path verified the
effective rules in ActiveStore and all three firewall profiles. Health then
returned HTTP 200 over loopback with network isolation and Windows Job Object
resource limits reported as enforced.

A bounded TCP connect attempt from the pinned Python executable to
1.1.1.1:443 was denied with PermissionError, errno 13, and Windows error
10013. This confirms the active policy blocked the tested non-loopback
connection. Loopback remained available for the local llama-server HTTP IPC.
The runtime assessment and replay made no Jev API or market-data request.

The installed local model identity is Qwen/Qwen3-4B-GGUF, revision
bc640142c66e1fdd12af0bd68f40445458f3869b, with model SHA-256
7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5.
The runtime is llama.cpp b12478. This is a local Qwen evidence assessor, not
TypeSafe Jev or a Jev weight port.

One synthetic-only B3.1 assessment completed in 5454 ms and abstained. The
write-once local JSON run bundle remains advisory-only, explicitly
uncalibrated, and ineligible for market fusion and paper decisions. Offline
replay verified the saved bundle with zero inference calls and zero network
requests. The focused suite passed all 17 tests, including typed result
normalization, terminal advisory abstention, fail-closed unverified egress,
offline replay, and typed runtime-start failure. PowerShell parsing passed.

The Windows Job Object enforces a 25% CPU cap and a 6 GiB process/job commit
limit. The 2048 MiB llama.cpp CUDA fit margin is adaptive and is not a hard
VRAM cap. A working-set cap is not enabled.

Sanitized evidence is in
[btc-local-assessor-windows-egress-2026-11-21.json](../evidence/btc-local-assessor-windows-egress-2026-11-21.json).
The raw synthetic packet, model response, and run bundle remain in ignored
local storage.

## Jev availability

TypeSafe’s [Enterprise FAQ](https://typesafe.ai/enterprise) currently answers
that Jev is available only through its hosted API. The
[model catalog](https://docs.typesafe.ai/models) and
[System One API reference](https://docs.typesafe.ai/api/system-one) describe
versioned Jev models through the authenticated remote endpoint. The vendor
inquiry and clarification sent on 2026-11-20 remain unanswered as of this
check; no vendor-authenticated local runtime manifest or Jev artifact hashes
are available. A private offer is not ruled out.

No hosted Jev output was used to train, tune, or evaluate the Qwen assessor.
BTC packets remain local under
[ADR-0058](../decisions/ADR-0058-btc-jev-connectivity-only-local-assessor.md).
Do not relabel Qwen as Jev or treat this Windows verification as proof of
authentic local Jev.

## Remaining verification

1. Verify isolation, cgroup limits, loopback, and GPU access on a supported
   Linux x64 host. Keep Linux readiness unverified until its live health
   result confirms the actual target boundary.
2. Require TypeSafe’s written local-use terms and a vendor-authenticated Jev
   runtime manifest with version and artifact hashes before implementing or
   claiming authentic local Jev.
3. Keep real BTC packet assessment gated on prospective, point-in-time
   eligible evidence. The historical Binance archive is not eligible for the
   earlier B2 decisions, and this synthetic run does not change that.

This is verified Windows runtime hardening for the local Qwen path. It does
not establish full cross-platform production readiness or Jev availability.

## Follow-up — 2026-11-25: health preflight and BTC verification

A code review found that the Windows health command started `llama-server`
before checking the effective outbound firewall policy. Health now uses the
same fail-closed startup preflight as assessment. If network isolation cannot
be verified, it returns an unavailable health record with the isolation
failure and does not leave the inference server running. The assessor context
manager also defers runtime startup until the packet passes its eligibility
gates, so a runtime-start failure can be returned and persisted as a typed
assessment result by the CLI path.

Verification on the local CPython 3.12 environment:

- `python -m pytest -q market_os/tests -k btc` — 200 passed.
- `git diff --check` — passed.

These checks use synthetic fixtures. They do not constitute a live BTC packet
assessment or a new Jev request. Linux host isolation remains unverified, CUDA
VRAM still has no hard cap, and the prior Windows evidence remains specific to
the pinned Qwen runtime and installed firewall policy.
