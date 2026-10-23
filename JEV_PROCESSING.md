# JEV_PROCESSING.md — Jev probabilistic evidence evaluator design

**Status:** B3.1 decision freeze recorded in [ADR-0022](docs/decisions/ADR-0022-b3-1-decision-freeze.md).
This architecture authorizes no provider request, credential use, data
acquisition, execution path, B3.1 implementation, or study.

**Scope:** BTCUSDT Spot research using B2's existing five-minute log-return
definition and B1/B2/B3 lineage. B3 remains an offline recorded-response
benchmark and is not promoted. B3.1 remains fixture-only; its decision freeze
does not authorize implementation or evaluation.

## 1. Architectural role

Jev is an **evidence evaluator**, not the primary market forecaster. It must
not be forced to produce ordinary free-form reasoning, replace arithmetic, or
own a trading decision. It is also not a proof system: a typed answer can be
well-formed while its claim is wrong, so evaluation must preserve that distinction.

Deterministic technical-analysis, mathematical,
statistical, numerical-model, and code-validation engines first produce
structured candidate hypotheses and tagged candidate values. Jev then evaluates
the supplied packet for semantic evidence support, agreement or contradiction,
and abstention under the frozen B3.1 questions. Any broader assessment
dimensions below are not additional Jev questions in B3.1.

For the frozen B3.1 question taxonomy, Jev remains advisory and the initial
versioned questions cover evidence support, agreement versus contradiction,
and abstention. Consistency, freshness, provenance, and evidence-quality gates
remain deterministic Market OS responsibilities. Regime questions and additional
context are deferred. The contract's broader dimensions do not expand this
initial question set.

The intended path is:

~~~text
closed point-in-time data
  -> deterministic features, quality checks, and numerical candidates
  -> immutable evidence packet
  -> optional typed Jev assessment
  -> Market OS validation and target calibration
  -> deterministic fusion and signal policy
  -> Market OS risk policy and paper-only execution
~~~

Market OS owns calibration, fusion, signal policy, position sizing, leverage,
risk, paper execution, provenance, persistence, recovery, and portfolio state.
Jev's role is an advisory typed evaluator over a supplied packet. Its result is
never an order, risk approval, execution permission, or native probability of a
future BTC return.

This preserves the boundaries in [TECH_DOCS.md](TECH_DOCS.md),
[STACK.md](STACK.md), [ADR-0015](docs/decisions/ADR-0015-btc-math-first-jev-experiment.md),
and [ADR-0019](docs/decisions/ADR-0019-u3-b3-jev-experimental-boundary.md).

## 2. Domain vocabulary and ownership

`market-os.jev-processing.v1` is the overall internal processing and governance
contract. It contains two distinct Market OS artifact schemas:

- `market-os.evidence-packet.v1` is the immutable packet input. Market OS owns
  its construction, canonical serialization, hashing, and persistence before an
  optional assessment.
- `market-os.jev-assessment.v1` is the normalized assessment output. Market OS
  owns validation, normalization, persistence, provenance, and compatibility;
  Jev supplies only the advisory typed-evaluator result inside it.

The packet is the input to an assessment, and the assessment records the packet
fingerprint plus the pinned question and provider/model identity. The schemas
version independently under the processing contract: a packet or assessment
version change requires an explicit adapter and new fingerprints, while the
immutable packet is never rewritten to fit a newer output. Both are internal
Market OS artifact schemas, not TypeSafe wire versions. Neither schema
authorizes a TypeSafe, Jev, OpenAI, Binance, or other provider request.

| Term | Meaning | Owner |
|---|---|---|
| **Observation** | One point-in-time evaluation identified by a deterministic ID. | Market OS |
| **Evidence packet** | Immutable, hashed inputs that were available by the observation decision time. | Market OS |
| **Candidate hypothesis** | A bounded claim produced by a deterministic or numerical engine, with explicit probability semantics. | Candidate engine |
| **Assessment probability** | Jev probability over labels in its assessment question. | Jev, validated by the adapter |
| **Market-outcome probability** | Calibrated estimate of a specified future event, such as P(return_5m > 0). | Market OS calibrator |
| **Calibration** | Mapping fitted on an allowed chronological range from scores to observed target frequencies. | Market OS |
| **Signal** | Deterministic policy result such as LONG_SPOT, REDUCE_SPOT, or HOLD. | Market OS policy |
| **Paper intent** | Risk-approved request for a virtual action. | Market OS risk/paper layer |
| **Abstention** | Deliberate refusal because the packet or response is insufficient for the requested assessment. | Jev or Market OS gate |

The words probability, confidence, score, and quality always name their object
and semantics. A concentrated Choice distribution is not a measured
future-return probability, economic edge, or permission to act.

## 3. Evidence-packet input contract

The packet artifact schema is `market-os.evidence-packet.v1` under the
`market-os.jev-processing.v1` governance contract. It is an internal Market OS
application artifact, not a TypeSafe wire version. Market OS creates the packet
only after validating source data and computing deterministic fields. It then
serializes, hashes, and persists the immutable packet before optional inference.
The JSON blocks in Sections 3.1, 3.2, and 4 are schema sketches: angle-bracket
values, empty collections, and null alternative fields are placeholders, not
complete valid instances. The invariants and typed meanings below define the
valid instances.

### 3.1 Required packet shape

