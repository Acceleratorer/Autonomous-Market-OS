from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from market_os.portfolio_backup import BackupRejected, backup_portfolio, restore_portfolio
from market_os.tests.test_portfolio_broker import approval, buy, event, genesis, policy
from market_os.portfolio_broker import B41Broker
from market_os.tests.test_portfolio_shared import approval as shared_approval, order as shared_order, policy as shared_policy, shared_genesis


def test_backup_restore_replays_identically_without_mutating_source(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    broker = B41Broker(source_root, genesis(), policy())
    broker.submit_order(buy(), approval(buy()))
    expected = broker.process_market_event(event("backup-event"))
    archive = tmp_path / "backups" / "portfolio.zip"

    assert backup_portfolio(source_root, genesis().portfolio_id, archive) == archive
    restored_root = tmp_path / "restored"
    restored = restore_portfolio(archive, restored_root)

    assert restored == restored_root / genesis().portfolio_id
    assert B41Broker.open(restored_root, genesis().portfolio_id).snapshot() == expected
    assert B41Broker.open(source_root, genesis().portfolio_id).snapshot() == expected


def test_restore_rejects_tampered_member_and_existing_destination(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    B41Broker(source_root, genesis(), policy())
    archive = tmp_path / "portfolio.zip"
    backup_portfolio(source_root, genesis().portfolio_id, archive)
    tampered = tmp_path / "tampered.zip"
    with ZipFile(archive) as original, ZipFile(tampered, "w", compression=ZIP_DEFLATED) as changed:
        for name in original.namelist():
            data = original.read(name)
            changed.writestr(name, data + b"x" if name == "policy.json" else data)

    with pytest.raises(BackupRejected, match="fingerprint mismatch"):
        restore_portfolio(tampered, tmp_path / "restored")

    restored_root = tmp_path / "restored"
    restore_portfolio(archive, restored_root)
    with pytest.raises(BackupRejected, match="already exists"):
        restore_portfolio(archive, restored_root)


def test_backup_rejects_archive_inside_source_store(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    B41Broker(source_root, genesis(), policy())
    with pytest.raises(BackupRejected, match="outside"):
        backup_portfolio(source_root, genesis().portfolio_id, source_root / genesis().portfolio_id / "backup.zip")


def test_cli_backup_and_restore_are_explicit_local_operations(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from market_os.cli import main

    source_root = tmp_path / "source"
    B41Broker(source_root, genesis(), policy())
    archive = tmp_path / "portfolio.zip"
    assert main(["b4-paper", "backup", genesis().portfolio_id, "--store-root", str(source_root), "--archive", str(archive)]) == 0
    assert Path(json.loads(capsys.readouterr().out)["archive"]) == archive

    restored_root = tmp_path / "restored"
    assert main(["b4-paper", "restore", "--store-root", str(restored_root), "--archive", str(archive)]) == 0
    assert Path(json.loads(capsys.readouterr().out)["portfolio_root"]).name == genesis().portfolio_id


def test_backup_rejects_checkpoint_without_ledger(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    broker = B41Broker(source_root, genesis(), policy())
    broker.process_market_event(event("checkpoint-event"))
    (source_root / genesis().portfolio_id / "ledger.jsonl").unlink()

    with pytest.raises(BackupRejected, match="failed broker validation"):
        backup_portfolio(source_root, genesis().portfolio_id, tmp_path / "broken.zip")


def test_shared_backup_preserves_reservations_audit_and_fingerprints(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    shared = shared_genesis()
    broker = B41Broker(source_root, shared, shared_policy())
    submitted = shared_order(shared, "strategy-a", "order-a")
    broker.submit_order(submitted, shared_approval(submitted))
    before = {resource: broker.inspect_jsonable(resource) for resource in ("genesis", "reservations", "risk", "ledger", "fingerprints")}
    source_files = {path.name: path.read_bytes() for path in broker.root.iterdir() if path.is_file()}

    archive = backup_portfolio(source_root, shared.portfolio_id, tmp_path / "shared.zip")
    restored_root = tmp_path / "restored"
    restore_portfolio(archive, restored_root)
    restored = B41Broker.open(restored_root, shared.portfolio_id)

    assert {resource: restored.inspect_jsonable(resource) for resource in before} == before
    assert {path.name: path.read_bytes() for path in broker.root.iterdir() if path.is_file()} == source_files
