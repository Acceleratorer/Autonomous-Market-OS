"""Application workflow shared by the CLI and service API."""
from __future__ import annotations

import threading
import uuid
import json
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
from .providers import BacktestProvider, EvidenceProvider, default_providers
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
            operation = "artifact.write"
            evidence_artifact = self.store.write_artifact(run.run_id, "evidence", [asdict(item) for item in evidence], tuple(item.evidence_id for item in evidence))
            self._check_cancel(run, cancel_event)
            operation = "artifact.write"
            research = self._research(task, evidence)
            research_artifact = self.store.write_artifact(run.run_id, "research", asdict(research), (evidence_artifact.artifact_id,))
            operation = "event.append"
            self._event(run, "research.completed", {"artifact_id": research_artifact.artifact_id})

            self._check_cancel(run, cancel_event)
            operation = "provider.backtest"
            backtest = self.backtest_provider.run(task.symbols, task.start, task.end, self.initial_cash)
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
                result = self._stable({"run": asdict(rejected), "task": asdict(task), "research": asdict(research), "backtest": asdict(backtest), "order_plan": asdict(order_plan), "risk": asdict(risk), "artifacts": [asdict(item) for item in self.store.artifacts_for(run.run_id)]})
                if task.idempotency_key:
                    self.store.save_idempotent_result(task.idempotency_key, result)
                return result

            operation = "run.finalize"
            completed = Run(run.run_id, run.task_id, "completed", run.started_at, utc_now())
            self.store.save_run(completed)
            operation = "event.append"
            self._event(run, "run.completed", {"artifact_ids": [research_artifact.artifact_id, backtest_artifact.artifact_id, order_artifact.artifact_id, risk_artifact.artifact_id]})
            result = self._stable({"run": asdict(completed), "task": asdict(task), "research": asdict(research), "backtest": asdict(backtest), "order_plan": asdict(order_plan), "risk": asdict(risk), "artifacts": [asdict(item) for item in self.store.artifacts_for(run.run_id)]})
            if task.idempotency_key:
                operation = "idempotency.save"
                self.store.save_idempotent_result(task.idempotency_key, result)
            return result
        except WorkflowCancelled:
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

    def _order_plan(self, task: Task, evidence: list[Evidence]) -> OrderPlan:
        prices: dict[str, float] = {}
        for item in evidence:
            if item.kind != "market":
                continue
            prices[item.symbols[0]] = float(item.content.rsplit("=", 1)[1])
        notional = self.initial_cash / len(task.symbols)
        orders = tuple(Order(symbol, "buy", max(1, int(notional / prices[symbol])), prices[symbol], max(1, int(notional / prices[symbol])) * prices[symbol]) for symbol in task.symbols)
        return OrderPlan("paper", orders, sum(order.notional for order in orders))

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
        self.store.append_event(RunEvent(f"event-{uuid.uuid4().hex}", run.run_id, kind, utc_now(), payload))

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
        for attempt in range(2):
            try:
                self.store.save_run(terminal)
                break
            except Exception as save_error:
                recovery["terminal_write_error"] = str(save_error)
                recovery["terminal_write_attempts"] = attempt + 1
        try:
            self.store.append_event(RunEvent(f"event-{uuid.uuid4().hex}", run.run_id, f"run.{kind}", utc_now(), {"error": terminal.error} if terminal.error else {}, provenance={"recovery": recovery}))
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
