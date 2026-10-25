"""Synthetic replay accounting summaries; no performance or promotion claims."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any, Mapping

from .b35_strategy_replay import SESSION_SCHEMA, StrategyReplayReport


ACCOUNTING_SCHEMA = "market-os.b3-6.synthetic-accounting-report@v1"
INTERPRETATION = (
    "synthetic replay accounting observability only; "
    "no predictive evidence, profitability claim, or promotion approval"
)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _finite(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{field} must be finite")
    return float(value)


def _nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an object")
    return value


def _counts(values: list[str]) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))


@dataclass(frozen=True)
class SyntheticAccountingReport:
    """Canonical accounting projection derived from one strategy replay."""

    canonical_payload: str
    fingerprint: str

    def __post_init__(self) -> None:
        try:
            payload = json.loads(self.canonical_payload)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError("accounting payload must be canonical JSON") from exc
        if not isinstance(payload, dict) or payload.get("schema") != ACCOUNTING_SCHEMA:
            raise ValueError("unsupported accounting schema")
        if payload.get("synthetic_only") is not True or payload.get("interpretation") != INTERPRETATION:
            raise ValueError("accounting report must preserve the synthetic boundary")
        if "fingerprint" in payload:
            raise ValueError("accounting projection cannot contain its own fingerprint")
        if self.canonical_payload != _canonical(payload) or self.fingerprint != _fingerprint(payload):
            raise ValueError("accounting fingerprint mismatch")

    def to_dict(self) -> dict[str, Any]:
        return {**json.loads(self.canonical_payload), "fingerprint": self.fingerprint}


def _validated_replay_payload(replay_report: StrategyReplayReport) -> dict[str, Any]:
    if not isinstance(replay_report, StrategyReplayReport):
        raise ValueError("accounting requires a typed strategy replay report")
    # Reconstruct to fail closed if a caller bypassed the frozen report instance.
    validated = StrategyReplayReport(replay_report.canonical_payload, replay_report.fingerprint)
    payload = validated.to_dict()
    if payload.get("schema") != SESSION_SCHEMA:
        raise ValueError("accounting source must be a B3.5 strategy replay")
    return payload


def build_synthetic_accounting_report(replay_report: StrategyReplayReport) -> SyntheticAccountingReport:
    """Summarize decisions and venue accounting from one immutable replay."""
    payload = _validated_replay_payload(replay_report)
    observations = payload.get("observations")
    replay = _mapping(payload.get("replay"), "replay")
    final_snapshot = _mapping(replay.get("final_venue_snapshot"), "final_venue_snapshot")
    position = _mapping(final_snapshot.get("position"), "final position")
    venue_config = _mapping(payload.get("venue_config"), "venue_config")
    if not isinstance(observations, list):
        raise ValueError("observations must be a list")

    actions: list[str] = []
    command_states: list[str] = []
    accepted_count = 0
    rejected_count = 0
    rejection_reasons: list[str] = []
    for observation in observations:
        item = _mapping(observation, "observation")
        command_states.append(str(item.get("command_state")))
        decision = item.get("decision")
        actions.append("missing_signal" if decision is None else str(_mapping(decision, "decision").get("action")))
        step = _mapping(item.get("replay_step"), "replay_step")
        accepted = step.get("accepted_commands")
        rejected = step.get("rejected_commands")
        if not isinstance(accepted, list) or not isinstance(rejected, list):
            raise ValueError("replay step command lists are required")
        accepted_count += len(accepted)
        rejected_count += len(rejected)
        for rejected_command in rejected:
            rejection_reasons.append(str(_mapping(rejected_command, "rejected command").get("reason")))

    fills = final_snapshot.get("fills")
    pending_commands = replay.get("pending_commands")
    terminal_commands = payload.get("unexecuted_end_of_stream")
    if not isinstance(fills, list) or not isinstance(pending_commands, list) or not isinstance(terminal_commands, list):
        raise ValueError("replay accounting lists are required")

    filled_notional = 0.0
    spread_cost = 0.0
    slippage_cost = 0.0
    fee_total = 0.0
    for fill in fills:
        record = _mapping(fill, "fill")
        quantity = _finite(record.get("filled_quantity"), "filled_quantity")
        price = _finite(record.get("fill_price"), "fill_price")
        filled_notional += quantity * price
        spread_cost += _finite(record.get("spread_cost"), "spread_cost")
        slippage_cost += _finite(record.get("slippage_cost"), "slippage_cost")
        fee_total += _finite(record.get("fee_amount"), "fee_amount")

    total_notional = _finite(position.get("total_notional_usdt"), "total_notional_usdt")
    if not math.isclose(filled_notional, total_notional, rel_tol=1e-9, abs_tol=1e-9):
        raise ValueError("fill turnover does not match venue position accounting")
    position_fee_total = _finite(position.get("total_fees_usdt"), "total_fees_usdt")
    if not math.isclose(fee_total, position_fee_total, rel_tol=1e-9, abs_tol=1e-9):
        raise ValueError("fill fees do not match venue position accounting")

    realized = _finite(position.get("realized_pnl_usdt"), "realized_pnl_usdt")
    unrealized = _finite(position.get("unrealized_pnl_usdt"), "unrealized_pnl_usdt")
    summary = {
        "initial_cash_usdt": _finite(venue_config.get("initial_cash_usdt"), "initial_cash_usdt"),
        "initial_btc_quantity": _finite(venue_config.get("initial_btc_quantity"), "initial_btc_quantity"),
        "final_cash_usdt": _finite(position.get("cash_usdt"), "cash_usdt"),
        "final_btc_quantity": _finite(position.get("btc_quantity"), "btc_quantity"),
        "mark_price_usdt": _finite(position.get("mark_price"), "mark_price"),
        "fill_count": _nonnegative_int(len(fills), "fill_count"),
        "turnover_usdt": filled_notional,
        "total_notional_usdt": total_notional,
        "total_fees_usdt": position_fee_total,
        "spread_cost_usdt": spread_cost,
        "slippage_cost_usdt": slippage_cost,
        "realized_pnl_usdt": realized,
        "unrealized_pnl_usdt": unrealized,
        "total_pnl_usdt": realized + unrealized,
    }
    report_base = {
        "schema": ACCOUNTING_SCHEMA,
        "synthetic_only": True,
        "interpretation": INTERPRETATION,
        "source_replay_schema": payload["schema"],
        "source_replay_fingerprint": payload["fingerprint"],
        "observation_count": len(observations),
        "decision_counts": _counts(actions),
        "command_state_counts": _counts(command_states),
        "accepted_command_count": accepted_count,
        "rejected_command_count": rejected_count,
        "rejection_reasons": _counts(rejection_reasons),
        "pending_command_count": len(pending_commands),
        "unexecuted_end_of_stream_count": len(terminal_commands),
        "accounting": summary,
    }
    return SyntheticAccountingReport(_canonical(report_base), _fingerprint(report_base))


def verify_synthetic_accounting(first: SyntheticAccountingReport, second: SyntheticAccountingReport) -> bool:
    return isinstance(first, SyntheticAccountingReport) and first == second


__all__ = [
    "ACCOUNTING_SCHEMA",
    "INTERPRETATION",
    "SyntheticAccountingReport",
    "build_synthetic_accounting_report",
    "verify_synthetic_accounting",
]
