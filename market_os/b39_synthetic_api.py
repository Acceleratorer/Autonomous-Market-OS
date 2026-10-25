"""Read-only local inspection for B3.8 synthetic session artifacts."""
from __future__ import annotations

import copy
import hashlib
import html
import json
from pathlib import Path
import re
from typing import Any, Mapping

from .b35_strategy_replay import StrategyReplayReport
from .b36_accounting import SyntheticAccountingReport


API_VERSION = "market-os.b3-9.synthetic-api.v1"
MANIFEST_SCHEMA = "market-os.b3-8.synthetic-session-manifest@v1"
SESSION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
RESOURCE_FILES = {"replay": "strategy-replay.json", "accounting": "accounting.json"}


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _object(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an object")
    return value


def _load_json(path: Path, field: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise KeyError(f"{field} not found") from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {field}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{field} must contain a JSON object")
    return value


def _without_fingerprint(value: Mapping[str, Any]) -> tuple[dict[str, Any], str]:
    fingerprint = value.get("fingerprint")
    if not isinstance(fingerprint, str):
        raise ValueError("artifact fingerprint is required")
    projection = copy.deepcopy(dict(value))
    projection.pop("fingerprint", None)
    if _fingerprint(projection) != fingerprint:
        raise ValueError("artifact fingerprint mismatch")
    return projection, fingerprint


class SyntheticSessionStore:
    """Read and validate immutable B3.8 session artifacts from local disk."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()

    def _session_path(self, session_id: str) -> Path:
        if not isinstance(session_id, str) or not SESSION_ID.fullmatch(session_id):
            raise KeyError("invalid synthetic session ID")
        path = (self.root / session_id).resolve()
        if path.parent != self.root:
            raise KeyError("invalid synthetic session path")
        if not path.is_dir():
            raise KeyError("synthetic session not found")
        return path

    def _validated(self, session_id: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        directory = self._session_path(session_id)
        manifest_raw = _load_json(directory / "manifest.json", "synthetic manifest")
        manifest_projection, manifest_fingerprint = _without_fingerprint(manifest_raw)
        if manifest_projection.get("schema") != MANIFEST_SCHEMA or manifest_projection.get("synthetic_only") is not True:
            raise ValueError("unsupported or non-synthetic session manifest")
        files = _object(manifest_projection.get("files"), "manifest files")
        if dict(files) != RESOURCE_FILES:
            raise ValueError("manifest file mapping is invalid")

        replay_raw = _load_json(directory / RESOURCE_FILES["replay"], "strategy replay")
        replay_projection, replay_fingerprint = _without_fingerprint(replay_raw)
        replay_report = StrategyReplayReport(_canonical(replay_projection), replay_fingerprint)
        replay_payload = replay_report.to_dict()
        if manifest_projection.get("replay_fingerprint") != replay_fingerprint:
            raise ValueError("manifest replay fingerprint mismatch")

        accounting_raw = _load_json(directory / RESOURCE_FILES["accounting"], "accounting report")
        accounting_projection, accounting_fingerprint = _without_fingerprint(accounting_raw)
        accounting_report = SyntheticAccountingReport(_canonical(accounting_projection), accounting_fingerprint)
        accounting_payload = accounting_report.to_dict()
        if manifest_projection.get("accounting_fingerprint") != accounting_fingerprint:
            raise ValueError("manifest accounting fingerprint mismatch")
        if accounting_payload.get("source_replay_fingerprint") != replay_fingerprint:
            raise ValueError("accounting source replay fingerprint mismatch")
        manifest = {**manifest_projection, "fingerprint": manifest_fingerprint}
        return manifest, replay_payload, accounting_payload

    def inspect(self, session_id: str, resource: str) -> dict[str, Any]:
        manifest, replay, accounting = self._validated(session_id)
        if resource == "manifest":
            return manifest
        if resource == "replay":
            return replay
        if resource == "accounting":
            return accounting
        if resource == "dashboard":
            return {"schema": API_VERSION, "session_id": session_id, "manifest": manifest, "accounting": accounting}
        raise KeyError("synthetic session resource not found")

    def list_sessions(self) -> tuple[str, ...]:
        if not self.root.is_dir():
            return ()
        return tuple(sorted(
            path.name
            for path in self.root.iterdir()
            if path.is_dir() and SESSION_ID.fullmatch(path.name) and (path / "manifest.json").is_file()
        ))

    def dashboard_html(self, session_id: str) -> str:
        manifest, replay, accounting = self._validated(session_id)
        metrics = _object(accounting.get("accounting"), "accounting summary")
        decision_counts = _object(accounting.get("decision_counts"), "decision counts")
        rows = [
            ("Session", session_id),
            ("Replay fingerprint", manifest["replay_fingerprint"]),
            ("Accounting fingerprint", manifest["accounting_fingerprint"]),
            ("Observations", accounting.get("observation_count")),
            ("Decisions", ", ".join(f"{key}: {value}" for key, value in sorted(decision_counts.items()))),
            ("Fills", metrics.get("fill_count")),
            ("Turnover (USDT)", metrics.get("turnover_usdt")),
            ("Fees (USDT)", metrics.get("total_fees_usdt")),
            ("Realized PnL (USDT)", metrics.get("realized_pnl_usdt")),
            ("Unrealized PnL (USDT)", metrics.get("unrealized_pnl_usdt")),
            ("Final BTC", metrics.get("final_btc_quantity")),
        ]
        table = "".join(f"<tr><th>{html.escape(str(key))}</th><td>{html.escape(str(value))}</td></tr>" for key, value in rows)
        replay_state = _object(replay.get("replay"), "replay")
        replay_status = html.escape(str(replay_state.get("status", "unknown")))
        observations = replay.get("observations")
        if not isinstance(observations, list):
            raise ValueError("replay observations must be an array")
        timeline = "".join(
            "<tr>"
            + "".join(f"<td>{html.escape(str(value))}</td>" for value in (
                item.get("event_id"),
                item.get("replay_step", {}).get("event_time_ms") if isinstance(item.get("replay_step"), Mapping) else None,
                item.get("decision", {}).get("action", "missing_signal") if isinstance(item.get("decision"), Mapping) else "missing_signal",
                item.get("command_state"),
            ))
            + "</tr>"
            for item in (_object(item, "observation") for item in observations)
        )
        fills = _object(replay_state.get("final_venue_snapshot"), "final venue snapshot").get("fills")
        if not isinstance(fills, list):
            raise ValueError("replay fills must be an array")
        fill_rows = "".join(
            "<tr>"
            + "".join(f"<td>{html.escape(str(fill.get(key)))}</td>" for key in ("event_id", "order_id", "filled_quantity", "fill_price", "fee_amount"))
            + "</tr>"
            for fill in (_object(fill, "fill") for fill in fills)
        )
        return (
            "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>Market OS synthetic session</title>"
            "<style>body{font-family:system-ui,sans-serif;max-width:960px;margin:2rem auto;padding:0 1rem;line-height:1.45;background:#f6f7f9;color:#18202a}"
            "main{background:#fff;border:1px solid #d9dee7;border-radius:12px;padding:1.5rem;box-shadow:0 4px 18px #18202a12}"
            "h1{margin-top:0}.badge{display:inline-block;padding:.25rem .55rem;border-radius:999px;background:#e5f5ea;color:#176b36;font-size:.85rem}"
            "table{border-collapse:collapse;width:100%;margin:1rem 0 2rem;display:block;overflow-x:auto}th,td{text-align:left;border-bottom:1px solid #e5e8ee;padding:.65rem;white-space:nowrap}"
            ".summary th{width:34%;color:#526070}"
            "code{font-size:.85rem;word-break:break-all}</style></head><body><main>"
            f"<h1>BTCUSDT synthetic session</h1><span class=\"badge\">synthetic-only · read-only</span>"
            f"<p>Replay status: <strong>{replay_status}</strong>. This view is contract and accounting observability; it is not predictive evidence or a promotion decision.</p>"
            f"<h2>Accounting</h2><table class=\"summary\">{table}</table>"
            f"<h2>Replay timeline</h2><table><thead><tr><th>Event</th><th>Time ms</th><th>Decision</th><th>Command state</th></tr></thead><tbody>{timeline}</tbody></table>"
            f"<h2>Fills</h2><table><thead><tr><th>Event</th><th>Order</th><th>Quantity</th><th>Price</th><th>Fee</th></tr></thead><tbody>{fill_rows}</tbody></table>"
            f"</main></body></html>"
        )


__all__ = ["API_VERSION", "SyntheticSessionStore"]
