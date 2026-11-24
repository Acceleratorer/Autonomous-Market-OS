# BTC Local Assessor — 50-minute health observation

- **Recorded:** 2026-11-25 local date (Asia/Saigon).
- **Outcome:** Completed with exit code 0 after 3,000.438 monotonic seconds;
  all 100 sampled health checks were healthy.
- **Scope:** Bounded Windows health monitoring of local Qwen on the secondary
  checkout. This is not Jev, a BTC assessment, or market evidence.

## Run identity and limits

- Repository: `Acceleratorer/Autonomous-Market-OS`
- Checkout: secondary local checkout, branch `main`, commit
  `83a2063cf356e5384dac29006edc90556ce1eb63`; the working tree was clean.
- Observation ID: `6c4df4f70faf4f5ab6e333af0e54b88a`
- Configured duration: 3,000 seconds after startup; startup timeout: 120 seconds.
- Configured health-sample interval: 30 seconds; 100 samples were recorded with
  contiguous indices 0–99.
- Start and stop fields in the log are `2026-11-24T20:19:37.704191+00:00` and
  `2026-11-24T21:09:48.988143+00:00`. The start record marks wall-clock quality
  `unqualified`, so these timestamps are trace metadata, not a clock-accuracy
  result. The measured duration is the monotonic stop value, 3,000.438 seconds.

The health log does not include checkout identity or executable paths. The
commit and checkout above were verified from the local Git/process context
around the run; they are not fields in the JSONL record. The ActiveStore rules
are executable-path-specific, so this result applies to the secondary checkout
that those rules covered. It does not clear the primary checkout's separate
fail-closed health result.

## Observed results

| Check | Result |
|---|---|
| Sampled health | 100/100 healthy; each response HTTP 200 |
| Runtime identity | `local_qwen_evidence_assessor`, llama.cpp b12478; not TypeSafe Jev |
| Model | Qwen3-4B Q4_K_M; SHA-256 `7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5` |
| Bind and IPC | `127.0.0.1`; health checks used local loopback |
| Windows outbound policy | Every sample reported Windows Defender Firewall ActiveStore isolation `enforced` for the checked `python` and `llama-server` executables |
| CPU and host memory | Windows Job Object reported a 25% CPU hard cap and 6 GiB process/job commit limits; no working-set limit was set |
| GPU memory | Aggregate use ranged from 5,320 to 5,323 MiB of 8,151 MiB; this is not per-process attribution |
| CUDA policy | 2,048 MiB adaptive free-memory margin; explicitly not a hard VRAM cap |
| Stop | `stopped` event reported exit code 0 at 3,000.438 monotonic seconds |

After the stop event, a separate process query found neither runtime process ID
observed during the run still present (llama-server PID 13648 and supervisor
PID 41888). The observation log itself contains no PID or teardown record.

## Egress evidence and scope

The observation made loopback health requests. It was not a packet capture and
does not establish that every process on the workstation generated zero
network traffic. No BTC packet, market-data request, hosted Jev request, or
provider assessment was part of this health-only run.

A separate, single-attempt pre-run probe to the RFC 5737 documentation address
`192.0.2.1:443` was denied locally with `PermissionError`, Windows error 10013;
the probe record says `application_payload_sent: false`. This is bounded probe
evidence, not an internet-wide egress audit. The periodic health records also
showed the configured executable-scoped firewall rules as enforced.

The run does not measure prediction quality, calibration, stability of a
market signal, paper decisions, or trading performance.

## Local artifact and limitations

The raw JSONL remains uncommitted in the ignored local checkout at
`.market_os/btc-assessor-observations/6c4df4f70faf4f5ab6e333af0e54b88a.jsonl`;
it is not included in this repository change.

- Raw log size: 125,770 bytes (below 1 MiB).
- Raw log SHA-256: `01fb52c2bd6255b77ad9fcece9377b78e64d989b7e4ce20d6ca9ca4bd49d6e46`.
- Pre-run denial-probe JSON SHA-256:
  `1d383d24c2d6f653eb2349958cc0f37d6393f74542fd98413fa96f5817063af0`.

This verifies a sampled, 50-minute health window for the secondary Windows
checkout only. It does not verify the primary checkout's path-specific
firewall policy, Linux isolation, authentic local Jev, a hard CUDA memory cap,
or a qualified UTC error bound. The wall-clock timestamps must not be used as
BTC evidence-availability timestamps.
