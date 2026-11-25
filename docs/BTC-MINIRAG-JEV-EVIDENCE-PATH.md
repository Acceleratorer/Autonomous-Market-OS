# BTC MiniRAG and Jev Evidence Path

**Status:** BTC-only MiniRAG integration slice and bounded local source corpus
built; local artifact hashes and row counts were rechecked on 2026-11-19.
The owner selected strict point-in-time availability under
[ADR-0057](decisions/ADR-0057-btc-strict-recorded-availability.md): when source
publication is unknown, a contemporaneous local receipt plus a defensible,
non-negative UTC error bound can establish availability. An event-time proxy
was not selected for the current B1 revision, whose receipt followed the B2
decisions and has no defensible clock bound.
Three pinned-runtime MiniRAG retrieval repeats completed before the child
network guard was added, followed by one post-guard retrieval with the same
four citations. The strict historical packet gate blocks market-linked Jev
assessment work. A synthetic recorded-assessment fixture traverses
normalization and alignment, validating that contract seam only.
The current owner choice is Jev connectivity-only; BTC B3.1 packet assessment
stays in the local Qwen path under
[ADR-0058](decisions/ADR-0058-btc-jev-connectivity-only-local-assessor.md).
**Scope:** BTCUSDT Spot, five-minute B2 research target, local historical data,
and paper research only.

## Project roles

| Part | Owner | Role in this path |
|---|---|---|
| B1/B2 | Market OS | Canonical candles, point-in-time features, numerical baselines, labels, calibration, chronological splits, and matched controls. |
| MiniRAG | Local retrieval adapter | Retrieve cited context from BTC-tagged source documents and return source lineage. It does not calculate market probabilities. |
| Jev | Hosted connectivity probe only | No BTC packet assessment or packet-content egress in the current owner-approved path. |
| Local Qwen | Local evidence assessor | Assess eligible BTC evidence packets under the B3.1-shaped contract. It is not Jev; its current one-hot outputs are uncalibrated and are not market probabilities. |
| Market OS | Decision and risk owner | Validate timestamps, provenance, calibration, stability, fusion, risk, paper decisions, persistence, and execution gates. |

## Jev and the fully local runtime

The real Jev is TypeSafe's hosted System One model. Its published interface is
an authenticated request to `https://api.typesafe.ai/v1/systemone`; current
public materials do not publish local Jev weights or a local runtime. The first U3
connectivity request failed local response validation; a later, separately
approved synthetic connectivity request passed. Neither request assessed a
BTC B3.1 packet. See the [U3 connectivity report](U3-API-CONNECTIVITY-REPORT.md)
and [successful probe evidence](evidence/jev-connectivity-reauthorized-2026-11-19.json).
Under ADR-0058, Jev remains at connectivity for this BTC work. Packet text,
citations, and assessments stay local; local Qwen is the selected packet path.
The synthetic probe did not assess a packet. Future Jev connectivity calls
still require separate explicit approval.

### Jev local-feasibility and use-boundary review — 2026-11-19

