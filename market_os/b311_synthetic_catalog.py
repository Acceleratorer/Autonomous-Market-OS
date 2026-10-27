"""Read-only catalog and comparison for validated B3.8 synthetic sessions."""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping

from .b39_synthetic_api import SyntheticSessionStore


CATALOG_SCHEMA = "market-os.b3-11.synthetic-session-catalog@v1"
COMPARISON_SCHEMA = "market-os.b3-11.synthetic-session-comparison@v1"
INTERPRETATION = "synthetic session observability only; no predictive evidence or promotion decision"


def _object(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an object")
    return value


def _number(value: Any, field: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{field} must be a finite number")
    return value


def _summary(store: SyntheticSessionStore, session_id: str) -> dict[str, Any]:
    dashboard = store.inspect(session_id, "dashboard")
    manifest = _object(dashboard.get("manifest"), "manifest")
    accounting = _object(dashboard.get("accounting"), "accounting")
    metrics = _object(accounting.get("accounting"), "accounting summary")
    decision_counts = accounting.get("decision_counts")
    if not isinstance(decision_counts, Mapping):
        raise ValueError("decision_counts must be an object")
    return {
        "session_id": session_id,
        "manifest_fingerprint": manifest["fingerprint"],
        "replay_fingerprint": manifest["replay_fingerprint"],
        "accounting_fingerprint": manifest["accounting_fingerprint"],
        "observation_count": accounting.get("observation_count"),
        "decision_counts": dict(sorted((str(k), v) for k, v in decision_counts.items())),
        "fill_count": metrics.get("fill_count"),
        "turnover_usdt": metrics.get("turnover_usdt"),
        "total_fees_usdt": metrics.get("total_fees_usdt"),
        "realized_pnl_usdt": metrics.get("realized_pnl_usdt"),
        "unrealized_pnl_usdt": metrics.get("unrealized_pnl_usdt"),
        "total_pnl_usdt": metrics.get("total_pnl_usdt"),
        "final_btc_quantity": metrics.get("final_btc_quantity"),
    }


@dataclass(frozen=True)
class SyntheticSessionCatalog:
    """Validated, deterministic view of all local synthetic session artifacts."""

    store: SyntheticSessionStore

    def __post_init__(self) -> None:
        if not isinstance(self.store, SyntheticSessionStore):
            raise ValueError("catalog requires a typed synthetic session store")

    def to_dict(self) -> dict[str, Any]:
        sessions = tuple(_summary(self.store, session_id) for session_id in self.store.list_sessions())
        return {
            "schema": CATALOG_SCHEMA,
            "synthetic_only": True,
            "interpretation": INTERPRETATION,
            "session_count": len(sessions),
            "sessions": list(sessions),
        }

    def compare(self, left_session_id: str, right_session_id: str) -> dict[str, Any]:
        if left_session_id == right_session_id:
            raise ValueError("comparison requires two distinct session IDs")
        left = _summary(self.store, left_session_id)
        right = _summary(self.store, right_session_id)
        fields = (
            "observation_count",
            "fill_count",
            "turnover_usdt",
            "total_fees_usdt",
            "realized_pnl_usdt",
            "unrealized_pnl_usdt",
            "total_pnl_usdt",
            "final_btc_quantity",
        )
        delta = {field: _number(right[field], f"right.{field}") - _number(left[field], f"left.{field}") for field in fields}
        return {
            "schema": COMPARISON_SCHEMA,
            "synthetic_only": True,
            "interpretation": INTERPRETATION,
            "delta_direction": "right_minus_left",
            "left": left,
            "right": right,
            "delta": delta,
        }


def catalog_sessions(store: SyntheticSessionStore) -> dict[str, Any]:
    return SyntheticSessionCatalog(store).to_dict()


def compare_sessions(store: SyntheticSessionStore, left_session_id: str, right_session_id: str) -> dict[str, Any]:
    return SyntheticSessionCatalog(store).compare(left_session_id, right_session_id)


__all__ = [
    "CATALOG_SCHEMA",
    "COMPARISON_SCHEMA",
    "INTERPRETATION",
    "SyntheticSessionCatalog",
    "catalog_sessions",
    "compare_sessions",
]
