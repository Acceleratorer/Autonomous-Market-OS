"""Parity harness for the dependency-free workflow and OpenHarness adapter."""
from __future__ import annotations

import argparse
import json
import threading
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from ..contracts import (
    BacktestResult,
    ContractError,
    OrderPlan,
    ResearchResult,
    RiskDecision,
    Task,
    from_json,
    order_plan_from_dict,
    task_from_dict,
    to_json,
)
from ..providers import default_providers
from ..store import RunStore
from ..workflow import MarketWorkflow
from .openharness_adapter import IsolatedOpenHarnessRuntime, OpenHarnessAdapter


@dataclass(frozen=True)
class ParityCheck:
    name: str
    status: Literal["match", "translation", "unsupported", "mismatch"]
    detail: str


@dataclass(frozen=True)
class ParityReport:
    runtime_verified: bool
    checks: tuple[ParityCheck, ...]
    reference_run_id: str
    openharness_run_id: str

    @property
    def matches(self) -> tuple[ParityCheck, ...]:
        return tuple(check for check in self.checks if check.status == "match")

    @property
    def translations(self) -> tuple[ParityCheck, ...]:
        return tuple(check for check in self.checks if check.status == "translation")

    @property
    def unsupported(self) -> tuple[ParityCheck, ...]:
        return tuple(check for check in self.checks if check.status == "unsupported")

    @property
    def mismatches(self) -> tuple[ParityCheck, ...]:
        return tuple(check for check in self.checks if check.status == "mismatch")

    @property
    def promotable(self) -> bool:
        return self.runtime_verified and not self.mismatches and not self.unsupported

    def to_dict(self) -> dict[str, Any]:
        return {
            "runtime_verified": self.runtime_verified,
            "promotable": self.promotable,
            "reference_run_id": self.reference_run_id,
            "openharness_run_id": self.openharness_run_id,
            "checks": [asdict(check) for check in self.checks],
        }


def compare_results(reference: dict[str, Any], candidate: dict[str, Any]) -> tuple[ParityCheck, ...]:
    """Compare stable result fields and report mismatches without raising."""
    checks: list[ParityCheck] = []
    for key in ("research", "backtest", "order_plan", "risk"):
        if reference.get(key) == candidate.get(key):
            checks.append(ParityCheck(f"result.{key}", "match", f"{key} payloads are identical"))
        else:
            checks.append(ParityCheck(f"result.{key}", "mismatch", f"{key} payload differs"))
    if reference.get("task", {}).get("execution_mode") == candidate.get("task", {}).get("execution_mode") == "paper":
        checks.append(ParityCheck("paper-only", "match", "both results remain paper-only"))
    else:
        checks.append(ParityCheck("paper-only", "mismatch", "execution mode differs or is not paper"))
    return tuple(checks)