~~~json
{
  "schema": "market-os.evidence-packet.v1",
  "observation_id": "<deterministic-id>",
  "task": {
    "question_id": "btc_evidence_assessment.v1",
    "question_version": "<pinned-question-version>",
    "assessment_configuration_id": "<pinned-configuration-id>",
    "assessment_configuration_version": "<pinned-configuration-version>",
    "assessment_target": "evidence_support|agreement_contradiction|abstention",
    "outcome_horizon_seconds": 300
  },
  "market": {"venue": "binance", "market_type": "spot", "symbol": "BTCUSDT", "interval": "1m"},
  "decision_eligible_at_ms": 0,
  "packet_available_at_ms": 0,
  "packet_ready_at_ms": 0,
  "fresh_until_ms": 0,
  "dataset_revision": "<B1-revision>",
  "feature_version": "btc.b2.features.v1",
  "target_definition_id": "<pinned-target-definition-id>",
  "target_version": "btc.b2.close-return-5m.v1",
  "input_fingerprint": "<sha256>",
  "candidates": [],
  "context": [],
  "quality": {
    "final_candles_only": true,
    "warmup_complete": true,
    "unresolved_gaps": false,
    "stale": false,
    "source_status": "valid"
  },
  "provenance": {
    "source_refs": [],
    "code_revision": "<revision>",
    "feature_fingerprint": "<sha256>",
    "created_at_ms": 0
  }
}
~~~

Required invariants:

1. `decision_eligible_at_ms` is the existing B2/B3 source/feature eligibility
   clock at which point-in-time and quality gates pass. Every required source or
   feature has availability no later than this time.
2. `packet_available_at_ms` is the latest required source, feature, or context
   availability. `packet_ready_at_ms` is at or after that time: it is recorded
   only after all required candidate computations, candidate validation, canonical
   serialization, and packet fingerprint hashing complete. Every source and
   candidate availability and `decision_eligible_at_ms` are `<=
   packet_ready_at_ms`, and `packet_ready_at_ms` is `<= request_started_at_ms`.
   `fresh_until_ms` is explicit and is not inferred from a response timestamp.
3. Target-definition identity may be present for point-in-time lineage through
   `target_definition_id` and `target_version`. Realized labels, future target
   references, future returns, fills, account state, target-derived fields, and
   B2's future-derived `target_fingerprint` are prohibited in the packet and in
   the provider request projection. B2/B3 join the packet to those outcomes only
   in a separate offline evaluation artifact after the outcome becomes
   available; the immutable packet is never amended with the outcome.
4. `input_fingerprint` is the packet fingerprint. It is the SHA-256 of the
   deterministic canonical serialization of a fingerprint projection that
   excludes the `input_fingerprint` field itself and all realized or future
   target fields. The projection includes the packet schema identity, packet
   contents and source/candidate/context identities, question ID and version,
   target-definition ID and version, and assessment-configuration ID and
   version. Replay of the same projection uses the same canonical bytes and
   fingerprint; cache reuse additionally requires matching identity and
   freshness fields.
5. Each source reference records a dataset or document ID, content hash,
   publication or event time, first-observed time, retrieval or ingestion time,
   availability time, optional expiry or maximum age, and the transformation
   that produced the candidate. Source dependencies and duplicate or
   supersedes groups prevent derivative evidence from posing as independent
   corroboration.
6. Numeric values are finite and unit-bearing. Unknown values use explicit
   statuses, never zero, empty strings, or invented probabilities.
7. Context is optional and separately identified. Missing context is an
   experimental condition, not permission to substitute later material or
   unrecorded provider memory.
8. Packet order, serialization, and hashing are deterministic. Canonical bytes,
   the projection, and the resulting fingerprint are persisted before any
   provider boundary.

### 3.2 Candidate hypothesis record

~~~json
{
  "hypothesis_id": "<stable-id>",
  "type": "technical_analysis|mathematical|statistical_forecast|numerical_model|code_validation|data_quality|contextual_evidence",
  "claim": "<bounded, testable statement>",
  "target": "return_5m_positive|return_5m_non_positive|regime|data_valid|context_support",
  "outcome_space": ["non_positive", "positive"],
  "direction": "up|down|flat|support|contradict|unknown",
  "value_kind": "calibrated_probability_distribution|uncalibrated_score|empirical_frequency|validation_result",
  "calibrated_probability_distribution": {"probability_distribution": {"non_positive": 0.48, "positive": 0.52}},
  "uncalibrated_score": null,
  "empirical_frequency": null,
  "validation_result": null,
  "event_definition": "return_5m > 0",
  "conditioning_set": [],
  "calibration_id": "<pinned-calibrator>",
  "calibration_status": "calibrated",
  "horizon_seconds": 300,
  "as_of_ms": 0,
  "available_at_ms": 0,
  "fresh_until_ms": 0,
  "estimator_or_model_id": "<pinned-estimator-or-model>",
  "training_range": {"start_ms": 0, "end_ms": 0},
  "source_lineage": ["<source-ref>"],
  "feature_lineage": ["<feature-ref>"],
  "engine_id": "<pinned-engine>",
  "engine_version": "<pinned-version>",
  "evidence_refs": ["<source-ref>"],
  "quality": "verified|provisional|degraded|invalid"
}
~~~

Candidate types have distinct meanings:

- **Technical analysis:** deterministic indicators and rule results. An
  indicator or rule truth value is not a probability; a historical conditional
  frequency remains an empirical frequency unless a separate calibration
  contract promotes it to a target-specific probability distribution.
- **Mathematical:** a result from a defined mathematical transformation or
  model, with assumptions, units, and input lineage. A formula output is not a
  probability unless it defines and estimates an event distribution.
- **Statistical forecast:** a distribution or event estimate from a pinned
  statistical procedure, with training range and calibration identity.
- **Numerical model:** output from a reproducible model such as a future
  LightGBM arm. Raw model scores remain uncalibrated until Market OS fits and
  records a calibrator.
- **Code validation:** deterministic assertion about schema, continuity, units,
  or implementation invariants. It can gate evidence but is not a market
  probability or price forecast.
- **Data quality:** freshness, gap, stale, outlier, or availability evidence.
  A failed quality candidate gates the packet rather than becoming directional
  evidence.
- **Contextual evidence:** timestamped external or retrieved material whose
  publication and availability times are independently recorded.

