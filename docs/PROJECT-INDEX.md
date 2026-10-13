# Project index

| Project | Primary role | Runtime shape | Key boundary | Fusion value |
|---|---|---|---|---|
| AI-Trader | Agent-native social/paper trading platform | TypeScript service, web assets, research/docs | `service/` | Market collaboration, signals, experiments |
| ClawWork | Economic benchmark and paid work simulation | Python services, livebench, React frontend | `livebench/`, `clawmode_integration/` | Work tasks, cost accounting, evaluation |
| CLI-Anything | Generate agent-native CLIs for existing software | Large Python/plugin ecosystem | per-app harness directories, `cli-anything-plugin/` | Tool adapters and artifact operations |
| DeepCode | Agentic coding assistant | Python package with core, CLI, app server, desktop | `core/`, `cli/`, `app_server/` | Coding agent, skills, protocol, sandboxing |
| DeepTutor | Personalized multi-agent tutor with RAG | Python package plus CLI/web | `deeptutor/`, `deeptutor_web/` | Planning, teaching, learner memory |
| LightRAG | Graph-enhanced RAG library/service | Python library, web UI, storage backends | `lightrag/`, `lightrag_webui/` | General knowledge graph retrieval |
| MiniRAG | Minimal RAG research implementation | Python package and experiments | `minirag/` | Small reference implementation and baseline |
| nanobot | Lightweight personal assistant | Python package, TUI, web UI, channel integrations | `nanobot/`, `tui/`, `webui/` | Small deployable agent runtime |
| OpenHarness | Agent infrastructure and `ohmo` assistant | Python package, CLI, frontend/dashboard | `src/`, `ohmo/` | Tools, skills, memory, multi-agent coordination |
| Paper2Slides | Paper/report to slides and posters | Python API plus frontend | `paper2slides/`, `api/`, `frontend/` | Document ingestion and presentation artifacts |
| RAG-Anything | Multimodal RAG built on LightRAG | Python package and examples | `raganything/` | Multimodal document understanding |
| Vibe-Trading | Natural-language finance research/backtesting agent | Python FastAPI agent plus React frontend | `agent/`, `frontend/` | Research, brokers, backtests, reports |
| ViMax | Agentic video generation | Python pipelines, agents, UI/web | `pipelines/`, `agents/`, `web/` | Story/media planning and rendering |

## Entry-point notes

- Python packages generally expose CLIs through `pyproject.toml`; inspect each project’s `[project.scripts]` before integration.
- Service-oriented projects are identifiable by `api`, `service`, `app_server`, `web`, or FastAPI/uvicorn dependencies.
- Frontends are local surfaces, not shared domain logic. Preserve them behind API or event contracts.
- `CLI-Anything` contains many independent application harnesses and should be consumed as a registry/tool provider, not merged wholesale.

## Dependency families observed

Python 3.10–3.12 is the common range, with `nanobot` and several newer projects requiring 3.11+. Common infrastructure includes Pydantic, FastAPI, LangChain/LangGraph, HTTP clients, vector stores, FAISS, graph databases, Docker, and React frontends. A fusion runtime should standardize one supported Python baseline, one configuration model, and one provider abstraction before sharing code.
