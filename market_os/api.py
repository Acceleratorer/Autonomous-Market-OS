"""Dependency-free HTTP adapter for the versioned workflow."""
from __future__ import annotations

import json
import os
import re
import stat
import threading
import signal
import urllib.parse
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from dataclasses import asdict

from .contracts import ContractError, error_response
from .workflow import MarketWorkflow


OPERATOR_ROOT = Path(__file__).resolve().parents[1] / "apps" / "web" / "operator"


class _B4QueryError(ValueError):
    """A malformed inspection query that should be rejected as a client error."""


class _B4CatalogConflict(RuntimeError):
    """A catalog entry changed during its validated read."""


class _BtcCatalogQueryError(ValueError):
    """A malformed local BTC dataset catalog query."""


class _BtcCandlePageQueryError(ValueError):
    """A malformed bounded BTC candle-page query."""


class _BtcManifestPageQueryError(ValueError):
    """A malformed bounded BTC ingestion-manifest query."""


class _BtcManifestRecordsQueryError(ValueError):
    """A malformed bounded BTC ingestion-record query."""


class _BtcResearchQueryError(ValueError):
    """A malformed bounded BTC research-run query."""


def _parse_page_limit(query: dict[str, list[str]], name: str, default: str = "25") -> int:
    raw_limit = query.get(name, [default])[0]
    if not raw_limit.isascii() or not raw_limit.isdecimal() or len(raw_limit) > 3:
        raise _B4QueryError(f"{name} must be an integer between 1 and 100")
    limit = int(raw_limit)
    if not 1 <= limit <= 100:
        raise _B4QueryError(f"{name} must be an integer between 1 and 100")
    return limit


def _inspection_page_query(query: dict[str, list[str]]) -> tuple[int, int | None, int, str | None]:
    allowed = {"risk_limit", "risk_before_sequence", "order_limit", "order_before_id"}
    if set(query) - allowed:
        raise _B4QueryError("unsupported portfolio inspection query")
    if any(len(values) != 1 for values in query.values()):
        raise _B4QueryError("portfolio inspection query parameters must be unique")

    risk_limit = _parse_page_limit(query, "risk_limit")
    order_limit = _parse_page_limit(query, "order_limit")

    raw_cursor = query.get("risk_before_sequence", [None])[0]
    risk_cursor = None
    if raw_cursor is not None:
        if not raw_cursor or len(raw_cursor) > 64 or not raw_cursor.isascii() or not raw_cursor.isdecimal():
            raise _B4QueryError("risk_before_sequence must be a positive decimal sequence")
        risk_cursor = int(raw_cursor)
        if risk_cursor < 1:
            raise _B4QueryError("risk_before_sequence must be a positive decimal sequence")

    order_cursor = query.get("order_before_id", [None])[0]
    if order_cursor is not None and (
        not order_cursor
        or len(order_cursor) > 160
        or any(ord(character) < 32 for character in order_cursor)
    ):
        raise _B4QueryError("order_before_id must be a bounded order ID")
    return risk_limit, risk_cursor, order_limit, order_cursor


def _inspection_page_query_v2(query: dict[str, list[str]]) -> tuple[int, int | None, int, str | None, int, str | None, int, str | None]:
    allowed = {
        "risk_limit", "risk_before_sequence", "order_limit", "order_before_id",
        "member_limit", "member_after_strategy_id", "reservation_limit", "reservation_before_order_id",
    }
    if set(query) - allowed:
        raise _B4QueryError("unsupported portfolio inspection query")
    if any(len(values) != 1 for values in query.values()):
        raise _B4QueryError("portfolio inspection query parameters must be unique")
    risk_limit, risk_cursor, order_limit, order_cursor = _inspection_page_query({
        name: values for name, values in query.items()
        if name in {"risk_limit", "risk_before_sequence", "order_limit", "order_before_id"}
    })

    member_limit = _parse_page_limit(query, "member_limit")
    reservation_limit = _parse_page_limit(query, "reservation_limit")
    member_cursor = query.get("member_after_strategy_id", [None])[0]
    if member_cursor is not None and (
        not member_cursor
        or len(member_cursor) > 128
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", member_cursor) is None
    ):
        raise _B4QueryError("member_after_strategy_id must be a stable strategy ID")
    reservation_cursor = query.get("reservation_before_order_id", [None])[0]
    if reservation_cursor is not None and (
        not reservation_cursor
        or len(reservation_cursor) > 160
        or any(ord(character) < 32 for character in reservation_cursor)
    ):
        raise _B4QueryError("reservation_before_order_id must be a bounded order ID")
    return risk_limit, risk_cursor, order_limit, order_cursor, member_limit, member_cursor, reservation_limit, reservation_cursor


def _portfolio_catalog_page_query(query: dict[str, list[str]]) -> tuple[int, str | None]:
    if set(query) - {"limit", "after_portfolio_id"}:
        raise _B4QueryError("unsupported portfolio catalog query")
    if any(len(values) != 1 for values in query.values()):
        raise _B4QueryError("portfolio catalog query parameters must be unique")
    limit = _parse_page_limit(query, "limit")
    cursor = query.get("after_portfolio_id", [None])[0]
    if cursor is not None and (
        not cursor
        or len(cursor) > 128
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", cursor) is None
    ):
        raise _B4QueryError("after_portfolio_id must be a stable portfolio ID")
    return limit, cursor


def _btc_dataset_catalog_page_query(query: dict[str, list[str]]) -> tuple[int, str | None]:
    if set(query) - {"limit", "after_dataset_revision"}:
        raise _BtcCatalogQueryError("unsupported BTC dataset catalog query")
    if any(len(values) != 1 for values in query.values()):
        raise _BtcCatalogQueryError("BTC dataset catalog query parameters must be unique")
    try:
        limit = _parse_page_limit(query, "limit")
    except _B4QueryError as exc:
        raise _BtcCatalogQueryError("limit must be an integer between 1 and 100") from exc
    cursor = query.get("after_dataset_revision", [None])[0]
    if cursor is not None and re.fullmatch(
        r"btc-history-(?:[0-9a-f]{20}|manifest-[0-9a-f]{20})",
        cursor,
    ) is None:
        raise _BtcCatalogQueryError("after_dataset_revision must be a BTC history revision")
    return limit, cursor


def _btc_candle_page_query(query: dict[str, list[str]]) -> tuple[int, int | None]:
    allowed = {"limit", "after_open_time_ms"}
    if set(query) - allowed:
        raise _BtcCandlePageQueryError("unsupported BTC candle-page query")
    if any(len(values) != 1 for values in query.values()):
        raise _BtcCandlePageQueryError("BTC candle-page query parameters must be unique")
    try:
        limit = _parse_page_limit(query, "limit")
    except _B4QueryError as exc:
        raise _BtcCandlePageQueryError("limit must be an integer between 1 and 100") from exc
    raw_cursor = query.get("after_open_time_ms", [None])[0]
    if raw_cursor is None:
        return limit, None
    if not raw_cursor or not raw_cursor.isascii() or not raw_cursor.isdecimal() or len(raw_cursor) > 16:
        raise _BtcCandlePageQueryError("after_open_time_ms must be a UTC millisecond timestamp")
    cursor = int(raw_cursor)
    from .btc_history import MAX_JS_DATE_TIME_MS

    if cursor > MAX_JS_DATE_TIME_MS:
        raise _BtcCandlePageQueryError("after_open_time_ms is outside the supported UTC date range")
    return limit, cursor


def _btc_manifest_page_query(query: dict[str, list[str]]) -> tuple[int, str | None]:
    allowed = {"limit", "after_manifest_id"}
    if set(query) - allowed:
        raise _BtcManifestPageQueryError("unsupported BTC manifest-page query")
    if any(len(values) != 1 for values in query.values()):
        raise _BtcManifestPageQueryError("BTC manifest-page query parameters must be unique")
    try:
        limit = _parse_page_limit(query, "limit")
    except _B4QueryError as exc:
        raise _BtcManifestPageQueryError("limit must be an integer between 1 and 100") from exc
    cursor = query.get("after_manifest_id", [None])[0]
    if cursor is not None and re.fullmatch(r"btc-history-manifest-[0-9a-f]{20}", cursor) is None:
        raise _BtcManifestPageQueryError("after_manifest_id must be a BTC ingestion-manifest ID")
    return limit, cursor