The four tagged value kinds are disjoint and exactly one corresponding field is
populated. Only `calibrated_probability_distribution` may contain a field named
`probability_distribution`; it is a target-specific distribution with finite
values in [0, 1] that covers exactly its declared outcome space and sums to one
within a versioned tolerance. `uncalibrated_score` is a score and must never be
stored in a field named `probability`; `empirical_frequency` is an observed rate
with its sample and range metadata; `validation_result` is a schema, quality, or
implementation judgment. Technical indicators, rule truth values, formula
outputs, and model scores are not automatically probabilities.

Every candidate claiming P(return_5m > 0) must explicitly provide the event
definition, horizon, conditioning set, outcome space, observation/as-of time,
estimator or model identity, training or fit range, calibration identity or an
explicit uncalibrated status, and source and feature lineage. A source-
uncalibrated score may be ranked or assessed but cannot be reported as a market
probability. A score, indicator, rule truth value, formula output, or model score
must remain in its tagged score/value field even when its numeric value lies in
[0, 1].

The packet's `calibrated_probability_distribution` is distinct from an assessment
probability returned by a typed Jev primitive. The latter remains under
`assessment_probabilities` in the output and is never silently promoted to a
market-outcome probability.

### 3.3 Timestamp mapping

The serialized `_at_ms` fields below are the artifact form of the existing B2/B3
timestamp vocabulary. They have this ordering and these uses:

| Concept | Canonical field and exact meaning | Ordering and use |
|---|---|---|
| Source availability | B2 `availability_timestamp` (with canonical `_ms` form in this artifact) on each source, feature, or context reference: the first time that item was available to Market OS for the observation | Every required item is `<= decision_eligible_at_ms`; use for point-in-time leakage checks and the packet's `packet_available_at_ms` maximum. |
| Decision eligibility | `decision_eligible_at` / `decision_eligible_at_ms`: the existing B2/B3 point-in-time source/feature eligibility clock | Every required source/feature availability is `<=` this time. Use for point-in-time leakage checks and signal eligibility. |
| Packet availability | `packet_available_at_ms`: the maximum availability of required packet inputs before candidate computation | `packet_available_at_ms <= decision_eligible_at_ms <= packet_ready_at_ms`. Use for input freshness and leakage evidence. |
| Packet ready | `packet_ready_at_ms`: after candidate computation, validation, canonical serialization, and packet hashing complete | `packet_ready_at_ms <= request_started_at_ms`. Use as the provider-boundary gate and packet cache point. |
| Request start | `request_started_at` / `request_started_at_ms`: when an optional provider request begins | `request_started_at_ms >= packet_ready_at_ms`. Use the interval to response receipt for provider latency. |
| Response received | `response_received_at` / `response_received_at_ms`: when provider response bytes are received | `response_received_at_ms >= request_started_at_ms`. Use with request start for provider latency. |
| Response available after validation | `available_at` / `available_at_ms`: when the normalized assessment is available after schema, identity, provenance, and freshness validation | `available_at_ms >= response_received_at_ms`; B3 recorded fixtures set `available_at == response_received_at`. Use for end-to-end latency and assessment freshness. |
| Freshness deadline or expiry | `fresh_until_ms` for packet input and `expires_at_ms` for the assessment: the explicit latest permitted use time | The relevant available time must be `<=` its deadline. Use for freshness and signal eligibility; never infer it from receipt time. B3's `response_deadline_ms` remains a duration budget, not a freshness timestamp. |

The packet and assessment are signal-eligible only when their decision,
availability, validity, and freshness checks pass at the actual use time. No
timestamp is a proxy for a future label or outcome. Cache reuse requires
matching packet/response fingerprints, provider/model/question identities,
schema versions, and the relevant freshness fields; a newer response does not
make older packet inputs fresh. Provider latency is measured from request start
to receipt; end-to-end latency is measured from B2/B3 decision eligibility to
validated assessment availability. The assessment inherits
`decision_eligible_at_ms` from its referenced packet through `observation_id` and
`packet_fingerprint`; it does not create a second eligibility clock.

## 4. Typed Jev output contract

The adapter normalizes a provider response into a versioned internal record.
The current local connectivity contract records provider/model/version,
request and response fingerprints, timestamps, failures, abstentions, usage,
and cost status. It separately requires an explicit live-probe gate,
paper-only mode, a pinned model, one request, zero retries, and the configured
spend ceiling. This design does not authorize that gate or a live request.

~~~json
{
  "schema": "market-os.jev-assessment.v1",
  "assessment_id": "<deterministic-id>",
  "observation_id": "<same-as-packet>",
  "status": "schema_invalid|unsupported|internally_inconsistent|stale|unavailable|abstained|usable",
  "provider": "typesafe",
  "model": "jev",
  "model_version": "<explicit-pinned-version>",
  "question_version": "<same-as-packet>",
  "request_fingerprint": "<sha256>",
  "packet_fingerprint": "<sha256>",
  "packet_ready_at_ms": null,
  "response_fingerprint": "<sha256-or-null>",
  "request_started_at_ms": null,
  "response_received_at_ms": null,
  "available_at_ms": null,
  "expires_at_ms": null,
  "assessment": {
    "selected_label": null,
    "per_hypothesis": [
      {
        "hypothesis_id": "<packet-hypothesis-id>",
        "support": {"label": "supported|mixed|unsupported|unknown", "probability": 0.0, "evidence_refs": []},
        "agreement": {"label": "strong|moderate|mixed|none|unknown", "evidence_refs": []},
        "contradiction": {"label": "strong|moderate|mixed|none|unknown", "conflicting_hypothesis_ids": []},
        "market_os_gates": {
          "consistency": {"label": "consistent|inconsistent|unknown", "reason_codes": []},
          "freshness": {"label": "fresh|aging|stale|unknown", "reason_codes": []},
          "provenance": {"label": "complete|incomplete|unknown", "reason_codes": []},
          "evidence_quality": {"label": "high|medium|low|unknown", "evidence_refs": []}
        }
      }
    ],
    "ranked_hypotheses": [],
    "ranking_order": "descending_support",
    "ranking_tie_rule": "equal rank for indistinguishable support; hypothesis_id ascending within ties",
    "ranking_unavailable_behavior": "empty_for_non_usable_terminal_status; explicit_id_sets_for_usable",
    "unavailable_hypothesis_ids": [],
    "abstaining_hypothesis_ids": [],
    "evidence_disagreement": {"present": false, "hypothesis_ids": [], "evidence_refs": []},
    "abstain": false,
    "abstain_reason": null,
    "assessment_probabilities": {},
    "choice_confidence": null,
    "concentration": null
  },
  "failure": null,
  "usage": "observed|unknown-not-observed-offline",
  "cost": "observed|unknown-not-observed-offline"
}
~~~

