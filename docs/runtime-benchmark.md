# Orchestration runtime benchmark

**Date:** 2026-10-13
**Status:** historical source-based comparison; direct runtime execution was not performed because the child repositories have incompatible dependency floors and provider configuration requirements. The benchmark is an architecture fit assessment, not a performance result. ADR-0010 is the later final ownership decision.

## Comparison

| Dimension | OpenHarness | nanobot | DeepCode |
|---|---|---|---|
| Lifecycle | Session/runtime lifecycle in `ohmo/runtime.py` and gateway runtime | Agent runner and session manager in `nanobot/agent/runner.py`, `session/manager.py` | Workflow/planning runtimes in `workflows/agent_orchestration_engine.py` and `planning_runtime.py` |
| Tools | Registry and bridge/session runner support; `src/openharness/commands/registry.py`, `src/openharness/bridge/` | Skill/tool loading in `agent/skills.py` and agent loop | Tool registry in `core/agent_runtime/tools/registry.py` |
| Skills | Runtime and project skill surfaces | First-class skills and subagents | Skill runtime in `core/skills/runtime.py` |
| Memory | `ohmo/memory.py` plus session storage | Agent memory and session state | Persistence and observability records |
| Multi-agent | In-process swarm coverage in `tests/test_swarm/test_in_process.py` | Subagent and subagent-session modules | Agent orchestration engine and coordination repository |
| Cancellation | Runtime/session hooks exist; adapter semantics still needed | Session recovery exists; explicit Market OS cancellation mapping still needed | Event/session protocol and workflow state provide the strongest recovery seam |
| Restart/recovery | Session storage and gateway runtime provide a usable seam | `session/recovery.py` provides lightweight recovery | SQLite persistence, checkpoints, and event repositories provide the strongest durable model |
| Event tracing | Gateway/session events can be translated to `RunEvent` | `events.py` provides an event surface | `core/events/` and `core/observability/` are the most explicit fit |
| CLI | `openharness`, `oh`, `openh`, and `ohmo` scripts | `nanobot` and desktop TUI scripts | CLI exists, but the repository is primarily a coding-agent system |
| API/service | Gateway runtime and service modules | `api/server.py` and `api/runtime.py` | `app_server/service.py` and `dispatcher.py` |
| Dependency complexity | High: model, UI, channel, MCP, and integration dependencies | High: assistant, document, channel, and model dependencies | Highest: broad internal architecture and larger dependency surface |
| Deployment complexity | Moderate to high; several optional surfaces | Moderate; lighter core but many optional channels | High; persistence, service, workflow, and coding-agent subsystems |
| Market OS fit | Best broad orchestration and gateway fit | Best lightweight channel/personal assistant adapter | Best durable event/recovery reference, but too specialized and complex as the first owner |
| Evidence paths | `OpenHarness/ohmo/*`, `OpenHarness/src/openharness/*`, `OpenHarness/tests/test_swarm/*` | `nanobot/nanobot/agent/*`, `nanobot/nanobot/session/*`, `nanobot/nanobot/api/*` | `DeepCode/core/events/*`, `DeepCode/core/persistence/*`, `DeepCode/workflows/*`, `DeepCode/app_server/*` |

## Recommendation

The historical recommendation was to use **OpenHarness as the provisional
orchestration owner** behind a narrow Market OS adapter. ADR-0010 supersedes
that recommendation: Market OS owns production orchestration, while
OpenHarness remains an optional adapter. Nanobot remains available for channel
and personal-assistant integration, and DeepCode's event, persistence,
checkpoint, and recovery ideas remain reference material rather than imported
architecture.

This recommendation is based on source inspection. Before the adapter is accepted, run a fixture-parity harness that compares task creation, event translation, cancellation, restart inspection, idempotency, and paper-only enforcement against the dependency-free `market_os` workflow.

## Benchmark limits

- No provider credentials or model calls were used.
- No child-repository dependencies were installed or imported into the fusion package.
- No latency, throughput, memory, or failure-rate number is claimed.
- The next runtime benchmark must use the same contract fixtures and a bounded local execution environment.
