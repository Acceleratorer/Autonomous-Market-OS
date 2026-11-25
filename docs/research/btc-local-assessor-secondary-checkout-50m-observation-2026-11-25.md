# BTC Local Assessor — secondary-checkout 50-minute health observation

**Recorded:** 2026-11-25 UTC (2026-11-26 Asia/Saigon).
**Outcome:** Completed with observer exit code 0 after 3,001.172 monotonic
seconds; all 100 sampled health checks were healthy.
**Scope:** Windows health monitoring of the local Qwen runtime on the
secondary checkout. This is not Jev, a BTC assessment, or a market decision.

## Checkout and rule identity

The observation used branch `fix/btc-checkout-scoped-egress` at base commit
`ff40ce1f61fa968372a4008a3123a4b08ca0e36b`, with the patched firewall-script
change present in the working tree. Its SHA-256 was
`1cbc3fb51cdc3354f7bfd247134741e66f58b80f8525f42b515db8b967184984`.

The active checkout already had two enabled, enforced rules in Windows
Firewall ActiveStore, named with the `-SecondaryCheckout` suffix. The
unsuffixed rule names remain bound to the primary checkout under
`D:\Code\Github\HKUDS\Autonomous-Market-OS`. The prior verifier searched by
base or hash-suffixed rule name and therefore failed closed despite the
secondary rules matching the exact pinned executable paths. The updated
verifier locates managed rules by exact application path and then checks the
entire rule configuration. The current rules were not installed, removed, or
changed during this observation; no UAC elevation was needed.

## Health and denial evidence

The pinned runtime became ready at `2026-11-25T16:42:04.810640Z`. The sampler
ran every 30 seconds for 100 samples, indices 0–99. All samples returned HTTP
200 on `127.0.0.1`, reported ActiveStore egress enforcement for both
executables, and reported the Windows Job Object resource limits enforced.
The last sample was at `2026-11-25T17:31:43.929798Z`; the runtime stopped at
`2026-11-25T17:32:05.997062Z`. The observer recorded exit code 0 and a
3,001.172-second duration after runtime startup.

Immediately before the observation, pinned CPython made one TCP connection
attempt to `192.0.2.1:443`, an RFC 5737 TEST-NET-1 documentation address.
Windows denied it with `PermissionError`, errno 13, WinError 10013; no
application payload was sent. The attempt was bounded to two seconds.

The runtime was local `Qwen3-4B-Q4_K_M.gguf`, SHA-256
`7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5`, served by
llama.cpp b12478 through loopback. Python and llama-server were subject to a
25% CPU hard cap and 6 GiB process/job commit limits. The 2,048 MiB CUDA
free-memory margin is adaptive and is not a hard VRAM cap.

The raw JSONL remains local and ignored at
`.market_os/btc-assessor-observations/660aff8e96b24a8ebb62c7f29e777498.jsonl`
(141,099 bytes; SHA-256
`853B6D4BF547A7DE572CAABE398E384AC31EBC2F6D41DF1E1B213A119DC89D20`). The
sanitized summary is in
[`btc-local-assessor-secondary-checkout-50m-2026-11-25.json`](../evidence/btc-local-assessor-secondary-checkout-50m-2026-11-25.json).

The observation performed no model inference and made zero BTC market-data,
TypeSafe Jev, or model-provider requests. It does not prove zero traffic for
unrelated workstation processes or substitute for packet capture.

## Remaining limits

- This verifies only the pinned Windows Python and llama-server paths. Linux
  namespace/cgroup isolation remains unverified on a supported target host.
- Authentic local Jev and its local-use terms remain unverified. Qwen is a
  separate evidence assessor and must not be called Jev.
- No BTC packet or market decision was processed. The clock error bound stays
  unknown, so B3.1 remains ineligible.
- The adaptive CUDA margin is not a hard VRAM quota.
