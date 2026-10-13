# HKUDS Fusion Product Vision

## Recommended flagship: HKUDS Autonomous Market OS

A multi-agent trading operating system that researches markets, debates strategies, backtests ideas, manages paper/live execution with approval controls, learns from outcomes, and exposes the same capabilities through CLI, web, desktop/mobile app, chat channels, and generated reports/media.

The product should be one platform with domain plugins. The existing repositories become owned capabilities behind contracts; they should not all be copied into one package.

## Product loop

```text
User goal or scheduled policy
  -> planner and agent team
  -> multimodal market/document retrieval
  -> research and signal generation
  -> backtest and risk checks
  -> approval or policy gate
  -> paper/live execution
  -> monitoring and event log
  -> evaluation, memory, and strategy improvement
```

## How the portfolio contributes

| Capability | Source projects | Product use |
|---|---|---|
| Agent runtime, sessions, tools, skills, channels | `OpenHarness`, `nanobot`, `DeepCode` | Common execution kernel; choose one owner and adapt the others |
| Broker and market research | `Vibe-Trading`, `AI-Trader` | Backtesting, market data, signals, social intelligence, experiments |
| Knowledge retrieval | `LightRAG`, `RAG-Anything`, `MiniRAG` | SEC filings, news, research papers, charts, PDFs, earnings calls |
| Tool access | `CLI-Anything` | Agent-controlled broker, spreadsheet, browser, charting, and analysis tools |
| Economic evaluation | `ClawWork` | Measure cost, quality, profitability, and agent survival |
| Education and strategy coaching | `DeepTutor` | Explain trades, teach users, run guided strategy improvement |
| Research-to-presentation | `Paper2Slides` | Generate investor reports, strategy reviews, and briefings |
| Story/video output | `ViMax` | Produce market explainers, daily recaps, and training media |

## Three product ideas

### 1. Autonomous Market OS — recommended

A serious trading and research platform. It combines the strongest company assets into one coherent workflow and can monetize through subscriptions, managed research, and execution tooling.

Core differentiators:

- Agent teams with explicit roles: researcher, quant, risk officer, executor, reviewer.
- Every claim and trade linked to source evidence, model reasoning, market timestamp, and tool events.
- Paper trading first, then policy-controlled live execution.
- Strategy marketplace and experiment tracking from AI-Trader.
- Natural-language research and backtesting from Vibe-Trading.
- CLI, web dashboard, desktop app, and chat-channel access through one API.

### 2. AI Hedge-Fund Workbench

A professional research environment for teams. It emphasizes shared knowledge, reproducible backtests, strategy versioning, risk review, and report generation. It uses less autonomous execution and is easier to sell to analysts and research groups.

### 3. Agent Economy Exchange

A marketplace where specialized agents publish signals, research, tools, and completed work. ClawWork evaluates agent economics while AI-Trader supplies trading reputation and rewards. This is strategically interesting but should follow the core platform because it needs identity, trust, billing, and safety at scale.

## Recommended build order

1. **Foundation:** choose the runtime owner, define identity, task, run event, artifact, market object, and approval contracts.
2. **Research MVP:** unify Vibe-Trading research/backtests with LightRAG/RAG-Anything evidence retrieval and a CLI/API surface.
3. **Risk and paper execution:** connect AI-Trader signals and experiments; add policy gates, audit logs, and simulated broker execution.
4. **Operator surfaces:** ship web dashboard, CLI, desktop/mobile shell, and chat adapters over the same API.
5. **Evaluation:** connect ClawWork to measure cost, latency, evidence quality, drawdown, and task success.
6. **Reports and learning:** use Paper2Slides for briefings and DeepTutor for explanations and strategy coaching.
7. **Live execution:** enable broker actions only after paper-trading parity, approval workflows, and recovery tests pass.
8. **Marketplace:** add agent, strategy, and tool sharing after the core platform is reliable.

## Non-negotiable boundaries

- Live trading is permissioned, auditable, cancellable, and idempotent.
- Research data is timestamped; backtests cannot silently use future information.
- Model output is not an execution authorization.
- Generated CLIs and code run in constrained sandboxes.
- Each artifact has provenance and access policy.
- User interfaces call the same versioned API; no UI owns trading logic.

## First vertical slice

`Ask: “Find three low-risk candidates for this portfolio, explain the evidence, backtest the allocation over the selected period, and prepare a paper-trading plan.”`

Success means one run can:

- ingest current market and document evidence;
- produce cited research;
- run a reproducible backtest;
- show risk and assumptions;
- create a paper order plan without sending live orders;
- export a report;
- retain an event trace that another agent or user can inspect.
