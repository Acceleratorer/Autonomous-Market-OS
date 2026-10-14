"""Application workflow shared by the CLI and service API."""
from __future__ import annotations

import threading
import uuid
import json
import hashlib
import inspect
import math
import traceback
from pathlib import Path
from dataclasses import asdict
from typing import Any

from .contracts import (
    Evidence,
    Order,
    OrderPlan,
    ResearchResult,
    RiskDecision,
    Run,
    RunEvent,
    Task,
    utc_now,
)
from .providers import BacktestProvider, EvidenceProvider, ProviderCancelled, default_providers
from .research import DeterministicResearchSynthesizer, research_synthesis_from_dict
from .store import RunStore


class WorkflowCancelled(Exception):
    """Raised internally after the cancellation event is durably recorded."""


class MarketWorkflow:
    def __init__(
        self,
        store: RunStore | None = None,
        evidence_provider: EvidenceProvider | None = None,
        backtest_provider: BacktestProvider | None = None,
        initial_cash: float = 10_000.0,
        max_notional: float = 10_000.0,
        max_symbols: int = 10,
    ) -> None:
        default_evidence, default_backtest = default_providers()
        self.store = store or RunStore()
        self.evidence_provider = evidence_provider or default_evidence
        self.backtest_provider = backtest_provider or default_backtest
        self.initial_cash = initial_cash
        self.max_notional = max_notional
        self.max_symbols = max_symbols

    def create_task(self, objective: str, symbols: list[str], start: str, end: str, *, execution_mode: str = "paper", idempotency_key: str | None = None) -> Task:
        clean_symbols = tuple(dict.fromkeys(s.strip().upper() for s in symbols if s.strip()))
        if not objective.strip():
            raise ValueError("objective must not be empty")
        if not clean_symbols:
            raise ValueError("at least one symbol is required")
        if start > end:
            raise ValueError("start must be on or before end")
        if execution_mode != "paper":
            raise ValueError("live execution is disabled in market-os.v1")
        return Task(f"task-{uuid.uuid4().hex}", objective.strip(), clean_symbols, start, end, utc_now(), execution_mode, idempotency_key)

    def run(self, task: Task, cancel_event: threading.Event | None = None) -> dict[str, Any]:
        if task.idempotency_key:
            previous = self.store.idempotent_result(task.idempotency_key)
            if previous:
                return previous
        run = Run(f"run-{uuid.uuid4().hex}", task.task_id, "running", utc_now())
        if hasattr(self.store, "last_artifact_attempt"):
            self.store.last_artifact_attempt = None
        operation = "run.index"
        try:
            self.store.save_run(run)
            operation = "event.append"
            self._event(run, "run.started", {"task": asdict(task)})
            self._check_cancel(run, cancel_event)
            operation = "provider.retrieve"
            evidence = self.evidence_provider.retrieve(task.objective, task.symbols, task.start, task.end)
            operation = "event.append"
            self._event(run, "evidence.retrieved", {"count": len(evidence)})
            document_context = self._document_context()
            document_artifact = None
            retrieval_artifact = None
            cited_research = None
            cited_research_artifact = None
            if document_context is not None:
                documents, document_payload, retrieval = document_context
                operation = "artifact.write"
                document_artifact = self.store.write_artifact(
                    run.run_id,
                    "documents",
                    document_payload,
                    tuple(document.document_id for document in documents),
                )
                retrieval_artifact = self.store.write_artifact(
                    run.run_id,
                    "retrieval",
                    asdict(retrieval),
                    (document_artifact.artifact_id,),
                )
                self._event(
                    run,
                    "retrieval.completed",
                    {
                        "artifact_id": retrieval_artifact.artifact_id,
                        "citations": list(retrieval.citations),
                    },
                )
            operation = "artifact.write"
            evidence_lineage = [item.evidence_id for item in evidence]
            if document_artifact is not None and retrieval_artifact is not None:
                evidence_lineage = [document_artifact.artifact_id, retrieval_artifact.artifact_id, *evidence_lineage]
            evidence_artifact = self.store.write_artifact(run.run_id, "evidence", [asdict(item) for item in evidence], tuple(evidence_lineage))
            self._check_cancel(run, cancel_event)
            if document_context is not None and document_artifact is not None and retrieval_artifact is not None:
                documents, _, retrieval = document_context
                cited_research = DeterministicResearchSynthesizer().synthesize(
                    task.objective,
                    documents,
                    retrieval,
                    retrieval_artifact_id=retrieval_artifact.artifact_id,
                    document_artifact_id=document_artifact.artifact_id,
                    evidence_artifact_id=evidence_artifact.artifact_id,
                )
                cited_research_artifact = self.store.write_artifact(
                    run.run_id,
                    "cited-research",
                    asdict(cited_research),
                    (document_artifact.artifact_id, retrieval_artifact.artifact_id, evidence_artifact.artifact_id),
                )
                self._event(
                    run,
                    "research.synthesized",
                    {
                        "artifact_id": cited_research_artifact.artifact_id,
                        "coverage": asdict(cited_research.coverage),
                    },
                )
            operation = "artifact.write"
            research = self._research(task, evidence)
            research_lineage = [evidence_artifact.artifact_id]
            if retrieval_artifact is not None:
                research_lineage.append(retrieval_artifact.artifact_id)
            if cited_research_artifact is not None:
                research_lineage.append(cited_research_artifact.artifact_id)
            research_artifact = self.store.write_artifact(run.run_id, "research", asdict(research), tuple(research_lineage))
            operation = "event.append"
            self._event(run, "research.completed", {"artifact_id": research_artifact.artifact_id})

            self._check_cancel(run, cancel_event)
            operation = "provider.backtest"
            run_provider = self.backtest_provider.run
            parameters = inspect.signature(run_provider).parameters
            if "cancel_event" in parameters or any(
                parameter.kind is inspect.Parameter.VAR_KEYWORD
                for parameter in parameters.values()
            ):
                backtest = run_provider(
                    task.symbols,
                    task.start,
                    task.end,
                    self.initial_cash,
                    cancel_event=cancel_event,
                )
            else:
                backtest = run_provider(task.symbols, task.start, task.end, self.initial_cash)
            operation = "artifact.write"
            backtest_artifact = self.store.write_artifact(run.run_id, "backtest", asdict(backtest), (evidence_artifact.artifact_id,))
            self._check_cancel(run, cancel_event)
            operation = "event.append"
            self._event(run, "backtest.completed", {"artifact_id": backtest_artifact.artifact_id})

            order_plan = self._order_plan(task, evidence)
            risk = self._risk(order_plan, task)
            operation = "artifact.write"
            order_artifact = self.store.write_artifact(run.run_id, "order-plan", asdict(order_plan), (backtest_artifact.artifact_id,))
            self._check_cancel(run, cancel_event)
            operation = "artifact.write"
            risk_artifact = self.store.write_artifact(run.run_id, "risk-decision", asdict(risk), (order_artifact.artifact_id,))
            self._check_cancel(run, cancel_event)
            operation = "event.append"
            self._event(run, "risk.checked", {"artifact_id": risk_artifact.artifact_id, "status": risk.status})
            if risk.status == "rejected":
                rejected = Run(run.run_id, run.task_id, "rejected", run.started_at, utc_now(), "; ".join(risk.reasons))
                operation = "run.finalize"
                self.store.save_run(rejected)
                operation = "event.append"
                self._event(run, "run.rejected", {"reasons": risk.reasons})
                result = self._stable({"run": asdict(rejected), "task": asdict(task), "research": asdict(research), "backtest": asdict(backtest), "order_plan": asdict(order_plan), "risk": asdict(risk), "artifacts": [asdict(item) for item in self.store.artifacts_for(run.run_id)], **self._document_result(document_context, cited_research)})
                if task.idempotency_key:
                    self.store.save_idempotent_result(task.idempotency_key, result)
                return result

            self._check_cancel(run, cancel_event)
            operation = "run.finalize"
            completed = Run(run.run_id, run.task_id, "completed", run.started_at, utc_now())
            self.store.save_run(completed)
            operation = "event.append"
            artifact_ids = [research_artifact.artifact_id, backtest_artifact.artifact_id, order_artifact.artifact_id, risk_artifact.artifact_id]
            if cited_research_artifact is not None:
                artifact_ids.extend((document_artifact.artifact_id, retrieval_artifact.artifact_id, cited_research_artifact.artifact_id))
            self._event(run, "run.completed", {"artifact_ids": artifact_ids})
            result = self._stable({"run": asdict(completed), "task": asdict(task), "research": asdict(research), "backtest": asdict(backtest), "order_plan": asdict(order_plan), "risk": asdict(risk), "artifacts": [asdict(item) for item in self.store.artifacts_for(run.run_id)], **self._document_result(document_context, cited_research)})
            if task.idempotency_key:
                operation = "idempotency.save"
                self.store.save_idempotent_result(task.idempotency_key, result)
            return result
        except WorkflowCancelled:
            cancelled = Run(run.run_id, run.task_id, "cancelled", run.started_at, utc_now())
            self._terminalize(run, cancelled, "cancelled", operation)
            return {"run": asdict(cancelled), "task": asdict(task), "events": [asdict(event) for event in self.store.events_for(run.run_id)]}
        except ProviderCancelled:
            cancelled = Run(run.run_id, run.task_id, "cancelled", run.started_at, utc_now())
            self._terminalize(run, cancelled, "cancelled", operation)
            return {"run": asdict(cancelled), "task": asdict(task), "events": [asdict(event) for event in self.store.events_for(run.run_id)]}
        except Exception as exc:
            failed = Run(run.run_id, run.task_id, "failed", run.started_at, utc_now(), self._error_message(exc, operation))
            self._terminalize(run, failed, "failed", operation, original=exc)
            raise

    def inspect_run(self, run_id: str) -> dict[str, Any]:
        events = self.store.events_for(run_id)
        if not events:
            raise KeyError(run_id)
        return {
            "run": self.store.latest_run(run_id),
            "run_id": run_id,
            "events": [asdict(event) for event in events],
            "artifacts": [asdict(item) for item in self.store.artifacts_for(run_id)],
            "recovery": self.store.recovery_for(run_id),
        }

    def inspect_resource(self, run_id: str, resource: str, item_id: str | None = None) -> dict[str, Any]:
        """Read persisted cited-research resources without invoking providers."""
        inspected = self.inspect_run(run_id)
        artifacts = {item["artifact_id"]: item for item in inspected["artifacts"]}
        payloads = {item["kind"]: self._read_inspection_artifact(item, artifacts) for item in inspected["artifacts"]}
        cited = payloads.get("cited-research")
        documents = payloads.get("documents")
        retrieval = payloads.get("retrieval")
        if resource == "lineage":
            if item_id is None or item_id not in artifacts:
                raise KeyError(item_id or "artifact")
            artifact = artifacts[item_id]
            return {"run_id": run_id, "artifact": artifact, "lineage": [self._artifact_summary(artifacts[ref]) for ref in artifact.get("lineage", ()) if ref in artifacts]}
        if cited is None or documents is None or retrieval is None:
            raise ValueError("cited research artifacts are incomplete")
        self._validate_document_payload(documents)
        synthesis = research_synthesis_from_dict(cited)
        artifact_ids = set(artifacts)
        referenced_lineage = {
            *(document.lineage_artifact_id for document in synthesis.documents),
            *(passage.lineage_artifact_id for passage in synthesis.passages),
            *(citation.lineage_artifact_id for citation in synthesis.citations),
            *(support.lineage_artifact_id for support in synthesis.supports),
            synthesis.lineage_artifact_id,
        }
        if not referenced_lineage.issubset(artifact_ids):
            raise ValueError("research lineage is incomplete")
        if resource == "documents":
            values = documents
            if item_id is not None:
                values = [item for item in values if item["document"]["document_id"] == item_id]
                if not values:
                    raise KeyError(item_id)
            return {"run_id": run_id, "documents": values}
        if resource == "passages":
            values = cited.get("passages", [])
            if item_id is not None:
                values = [item for item in values if item["passage_id"] == item_id]
                if not values:
                    raise KeyError(item_id)
            return {"run_id": run_id, "passages": values}
        if resource == "claims":
            values = [*cited.get("claims", []), *cited.get("unsupported_claims", [])]
            if item_id is not None:
                values = [item for item in values if item["claim_id"] == item_id]
                if not values:
                    raise KeyError(item_id)
            return {"run_id": run_id, "claims": values, "coverage": asdict(synthesis.coverage)}
        if resource == "unsupported-claims":
            values = cited.get("unsupported_claims", [])
            if item_id is not None:
                values = [item for item in values if item["claim_id"] == item_id]
                if not values:
                    raise KeyError(item_id)
            return {"run_id": run_id, "unsupported_claims": values, "coverage": asdict(synthesis.coverage)}
        if resource == "passage-claims":
            if item_id is None:
                raise KeyError("passage_id")
            passage_ids = {item["passage_id"] for item in cited.get("passages", [])}
            if item_id not in passage_ids:
                raise KeyError(item_id)
            support_by_passage = {
                support["passage_id"]: support["claim_id"]
                for support in cited.get("supports", [])
            }
            claims = [
                claim
                for claim in cited.get("claims", [])
                if claim["claim_id"] == support_by_passage.get(item_id)
            ]
            return {"run_id": run_id, "passage_id": item_id, "claims": claims}
        if resource == "citations":
            citations = [asdict(citation) for citation in synthesis.citations]
            if item_id is not None:
                claim_ids = {item["claim_id"] for item in cited.get("claims", []) if item["claim_id"] == item_id}
                if not claim_ids:
                    raise KeyError(item_id)
                citations = [item for item in citations if item["claim_id"] == item_id]
            return {"run_id": run_id, "citations": citations}
        raise ValueError(f"unknown inspection resource: {resource}")

    def _read_inspection_artifact(self, artifact: dict[str, Any], artifacts: dict[str, dict[str, Any]]) -> Any:
        path = Path(artifact["path"])
        artifact_root = self.store.artifacts.resolve()
        resolved_path = path.resolve()
        if not resolved_path.is_relative_to(artifact_root):
            raise ValueError(f"artifact path is outside the run store: {artifact['artifact_id']}")
        if not path.exists():
            raise ValueError(f"artifact is missing: {artifact['artifact_id']}")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != artifact["sha256"]:
            raise ValueError(f"artifact content hash mismatch: {artifact['artifact_id']}")
        for ref in artifact.get("lineage", ()):
            if ref.startswith("artifact-") and ref not in artifacts:
                raise ValueError(f"artifact lineage is incomplete: {ref}")
        return json.loads(raw)

    @staticmethod
    def _artifact_summary(artifact: dict[str, Any]) -> dict[str, Any]:
        return {key: artifact[key] for key in ("artifact_id", "kind", "sha256", "lineage", "media_type", "created_at")}

    @staticmethod
    def _validate_document_payload(payload: Any) -> None:
        if not isinstance(payload, list):
            raise ValueError("document artifact is malformed")
        for item in payload:
            document = item.get("document") if isinstance(item, dict) else None
            content = item.get("content") if isinstance(item, dict) else None
            if not isinstance(document, dict) or not isinstance(content, str):
                raise ValueError("document artifact is malformed")
            if hashlib.sha256(content.encode("utf-8")).hexdigest() != document.get("content_hash"):
                raise ValueError(f"document content hash mismatch: {document.get('document_id')}")

    def recover_inflight_runs(self) -> list[dict[str, Any]]:
        """Mark abandoned runs failed; provider/backtest work is never resumed."""
        latest: dict[str, dict[str, Any]] = {}
        for line in self.store.runs.read_text(encoding="utf-8").splitlines():
            if line.strip():
                value = json.loads(line)
                latest[value["run_id"]] = value
        recovered: list[dict[str, Any]] = []
        for value in latest.values():
            if value["status"] != "running":
                continue
            run = Run(value["run_id"], value["task_id"], "running", value["started_at"])
            terminal = Run(run.run_id, run.task_id, "failed", run.started_at, utc_now(), "restart_interrupted:resume_unsupported")
            self._terminalize(run, terminal, "failed", "process.restart")
            recovered.append(asdict(terminal))
        return recovered

    def _research(self, task: Task, evidence: list[Evidence]) -> ResearchResult:
        citations = tuple(item.evidence_id for item in evidence)
        summary = f"Evidence-backed review for {', '.join(task.symbols)} from {task.start} through {task.end}. Orders remain paper-only."
        return ResearchResult(summary, citations, citations)

    def _document_context(self):
        provider = self.evidence_provider
        documents = getattr(provider, "last_documents", ())
        payload = getattr(provider, "last_document_payload", ())
        retrieval = getattr(provider, "last_retrieval_result", None)
        if documents and payload and retrieval is not None:
            return tuple(documents), list(payload), retrieval
        return None

    @staticmethod
    def _document_result(context, cited_research=None) -> dict[str, Any]:
        if context is None:
            return {}
        documents, payload, retrieval = context
        result = {
            "documents": payload,
            "retrieval": asdict(retrieval),
        }
        if cited_research is not None:
            result["cited_research"] = asdict(cited_research)
        return result

    def _order_plan(self, task: Task, evidence: list[Evidence]) -> OrderPlan:
        prices: dict[str, float] = {}
        for item in evidence:
            if item.kind != "market":
                continue
            prices[item.symbols[0]] = self._latest_evidence_close(item.content)
        notional = self.initial_cash / len(task.symbols)
        orders = tuple(Order(symbol, "buy", max(1, int(notional / prices[symbol])), prices[symbol], max(1, int(notional / prices[symbol])) * prices[symbol]) for symbol in task.symbols)
        return OrderPlan("paper", orders, sum(order.notional for order in orders))

    @staticmethod
    def _latest_evidence_close(content: str) -> float:
        try:
            rows = json.loads(content)
        except json.JSONDecodeError:
            return float(content.rsplit("=", 1)[1])
        if not isinstance(rows, list) or not rows:
            raise ValueError("market evidence must contain at least one bar")
        close = rows[-1].get("close") if isinstance(rows[-1], dict) else None
        if not isinstance(close, (int, float)) or not math.isfinite(close) or close <= 0:
            raise ValueError("market evidence has an invalid latest close")
        return float(close)

    def _risk(self, order_plan: OrderPlan, task: Task) -> RiskDecision:
        reasons: list[str] = []
        if len(task.symbols) > self.max_symbols:
            reasons.append(f"symbol count exceeds {self.max_symbols}")
        if order_plan.total_notional > self.max_notional:
            reasons.append(f"notional exceeds {self.max_notional:.2f}")
        return RiskDecision("rejected" if reasons else "approved", tuple(reasons), {"max_notional": self.max_notional, "max_symbols": float(self.max_symbols)})

    def _check_cancel(self, run: Run, cancel_event: threading.Event | None) -> None:
        if cancel_event and cancel_event.is_set():
            raise WorkflowCancelled

    def _event(self, run: Run, kind: str, payload: dict[str, Any]) -> None:
        provider = self._provider_metadata()
        self.store.append_event(
            RunEvent(
                f"event-{uuid.uuid4().hex}",
                run.run_id,
                kind,
                utc_now(),
                payload,
                provenance=provider,
            )
        )

    def _provider_metadata(self) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for name, provider in (("evidence", self.evidence_provider), ("backtest", self.backtest_provider)):
            metadata = getattr(provider, "provider_metadata", None)
            if callable(metadata):
                values[name] = metadata()
        return values

    def _terminalize(self, run: Run, terminal: Run, kind: str, operation: str, *, original: Exception | None = None) -> None:
        recovery = {
            "run_id": run.run_id,
            "task_id": run.task_id,
            "operation": operation,
            "terminal_status": terminal.status,
            "error": terminal.error,
            "partial_artifact": self._partial_artifact(),
            "traceback": traceback.format_exception(original) if original is not None else None,
            "retry_policy": "manual replay is safe only with the same idempotency key",
        }
        provider_error = getattr(original, "provider_error", None)
        if provider_error is not None:
            recovery["provider_error"] = asdict(provider_error)
        for attempt in range(2):
            try:
                self.store.save_run(terminal)
                break
            except Exception as save_error:
                recovery["terminal_write_error"] = str(save_error)
                recovery["terminal_write_attempts"] = attempt + 1
        try:
            self.store.append_event(RunEvent(f"event-{uuid.uuid4().hex}", run.run_id, f"run.{kind}", utc_now(), {"error": terminal.error} if terminal.error else {}, provenance={**self._provider_metadata(), "recovery": recovery}))
        except Exception as event_error:
            recovery["event_write_error"] = str(event_error)
        try:
            self.store.append_recovery(recovery)
        except Exception:
            pass

    def _partial_artifact(self) -> dict[str, Any] | None:
        artifact = getattr(self.store, "last_artifact_attempt", None)
        if artifact is None:
            return None
        try:
            indexed = any(item.artifact_id == artifact.artifact_id for item in self.store.artifacts_for(artifact.run_id))
        except Exception:
            indexed = False
        return {
            "artifact_id": artifact.artifact_id,
            "kind": artifact.kind,
            "sha256": artifact.sha256,
            "indexed": indexed,
            "file_exists": Path(artifact.path).exists(),
        }

    @staticmethod
    def _error_message(error: Exception, operation: str) -> str:
        if operation.startswith(("event.", "run.", "artifact.", "idempotency.")):
            return f"persistence_error:{operation}:{error}"
        return str(error)

    @staticmethod
    def _stable(value: dict[str, Any]) -> dict[str, Any]:
        return json.loads(json.dumps(value, sort_keys=True))
