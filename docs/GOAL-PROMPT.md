# Prompt for a Separate `/goal` Chat

Copy the following prompt into a new Codex chat:

```text
Create and execute a staged implementation plan for the HKUDS Autonomous Market OS in D:\Code\Github\HKUDS.

Goal: fuse the company projects into one autonomous trading platform with a shared backend and CLI, web, desktop/mobile, and chat surfaces. The first deliverable is an evidence-backed research and paper-trading workflow. Live trading must remain disabled until explicit safety gates pass.

Use these documents as the current product source of truth:
- docs/PRODUCT-VISION.md
- docs/PHASES.md
- docs/ROADMAP.md
- docs/TARGET-STRUCTURE.md
- docs/FUSION-MAP.md
- docs/INTEGRATION-GUIDE.md

Inspect all child repositories before choosing implementation boundaries. Preserve existing user changes. Use the repository guidance and the coding workflow skills, including cautious-coding, ecc-harness, ponytail, and code review where applicable.

First produce a concrete Phase 0 decision record covering:
1. the first user and supported market scope;
2. the orchestration runtime to own sessions, tools, skills, memory, and approvals;
3. the initial API and domain contract schemas;
4. the first vertical slice and its acceptance criteria;
5. the minimum repository/package layout;
6. risks, unknowns, and decisions that require human input.

Then implement only the smallest vertical slice that can:
- create a research task;
- retrieve timestamped market/document evidence;
- produce cited research;
- run a reproducible backtest;
- create a paper-trading order plan;
- apply risk checks without live side effects;
- persist run events and artifacts;
- expose the workflow through a CLI and one service API.

For every change, inspect the real code path first, keep adapters narrow, avoid copying entire repositories, and add focused contract/integration tests. Do not add live broker execution, marketplace billing, or broad UI polish before the paper-trading slice is verified.

At the end of each phase, update docs/UNDERSTANDING-LOG.md and record what was verified, what remains unknown, and the next gate. Finish with a concise implementation report, test results, and the exact next decision needed from me.
```
