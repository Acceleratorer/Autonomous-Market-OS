"""Local, opt-in backup and restore for the synthetic B4 portfolio store."""
from __future__ import annotations

from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
from contextlib import contextmanager
from typing import Any, Mapping
from zipfile import BadZipFile, ZIP_DEFLATED, ZipFile, ZipInfo

from .portfolio_broker import B41Broker, BrokerRejected, SCHEMA, _is_reparse_point


BACKUP_SCHEMA = "market-os.b4-11.portfolio-backup@v1"
RETENTION_PREFLIGHT_SCHEMA = "market-os.b4-20.retention-archive-preflight@v1"
_FILES = ("genesis.json", "policy.json", "ledger.jsonl", "checkpoint.json")
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 64 * 1024 * 1024
MAX_ARCHIVE_MANIFEST_BYTES = 1024 * 1024
MAX_ARCHIVE_BYTES = 128 * 1024 * 1024


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
    if _is_reparse_point(candidate):
        raise BackupRejected("portfolio directory cannot be a symlink")
    path = candidate.resolve()
    if path.parent != root:
        raise BackupRejected("portfolio_id escapes store root")
    return path


def _archive_digest(handle) -> str:
    digest = hashlib.sha256()
    size = 0
    handle.seek(0)
    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
        size += len(chunk)
        if size > MAX_ARCHIVE_BYTES:
            raise BackupRejected("archive is oversized")
        digest.update(chunk)
    handle.seek(0)
    return digest.hexdigest()


@contextmanager
def _archive_handle(archive_path: str | Path):
    """Open one regular archive file after rejecting symlinked path components."""
    candidate = Path(os.path.abspath(os.fspath(archive_path)))
    current = Path(candidate.anchor)
    for part in candidate.parts[1:]:
        current /= part
        if _is_reparse_point(current):
            raise BackupRejected("archive path contains a symlink or reparse point")
    try:
        handle = candidate.open("rb")
    except IsADirectoryError as exc:
        raise BackupRejected("archive is not a regular file") from exc
    try:
        opened = os.fstat(handle.fileno())
        path_info = candidate.lstat()
        if (
            _is_reparse_point(candidate)
            or not stat.S_ISREG(opened.st_mode)
            or (opened.st_dev, opened.st_ino) != (path_info.st_dev, path_info.st_ino)
        ):
            raise BackupRejected("archive path changed or is not a regular file")
        yield handle
    finally:
        handle.close()


def _archive_destination(archive_path: str | Path) -> Path:
    """Return an absolute archive path whose existing parents are local."""
    candidate = Path(os.path.abspath(os.fspath(archive_path)))
    current = Path(candidate.anchor)
    for part in candidate.parts[1:]:
        current /= part
        if _is_reparse_point(current):
            raise BackupRejected("archive path contains a symlink or reparse point")
    if candidate.parent.exists() and candidate.parent.resolve(strict=True) != candidate.parent:
        raise BackupRejected("archive parent must remain local")
    return candidate


