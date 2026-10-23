# B3.1 Offline Question Contract Proposal

**Status:** Proposed document-only contract; owner approval is still required.

**Scope:** BTCUSDT Spot, recorded fixtures, and offline research artifacts only.
This document prepares a later fixture-only scaffold. It does not authorize an
implementation, provider request, data acquisition, paper execution, or
trading.

## 1. Inherited boundaries and invariants

This is an internal Market OS contract profile. It is not a TypeSafe wire
schema, a Jev wire schema, or evidence that a provider supports these
questions. Provider mapping is deferred. The profile is an interpretation of
the internal market-os.jev-processing.v1 governance contract over the existing
market-os.evidence-packet.v1 and market-os.jev-assessment.v1 artifact families.

The following boundaries are frozen by [ADR-0022](decisions/ADR-0022-b3-1-decision-freeze.md):

- Jev is a typed, advisory evidence evaluator. It is not a forecaster,
  execution authority, risk approver, or source of market-return probabilities.
- B3.1 is BTCUSDT Spot-only and paper-only. It excludes short inventory,
  leverage, margin, futures, perpetuals, and funding.
- B3.1 uses recorded fixtures only. It makes no Jev, TypeSafe, Binance,
  OpenAI, or other provider call; uses no credentials; acquires no history; and
  changes no signal, sizing, risk, execution, persistence, or recovery path.
- Market OS owns packet validation, provenance, freshness, calibration, fusion,
  signals, sizing, risk, paper execution, persistence, recovery, and portfolio
  state. Jev supplies only typed advisory results for a supplied packet.
- Existing B3 E1/E2 remain unchanged, offline, recorded-response-only, and not
  promoted. This proposal does not rename, rewrite, or promote either arm.

The B2 primary target remains the five-minute log return
ln(C[t+5]/C[t]), classified as positive versus non-positive. That target is
for a later offline join and evaluation. No question result below is a market
prediction, a trading signal, or P(return_5m > 0).

## 2. Proposed versioned identities

The following identities are recommendations for owner review. Each row has
one canonical machine identity in the form schema_id@version. The symbolic
names are code-facing labels only; they are not schema IDs, versions, or
provider identities.

| Artifact or question | Symbolic name | Canonical schema ID | Version | Canonical machine identity | Cardinality |
|---|---|---|---|---|---|
| B3.1 evidence-packet profile | B31_EVIDENCE_PACKET_PROFILE | market-os.b3-1.evidence-packet-profile | v1 | market-os.b3-1.evidence-packet-profile@v1 | one profile per packet |
| Evidence support question | B31_EVIDENCE_SUPPORT_QUESTION | market-os.b3-1.question.evidence-support | v1 | market-os.b3-1.question.evidence-support@v1 | one result per stable hypothesis ID |
| Agreement/contradiction question | B31_AGREEMENT_CONTRADICTION_QUESTION | market-os.b3-1.question.agreement-contradiction | v1 | market-os.b3-1.question.agreement-contradiction@v1 | one result per stable hypothesis ID |
| Abstention question | B31_ABSTENTION_QUESTION | market-os.b3-1.question.abstention | v1 | market-os.b3-1.question.abstention@v1 | one result per packet |
| Normalized assessment configuration | B31_NORMALIZED_ASSESSMENT | market-os.b3-1.normalized-assessment | v1 | market-os.b3-1.normalized-assessment@v1 | one normalized assessment per packet |

market-os.jev-processing.v1 remains the governance contract. The packet
profile does not replace market-os.evidence-packet.v1; it pins the B3.1 task,
question references, target lineage, and fixture-only identity fields within
that packet schema. The normalized result remains an instance of
market-os.jev-assessment.v1; the configuration version declares how its
question results are represented and normalized. None of these identities is a
TypeSafe or Jev provider version.

## 3. Common result shape

Each question result is retained with:

- canonical schema ID/version and assessment configuration canonical machine
  identity;
- the referenced observation_id, packet fingerprint, and stable packet
  hypothesis_id values (or packet for the packet-level abstention result);
