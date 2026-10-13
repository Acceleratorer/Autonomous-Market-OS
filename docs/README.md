# Autonomous Market OS Workspace Guide

Status: initial architecture pass, generated 2026-10-13.

This directory documents the independent source projects used by this personal project. Each child project remains an independent Git repository. The documents describe observed boundaries and likely integration seams; they do not claim that the projects already share a runtime or API contract.

## Start here

- [Project index](PROJECT-INDEX.md): purpose, runtime shape, entry points, and integration value for every project.
- [Fusion map](FUSION-MAP.md): capability layers, duplicate responsibilities, and a staged target architecture.
- [Understanding log](UNDERSTANDING-LOG.md): evidence collected, assumptions, open questions, and next discovery passes.
- [Integration guide](INTEGRATION-GUIDE.md): rules for combining capabilities without collapsing independent project boundaries.

## Current capability layers

1. **Agent runtimes and harnesses:** `nanobot`, `OpenHarness`, `DeepCode`, `CLI-Anything`.
2. **Retrieval and knowledge:** `LightRAG`, `MiniRAG`, `RAG-Anything`.
3. **Learning and tutoring:** `DeepTutor`.
4. **Research and trading:** `AI-Trader`, `Vibe-Trading`.
5. **Economic evaluation:** `ClawWork`.
6. **Creative generation:** `Paper2Slides`, `ViMax`.

The most reusable shared kernel is an agent runtime with typed tools, skills, memory, task execution, artifact handling, and event tracing. Retrieval, trading, tutoring, economic evaluation, slides, and video should attach as domain modules behind explicit interfaces.

## Working rule

Treat each child repository as a bounded context until an adapter, schema, and ownership decision exist. Do not merge by copying folders or flattening dependencies first. Define contracts first, then integrate one vertical workflow at a time.

- [Product vision](PRODUCT-VISION.md): recommended flagship and staged fusion plan for an autonomous trading AI.

