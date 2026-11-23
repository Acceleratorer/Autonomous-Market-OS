"""Read-only host clock diagnostics, never a UTC qualification by themselves."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time


_FIELDS = {
    "Leap Indicator": "leap_indicator",
    "Stratum": "stratum",
    "Root Delay": "root_delay",
    "Root Dispersion": "root_dispersion",
    "Phase Offset": "phase_offset",
    "Source": "source",
    "Last Sync Error": "last_sync_error",
    "Time since Last Good Sync Time": "time_since_last_good_sync",
}


def capture_clock_status() -> dict[str, object]:
    """Bracket one bounded local status query; do not start or configure W32Time."""
    result: dict[str, object] = {
        "schema": "market-os.clock-diagnostic.v1",
        "status": "unsupported_platform",
        "clock_error_bound_ms": None,
        "query_started_at": datetime.now(timezone.utc).isoformat(),
        "query_started_monotonic_ns": time.monotonic_ns(),
    }
    try:
        if sys.platform != "win32":
            return result
        system_root = os.environ.get("SystemRoot")
        if not system_root:
            result["status"] = "unavailable"
            return result
        response = subprocess.run(
            [str(Path(system_root) / "System32" / "w32tm.exe"), "/query", "/status", "/verbose"],
            capture_output=True, text=True, errors="replace", timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        result["exit_code"] = response.returncode
        if response.returncode != 0:
            result["status"] = "query_failed"
            return result
        fields = {}
        for line in response.stdout.splitlines():
            label, separator, value = line.partition(":")
            key = _FIELDS.get(label.strip())
            if separator and key and value.strip() and len(json.dumps(value.strip())) <= 256:
                fields[key] = value.strip()
        result["fields"] = fields
        result["status"] = "observed" if len(fields) == len(_FIELDS) else "incomplete"
    except subprocess.TimeoutExpired:
        result["status"] = "timeout"
    except OSError:
        result["status"] = "unavailable"
    finally:
        result["query_finished_at"] = datetime.now(timezone.utc).isoformat()
        result["query_finished_monotonic_ns"] = time.monotonic_ns()
    return result