- the exact closed labels map, selected_label, and a probability distribution
  over every label;
- status, evidence references, response fingerprint, and applicable
  response/availability/freshness timestamps.

Every probability is finite, in [0, 1], covers the complete declared label set,
and sums to one within the contract tolerance. A selected label must be the
unique maximum. A tied maximum is not resolved by object order: the result is
abstained with reason tied_maximum, or, if a non-abstaining selected label is
supplied, internally inconsistent. A probability is always the probability of
a label in that question, conditional on the supplied packet and hypothesis; it
is never a market-return probability, expected return, confidence in a trade,
or permission to act.

hypothesis_id values must be copied from the packet's stable candidate
hypotheses. A result may refer to related hypotheses only by their existing
stable IDs. The evaluator cannot mint, rename, merge, or reorder hypothesis
IDs. Missing, duplicate, or foreign IDs are internally inconsistent.

For a packet with H stable candidate hypotheses, the required result counts
are:

| Hypothesis count | Evidence-support results | Agreement/contradiction results | Abstention results |
|---:|---:|---:|---:|
| H = 0 | 0 | 0 | exactly 1 packet-level result |
| H = 1 | exactly 1 | exactly 1 | exactly 1 packet-level result |
| H > 1 | exactly H | exactly H | exactly 1 packet-level result |

Every hypothesis requires both per-hypothesis results. There are no
cross-hypothesis aggregate results in v1. With H = 0, the packet-level
abstention result must select abstain; selecting answerable is internally
inconsistent because no hypothesis exists to assess. With H >= 1, the
packet-level abstention result is still required exactly once.

When H = 1, the required agreement/contradiction result must select unknown.
Agreement, mixed, and contradiction require at least one distinct comparison
hypothesis or at least one independently identified, non-correlated evidence
group relevant to the same normalized target, direction, units, and horizon.
The sole hypothesis must never be treated as independent corroboration of
itself. This single-hypothesis unknown is a valid usable semantic label; it is
not terminal abstained.

## 4. Exact question contracts

### 4.1 Evidence support

- Question identity: market-os.b3-1.question.evidence-support@v1.
- Purpose: assess how well the packet evidence supports one bounded candidate
  hypothesis, without judging future market accuracy.
- Deterministic wording: “Given only the point-in-time packet and the cited
  evidence for hypothesis {hypothesis_id}, classify the evidence support for
  that hypothesis claim.”
- Permitted inputs: the hypothesis claim, target/direction/horizon, packet
  source references, evidence excerpts or hashes already in the packet,
  candidate lineage, and deterministic packet quality fields. No future rows,
  realized outcomes, account state, provider memory, or unrecorded context.
- Exact labels: supported, mixed, unsupported, unknown. Explicit refusal is
  represented by the terminal status abstained, not by an additional support
  label.
- Meanings: supported means supplied evidence supports the bounded claim;
  mixed means support and counterevidence coexist; unsupported means supplied
  evidence does not support the claim; unknown means the packet is insufficient
  to classify support. Unknown is a valid semantic label and does not itself
  force terminal abstained status. Explicit refusal is represented by terminal
  status abstained.
- Selection: unique maximum probability. A tied maximum yields terminal
  abstained with reason tied_maximum. An explicit refusal also yields terminal
  abstained with its reason.
- Never infer: supported is not truth, accuracy, causal validity,
  P(return_5m > 0), expected return, or a signal.

### 4.2 Agreement versus contradiction

- Question identity: market-os.b3-1.question.agreement-contradiction@v1.
- Purpose: classify whether independently identified packet hypotheses and
  evidence support a common bounded claim or conflict for the same target and
  horizon.
- Deterministic wording: “Considering only the packet hypotheses with the same
  normalized target, direction, units, and horizon as {hypothesis_id}, classify
  their relationship to that hypothesis.”
- Permitted inputs: stable hypothesis IDs, normalized claims, target and
  horizon, source identities and dependency groups, and packet-local evidence
  references. Correlated duplicates cannot count as independent support.
