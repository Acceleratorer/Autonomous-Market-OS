from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import json
import market_os.schema_migration as schema_migration

import pytest

from market_os.portfolio_broker import B41Broker, B41Order, B41Approval
from market_os.paper_venue import BUY, MARKET, SyntheticMarketEvent
from market_os.schema_migration import MigrationRejected, migrate_portfolio, validate_migrated_store
from market_os.tests.test_portfolio_broker import genesis, policy
from market_os.tests.test_portfolio_shared import shared_genesis, policy as shared_policy, order as shared_order, approval as shared_approval


def test_isolated_migration_preserves_source_and_replay(tmp_path: Path) -> None:
    source = tmp_path / "source"
    portfolio = genesis()
    broker = B41Broker(source, portfolio, policy())
    order = B41Order(portfolio.portfolio_id, "migration-order", "migration-command", "migration-key", BUY, MARKET, Decimal("0.1"), None, 900)
    broker.submit_order(order, B41Approval.for_command("migration-approval", "owner", order.command_fingerprint, 900, 10_000))
    broker.process_market_event(SyntheticMarketEvent("migration-event", "BTCUSDT", 1_000, 100, 101, 100.5, 10, "synthetic-source-v1"))
    source_bytes = {path.name: path.read_bytes() for path in broker.root.iterdir() if path.is_file()}

    result = migrate_portfolio(source, portfolio.portfolio_id)

    destination = Path(result["target"]["path"])
    assert destination.is_dir()
    assert validate_migrated_store(destination)["migration_identity"] == result["migration_identity"]
    assert result["semantic_equivalence"]["status"] == "passed"
    assert result["semantic_equivalence"]["target_native"]["status"] == "recovered"
    assert {path.name: path.read_bytes() for path in broker.root.iterdir() if path.is_file()} == source_bytes


def test_shared_migration_preserves_membership_and_reservations(tmp_path: Path) -> None:
    shared = shared_genesis()
    broker = B41Broker(tmp_path / "source", shared, shared_policy())
    order = shared_order(shared, "strategy-a", "migration-shared-order")
    broker.submit_order(order, shared_approval(order))

    result = migrate_portfolio(tmp_path / "source", shared.portfolio_id)

    target = Path(result["target"]["path"])
    target_genesis = json.loads((target / "genesis.json").read_text(encoding="utf-8"))
    assert target_genesis["source_schema"] == shared.schema
    assert target_genesis["member_strategy_ids"] == list(shared.member_strategy_ids)
    assert result["counts"]["ledger_records"] == 1


def test_migration_retry_is_idempotent_and_conflicts_are_rejected(tmp_path: Path) -> None:
    portfolio = genesis()
    source = tmp_path / "source"
    B41Broker(source, portfolio, policy())
    first = migrate_portfolio(source, portfolio.portfolio_id)
    assert migrate_portfolio(source, portfolio.portfolio_id) == first

    with pytest.raises(MigrationRejected, match="identity conflict"):
        migrate_portfolio(source, portfolio.portfolio_id, source / "other-target")


def test_migration_rejects_destination_outside_store(tmp_path: Path) -> None:
    portfolio = genesis()
    source = tmp_path / "source"
    B41Broker(source, portfolio, policy())
    with pytest.raises(MigrationRejected, match="inside the store root"):
        migrate_portfolio(source, portfolio.portfolio_id, tmp_path / "outside")


def test_migration_rejects_unknown_source_fields(tmp_path: Path) -> None:
    portfolio = genesis()
    source = tmp_path / "source"
    broker = B41Broker(source, portfolio, policy())
    path = broker.root / "genesis.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["unexpected"] = "reject"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(MigrationRejected, match="failed closed|unsupported"):
        migrate_portfolio(source, portfolio.portfolio_id)


def test_migration_rejects_checkpoint_without_ledger(tmp_path: Path) -> None:
    portfolio = genesis()
    source = tmp_path / "source"
    broker = B41Broker(source, portfolio, policy())
    broker.process_market_event(SyntheticMarketEvent("migration-checkpoint", "BTCUSDT", 1_000, 100, 101, 100.5, 10, "synthetic-source-v1"))
    (broker.root / "ledger.jsonl").unlink()
    with pytest.raises(MigrationRejected):
        migrate_portfolio(source, portfolio.portfolio_id)


