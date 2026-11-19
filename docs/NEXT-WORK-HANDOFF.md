# Next Work Handoff — BTC MiniRAG and recorded Jev evidence path

## Current continuation update — 2026-11-20

The current owner decision is recorded in
[ADR-0058](decisions/ADR-0058-btc-jev-connectivity-only-local-assessor.md):
Jev stays at connectivity-only for this BTC work; BTC B3.1 packet content and
assessment stay local with the separately identified Qwen assessor. The
reauthorized synthetic U3 probe passed its response contract but assessed no
BTC packet. Do not send packet text, citations, or assessment context to Jev.

The local Qwen runtime has only been exercised on synthetic packets. Those
smokes validate local inference and audit plumbing, not BTC prediction,
calibration, or market fusion. The B2 temporal-dependence audit found that the
empirical and conditional baselines classified every holdout row as
non-positive; their accuracy equals the holdout majority rate. This short
holdout does not establish stable edge or regime coverage. See the updated
[BTC MiniRAG/Jev path](BTC-MINIRAG-JEV-EVIDENCE-PATH.md) and
[B2 baseline report](B2-BTC-FEATURES-BASELINES-REPORT.md).

The packet-availability rule is resolved in ADR-0057: a contemporaneous local
receipt with a defensible UTC error bound establishes availability while source
publication remains unknown. The packet must compare the conservative receipt
upper bound with B2 decision eligibility and preserve the unknown publication
field. The B1 archive remains ineligible because its receipt occurred after the
historical B2 decisions and it has no defensible clock error bound. Updating
the code does not authorize the prospective market-data capture; it still
needs separate date-bound approval.

The implementation now serializes the complete eligible B2 feature row,
including `status` and `decision_eligible`, and records MiniRAG completion plus
document receipt separately. A shared pre-inference validator recomputes the
B2 fingerprint, candle continuity, event-time bound, publication or bounded
receipt availability, retrieval fingerprints, and source lineage; it rejects
self-consistent packets that merely assert `provenance.complete` or
`quality.valid`. `CONTRIBUTING.md` documents the narrow write-once local BTC
assessment store and replay exception to read-only CLI inspection.

Keep packet assessment local: qualify an eligible packet, assess it with Qwen,
retain exact packet and B2 observation lineage, and freeze a matched offline
comparison before inspecting holdout results. No Jev packet egress, provider
assessment, market fusion, shadow run, or trading path follows from the
connectivity approval.

The Windows local-assessor child now starts suspended and enters a Windows Job
Object with hard 25% CPU and 6 GiB committed-memory limits before it runs. The
CUDA build uses llama.cpp's 2,048 MiB adaptive free-memory target; this does
not hard-cap VRAM. A synthetic inference and offline replay passed, and the
runtime smoke evidence is in
[`btc-local-assessor-resource-guard-2026-11-20.json`](evidence/btc-local-assessor-resource-guard-2026-11-20.json).
The full Python suite passed: 692 passed, 7 skipped.
Health remains degraded because no OS-level egress block or complete packet
trace is available. This Windows account is non-admin, and Linux has no
configured cgroup supervisor. Do not call this zero-egress or production-ready
until those boundaries are enforced and verified.

The Windows workstation now has the U6.4-baseline CPython 3.11.9 runtime at
`.market_os/runtimes/btc-assessor-py311`, with verified DuckDB 2.0.0 and PyArrow
26.0.1 wheels. Import smoke passed for `market_os.cli`; local health returned
HTTP 200 and the Job Object enforced 25% CPU and 6 GiB. Health remains degraded
because egress rules are absent. No model inference or packet assessment ran,
and no firewall policy changed. Provenance is in
[`btc-assessor-cpython-3.11-runtime-2026-11-20.json`](evidence/btc-assessor-cpython-3.11-runtime-2026-11-20.json).
The older CPython 3.12 feasibility venv is left intact. A repeatable setup and
the Linux CPython 3.11.14 source build remain open.