def run_parity_harness(
    root: str | Path,
    task: Task,
    *,
    runtime: Any | None = None,
) -> ParityReport:
    """Run the same task through both paths and return an auditable report."""
    root = Path(root)
    reference_root = root / "reference"
    openharness_root = root / "openharness"
    reference = MarketWorkflow(RunStore(reference_root))
    adapter = OpenHarnessAdapter(RunStore(openharness_root), runtime=runtime)
    reference_task = reference.create_task(
        task.objective,
        list(task.symbols),
        task.start,
        task.end,
        execution_mode=task.execution_mode,
        idempotency_key=task.idempotency_key,
    )
    openharness_task = adapter.create_task(
        task.objective,
        list(task.symbols),
        task.start,
        task.end,
        execution_mode=task.execution_mode,
        idempotency_key=task.idempotency_key,
    )
    checks = [_compare_task_creation(reference_task, openharness_task)]
    reference_result = reference.run(reference_task)
    openharness_result = adapter.run(openharness_task)
    checks.extend(compare_results(reference_result, openharness_result))
    reference_run_id = reference_result["run"]["run_id"]
    openharness_run_id = openharness_result["run"]["run_id"]

    if reference_result["run"]["status"] == openharness_result["run"]["status"] == "completed":
        checks.append(ParityCheck("completion", "match", "both paths reach a completed run"))
    else:
        checks.append(ParityCheck("completion", "mismatch", "completed run status differs"))

    reference_events = RunStore(reference_root).events_for(reference_run_id)
    openharness_events = RunStore(openharness_root).events_for(openharness_run_id)
    reference_kinds = [event.kind for event in reference_events]
    openharness_kinds = [event.kind for event in openharness_events]
    if reference_kinds == openharness_kinds:
        checks.append(ParityCheck("event-order", "match", "market-os event kinds preserve order"))
    else:
        checks.append(ParityCheck("event-order", "mismatch", f"reference={reference_kinds}; openharness={openharness_kinds}"))

    if all(_is_utc(event.timestamp) for event in reference_events + openharness_events) and all(
        _is_monotonic(event.timestamp for event in events)
        for events in (reference_events, openharness_events)
    ):
        checks.append(ParityCheck("event-timestamps", "match", "all persisted event timestamps are explicit UTC"))
    else:
        checks.append(ParityCheck("event-timestamps", "mismatch", "one or more event timestamps are not UTC"))

    checks.extend(_artifact_checks(reference_result, openharness_result))
    checks.extend(_serialization_checks(reference_result, openharness_result))
    reference_inspection = reference.inspect_run(reference_run_id)
    openharness_inspection = adapter.inspect_run(openharness_run_id)
    if (
        set(reference_result) == set(openharness_result)
        and set(reference_inspection) == set(openharness_inspection)
        and set(reference_inspection["run"]) == set(openharness_inspection["run"])
        and set(reference_inspection["events"][0]) == set(openharness_inspection["events"][0])
    ):
        checks.append(ParityCheck("cli-api-shape", "match", "both paths expose the same workflow result and inspection keys"))
    else:
        checks.append(ParityCheck("cli-api-shape", "mismatch", "workflow result keys differ"))
    checks.append(ParityCheck("event-mapping", "translation", "OpenHarness session/tool names translate to market-os event kinds"))
    if adapter.runtime_verified:
        checks.append(ParityCheck("runtime-execution", "match", "real OpenHarness runtime executed in an isolated environment"))
        checks.extend(_runtime_checks(adapter))
    else:
        checks.append(ParityCheck("runtime-execution", "unsupported", "real OpenHarness runtime was not executed; fixture double used"))

    checks.extend(_cancellation_checks(root, task))
    checks.extend(_failure_checks(root, task))
    checks.extend(_idempotency_checks(reference, adapter, task, reference_result, openharness_result))
    checks.extend(_restart_checks(reference_root, openharness_root, reference_run_id, openharness_run_id))
    checks.extend(_live_guard_checks(reference, adapter, task))
    return ParityReport(adapter.runtime_verified, tuple(checks), reference_run_id, openharness_run_id)


def _runtime_checks(adapter: OpenHarnessAdapter) -> list[ParityCheck]:
    checks: list[ParityCheck] = []
    evidence = getattr(adapter.runtime, "evidence", None)
    for item in getattr(evidence, "checks", ()):
        status = item.get("status", "mismatch")
        if status not in {"match", "translation", "unsupported", "mismatch"}:
            status = "mismatch"
        checks.append(ParityCheck(f"runtime.{item.get('name', 'unknown')}", status, item.get("detail", "")))
    return checks