- Exact labels: agreement, mixed, contradiction, unknown. Explicit refusal is
  represented by the terminal status abstained, not by an additional
  relationship label.
- Meanings: agreement means relevant independent candidates support compatible
  claims; mixed means compatible and conflicting evidence coexist; contradiction
  means incompatible claims for the same event and horizon; unknown means the
  relationship cannot be determined from the packet. Unknown is a valid
  semantic label and does not itself force terminal abstained status. Explicit
  refusal is represented by terminal status abstained.
- Selection: the same unique-maximum and tied-maximum rule as support. An
  explicit refusal or tied maximum yields terminal abstained for this result.
- Never infer: agreement is not correctness, contradiction is not proof that
  either candidate is right, and neither label is a market probability or
  trading instruction.

### 4.3 Abstention

- Question identity: market-os.b3-1.question.abstention@v1.
- Purpose: make answerability explicit when the packet is insufficient,
  conflicting, invalid, stale, or unsafe to use for the requested semantic
  assessment.
- Deterministic wording: “Using only this packet, is the requested B3.1
  assessment answerable without inventing evidence or relying on future
  information?”
- Permitted inputs: packet status and quality gates, source availability and
  freshness, hypothesis completeness, and packet evidence references. It is
  parsed independently from the other two question families and cannot use
  their parsed results to decide whether the packet is answerable. It cannot
  override deterministic Market OS gates.
- Exact labels: answerable, abstain.
- Meanings: answerable means the packet is sufficient for the requested
  semantic assessment; abstain means the evaluator explicitly refuses because
  the packet is insufficient or unsafe.
- Selection: unique maximum is required. A tie is abstention with reason
  tied_maximum; abstain as maximum yields terminal abstained.
- Never infer: answerable does not mean evidence is correct, fresh, predictive,
  calibrated, or executable. Deterministic consistency, provenance, freshness,
  and evidence-quality gates remain Market OS answers.

## 5. Deterministic processing and normalization

The proposed configuration identity is
market-os.b3-1.normalized-assessment@v1. Processing is strictly ordered:

1. **Packet gates.** Validate packet identity, schema, hypothesis cardinality,
   point-in-time availability, freshness, provenance, and future-field
   exclusions. A failed packet gate prevents a usable assessment before any
   question result is used.
2. **Parse individual results.** Parse the packet-level abstention result and
   every required per-hypothesis support and agreement/contradiction result
   independently. The abstention result does not depend on sibling results.
3. **Apply per-question statuses.** Apply each result's schema, support,
   identity, timestamp, freshness, unavailable, abstained, or usable status.
   A selected unknown label remains a usable semantic result.
4. **Normalize the top-level assessment.** Apply the status precedence and
   cardinality rules below, then retain all parsed results without changing
   their question semantics.

The normalized artifact retains all three question families as
separate records. It never averages, multiplies, or otherwise turns their
semantic distributions into a market probability. The normalized artifact
contains individual distributions, selected labels, statuses, hypothesis IDs,
evidence references, timestamps, and fingerprints, plus deterministic summary
fields such as ranked_hypothesis_ids and explicit missing or abstaining ID sets.