def _btc_manifest_records_page_query(query: dict[str, list[str]], resource: str) -> tuple[int, dict[str, str | int | None]]:
    cursor_fields = {
        "outcomes": {"after_outcome_index"},
        "gaps": {"after_start_time_ms"},
        "provenance": {"after_raw_page_sha256", "after_row_index"},
    }.get(resource)
    if cursor_fields is None:
        raise KeyError("BTC ingestion-manifest record resource")
    allowed = {"limit", *cursor_fields}
    if set(query) - allowed:
        raise _BtcManifestRecordsQueryError("unsupported BTC ingestion-record query")
    if any(len(values) != 1 for values in query.values()):
        raise _BtcManifestRecordsQueryError("BTC ingestion-record query parameters must be unique")
    try:
        limit = _parse_page_limit(query, "limit")
    except _B4QueryError as exc:
        raise _BtcManifestRecordsQueryError("limit must be an integer between 1 and 100") from exc

    def decimal_cursor(name: str, maximum: int, digits: int) -> int | None:
        raw = query.get(name, [None])[0]
        if raw is None:
            return None
        if not raw or not raw.isascii() or not raw.isdecimal() or len(raw) > digits:
            raise _BtcManifestRecordsQueryError(f"{name} must be a bounded integer cursor")
        value = int(raw)
        if value > maximum:
            raise _BtcManifestRecordsQueryError(f"{name} is outside the supported range")
        return value

    if resource == "outcomes":
        from .btc_history import MAX_CANDLES

        return limit, {"after_outcome_index": decimal_cursor("after_outcome_index", MAX_CANDLES * 2, 6)}
    if resource == "gaps":
        from .btc_history import MAX_JS_DATE_TIME_MS

        return limit, {"after_start_time_ms": decimal_cursor("after_start_time_ms", MAX_JS_DATE_TIME_MS, 16)}

    raw_hash = query.get("after_raw_page_sha256", [None])[0]
    if raw_hash is not None and re.fullmatch(r"[0-9a-f]{64}", raw_hash) is None:
        raise _BtcManifestRecordsQueryError("after_raw_page_sha256 must be a lowercase SHA-256 fingerprint")
    row_index = decimal_cursor("after_row_index", 999, 3)
    if (raw_hash is None) != (row_index is None):
        raise _BtcManifestRecordsQueryError("provenance cursor fields must be supplied together")
    return limit, {"after_raw_page_sha256": raw_hash, "after_row_index": row_index}


def _btc_research_page_query(query: dict[str, list[str]], engine: str) -> tuple[int, str | None]:
    if set(query) - {"limit", "after_run_id"}:
        raise _BtcResearchQueryError("unsupported BTC research-run query")
    if any(len(values) != 1 for values in query.values()):
        raise _BtcResearchQueryError("BTC research-run query parameters must be unique")
    try:
        limit = _parse_page_limit(query, "limit")
    except _B4QueryError as exc:
        raise _BtcResearchQueryError("limit must be an integer between 1 and 100") from exc
    cursor = query.get("after_run_id", [None])[0]
    pattern = rf"btc-{engine}-[0-9a-f]{{20}}"
    if cursor is not None and re.fullmatch(pattern, cursor) is None:
        raise _BtcResearchQueryError("after_run_id must match the selected BTC research engine")
    return limit, cursor


def _is_reparse_point(path: Path) -> bool:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    is_junction = getattr(path, "is_junction", None)
    reparse_attribute = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return (
        stat.S_ISLNK(info.st_mode)
        or bool(getattr(info, "st_file_attributes", 0) & reparse_attribute)
        or (callable(is_junction) and is_junction())
    )


def _configured_btc_history_store(store_root: Path):
    from .btc_history import HistoryError, HistoryStore

    resolved_store_root = store_root.resolve()
    history_root = resolved_store_root / "btc-history"
    if _is_reparse_point(history_root):
        raise HistoryError("catalog_integrity_error", "BTC history store must remain local")
    if history_root.exists():
        if not history_root.is_dir():
            raise HistoryError("catalog_integrity_error", "BTC history store must be a directory")
        resolved_history_root = history_root.resolve(strict=True)
        if resolved_history_root.parent != resolved_store_root:
            raise HistoryError("catalog_integrity_error", "BTC history store must remain local")
    catalog_path = history_root / "catalog.duckdb"
    if _is_reparse_point(catalog_path):
        raise HistoryError("catalog_integrity_error", "BTC history catalog must be a local file")
    if catalog_path.exists() and not catalog_path.is_file():
        raise HistoryError("catalog_integrity_error", "BTC history catalog must be a local file")
    if not catalog_path.is_file():
        return None
    return HistoryStore(history_root, read_only=True)


def _configured_btc_research_store(workflow_root: Path, engine: str):
    from .btc_research_inspection import BtcResearchInspectionStore, ResearchInspectionError

    env_name = "MARKET_OS_BTC_B2_STORE_ROOT" if engine == "b2" else "MARKET_OS_BTC_B3_STORE_ROOT"
    configured_root = Path(os.environ[env_name]) if os.environ.get(env_name) else workflow_root / f"btc-{engine}"
    if _is_reparse_point(configured_root):
        raise ResearchInspectionError("BTC research store must remain a local configured directory")
    try:
        if not configured_root.exists():
            return None
        if not configured_root.is_dir():
            raise ResearchInspectionError("BTC research store must be a directory")
        resolved_root = configured_root.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ResearchInspectionError("BTC research store cannot be resolved safely") from exc
    return BtcResearchInspectionStore(resolved_root, engine)


def _legacy_resource_page_query(
    query: dict[str, list[str]], resource: str,
) -> tuple[int | None, str | int | None, str | None]:
    page_fields = {
        "genesis": ("member_limit", "member_after_strategy_id"),
        "reservations": ("reservation_limit", "reservation_before_order_id"),
        "orders": ("order_limit", "order_before_id"),
        "fills": ("fill_limit", "fill_before_id"),
        "risk": ("risk_limit", "risk_before_sequence"),
        "approvals": ("approval_limit", "approval_before_sequence"),
        "ledger": ("ledger_limit", "ledger_before_sequence"),
    }
    item_id = query.get("id", [None])[0]
    if resource in page_fields:
        limit_name, cursor_name = page_fields[resource]
        allowed = {limit_name, cursor_name, "id"}
        if set(query) - allowed:
            raise _B4QueryError(f"unsupported {resource} query")
        if any(len(values) != 1 for values in query.values()):
            raise _B4QueryError(f"{resource} query parameters must be unique")
        limit = _parse_page_limit(query, limit_name)
        raw_cursor = query.get(cursor_name, [None])[0]
        cursor: str | int | None = raw_cursor
        if raw_cursor is not None:
            if resource in {"risk", "approvals", "ledger"}:
                if not raw_cursor or len(raw_cursor) > 64 or not raw_cursor.isascii() or not raw_cursor.isdecimal() or int(raw_cursor) < 1:
                    raise _B4QueryError(f"{cursor_name} must be a positive decimal sequence")
                cursor = int(raw_cursor)
            elif resource == "genesis":
                if not raw_cursor or len(raw_cursor) > 128 or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", raw_cursor) is None:
                    raise _B4QueryError(f"{cursor_name} must be a stable strategy ID")
            elif not raw_cursor or len(raw_cursor) > 160 or any(ord(character) < 32 for character in raw_cursor):
                raise _B4QueryError(f"{cursor_name} must be a bounded ID")
        if item_id is not None and (
            not item_id or len(item_id) > 160 or any(ord(character) < 32 for character in item_id)
        ):
            raise _B4QueryError("id must be a bounded non-empty resource ID")
        if item_id is not None and cursor is not None:
            raise _B4QueryError("id cannot be combined with a page cursor")
        return limit, cursor, item_id

    if resource == "snapshot":
        raise _B4QueryError("full snapshot export is not available over HTTP; use bounded resources")
    if query:
        raise _B4QueryError(f"{resource} does not accept query parameters")
    return None, None, None