`request_started_at_ms` must be at or after `packet_ready_at_ms` when a request
is made. `response_received_at_ms` must be at or after request start, and
`available_at_ms` must be at or after response receipt after validation. The
provider latency is `response_received_at_ms - request_started_at_ms`; the
end-to-end latency is `available_at_ms - decision_eligible_at_ms`. Freshness is
evaluated at the actual use time against the relevant explicit expiry, not only
at response receipt. B3 recorded fixtures preserve `available_at ==
response_received_at`.

`status` is the terminal response status for the normalized artifact. Its
taxonomy and precedence are defined in Section 14; it is separate from the
Jev question results `support`, `agreement`, `contradiction`, and abstention,
plus `evidence_disagreement` and `ranking`. `market_os_gates` are computed and
owned deterministically by Market OS and are not answers supplied by Jev.
`choice_confidence` and `concentration` are diagnostic fields only. A valid
concentrated Choice or Score response remains `usable` and records
concentration separately. Only a separately versioned and calibrated Market OS
policy may turn concentration into `HOLD`; `overconfident` is not a terminal
status and must never cause adapter rejection.

Assessment dimensions are typed labels with bounded optional scores and
reason or evidence references where the question supports them. Ranking is
deterministic: it contains stable packet hypothesis IDs only, declares its
ordering direction, and uses either an explicit rank or a complete ordered list.
Equal support receives the same rank and `hypothesis_id` sorts ascending
lexicographically only as a stable display order within that tie. For a
`usable` assessment, every packet hypothesis ID appears exactly once across
`ranked_hypotheses`, `unavailable_hypothesis_ids`, and
`abstaining_hypothesis_ids`; unknown, duplicate, or missing IDs fail validation.
For every terminal status other than `usable`, `ranked_hypotheses` and both
explicit ID sets are empty. No order is inferred from a free-form explanation,
and no free-form ranking content may influence calibration, fusion, signal,
sizing, risk, or execution paths.

`assessment_probabilities` is a distribution over labels in the declared
question. A coherent assessment instance includes an explicit
`selected_label` (or equivalent primitive answer) alongside that distribution;
`support.probability` (when present) is the same typed question probability,
meaning `P(label = supported | supplied packet, hypothesis)` when the support
question uses the `supported` label (and analogously for another explicitly
declared label). It is never a market-outcome probability or an uncalibrated
score. It must
be finite, bounded, sum to one within the contract tolerance,
and have a selected label consistent with the distribution when required by the
primitive. It is not p_up, p_down, expected return, or a risk limit. Any
provider score remains in a score-named field and is never copied into a field
named probability.
`choice_confidence` is retained only when the typed primitive supplies it; it is
a descriptive concentration property of the answer distribution and is never
treated as correctness or market probability. Tied maximum choices are represented as
ambiguous or abstaining under the question contract, not resolved from object
field order.

The adapter classifies malformed provider wire/schema output as
`schema_invalid`, unsupported providers, model versions, questions, option sets,
or primitives as `unsupported`, and selected-label, probability, timestamp,
identity, or provenance invariant violations as `internally_inconsistent`. It
preserves the raw typed result, or a permitted redacted representation plus its
hash. Typed shape is not truth.

## 5. Evaluator dimension semantics

The concepts remain separate. A packet can be fresh but contradictory,
consistent but weakly supported, or high quality but insufficient to answer.
Under ADR-0022, B3.1 asks Jev only for semantic evidence support, agreement or
contradiction, and abstention. Consistency, freshness, provenance, and evidence
quality are deterministic Market OS gates; uncertainty is not an additional
frozen Jev question.

| Dimension | Meaning | Required basis |
|---|---|---|
| **Agreement** | Degree to which independent candidates support the same stated claim. | Normalized target, direction, horizon, and source identity. Correlated duplicate engines do not count as independent support. |
| **Contradiction** | Degree to which candidates make incompatible claims for the same event and horizon. | Same event, direction, units, and time window. Different targets are disagreement, not automatically contradiction. |
| **Consistency** | Whether claims, probabilities, timestamps, units, and provenance satisfy cross-field rules. | Deterministic Market OS schema and invariant checks. |
| **Uncertainty** | Remaining uncertainty from incomplete evidence, disagreement, unknown calibration, or temporal risk. | A separate Market OS or later study measure; never Choice concentration alone. |
| **Freshness** | Whether required evidence remains within its explicit window at decision time. | Deterministic Market OS gate using packet_available_at_ms, available_at_ms, fresh_until_ms, expires_at_ms, and decision_eligible_at_ms. |
| **Abstention** | Deliberate refusal when the question is not answerable or is unsafe to use. | Terminal status and reason code; no silent neutral probability. |
| **Evidence quality** | Completeness, provenance, temporal validity, independence, and validation status. | Deterministic Market OS quality checks and source references. |
| **Ranking** | Ordered candidates by support for the declared assessment. | Stable IDs, direction, ties, and unavailable states are explicit; explanations are non-operative. |

Agreement is not accuracy. Contradiction detection is not proof that either
side is correct. Freshness is not recency alone: a new response about stale
inputs remains stale. High evidence quality does not imply a high market
probability.

## 6. Assessment probability versus market-outcome probability

The following objects stay separate in storage, reports, and code:

1. `P(agreement | supplied packet)` answers whether candidates support one
   another under the Jev question.
