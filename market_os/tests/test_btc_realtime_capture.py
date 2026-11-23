from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from market_os.btc_realtime_capture import replay_capture_run


def _jsonl_record(value: dict[str, object]) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _write_completed_capture(root: Path) -> Path:
    run_id = "btc-live-20261123T010203Z-a1b2c3d4"
    run_root = root / run_id
    run_root.mkdir()
    open_time = datetime(2026, 11, 23, 1, 0, tzinfo=timezone.utc)
    close_time = datetime(2026, 11, 23, 1, 1, tzinfo=timezone.utc)
    candle = {
        "symbol": "BTCUSDT",
        "interval": "1m",
        "open_time": open_time.isoformat(),
        "close_time": close_time.isoformat(),
        "open": 100.0,
        "high": 102.0,
        "low": 99.0,
        "close": 101.0,
        "volume": 2.5,
        "source_timestamp": close_time.isoformat(),
        "received_at": "2026-11-23T01:01:03+00:00",
        "availability_timestamp": "2026-11-23T01:01:03+00:00",
        "provenance_id": "a" * 64,
        "candle_fingerprint": "b" * 64,
        "api_version": "market-os.btc-paper.v1",
    }
    candle_bytes = _jsonl_record({
        "schema": "market-os.btc-realtime-candle.v1",
        "provider": "binance_public",
        "symbol": "BTCUSDT",
        "interval": "1m",
        "candle": candle,
        "response_fingerprint": "c" * 64,
        "received_monotonic_ns": 100,
        "source_published_at": None,
        "clock_error_bound_ms": None,
        "packet_eligible": False,
        "trading_action": "none",
    })
    poll_bytes = _jsonl_record({
        "poll_index": 1,
        "status": "valid",
        "request_started_at": "2026-11-23T01:01:02+00:00",
        "request_started_monotonic_ns": 50,
        "received_at": "2026-11-23T01:01:03+00:00",
        "request_count": 1,
        "retry_count": 0,
        "response_fingerprint": "c" * 64,
        "closed_candles_in_response": 1,
        "new_closed_candles": 1,
        "excluded_open_candles": 0,
        "latest_close": 101.0,
        "clock_error_bound_ms": None,
        "packet_eligible": False,
        "trading_action": "none",
    })
    (run_root / "candles.jsonl").write_bytes(candle_bytes)
    (run_root / "polls.jsonl").write_bytes(poll_bytes)
    manifest = {
        "schema": "market-os.btc-realtime-capture.v1",
        "run_id": run_id,
        "status": "completed",
        "provider": "binance_public",
        "symbol": "BTCUSDT",
        "market": "spot",
        "interval": "1m",
        "poll_interval_seconds": 180,
        "requested_polls": 1,
        "request_cap": 1,
        "request_count": 1,
        "retry_count": 0,
        "failed_polls": 0,
        "new_closed_candles": 1,
        "source_published_at": None,
        "clock_error_bound_ms": None,
        "packet_eligible": False,
        "eligibility_reason": "UTC receipt clock error bound has not been verified",
        "storage": "local-only under configured Market OS store root",
        "redistribution": False,
        "trading_action": "none",
        "started_at": "2026-11-23T01:01:00+00:00",
        "updated_at": "2026-11-23T01:01:04+00:00",
        "finished_at": "2026-11-23T01:01:04+00:00",
        "artifact_sha256": {
            "candles.jsonl": hashlib.sha256(candle_bytes).hexdigest(),
            "polls.jsonl": hashlib.sha256(poll_bytes).hexdigest(),
        },
    }
    (run_root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return run_root


def test_offline_capture_replay_is_repeatable_and_never_packet_eligible(tmp_path: Path) -> None:
    run_root = _write_completed_capture(tmp_path)

    first = replay_capture_run(run_root)
    second = replay_capture_run(run_root)

    assert first["integrity_status"] == "verified"
    assert first["replay_fingerprint"] == second["replay_fingerprint"]
    assert first["candles"][0]["close"] == 101.0
    assert first["clock_error_bound_ms"] is None
    assert first["packet_eligible"] is False
