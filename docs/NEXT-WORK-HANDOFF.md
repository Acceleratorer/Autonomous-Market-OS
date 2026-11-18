# Next Work Handoff — BTC MiniRAG and recorded Jev evidence path

**Checkpoint:** 2026-11-19, implementation branch
`fix/btc-local-storage-runtime-caps`, based on `main` at `3584d3e`. **Status:**
U6.4-F/U7-P are closed; B1 and B2 are complete. The optional MiniRAG runtime
has been exercised locally: three repeats returned the same four of six
selected candle documents. No real BTC packet has a recorded B3.1 assessment;
no market-level Jev comparison has run.

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
- B1 follow-up hardening rejects UNC, mapped Windows network-drive, and
  recognized Linux network-mount roots in the shared history-store boundary.
  The acquisition deadline now reaches canonicalization, Parquet writes, and
  DuckDB catalog ingestion, with an expiry check before commit. Regression
  tests cover UNC rejection and archive-ingest expiry; the current suite passes
  682 tests with 7 skips. PR checks for secrets, 93 JSON evidence files, the
  web artifact, the MLOps manifest, Python compilation, and whitespace also
  pass.
- B3.1 normalized 14 recorded synthetic fixture cases (5 usable; 9 rejected,
  unavailable, stale, or abstained). A BTC-only MiniRAG adapter, future-free
  packet builder, alignment-only helper, and a 43,200-document local source
  corpus now connect the intended seam. Corpus manifest fingerprint:
  `becdc7b7801e8a3d145f43637043a80ed6fb1053ba281ad0f36f7635ef4e2caa` under
  `.market_os/btc-evidence-corpus/`. It preserves original publication time as
  unknown and retains local receipt availability. Its loader verified and
  hydrated all 43,200 records using local availability as a conservative
  `published_at` projection. The isolated research runtime uses Python 3.12.0
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
- The full Understand Anything graph was refreshed on 2026-11-19 from the
  current working tree at HEAD `3584d3e`: 626 files, 2,539 nodes, 4,249 edges,
  8 Vietnamese layers, and a 10-step guided tour. Review covered 626 file
  paths and all 437 import-map pairs; validation found zero duplicate IDs,
  dangling edges, missing required node fields, or other issues. It reports
  351 no-edge warnings. The graph includes the BTC MiniRAG code, evidence, and
  report changes. Its metadata records `analyzedWorkingTree: true`; `.ua/` is
  ignored generated state, and the local `.market_os/` data was excluded by
  Git ignore. `.ua/intermediate/scan-result.json` is preserved for incremental
  graph updates.
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

1. Treat B1 execution evidence as complete for the approved 2026-10-19 through
   2026-11-17 range. Do not repeat or extend acquisition without fresh,
   date-bound approval. Preserve the source receipt-time caveat: the manifest
   uses local raw-artifact timestamps because exact per-response times were
   lost before the first ingest failed. Before any later archive run, verify
   that `--store-root` is genuinely local and include local persistence in the
   runtime bound; the current adapter accepts an arbitrary path and does not
   persist a measured full-run duration.
2. Treat B2's result as a retrospective diagnostic. Its features use only
   current and prior candles and its splits are chronological with five-minute
   purge/embargo, but archive receipt timestamps do not reconstruct actual
   per-candle feed availability. Define that limitation before making any
   paper-performance or market-predictive claim.
3. Until the timestamp policy receives an explicit owner decision, apply strict
   recorded availability: source publication time remains unknown, and the
   current archive cannot establish point-in-time availability at B2 decision
   times. Do not substitute candle event time for publication time.
4. Resolve the BTC archive timestamp gate before creating market-linked
   assessment packets. Continue with strict availability and obtain sources
   with contemporaneous timestamps, or explicitly authorize an event-time proxy
   labeled retrospective and not point-in-time valid.
5. Only after packet eligibility is resolved, join recorded B3.1 assessments
   tied to exact packet fingerprints. Freeze a time-aligned matched comparison
   before reading held-out results; keep calibration on the calibration
   partition only under ADR-0022. Jev API access needs separate approval. Jev
   remains advisory; Market OS retains risk and execution authority.
6. Keep U7-P as a local regression gate and preserve the U6.4-F hosted evidence
   record. Do not reopen connected or live-readiness work without a new owner
   decision.

## Reference artifacts

- [Unified roadmap](ROADMAP.md)
- [Unified phases](PHASES.md)
- [Project context](PROJECT-CONTEXT.md)
- [U6.4-D installer preflight](U6.4-D-INSTALLER-PREFLIGHT.md)
- [U6.4-E offline install simulation](U6.4-E-OFFLINE-INSTALL-SIMULATION.md)
- [U8-C permanent paper-only decision](U8-C-PERMANENT-PAPER-ONLY.md)
- [Goal prompt for the next implementation chat](GOAL-PROMPT.md)
