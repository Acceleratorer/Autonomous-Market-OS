from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from market_os.synthetic_session import load_synthetic_fixture, run_synthetic_fixture, write_synthetic_session_run


FIXTURE = Path(__file__).parent / "fixtures" / "b38" / "synthetic_session.json"
REPO_ROOT = Path(__file__).parents[2]


def make_store(tmp_path: Path) -> Path:
    root = tmp_path / "synthetic"
    run = run_synthetic_fixture(load_synthetic_fixture(FIXTURE))
    write_synthetic_session_run(run, root / "beta")
    write_synthetic_session_run(run, root / "alpha")
    return root


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "market_os.cli", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def snapshot(root: Path) -> dict[str, tuple[bytes, int]]:
    return {
        str(path.relative_to(root)): (path.read_bytes(), path.stat().st_mtime_ns)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_catalog_cli_is_sorted_deterministic_and_read_only(tmp_path: Path) -> None:
    root = make_store(tmp_path)
    before = snapshot(root)
    first = run_cli("synthetic", "catalog", "--store-root", str(root))
    second = run_cli("synthetic", "catalog", "--store-root", str(root))

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert first.stdout == second.stdout
    payload = json.loads(first.stdout)
    assert [item["session_id"] for item in payload["sessions"]] == ["alpha", "beta"]
    assert payload["session_count"] == 2
    assert snapshot(root) == before


def test_compare_cli_includes_fingerprints_and_right_minus_left_deltas(tmp_path: Path) -> None:
    root = make_store(tmp_path)
    before = snapshot(root)
    result = run_cli("synthetic", "compare", "--store-root", str(root), "--left", "alpha", "--right", "beta")
    repeat = run_cli("synthetic", "compare", "--store-root", str(root), "--left", "alpha", "--right", "beta")

    assert result.returncode == 0, result.stderr
    assert repeat.returncode == 0, repeat.stderr
    assert result.stdout == repeat.stdout
    payload = json.loads(result.stdout)
    assert payload["delta_direction"] == "right_minus_left"
    assert payload["left"]["session_id"] == "alpha"
    assert payload["right"]["session_id"] == "beta"
    for side in ("left", "right"):
        assert payload[side]["manifest_fingerprint"]
        assert payload[side]["replay_fingerprint"]
        assert payload[side]["accounting_fingerprint"]
    assert payload["delta"]["total_pnl_usdt"] == 0.0
    assert snapshot(root) == before


@pytest.mark.parametrize(
    "args",
    [
        ("synthetic", "compare", "--store-root", "{root}", "--left", "missing", "--right", "alpha"),
        ("synthetic", "compare", "--store-root", "{root}", "--left", "alpha", "--right", "alpha"),
        ("synthetic", "compare", "--store-root", "{root}", "--left", "bad/id", "--right", "alpha"),
    ],
)
def test_cli_rejects_unknown_and_duplicate_sessions(tmp_path: Path, args: tuple[str, ...]) -> None:
    root = make_store(tmp_path)
    result = run_cli(*(item.format(root=str(root)) for item in args))

    assert result.returncode != 0
    assert result.stderr


def test_cli_rejects_tampered_sessions(tmp_path: Path) -> None:
    root = make_store(tmp_path)
    accounting = root / "alpha" / "accounting.json"
    payload = json.loads(accounting.read_text(encoding="utf-8"))
    payload["accounting"]["total_pnl_usdt"] = 123.0
    accounting.write_text(json.dumps(payload), encoding="utf-8")

    catalog = run_cli("synthetic", "catalog", "--store-root", str(root))
    compare = run_cli("synthetic", "compare", "--store-root", str(root), "--left", "alpha", "--right", "beta")

    assert catalog.returncode != 0
    assert compare.returncode != 0
    assert "fingerprint" in (catalog.stderr + compare.stderr).lower()


def test_existing_synthetic_inspect_cli_behavior_is_unchanged(tmp_path: Path) -> None:
    root = make_store(tmp_path)
    replay_report = root / "alpha" / "strategy-replay.json"
    result = run_cli("synthetic", "inspect", "--replay-report", str(replay_report), "--resource", "replay")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema"] == "market-os.b3-5.synthetic-strategy-session@v1"


def test_existing_synthetic_run_cli_behavior_is_unchanged(tmp_path: Path) -> None:
    output = tmp_path / "new-session"
    result = run_cli("synthetic", "run", "--fixture", str(FIXTURE), "--output", str(output))

    assert result.returncode == 0, result.stderr
    assert {path.name for path in output.iterdir()} == {"accounting.json", "manifest.json", "strategy-replay.json"}
    assert json.loads(result.stdout)["schema"] == "market-os.b3-8.synthetic-session-manifest@v1"


def test_existing_synthetic_serve_cli_behavior_is_unchanged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from market_os import synthetic_server as b310_synthetic_server, cli

    calls: list[tuple[str, str, int]] = []
    monkeypatch.setattr(b310_synthetic_server, "serve_synthetic", lambda root, host, port: calls.append((root, host, port)))

    assert cli.main(["synthetic", "serve", "--store-root", str(tmp_path), "--host", "127.0.0.1", "--port", "8791"]) == 0
    assert calls == [(str(tmp_path), "127.0.0.1", 8791)]