def make_handler(
    workflow: MarketWorkflow,
    *,
    request_timeout: float = 5.0,
    service_log_path: str | Path | None = None,
) -> type[BaseHTTPRequestHandler]:
    log_lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def setup(self) -> None:
            super().setup()
            self.request.settimeout(request_timeout)
            self.request_id = uuid.uuid4().hex

        def _trusted_host(self) -> bool:
            value = self.headers.get("Host", "")
            if not value or any(character.isspace() or character in "/?#@" for character in value):
                return False
            parsed = None
            try:
                parsed = urllib.parse.urlsplit(f"//{value}")
                host = parsed.hostname
                parsed.port  # Validate malformed or out-of-range ports.
            except ValueError:
                host = None
            return (
                parsed is not None
                and host is not None
                and host.lower() in {"127.0.0.1", "localhost", "::1"}
                and parsed.username is None
                and parsed.password is None
                and not parsed.path
                and not parsed.query
                and not parsed.fragment
            )

        def _reject_untrusted_host(self) -> bool:
            if self._trusted_host():
                return False
            self._send(403, {"error": "loopback host required", "api_version": "market-os.v1"})
            self._audit(403, error_type="UntrustedHost")
            return True

        def _audit(self, status: int, *, run_id: str | None = None, error_type: str | None = None) -> None:
            if service_log_path is None:
                return
            record = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "request_id": self.request_id,
                "method": self.command,
                "path": urllib.parse.urlsplit(self.path).path,
                "status": status,
                "run_id": run_id,
                "error_type": error_type,
            }
            destination = Path(service_log_path)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with log_lock, destination.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, sort_keys=True) + "\n")

        def _send(self, status: int, payload: dict[str, Any]) -> None:
            raw = json.dumps(payload, sort_keys=True).encode()
            self.send_response(status)
            self.send_header("X-Request-ID", self.request_id)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _send_html(self, status: int, body: str) -> None:
            raw = body.encode("utf-8")
            self.send_response(status)
            self.send_header("X-Request-ID", self.request_id)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _send_static(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("X-Request-ID", self.request_id)
            self.send_header("Content-Type", content_type)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src data:; base-uri 'none'; frame-ancestors 'none'")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _operator_asset(self) -> bool:
            parsed = urllib.parse.urlsplit(self.path)
            if parsed.path != "/operator" and not parsed.path.startswith("/operator/"):
                return False
            status = 200
            error_type = None
            try:
                if parsed.query:
                    raise ValueError("operator shell does not accept query parameters")
                relative = urllib.parse.unquote(parsed.path.removeprefix("/operator")).strip("/")
                if relative in {"", "operator.js", "operator.css", "app.js", "styles.css"}:
                    asset = "index.html" if not relative else relative
                else:
                    parts = relative.split("/")
                    if len(parts) not in {1, 2} or any(not part or part in {".", ".."} for part in parts):
                        raise KeyError("operator asset")
                    if len(parts) == 2 and parts[1] not in {""}:
                        raise KeyError("operator asset")
                    asset = "index.html"
                # The old asset URLs remain read-only compatibility aliases while
                # the product-facing filenames use the operator prefix.
                asset = {"app.js": "operator.js", "styles.css": "operator.css"}.get(asset, asset)
                path = (OPERATOR_ROOT / asset).resolve()
                if path.parent != OPERATOR_ROOT.resolve() or not path.is_file():
                    raise KeyError("operator asset")
                content_type = {
                    "index.html": "text/html; charset=utf-8",
                    "operator.js": "text/javascript; charset=utf-8",
                    "operator.css": "text/css; charset=utf-8",
                }[asset]
                self._send_static(200, path.read_bytes(), content_type)
            except KeyError:
                status = 404
                error_type = "KeyError"
                self._send(404, {"error": "operator asset not found", "api_version": "market-os.u5-4.operator.v1"})
            except (OSError, ValueError) as exc:
                status = 400 if isinstance(exc, ValueError) else 404
                error_type = type(exc).__name__
                self._send(status, {"error": {"code": "operator_request_error", "message": str(exc), "api_version": "market-os.u5-4.operator.v1"}})
            finally:
                self._audit(status, error_type=error_type)
            return True

        @staticmethod
        def _b4_cell(value: Any) -> str:
            import html

            return html.escape(str(value), quote=True)

        def _b4_dashboard(self, broker: Any) -> str:
            summary = broker.inspect_summary_compact()
            order_page = broker.inspect_orders_page(limit=25)
            risk_page = broker.inspect_risk_page(limit=8)
            risk = risk_page["records"]
            orders = order_page["orders"]
            rows = "".join(
                "<tr>"
                + "".join(f"<td>{self._b4_cell(order.get(key))}</td>" for key in ("order_id", "side", "order_type", "quantity", "state"))
                + "</tr>"
                for order in orders
            )
            risk_rows = "".join(
                f"<li>{self._b4_cell(record.get('kind'))}: {self._b4_cell(record.get('reason_code'))}</li>"
                for record in risk
            )
            return (
                "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
                "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
                "<title>Market OS paper portfolio</title></head><body><main>"
                "<h1>Market OS paper portfolio</h1><p>synthetic-only · paper-only · read-only</p>"
                f"<p>Portfolio: {self._b4_cell(summary['portfolio_id'])}</p>"
                f"<p>Cash USDT: {self._b4_cell(summary['cash_usdt'])} · BTC: {self._b4_cell(summary['btc_quantity'])} · Mark: {self._b4_cell(summary['mark_price'])}</p>"
                f"<p>Market events: {self._b4_cell(summary['market_event_count'])}</p>"
                "<h2>Recent orders</h2><p>Showing up to 25 most recent orders.</p><table><thead><tr><th>Order</th><th>Side</th><th>Type</th><th>Quantity</th><th>State</th></tr></thead>"
                f"<tbody>{rows}</tbody></table><h2>Risk outcomes</h2><ul>{risk_rows}</ul></main></body></html>"
            )

        def _operator_index(self, catalog: dict[str, Any]) -> str:
            portfolios = catalog["portfolios"]
            page = catalog["page"]
            rows = "".join(
                f'<li><a href="/operator/{self._b4_cell(item["portfolio_id"])}/">'
                f'{self._b4_cell(item["portfolio_id"])}</a>'
                f'<span>{self._b4_cell(item["mode"])} · {self._b4_cell(item["open_orders"])} open orders</span></li>'
                for item in portfolios
            )
            empty = "<p>No local paper portfolios found.</p>" if not portfolios else ""
            navigation = []
            if page["after_portfolio_id"] is not None:
                first_query = urllib.parse.urlencode({"limit": page["limit"]})
                navigation.append(f'<a href="/operator/?{first_query}" aria-label="First portfolio page">First page</a>')
            if page["has_more"]:
                query = urllib.parse.urlencode({"limit": page["limit"], "after_portfolio_id": page["next_after_portfolio_id"]})
                navigation.append(f'<a href="/operator/?{self._b4_cell(query)}" aria-label="Next portfolio page">Next page</a>')
            skipped_note = ""
            if page["skipped_count"]:
                noun = "candidate" if page["skipped_count"] == 1 else "candidates"
                skipped_note = f'<span role="status"> · Skipped {page["skipped_count"]} unreadable portfolio {noun} while filling this page.</span>'
            page_nav = (
                f'<nav aria-label="Portfolio pages"><span>Showing {len(portfolios)} portfolios on this page.</span>'
                + (" " + " ".join(navigation) if navigation else "")
                + skipped_note
                + "</nav>"
            )
            return (
                "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
                "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
                "<meta name=\"robots\" content=\"noindex, nofollow\">"
                "<link rel=\"stylesheet\" href=\"/operator/operator.css\">"
                "<title>Market OS · Local Portfolios</title></head><body><main>"
                "<header class=\"masthead\"><div><p class=\"eyebrow\">Market OS / local operator</p>"
                "<h1>Local paper portfolios</h1><p class=\"lede\">Validated local portfolio directory for read-only inspection.</p></div>"
                "<span class=\"status-pill\">SYNTHETIC · PAPER ONLY</span></header>"
                f"<section class=\"boundary\"><strong>Local access only.</strong> {self._b4_cell('Portfolio state is read from validated local broker stores.')}</section>"
                f"<ul class=\"catalog-list\">{rows}</ul>{empty}{page_nav}</main></body></html>"
            )

        def _operator_catalog(self, limit: int = 25, after_portfolio_id: str | None = None) -> dict[str, Any]:
            from .portfolio_broker import B41Broker, BrokerStale

            root = (workflow.store.root / "b4-paper").resolve()
            portfolios = []
            if not root.is_dir():
                if after_portfolio_id is not None:
                    raise _B4QueryError("after_portfolio_id is not in this portfolio catalog")
                return {"portfolios": portfolios, "page": {
                    "limit": limit,
                    "after_portfolio_id": after_portfolio_id,
                    "has_more": False,
                    "next_after_portfolio_id": None,
                    "skipped_count": 0,
                }}
            if after_portfolio_id is not None:
                if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", after_portfolio_id) is None:
                    raise _B4QueryError("after_portfolio_id is not in this portfolio catalog")
                cursor_directory = root / after_portfolio_id
                if (
                    cursor_directory.parent != root
                    or _is_reparse_point(cursor_directory)
                    or not cursor_directory.is_dir()
                ):
                    raise _B4QueryError("after_portfolio_id is not in this portfolio catalog")
                policy_path = cursor_directory / "policy.json"
                try:
                    resolved_cursor = cursor_directory.resolve(strict=True)
                    resolved_policy = policy_path.resolve(strict=True)
                except (OSError, RuntimeError) as exc:
                    raise _B4QueryError("after_portfolio_id is not in this portfolio catalog") from exc
                if (
                    resolved_cursor.parent != root
                    or _is_reparse_point(policy_path)
                    or not resolved_policy.is_file()
                    or resolved_policy.parent != resolved_cursor
                ):
                    raise _B4QueryError("after_portfolio_id is not in this portfolio catalog")
                try:
                    cursor_broker = B41Broker.open(root, after_portfolio_id)
                    cursor_broker.inspect_summary_compact()
                except BrokerStale as exc:
                    raise _B4CatalogConflict("portfolio state changed during catalog inspection; retry") from exc
                except (OSError, TypeError, ValueError) as exc:
                    raise _B4QueryError("after_portfolio_id is not in this portfolio catalog") from exc
            directories = sorted(
                (
                    path for path in root.iterdir()
                    if (after_portfolio_id is None or path.name > after_portfolio_id)
                    and not _is_reparse_point(path)
                    and path.is_dir()
                    and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", path.name) is not None
                ),
                key=lambda path: path.name,
            )
            has_more = False
            skipped_count = 0
            for directory in directories:
                try:
                    broker = B41Broker.open(root, directory.name)
                    genesis = broker.genesis
                    summary = broker.inspect_summary_compact()
                    if len(portfolios) == limit:
                        has_more = True
                        break
                    member_count = len(broker.genesis.member_strategy_ids) or 1
                    portfolios.append({
                        "portfolio_id": genesis.portfolio_id,
                        "mode": "shared" if genesis.shared_portfolio_id else "isolated",
                        "member_count": member_count,
                        "open_orders": summary["open_orders"],
                    })
                except BrokerStale as exc:
                    raise _B4CatalogConflict("portfolio state changed during catalog inspection; retry") from exc
                except (OSError, TypeError, ValueError):
                    skipped_count += 1
                    continue
            next_after = portfolios[-1]["portfolio_id"] if has_more and portfolios else None
            return {"portfolios": portfolios, "page": {
                "limit": limit,
                "after_portfolio_id": after_portfolio_id,
                "has_more": has_more,
                "next_after_portfolio_id": next_after,
                "skipped_count": skipped_count,
            }}

        def do_POST(self) -> None:  # noqa: N802
            if self._reject_untrusted_host():
                return
            if self.path == "/v1/btc/history/ingest":
                status = 500
                try:
                    size = int(self.headers.get("Content-Length", "0"))
                    body = json.loads(self.rfile.read(size))
                    from .btc_history import HistoryStore

                    result = HistoryStore(body["store_root"]).ingest_fixture(body["fixture"])
                    status = 200
                    self._send(200, asdict(result))
                except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                    status = 400
                    self._send(400, {"error": {"code": "invalid_request", "message": str(exc), "api_version": "market-os.btc-history.v1"}})
                except Exception as exc:  # pragma: no cover
                    self._send(500, {"error": str(exc)})
                finally:
                    self._audit(status)
                return
            if self.path == "/v1/btc/b2/runs":
                status = 500
                try:
                    size = int(self.headers.get("Content-Length", "0"))
                    body = json.loads(self.rfile.read(size))
                    from .btc_features import B2Config, B2Store, run_b2
                    from .btc_history import HistoryStore

                    result = run_b2(
                        HistoryStore(body["history_store_root"]),
                        body["dataset_revision"],
                        B2Store(body.get("store_root", str(workflow.store.root / "btc-b2"))),
                        B2Config(body.get("experiment_id", "btc-b2-offline"), body.get("as_of")),
                    )
                    status = 200
                    self._send(200, result)
                except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                    status = 400
                    self._send(400, {"error": {"code": "invalid_request", "message": str(exc), "api_version": "market-os.btc-b2.v1"}})
                except Exception as exc:  # pragma: no cover - defensive transport boundary
                    self._send(500, {"error": str(exc)})
                finally:
                    self._audit(status)
                return
            if self.path == "/v1/btc/b3/runs":
                status = 500
                try:
                    size = int(self.headers.get("Content-Length", "0"))
                    body = json.loads(self.rfile.read(size))
                    from .btc_jev_evaluation import B3Store, RecordedJevAdapter, run_b3
                    from .btc_history import HistoryStore

                    result = run_b3(
                        HistoryStore(body["history_store_root"]),
                        body["dataset_revision"],
                        RecordedJevAdapter.from_path(body["fixture"]),
                        B3Store(body.get("store_root", str(workflow.store.root / "btc-b3"))),
                        experiment_id=body.get("experiment_id", "btc-b3-jev-offline"),
                    )
                    status = 200
                    self._send(200, result)
                except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                    status = 400
                    self._send(400, {"error": {"code": "invalid_request", "message": str(exc), "api_version": "market-os.btc-b3.v1"}})
                except Exception as exc:  # pragma: no cover - defensive transport boundary
                    self._send(500, {"error": str(exc)})
                finally:
                    self._audit(status)
                return
            if self.path == "/v1/benchmarks":
                status = 500
                try:
                    size = int(self.headers.get("Content-Length", "0"))
                    body = json.loads(self.rfile.read(size))
                    from .quality_benchmark import run_quality_benchmark

                    result = run_quality_benchmark(workflow.store.root, body.get("fixture"))
                    status = 200
                    self._send(200, result)
                except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                    status = 400
                    self._send(400, {"error": {"code": "invalid_request", "message": str(exc), "api_version": "market-os.v1"}})
                except Exception as exc:  # pragma: no cover - defensive transport boundary
                    self._send(500, {"error": str(exc)})
                finally:
                    self._audit(status)
                return
            if self.path != "/v1/tasks":
                self._send(404, {"error": "not found"})
                self._audit(404)
                return
            status = 500
            run_id = None
            error_type = None
            try:
                size = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(size))
                selected = workflow
                if body.get("provider") or body.get("backtest_provider") or body.get("summary_provider"):
                    from .provider_selection import selected_workflow

                    if body.get("summary_provider") is None:
                        selected = selected_workflow(
                            workflow,
                            body.get("provider", "fixture"),
                            body.get("backtest_provider"),
                        )
                    else:
                        selected = selected_workflow(
                            workflow,
                            body.get("provider", "fixture"),
                            body.get("backtest_provider"),
                            body.get("summary_provider"),
                        )
                task = selected.create_task(body["objective"], body["symbols"], body["start"], body["end"], execution_mode=body.get("execution_mode", "paper"), idempotency_key=self.headers.get("Idempotency-Key"))
                result = selected.run(task)
                run_id = result.get("run", {}).get("run_id")
                status = 200
                self._send(200, result)
            except ContractError as exc:
                status = 400
                error_type = type(exc).__name__
                self._send(400, {"error": error_response(exc)})
            except (KeyError, TypeError, ValueError, json.JSONDecodeError, TimeoutError) as exc:
                status = 408 if isinstance(exc, TimeoutError) else 400
                error_type = type(exc).__name__
                self._send(status, {"error": {"code": "request_timeout" if status == 408 else "invalid_request", "message": str(exc), "api_version": "market-os.v1"}})
            except Exception as exc:  # pragma: no cover - defensive transport boundary
                error_type = type(exc).__name__
                self._send(500, {"error": str(exc)})
            finally:
                self._audit(status, run_id=run_id, error_type=error_type)

        def do_GET(self) -> None:  # noqa: N802
            if self._reject_untrusted_host():
                return
            if urllib.parse.urlsplit(self.path).path in {"/operator", "/operator/"}:
                status = 200
                error_type = None
                try:
                    parsed = urllib.parse.urlsplit(self.path)
                    try:
                        query = urllib.parse.parse_qs(parsed.query, strict_parsing=True, keep_blank_values=True, max_num_fields=2)
                    except ValueError as exc:
                        raise _B4QueryError("malformed operator catalog query") from exc
                    limit, cursor = _portfolio_catalog_page_query(query)
                    self._send_html(200, self._operator_index(self._operator_catalog(limit, cursor)))
                except _B4QueryError as exc:
                    status = 400
                    error_type = type(exc).__name__
                    self._send(400, {"error": {"code": "operator_catalog_query_rejected", "message": str(exc), "api_version": "market-os.u5-6.operator.v1"}})
                except _B4CatalogConflict:
                    status = 409
                    error_type = "B4CatalogConflict"
                    self._send_html(409, "<!doctype html><html lang=\"en\"><meta charset=\"utf-8\"><title>Portfolio state changed</title><body><main><h1>Portfolio state changed</h1><p>Reload the local portfolio registry and try again.</p></main></body></html>")
                finally:
                    self._audit(status, error_type=error_type)
                return
            if self._operator_asset():
                return
            if self.path == "/healthz":
                self._send(200, {"api_version": "market-os.v1", "service": "market-os", "status": "ok"})
                self._audit(200)
                return
            if self.path == "/readyz":
                self._send(200, {"api_version": "market-os.v1", "service": "market-os", "status": "ready"})
                self._audit(200)
                return
            if urllib.parse.urlsplit(self.path).path == "/v1/b4/portfolios":
                status = 200
                error_type = None
                try:
                    parsed = urllib.parse.urlsplit(self.path)
                    try:
                        query = urllib.parse.parse_qs(parsed.query, strict_parsing=True, keep_blank_values=True, max_num_fields=2)
                    except ValueError as exc:
                        raise _B4QueryError("malformed portfolio catalog query") from exc
                    limit, cursor = _portfolio_catalog_page_query(query)
                    catalog = self._operator_catalog(limit, cursor)
                    self._send(200, {"api_version": "market-os.b4-catalog@v1", **catalog})
                except _B4QueryError as exc:
                    status = 400
                    error_type = type(exc).__name__
                    self._send(400, {"error": {"code": "b4_catalog_query_rejected", "message": str(exc), "api_version": "market-os.b4-catalog@v1"}})
                except _B4CatalogConflict:
                    status = 409
                    error_type = "B4CatalogConflict"
                    self._send(409, {"error": {"code": "b4_catalog_conflict", "message": "portfolio state changed during catalog inspection; retry", "api_version": "market-os.b4-catalog@v1"}})
                finally:
                    self._audit(status, error_type=error_type)
                return
            request_path = urllib.parse.urlsplit(self.path).path
            b4_prefix = next(
                (prefix for prefix in ("/v1/b4/portfolios/", "/v2/b4/portfolios/", "/v3/b4/portfolios/") if request_path.startswith(prefix)),
                None,
            )
            if b4_prefix is not None:
                inspection_version = b4_prefix.split("/", 2)[1]
                status = 200
                error_type = None
                resource = "summary"
                try:
                    parsed = urllib.parse.urlsplit(self.path)
                    parts = parsed.path[len(b4_prefix):].split("/")
                    if len(parts) not in (1, 2) or not parts[0]:
                        raise KeyError("B4 portfolio resource")
                    resource = parts[1] if len(parts) == 2 else "summary"
                    try:
                        query = urllib.parse.parse_qs(
                            parsed.query,
                            strict_parsing=True,
                            keep_blank_values=True,
                            max_num_fields=8,
                        )
                    except ValueError as exc:
                        raise _B4QueryError("malformed B4 inspection query") from exc
                    if resource == "inspection":
                        (risk_limit, risk_before_sequence, order_limit, order_before_id,
                         member_limit, member_after_strategy_id, reservation_limit,
                         reservation_before_order_id) = _inspection_page_query_v2(query)
                    else:
                        if inspection_version in {"v2", "v3"}:
                            raise KeyError(f"B4 {inspection_version} exposes only portfolio inspection")
                        legacy_limit, legacy_cursor, legacy_item_id = _legacy_resource_page_query(query, resource)
                    from .portfolio_broker import B41Broker, InspectionCursorError

                    broker = B41Broker.open(workflow.store.root / "b4-paper", parts[0])
                    if resource == "inspection":
                        try:
                            orders = broker.inspect_orders_page(order_limit, order_before_id)
                            risk = broker.inspect_risk_page(risk_limit, risk_before_sequence)
                            members = broker.inspect_members_page(member_limit, member_after_strategy_id)
                            reservations = broker.inspect_reservations_page(reservation_limit, reservation_before_order_id)
                        except InspectionCursorError as exc:
                            raise _B4QueryError("inspection cursor is not in this portfolio") from exc
                        if inspection_version == "v1":
                            genesis = broker.inspect_genesis_compact()
                            if genesis.get("shared_portfolio_id") is not None:
                                genesis["member_strategy_ids"] = members["strategy_ids"]
                            genesis["members_page"] = members["page"]
                            result = {
                                "api_version": "market-os.b4-portfolio-inspection@v1",
                                "portfolio_id": parts[0],
                                "summary": broker.inspect_summary_compact(),
                                "genesis": genesis,
                                "reservations": reservations,
                                "orders": orders,
                                "risk": risk,
                            }
                        elif inspection_version == "v2":
                            result = {
                                "api_version": "market-os.b4-portfolio-inspection@v2",
                                "portfolio_id": parts[0],
                                "summary": broker.inspect_summary_compact(),
                                "genesis": broker.inspect_genesis_compact(),
                                "members": members,
                                "reservations": reservations,
                                "orders": orders,
                                "risk": risk,
                            }
                        else:
                            result = {
                                "api_version": "market-os.b4-portfolio-inspection@v3",
                                "portfolio_id": parts[0],
                                "summary": broker.inspect_summary_compact(),
                                "genesis": broker.inspect_genesis_compact(),
                                "members": members,
                                "reservations": reservations,
                                "orders": orders,
                                "risk": risk,
                                "equity_history": broker.inspect_equity_history_page(100),
                            }
                        self._send(200, result)
                    elif resource == "dashboard":
                        if query:
                            raise _B4QueryError("dashboard does not accept query parameters")
                        self._send_html(200, self._b4_dashboard(broker))
                    else:
                        try:
                            if resource == "summary":
                                result = broker.inspect_summary_compact()
                            elif resource == "genesis":
                                result = broker.inspect_genesis_compact()
                                members = broker.inspect_members_page(legacy_limit, legacy_cursor)
                                if result.get("shared_portfolio_id") is not None:
                                    result["member_strategy_ids"] = members["strategy_ids"]
                                result["members_page"] = members["page"]
                            elif resource == "reservations":
                                result = broker.inspect_reservations_page(legacy_limit, legacy_cursor)
                            elif resource == "orders":
                                result = (
                                    broker.inspect_item_jsonable(resource, legacy_item_id)
                                    if legacy_item_id is not None
                                    else broker.inspect_orders_page(legacy_limit, legacy_cursor)
                                )
                            elif resource == "fills":
                                result = (
                                    broker.inspect_item_jsonable(resource, legacy_item_id)
                                    if legacy_item_id is not None
                                    else broker.inspect_fills_page(legacy_limit, legacy_cursor)
                                )
                            elif resource in {"risk", "approvals", "ledger"}:
                                result = broker.inspect_event_page(resource, legacy_limit, legacy_cursor, legacy_item_id)
                            else:
                                result = broker.inspect_jsonable(resource)
                        except InspectionCursorError as exc:
                            raise _B4QueryError("inspection cursor is not in this portfolio") from exc
                        self._send(200, result)
                except _B4QueryError as exc:
                    status = 400
                    error_type = type(exc).__name__
                    api_version = f"market-os.b4-portfolio-inspection@{inspection_version}" if resource == "inspection" else "market-os.b4-1.paper-broker@v1"
                    self._send(400, {"error": {"code": "invalid_request", "message": str(exc), "api_version": api_version}})
                except KeyError:
                    status = 404
                    error_type = "KeyError"
                    self._send(404, {"error": "B4 portfolio or resource not found", "api_version": "market-os.b4-1.paper-broker@v1"})
                except (OSError, TypeError, ValueError) as exc:
                    status = 409
                    error_type = type(exc).__name__
                    self._send(409, {"error": {"code": "b4_inspection_error", "message": str(exc), "api_version": "market-os.b4-1.paper-broker@v1"}})
                finally:
                    self._audit(status, error_type=error_type)
                return
            btc_dataset_candles_prefix = "/v1/btc/history/datasets/"
            parsed_btc_dataset_path = urllib.parse.urlsplit(self.path)
            btc_dataset_route_parts = parsed_btc_dataset_path.path.removeprefix(btc_dataset_candles_prefix).split("/") if parsed_btc_dataset_path.path.startswith(btc_dataset_candles_prefix) else []
            if len(btc_dataset_route_parts) in {2, 3, 4} and btc_dataset_route_parts[1] == "manifests":
                status = 200
                error_type = None
                api_version = "market-os.btc-history-manifests@v1"
                try:
                    from .btc_history import HistoryError

                    if len(btc_dataset_route_parts) == 2:
                        try:
                            query = urllib.parse.parse_qs(
                                parsed_btc_dataset_path.query,
                                strict_parsing=True,
                                keep_blank_values=True,
                                max_num_fields=2,
                            )
                        except ValueError as exc:
                            raise _BtcManifestPageQueryError("malformed BTC manifest-page query") from exc
                        limit, cursor = _btc_manifest_page_query(query)
                    elif len(btc_dataset_route_parts) == 4:
                        api_version = "market-os.btc-history-manifest-records@v1"
                        resource = btc_dataset_route_parts[3]
                        try:
                            query = urllib.parse.parse_qs(
                                parsed_btc_dataset_path.query,
                                strict_parsing=True,
                                keep_blank_values=True,
                                max_num_fields=4,
                            )
                        except ValueError as exc:
                            raise _BtcManifestRecordsQueryError("malformed BTC ingestion-record query") from exc
                        limit, cursors = _btc_manifest_records_page_query(query, resource)

                    store = _configured_btc_history_store(workflow.store.root)
                    if store is None:
                        raise KeyError(btc_dataset_route_parts[0])
                    if len(btc_dataset_route_parts) == 2:
                        result = store.inspect_manifests_page(
                            btc_dataset_route_parts[0],
                            limit=limit,
                            after_manifest_id=cursor,
                        )
                    elif len(btc_dataset_route_parts) == 4:
                        if resource == "outcomes":
                            result = store.inspect_manifest_outcomes_page(
                                btc_dataset_route_parts[0], btc_dataset_route_parts[2],
                                limit=limit, after_outcome_index=cursors["after_outcome_index"],
                            )
                        elif resource == "gaps":
                            result = store.inspect_manifest_gaps_page(
                                btc_dataset_route_parts[0], btc_dataset_route_parts[2],
                                limit=limit, after_start_time_ms=cursors["after_start_time_ms"],
                            )
                        else:
                            result = store.inspect_manifest_provenance_page(
                                btc_dataset_route_parts[0], btc_dataset_route_parts[2],
                                limit=limit,
                                after_raw_page_sha256=cursors["after_raw_page_sha256"],
                                after_row_index=cursors["after_row_index"],
                            )
                    else:
                        if parsed_btc_dataset_path.query:
                            raise _BtcManifestPageQueryError("manifest detail does not accept query parameters")
                        result = {"manifest": store.inspect_manifest_record(btc_dataset_route_parts[0], btc_dataset_route_parts[2])}
                    self._send(200, {"api_version": api_version, **result})
                except _BtcManifestPageQueryError as exc:
                    status = 400
                    error_type = type(exc).__name__
                    self._send(400, {"error": {"code": "btc_history_manifest_query_rejected", "message": str(exc), "api_version": "market-os.btc-history-manifests@v1"}})
                except _BtcManifestRecordsQueryError as exc:
                    status = 400
                    error_type = type(exc).__name__
                    self._send(400, {"error": {"code": "btc_history_manifest_records_query_rejected", "message": str(exc), "api_version": "market-os.btc-history-manifest-records@v1"}})
                except KeyError:
                    status = 404
                    error_type = "KeyError"
                    self._send(404, {"error": "BTC dataset, ingestion manifest, or record cursor not found", "api_version": api_version})
                except (HistoryError, OSError, RuntimeError, ValueError) as exc:
                    status = 409
                    error_type = type(exc).__name__
                    error_code = "btc_history_manifest_records_integrity_error" if api_version.endswith("records@v1") else "btc_history_manifests_integrity_error"
                    self._send(409, {"error": {"code": error_code, "message": "BTC history manifest storage failed its integrity checks", "api_version": api_version}})
                finally:
                    self._audit(status, error_type=error_type)
                return
            if parsed_btc_dataset_path.path.startswith(btc_dataset_candles_prefix):
                status = 200
                error_type = None
                try:
                    from .btc_history import HistoryError

                    try:
                        query = urllib.parse.parse_qs(
                            parsed_btc_dataset_path.query,
                            strict_parsing=True,
                            keep_blank_values=True,
                            max_num_fields=2,
                        )
                    except ValueError as exc:
                        raise _BtcCandlePageQueryError("malformed BTC candle-page query") from exc
                    limit, cursor = _btc_candle_page_query(query)
                    parts = parsed_btc_dataset_path.path[len(btc_dataset_candles_prefix):].split("/")
                    if len(parts) != 2 or parts[1] != "candles":
                        raise KeyError("BTC dataset candle resource")
                    store = _configured_btc_history_store(workflow.store.root)
                    if store is None:
                        raise KeyError(parts[0])
                    result = store.inspect_candles_page(
                        parts[0],
                        limit=limit,
                        after_open_time_ms=cursor,
                    )
                    self._send(200, {"api_version": "market-os.btc-history-candles@v1", **result})
                except _BtcCandlePageQueryError as exc:
                    status = 400
                    error_type = type(exc).__name__
                    self._send(400, {"error": {"code": "btc_history_candle_query_rejected", "message": str(exc), "api_version": "market-os.btc-history-candles@v1"}})
                except KeyError:
                    status = 404
                    error_type = "KeyError"
                    self._send(404, {"error": "BTC history dataset or candle cursor not found", "api_version": "market-os.btc-history-candles@v1"})
                except (HistoryError, OSError, ValueError) as exc:
                    status = 409
                    error_type = type(exc).__name__
                    self._send(409, {"error": {"code": "btc_history_candles_integrity_error", "message": str(exc), "api_version": "market-os.btc-history-candles@v1"}})
                finally:
                    self._audit(status, error_type=error_type)
                return
            if parsed_btc_dataset_path.path == "/v1/btc/history/datasets":
                status = 200
                error_type = None
                try:
                    try:
                        query = urllib.parse.parse_qs(
                            parsed_btc_dataset_path.query,
                            strict_parsing=True,
                            keep_blank_values=True,
                            max_num_fields=2,
                        )
                    except ValueError as exc:
                        raise _BtcCatalogQueryError("malformed BTC dataset catalog query") from exc
                    limit, cursor = _btc_dataset_catalog_page_query(query)

                    from .btc_history import HistoryError

                    store = _configured_btc_history_store(workflow.store.root)
                    if store is None:
                        if cursor is not None:
                            raise KeyError(cursor)
                        result = {
                            "datasets": [],
                            "page": {
                                "limit": limit,
                                "after_dataset_revision": None,
                                "has_more": False,
                                "next_after_dataset_revision": None,
                            },
                        }
                    else:
                        result = store.inspect_datasets_page(
                            limit=limit,
                            after_dataset_revision=cursor,
                        )
                    self._send(200, {"api_version": "market-os.btc-history-catalog@v1", **result})
                except _BtcCatalogQueryError as exc:
                    status = 400
                    error_type = type(exc).__name__
                    self._send(400, {"error": {"code": "btc_history_catalog_query_rejected", "message": str(exc), "api_version": "market-os.btc-history-catalog@v1"}})
                except KeyError:
                    status = 404
                    error_type = "KeyError"
                    self._send(404, {"error": "BTC history dataset revision not found", "api_version": "market-os.btc-history-catalog@v1"})
                except (HistoryError, OSError) as exc:
                    status = 409
                    error_type = type(exc).__name__
                    self._send(409, {"error": {"code": "btc_history_catalog_integrity_error", "message": str(exc), "api_version": "market-os.btc-history-catalog@v1"}})
                finally:
                    self._audit(status, error_type=error_type)
                return
            if urllib.parse.urlsplit(self.path).path == "/v1/btc/history/readiness":
                status = 200
                error_type = None
                try:
                    parsed = urllib.parse.urlsplit(self.path)
                    query = urllib.parse.parse_qs(parsed.query)
                    from .btc_history import plan_historical_readiness

                    result = plan_historical_readiness(int(query["cutoff-ms"][0]))
                    self._send(200, result)
                except (KeyError, TypeError, ValueError) as exc:
                    status = 400
                    error_type = type(exc).__name__
                    self._send(400, {"error": {"code": "invalid_request", "message": str(exc), "api_version": "market-os.btc-history-readiness.v1"}})
                finally:
                    self._audit(status, error_type=error_type)
                return
            synthetic_prefix = "/v1/synthetic/sessions/"
            if urllib.parse.urlsplit(self.path).path.startswith(synthetic_prefix):
                status = 200
                error_type = None
                try:
                    parsed = urllib.parse.urlsplit(self.path)
                    parts = parsed.path[len(synthetic_prefix):].split("/")
                    if len(parts) != 2:
                        raise KeyError("synthetic session resource")
                    from .synthetic_session_api import SyntheticSessionStore

                    query = urllib.parse.parse_qs(parsed.query)
                    store = SyntheticSessionStore(query.get("store_root", [str(workflow.store.root / "synthetic")])[0])
                    session_id, resource = parts
                    if resource == "dashboard":
                        self._send_html(200, store.dashboard_html(session_id))
                    else:
                        self._send(200, store.inspect(session_id, resource))
                except KeyError:
                    status = 404
                    error_type = "KeyError"
                    self._send(404, {"error": "synthetic session or resource not found", "api_version": "market-os.b3-9.synthetic-api.v1"})
                except ValueError as exc:
                    status = 409
                    error_type = type(exc).__name__
                    self._send(409, {"error": {"code": "synthetic_integrity_error", "message": str(exc), "api_version": "market-os.b3-9.synthetic-api.v1"}})
                finally:
                    self._audit(status, error_type=error_type)
                return
            btc_prefix = "/v1/btc/history/"
            if self.path.startswith(btc_prefix):
                status = 200
                error_type = None
                try:
                    parsed = urllib.parse.urlsplit(self.path)
                    parts = parsed.path[len(btc_prefix):].split("/")
                    if len(parts) != 2:
                        raise KeyError("BTC dataset resource")
                    from .btc_history import HistoryStore

                    query = urllib.parse.parse_qs(parsed.query)
                    store = HistoryStore(query.get("store_root", [str(workflow.store.root / "btc-history")])[0])
                    dataset_id, resource = parts
                    if resource == "manifest":
                        result = store.inspect_manifest(dataset_id)
                    elif resource == "candles":
                        start_ms = int(query["start-ms"][0]) if "start-ms" in query else None
                        end_ms = int(query["end-ms"][0]) if "end-ms" in query else None
                        result = store.inspect_candles(dataset_id, start_time_ms=start_ms, end_time_ms=end_ms)
                    elif resource == "outcomes":
                        result = store.inspect_outcomes(dataset_id)
                    elif resource == "provenance":
                        result = store.inspect_provenance(dataset_id)
                    elif resource == "gaps":
                        result = store.inspect_gaps(dataset_id)
                    elif resource == "replay":
                        result = store.replay(dataset_id)
                    else:
                        raise KeyError("BTC dataset resource")
                    self._send(200, result)
                except KeyError:
                    status = 404
                    error_type = "KeyError"
                    self._send(404, {"error": "BTC dataset or resource not found"})
                except ValueError as exc:
                    status = 409
                    error_type = type(exc).__name__
                    self._send(409, {"error": {"code": "btc_history_integrity_error", "message": str(exc), "api_version": "market-os.btc-history.v1"}})
                finally:
                    self._audit(status, error_type=error_type)
                return
            btc_research_prefix = "/v1/btc/research/"
            if urllib.parse.urlsplit(self.path).path.startswith(btc_research_prefix):
                status = 200
                error_type = None
                try:
                    from .btc_research_inspection import ResearchInspectionError

                    parsed = urllib.parse.urlsplit(self.path)
                    parts = parsed.path[len(btc_research_prefix):].split("/")
                    if len(parts) not in {2, 3} or parts[0] not in {"b2", "b3"} or parts[1] != "runs":
                        raise KeyError("BTC research resource")
                    engine = parts[0]
                    store = _configured_btc_research_store(workflow.store.root, engine)
                    if len(parts) == 2:
                        try:
                            query = urllib.parse.parse_qs(
                                parsed.query,
                                strict_parsing=True,
                                keep_blank_values=True,
                                max_num_fields=2,
                            )
                        except ValueError as exc:
                            raise _BtcResearchQueryError("malformed BTC research-run query") from exc
                        limit, cursor = _btc_research_page_query(query, engine)
                        if store is None:
                            if cursor is not None:
                                raise KeyError(cursor)
                            result = {
                                "engine": engine,
                                "runs": [],
                                "page": {"limit": limit, "after_run_id": None, "has_more": False, "next_after_run_id": None},
                            }
                        else:
                            result = store.list_runs_page(limit=limit, after_run_id=cursor)
                    else:
                        if parsed.query:
                            raise _BtcResearchQueryError("BTC research run detail does not accept query parameters")
                        if store is None:
                            raise KeyError(parts[2])
                        result = store.inspect_run(parts[2])
                    self._send(200, {"api_version": "market-os.btc-research-inspection@v1", **result})
                except _BtcResearchQueryError as exc:
                    status = 400
                    error_type = type(exc).__name__
                    self._send(400, {"error": {"code": "btc_research_query_rejected", "message": str(exc), "api_version": "market-os.btc-research-inspection@v1"}})
                except KeyError:
                    status = 404
                    error_type = "KeyError"
                    self._send(404, {"error": "BTC research run not found", "api_version": "market-os.btc-research-inspection@v1"})
                except (ResearchInspectionError, OSError, RuntimeError, TypeError, ValueError):
                    status = 409
                    error_type = "ResearchInspectionError"
                    self._send(409, {"error": {"code": "btc_research_integrity_error", "message": "BTC research run failed its local integrity checks", "api_version": "market-os.btc-research-inspection@v1"}})
                finally:
                    self._audit(status, error_type=error_type)
                return
            btc_b2_prefix = "/v1/btc/b2/"
            if self.path.startswith(btc_b2_prefix):
                status = 200
                error_type = None
                try:
                    parsed = urllib.parse.urlsplit(self.path)
                    parts = parsed.path[len(btc_b2_prefix):].split("/")
                    if len(parts) != 2:
                        raise KeyError("B2 run resource")
                    from .btc_features import B2Store

                    query = urllib.parse.parse_qs(parsed.query)
                    store = B2Store(query.get("store_root", [str(workflow.store.root / "btc-b2")])[0], read_only=True)
                    result = store.inspect(parts[0], parts[1])
                    self._send(200, result)
                except KeyError:
                    status = 404
                    error_type = "KeyError"
                    self._send(404, {"error": "B2 run not found"})
                except ValueError as exc:
                    status = 409
                    error_type = type(exc).__name__
                    self._send(409, {"error": {"code": "btc_b2_integrity_error", "message": str(exc), "api_version": "market-os.btc-b2.v1"}})
                finally:
                    self._audit(status, error_type=error_type)
                return
            btc_b3_prefix = "/v1/btc/b3/"
            if self.path.startswith(btc_b3_prefix):
                status = 200
                error_type = None
                try:
                    parsed = urllib.parse.urlsplit(self.path)
                    parts = parsed.path[len(btc_b3_prefix):].split("/")
                    if len(parts) != 2:
                        raise KeyError("B3 run resource")
                    from .btc_jev_evaluation import B3Store

                    query = urllib.parse.parse_qs(parsed.query)
                    store = B3Store(query.get("store_root", [str(workflow.store.root / "btc-b3")])[0], read_only=True)
                    result = store.inspect(parts[0], parts[1])
                    self._send(200, result)
                except KeyError:
                    status = 404
                    error_type = "KeyError"
                    self._send(404, {"error": "B3 run not found"})
                except ValueError as exc:
                    status = 409
                    error_type = type(exc).__name__
                    self._send(409, {"error": {"code": "btc_b3_integrity_error", "message": str(exc), "api_version": "market-os.btc-b3.v1"}})
                finally:
                    self._audit(status, error_type=error_type)
                return
            connectivity_prefix = "/v1/btc/connectivity/"
            if self.path.startswith(connectivity_prefix):
                status = 200
                error_type = None
                try:
                    parsed = urllib.parse.urlsplit(self.path)
                    parts = parsed.path[len(connectivity_prefix):].split("/")
                    if len(parts) != 2:
                        raise KeyError("connectivity resource")
                    from .btc_connectivity import ConnectivityStore

                    query = urllib.parse.parse_qs(parsed.query)
                    store = ConnectivityStore(query.get("store_root", [str(workflow.store.root / "btc-connectivity")])[0])
                    result = store.inspect(parts[0], parts[1])
                    self._send(200, result)
                except KeyError:
                    status = 404
                    error_type = "KeyError"
                    self._send(404, {"error": "connectivity probe or resource not found"})
                except ValueError as exc:
                    status = 409
                    error_type = type(exc).__name__
                    self._send(409, {"error": {"code": "btc_connectivity_integrity_error", "message": str(exc), "api_version": "market-os.u3-api-connectivity.v1"}})
                finally:
                    self._audit(status, error_type=error_type)
                return
            benchmark_prefix = "/v1/benchmarks/"
            if self.path.startswith(benchmark_prefix):
                status = 200
                error_type = None
                try:
                    parts = self.path[len(benchmark_prefix):].split("/")
                    if len(parts) not in {2, 3}:
                        raise KeyError("benchmark resource")
                    from .quality_benchmark import BenchmarkStore

                    result = BenchmarkStore(workflow.store.root).inspect(parts[0], parts[1], parts[2] if len(parts) == 3 else None)
                    self._send(200, result)
                except KeyError:
                    status = 404
                    error_type = "KeyError"
                    self._send(404, {"error": "benchmark not found"})
                except ValueError as exc:
                    status = 409
                    error_type = type(exc).__name__
                    self._send(409, {"error": {"code": "benchmark_integrity_error", "message": str(exc), "api_version": "market-os.v1"}})
                finally:
                    self._audit(status, error_type=error_type)
                return
            prefix = "/v1/runs/"
            if not self.path.startswith(prefix):
                self._send(404, {"error": "not found"})
                self._audit(404)
                return
            status = 200
            error_type = None
            try:
                suffix = self.path[len(prefix):]
                parts = suffix.split("/")
                if len(parts) == 1:
                    result = workflow.inspect_run(parts[0])
                elif len(parts) in {3, 4} and parts[1] == "research":
                    resource = parts[2]
                    item_id = parts[3] if len(parts) == 4 else None
                    if resource not in {"documents", "passages", "claims", "unsupported-claims", "passage-claims", "citations", "model-summary", "inferences", "lineage"}:
                        self._send(404, {"error": "research resource not found"})
                        self._audit(404)
                        return
                    result = workflow.inspect_resource(parts[0], resource, item_id)
                else:
                    self._send(404, {"error": "run resource not found"})
                    self._audit(404)
                    return
                self._send(200, result)
            except KeyError:
                status = 404
                error_type = "KeyError"
                self._send(404, {"error": "run or research item not found"})
            except ValueError as exc:
                status = 409
                error_type = type(exc).__name__
                self._send(409, {"error": {"code": "research_integrity_error", "message": str(exc), "api_version": "market-os.v1"}})
            finally:
                self._audit(status, error_type=error_type)

        def log_message(self, *_args: Any) -> None:
            return

    return Handler


def serve(
    workflow: MarketWorkflow,
    host: str = "127.0.0.1",
    port: int = 8787,
    *,
    request_timeout: float = 5.0,
    service_log_path: str | Path | None = None,
) -> None:
    if request_timeout <= 0:
        raise ValueError("request_timeout must be positive")
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("market-os service is loopback-only")
    workflow.recover_inflight_runs()
    server = ThreadingHTTPServer((host, port), make_handler(workflow, request_timeout=request_timeout, service_log_path=service_log_path))
    server.daemon_threads = True
    handled_signals = [signal.SIGTERM]
    if hasattr(signal, "SIGBREAK"):
        handled_signals.append(signal.SIGBREAK)
    previous_signals = {value: signal.getsignal(value) for value in handled_signals}

    def stop_server(_signum: int, _frame: object) -> None:
        threading.Thread(target=server.shutdown, daemon=True).start()

    for value in handled_signals:
        signal.signal(value, stop_server)
    try:
        server.serve_forever()
    finally:
        for value, previous in previous_signals.items():
            signal.signal(value, previous)
        server.server_close()
