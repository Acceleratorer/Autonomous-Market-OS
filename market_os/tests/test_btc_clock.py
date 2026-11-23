from types import SimpleNamespace
import subprocess

import pytest

from market_os import btc_clock


@pytest.mark.parametrize("outcome,expected", [
    ("complete", "observed"), ("missing", "incomplete"),
    ("failed", "query_failed"), ("timeout", "timeout"),
    ("unavailable", "unavailable"),
])
def test_clock_query_is_bounded_read_only_and_never_qualifies(monkeypatch, outcome, expected):
    monkeypatch.setattr(btc_clock.sys, "platform", "win32")
    monkeypatch.setenv("SystemRoot", "C:/Windows")
    monkeypatch.setattr(subprocess, "CREATE_NO_WINDOW", 0x08000000, raising=False)

    def query(command, **kwargs):
        assert command[1:] == ["/query", "/status", "/verbose"]
        assert kwargs["timeout"] == 5
        assert kwargs["creationflags"] == 0x08000000
        if outcome == "timeout":
            raise subprocess.TimeoutExpired(command, 5)
        if outcome == "unavailable":
            raise FileNotFoundError
        text = "\n".join(f"{label}: 0" for label in btc_clock._FIELDS)
        text = text.replace("Time since Last Good Sync Time: 0", "Time since Last Good Sync Time: 15.7344985s")
        if outcome == "missing":
            text = "Stratum: 5"
        return SimpleNamespace(returncode=1 if outcome == "failed" else 0, stdout=text)

    monkeypatch.setattr(subprocess, "run", query)
    result = btc_clock.capture_clock_status()
    assert result["status"] == expected
    assert result["clock_error_bound_ms"] is None
    assert result["query_finished_monotonic_ns"] >= result["query_started_monotonic_ns"]
    if outcome == "complete":
        assert result["fields"]["time_since_last_good_sync"] == "15.7344985s"


def test_other_platform_does_not_execute_windows_command(monkeypatch):
    monkeypatch.setattr(btc_clock.sys, "platform", "linux")
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: pytest.fail("unexpected command"))
    assert btc_clock.capture_clock_status()["status"] == "unsupported_platform"
