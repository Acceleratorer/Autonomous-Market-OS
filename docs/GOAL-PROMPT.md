# Goal prompt for the next implementation chat

Continue Autonomous-Market-OS from the live repository state. Read
`docs/PROJECT-CONTEXT.md`, `docs/NEXT-WORK-HANDOFF.md`, `STRUCTURE.md`,
`docs/ROADMAP.md`, `docs/PHASES.md`, the B2/B3/B3.1 contracts and evidence,
and `git status` before editing. Repository history and generated graph data
may lag the live worktree, so verify their checkpoints before relying on them.

## Product north star

Quantitative math and probability are the core. Market OS owns data quality,
stability, calibration, deterministic fusion, signal policy, risk, and paper
execution. Jev adds advisory evidence support, contradiction detection, and
abstention; Jev assessment probabilities are not BTC-return probabilities and
never grant execution or risk authority.

## Current baseline

- U6.4-D signed-artifact installer preflight and U6.4-E offline install
  simulation are complete. E publishes through a staging directory and one
  rename, resets mutable storage, and revalidates the copied artifact. Neither
  registers a service nor bundles Python.
- U7-A through U7-O evidence and evaluation products are complete.
- U8-A and U8-B readiness packs remain gated. U8-C records the owner's
  accepted permanent paper-only decision. Do not reopen connected or live
  work without a new explicit owner decision and complete U8 review.
- The current product boundary remains local, synthetic, private,
  paper-only, read-only, and offline. Credentials, providers, mutation routes,
  public listeners, and live execution remain disabled.
- The latest documented full-suite result is `659 passed, 0 failed, 7
  skipped` on U8-B commit `db8c8dd`. Do not describe that as a full-suite run
  on later commits. U6.4-D/E have their own local evidence and focused test
  coverage; inspect those artifacts before making verification claims.
- U6.4-F is now an accepted implementation scope: signed portable tar.gz,
  per-user/no-elevation installation, CI-frozen CPython 3.11.x, preserved
  mutable state, manual rollback, and no native service. Read
  `docs/NEXT-WORK-HANDOFF.md` and verify the local slice before extending CI.
- The Vietnamese Understand graph is an ignored local artifact at
  `.ua/knowledge-graph.json`. Check its commit and project-scoped freshness
  before using it; refresh after source or documentation changes.
- U6.4-F is merged under accepted ADR-0055: portable signed install,
  embedded-runtime identity, state preservation, rollback, uninstall retention,
  and evidence rendering. Hosted Windows/Linux evidence is complete and
  retained in `docs/evidence/u6-4-f-hosted-installation.json`.
- U7-P is complete and remains a local regression gate. It regenerates U7-N/J/K/L
  twice and compares the results with committed U7-O evidence.
- B2/B3 math-first contracts and the fixture-only B3.1 assessment
  contract/normalizer already exist. Current B2/B3 evidence has zero
  leakage-safe labeled samples, so predictive and calibration results are
  unavailable. Do not claim Jev value or promote it from these fixtures.
- The approved B1 Binance Vision archive is complete and stored locally: 30
  daily archives, 43,200 canonical candles, 60 HTTPS requests, and no gaps.
  Do not extend acquisition without new date-bound approval. Its retrospective
  receipt still cannot qualify evidence for the earlier B2 decisions.
- Jev is hosted-only in the public TypeSafe release; no official local Jev
  weights or runtime were found. ADR-0058 keeps BTC packet content local with
  separately identified Qwen. The current public Master Customer Agreement
  raises a restriction on developing similar products using TypeSafe Services
  or outputs; check any account-specific agreement or obtain written clearance
  before expanding the local assessor. Do not use Jev outputs to train, tune,
  or evaluate it.
- The Windows CPython 3.11.18 runtime is installed and verified locally. The
  2026-11-20 health check returned HTTP 200 but was degraded because its
  checkout-specific firewall rule was absent. On 2026-11-25, the current
  secondary checkout's existing rules were matched by exact executable path;
  fresh health and a bounded denial probe passed without changing firewall
  policy. A subsequent 50-minute health-only observation completed 100/100
  healthy samples. Linux target-host isolation remains unverified.

## Objective

Continue from the live `main` state; U6.4-F and U7-P are closed. Prioritize the
BTC quantitative line: B2 math/probability first, Market OS-owned stability,
calibration and risk, and Jev as an advisory evidence evaluator. The next
meaningful evaluation requires leakage-safe labeled market history; until it is
available, preserve the fixture-only/offline boundary and report metrics as
unavailable.

## Execution rules

1. Inspect live Git state and the B1/B2/B3/B3.1 modules, contracts, evidence,
   `JEV_PROCESSING.md`, ADR-0015/0019/0022, and U8-C. Treat graph-backed
   context as stale if its project-scoped source checkpoint trails HEAD.
2. Keep B2 numerical forecasts and target definitions authoritative. Keep
   calibration, fusion, freshness/stability gates, risk, and paper execution
   inside Market OS. Preserve missing, stale, contradictory, and abstaining Jev
   outcomes explicitly; never substitute a neutral probability silently.
3. Preserve U8-C permanent paper-only mode. B1 is complete under its
   date-bound approval; do not repeat or extend it without new approval. The
   prospective Binance stream remains unapproved and requires a qualified
   continuous UTC error bound, a current source/region review, and separate
   date-bound approval. Jev stays at connectivity-only; no packet egress,
   credentials, connected runtime, mutation routes, or live trades.
4. Do not fabricate market labels or infer predictive value from synthetic
   rows. Keep B2/B3 metrics unavailable until the exact leakage-safe sample
   exists. Follow ADR-0022's frozen target, split, calibration, and fusion rules.
5. Keep Python as the sole domain/accounting authority; web and Electron remain
   thin adapters. Preserve unrelated worktree files. Do not reset, clean,
   commit, push, deploy, install software on the host, or expose secrets unless
   separately requested.

## Final report

State the quantitative gate, decisions made, files changed, checks and
evidence actually run, remaining data/provider boundaries, and the exact next
step. Distinguish local verification from hosted CI evidence.
