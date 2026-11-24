# Next Work Handoff — BTC MiniRAG and recorded Jev evidence path

## Current status — 2026-11-25

The goal remains local-only BTC research with Market OS owning math,
probability, calibration, stability, risk, and paper decisions. Authentic
local Jev is still unverified: current TypeSafe docs show its authenticated
hosted API, the public repositories expose no Jev weights/runtime, and the
2026-11-21 inquiry to `sales@typesafe.ai` has no reply. Keep the local Qwen
assessor explicitly identified as Qwen under ADR-0058; do not send BTC packets
to hosted Jev or call Qwen Jev. See the
[2026-11-25 Jev recheck](research/typesafe-jev-local-runtime-recheck-2026-11-23.md).

The current checkout's pinned-runtime health returned `unavailable` because
the enforced Windows ActiveStore rules target executable paths in an alternate
checkout. The fail-closed preflight did not start llama-server. No firewall
change was applied; an elevated update still needs a successful Windows
approval, followed by health and a bounded non-loopback denial probe. See the
[current-checkout health evidence](evidence/btc-local-assessor-current-checkout-health-2026-11-25.json)
and [isolation report](research/btc-local-assessor-os-isolation-2026-11-21.md).

Linux host isolation, a hard CUDA VRAM cap, ongoing monitoring beyond the
one-shot health command, and eligible prospective BTC evidence remain open.
The UTC error bound remains unknown; the previously completed 60-minute clock
observation is not to be repeated. Do not treat the historical Binance archive
or the synthetic Qwen run as market evidence.

## Current milestone — qualify UTC receipt clock — 2026-11-23

The live chart and finite Binance capture are integrated, but captures remain
ineligible for B3.1 because `clock_error_bound_ms` is unknown. The authorized
60-minute observation completed: 10 minutes of W32Time status checks and 50
minutes of unprivileged wall-clock versus monotonic-clock sampling. The local
clock showed no interval at the diagnostic step threshold, but this only
measures relative stability. W32Time remained stopped/manual. A separate
stripchart diagnostic did not expose root dispersion or establish a UTC error
bound. Raw workstation telemetry remains in ignored `.market_os/clock/` files;
see the sanitized [UTC clock research note](research/btc-utc-clock-error-bound.md).

Next, obtain fresh synchronization-quality data from an approved time source
and define the bound's freshness, holdover drift, and invalidation behavior for
clock steps, suspend/resume, or sync loss. Do not retry the canceled elevated
service launch automatically. Only thread a defensible bound into capture
lineage after these conditions are met; otherwise keep `packet_eligible: false`.
n8n may schedule a one-shot capture, but it is not a time source. Hosted Jev
remains synthetic-connectivity-only and BTC packets stay local.

The capture proposal's original window starts at `2026-11-23T00:00:00Z` and
cannot be run in full now. Rebase it to a future UTC window, recheck Binance
terms, regional eligibility, and retention, and obtain fresh date-bound
approval before any new market-data connection. See the
[prospective-capture proposal](BTC-PROSPECTIVE-CAPTURE-PROPOSAL.md).

## Owner goal: verify authentic local Jev — 2026-11-20

The owner now wants the BTC evidence flow to run locally and use authentic Jev
if TypeSafe provides a lawful, technically supported local runtime. Market OS
continues to own market math, probability, calibration, stability, risk, and
paper decisions.

