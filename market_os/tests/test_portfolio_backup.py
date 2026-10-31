from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from market_os.portfolio_backup import BackupRejected, backup_portfolio, preflight_retention_archive, restore_portfolio
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


def test_restore_never_overwrites_destination_created_during_promotion(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source_root = tmp_path / "source"
    B41Broker(source_root, genesis(), policy())
    archive = tmp_path / "portfolio.zip"
    backup_portfolio(source_root, genesis().portfolio_id, archive)
    restored_root = tmp_path / "restored"
    destination = restored_root / genesis().portfolio_id
    original_rename = Path.rename
    raced = {"done": False}

    def create_competing_destination(self: Path, target: str | Path) -> Path:
        if Path(target) == destination and not raced["done"]:
            raced["done"] = True
            destination.mkdir(parents=True)
            (destination / "sentinel").write_text("competitor", encoding="utf-8")
        if Path(target) == destination:
            raise FileExistsError("destination reserved by competing writer")
        return original_rename(self, target)

    monkeypatch.setattr(Path, "rename", create_competing_destination)

    with pytest.raises(BackupRejected, match="already exists"):
        restore_portfolio(archive, restored_root)
    assert (destination / "sentinel").read_text(encoding="utf-8") == "competitor"


def test_restore_failure_before_directory_publish_leaves_no_partial_destination(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source_root = tmp_path / "source"
    B41Broker(source_root, genesis(), policy())
    archive = tmp_path / "portfolio.zip"
    backup_portfolio(source_root, genesis().portfolio_id, archive)
    restored_root = tmp_path / "restored"
    original_rename = Path.rename

    def interrupt_publish(self: Path, target: str | Path) -> Path:
        if Path(target) == restored_root / genesis().portfolio_id:
            raise OSError("simulated publish interruption")
        return original_rename(self, target)

    monkeypatch.setattr(Path, "rename", interrupt_publish)

    with pytest.raises(BackupRejected, match="published atomically"):
        restore_portfolio(archive, restored_root)
    assert not (restored_root / genesis().portfolio_id).exists()


def test_backup_rejects_archive_inside_source_store(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    B41Broker(source_root, genesis(), policy())
    with pytest.raises(BackupRejected, match="outside"):
        backup_portfolio(source_root, genesis().portfolio_id, source_root / genesis().portfolio_id / "backup.zip")


def test_backup_publication_never_overwrites_a_concurrent_archive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import market_os.portfolio_backup as backup_module

    source_root = tmp_path / "source"
    B41Broker(source_root, genesis(), policy())
    archive = tmp_path / "portfolio.zip"
    real_link = backup_module.os.link

    def concurrent_creation(source: str | Path, destination: str | Path) -> None:
        Path(destination).write_bytes(b"another writer published first")
        real_link(source, destination)

    monkeypatch.setattr(backup_module.os, "link", concurrent_creation)

    with pytest.raises(BackupRejected, match="already exists"):
        backup_portfolio(source_root, genesis().portfolio_id, archive)

    assert archive.read_bytes() == b"another writer published first"


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


def test_retention_preflight_reports_isolated_store_and_valid_archive_without_mutation(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    broker = B41Broker(source_root, genesis(), policy())
    archive = backup_portfolio(source_root, genesis().portfolio_id, tmp_path / "backups" / "portfolio.zip")
    before = {path.name: path.read_bytes() for path in broker.root.iterdir() if path.is_file()}

    report = preflight_retention_archive(source_root, genesis().portfolio_id, archive)

    assert report["schema"] == "market-os.b4-20.retention-archive-preflight@v1"
    assert report["portfolio"]["mode"] == "isolated"
    assert report["source_retention"] == "indefinite-local"
    assert report["deletion_eligible"] is False
    assert report["ledger"]["present"] is False
    assert report["zero_event_ambiguous"] is True
    assert report["archive"]["status"] == "valid"
    assert report["archive"]["archive_sha256"]
    assert "path" not in json.dumps(report).lower()
    assert {path.name: path.read_bytes() for path in broker.root.iterdir() if path.is_file()} == before


def test_retention_preflight_reports_shared_membership_and_active_reservations(tmp_path: Path) -> None:
    shared = shared_genesis()
    root = tmp_path / "shared"
    broker = B41Broker(root, shared, shared_policy())
    order = shared_order(shared, "strategy-a", "preflight-order")
    broker.submit_order(order, shared_approval(order))

    report = preflight_retention_archive(root, shared.portfolio_id)

    assert report["portfolio"] == {
        "portfolio_id": shared.portfolio_id,
        "mode": "shared",
        "member_count": len(shared.member_strategy_ids),
        "open_order_count": 1,
    }
    assert report["reservations"]["cash_usdt"] != "0"
    assert report["deletion_eligible"] is False
    assert report["archive"]["status"] == "not_supplied"


def test_retention_preflight_counts_nonblank_ledger_records(tmp_path: Path) -> None:
    root = tmp_path / "source"
    broker = B41Broker(root, genesis(), policy())
    broker.process_market_event(event("preflight-count"))
    with broker.ledger_path.open("ab") as ledger:
        ledger.write(b"\n  \n")

    report = preflight_retention_archive(root, genesis().portfolio_id)

    assert report["ledger"]["record_count"] == 1


@pytest.mark.parametrize("archive_state", ["missing", "tampered", "identity_mismatch", "oversized"])
def test_retention_preflight_classifies_invalid_archives_without_changing_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, archive_state: str
) -> None:
    import market_os.portfolio_backup as backup_module

    root = tmp_path / "source"
    broker = B41Broker(root, genesis(), policy())
    archive = backup_portfolio(root, genesis().portfolio_id, tmp_path / "portfolio.zip")
    before = {path.name: path.read_bytes() for path in broker.root.iterdir() if path.is_file()}
    expected_status = "missing" if archive_state == "missing" else "invalid"

    if archive_state == "missing":
        archive = tmp_path / "missing.zip"
    elif archive_state == "tampered":
        changed = tmp_path / "changed.zip"
        with ZipFile(archive) as original, ZipFile(changed, "w", compression=ZIP_DEFLATED) as output:
            for name in original.namelist():
                data = original.read(name)
                output.writestr(name, data + b"x" if name == "policy.json" else data)
        archive = changed
    elif archive_state == "identity_mismatch":
        other_root = tmp_path / "other"
        other_genesis = genesis().__class__.create("other-portfolio", "synthetic-fixture-v1", policy())
        B41Broker(other_root, other_genesis, policy())
        archive = backup_portfolio(other_root, other_genesis.portfolio_id, tmp_path / "identity.zip")
    else:
        monkeypatch.setattr(backup_module, "MAX_ARCHIVE_UNCOMPRESSED_BYTES", 1)

    report = preflight_retention_archive(root, genesis().portfolio_id, archive)

    assert report["archive"]["status"] == expected_status
    assert report["deletion_eligible"] is False
    assert {path.name: path.read_bytes() for path in broker.root.iterdir() if path.is_file()} == before


def test_retention_preflight_rejects_archive_symlink(tmp_path: Path) -> None:
    root = tmp_path / "source"
    B41Broker(root, genesis(), policy())
    archive = backup_portfolio(root, genesis().portfolio_id, tmp_path / "portfolio.zip")
    link = tmp_path / "portfolio-link.zip"
    try:
        link.symlink_to(archive)
    except OSError as exc:
        pytest.skip(f"symlink creation is unavailable: {exc}")

    report = preflight_retention_archive(root, genesis().portfolio_id, link)

    assert report["archive"]["status"] == "invalid"
    assert report["deletion_eligible"] is False


def test_retention_preflight_rejects_symlinked_archive_parent(tmp_path: Path) -> None:
    root = tmp_path / "source"
    B41Broker(root, genesis(), policy())
    archive = backup_portfolio(root, genesis().portfolio_id, tmp_path / "real" / "portfolio.zip")
    alias = tmp_path / "alias"
    try:
        alias.symlink_to(archive.parent, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink creation is unavailable: {exc}")

    report = preflight_retention_archive(root, genesis().portfolio_id, alias / archive.name)

    assert report["archive"] == {"status": "invalid", "reason": "archive_symlink"}


def test_retention_preflight_classifies_archive_path_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import market_os.portfolio_backup as backup_module

    root = tmp_path / "source"
    B41Broker(root, genesis(), policy())

    def reject_archive(_archive_path: str | Path, _portfolio_id: str) -> dict[str, object]:
        raise OSError("archive path is unavailable")

    monkeypatch.setattr(backup_module, "_validate_archive_for_preflight", reject_archive)

    report = preflight_retention_archive(root, genesis().portfolio_id, tmp_path / "portfolio.zip")

    assert report["archive"] == {"status": "invalid", "reason": "archive_path_invalid"}


def test_restore_rejects_symlinked_archive_parent(tmp_path: Path) -> None:
    root = tmp_path / "source"
    B41Broker(root, genesis(), policy())
    archive = backup_portfolio(root, genesis().portfolio_id, tmp_path / "real" / "portfolio.zip")
    alias = tmp_path / "alias"
    try:
        alias.symlink_to(archive.parent, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink creation is unavailable: {exc}")

    with pytest.raises(BackupRejected, match="symlink|reparse"):
        restore_portfolio(alias / archive.name, tmp_path / "restored")


def test_retention_preflight_rejects_checkpoint_without_ledger(tmp_path: Path) -> None:
    root = tmp_path / "source"
    broker = B41Broker(root, genesis(), policy())
    broker.process_market_event(event("preflight-checkpoint"))
    (broker.root / "ledger.jsonl").unlink()

    with pytest.raises(BackupRejected, match="failed broker validation"):
        preflight_retention_archive(root, genesis().portfolio_id)