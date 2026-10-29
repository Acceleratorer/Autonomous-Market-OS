from __future__ import annotations

from pathlib import Path

import pytest

from market_os.portfolio_migration import MigrationRejected, preflight_portfolio
from market_os.portfolio_broker import B41Broker
from market_os.tests.test_portfolio_broker import event, genesis, policy
from market_os.tests.test_portfolio_shared import shared_genesis, policy as shared_policy


def test_migration_preflight_reports_current_schema_without_mutation(tmp_path: Path) -> None:
    root = tmp_path / "store"
    B41Broker(root, genesis(), policy())
    before = {path.name: path.read_bytes() for path in (root / genesis().portfolio_id).iterdir() if path.is_file()}

    result = preflight_portfolio(root, genesis().portfolio_id)

    assert result["status"] == "current"
    assert result["requires_migration"] is False
    assert result["history_immutable"] is True
    after = {path.name: path.read_bytes() for path in (root / genesis().portfolio_id).iterdir() if path.is_file()}
    assert after == before


def test_migration_preflight_rejects_unsupported_genesis_schema(tmp_path: Path) -> None:
    root = tmp_path / "store"
    B41Broker(root, genesis(), policy())
    path = root / genesis().portfolio_id / "genesis.json"
    path.write_text(path.read_text(encoding="utf-8").replace("@v1", "@v2"), encoding="utf-8")

    with pytest.raises(MigrationRejected, match="unsupported"):
        preflight_portfolio(root, genesis().portfolio_id)


def test_migration_preflight_cli_is_read_only_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from market_os.cli import main

    root = tmp_path / "store"
    B41Broker(root, genesis(), policy())
    assert main(["b4-paper", "migration-check", genesis().portfolio_id, "--store-root", str(root)]) == 0
    assert '"requires_migration": false' in capsys.readouterr().out


def test_migration_preflight_rejects_checkpoint_without_ledger(tmp_path: Path) -> None:
    root = tmp_path / "store"
    broker = B41Broker(root, genesis(), policy())
    broker.process_market_event(event("checkpoint-event"))
    (root / genesis().portfolio_id / "ledger.jsonl").unlink()

    with pytest.raises(MigrationRejected, match="unsupported"):
        preflight_portfolio(root, genesis().portfolio_id)


def test_migration_preflight_reports_shared_genesis_without_changing_bytes(tmp_path: Path) -> None:
    shared = shared_genesis()
    broker = B41Broker(tmp_path, shared, shared_policy())
    before = {path.name: path.read_bytes() for path in broker.root.iterdir() if path.is_file()}

    result = preflight_portfolio(tmp_path, shared.portfolio_id)

    assert result["genesis_schema"] == shared.schema
    assert {path.name: path.read_bytes() for path in broker.root.iterdir() if path.is_file()} == before