2. `P(supported | supplied evidence)` answers the initial semantic evidence
   support question; agreement versus contradiction and abstention are separate
   questions.
3. The primary market classification target is positive versus non-positive
   five-minute log return under B2's existing return definition. Its event is
   `Y = 1[ln(C[t+5]/C[t]) > 0]`; zero return is in the non-positive class.
4. `P(net executable return > 0 | state, post-decision price, delay, fees,
   slippage)` is a separate economic-evaluation target and is not the primary
   classification target.

Only a Market OS probability calibrated for the matching target using a
chronologically valid procedure may be evaluated for a corresponding policy.
A Jev assessment probability is over its declared question labels. It is never
relabeled as a market-return probability. A Jev assessment may be a feature to a
downstream calibrator or fusion model, but that mapping must be learned from
outcomes unavailable to the packet and recorded with a calibration fingerprint.
No provider confidence field authorizes relabeling it as `P(Y=1)`.

## 7. Baseline and incremental experiments

The new arms must not overwrite B3's existing E1/E2 meanings. C2 and
C2-control require additional context, which is deferred by ADR-0022; they are
future conceptual arms and are not part of the frozen B3.1 protocol.

| Arm | Inputs | Purpose |
|---|---|---|
| **N0 numerical-only** | X_t and deterministic quality fields | Naive, statistical, and later numerical-model controls without Jev. |
| **J1 same-evidence Jev evaluator** | The same X_t packet plus Jev assessment | Test whether Jev representation adds value without new information. |
| **C2 Jev with additional timestamped context** | X_t plus timestamped context Z_t, assessed by Jev | Test semantic handling of additional information. |
| **C2-control same context without Jev representation** | X_t plus the same Z_t through a non-Jev representation | Separate Jev value from the value of receiving Z_t. |
| **F3 calibrated fusion** | Calibrated N0 plus eligible J1/C2 assessments and quality fields | Test a frozen downstream fusion policy and post-cost utility. |

These are five named arms in four conceptual categories: N0 numerical-only;
J1 same-evidence Jev evaluator; the additional-context category containing C2
and C2-control; and F3 calibrated fusion. C2 and C2-control use the same
timestamped context and differ in whether Jev represents it.

Every arm shares observation IDs, target definition, chronological boundaries,
purge/embargo rules, held-out periods, cost assumptions, and reporting. J1 is
compared with N0 on the same usable rows. C2 is compared with N0 and the
same-context control. F3 weights and thresholds are never selected on test
outcomes.

The existing B3 result is preserved without reinterpretation: E1 is the
numerical B2 conditional-rate arm; E2 uses the same numerical input plus one
recorded typed Jev assessment. B3 remains offline, recorded-response-only, has
no leakage-safe labels in its shipped fixture, and is **not promoted**. B3.1
extends this research line with five new named arms; it does not rename, replace,
or rewrite B3 E1/E2. N0 is a future numerical-only baseline, not a replacement
for B3 E1, and J1 is a future same-evidence study, not a rewrite of B3 E2.

| Existing B3 identity | B3.1 relationship |
|---|---|
| E1: numerical B2 conditional-rate arm | Preserved unchanged; N0 is a future numerical-only baseline and does not replace E1. |
| E2: same numerical input plus one recorded typed Jev assessment | Preserved unchanged; J1 is a future same-evidence study and does not rewrite E2. C2/C2-control and F3 are additional arms. |
| Offline recorded-response-only, not promoted | Remains the B3 boundary; B3.1 requires a separately approved study and does not promote B3. |

## 8. Chronological train, calibration, and test protocol

1. Freeze dataset revision, feature/target versions, question version,
   provider/model version, arm definitions, cost assumptions, and metrics
   before reading test outcomes.
2. Sort observations by decision time. Use an earlier train range, a later
   calibration range, and a final test range. Validation may be nested inside
   training, but cannot cross calibration or test boundaries.
3. Purge observations whose five-minute target overlaps a split boundary and
   embargo the next five minutes, retaining B2/B3 rules.
4. Fit numerical models, normalizers, fusion weights, thresholds, and
   calibrators only on permitted earlier ranges. Fit calibration on calibration
   rows; never tune on test rows.
5. Apply frozen transformations to the test range once per preregistered
   evaluation. Report the identical matched test intersection for arms with
   different coverage.
6. Repeat in rolling or expanding walk-forward windows. Keep one final
   untouched period for promotion review.
7. Persist split, purge, embargo, calibration, and evaluation fingerprints
   with every prediction and report.

## 9. Leakage, contamination, drift, and provenance

### 9.1 Leakage controls

- Keep future labels and target returns in an offline store; reject packets
  containing them.
- Enforce each source/feature available_at_ms <= decision_eligible_at_ms for
  every feature and context item. Publication time is not retrieval time.
- Do not use revised historical text, later corrections, or future summaries
  unless the experiment explicitly models historical availability.
- Fit imputation, normalization, feature selection, calibration, fusion, and
  abstention thresholds only on permitted ranges.
- Preserve unavailable, stale, malformed, and abstaining responses as missing
  outcomes. Never convert them into a favorable class.

### 9.2 Retrospective pretraining contamination

A provider may have learned from historical material after an observation time.
Local code cannot prove that absence. Therefore:

- record provider, explicit model version, question version, packet fingerprint,
  and evaluation date;
- distinguish retrospective replay from prospective shadow evaluation;
- do not claim a historical Jev replay is an uncontaminated simulation of what
  the model knew then;
- use prospective timestamped shadow data for deployable-information claims;
- treat a provider-version change as a new treatment and new benchmark.

### 9.3 Provider drift and provenance

Pin an explicit model version rather than a moving alias. Record resolved
provider identity, version, request/response fingerprints, latency, usage/cost
status, failure and abstention reasons, and lineage from B1 through B2 and the
packet. A cache is replay evidence only when identity and freshness fields
match. An unrecorded provider version is unavailable for the frozen arm.