**Checkpoint base:** `main` at `f316f5f` after PR #52 merged. The Windows
firewall installer remains opt-in and unrun; the ActiveStore verifier did not
find installed rules. No new market-data capture has been run.
U6.4-F/U7-P, B1, and B2 remain closed. ADR-0057 preserves unknown source
publication time while allowing a contemporaneous local receipt with a
defensible UTC error bound to establish future availability. The retrospective
B1 archive remains ineligible. Jev stays connectivity-only, and eligible BTC
packets are assessed locally with Qwen. The prospective Binance stream remains
an unapproved timestamp/provenance pilot; the proposal authorizes no request.

The next engineering slice is to make the CPython 3.11 provisioning repeatable
for Windows and Linux, then finish Linux OS-level egress and cgroup isolation
for the standalone assessor path. The owner’s receipt-time decision does not
approve a new Binance stream: any prospective run still needs current terms and
regional review, a defensible UTC error bound throughout the run, and separate
date-bound approval.

## Where the project stands

- U6.4-D validates a signed, target-native artifact, its Electron binary,
  Python source sidecar, storage separation, slot metadata, and runtime
  boundary without installing anything.
- U6.4-E simulates a local install by copying through a sibling staging
  directory and publishing with one rename. It verifies the published tree,
  manifest, signature, entrypoints, slot metadata, and fresh mutable storage.
- U7-A through U7-O evidence products are complete.
- U7-P now audits deterministic regeneration of the U7-O evidence catalog from
  the U7-I/U7-M inputs and U7-J/K/L synthetic fixtures.
- Product north star: quantitative math and probability are the core; Market OS
  owns stability, calibration, deterministic fusion, signal policy, risk, and
  paper execution; Jev advises on evidence support, contradiction, and
  abstention only.
- The approved B1 dataset is local at `.market_os/btc-history`, revision
  `btc-history-9c58a3ac5cfd05c7398e`. Its 30 daily archives produced 43,200
  canonical candles, 60 HTTPS requests, and zero gaps. The B2 run
  `btc-b2-dde76de3b2965ac6f66a` has 43,190 chronological samples, including
  8,633 test rows. Baselines are near chance; this is a retrospective
  chronological diagnostic, not a contemporaneous feed replay or execution
  result.
- A read-only local recheck matched all 30 checksum files to their 30 ZIPs and
  the registered manifest, read 43,200 rows from Parquet, and matched both the
  Parquet and 43,200-document MiniRAG corpus hashes to their manifests. It made
  zero network requests; details are in
  [`btc-local-artifact-integrity-2026-11-19.json`](evidence/btc-local-artifact-integrity-2026-11-19.json).
- B1 follow-up hardening rejects UNC, mapped Windows network-drive, and
  recognized Linux network-mount roots in the shared history-store boundary.
  The acquisition deadline now reaches canonicalization, Parquet writes, and
  DuckDB catalog ingestion, with an expiry check before commit. Regression
  tests cover UNC rejection and archive-ingest expiry; the current suite passes
  683 tests with 7 skips. Coverage also rejects fixture-supplied raw-file paths
  outside their content-addressed storage names. Secret scan, 93-file evidence
  validation, web artifact, MLOps manifest, Python compilation, and whitespace
  checks pass.
- B3.1 normalized 14 recorded synthetic fixture cases (5 usable; 9 rejected,
  unavailable, stale, or abstained). A BTC-only MiniRAG adapter, future-free
  packet builder, alignment-only helper, and a 43,200-document local source
  corpus now connect the intended seam. Corpus manifest fingerprint:
  `becdc7b7801e8a3d145f43637043a80ed6fb1053ba281ad0f36f7635ef4e2caa` under
  `.market_os/btc-evidence-corpus/`. It preserves original publication time as
  unknown and retains local receipt availability. Its loader verified and
  hydrated all 43,200 records using local availability only as a compatibility
  value for the legacy `published_at` field; source publication remains
  explicitly unknown. Under the clarified gate, unknown publication requires
  a contemporaneous receipt and UTC error bound; the B1 archive has no bound
  and its receipt followed the historical B2 decisions. The
  isolated research runtime uses Python 3.12.0
  and MiniRAG commit `e204d239421f45004852953679927fdf6733f236`; it is outside
  the Market OS base dependencies and U6.4 embedded runtime. Three same-input
  retrieval repeats returned the same four of six candle documents after
  fixing the child `PYTHONHASHSEED`. This checks repeatability only, not
  retrieval quality. Strict packet timing rejects the evidence because local
  availability is after the 2026-10-19 B2 feature close. No recorded Jev
  assessment or B2-to-assessment comparison has run. There is no label-backed
  fusion result or Jev provider path. The fixtures are not a market-level Jev
  comparison. The offline alignment helper reports packet readiness, Jev
  assessment availability, and declared assessment-use time against the B2
  decision clock, without computing market metrics. One synthetic alignment
  fixture matched one observation by exact feature fingerprint and decision
  clock; it validates the contract seam only, with no real market data,
  provider Jev response, usable citation, or market metric. See
  [`btc-b31-synthetic-alignment-2026-11-19.json`](evidence/btc-b31-synthetic-alignment-2026-11-19.json).
  This BTC-specific MiniRAG slice leaves the project's broader LightRAG
  decision unchanged. See the
  [retrieval evidence](evidence/btc-minirag-retrieval-2026-11-19.json) and
  [runtime package snapshot](evidence/btc-minirag-runtime-freeze-2026-11-19.txt).
