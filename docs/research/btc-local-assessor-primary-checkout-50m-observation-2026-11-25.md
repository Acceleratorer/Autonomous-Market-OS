# BTC Local Assessor — primary-checkout 50-minute health observation

- **Recorded:** 2026-11-25 (Asia/Saigon).
- **Outcome:** Completed with observer exit code 0 after 3,000.891 monotonic
  seconds; all 100 sampled health checks were healthy.
- **Scope:** Windows health monitoring of local Qwen on the primary checkout.
  This is not Jev, a BTC assessment, market evidence, or a prediction-quality
  result.

## Checkout and run identity

- Repository: `Acceleratorer/Autonomous-Market-OS`.
- Checkout: primary local checkout, branch `main`, commit
  `b15584f530b8423e848ba7742d125b71c3d28749`; the tree was clean before these
  documentation changes.
- Observation ID: `e21fd706489041f999a5201eabdd88f4`.
- Runtime ready: `2026-11-25T08:03:52.020638+00:00`; stop:
  `2026-11-25T08:53:52.923160+00:00`. These are trace timestamps. The log marks
  wall-clock quality `unqualified`; duration is based on the monotonic clock.
- Sampling: 100 samples, indices 0–99, scheduled every 30 seconds after
  startup. Every sample was healthy, returned HTTP 200 on `127.0.0.1`, and
  reported firewall isolation and resource limits enforced.
- Runtime: `local_qwen_evidence_assessor`, llama.cpp b12478, model
  `Qwen3-4B-Q4_K_M.gguf`, model SHA-256
  `7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5`.
  The pinned CPython runtime was 3.11.18. This is explicitly not TypeSafe Jev.
- Raw JSONL remains local and ignored at
  `.market_os/btc-assessor-observations/e21fd706489041f999a5201eabdd88f4.jsonl`.
  Size: 126,428 bytes. SHA-256:
  `74ce03ce7fccb5af51f96a61bb286352a7f4c86848e231f76ab15e68e0bc1bce`.

## Egress and resource evidence

Windows Defender Firewall ActiveStore reported the Python and pinned
`llama-server.exe` outbound block rules enabled and enforced for the primary
checkout before and across all 100 samples. The retarget result records the
separate secondary-checkout rules preserved. A separate read-only ActiveStore
query at `2026-11-25T09:14:37.5145117Z`, after the observation, found both
secondary rules enabled and enforced; the primary observation did not sample
the secondary executables. Domain, Private, and Public profiles were enabled.
The rules block non-loopback IPv4 and IPv6 while retaining loopback for local
HTTP IPC.

Before the observation, the pinned CPython made one TCP connection attempt to
`192.0.2.1:443`, the RFC 5737 TEST-NET-1 documentation address. Windows denied
it with `PermissionError`, errno 13, and WinError 10013; no application payload
was sent. The sanitized probe record is
`.market_os/btc-assessor-observations/egress-probe.json`, SHA-256
`40d8a62ced52d53e9e4c38d07c19633207f4d0fbc419648b11c0059a6f7ab16b`.

The Windows Job Object reported a 25% CPU hard cap and 6 GiB process/job
commit limits for the inference runtime. No working-set limit was configured.
The CUDA free-memory margin was 2,048 MiB, explicitly adaptive rather than a
hard VRAM limit. `nvidia-smi` sampled 6,804–7,445 MiB of 8,151 MiB aggregate GPU
memory during the run; these values are not per-process attribution.

The observer made zero BTC market-data, TypeSafe Jev, and model-provider
requests. It issued health requests only to loopback. It did not perform model
inference, assess a packet, or prove zero network traffic for unrelated
workstation processes. This is bounded process-policy and runtime-health
evidence, not an internet-wide packet capture.

## Earlier interrupted attempt

The first primary-checkout attempt stopped after 2,173.844 monotonic seconds.
It had 72 healthy samples; sample 72 returned HTTP 200 and retained enforced
resource limits, but the Windows PowerShell ActiveStore verifier exceeded its
8-second subprocess deadline and returned `unverified`. The observer stopped
the runtime and marked that attempt failed. Three immediate read-only verifier
checks then succeeded in 4.2–4.5 seconds each; a new observation was started
and completed as recorded above. The failed raw log remains local at
`.market_os/btc-assessor-observations/d011f738635e435c9695dc39db57d83d.jsonl`
(92,572 bytes; SHA-256
`8a789d333c4665019967c83e003f5b60ef7017853f11858bc09ae1ea4177e35f`). It is
not counted as a successful 50-minute run.

## Limits and next gates

- This run validates only the Windows primary checkout and two executable
  paths. Linux isolation still needs a supported Linux host.
- Windows policy evidence is one bounded RFC 5737 probe plus sampled ActiveStore
  checks. It is not a packet capture or a claim about other workstation
  processes.
- The CUDA margin is not a hard VRAM quota; total GPU memory includes other
  users of the device.
- Authentic local Jev and its local-use terms remain unverified. Qwen is a
  separate local evidence assessor and must not be called Jev. No BTC packet
  was sent to hosted Jev.
- The observation says nothing about prediction quality, calibration,
  stability, paper decisions, or prospective BTC evidence eligibility.
- The raw observation and probe records remain local-only; the committed JSON
  evidence is a sanitized summary.
