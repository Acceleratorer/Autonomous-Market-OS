# Fusion map

## Recommended target layers

```text
Clients / channels / web UIs
        |
Interaction gateway and identity
        |
Agent orchestration kernel
  tools | skills | memory | tasks | events | approvals
        |
Domain modules
  knowledge | education | finance | work-evaluation | media | software-control
        |
Capability adapters
  RAG backends | brokers | model providers | CLIs | renderers | sandboxes
        |
Storage and operations
  metadata | artifacts | traces | vector/graph indexes | credentials | queues
```

## Candidate ownership

- **Orchestration kernel:** Market OS owns production orchestration and its
  safety-critical state. `OpenHarness`, `nanobot`, and `DeepCode` are optional
  capability adapters or reference implementations; their overlapping
  concerns are tool invocation, skills, sessions, memory, and multi-agent
  execution.
- **Knowledge subsystem:** use `LightRAG` as the graph-RAG foundation and `RAG-Anything` as multimodal ingestion. Keep `MiniRAG` as a benchmark/reference rather than a second production backend.
- **Tool subsystem:** expose `CLI-Anything` harnesses through a registry and typed tool gateway. Do not let arbitrary generated CLIs receive unrestricted host access.
- **Finance subsystem:** keep `Vibe-Trading` as research/backtesting domain logic and `AI-Trader` as social/live signal and experiment logic. Define a shared instrument, portfolio, signal, and provenance schema.
- **Work/evaluation subsystem:** use `ClawWork` for task catalogues, economic scoring, cost tracking, and evaluation; connect it to the orchestration event stream.
- **Content subsystem:** treat `Paper2Slides` and `ViMax` as artifact-producing workflows consuming common document, plan, asset, and render contracts.
- **Education subsystem:** treat `DeepTutor` as a domain workflow over the shared knowledge and agent layers.

## High-value shared contracts

1. `Task`: requester, objective, constraints, status, budget, owner, parent task.
2. `RunEvent`: run id, timestamp, actor, tool/model, input/output references, cost, error, provenance.
3. `Artifact`: immutable content reference, media type, lineage, renderer, access policy.
4. `KnowledgeDocument`: source, modality, chunks/entities/relations, embedding/index references.
5. `AgentProfile`: model/provider, skills, tools, permissions, memory scope.
6. `FinancialObject`: instrument, venue, timestamp, price basis, currency, confidence.

## Main integration risks

- Python version and dependency conflicts across projects.
- Multiple competing agent runtimes and session/state models.
- Inconsistent provider configuration and secret handling.
- Artifact paths and local files treated as implicit APIs.
- Trading and sandbox tools require explicit permission, audit, and isolation boundaries.
- Research prototypes and production services have different reliability expectations.

## Staged fusion

1. **Catalog:** freeze project ownership, entry points, dependencies, and licenses.
2. **Kernel decision:** select the orchestration runtime and write adapter interfaces.
3. **Event spine:** add task/run/artifact events without changing domain logic.
4. **Knowledge adapter:** standardize ingestion and retrieval against LightRAG/RAG-Anything.
5. **Vertical slices:** tutor, research, work evaluation, and media workflows each prove one end-to-end path.
6. **Surface consolidation:** connect channels and UIs after backend contracts stabilize.
7. **Retirement:** remove duplicate implementations only after parity evidence exists.
