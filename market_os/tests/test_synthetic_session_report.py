from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from market_os.synthetic_session import (
    load_synthetic_fixture,
    run_synthetic_fixture,
    write_synthetic_session_run,
)
from market_os.synthetic_session_api import SyntheticSessionStore
from market_os.synthetic_session_report import (
    REPORT_SCHEMA,
    SyntheticSessionReportError,
    build_synthetic_session_report,
    main,
    render_synthetic_session_report,
)
from market_os import cli


FIXTURE = Path(__file__).parent / "fixtures" / "b38" / "synthetic_session.json"


def _store(tmp_path: Path) -> tuple[SyntheticSessionStore, str]:
    root = tmp_path / "sessions"
    session_id = "alpha"
    write_synthetic_session_run(
        run_synthetic_fixture(load_synthetic_fixture(FIXTURE)),
        root / session_id,
    )
    return SyntheticSessionStore(root), session_id


def _snapshot(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_u7_h_report_is_stable_and_preserves_boundary(tmp_path: Path) -> None:
    store, session_id = _store(tmp_path)
    first = build_synthetic_session_report(store, session_id)
    second = build_synthetic_session_report(store, session_id)

    assert first == second
    assert first["schema"] == REPORT_SCHEMA
    assert first["status"] == "passed"
    assert first["promotion_approved"] is False
    assert first["accounting"]["fill_count"] >= 0
    assert first["accounting"]["total_fees_usdt"] >= 0
    assert first["checks"]["deterministic_replay"] is True
    assert first["checks"]["bounded_counts"] is True
    assert first["checks"]["replay_accounting_linkage"] is True
    assert first["boundary"] == {
        "synthetic_only": True,
        "paper_only": True,
        "read_only": True,
        "predictive_evidence": False,
        "promotion_approved": False,
        "network_access": False,
        "provider_requests": 0,
        "credentials": False,
        "mutation_routes": False,
        "live_execution": False,
    }


def test_u7_h_render_keeps_store_unchanged_and_writes_json_markdown(tmp_path: Path) -> None:
    store, session_id = _store(tmp_path)
    before = _snapshot(store.root)
    report = render_synthetic_session_report(
        store,
        session_id,
        markdown_path=tmp_path / "report.md",
        json_path=tmp_path / "report.json",
    )

    assert _snapshot(store.root) == before
    assert json.loads((tmp_path / "report.json").read_text(encoding="utf-8")) == report
    assert "# U7-H Synthetic Session Accounting Report" in (
        tmp_path / "report.md"
    ).read_text(encoding="utf-8")


def test_u7_h_rejects_tampered_accounting_artifact(tmp_path: Path) -> None:
    store, session_id = _store(tmp_path)
    accounting_path = store.root / session_id / "accounting.json"
    payload = json.loads(accounting_path.read_text(encoding="utf-8"))
    payload["accounting"]["total_pnl_usdt"] = 999.0
    accounting_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises((SyntheticSessionReportError, ValueError), match="fingerprint mismatch"):
        build_synthetic_session_report(store, session_id)


def test_u7_h_rejects_nondeterministic_replay(tmp_path: Path) -> None:
    store, session_id = _store(tmp_path)
    with pytest.raises(SyntheticSessionReportError, match="not deterministic"):
        build_synthetic_session_report(store, session_id, deterministic_replay=False)


def test_u7_h_module_cli_writes_fixture_report(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--fixture", str(FIXTURE), "--output-dir", str(tmp_path)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result == {"schema": REPORT_SCHEMA, "status": "passed"}
    assert (tmp_path / "synthetic-session-report.json").exists()
    assert (tmp_path / "synthetic-session-report.md").exists()


def test_u7_h_market_os_cli_writes_fixture_report(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main([
        "synthetic",
        "report",
        "--fixture",
        str(FIXTURE),
        "--output-dir",
        str(tmp_path / "output"),
    ]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["schema"] == REPORT_SCHEMA
    assert result["checks"]["promotion_disabled"] is True
    assert (tmp_path / "output" / "synthetic-session-report.json").exists()