## 10. Calibration and fusion

Calibration is a Market OS responsibility. For the frozen binary primary
target, B3.1's primary method is binary logistic (Platt) calibration. The
existing one-bin empirical method remains a weak baseline. Isotonic calibration
is unavailable unless a later preregistered sample threshold explicitly permits
it. Multiclass calibration is outside the frozen primary target.

Persist method, hyperparameters, fit range, sample count, target definition,
calibrator fingerprint, and fallback behavior. Reject calibration when labels
are unavailable or score and target semantics do not match; when calibration
cannot be fit, mark it unavailable instead of silently substituting another
method.

Fusion is deterministic Market OS code. The frozen primary method is a
regularized logistic model, fitted only on permitted training-range data with
properly separated base predictions. Missing or abstaining Jev results remain
explicit missing/abstaining inputs; they are never silently replaced with a
neutral probability. Any alternative method, treatment, threshold, and regime
or drift handling requires a separately preregistered decision.

## 11. Deterministic conversion from probability to signal

The signal policy consumes only calibrated, target-specific outputs and valid
quality metadata. A representative binary policy is:

~~~text
edge_up   = p_up * gain_up - (1 - p_up) * loss_down - fees - slippage - delay_cost
edge_down = p_down * gain_down - (1 - p_down) * loss_up - fees - slippage - delay_cost

if data is stale, invalid, unavailable, or the calibrator is not approved:
    HOLD
elif uncertainty or abstention policy blocks action:
    HOLD
elif edge_up >= open_threshold and p_up >= p_min:
    LONG_SPOT
elif edge_down >= reduce_threshold and p_down >= p_min:
    REDUCE_SPOT
else:
    HOLD
~~~

Actual thresholds, costs, hysteresis, cooldown, and minimum sample gates are
versioned and frozen before test evaluation. For a three-class target, p_flat
is explicit and may force HOLD; it is not silently folded into either side. A
Jev label, assessment probability, or confidence value alone cannot produce a
signal.

## 12. Signal, sizing, leverage, risk, and paper execution

These are separate contracts and state machines:

1. **Assessment:** Jev returns a typed record.
2. **Calibration:** Market OS maps eligible scores to target probabilities.
3. **Signal:** a deterministic policy chooses LONG_SPOT, REDUCE_SPOT, or HOLD.
4. **Position sizing:** deterministic portfolio policy chooses quantity from
   wallet state, price, volatility, and exposure limits; it may choose zero.
5. **Leverage:** unavailable in the Spot experiment.
6. **Risk approval:** Market OS checks freshness, concentration, turnover,
   drawdown, paper-mode permission, and all limits. Jev cannot approve or
   override this gate.
7. **Paper execution:** the virtual broker simulates fills, fees, slippage,
   delay, inventory, and ledger events; it has no live exchange transport.

Every rejected and no-action path records a reason and remains replayable.

## 13. Spot-first policy and separate perpetual requirements

The current experiment is Spot-only: no short inventory, margin, futures,
perpetuals, funding, or leverage. A Spot signal can buy, hold, reduce, or sell
owned inventory under paper risk policy.

A future futures/perpetual simulator requires a separate contract and evidence
gate covering at least: contract identity and multiplier; mark, index, and last
prices; funding timestamps/rates; initial and maintenance margin; isolated or
cross mode; liquidation and bankruptcy rules; fees/slippage; position mode;
short inventory; oracle/index outages; ADL assumptions; leverage caps;
margin-call timing; and a dedicated paper ledger. It must be compared with a
Spot control and cannot inherit Spot thresholds. x50/x100 is not a promotion
target.

## 14. Status, contradiction, and failure semantics

The normalized artifact has one terminal `status`; dimensions such as agreement,
evidence disagreement, contradiction, consistency, uncertainty, freshness,
evidence quality, and ranking remain independent assessment fields. Apply the
first matching status in this deterministic order:

1. **`schema_invalid`** — provider output is malformed or violates the declared
   wire/schema shape, required fields, primitive type, or value encoding.
2. **`unsupported`** — provider, model, question, version, option set, or
   primitive is outside the explicitly supported contract.
3. **`internally_inconsistent`** — selected label, probability distribution,
   timestamp ordering, identity, or provenance fields violate cross-field
   invariants despite being individually parseable.
4. **`stale`** — packet or response is outside its explicit permitted freshness
   window.
5. **`unavailable`** — timeout, response-duration budget (including B3's
   recorded `late` outcome), permission, provider, or transport failure prevents
   an on-time validated assessment. Preserve the source outcome and reason.
6. **`abstained`** — a valid explicit refusal to assess, with a reason code.
7. **`usable`** — a contract-valid assessment that may enter research evaluation.

This ordering resolves simultaneous conditions: malformed output is
`schema_invalid` even if it is also stale; an unsupported primitive is
`unsupported` even when its content disagrees with evidence; a selected label
that is inconsistent with its declared probability distribution is
`internally_inconsistent`. Valid independently sourced candidates may disagree
while the assessment remains `usable`; record `evidence_disagreement` as a
dimension, not a parser failure. Only `usable` can proceed to separately
approved calibration/fusion, and all signal, risk, sizing, and execution gates
still belong to Market OS.

High probability concentration or high `choice_confidence` is diagnostic, not a
terminal failure. A valid concentrated Choice or Score response remains
`usable` and records concentration separately. Only a separately versioned and
calibrated Market OS policy may turn concentration into `HOLD`; `overconfident`
is not a terminal status and must never cause adapter rejection.

