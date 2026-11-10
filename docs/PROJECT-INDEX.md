# Project index

| Project | Primary role | Runtime shape | Key boundary | Fusion value | Current use / decision |
|---|---|---|---|---|---|
| AI-Trader | Agent-native social/paper trading platform | TypeScript service, web assets, research/docs | `service/` | Market collaboration, signals, experiments | Reference only for the Polymarket outcome-to-token mapping; token, heartbeat, and signal workflows remain deferred |
| ClawWork | Economic benchmark and paid work simulation | Python services, livebench, React frontend | `livebench/`, `clawmode_integration/` | Cost/income accounting and evaluation | U7-J uses synthetic cost/income semantics; paid-task runtime remains deferred |
| CLI-Anything | Generate agent-native CLIs for existing software | Large Python/plugin ecosystem | per-app harness directories, `cli-anything-plugin/` | Typed command registries and sandboxing | U7-K audits typed registry metadata and explicit denials; generated execution remains deferred |
| DeepCode | Agentic coding assistant | Python package with core, CLI, app server, desktop | `core/`, `cli/`, `app_server/` | Coding agent, skills, protocol, sandboxing | No runtime reuse selected; sessions, persistence, recovery, and permissions overlap Market OS-owned orchestration |
| DeepTutor | Personalized multi-agent tutor with RAG | Python package plus CLI/web | `deeptutor/`, `deeptutor_web/` | Planning, teaching, learner memory | Defer model/tool-driven learning flows; no current offline seam adds enough value |
| LightRAG | Graph-enhanced RAG library/service | Python library, web UI, storage backends | `lightrag/`, `lightrag_webui/` | Cited text retrieval | M2.2 uses an isolated optional adapter and synthetic corpus; graph modes, multimodal parsing, and generated answers remain out of scope |
| MiniRAG | Minimal RAG research implementation | Python package and experiments | `minirag/` | Small reference implementation and baseline | Reference only; it does not fill a distinct gap beside the existing LightRAG adapter |
| nanobot | Lightweight personal assistant | Python package, TUI, web UI, channel integrations | `nanobot/`, `tui/`, `webui/` | Skills and agent runtime | Keep its simple `SKILL.md` format as a future playbook reference; defer the gateway/runtime and provider integrations |
| OpenHarness | Agent infrastructure and `ohmo` assistant | Python package, CLI, frontend/dashboard | `src/`, `ohmo/` | Tools, skills, memory, multi-agent coordination | Existing adapter and bounded probes remain optional; Market OS keeps orchestration, persistence, cancellation, and recovery ownership |
| Paper2Slides | Paper/report to slides and posters | Python API plus frontend | `paper2slides/`, `api/`, `frontend/` | Research document presentation | U7-L exports a cited Markdown input; its model and media pipeline remains deferred |
| RAG-Anything | Multimodal RAG built on LightRAG | Python package and examples | `raganything/` | Multimodal document understanding | Defer parser, VLM, storage, and model dependency expansion |
| Vibe-Trading | Natural-language finance research/backtesting agent | Python FastAPI agent plus React frontend | `agent/`, `frontend/` | Research and backtesting | M2.1 keeps an explicit paper backtest adapter; broker and live integrations remain deferred |
| ViMax | Agentic video generation | Python pipelines, agents, UI/web | `pipelines/`, `agents/`, `web/` | Story/media planning and rendering | Defer model-based planning and image/video generation providers |

## Entry-point notes

- Python packages generally expose CLIs through `pyproject.toml`; inspect each project’s `[project.scripts]` before integration.
- Service-oriented projects are identifiable by `api`, `service`, `app_server`, `web`, or FastAPI/uvicorn dependencies.
- Frontends are local surfaces, not shared domain logic. Preserve them behind API or event contracts.
- `CLI-Anything` contains many independent application harnesses and should be consumed as a registry/tool provider, not merged wholesale.

## Dependency families observed

Python 3.10–3.12 is the common range, with `nanobot` and several newer projects requiring 3.11+. Common infrastructure includes Pydantic, FastAPI, LangChain/LangGraph, HTTP clients, vector stores, FAISS, graph databases, Docker, and React frontends. A fusion runtime should standardize one supported Python baseline, one configuration model, and one provider abstraction before sharing code.