def _validate_archive_for_preflight(archive_path: str | Path, portfolio_id: str) -> dict[str, Any]:
    """Validate one archive without extracting or returning its contents."""
    candidate = Path(os.path.abspath(os.fspath(archive_path)))
    try:
        with _archive_handle(candidate) as archive_handle:
            before_digest = _archive_digest(archive_handle)
            before_stat = os.fstat(archive_handle.fileno())
            with ZipFile(archive_handle) as bundle:
                infos = bundle.infolist()
                names = [info.filename for info in infos]
                if len(names) != len(set(names)) or "manifest.json" not in names:
                    raise BackupRejected("archive member set is invalid")
                total_size = sum(info.file_size for info in infos)
                if total_size > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
                    raise BackupRejected("archive is oversized")
                manifest_info = bundle.getinfo("manifest.json")
                if manifest_info.file_size > MAX_ARCHIVE_MANIFEST_BYTES:
                    raise BackupRejected("archive manifest is oversized")
                manifest = json.loads(bundle.read("manifest.json"))
                if not isinstance(manifest, Mapping) or set(manifest) != {"schema", "broker_schema", "portfolio_id", "files"} or manifest.get("schema") != BACKUP_SCHEMA or manifest.get("broker_schema") != SCHEMA:
                    raise BackupRejected("archive schema is unsupported")
                if manifest.get("portfolio_id") != portfolio_id:
                    raise BackupRejected("archive portfolio identity mismatch")
                entries = manifest.get("files")
                if not isinstance(entries, list):
                    raise BackupRejected("archive manifest is malformed")
                expected: dict[str, tuple[int, str]] = {}
                for entry in entries:
                    if not isinstance(entry, Mapping) or set(entry) != {"path", "size", "sha256"}:
                        raise BackupRejected("archive manifest is malformed")
                    name, size, digest = entry.get("path"), entry.get("size"), entry.get("sha256")
                    if name not in _FILES or name in expected or Path(name).name != name:
                        raise BackupRejected("archive file path is invalid")
                    if isinstance(size, bool) or not isinstance(size, int) or size < 0 or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                        raise BackupRejected("archive file metadata is malformed")
                    expected[name] = (size, digest)
                if not {"genesis.json", "policy.json"}.issubset(expected) or set(names) != set(expected) | {"manifest.json"}:
                    raise BackupRejected("archive file set is incomplete")
                for name, (expected_size, expected_digest) in expected.items():
                    info = bundle.getinfo(name)
                    if info.file_size != expected_size:
                        raise BackupRejected(f"archive file size mismatch: {name}")
                    digest = hashlib.sha256()
                    actual_size = 0
                    with bundle.open(info) as member:
                        for chunk in iter(lambda: member.read(1024 * 1024), b""):
                            actual_size += len(chunk)
                            if actual_size > expected_size:
                                raise BackupRejected(f"archive file size mismatch: {name}")
                            digest.update(chunk)
                    if actual_size != expected_size or digest.hexdigest() != expected_digest:
                        raise BackupRejected(f"archive file fingerprint mismatch: {name}")
            after_digest = _archive_digest(archive_handle)
            after_stat = os.fstat(archive_handle.fileno())
            try:
                current_path_stat = candidate.lstat()
            except FileNotFoundError as exc:
                raise BackupRejected("archive changed during validation") from exc
            if (
                before_digest != after_digest
                or (before_stat.st_size, before_stat.st_mtime_ns) != (after_stat.st_size, after_stat.st_mtime_ns)
                or (before_stat.st_dev, before_stat.st_ino) != (current_path_stat.st_dev, current_path_stat.st_ino)
            ):
                raise BackupRejected("archive changed during validation")
    except FileNotFoundError:
        raise
    except (BadZipFile, KeyError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BackupRejected("archive is malformed") from exc
    manifest_bytes = _canonical(manifest).encode("utf-8")
    return {
        "status": "valid",
        "archive_sha256": after_digest,
        "manifest_fingerprint": _sha256(manifest_bytes),
        "member_count": len(expected),
        "uncompressed_bytes": sum(size for size, _ in expected.values()),
    }


def _archive_preflight_status(archive_path: str | Path | None, portfolio_id: str) -> dict[str, Any]:
    if archive_path is None:
        return {"status": "not_supplied"}
    try:
        return _validate_archive_for_preflight(archive_path, portfolio_id)
    except FileNotFoundError:
        return {"status": "missing", "reason": "archive_missing"}
    except BackupRejected as exc:
        message = str(exc)
        reason = "archive_invalid"
        for prefix, code in (("archive is a symlink", "archive_symlink"), ("archive path contains", "archive_symlink"), ("archive path changed", "archive_symlink"), ("archive is oversized", "archive_oversized"), ("archive portfolio identity mismatch", "archive_identity_mismatch"), ("archive file fingerprint mismatch", "archive_fingerprint_mismatch"), ("archive changed", "archive_changed"), ("archive schema", "archive_schema_invalid")):
            if message.startswith(prefix):
                reason = code
                break
        return {"status": "invalid", "reason": reason}
    except (OSError, TypeError, ValueError):
        return {"status": "invalid", "reason": "archive_path_invalid"}


def preflight_retention_archive(
    store_root: str | Path,
    portfolio_id: str,
    archive_path: str | Path | None = None,
) -> dict[str, Any]:
    """Return bounded retention/archive evidence without changing local state."""
    try:
        broker = B41Broker.open(store_root, portfolio_id, read_only=True)
    except (BrokerRejected, OSError, TypeError, ValueError) as exc:
        raise BackupRejected("portfolio failed broker validation") from exc
    storage = broker.inspect_storage_state()
    source_files = storage["files"]
    ledger = source_files["ledger.jsonl"]
    checkpoint = source_files["checkpoint.json"]
    record_count = ledger.get("record_count", 0)
    reservations = broker.inspect_jsonable("reservations")
    final_storage = broker.inspect_storage_state()
    if final_storage != storage:
        raise BackupRejected("portfolio changed during retention preflight")
    return {
        "schema": RETENTION_PREFLIGHT_SCHEMA,
        "portfolio": {
            "portfolio_id": broker.genesis.portfolio_id,
            "mode": "shared" if broker.genesis.shared_portfolio_id else "isolated",
            "member_count": len(broker.genesis.member_strategy_ids) if broker.genesis.shared_portfolio_id else 1,
            "open_order_count": len(broker.open_orders),
        },
        "source_retention": "indefinite-local",
        "deletion_eligible": False,
        "zero_event_ambiguous": not ledger["present"] and not checkpoint["present"],
        "source_files": source_files,
        "ledger": {"present": ledger["present"], "record_count": record_count, "size": ledger.get("size"), "sha256": ledger.get("sha256")},
        "checkpoint": {"present": checkpoint["present"], "status": storage["checkpoint_status"], "size": checkpoint.get("size"), "sha256": checkpoint.get("sha256")},
        "reservations": reservations,
        "archive": _archive_preflight_status(archive_path, broker.genesis.portfolio_id),
    }


def backup_portfolio(store_root: str | Path, portfolio_id: str, archive_path: str | Path) -> Path:
    """Create an immutable local ZIP backup without changing the portfolio."""
    source = _safe_portfolio_path(store_root, portfolio_id)
    archive = _archive_destination(archive_path)
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
    archive = _archive_destination(archive)
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
        try:
            os.link(temp, archive)
        except FileExistsError as exc:
            raise BackupRejected("backup archive already exists") from exc
        except OSError as exc:
            raise BackupRejected("backup archive could not be published atomically") from exc
    finally:
        temp.unlink(missing_ok=True)
    return archive


def restore_portfolio(archive_path: str | Path, store_root: str | Path, portfolio_id: str | None = None) -> Path:
    """Verify and restore a backup into a new portfolio directory."""
    archive = Path(os.path.abspath(os.fspath(archive_path)))
    try:
        with _archive_handle(archive) as archive_handle, ZipFile(archive_handle) as bundle:
            names = bundle.namelist()
            if len(names) != len(set(names)) or "manifest.json" not in names:
                raise BackupRejected("backup archive members are invalid")
            archive_handle.seek(0, os.SEEK_END)
            if archive_handle.tell() > MAX_ARCHIVE_BYTES:
                raise BackupRejected("backup archive is oversized")
            archive_handle.seek(0)
            manifest = json.loads(bundle.read("manifest.json"))
            if not isinstance(manifest, Mapping) or manifest.get("schema") != BACKUP_SCHEMA or manifest.get("broker_schema") != SCHEMA:
                raise BackupRejected("backup schema is unsupported")
            manifest_info = bundle.getinfo("manifest.json")
            if manifest_info.file_size > MAX_ARCHIVE_MANIFEST_BYTES:
                raise BackupRejected("backup manifest is oversized")
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
            if sum(size for size, _ in expected.values()) > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
                raise BackupRejected("backup archive is oversized")
            files = {name: bundle.read(name) for name in expected}
    except FileNotFoundError as exc:
        raise BackupRejected("backup archive is missing") from exc
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
    staging_root = Path(tempfile.mkdtemp(prefix=f".{target_id}.restore-", dir=root))
    staging_portfolio = staging_root / target_id
    staging_portfolio.mkdir()
    try:
        for name, data in files.items():
            (staging_portfolio / name).write_bytes(data)
        B41Broker.open(staging_root, target_id)
        # Publish one complete validated directory with an atomic no-overwrite
        # rename. A file-by-file move could leave a partial destination after
        # an interruption.
        try:
            staging_portfolio.rename(destination)
        except FileExistsError as exc:
            raise BackupRejected("restore destination already exists") from exc
        except OSError as exc:
            raise BackupRejected("restored portfolio could not be published atomically") from exc
    except Exception as exc:
        if isinstance(exc, BackupRejected):
            raise
        raise BackupRejected("restored portfolio failed broker validation") from exc
    finally:
        if staging_root.exists():
            shutil.rmtree(staging_root)
    return destination


__all__ = ["BACKUP_SCHEMA", "RETENTION_PREFLIGHT_SCHEMA", "BackupRejected", "backup_portfolio", "preflight_retention_archive", "restore_portfolio"]