TypeSafe's current [Quick Start](https://docs.typesafe.ai/introduction/quickstart)
and [System One API reference](https://docs.typesafe.ai/api/system-one) document
Jev through its authenticated hosted API. The public material reviewed here
does not provide Jev weights or a self-hosted runtime. This is a finding about
the public release path, not proof that TypeSafe has no private deployment
option; a private option would need confirmation from TypeSafe.

The public
[Master Customer Agreement, section 2.3(b)](https://typesafe.ai/legal/mca)
restricts using TypeSafe Services or their output to train an imitator or
develop a similar or competing product, and section 2.3(c) restricts reverse
engineering. That contract language is broader than whether this research is
commercial. This note is not a legal interpretation; it does not establish
that the local assessor is contractually cleared. Keep future local-assessor
design, tests, and tuning independent of TypeSafe Services and their outputs,
and resolve any contractual question with TypeSafe or counsel before expanding
or distributing the assessor. The 2026-11-19 request was isolated synthetic
connectivity evidence; it assessed no BTC packet and its result was not used as
local-model training or evaluation data.

### Independent local System One-compatible runtime candidate — 2026-11-20

The official TypeSafe [Quick Start](https://docs.typesafe.ai/introduction/quickstart)
and [System One API reference](https://docs.typesafe.ai/api/system-one) describe
Jev through an authenticated hosted endpoint. The [Enterprise FAQ](https://typesafe.ai/enterprise)
now answers that Jev is currently available only through the hosted API. Public
Cloudflare, Vercel, Netlify, and OpenRouter routes are hosted gateways; the
public TypeSafe registries reviewed expose no verifiable Jev weights or local
runtime. TypeSafe Sales was asked whether a separately licensed or private
deployment exists and for a runtime manifest and written local-use terms; no
reply has arrived as of this check. This does not rule out a private option.
The dated source, terms, and inquiry record is in
[the local-runtime research note](research/typesafe-jev-local-runtime-2026-11-20.md).
The current [model reference](https://docs.typesafe.ai/models) says the same
weights serve every account and describes domain customization through request
state and questions.
TypeSafe also publishes an official [System One adapter](https://github.com/typesafe-ai/system-one-adapter-python)
for generic LLM APIs; it can preserve the typed client shape with a local
endpoint, but that endpoint's model remains a substitute, not Jev.

An independent project,
[`amithgc/local-jev`](https://github.com/amithgc/local-jev/tree/64a0b31ff343dca32142496cf9edca5a0174a18d),
implements the public System One request/response shape with open models. Its
README describes it as unaffiliated with TypeSafe and containing no TypeSafe
code. **It is a compatible implementation, not Jev.** Keep its reported model
identity and calibration separate from Jev. The reviewed source is pinned to
[`64a0b31`](https://github.com/amithgc/local-jev/commit/64a0b31ff343dca32142496cf9edca5a0174a18d);
the code is MIT-licensed and each model has its own license. Upstream calls it
a research project rather than a finished product and reports its own JevBench
scores. Those scores are not independently reproduced here and say nothing
about BTC evidence-assessment quality or calibration.

The source review found these gaps before it could be treated as a production
runtime:

- `pyproject.toml` uses broad dependency ranges and leaves several dependencies
  without version pins.
- Hugging Face `from_pretrained` calls do not require local-only loading, so a
  model cache miss can attempt a download during model loading. An offline
  deployment would need separately staged and hash-verified files plus runtime
  egress denial.
- The engine has a model-count limit and a memory-budget eviction policy, but
  permits one model to load even when it exceeds the configured budget. That
  is not a hard resource cap.
- The API key is optional. The CLI defaults to loopback, but `/healthz` reports
  only process/version/default-model state and does not establish loaded-model
  readiness.

This candidate has not been installed or adopted. The current BTC owner choice
in [ADR-0058](decisions/ADR-0058-btc-jev-connectivity-only-local-assessor.md)
still selects the separately identified local Qwen assessor. The candidate
review does not change the packet path or authorize Jev, Binance, or model-host
network requests. The synthetic TypeSafe connectivity response remains
excluded from model training, tuning, and quality evaluation, consistent with
[TypeSafe's Master Customer Agreement §2.3](https://typesafe.ai/legal/mca).

Reviewed sources: [`local-jev` README](https://github.com/amithgc/local-jev/blob/64a0b31ff343dca32142496cf9edca5a0174a18d/README.md),
[`pyproject.toml`](https://github.com/amithgc/local-jev/blob/64a0b31ff343dca32142496cf9edca5a0174a18d/pyproject.toml),
[`engine.py`](https://github.com/amithgc/local-jev/blob/64a0b31ff343dca32142496cf9edca5a0174a18d/src/local_jev/engine.py),
[`llm.py`](https://github.com/amithgc/local-jev/blob/64a0b31ff343dca32142496cf9edca5a0174a18d/src/local_jev/backends/llm.py),
and [`api.py`](https://github.com/amithgc/local-jev/blob/64a0b31ff343dca32142496cf9edca5a0174a18d/src/local_jev/api.py).

The local runtime is separately identified as Qwen, using the pinned
[Qwen3-4B model](https://huggingface.co/Qwen/Qwen3-4B) under its published
Apache-2.0 license and llama.cpp under the runtime lock's MIT license. It is
not Jev or a Jev weight port. The local prompt and schema implement Market OS's
BTC B3.1 contract; they do not emulate TypeSafe's model or expose its
`/v1/systemone` API. The Jev API result is not used by that inference path.

The optional local runtime in `market_os/btc_local_assessor.py` uses the pinned
Qwen3-4B GGUF model and llama.cpp. It is a separate local evidence assessor,
not Jev or a Jev model port. It implements the B3.1 support,
agreement/contradiction, and abstention contract; current output labels are
serialized one-hot and explicitly marked uncalibrated. It does not estimate
`P(return_5m > 0)` and cannot enter fusion or paper decisions. Market OS B2,
calibration, stability, and risk remain separate owners.

After the one-time runtime bootstrap, the inference path loads the installed
model/runtime and uses loopback IPC. No TypeSafe, Binance, Hugging Face, or
embedding-provider call is part of the assessment or replay code path. This is
an operating-system egress boundary only when its platform checks pass. Linux
`health` and `assess` run in a rootless systemd user scope and a loopback-only
network namespace; the runtime checks effective cgroup-v2 limits and namespace
membership. Missing user namespaces or cgroup controls fail closed. Linux has
not yet been exercised on a target host. The Windows run on 2026-11-21 verified
executable-scoped firewall enforcement for the paths used in that run. On
2026-11-25, the initial current-checkout health check correctly failed closed
because ActiveStore rules targeted an alternate checkout. The rules were then
retargeted and verified for both checkouts; the primary checkout completed a
50-minute health-only observation with 100/100 healthy samples, and a bounded
RFC 5737 outbound probe was denied locally. This did not run assessment
inference or establish network behavior for unrelated processes. See the
[Windows isolation report](research/btc-local-assessor-os-isolation-2026-11-21.md),
[pre-retarget health evidence](evidence/btc-local-assessor-current-checkout-health-2026-11-25.json),
and [primary-checkout observation report](research/btc-local-assessor-primary-checkout-50m-observation-2026-11-25.md).
Authentic local Jev availability and its offline-use terms remain unverified;
the Windows CUDA fit margin also does not provide a hard VRAM cap. See the
[local Jev runtime check](research/jev-local-runtime-availability-2026-11-25.md)
and [VRAM budgeting options](research/btc-assessor-vram-budgeting-2026-11-25.md).
Bootstrap may download pinned artifacts during setup; the verified assessment
and replay used installed local files and loopback IPC only.
Before inference, the local assessor recomputes the B2 feature fingerprint and
decision clock, checks the six candle references, and validates event time,
publication or bounded-receipt availability, MiniRAG completion, source
fingerprints, and citation lineage from the packet itself. It does not treat
the packet's `provenance.complete` or `quality.valid` booleans as proof.

Assessment runs are stored as write-once JSON bundles through the application
interface, containing the bounded packet, structured local response,
normalized assessment, identities, and fingerprints. `replay` reruns packet
gates and response normalization from that saved bundle; it does not call the
model again. SHA-256 fingerprints detect accidental or unsophisticated
modification, but are not signatures or proof of who created a run.

Prepare the target from an existing host Python, then launch the local assessor
with the pinned CPython 3.11 runtime. From the repository root on Windows:

```powershell
py -3.12 scripts/bootstrap_btc_local_assessor.py --target windows-x64-cuda-13.5
\.market_os\runtimes\btc-assessor-py311\python.exe -m market_os.cli btc-paper local-assessor health --install-root .market_os/local-evidence-runtime/windows-x64-cuda-13.5
\.market_os\runtimes\btc-assessor-py311\python.exe -m market_os.cli btc-paper local-assessor assess --packet <eligible-b31-packet.json> --install-root .market_os/local-evidence-runtime/windows-x64-cuda-13.5
\.market_os\runtimes\btc-assessor-py311\python.exe -m market_os.cli btc-paper local-assessor replay <run-id>
```

The BTC runtime lock uses official CPython 3.11.18 source on both targets,
separate from the existing U6.4/Electron runtime baseline. Linux builds with
the host compiler; Windows uses CPython's `PCbuild` and `PC/layout` flow and
requires the Visual Studio C++ build tools. Bootstrap does not overwrite an
existing runtime that fails the lock check: preserve or move that directory
before rebuilding. The workstation's recorded Windows 3.11.9 runtime predates
this lock and must be rebuilt before the updated assessor can start.

On Linux x64, bootstrap and launch with the target-native interpreter:

```bash
python3 scripts/bootstrap_btc_local_assessor.py --target linux-x64-cpu
.market_os/runtimes/btc-assessor-py311/bin/python3.11 -m market_os.cli btc-paper local-assessor health --install-root .market_os/local-evidence-runtime/linux-x64-cpu
.market_os/runtimes/btc-assessor-py311/bin/python3.11 -m market_os.cli btc-paper local-assessor assess --packet <eligible-b31-packet.json> --install-root .market_os/local-evidence-runtime/linux-x64-cpu
.market_os/runtimes/btc-assessor-py311/bin/python3.11 -m market_os.cli btc-paper local-assessor replay <run-id>
```

On either target, `health` and `assess` automatically enter the local OS
isolation boundary; `replay` stays local file inspection.

The real historical Binance packet still fails the point-in-time availability
gate because its local receipt was after the B2 decisions and the archive has
no defensible UTC clock error bound. Unknown publication time remains unknown;
it does not by itself block a future prospectively received record when
availability is captured with the required clock bound. A successful local
runtime smoke on a clearly synthetic packet proves the inference and audit
plumbing only; it is not a market observation, Jev result, calibration result,
or predictive claim. The smoke metadata is recorded in
[`btc-local-assessor-smoke-2026-11-19.json`](evidence/btc-local-assessor-smoke-2026-11-19.json);
the detailed packet and raw local response remain in the ignored `.market_os`
run store. Windows and Linux runtime archives are separately pinned; only the
Windows CUDA target is currently installed and exercised. No OS-level egress
trace was captured during the original smoke run. A later unprivileged
process-level TCP sample around one fresh synthetic inference observed a
loopback listener and loopback client/server connections; the largest sampled
host working set was about 2.8 GiB. Windows denied PktMon access without
Administrator privileges, so the sample does not prove zero egress or cover
UDP and short-lived attempts. It also does not measure GPU memory. See the
[process observation evidence](evidence/btc-local-assessor-process-network-observation-2026-11-19.json).
A separate Windows CUDA inference sampled aggregate GPU memory 94 times at a
requested 100 ms interval: observed usage rose from 1,300 MiB to a maximum of
5,033 MiB on an 8,151 MiB device. Windows WDDM did not provide per-process
memory attribution, and this sample does not enforce a VRAM cap. See the
[GPU resource observation](evidence/btc-local-assessor-gpu-resource-observation-2026-11-19.json).

On 2026-11-20, the Windows runtime was updated to create `llama-server`
suspended, assign it to a Windows Job Object, and resume it only after the hard
25% CPU-rate and 6 GiB process/job committed-memory limits were accepted by
Windows. The test also exercised a 128 MiB memory limit against a synthetic
child allocation. The runtime now enables llama.cpp's adaptive `--fit` target
with a 2,048 MiB free-memory margin; this is not a hard VRAM quota. The host
does not grant the privilege required for a working-set cap. The local smoke
completed and replayed offline, but health was `degraded` at that checkpoint
because OS-level egress isolation was still unverified. The Linux runtime now
uses a transient systemd scope and user/network namespace, but has not been
resource-verified on a target host. The U5.5 systemd unit files
configure loopback-only IP access, but that disabled deployment package has
not been verified on a target host and the standalone assessor CLI does not
run inside those units. Its policy therefore does not isolate this launch
path. See the
[`OS isolation readiness note`](research/btc-local-assessor-os-isolation-2026-11-20.md)
and [`resource-guard evidence`](evidence/btc-local-assessor-resource-guard-2026-11-20.json).
At that 2026-11-20 checkpoint, Windows had a read-only ActiveStore verifier
and an opt-in executable-scoped firewall installer, but the host rules had not
yet been installed. The dated health evidence records that historical state:
loopback HTTP 200, Job Object resource limits enforced, and egress rules
absent from ActiveStore
([`2026-11-20 OS-isolation evidence`](evidence/btc-local-assessor-os-isolation-2026-11-20.json)).

### Windows runtime egress verification — 2026-11-21

The owner-approved installer now has two active outbound block rules for the
pinned Python and llama-server executables. The verifier checks their
effective ActiveStore filters and enforcement status, along with enabled
Domain, Private, and Public profiles. Health returned HTTP 200 over loopback
and reported both network isolation and resource limits as enforced. A
non-loopback TCP attempt from the pinned Python runtime to 1.1.1.1:443 was
blocked with Windows error 10013. The local IPC path remained available.

One synthetic-only Qwen B3.1 assessment abstained. Its result is uncalibrated,
advisory-only, and ineligible for market fusion or paper decisions. Offline
replay verified the stored bundle with zero inference calls and zero network
requests. No BTC observation, Jev request, or market-data request was used.
The raw packet and response remain in ignored local storage; sanitized
identifiers and results are recorded in
[`Windows egress evidence`](evidence/btc-local-assessor-windows-egress-2026-11-21.json).

This historical run verifies the local Qwen path for the executable paths
used on that Windows target only. Qwen is not Jev. Current-checkout Windows
egress isolation, Linux runtime isolation, and target-host GPU access remain
unverified; the synthetic packet provides no market or calibration evidence.

The five-minute numerical target remains
`ln(C[t+5]/C[t])`, classified as positive versus non-positive. Jev output is
never substituted for that probability, a return forecast, or an order.

The existing U3/B3 directional `Choice` benchmark is a prior fixture-only
experiment. Its bullish/bearish labels and E2 market-direction score are not
the target evidence-assessment role for this BTC flow and remain unpromoted.
The forward BTC contract is B3.1: a local evidence assessor may assess support,
agreement/contradiction, and abstention for an eligible packet. These semantic
labels are not converted into `P(up)` or used as stability, calibration, risk,
or execution inputs. The current implementation uses local Qwen, not Jev.

## Implemented seam

- [`market_os/adapters/minirag.py`](../market_os/adapters/minirag.py) runs
  MiniRAG's `mini` retrieval mode in an isolated child process. It injects
  deterministic local embeddings and structural extraction, strips provider
  credentials from the child environment, disables model caching, and maps
  returned source chunks back to caller-owned document IDs. The adapter only
  accepts BTCUSDT-tagged documents.
- [`market_os/btc_evidence_packet.py`](../market_os/btc_evidence_packet.py)
  joins one eligible B2 feature row to MiniRAG citations and the B3.1 packet
  profile. It preserves observation identity, document and passage hashes,
  publication and availability times, retrieval fingerprints, B1 candle
  lineage, event-time bounds, and source dependency groups.
- [`market_os/btc_source_corpus.py`](../market_os/btc_source_corpus.py) builds
  43,200 one-candle documents from the approved B1 dataset into the ignored
  local store `.market_os/btc-evidence-corpus/`. The corpus retains exact
  decimal values, candle event bounds, content hashes, Binance archive
  fingerprints, one shared dependency group, and B1 local availability times.
  It explicitly records original source publication time as unknown.
  The local build counts, fingerprints, and timing gate are retained in
  [`btc-minirag-corpus-build-2026-11-18.json`](evidence/btc-minirag-corpus-build-2026-11-18.json).
- `LoadedBTCCorpus.for_b2_feature` narrows a retrieval input to exactly the
  six canonical candle documents referenced by that B2 feature fingerprint.
  This keeps the initial MiniRAG/Jev arm on the same frozen market inputs and
  prevents wider-lookback or future-candle additions.
- `load_btc_source_corpus` verifies both artifact hashes and hydrates the
  existing `DocumentRecord` seam. Since that contract requires `published_at`,
  the loader places conservative local availability in that legacy field only
  as a compatibility field; `SourceTimeBounds` separately preserves
  `publication_time_status="unknown-not-captured"`, local receipt, and its
  optional clock error bound. Under ADR-0057, unknown publication requires a
  contemporaneous local receipt plus a defensible UTC error bound; eligibility
  uses the conservative receipt upper bound. The historical B1 records have no
  such bound and arrived after the B2 decisions, so they remain rejected.
- Its recorded-assessment alignment helper matches normalized B3.1 results to
  B2 test predictions by observation, exact feature lineage, decision clock,
  and packet fingerprint. It reports usable coverage only, preserves the B2
  calibration status (including the raw fallback when calibration is
  unavailable), and reports packet readiness, recorded-assessment
  availability, and declared assessment-use time against the original B2
  decision clock. It computes no market metrics.
- The builder excludes realized labels, target returns, future candle rows,
  account state, and execution state. A source event range and publication
  time must be no later than the B2 feature close. Its local availability
  must be no later than B2 decision eligibility and precede MiniRAG retrieval
  completion. Packet availability is the latest feature or source availability;
  retrieval completion contributes to packet readiness, not source availability.
- Correlated passages are grouped by their declared source dependency. The
  builder leaves `independent_evidence_groups` empty unless the caller names
  present groups explicitly. In particular, candles from one Binance Vision
  dataset are one source family, not independent confirmation.
- The existing B3.1 normalizer remains recorded-response-only. This path does
  not contact Jev, TypeSafe, Binance, an LLM API, or an embedding API and does
  not add a calibration or paper-execution path.

The local MiniRAG functions make the adapter executable without an LLM or
embedding service. They provide structural tags and deterministic vectors for
the retrieval seam; they do not demonstrate semantic retrieval quality or
Jev value. The optional upstream MiniRAG runtime is not a Market OS base
dependency. A developer-only runtime is isolated under `.market_os/`, pinned
to Python 3.12.0 and upstream commit
`e204d239421f45004852953679927fdf6733f236`; it does not replace the U6.4
embedded CPython 3.11 runtime. See the local package snapshot and retrieval
evidence linked below.

The alignment contract also has one recorded synthetic exercise in
[`btc-b31-synthetic-alignment-2026-11-19.json`](evidence/btc-b31-synthetic-alignment-2026-11-19.json).
It matches one synthetic observation by exact feature fingerprint and decision
clock; the packet and assessment timestamps are eligible in that synthetic
fixture. This confirms normalization and alignment wiring only. It contains no
real market observation, provider Jev response, usable citation, or market
metric and does not change the historical archive timestamp gate.

## First runtime exercise

The 2026-11-19 experiment selected one eligible B2 feature closing at
`2026-10-19T00:06:00Z`, then supplied MiniRAG exactly the six canonical candle
documents referenced by that feature fingerprint. With `PYTHONHASHSEED=0`,
three consecutive runs returned the same four documents and citation chunks.
Two earlier runs without the fixed hash seed returned four and three passages;
the child environment now fixes that source of variation. This is a narrow
repeatability check, not a retrieval-quality benchmark. The six inputs and
four returned citations are listed by identifier and hash in
[`btc-minirag-retrieval-2026-11-19.json`](evidence/btc-minirag-retrieval-2026-11-19.json).

Those three runs predate the fail-closed socket guard now present in the
MiniRAG child runner. A new run after the guard merge used the same six inputs
and query, returned the same four citations, and had the same query fingerprint.
This verifies that retrieval still completes with the guard and cached runtime;
it does not measure retrieval quality. Against the six B2 input documents, the
stored citations cover four; two inputs were not returned. This is a
single-query coverage diagnostic, not a semantic-quality estimate. The
tokenizer cache was present, but socket attempts were not instrumented. The
guard limits common Python socket APIs to loopback or Unix-domain sockets and
blocks forward/reverse DNS lookups.
It is not operating-system network isolation and native code can bypass it, so
the run does not establish a zero-egress guarantee. See
[`btc-minirag-post-guard-retrieval-2026-11-19.json`](evidence/btc-minirag-post-guard-retrieval-2026-11-19.json).

The packet builder rejects the retrieved passage because its archive receipt
was after the historical B2 decision and the capture did not retain a clock
error bound. Its local availability is not emitted or treated as source
publication time. Retrieval is retrospective and cannot support a
historically eligible Qwen assessment. No
Jev, LLM, embedding, or market-data API was called by the four retrieval runs.
The post-guard run used the cached tokenizer asset; outbound socket attempts
were not instrumented.
The exact Python executable hash and package versions are recorded in the
[runtime package snapshot](evidence/btc-minirag-runtime-freeze-2026-11-19.txt)
and retrieval evidence.

## Research guardrails

The BTC Vision archive is retrospective. Its local receipt timestamps do not
reconstruct what a live feed exposed at each historical minute. Each packet
must therefore retain B2 `decision_eligible_at` and source availability
timestamps. Event time and local availability are separate fields.
The owner selected strict recorded availability in
[ADR-0057](decisions/ADR-0057-btc-strict-recorded-availability.md). Preserve the
unknown original Binance publication time and use only captured availability
metadata. Do not infer publication or availability from candle event time. The
current B1 corpus therefore cannot establish historical point-in-time evidence
for older B2 observations, and its citations remain ineligible for B3.1.

The current B2 run and data limitations are recorded in
[`B2-BTC-FEATURES-BASELINES-REPORT.md`](B2-BTC-FEATURES-BASELINES-REPORT.md).
Any later MiniRAG/Jev comparison must join by the same observation ID and B2
feature fingerprint, use the existing chronological train/calibration/test
partitions and purge/embargo rules, and report only the matched rows where both
arms are usable. The MiniRAG/Jev path adds no realized target to the packet.

No claim about edge, calibration, stability, economic return, or trading value
follows from constructing or retrieving a packet. Jev remains advisory;
Market OS stays paper-only and owns every risk and execution decision.

## Next work

1. Keep source publication time unknown and preserve B1 local availability;
   do not infer publication time from candle event time.
2. A local inventory on 2026-11-19 found the B1 corpus is the only current BTC
   evidence corpus; five saved general document bundles contained no BTC-tagged
   records. No local source corpus qualifies for the strict packet gate. The
   [prospective capture proposal](BTC-PROSPECTIVE-CAPTURE-PROPOSAL.md) defines a
   one-day public-stream pilot and is not execution approval. It records the
   source publication time as unknown and keeps local receipt as a separate
   availability timestamp.
3. Follow the ADR-0057 clarification: a future record with unknown source
   publication time needs a contemporaneous local receipt and defensible UTC
   error bound; use receipt plus bound for availability. This does not turn
   local receipt into publication time. The capture proposal is not approval;
   obtain separate date-bound approval before any new data request.
4. The synthetic path has been exercised and replayed locally. After a
   prospectively eligible BTC packet exists, assess it locally and persist the
   B3.1-shaped response against its exact fingerprint and forward observation
   lineage. The prospective pilot alone is not a market study.
5. Freeze an offline matched comparison protocol before reading held-out
   results. Jev remains connectivity-only; packet assessment egress, any future
   shadow, and any trading path require a new owner decision.

## References

- [ADR-0056: MiniRAG scope for the BTC evidence path](decisions/ADR-0056-minirag-btc-evidence-scope.md)
- [ADR-0057: Strict recorded availability for BTC evidence](decisions/ADR-0057-btc-strict-recorded-availability.md)
- [ADR-0058: Jev connectivity-only and local BTC packet assessment](decisions/ADR-0058-btc-jev-connectivity-only-local-assessor.md)
- [BTC prospective capture proposal](BTC-PROSPECTIVE-CAPTURE-PROPOSAL.md)
- [BTC local assessor Windows OS-isolation verification](research/btc-local-assessor-os-isolation-2026-11-21.md)
- [BTC local assessor OS-isolation implementation checkpoint](research/btc-local-assessor-os-isolation-2026-11-20.md)
- [U3 API connectivity evidence](evidence/u3-api-connectivity.json)
- [B3.1 question contract](B3-1-QUESTION-CONTRACT.md)
- [B3.1 offline evaluation protocol](B3.1-OFFLINE-EVALUATION-PROTOCOL.md)
- [B2 feature and target implementation](../market_os/btc_features.py)
- [B3.1 packet profile and recorded normalizer](../market_os/btc_question_evaluation.py)
- [MiniRAG upstream source](https://github.com/HKUDS/MiniRAG)
