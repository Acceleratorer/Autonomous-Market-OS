# STACK.md

## Purpose

This project is a trading research system in which the model is one optional capability inside a deterministic trading platform. The model must improve explanation and research usability without becoming the authority for risk, execution, or unsupported claims.

## Current architecture

```text
Retrieved documents
        ↓
LightRAG passages
        ↓
Deterministic evidence and claims
        ↓
Optional model summary
        ↓
Citation and grounding gate
        ↓
Research report
        ↓
Backtest and paper order plan
```

### Responsibilities

- **Market OS** owns orchestration, persistence, risk checks, paper orders, and audit events.
- **LightRAG** retrieves document evidence and passages.
- **Vibe-Trading** runs the deterministic backtest.
- **Deterministic synthesis** produces a usable result without a model or network.
- **The model** is optional and produces a richer, citation-preserving research summary.
- **The OpenAI adapter** is isolated behind a small interface and currently targets `gpt-6.1-sol`.

## Model scope

The model should help with:

- Clear summaries
- Combining related evidence
- Explaining risks and assumptions
- Labeling differences between sources
- Explaining backtest results
- Answering user questions about the research

The model must not decide:

- Whether a trade is safe
- Whether a broker order is allowed
- Position limits or risk limits
- Account permissions
- Live execution
- Whether unsupported claims are acceptable

These decisions remain in deterministic Market OS code.

## Grounding and safety rules

- Every model claim must resolve to stored passages and documents.
- Unsupported model output is rejected or explicitly labeled.
- Citation and grounding checks run before a report is exposed to users.
- If the model fails, the deterministic summary remains available.
- The model cannot place orders or authorize live trading.
- Redaction, retry, timeout, spend-limit, parsing, citation, and grounding behavior are covered by recorded-response tests.

## Current implementation status

- Offline model preparation is complete (M2.8).
- No real model request has been made yet.
- M2.9 received the exact approval, but execution was safely blocked because `OPENAI_API_KEY` was unavailable through the approved secret boundary. No reservation was consumed and no request was made.
- Recorded-response tests already verify parsing, citations, grounding, retries, timeouts, spend limits, redaction, and fallback.

## Recommended model strategy

### Stage 1: Current

Use one optional model for citation-preserving research summaries.

### Stage 2: Next

Supply a credential only through the approved secret boundary, then make at most one separately approved synthetic request and measure real model quality, latency, cost, and failure behavior.

### Stage 3: Later, only if benchmarks justify it

Consider separate roles such as:

- Research summarizer
- Risk explanation assistant
- Strategy analyst
- Portfolio review assistant

Do not start with many agents or many models. One reliable model behind strict evidence gates is easier to test and safer to operate.

## Open decisions

1. Is the model limited to research explanation, or may it also generate strategy ideas?
2. Should the first live test use OpenAI only, or compare OpenAI with another provider?
3. How much retrieved document text may leave the machine?
4. What latency and monthly cost are acceptable?
5. Should model summaries be stored, or only redacted evidence and fingerprints?
6. What quality threshold must a model pass before users see it by default?

## Working recommendation

Keep the current architecture:

> Deterministic trading and evidence core, optional model for grounded explanation, strict fallback, and no model authority over execution.

This document is a planning and context artifact. It describes the intended model boundary and current status; it is not authorization to make a real model request or enable live trading.

## Context for future discussions

When discussing model choices, preserve these constraints:

- The deterministic system must remain useful without a model or network.
- Model output must remain grounded in retrieved evidence.
- Risk and execution authority stay outside the model.
- Changes should be evaluated against quality, latency, cost, privacy, and failure behavior.
- Prefer the smallest architecture that satisfies the evidence and safety requirements.

## BTC paper experiment B0 status (2026-10-18)

- B0 adds an isolated, versioned BTCUSDT Spot offline contract/replay module and
  a read-only fixture replay CLI. It does not change the equities workflow or
  the model-summary lane.
- No Binance/network call, Jev/OpenAI request, model credential, broker,
  training, or live execution path is part of B0.
- See `docs/B0-BTC-PAPER-REPLAY-REPORT.md` and
  `docs/evidence/b0-btc-paper-replay.json` for actual timestamp, label,
  lineage, and verification details.
- Exact next milestone: **B1 historical closed-candle ingestion and canonical
  local Parquet/DuckDB dataset**, after source authorization and network policy
  are separately resolved.