| Condition | Terminal status | Signal consequence |
|---|---|---|
| Malformed/schema-invalid provider output | `schema_invalid` | Discard as assessment evidence; preserve error and fingerprint when available. |
| Unsupported provider/model/question/version/option set/primitive | `unsupported` | Do not use the assessment; preserve the unsupported reason. |
| Cross-field label, distribution, timestamp, identity, or provenance violation | `internally_inconsistent` | Do not use the assessment; preserve validation detail. |
| Stale packet or response | `stale` | No new Jev-dependent signal; record freshness failure. |
| Timeout, budget, permission, provider, or transport failure | `unavailable` | No Jev-dependent signal; numerical arm may continue only as its own approved arm. |
| Valid explicit refusal | `abstained` | No Jev-dependent signal; count coverage and selective metrics. |
| Valid independent candidates disagree | `usable` with `evidence_disagreement` dimension | Retain for research evaluation; disagreement is not parser failure. |
| Valid assessment, including concentrated output absent an approved blocker | `usable` | May enter research evaluation and separately approved downstream calibration/fusion. |

Free-form ranking explanations are never consumed by a signal, risk, sizing, or
execution path.

The fallback is a recorded no-Jev state, not an unannounced model, provider,
or cached answer. If a numerical-only policy continues, it is a separate arm
with its own paper permissions and audit record.

## 15. Metrics and reporting

Report by arm, chronological window, market regime, response status, and
matched test intersection. Point estimates alone are insufficient; use a
dependence-aware interval method such as block bootstrap when sample support
permits it.

### Evaluator and probability quality

- agreement and contradiction precision, recall, F1, and confusion matrix
  against a frozen adjudication rubric;
- consistency and evidence-quality classification accuracy;
- abstention coverage, selective risk, risk-coverage curve, and utility of
  abstaining on low-quality rows;
- Brier score, log loss, reliability diagrams, calibration slope/intercept,
  declared-bin ECE, and regime-conditional calibration for market probabilities;
- top-k support precision and pairwise ordering accuracy when ranking is tested.

### Operational quality

- validation and failure rates by reason;
- p50/p95/p99 latency from eligible packet to validated assessment;
- timeout rate, queue delay, cache hit rate, and provider/model stability;
- observed requests, input usage, cost, budget headroom, and
  unknown-not-observed-offline when fixtures are used;
- replay determinism, artifact hash integrity, provenance completeness, and
  packet-to-response lineage.

### Research and paper utility

- coverage and matched-row counts;
- directional accuracy, log loss, Brier score, and target-specific AUC only
  when target and sample support it;
- turnover, fees, spread/slippage, latency cost, exposure, inventory, realized
  and unrealized PnL, maximum drawdown, recovery, and return distribution;
- no-trade rate, rejected-risk rate, post-cost paper utility, and stability
  across chronological windows;
- comparison with N0 and same-context controls, intervals, and negative-result
  explanation.

No metric is an unsupported alpha claim. A positive point estimate without
leakage controls, uncertainty, costs, and prospective verification is not a
promotion result.

## 16. Explicit non-goals

This design provides no:

- Jev-controlled orders or Jev authority over a broker;
- live trading, authenticated exchange access, or real capital movement;
- automatic leverage or any derivative execution path;
- x50/x100 promotion or a claim that high leverage is safe;
- unsupported alpha, profitability, causality, or deployability claim;
- requirement that Jev generate free-form reasoning;
- replacement for deterministic validation, calibration, persistence, policy,
  risk, or execution code.

## 17. Compatibility and references

The design is grounded in:

- [TECH_DOCS.md](TECH_DOCS.md), especially Sections 6, 9, 11, and 13–19;
- [STACK.md](STACK.md), especially model scope, grounding, and ownership;
- [ADR-0015](docs/decisions/ADR-0015-btc-math-first-jev-experiment.md), which
  establishes the math-first experimental role;
- [ADR-0019](docs/decisions/ADR-0019-u3-b3-jev-experimental-boundary.md), which
  freezes B3's offline E1/E2 boundary and non-promotion decision;
- [ADR-0020](docs/decisions/ADR-0020-u3-api-connectivity-boundary.md), which
  governs the separate bounded connectivity probe;
- [U3/B3 report](docs/U3-B3-JEV-INCREMENTAL-BENCHMARK-REPORT.md);
- [API contracts](docs/api/contracts.md), including B2, B3, and U3 connectivity;
- [btc_b3.py](market_os/btc_b3.py) and
  [btc_connectivity.py](market_os/btc_connectivity.py);
- [TypeSafe/Jev research note](docs/research/typesafe-jev-u3-b3.md), the local
  record of first-party facts used by B3;
- [B1.1 readiness report](docs/U3-B1-HISTORICAL-READINESS-REPORT.md) and
  [B1.1 ADR](docs/decisions/ADR-0021-btc-historical-readiness-gate.md);
- [U3/API connectivity report](docs/U3-API-CONNECTIVITY-REPORT.md) and
  [connectivity evidence](docs/evidence/u3-api-connectivity.json), which keep
  separately approved probe activity distinct from B3 and B1.1.

The TypeSafe claims here are intentionally narrow: the repository records Jev
as a typed System One model; B3 uses a versioned Choice shape with probabilities
and confidence; identity, fingerprints, timestamps, failures, abstentions,
usage, and cost status are recorded; and B3 uses deterministic fixtures only.
Current provider behavior, pricing, limits, and availability require a fresh
review before any future integration. This design and B3 make no TypeSafe
request.

ADR-0015 contains historical wording that calls Jev the primary experimental
model candidate. This document refines the proposed role to evidence evaluator,
not primary market forecaster; it does not rewrite that accepted record or
change B3. A later implementation milestone should update the decision record
if this role is adopted.

## 18. Frozen decisions and deferred choices

ADR-0022 freezes the B3.1 decisions below. The freeze does not authorize an
implementation, provider request, acquisition, or study.

- Jev is an advisory typed evidence evaluator. Initial questions cover evidence
  support, agreement versus contradiction, and abstention. Consistency,
  freshness, provenance, and evidence-quality gates stay deterministic in
  Market OS. Regime questions and additional context are deferred.
- Preserve B2's five-minute log-return definition. The primary classification
  is positive versus non-positive return. Executable net return after
  post-decision pricing, delay, fees, and slippage is a separate economic
  target. Jev assessment probabilities are never market-return probabilities.