- The older U3/B3 fixture benchmark uses bullish/bearish/indeterminate
  `Choice` labels and an E2 market-direction score. It is a historical,
  unpromoted experiment, not the target Jev contract for the BTC evidence flow.
  B3.1 is the forward contract: evidence support, agreement/contradiction, and
  abstention remain semantic outputs and are never converted to B2 market
  probabilities or risk/execution inputs.
- The earlier MiniRAG repeats used deterministic local embedding/extraction,
  but their evidence records that the tokenizer cache HTTP request count was
  not instrumented. A post-guard retrieval completed with the same four
  citations. The Python socket guard is not operating-system network isolation
  and outbound socket attempts were not instrumented, so this does not prove
  zero network egress.
- B1 source publication times per candle were not captured. The approved
  archive's local receipt time is 2026-11-18; it does not establish that each
  archived candle was available at its original historical B2 decision.
  Keep packet readiness separate from B2 decision eligibility.
- U8-A/U8-B remain gated. U8-C records the permanent paper-only owner
  decision. Connected promotion, production operations, provider access,
  credentials, mutation, and live execution stay disabled.
- U6.4-F now packages a target-native embedded CPython runtime when CI passes
  `--python-runtime`; the U6.4-D preflight and U6.4-E simulation accept and
  validate that runtime. No native service is registered.
- The Understand Anything graph is a local generated artifact under ignored
  `.ua/`; refresh it after substantive source changes. Local `.market_os/` data
  remains excluded by Git ignore.
- The graph includes the U6.4-F contract, accepted ADR-0055, runtime validator,
  portable installer, focused regression tests, and the U7-P reproducibility module, contract, tests, and evidence; `.ua/` remains an ignored generated working artifact.
- U6.4-F is accepted as signed portable tar.gz for Windows/Linux, per-user
  without elevation, CI-frozen CPython 3.11.x from python.org, manual launch,
  no native service, preserved `python/.market_os` state, and a manual
  `<destination>.rollback` copy on upgrade.
- A local `install:contract:validate` gate validates the accepted fixture,
  rejects authorization while decisions are open or proposed, and fails closed
  on any boundary change. Its focused regression tests pass with the Electron
  suite.

## Closed gate: U6.4-F hosted evidence