def test_idempotent_retry_revalidates_target_files(tmp_path: Path) -> None:
    portfolio = genesis()
    source = tmp_path / "source"
    B41Broker(source, portfolio, policy())
    result = migrate_portfolio(source, portfolio.portfolio_id)
    target = Path(result["target"]["path"])
    (target / "genesis.json").write_text("{}", encoding="utf-8")
    with pytest.raises(MigrationRejected, match="destination exists but is invalid"):
        migrate_portfolio(source, portfolio.portfolio_id)


def test_manifest_tampering_is_rejected_even_when_file_hashes_are_updated(tmp_path: Path) -> None:
    portfolio = genesis()
    source = tmp_path / "source"
    B41Broker(source, portfolio, policy())
    result = migrate_portfolio(source, portfolio.portfolio_id)
    target = Path(result["target"]["path"])
    manifest_path = target / "migration.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["source"].pop("schema")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(MigrationRejected, match="source"):
        validate_migrated_store(target)


def test_target_provenance_tampering_is_rejected_after_rehashed_manifest(tmp_path: Path) -> None:
    portfolio = genesis()
    source = tmp_path / "source"
    B41Broker(source, portfolio, policy())
    result = migrate_portfolio(source, portfolio.portfolio_id)
    target = Path(result["target"]["path"])
    genesis_path = target / "genesis.json"
    payload = json.loads(genesis_path.read_text(encoding="utf-8"))
    payload["source_schema"] = "unsupported"
    genesis_path.write_text(json.dumps(payload), encoding="utf-8")
    manifest_path = target / "migration.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = {name: (target / name).read_bytes() for name in manifest["target"]["file_fingerprints"]}
    manifest["target"]["file_fingerprints"]["genesis.json"] = schema_migration._sha256(files["genesis.json"])
    manifest["target"]["fingerprint"] = schema_migration._files_fingerprint(files)[1]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(MigrationRejected, match="schema|provenance|target"):
        validate_migrated_store(target)


def test_interrupted_promotion_keeps_source_and_retry_succeeds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    portfolio = genesis()
    source = tmp_path / "source"
    broker = B41Broker(source, portfolio, policy())
    source_bytes = {path.name: path.read_bytes() for path in broker.root.iterdir() if path.is_file()}
    original_rename = Path.rename
    calls = {"count": 0}

    def fail_once(self: Path, target: str | Path) -> Path:
        if self.parent == (source / ".migrations") and calls["count"] == 0:
            calls["count"] += 1
            raise OSError("simulated promotion interruption")
        return original_rename(self, target)

    monkeypatch.setattr(Path, "rename", fail_once)
    with pytest.raises(MigrationRejected, match="failed closed|interruption"):
        migrate_portfolio(source, portfolio.portfolio_id)
    assert {path.name: path.read_bytes() for path in broker.root.iterdir() if path.is_file()} == source_bytes
    target = source / ".migrations" / f"{portfolio.portfolio_id}-b4-18-v2"
    assert not target.exists()
    monkeypatch.setattr(Path, "rename", original_rename)
    retry = migrate_portfolio(source, portfolio.portfolio_id)
    assert Path(retry["target"]["path"]).is_dir()


def test_retry_recovers_when_rename_completes_before_interruption(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    portfolio = genesis()
    source = tmp_path / "source"
    B41Broker(source, portfolio, policy())
    original_rename = Path.rename
    calls = {"count": 0}

    def rename_then_fail(self: Path, target: str | Path) -> Path:
        result = original_rename(self, target)
        if self.parent == (source / ".migrations") and calls["count"] == 0:
            calls["count"] += 1
            raise OSError("simulated post-rename interruption")
        return result

    monkeypatch.setattr(Path, "rename", rename_then_fail)
    with pytest.raises(MigrationRejected, match="failed closed|interruption"):
        migrate_portfolio(source, portfolio.portfolio_id)
    target = source / ".migrations" / f"{portfolio.portfolio_id}-b4-18-v2"
    assert target.is_dir()
    monkeypatch.setattr(Path, "rename", original_rename)
    retry = migrate_portfolio(source, portfolio.portfolio_id)
    assert retry["target"]["path"] == str(target.resolve())
