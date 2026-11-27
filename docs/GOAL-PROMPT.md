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
- The product boundary remains local, private, paper-only, read-only, and
  offline. Synthetic fixtures cover product contracts; the approved BTC
  archive is limited to retrospective diagnostics. Credentials, BTC-packet
  egress, mutation routes, public listeners, and live execution remain
  disabled.
- The latest documented full-suite result is `659 passed, 0 failed, 7
  skipped` on U8-B commit `db8c8dd`. Do not describe that as a full-suite run
  on later commits. U6.4-D/E have their own local evidence and focused test
  coverage; inspect those artifacts before making verification claims.
- U6.4-F is now an accepted implementation scope: signed portable tar.gz,
  per-user/no-elevation installation, CI-frozen CPython 3.11.x, preserved
  mutable state, manual rollback, and no native service. Read
  `docs/NEXT-WORK-HANDOFF.md` and verify the local slice before extending CI.
- The English Understand graph is a committed shared artifact at
  `.ua/knowledge-graph.json`. Check its analyzed commit and project-scoped
  freshness before relying on it; refresh it after meaningful source,
  architecture, or contributor-facing documentation changes. See
  [COLLABORATION-WORKFLOW.md](COLLABORATION-WORKFLOW.md) and
  [UNDERSTAND-GRAPH.md](UNDERSTAND-GRAPH.md) for the team workflow.
- U6.4-F is merged under accepted ADR-0055: portable signed install,
  embedded-runtime identity, state preservation, rollback, uninstall retention,
  and evidence rendering. Hosted Windows/Linux evidence is complete and
  retained in `docs/evidence/u6-4-f-hosted-installation.json`.
- U7-P is complete and remains a local regression gate. It regenerates U7-N/J/K/L
  twice and compares the results with committed U7-O evidence.
- B2/B3 math-first contracts and the fixture-only B3.1 assessment
  contract/normalizer already exist. The synthetic B1 fixture still yields
  zero leakage-safe labeled samples, so its B2/B3 metrics remain unavailable.
  Separately, the approved archive has a verified retrospective B2 run with
  43,190 labeled rows, chronological train/calibration/test splits, three
  numerical baselines, and a six-day test diagnostic. These results do not
  establish point-in-time performance, stable edge, profitability, or Jev
  value. See `docs/B2-BTC-FEATURES-BASELINES-REPORT.md` and
  `docs/NEXT-WORK-HANDOFF.md`.
- The approved B1 Binance Vision archive is complete and stored locally: 30
  daily archives, 43,200 canonical candles, 60 HTTPS requests, and no gaps.
  Do not extend acquisition without new date-bound approval. Its retrospective
  receipt still cannot qualify evidence for the earlier B2 decisions.
- Jev is hosted-only in the public TypeSafe release; no official local Jev
  weights or runtime were found. ADR-0058 keeps BTC packet content local with
  separately identified Qwen. The current public Master Customer Agreement
  raises a restriction on developing similar products using TypeSafe Services
  or outputs; check any account-specific agreement or obtain written clearance
  before expanding the local assessor. The 2026-11-27 primary-source recheck
  also found that TypeSafeAI/Qyvos describes a separate Julia-1-based model
  trained on Open-Jev data; it is not Jev and does not establish Jev weights or
  local rights. The already-approved Sales inquiry still has no reply. The next
  Jev gate is written local-use terms plus a verifiable vendor runtime/weight
  manifest. Do not use Jev outputs to train, tune, or evaluate a substitute.
- The Windows CPython 3.11.18 runtime is installed locally. Historical health
  and denial probes from 2026-11-25 do not prove the current boundary: on
  2026-11-27, a direct TCP connection from the pinned Python to `1.1.1.1:443`
  completed even though ActiveStore metadata reported its outbound block rule as
  enforced. An initial PR draft repeated that probe at runtime; it was removed
  because a failed boundary could let the check itself send an outbound TCP
  handshake. The current branch fails closed with
  `active_store_policy_does_not_prove_runtime_egress_denial` and does not open a
  socket. The read-only WFP filter diagnostic still needs an accepted UAC
  prompt. `llama-server` behavior is not independently verified, and Linux
  target-host isolation remains unverified; WSL is not installed on the
  workstation.

## Objective

Continue from the live `main` state; U6.4-F and U7-P are closed. Prioritize the
BTC quantitative line: B2 math/probability first, Market OS-owned stability,
calibration and risk, and Jev as an advisory evidence evaluator. The existing
archive run is retrospective. The next meaningful evaluation requires
prospective, time-aligned history with recorded receipt and a qualified UTC
error bound, plus eligible packets for B3.1. Until those gates are met, retain
the B2 results as retrospective diagnostics and leave the B3.1/Jev comparison
unrun. First resolve whether TypeSafe offers an authentic Jev runtime with
  written local-use rights and a vendor-verifiable manifest. If that remains
  unverified, keep the project goal open and continue only work that does not
  misidentify or train a substitute as Jev.

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
4. Do not fabricate labels or infer predictive value from synthetic rows.
   Keep synthetic-fixture metrics unavailable; treat the real archive B2 run
   as retrospective only. Leave B3.1/Jev comparison unrun until exact
   time-aligned packets, recorded assessments, and matched controls are
   eligible. Follow ADR-0022's frozen target, split, calibration, and fusion
   rules.
5. Keep Python as the sole domain/accounting authority; web and Electron remain
   thin adapters. Preserve unrelated worktree files. Do not reset, clean,
   commit, push, deploy, install software on the host, or expose secrets unless
   separately requested.

## Final report

State the quantitative gate, decisions made, files changed, checks and
evidence actually run, remaining data/provider boundaries, and the exact next
step. Distinguish local verification from hosted CI evidence.