- Use binary logistic/Platt calibration and regularized logistic fusion as the
  primary methods. One-bin calibration is a weak baseline. Isotonic is
  unavailable unless a later preregistered sample threshold permits it. Missing
  and abstaining Jev results stay explicit.
- B3.1 implementation and evaluation are recorded-fixture-only. No new Jev or
  TypeSafe request, credential, provider adapter activation, or context egress
  is authorized. Provider budget, version, retention, redaction, and latency
  require separate approval.
- B3.1 scope is BTCUSDT Spot-only: no short inventory, margin, leverage,
  futures, perpetuals, funding, or x50/x100 assumptions. Derivative work needs
  a new contract, ledger, risk gate, and human decision.
- A 90-day prospective shadow period is only a future proposal. It requires a
  sufficient approved dataset, preregistered power/sample and regime-coverage
  rules, frozen costs and latency assumptions, and separate approval; it is
  not an active or approved study.

The following remain deferred to any separately approved implementation or
study decision:

1. Exact packet, assessment, question, and configuration version identifiers;
   exact question wording and any provider-specific primitive mapping.
2. Dataset sufficiency, power/sample thresholds, regime coverage, and a numeric
   sample threshold that could permit isotonic calibration.
3. Fusion features and missingness encoding, thresholds, uncertainty policy,
   and other preregistered evaluation details.
4. Provider/model version and capability verification, request budget, cost,
   latency ceiling, permitted source classes, redaction, retention, and deletion
   policy.
5. Whether and when to propose a prospective shadow study, plus its duration,
   acceptance criteria, frozen cost/latency assumptions, and human review.
6. Whether derivatives are permanently excluded or merit a separate future
   contract and simulator.

## 19. Proposed contract version

Overall processing/governance: `market-os.jev-processing.v1`

Immutable packet artifact: `market-os.evidence-packet.v1`
Normalized assessment artifact: `market-os.jev-assessment.v1`

These are proposed internal Market OS contracts. They are not TypeSafe wire
versions and do not authorize a network request.

## 20. Future B3.1 study proposal

B3.1 is a frozen offline protocol decision, not an approved implementation,
dataset acquisition, or active study. A separately approved successor study may
propose the N0 and J1 arms; C2 and C2-control would additionally require
separate approval for timestamped context and its egress. Such a study must
preserve B3's purge/embargo and lineage rules and fit calibration and fusion
only on permitted ranges. It requires a sufficient approved dataset and a
separately approved plan. A 90-day prospective shadow period is only a future
proposal and requires preregistered power/sample and regime-coverage rules,
frozen costs and latency assumptions, and separate approval. A negative or
inconclusive result remains a valid research outcome.

## 21. Migration notes: existing B3 remains valid

- Keep market_os/btc_b3.py, B3_API_VERSION, B3_RUN_SCHEMA, the recorded fixture
  schema, and existing E1/E2 semantics unchanged.
- Keep B3 context_mode equal to none, transport_mode equal to
  offline-recorded-only, pinned recorded model identity, one-bin calibration,
  chronological split, purge, embargo, explicit failure/abstention outcomes,
  artifact hashes, and replay fingerprints.
- Treat `market-os.jev-processing.v1` as the future processing/governance
  contract, with `market-os.evidence-packet.v1` and
  `market-os.jev-assessment.v1` as its distinct internal artifacts; these do not
  reinterpret B3 Choice probability or confidence.
- B3 unavailable classification and calibration metrics remain unavailable
  because the shipped fixture has no leakage-safe labels. They are not replaced
  by design estimates.
- A future adapter may translate a validated B3-shaped recorded assessment into
  the proposed normalized record only with an explicit mapping and new
  fingerprints. No migration changes execution authority.

## 22. Acceptance criteria for separately approved work

The current B3.1 freeze authorizes no implementation or evaluation. A future
implementation ticket or successor-study proposal requires separate approval.
For any offline implementation review, require:

- packet schema, candidate taxonomy, question versions, and output schema are
  approved by a human owner;
- deterministic packet validation rejects future, stale, malformed, missing, or
  provenance-incomplete inputs before an optional provider boundary;
- every candidate probability has explicit outcome-space semantics and a
  target-specific calibration plan;
- deterministic candidate rankings define tie behavior and reference only
  packet hypothesis IDs;
- provider/model/version, request and response fingerprints, timestamps,
  failures, abstentions, usage, cost status, and lineage are persisted;
- fixture tests cover valid, schema-invalid, unsupported, internally
  inconsistent, stale, evidence-disagreement, unavailable, and abstaining
  responses with zero provider requests; concentrated output is covered as a
  diagnostic case and is not rejected solely for concentration;
- offline conformance verifies that no TypeSafe, Binance, Jev, or other
  provider transport is called;
- chronological train/calibration/test splits, target-overlap purge, and
  embargo are frozen and replay-checked;
- N0 and J1 are defined before test data is inspected. C2 and C2-control remain
  deferred because they require additional context and separate egress approval;
  include them only in a separately approved successor protocol;
- calibration, fusion, signal thresholds, fees, slippage, latency, and
  uncertainty rules are fitted only on permitted ranges;
- signal, position sizing, leverage, risk approval, and paper execution remain
  separate Market OS contracts, with no Jev execution authority;
- Spot-only paper behavior is verified and any perpetual simulator has a
  separate contract, ledger, and risk gate;
- metrics include evaluator quality, calibration, contradiction detection,
  abstention, latency, cost, stability, turnover, drawdown, and paper utility;
- provenance, provider drift, retrospective contamination, privacy, and
  retention decisions are recorded;
- no live provider request, credential, Binance acquisition, OpenAI request,
  trade, or approved-policy.json change is required to pass the offline gate.

Completion of these criteria authorizes only a separately reviewed offline
implementation proposal. C2/context egress and any prospective study require
their own approval; no criterion authorizes a provider request, acquisition,
or trading deployment.