The hosted gate closed in CI run `43740383177` on source commit `19367f4`
(PR #37). Both target legs passed the signed package, embedded-runtime, fresh
install, upgrade, rollback, verification-failure recovery, uninstall-retention,
and boundary checks. The exact runner images, CPython archive hashes, runtime
manifest hashes, tree hashes, and candidate archive hashes are retained in
[`u6-4-f-hosted-installation.json`](evidence/u6-4-f-hosted-installation.json).


The accepted contract is recorded in
[`U6.4-F-INSTALLER-AND-PYTHON-RUNTIME-PLANNING.md`](U6.4-F-INSTALLER-AND-PYTHON-RUNTIME-PLANNING.md),
the accepted decision is
[`ADR-0055`](decisions/ADR-0055-u6-4-f-installer-planning.md), and the evidence
schema is [`u6-4-f-installation-contract.json`](evidence/u6-4-f-installation-contract.json).

### Accepted contract decisions

1. **Targets:** supported operating systems, architectures, and minimum
   versions for the first release.
2. **Package format and install scope:** per-user or machine-wide installation
   and the target-native package format for each platform.
3. **Python runtime:** bundled runtime and dependency layout, version pinning,
   offline availability, and how the runtime is validated.
4. **Mutable state:** application, configuration, cache, and portfolio data
   locations; upgrade behavior; preservation and migration rules; uninstall
   behavior.
5. **Permissions and lifecycle:** required elevation, launch model, service
   registration (if any), upgrade, rollback, and removal semantics.
6. **Trust and evidence:** signing inputs, provenance, manifest changes,
   install-result schema, and matching Windows/Linux CI evidence.
7. **Failure handling:** atomicity, retry behavior, interrupted installation,
   conflicting destinations, and recovery after verification failure.

These choices affect installed files, machine/user state, permissions, and
rollback. They are fixed in the accepted contract; the gate closes only after
matching Windows/Linux CI evidence is retained.

## Design direction

The existing seam runs from the U6.4-C signed artifact through the U6.4-D
preflight and U6.4-E simulation. Keep those checks authoritative and put
platform-specific installation behavior in a target adapter that returns a
small, inspectable result. Preserve locality: signature, manifest, storage,
and rollback rules should live behind that installation interface rather than
being reimplemented in each caller.

Keep Python as the domain and accounting authority. Electron owns shell and
installation orchestration only. Do not introduce a second portfolio or risk
implementation. The U8-C paper-only decision remains in force; U6.4-F is
offline packaging work and does not reopen connected or live execution.

## Next steps

1. Do not repeat or extend the approved B1 acquisition without fresh,
   date-bound approval. The local integrity audit is in
   [`btc-local-artifact-integrity-2026-11-19.json`](evidence/btc-local-artifact-integrity-2026-11-19.json).
2. Keep B2 classified as a retrospective chronological diagnostic. Its
   features use current and prior candles with five-minute purge/embargo, but
   archived receipt times do not reconstruct per-candle live availability.
3. Follow the accepted strict recorded-availability rule in
   [ADR-0057](decisions/ADR-0057-btc-strict-recorded-availability.md).
   Original Binance publication time remains unknown; do not infer it from
   candle event time or local archive receipt. A separately recorded local
   receipt with a defensible UTC error bound may establish availability.
4. Review [the prospective-capture proposal](BTC-PROSPECTIVE-CAPTURE-PROPOSAL.md).
   This stream remains diagnostics-only and is not authorized. Before any new
   market-data request, establish that the configured time source can provide
   a defensible UTC error bound throughout the run, recheck terms and regional
   eligibility, and obtain separate date-bound approval. Do not reopen an
   event-time proxy for B1.
5. Treat the post-guard retrieval as a functional check only. It does not prove
   zero egress. No Jev API or other provider call is allowed without separate
   authorization.
6. Once packet eligibility and response provenance are established, use B3.1
   recorded assessments tied to exact packet fingerprints. Freeze the matched
   comparison before looking at held-out results. Keep Jev's support,
   contradiction, and abstention labels semantic; Market OS owns all market
   probability, calibration, stability, risk, and execution decisions.
7. Preserve U7-P and U6.4-F evidence. Keep the older B3 bullish/bearish
   direction benchmark unpromoted and retain the project-wide LightRAG choice.

## Reference artifacts

- [Unified roadmap](ROADMAP.md)
- [Unified phases](PHASES.md)
- [Project context](PROJECT-CONTEXT.md)
- [U6.4-D installer preflight](U6.4-D-INSTALLER-PREFLIGHT.md)
- [U6.4-E offline install simulation](U6.4-E-OFFLINE-INSTALL-SIMULATION.md)
- [U8-C permanent paper-only decision](U8-C-PERMANENT-PAPER-ONLY.md)
- [BTC prospective capture proposal](BTC-PROSPECTIVE-CAPTURE-PROPOSAL.md)
- [Goal prompt for the next implementation chat](GOAL-PROMPT.md)
