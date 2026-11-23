"""Finite, local-only Binance BTCUSDT candle capture for live chart data."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import time
import uuid

from .btc_connectivity import (
    BINANCE_BASE_URL,
    BINANCE_KLINE_PATH,
    BinancePublicAdapter,
    ConnectivityError,
)
from .btc_history import resolve_local_storage_root


POLL_SECONDS = 180
MAX_POLLS = 432  # At most 21h 36m of scheduled polling, plus bounded requests.
KLINES_PER_POLL = 5
SCHEMA = "market-os.btc-realtime-capture.v1"
CAPTURE_RUN_PATTERN = re.compile(r"^btc-live-\d{8}T\d{6}Z-[0-9a-f]{8}$")
MAX_CAPTURE_MANIFEST_BYTES = 16 * 1024
MAX_CAPTURE_CANDLE_BYTES = 4 * 1024 * 1024
MAX_CAPTURE_POLL_BYTES = 1024 * 1024
LIVE_CHART_CANDLE_LIMIT = 64


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _append_jsonl(path: Path, record: dict[str, object]) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(record, sort_keys=True, separators=(",", ":"), allow_nan=False))
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def _write_manifest(path: Path, manifest: dict[str, object]) -> None:
    temporary = path.with_suffix(".json.tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(manifest, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Capture a finite BTCUSDT Spot 1m candle sample locally every three minutes."
    )
    parser.add_argument("--allow-live-capture", action="store_true", required=True)
    parser.add_argument("--samples", type=int, required=True, help=f"1 to {MAX_POLLS} polls; each poll is one request")
    parser.add_argument("--store-root", help="local Market OS store root; defaults to MARKET_OS_STORE_ROOT or .market_os")
    return parser


def _capture_timestamp_ms(value: object) -> int:
    if not isinstance(value, str):
        raise ValueError("capture candle timestamp is malformed")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("capture candle timestamp is malformed") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError("capture candle timestamp must be UTC")
    return int(parsed.timestamp() * 1000)


def inspect_latest_capture(store_root: str | Path) -> dict[str, object]:
    """Read the newest bounded local capture for the read-only operator chart."""
    capture_root = resolve_local_storage_root(store_root) / "btc-realtime-captures"
    if capture_root.is_symlink() or not capture_root.is_dir():
        raise FileNotFoundError("no local BTC realtime capture is available")
    candidates = sorted(
        (path for path in capture_root.iterdir() if CAPTURE_RUN_PATTERN.fullmatch(path.name) and path.is_dir() and not path.is_symlink()),
        key=lambda path: path.name,
        reverse=True,
    )
    for run_root in candidates:
        manifest_path = run_root / "manifest.json"
        candles_path = run_root / "candles.jsonl"
        if manifest_path.is_symlink() or not manifest_path.is_file() or manifest_path.stat().st_size > MAX_CAPTURE_MANIFEST_BYTES:
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if (
            not isinstance(manifest, dict)
            or manifest.get("schema") != SCHEMA
            or manifest.get("run_id") != run_root.name
            or manifest.get("provider") != "binance_public"
            or manifest.get("symbol") != "BTCUSDT"
            or manifest.get("market") != "spot"
            or manifest.get("interval") != "1m"
            or manifest.get("poll_interval_seconds") != POLL_SECONDS
            or manifest.get("status") not in {"running", "completed", "interrupted"}
            or manifest.get("packet_eligible") is not False
        ):
            raise ValueError("local BTC realtime capture manifest failed validation")

        records: list[dict[str, object]] = []
        if candles_path.exists():
            if candles_path.is_symlink() or not candles_path.is_file() or candles_path.stat().st_size > MAX_CAPTURE_CANDLE_BYTES:
                raise ValueError("local BTC realtime capture candle file failed validation")
            raw = candles_path.read_bytes()
            lines = raw.splitlines()
            if raw and not raw.endswith(b"\n"):
                lines.pop()  # Ignore a final record being appended by the active capture process.
            for line in lines:
                record = json.loads(line)
                if not isinstance(record, dict) or record.get("schema") != "market-os.btc-realtime-candle.v1" or record.get("packet_eligible") is not False:
                    raise ValueError("local BTC realtime candle record failed validation")
                candle = record.get("candle")
                if not isinstance(candle, dict) or candle.get("symbol") != "BTCUSDT" or candle.get("interval") != "1m":
                    raise ValueError("local BTC realtime candle instrument failed validation")
                open_time_ms = _capture_timestamp_ms(candle.get("open_time"))
                close_time_ms = _capture_timestamp_ms(candle.get("close_time"))
                values = {name: candle.get(name) for name in ("open", "high", "low", "close", "volume")}
                if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in values.values()):
                    raise ValueError("local BTC realtime candle values failed validation")
                if any(not math.isfinite(value) for value in values.values()):
                    raise ValueError("local BTC realtime candle values failed validation")
                if close_time_ms - open_time_ms != 60_000 or min(values["open"], values["high"], values["low"], values["close"]) <= 0 or values["volume"] < 0:
                    raise ValueError("local BTC realtime candle range failed validation")
                if values["high"] < max(values["open"], values["close"], values["low"]) or values["low"] > min(values["open"], values["close"], values["high"]):
                    raise ValueError("local BTC realtime OHLC range failed validation")
                records.append({
                    "open_time_ms": open_time_ms,
                    "close_time_ms": close_time_ms,
                    **values,
                    "received_at": candle.get("received_at"),
                })
        if len(records) > 1 and any(records[index - 1]["open_time_ms"] >= records[index]["open_time_ms"] for index in range(1, len(records))):
            raise ValueError("local BTC realtime candles are not strictly ordered")
        return {
            "api_version": "market-os.btc-realtime-capture@v1",
            "capture": {
                "run_id": manifest["run_id"],
                "status": manifest["status"],
                "symbol": manifest["symbol"],
                "interval": manifest["interval"],
                "poll_interval_seconds": manifest["poll_interval_seconds"],
                "requested_polls": manifest["requested_polls"],
                "request_count": manifest["request_count"],
                "failed_polls": manifest["failed_polls"],
                "new_closed_candles": manifest["new_closed_candles"],
                "started_at": manifest["started_at"],
                "updated_at": manifest.get("updated_at", manifest["started_at"]),
                "finished_at": manifest.get("finished_at"),
                "source_published_at": None,
                "clock_error_bound_ms": None,
                "packet_eligible": False,
                "eligibility_reason": manifest["eligibility_reason"],
            },
            "candles": records[-LIVE_CHART_CANDLE_LIMIT:],
        }
    raise FileNotFoundError("no local BTC realtime capture is available")


def replay_capture_run(run_root: str | Path) -> dict[str, object]:
    """Verify and replay a completed local capture without network access."""
    supplied_root = Path(run_root).expanduser()
    if supplied_root.is_symlink() or supplied_root.parent.is_symlink():
        raise ValueError("local BTC capture path must not be a symlink")
    try:
        resolved_root = supplied_root.resolve(strict=True)
    except FileNotFoundError as exc:
        raise FileNotFoundError("local BTC capture run does not exist") from exc
    if not resolved_root.is_dir() or CAPTURE_RUN_PATTERN.fullmatch(resolved_root.name) is None:
        raise ValueError("local BTC capture run path is invalid")
    local_parent = resolve_local_storage_root(resolved_root.parent)
    if resolved_root != local_parent / resolved_root.name:
        raise ValueError("local BTC capture run path is invalid")

    manifest_path = resolved_root / "manifest.json"
    candles_path = resolved_root / "candles.jsonl"
    polls_path = resolved_root / "polls.jsonl"
    paths = {"candles.jsonl": candles_path, "polls.jsonl": polls_path}
    if manifest_path.is_symlink() or not manifest_path.is_file() or manifest_path.stat().st_size > MAX_CAPTURE_MANIFEST_BYTES:
        raise ValueError("local BTC capture manifest failed validation")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("local BTC capture manifest is unreadable") from exc
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema") != SCHEMA
        or manifest.get("run_id") != resolved_root.name
        or manifest.get("status") != "completed"
        or manifest.get("provider") != "binance_public"
        or manifest.get("symbol") != "BTCUSDT"
        or manifest.get("market") != "spot"
        or manifest.get("interval") != "1m"
        or manifest.get("poll_interval_seconds") != POLL_SECONDS
        or manifest.get("source_published_at") is not None
        or manifest.get("clock_error_bound_ms") is not None
        or manifest.get("packet_eligible") is not False
        or manifest.get("redistribution") is not False
        or manifest.get("trading_action") != "none"
    ):
        raise ValueError("local BTC capture manifest failed validation")

    hashes = manifest.get("artifact_sha256")
    if not isinstance(hashes, dict) or set(hashes) != set(paths) or any(
        not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None
        for value in hashes.values()
    ):
        raise ValueError("local BTC capture artifact hashes failed validation")
    artifact_bytes: dict[str, bytes] = {}
    for name, path in paths.items():
        limit = MAX_CAPTURE_CANDLE_BYTES if name == "candles.jsonl" else MAX_CAPTURE_POLL_BYTES
        if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
            raise ValueError(f"local BTC capture {name} failed validation")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != hashes[name]:
            raise ValueError(f"local BTC capture {name} hash mismatch")
        artifact_bytes[name] = raw

    def records_from(raw: bytes, name: str) -> list[dict[str, object]]:
        if raw and not raw.endswith(b"\n"):
            raise ValueError(f"local BTC capture {name} has an incomplete record")
        try:
            records = [json.loads(line) for line in raw.splitlines()]
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"local BTC capture {name} contains invalid JSON") from exc
        if any(not isinstance(record, dict) for record in records):
            raise ValueError(f"local BTC capture {name} contains an invalid record")
        return records

    poll_records = records_from(artifact_bytes["polls.jsonl"], "polls.jsonl")
    candle_records = records_from(artifact_bytes["candles.jsonl"], "candles.jsonl")
    requested_polls = manifest.get("requested_polls")
    if type(requested_polls) is not int or not 1 <= requested_polls <= MAX_POLLS:
        raise ValueError("local BTC capture poll count failed validation")
    for index, record in enumerate(poll_records, start=1):
        if (
            record.get("poll_index") != index
            or record.get("status") not in {"valid", "failed"}
            or type(record.get("request_count")) is not int
            or record.get("request_count") != 1
            or type(record.get("retry_count")) is not int
            or record.get("retry_count") != 0
            or record.get("clock_error_bound_ms") is not None
            or record.get("packet_eligible") is not False
            or record.get("trading_action") != "none"
        ):
            raise ValueError("local BTC capture poll record failed validation")
    if (
        manifest.get("request_cap") != requested_polls
        or manifest.get("request_count") != len(poll_records)
        or manifest.get("retry_count") != 0
        or manifest.get("failed_polls") != sum(record.get("status") == "failed" for record in poll_records)
        or len(poll_records) != requested_polls
        or manifest.get("new_closed_candles") != len(candle_records)
    ):
        raise ValueError("local BTC capture manifest counts do not match its artifacts")

    candles: list[dict[str, object]] = []
    for record in candle_records:
        candle = record.get("candle")
        if (
            record.get("schema") != "market-os.btc-realtime-candle.v1"
            or record.get("provider") != "binance_public"
            or record.get("symbol") != "BTCUSDT"
            or record.get("interval") != "1m"
            or record.get("packet_eligible") is not False
            or record.get("clock_error_bound_ms") is not None
            or record.get("source_published_at") is not None
            or record.get("trading_action") != "none"
            or not isinstance(candle, dict)
            or candle.get("symbol") != "BTCUSDT"
            or candle.get("interval") != "1m"
        ):
            raise ValueError("local BTC capture candle record failed validation")
        open_time_ms = _capture_timestamp_ms(candle.get("open_time"))
        close_time_ms = _capture_timestamp_ms(candle.get("close_time"))
        values = {name: candle.get(name) for name in ("open", "high", "low", "close", "volume")}
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in values.values()):
            raise ValueError("local BTC capture candle values failed validation")
        if any(not math.isfinite(value) for value in values.values()):
            raise ValueError("local BTC capture candle values failed validation")
        if (
            close_time_ms - open_time_ms != 60_000
            or min(values["open"], values["high"], values["low"], values["close"]) <= 0
            or values["volume"] < 0
            or values["high"] < max(values["open"], values["close"], values["low"])
            or values["low"] > min(values["open"], values["close"], values["high"])
            or (candles and candles[-1]["open_time_ms"] >= open_time_ms)
        ):
            raise ValueError("local BTC capture candle range or ordering failed validation")
        candles.append({
            "open_time_ms": open_time_ms,
            "close_time_ms": close_time_ms,
            **values,
            "received_at": candle.get("received_at"),
        })

    replay_fingerprint = hashlib.sha256(json.dumps(
        {"run_id": resolved_root.name, "artifact_sha256": hashes, "schema": SCHEMA},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    return {
        "api_version": "market-os.btc-realtime-replay@v1",
        "run_id": resolved_root.name,
        "integrity_status": "verified",
        "replay_fingerprint": replay_fingerprint,
        "candles": candles,
        "candle_count": len(candles),
        "clock_error_bound_ms": None,
        "packet_eligible": False,
        "trading_action": "none",
        "network_requests": 0,
    }


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not 1 <= args.samples <= MAX_POLLS:
        _parser().error(f"--samples must be between 1 and {MAX_POLLS}")

    repository_root = Path(__file__).resolve().parents[1]
    run_id = f"btc-live-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    store_root = resolve_local_storage_root(args.store_root or os.environ.get("MARKET_OS_STORE_ROOT") or repository_root / ".market_os")
    run_root = store_root / "btc-realtime-captures" / run_id
    run_root.mkdir(parents=True, exist_ok=False)
    candles_path = run_root / "candles.jsonl"
    polls_path = run_root / "polls.jsonl"
    manifest_path = run_root / "manifest.json"
    candles_path.touch()
    polls_path.touch()

    started_at = _utc_now()
    started_monotonic = time.monotonic()
    seen_open_times: set[str] = set()
    request_count = 0
    failed_polls = 0
    candle_count = 0
    manifest: dict[str, object] = {
        "schema": SCHEMA,
        "run_id": run_id,
        "status": "running",
        "provider": "binance_public",
        "endpoint": f"{BINANCE_BASE_URL}{BINANCE_KLINE_PATH}",
        "symbol": "BTCUSDT",
        "market": "spot",
        "interval": "1m",
        "poll_interval_seconds": POLL_SECONDS,
        "requested_polls": args.samples,
        "request_cap": args.samples,
        "request_count": 0,
        "retry_count": 0,
        "failed_polls": 0,
        "new_closed_candles": 0,
        "source_published_at": None,
        "clock_error_bound_ms": None,
        "packet_eligible": False,
        "eligibility_reason": "UTC receipt clock error bound has not been verified",
        "storage": "local-only under configured Market OS store root",
        "redistribution": False,
        "trading_action": "none",
        "started_at": started_at,
        "finished_at": None,
    }
    _write_manifest(manifest_path, manifest)

    adapter = BinancePublicAdapter()
    status = "completed"
    interrupted = False
    try:
        for index in range(args.samples):
            if index:
                due = started_monotonic + index * POLL_SECONDS
                time.sleep(max(0.0, due - time.monotonic()))

            request_started_at = _utc_now()
            request_started_monotonic_ns = time.monotonic_ns()
            request_count += 1
            try:
                result, attempts = adapter.klines(limit=KLINES_PER_POLL, max_attempts=1)
                new_candles = [candle for candle in result.candles if candle.open_time not in seen_open_times]
                for candle in new_candles:
                    seen_open_times.add(candle.open_time)
                    _append_jsonl(candles_path, {
                        "schema": "market-os.btc-realtime-candle.v1",
                        "provider": "binance_public",
                        "symbol": candle.symbol,
                        "interval": candle.interval,
                        "candle": asdict(candle),
                        "response_fingerprint": result.response_fingerprint,
                        "received_monotonic_ns": time.monotonic_ns(),
                        "source_published_at": None,
                        "clock_error_bound_ms": None,
                        "packet_eligible": False,
                        "eligibility_reason": "UTC receipt clock error bound has not been verified",
                        "trading_action": "none",
                    })
                candle_count += len(new_candles)
                _append_jsonl(polls_path, {
                    "poll_index": index + 1,
                    "status": "valid",
                    "request_started_at": request_started_at,
                    "request_started_monotonic_ns": request_started_monotonic_ns,
                    "received_at": result.received_at,
                    "request_count": attempts,
                    "retry_count": attempts - 1,
                    "response_fingerprint": result.response_fingerprint,
                    "closed_candles_in_response": len(result.candles),
                    "new_closed_candles": len(new_candles),
                    "excluded_open_candles": result.excluded_open_candles,
                    "latest_close": result.candles[-1].close if result.candles else None,
                    "clock_error_bound_ms": None,
                    "packet_eligible": False,
                    "trading_action": "none",
                })
            except ConnectivityError as exc:
                failed_polls += 1
                attempts = max(1, exc.attempts)
                _append_jsonl(polls_path, {
                    "poll_index": index + 1,
                    "request_started_at": request_started_at,
                    "request_started_monotonic_ns": request_started_monotonic_ns,
                    "received_at": _utc_now(),
                    "request_count": attempts,
                    "retry_count": attempts - 1,
                    "status": "failed",
                    "failure": {"code": exc.code, "status": exc.status, "retryable": exc.retryable},
                    "packet_eligible": False,
                    "trading_action": "none",
                })

            manifest.update({
                "request_count": request_count,
                "retry_count": 0,
                "failed_polls": failed_polls,
                "new_closed_candles": candle_count,
                "updated_at": _utc_now(),
            })
            _write_manifest(manifest_path, manifest)
    except KeyboardInterrupt:
        status = "interrupted"
        interrupted = True
    finally:
        manifest.update({
            "status": status,
            "finished_at": _utc_now(),
            "artifact_sha256": {
                "candles.jsonl": hashlib.sha256(candles_path.read_bytes()).hexdigest(),
                "polls.jsonl": hashlib.sha256(polls_path.read_bytes()).hexdigest(),
            },
        })
        _write_manifest(manifest_path, manifest)

    print(json.dumps({
        "run_id": run_id,
        "status": status,
        "requested_polls": args.samples,
        "request_count": request_count,
        "failed_polls": failed_polls,
        "new_closed_candles": candle_count,
        "manifest": str(manifest_path),
    }, sort_keys=True))
    if interrupted:
        return 130
    return 0 if failed_polls == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
