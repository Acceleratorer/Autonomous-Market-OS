"""Local, opt-in backup and restore for the synthetic B4 portfolio store."""
from __future__ import annotations

from pathlib import Path
import hashlib
import json
import os
import shutil
import tempfile
from typing import Any, Mapping
from zipfile import BadZipFile, ZIP_DEFLATED, ZipFile, ZipInfo

from .portfolio_broker import B41Broker, SCHEMA


BACKUP_SCHEMA = "market-os.b4-11.portfolio-backup@v1"
_FILES = ("genesis.json", "policy.json", "ledger.jsonl", "checkpoint.json")


class BackupRejected(ValueError):
    """A backup or restore operation failed closed."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _safe_portfolio_path(store_root: str | Path, portfolio_id: str) -> Path:
    if not isinstance(portfolio_id, str) or not portfolio_id or Path(portfolio_id).name != portfolio_id:
        raise BackupRejected("portfolio_id is unsafe")
    root = Path(store_root).resolve()
    candidate = root / portfolio_id
    if candidate.is_symlink():
        raise BackupRejected("portfolio directory cannot be a symlink")
    path = candidate.resolve()
    if path.parent != root:
        raise BackupRejected("portfolio_id escapes store root")
    return path


def backup_portfolio(store_root: str | Path, portfolio_id: str, archive_path: str | Path) -> Path:
    """Create an immutable local ZIP backup without changing the portfolio."""
    source = _safe_portfolio_path(store_root, portfolio_id)
    archive = Path(archive_path).resolve()
    if archive.parent == source or source in archive.parents:
        raise BackupRejected("backup archive must be outside the portfolio store")
    if archive.exists() or archive.is_symlink():
        raise BackupRejected("backup archive already exists")
    try:
        files = B41Broker.open(store_root, portfolio_id, read_only=True).export_backup_files()
    except (OSError, ValueError) as exc:
        raise BackupRejected("portfolio failed broker validation") from exc

    manifest = {
        "schema": BACKUP_SCHEMA,
        "broker_schema": SCHEMA,
        "portfolio_id": portfolio_id,
        "files": [{"path": name, "size": len(data), "sha256": _sha256(data)} for name, data in sorted(files.items())],
    }
    archive.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{archive.name}.", suffix=".tmp", dir=archive.parent)
    os.close(fd)
    temp = Path(temp_name)
    try:
        with ZipFile(temp, "w", compression=ZIP_DEFLATED) as bundle:
            for name, data in sorted(files.items()):
                info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = ZIP_DEFLATED
                bundle.writestr(info, data)
            info = ZipInfo("manifest.json", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            bundle.writestr(info, (_canonical(manifest) + "\n").encode("utf-8"))
        temp.replace(archive)
    finally:
        temp.unlink(missing_ok=True)
    return archive


def restore_portfolio(archive_path: str | Path, store_root: str | Path, portfolio_id: str | None = None) -> Path:
    """Verify and restore a backup into a new portfolio directory."""
    archive = Path(archive_path).resolve()
    if not archive.is_file() or archive.is_symlink():
        raise BackupRejected("backup archive is missing")
    try:
        with ZipFile(archive) as bundle:
            names = bundle.namelist()
            if len(names) != len(set(names)) or "manifest.json" not in names:
                raise BackupRejected("backup archive members are invalid")
            manifest = json.loads(bundle.read("manifest.json"))
            if not isinstance(manifest, Mapping) or manifest.get("schema") != BACKUP_SCHEMA or manifest.get("broker_schema") != SCHEMA:
                raise BackupRejected("backup schema is unsupported")
            stored_id = manifest.get("portfolio_id")
            if not isinstance(stored_id, str):
                raise BackupRejected("backup portfolio identity is malformed")
            target_id = portfolio_id or stored_id
            if target_id != stored_id:
                raise BackupRejected("backup portfolio identity mismatch")
            _safe_portfolio_path(store_root, target_id)
            entries = manifest.get("files")
            if not isinstance(entries, list):
                raise BackupRejected("backup manifest is malformed")
            expected: dict[str, tuple[int, str]] = {}
            for entry in entries:
                if not isinstance(entry, Mapping):
                    raise BackupRejected("backup manifest is malformed")
                name = entry.get("path")
                if name not in _FILES or name in expected or Path(name).name != name:
                    raise BackupRejected("backup file path is invalid")
                size = entry.get("size")
                digest = entry.get("sha256")
                if not isinstance(size, int) or size < 0 or not isinstance(digest, str):
                    raise BackupRejected("backup file metadata is malformed")
                expected[name] = (size, digest)
            if not {"genesis.json", "policy.json"}.issubset(expected) or set(names) != set(expected) | {"manifest.json"}:
                raise BackupRejected("backup file set is invalid")
            files = {name: bundle.read(name) for name in expected}
    except (BadZipFile, KeyError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BackupRejected("backup archive is malformed") from exc

    for name, data in files.items():
        size, digest = expected[name]
        if len(data) != size or _sha256(data) != digest:
            raise BackupRejected(f"backup file fingerprint mismatch: {name}")

    root = Path(store_root).resolve()
    destination = _safe_portfolio_path(root, target_id)
    if destination.exists():
        raise BackupRejected("restore destination already exists")
    root.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix=f".{target_id}.restore-", dir=root))
    temp_portfolio = temp / target_id
    temp_portfolio.mkdir()
    try:
        for name, data in files.items():
            (temp_portfolio / name).write_bytes(data)
        B41Broker.open(temp, target_id)
        temp_portfolio.replace(destination)
    except Exception as exc:
        if isinstance(exc, BackupRejected):
            raise
        raise BackupRejected("restored portfolio failed broker validation") from exc
    finally:
        if temp.exists():
            shutil.rmtree(temp)
    return destination


__all__ = ["BACKUP_SCHEMA", "BackupRejected", "backup_portfolio", "restore_portfolio"]
