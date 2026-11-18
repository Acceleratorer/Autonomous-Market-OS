# BTC MiniRAG and Jev Evidence Path

**Status:** Offline integration slice and bounded local source corpus built.
Three pinned-runtime MiniRAG retrieval repeats completed; the strict historical
packet gate blocks Jev assessment work. A synthetic recorded-assessment fixture
now traverses normalization and alignment, validating that offline seam only.
**Scope:** BTCUSDT Spot, five-minute B2 research target, local historical data,
and paper research only.

## Project roles

| Part | Owner | Role in this path |
|---|---|---|
| B1/B2 | Market OS | Canonical candles, point-in-time features, numerical baselines, labels, calibration, chronological splits, and matched controls. |
| MiniRAG | Local retrieval adapter | Retrieve cited context from BTC-tagged source documents and return source lineage. It does not calculate market probabilities. |
| Jev | Optional typed assessor | Classify evidence support, contradiction, and answerability for a packet. Its label probabilities remain semantic. |
| Market OS | Decision and risk owner | Validate timestamps, provenance, calibration, stability, fusion, risk, paper decisions, persistence, and execution gates. |

The five-minute numerical target remains
`ln(C[t+5]/C[t])`, classified as positive versus non-positive. Jev output is
never substituted for that probability, a return forecast, or an order.

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
  the loader projects the conservative local availability time into that field;
  it does not infer an upstream publication time. This prevents the packet
  builder from treating these later-received archives as available at older
  candle closes.
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

The packet builder rejected the retrieved passage because its conservative
local availability / `published_at` projection is after the feature close.
The original Binance publication time remains unknown. Retrieval is therefore
retrospective and cannot support a historically eligible Jev assessment. No
Jev, LLM, embedding, or market-data API was called. The tokenizer asset needed
by MiniRAG was cached locally; its HTTP request count was not instrumented.
The exact Python executable hash and package versions are recorded in the
[runtime package snapshot](evidence/btc-minirag-runtime-freeze-2026-11-19.txt)
and retrieval evidence.

## Research guardrails

The BTC Vision archive is retrospective. Its local receipt timestamps do not
reconstruct what a live feed exposed at each historical minute. Each packet
must therefore retain B2 `decision_eligible_at` and source availability
timestamps. Event time and local availability are separate fields.
The current policy preserves the unknown original Binance publication time
and uses only recorded local availability. The corpus therefore cannot
establish historical point-in-time eligibility at older B2 decision times.
No source publication time is inferred from candle event time. An explicitly
optimistic event-time proxy would require a separate owner decision and must
not be presented as historical source availability.

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
2. Resolve packet timing before any Jev assessment. The current default remains
   strict recorded availability; keep it and obtain source records with
   contemporaneous availability timestamps, or explicitly authorize a
   separate event-time proxy labeled retrospective and not point-in-time valid.
3. After packet eligibility is resolved, build only recorded B3.1 assessments
   for exact packet fingerprints and join them to the same B2 observations as
   the numerical controls.
4. Freeze an offline matched comparison protocol before reading held-out
   results. Keep Jev API access, credentials, provider egress, and any future
   shadow or trading path behind separate owner decisions.

## References

- [ADR-0023: MiniRAG scope for the BTC evidence path](decisions/ADR-0023-minirag-btc-evidence-scope.md)
- [B3.1 question contract](B3-1-QUESTION-CONTRACT.md)
- [B3.1 offline evaluation protocol](B3.1-OFFLINE-EVALUATION-PROTOCOL.md)
- [B2 feature and target implementation](../market_os/btc_features.py)
- [B3.1 packet profile and recorded normalizer](../market_os/btc_question_evaluation.py)
- [MiniRAG upstream source](https://github.com/HKUDS/MiniRAG)