The public [Enterprise FAQ](https://typesafe.ai/enterprise) says Jev is
currently available only through its hosted API. The public TypeSafe
repositories reviewed expose no verifiable Jev weights or offline runtime.
Public documentation does not rule out a private deployment. See the
[2026-11-23 public-source recheck](research/typesafe-jev-local-runtime-recheck-2026-11-23.md)
for the current documentation, API, and agreement evidence.

Until TypeSafe provides written local-deployment terms and an identifiable
Jev runtime artifact, do not claim the local Qwen assessor is Jev, do not use
hosted Jev outputs to train an imitator, and do not send BTC packets to hosted
Jev. The existing ADR-0058 boundary remains in force while authentic local Jev
is unverified. The public-source review made no Jev API call.

## Current verification — 2026-11-23

The [2026-11-23 public-source recheck](research/typesafe-jev-local-runtime-recheck-2026-11-23.md)
confirms that public TypeSafe materials document hosted Jev only. No
vendor-verified local runtime or local-use terms are evidenced by the public
sources reviewed; a private offer remains unverified. The separately named
`jev-ai/jev-model` repository is an unaffiliated static website, not model
weights or an official TypeSafe runtime. Keep the BTC packet boundary in
ADR-0058.

The Windows x64 local Qwen runtime now has executable-scoped outbound block
rules for the pinned CPython 3.11.18 and llama-server processes. ActiveStore
verification reported enforcement with all three firewall profiles enabled.
A bounded connection attempt to 1.1.1.1:443 was denied by Windows Firewall.
Loopback health returned HTTP 200 with the 25% CPU and 6 GiB Job Object limits
enforced; the 2 GiB CUDA free-memory margin remains adaptive, not a hard VRAM
cap.

One synthetic-only B3.1 run used local Qwen, abstained, and remained
advisory-only, uncalibrated, and ineligible for market fusion and paper
decisions. Offline replay verified the saved bundle with zero inference calls
and zero network requests. This assessed no BTC observation and made no Jev
or market-data request. The raw packet and response remain local in ignored
storage; the sanitized report is
[btc-local-assessor-windows-egress-2026-11-21.json](evidence/btc-local-assessor-windows-egress-2026-11-21.json).
The Windows isolation report is
[btc-local-assessor-os-isolation-2026-11-21.md](research/btc-local-assessor-os-isolation-2026-11-21.md).

This verifies the bounded Windows Qwen path only. Authentic local Jev remains
unverified and Qwen is not Jev. Linux target isolation/GPU access and a
prospective, point-in-time eligible BTC packet remain open gates. Continue
with a real Jev runtime only after TypeSafe provides written local-use terms
and a vendor-authenticated version/runtime/weight manifest. Keep numerical
probability, calibration, stability, risk, and paper decisions owned by Market
OS.

## Live connectivity follow-up — 2026-11-22

The owner requested a fresh synthetic Jev API smoke and a three-minute BTC
update path. The Jev API returned a valid `jev-1.14.0` result from one
synthetic-only request; this verified hosted connectivity, not local Jev or
BTC evidence assessment. The first capture implementation wrote public
BTCUSDT 1-minute candles locally every 180 seconds and required a finite
`--samples` count; the later chart integration is recorded below.

The two-poll capture completed with 2 requests, 0 retries, and 7 new closed
candles. Its data remains in ignored `.market_os/` storage. The workstation
UTC error bound is unknown, so the run marks all records ineligible for B3.1.
No BTC packet went to Jev. See the dated evidence in the
[U3 connectivity report](U3-API-CONNECTIVITY-REPORT.md).

Next: establish a defensible clock error bound before treating receipts as
point-in-time evidence and review Binance terms/retention before planning a
longer bounded capture. Keep hosted Jev at the synthetic connectivity boundary
while BTC packets remain local.

## Local chart continuation — 2026-11-22

The local chart integration is now complete. `market_os.btc_realtime_capture`
stores a finite public BTCUSDT Spot 1m capture under the configured
`MARKET_OS_STORE_ROOT` (default `.market_os/`). The read-only Python route
`GET /v1/btc/realtime/latest` validates and returns up to 64 latest closed
candles. The local Next.js chart reads it through a same-origin route and
refreshes every 180 seconds; it shows registered history while no live capture
is present. The browser does not call Binance, and BTC evidence never goes to
hosted Jev. The chart marks receipts as not B3.1 or paper-decision eligible
while the workstation UTC error bound is unknown.

To run a bounded 30-poll sample, start
`python -m market_os.btc_realtime_capture --allow-live-capture --samples 30`
from the repository with the same `MARKET_OS_STORE_ROOT` as the gateway. This
is a 90-minute run with one public request every three minutes; it does not
install an always-on background task. Change the finite sample count only with
a bounded capture plan and after reviewing Binance terms/retention.

Next work: verify a defensible local UTC clock error bound and capture lineage;
then determine whether a prospective packet can pass the existing B3.1 gates.
Do not enable hosted Jev packet egress or call Qwen Jev. Keep math,
probability, calibration, stability, risk, and paper decisions in Market OS.

## Historical continuation update — 2026-11-20

The current owner decision is recorded in
[ADR-0058](decisions/ADR-0058-btc-jev-connectivity-only-local-assessor.md):
Jev stays at connectivity-only for this BTC work; BTC B3.1 packet content and
assessment stay local with the separately identified Qwen assessor. The
reauthorized synthetic U3 probe passed its response contract but assessed no
BTC packet. Do not send packet text, citations, or assessment context to Jev.

The TypeSafe Sales inquiry and same-thread clarification about local-deployment
identity, artifact hashes, and written terms were sent on 2026-11-20. The
mailbox currently shows those messages as sent, with no vendor reply. Neither
message included an API key or BTC research data. See the
[local Jev runtime note](research/typesafe-jev-local-runtime-2026-11-20.md).

The local Qwen runtime has only been exercised on synthetic packets. Those
smokes validate local inference and audit plumbing, not BTC prediction,
calibration, or market fusion. The B2 temporal-dependence audit found that the
empirical and conditional baselines classified every holdout row as
non-positive; their accuracy equals the holdout majority rate. This short
holdout does not establish stable edge or regime coverage. See the updated
[BTC MiniRAG/Jev path](BTC-MINIRAG-JEV-EVIDENCE-PATH.md) and
[B2 baseline report](B2-BTC-FEATURES-BASELINES-REPORT.md).

The workstation now has the BTC-locked CPython 3.11.18 runtime at
`.market_os/runtimes/btc-assessor-py311`; `--verify-only` passed. The existing
Qwen/llama.cpp artifacts were SHA-256 verified and the bootstrap regenerated
their local install manifest without downloading artifacts. Health returned
HTTP 200 with the Windows Job Object limits enforced, but remains `degraded`
because the Python and llama-server outbound-block rules are absent from
ActiveStore. No model inference or packet assessment ran. Evidence is in
[`btc-assessor-cpython-3.11.18-local-health-2026-11-20.json`](evidence/btc-assessor-cpython-3.11.18-local-health-2026-11-20.json).
The firewall installer is prepared but has not been run; it requires an
elevated session and owner approval before changing Windows Firewall policy.

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
Windows health remains degraded because the executable-scoped firewall rules
are absent. The Linux path now launches local-assessor `health` and `assess`
inside a transient user systemd scope plus a user/network namespace, then
checks the effective cgroup-v2 CPU, memory, and task limits; namespace
membership; loopback-only interface; and IPv4/IPv6 route devices. It fails
closed if any check is missing. Linux tests use mocked OS state only, and this
Windows workstation has no WSL distribution, so the Linux boundary and GPU
device access remain unverified on a real target host. Do not call either
platform production-ready until its target boundary is observed.
The runtime/bootstrap and mocked-isolation evidence is in
[`btc-assessor-runtime-isolation-implementation-2026-11-20.json`](evidence/btc-assessor-runtime-isolation-implementation-2026-11-20.json).
PR #54 merged as `8132c5765d53a3b92486d1c76adaa6f35ddd32ff`. GitHub Actions
run [44644535859](https://github.com/Acceleratorer/Autonomous-Market-OS/actions/runs/44644535859)
passed the Windows and Linux CPython 3.11.18 target builds and uploaded both
runtime evidence artifacts. This proves source-build and packaging steps on
the hosted runners; it does not prove Linux isolation or GPU access on a
supported target host.

The Windows workstation previously used the U6.4-baseline CPython 3.11.9
runtime, with verified DuckDB 2.0.0 and PyArrow 26.0.1 wheels. Its historical
provenance is in
[`btc-assessor-cpython-3.11-runtime-2026-11-20.json`](evidence/btc-assessor-cpython-3.11-runtime-2026-11-20.json).
The older CPython 3.12 feasibility venv remains intact. The 3.11.9 tree is
preserved at `.market_os/runtimes/btc-assessor-py311-3.11.9`; it is historical
U6.4 baseline evidence and does not match the updated BTC lock. The Windows
source build and Linux build remain unverified locally because this workstation
lacks the Visual Studio C++ build tools and a WSL distribution. The pinned
3.11.18 builds passed in CI, and the Windows 3.11.18 bundle is now installed
and verified locally as recorded above.

**Checkpoint base:** `main` at `75a3bbf` after PR #58 merged. PR #57 records
the verified Windows CPython 3.11.18 runtime health; PR #58 adds regression
coverage for unknown publication time with bounded local receipt. Both PRs
were merged under `Acceleratorer`, and both branches were deleted. The local
assessor module passed 17 tests; PR #58 CI finished with 15 passed, 0 failed,
and 3 skipped checks.

The incremental Understand graph is current at `75a3bbf`: 656 files analyzed,
20 symbols in `test_btc_local_assessor.py`, and no unresolved symbols. Two
candidate call edges to provider classes absent from the graph were dropped by
the merge validator.

The Windows firewall installer remains opt-in and unrun; ActiveStore has no
matching executable rules. No new market-data capture or B3.1 packet
assessment has run; Jev remains at the existing synthetic U3 connectivity
scope.
U6.4-F/U7-P, B1, and B2 remain closed. ADR-0057 preserves unknown source
publication time while allowing a contemporaneous local receipt with a
defensible UTC error bound to establish future availability. The retrospective
B1 archive remains ineligible. Jev stays connectivity-only, and eligible BTC
packets are assessed locally with Qwen. The prospective Binance stream remains
an unapproved timestamp/provenance pilot; the proposal authorizes no request.

Next, if the owner approves the two executable-scoped Windows firewall rules,
run the installer elevated, verify ActiveStore, then perform the bounded
non-loopback denial probe and confirm loopback health before one synthetic-only
Qwen assessment. The current PowerShell session is not elevated. On Linux,
verify `health`, cgroup limits, namespace, loopback, and GPU access on a
supported x64 host; this workstation has neither WSL nor Docker. The
receipt-time decision resolves B3.1 eligibility but does not approve a Binance
stream: any prospective run still needs current terms and regional review, a
defensible UTC error bound throughout the run, and separate date-bound
approval. Keep Jev connectivity-only and BTC packets local to Qwen.

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
  tests cover UNC rejection and archive-ingest expiry; the 2026-11-19
  checkpoint passed 683 tests with 7 skips. The later PR #54 full suite passed
  706 tests with 7 skips. Coverage also rejects fixture-supplied raw-file paths
  outside their content-addressed storage names. Secret scan, evidence
  validation, Python compilation, and whitespace checks passed.
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
7. The Windows egress rules, denial probe, loopback health, synthetic-only
   Qwen abstention, and offline replay are now verified in the 2026-11-21
   evidence linked above. Linux still needs a supported x64 host to verify the
   live scope, cgroup, namespace, loopback, and GPU access.
8. Preserve U7-P and U6.4-F evidence. Keep the older B3 bullish/bearish
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