Top-level terminal status uses the existing precedence from
[JEV_PROCESSING.md §14](../JEV_PROCESSING.md#14-status-contradiction-and-failure-semantics):

schema_invalid > unsupported > internally_inconsistent > stale > unavailable >
abstained > usable.

Normalization rules:

1. Malformed result or malformed question set is schema_invalid; no ranking.
2. Unsupported question, version, option set, primitive, or configuration is
   unsupported; no ranking.
3. Selected-label/distribution, identity, timestamp, provenance, or
   hypothesis-ID violation is internally_inconsistent; no ranking.
4. A packet freshness failure at the declared assessment use time is stale;
   no ranking. A response freshness failure at that same use time is also
   stale; no ranking. Freshness failure is evaluated before deciding whether
   a response is merely unavailable.
5. A missing question result or no valid response is unavailable; valid
   siblings are retained for audit, but the artifact is not an eligible
   candidate input.
6. For a recorded response, compare response_received_at_ms with the frozen
   response deadline measured from request_started_at_ms, and compare both
   response and packet freshness against the applicable fresh_until_ms or
   expires_at_ms at the declared assessment use time. A response received
   after the response deadline but while the packet and response remain within
   their freshness windows is unavailable with reason late. If the response or
   packet is outside its freshness window at use time, status is stale, which
   takes precedence over late. If no valid response exists, status is
   unavailable, provided the packet freshness gate passed, unless an earlier
   schema, unsupported, or inconsistency failure has precedence. Thus a
   recorded response that arrives after the eligibility/use freshness window is
   stale; a missing response without a freshness failure is unavailable. Valid
   explicit refusal, including a tied maximum, is abstained; valid siblings are
   retained, but the artifact is not an eligible candidate input.
7. Three complete result families with valid statuses yield usable. A selected
   unknown label remains usable. Valid evidence disagreement remains a
   dimension of that usable artifact, not parser failure.
8. A concentrated-but-valid distribution remains usable and records
   concentration diagnostically. Concentration alone never causes rejection or
   a HOLD.

The v1 normalized artifact requires all three question families and the
cardinality counts in Section 3. A partial fixture may preserve valid
individual results, but normalization fails closed as unavailable with an
explicit missing-question or missing-hypothesis set. No provider result is
silently replaced with a neutral value. A complete usable artifact is only an
eligible candidate input; actual calibration or fusion use requires a
separately frozen Market OS protocol.

For a complete usable artifact, v1 defines one diagnostic ranking projection:
include each hypothesis whose support result is usable; order first by support
label rank supported (0), mixed (1), unknown (2), unsupported (3); within an
equal label rank, order by descending support probability for the selected
label; break any remaining tie by ascending stable hypothesis_id. Hypotheses
with non-usable support results are omitted and listed explicitly. This
ranking is diagnostic only, is empty for every non-usable or partial artifact,
and cannot affect calibration, fusion, signal, sizing, risk, or execution.

## 6. Candidate, target, and timestamp boundaries

The packet uses B2 feature lineage (btc.b2.features.v1) and preserves B2 target
identity (btc.b2.close-return-5m.v1) only as point-in-time lineage. The realized
target is joined later in an offline evaluation artifact. The packet and any
future provider-request projection must exclude realized labels, future target
rows, future returns, fills, account state, target-derived fields, and B2's
future-derived target_fingerprint.

The packet follows the existing rules for decision_eligible_at_ms,
packet_available_at_ms, packet_ready_at_ms, request_started_at_ms,
response_deadline_at_ms, response_received_at_ms, available_at_ms,
fresh_until_ms, and explicit expiry. response_deadline_at_ms is required and
configuration-derived:

response_deadline_at_ms = request_started_at_ms + max_response_latency_ms

max_response_latency_ms is a named configuration parameter. Its actual
threshold remains deferred for owner approval. The response deadline is
distinct from fresh_until_ms and expires_at_ms: the deadline determines
whether an otherwise fresh response is late, while freshness or expiry at the
declared assessment use time determines stale. Under the existing status
precedence, stale takes precedence over unavailable and late.

Packet readiness is after candidate computation, validation, canonical
serialization, and fingerprinting; request start cannot precede packet
readiness; response availability follows validated receipt. Fingerprints are
deterministic SHA-256 values over declared future-free projections. Freshness
is checked at use time and is never inferred from response time.

These boundaries follow [JEV_PROCESSING.md §§3–4](../JEV_PROCESSING.md#3-evidence-packet-input-contract)
and [btc_b2.py](../market_os/btc_b2.py), whose materialize_rows function keeps
point-in-time features separate from future labels.

## 7. Minimum fixture taxonomy

The following cases are required for a later fixture-only scaffold. They are
contract cases, not evidence of provider behavior.

| Fixture kind | Expected status | Ranking allowed? | Later calibration/fusion? | Required handling |
|---|---|---:|---:|---|
| Valid complete assessment | usable | Yes, deterministic display ranking only | Eligible candidate input only; actual calibration/fusion use requires a separately frozen protocol | Preserve all three results and provenance. |
| Malformed/schema-invalid | schema_invalid | No | No | Fail closed; preserve rejection and response fingerprint when available. |
| Unsupported question/version/configuration | unsupported | No | No | Preserve unsupported identity; do not infer compatibility. |
| Selected label versus distribution mismatch | internally_inconsistent | No | No | Reject; never repair by field order. |
| Stale or late response | stale for freshness; unavailable for recorded late outcome | No | No | Preserve timestamps and reason; no silent fallback. |
| Unavailable response | unavailable | No | No | Preserve explicit unavailable state; numerical arm remains separate. |
| Explicit abstention | abstained | No | No | Preserve label/reason and count coverage; no neutral substitution. |
| Valid evidence disagreement | usable with disagreement dimension | Yes, if otherwise complete | Eligible candidate input only; actual calibration/fusion use requires a separately frozen protocol | Disagreement is semantic evidence, not parser failure. |
| Concentrated-but-valid output | usable with concentration diagnostic | Yes, if otherwise complete | Eligible candidate input only; actual calibration/fusion use requires a separately frozen protocol | Do not treat concentration as market confidence. |
| Partial three-question result | unavailable with missing IDs | No | No | Retain valid siblings for audit; require all three for usable v1. |

schema_invalid, unsupported, internally_inconsistent, stale, unavailable,
abstained, and usable are the only terminal statuses in this proposal. They
follow JEV_PROCESSING.md; late is a source case that normalizes to unavailable.

## 8. Compatibility and experiment mapping

The existing B3 identities remain unchanged:

- E1 is the numerical B2 conditional-rate control over the frozen feature
  input.
- E2 is the same numerical input plus one typed recorded Jev assessment.
- E1 and E2 remain offline, recorded-response-only, and not promoted. B3.1
  does not relabel, rewrite, or replace either arm.

N0, J1, C2, C2-control, and F3 remain future conceptual arms only, as
described in [JEV_PROCESSING.md §7](../JEV_PROCESSING.md#7-baseline-and-incremental-experiments).
B3.1 fixture work is not a claim of predictive edge, execution readiness,
provider compatibility, or prospective-shadow approval.

## 9. Unresolved owner choices

The following are recommendations, not approvals:

- approve or revise the proposed IDs, versions, label sets, and wording;
- confirm that v1 requires all three results for a usable normalized assessment
  and treats partials as unavailable;
- approve the deterministic display-ranking projection for inspection only;
- decide whether a later owner-approved scaffold may add these internal
  contracts and fixtures without changing B3 code, API contracts, provider
  adapters, or execution paths.

Provider/model capability, wire mapping, request budget, retention, redaction,
latency, dataset sufficiency, calibration sample thresholds, and
prospective-shadow terms remain deferred under
[ADR-0022](decisions/ADR-0022-b3-1-decision-freeze.md).

## 10. Future gate: explicit owner approval request

Before any implementation, the owner must approve this proposal or a revised
version as a fixture-only B3.1 scaffold. A later implementation may only add
offline typed contracts, deterministic normalizers, and recorded fixtures;
make zero external requests; use no credentials; preserve B3 E1/E2; and avoid
changes to signals, sizing, risk, paper execution, persistence, recovery, and
provider adapters. This document does not claim that approval has been given.

## References

- [ADR-0022: B3.1 decision freeze](decisions/ADR-0022-b3-1-decision-freeze.md)
- [ADR-0015: BTC math-first Jev experiment](decisions/ADR-0015-btc-math-first-jev-experiment.md)
- [ADR-0019: U3/B3 Jev boundary](decisions/ADR-0019-u3-b3-jev-experimental-boundary.md)
- [JEV_PROCESSING.md](../JEV_PROCESSING.md)
- [U3/B3 incremental benchmark report](U3-B3-JEV-INCREMENTAL-BENCHMARK-REPORT.md)
- [API contracts](api/contracts.md)
- [B2 implementation](../market_os/btc_b2.py)
- [B3 implementation](../market_os/btc_b3.py)