def _artifact_checks(reference: dict[str, Any], candidate: dict[str, Any]) -> list[ParityCheck]:
    ref_artifacts = {item["kind"]: item for item in reference["artifacts"]}
    candidate_artifacts = {item["kind"]: item for item in candidate["artifacts"]}
    checks: list[ParityCheck] = []
    ref_digests = {kind: item["sha256"] for kind, item in ref_artifacts.items()}
    candidate_digests = {kind: item["sha256"] for kind, item in candidate_artifacts.items()}
    if ref_digests == candidate_digests:
        checks.append(ParityCheck("artifact-content-addressing", "match", "artifact SHA-256 values match by kind"))
    else:
        checks.append(ParityCheck("artifact-content-addressing", "mismatch", "artifact SHA-256 sets differ"))
    ref_lineage = {kind: tuple(item["lineage"]) for kind, item in ref_artifacts.items()}
    candidate_lineage = {kind: tuple(item["lineage"]) for kind, item in candidate_artifacts.items()}
    if ref_lineage == candidate_lineage:
        checks.append(ParityCheck("artifact-lineage", "match", "artifact lineage identifiers are preserved"))
    else:
        checks.append(ParityCheck("artifact-lineage", "mismatch", "artifact lineage differs"))
    if reference["research"]["citations"] == candidate["research"]["citations"]:
        checks.append(ParityCheck("evidence-citations", "match", "evidence IDs and citations are preserved"))
    else:
        checks.append(ParityCheck("evidence-citations", "mismatch", "evidence IDs or citations differ"))
    if reference["risk"] == candidate["risk"]:
        checks.append(ParityCheck("risk-decision", "match", "risk status, reasons, and limits are preserved"))
    else:
        checks.append(ParityCheck("risk-decision", "mismatch", "risk decision differs"))
    return checks


def _compare_task_creation(reference: Task, candidate: Task) -> ParityCheck:
    stable_fields = ("objective", "symbols", "start", "end", "execution_mode", "idempotency_key", "api_version")
    if all(getattr(reference, field) == getattr(candidate, field) for field in stable_fields):
        return ParityCheck(
            "task-creation",
            "translation",
            "stable task fields match; task IDs and creation timestamps are adapter-owned",
        )
    return ParityCheck("task-creation", "mismatch", "task creation fields differ")


def _serialization_checks(reference: dict[str, Any], candidate: dict[str, Any]) -> list[ParityCheck]:
    try:
        for result in (reference, candidate):
            task_from_dict(result["task"])
            from_json(to_json(ResearchResult(**result["research"])), ResearchResult)
            from_json(to_json(BacktestResult(**result["backtest"])), BacktestResult)
            order_plan_from_dict(json.loads(to_json(OrderPlan(**result["order_plan"]))))
            from_json(to_json(RiskDecision(**result["risk"])), RiskDecision)
    except (ContractError, TypeError, ValueError) as exc:
        return [ParityCheck("contract-serialization", "mismatch", str(exc))]
    return [ParityCheck("contract-serialization", "match", "both result paths round-trip through market-os.v1 JSON")]


def _cancellation_checks(root: Path, task: Task) -> list[ParityCheck]:
    reference_cancel = threading.Event()
    adapter_cancel = threading.Event()
    reference_evidence, default_backtest = default_providers()
    adapter_evidence, _ = default_providers()

    class CancellingEvidence:
        def __init__(self, provider: Any, cancel: threading.Event) -> None:
            self.provider = provider
            self.cancel = cancel

        def retrieve(self, *args: Any) -> list[Any]:
            evidence = self.provider.retrieve(*args)
            self.cancel.set()
            return evidence

    reference = MarketWorkflow(
        RunStore(root / "cancel-reference"), CancellingEvidence(reference_evidence, reference_cancel), default_backtest
    )
    adapter = OpenHarnessAdapter(
        RunStore(root / "cancel-openharness"), CancellingEvidence(adapter_evidence, adapter_cancel), default_backtest
    )
    reference_result = reference.run(task, reference_cancel)
    adapter_result = adapter.run(task, adapter_cancel)
    reference_artifacts = RunStore(root / "cancel-reference").artifacts_for(reference_result["run"]["run_id"])
    adapter_artifacts = RunStore(root / "cancel-openharness").artifacts_for(adapter_result["run"]["run_id"])
    if (
        reference_result["run"]["status"] == adapter_result["run"]["status"] == "cancelled"
        and {artifact.kind for artifact in reference_artifacts} == {artifact.kind for artifact in adapter_artifacts}
        and "backtest" not in {artifact.kind for artifact in reference_artifacts}
    ):
        return [ParityCheck("cancellation", "match", "both paths honor cancellation between retrieve and backtest")]
    return [ParityCheck("cancellation", "mismatch", "cancellation status differs")]


def _failure_checks(root: Path, task: Task) -> list[ParityCheck]:
    class Broken:
        def retrieve(self, *_args: Any) -> list[Any]:
            raise RuntimeError("provider unavailable")

    default_backtest = default_providers()[1]
    reference_root = root / "failure-reference"
    openharness_root = root / "failure-openharness"
    reference = MarketWorkflow(RunStore(reference_root), Broken(), default_backtest)
    adapter = OpenHarnessAdapter(RunStore(openharness_root), Broken(), default_backtest)
    errors: list[str] = []
    for runner in (reference, adapter):
        try:
            runner.run(task)
        except RuntimeError as exc:
            errors.append(str(exc))
    reference_run = _latest_run_for_task(reference_root, task.task_id)
    adapter_run = _latest_run_for_task(openharness_root, task.task_id)
    if errors == ["provider unavailable", "provider unavailable"] and reference_run.get("status") == adapter_run.get("status") == "failed":
        return [ParityCheck("failure-normalization", "match", "provider failures preserve the same exception and terminal status")]
    return [ParityCheck("failure-normalization", "mismatch", f"errors={errors}; runs={reference_run}, {adapter_run}")]


def _idempotency_checks(reference: MarketWorkflow, adapter: OpenHarnessAdapter, task: Task, reference_result: dict[str, Any], adapter_result: dict[str, Any]) -> list[ParityCheck]:
    if reference.run(task) == reference_result and adapter.run(task) == adapter_result:
        return [ParityCheck("idempotency", "match", "replay returns the persisted result without a new run")]
    return [ParityCheck("idempotency", "mismatch", "replay result differs")]


def _restart_checks(reference_root: Path, openharness_root: Path, reference_run_id: str, openharness_run_id: str) -> list[ParityCheck]:
    reference = MarketWorkflow(RunStore(reference_root)).inspect_run(reference_run_id)
    adapter = OpenHarnessAdapter(RunStore(openharness_root)).inspect_run(openharness_run_id)
    reference_keys = set(reference)
    if reference_keys == set(adapter) and [event["kind"] for event in reference["events"]] == [event["kind"] for event in adapter["events"]]:
        return [ParityCheck("restart-inspection", "match", "a new adapter instance replays run events and artifacts")]
    return [ParityCheck("restart-inspection", "mismatch", "restart inspection shape or event order differs")]


def _live_guard_checks(reference: MarketWorkflow, adapter: OpenHarnessAdapter, task: Task) -> list[ParityCheck]:
    errors: list[str] = []
    for runner in (reference, adapter):
        try:
            runner.create_task(task.objective, list(task.symbols), task.start, task.end, execution_mode="live")
        except ValueError as exc:
            errors.append(str(exc))
    if errors == ["live execution is disabled in market-os.v1", "live execution is disabled in market-os.v1"]:
        return [ParityCheck("paper-only-enforcement", "match", "both adapters reject live task creation")]
    return [ParityCheck("paper-only-enforcement", "mismatch", f"live guard errors={errors}")]


def _is_utc(value: str) -> bool:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None and parsed.utcoffset().total_seconds() == 0


def _is_monotonic(values: Any) -> bool:
    timestamps = [datetime.fromisoformat(value.replace("Z", "+00:00")) for value in values]
    return timestamps == sorted(timestamps)


def _latest_run_for_task(root: Path, task_id: str) -> dict[str, Any]:
    latest: dict[str, Any] = {}
    runs = root / "runs.jsonl"
    if not runs.exists():
        return latest
    for line in runs.read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            if value.get("task_id") == task_id:
                latest = value
    return latest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="market-os-parity")
    parser.add_argument("--root", default=".market_os-parity")
    parser.add_argument("--fixture", default="market_os/tests/fixtures/contracts/task.json")
    parser.add_argument("--openharness-python", help="isolated Python executable for real OpenHarness verification")
    args = parser.parse_args(argv)
    task = from_json(Path(args.fixture).read_text(encoding="utf-8"), Task)
    runtime = IsolatedOpenHarnessRuntime(args.openharness_python) if args.openharness_python else None
    print(json.dumps(run_parity_harness(args.root, task, runtime=runtime).to_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
