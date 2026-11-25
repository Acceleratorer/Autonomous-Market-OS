"""Immutable, local-only storage and deterministic replay for BTC assessments."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from typing import Any, Iterator, Mapping

from .btc_evidence_packet import packet_fingerprint
from .btc_local_assessor import (
    LOCAL_MODEL,
    LOCAL_PROVIDER,
    LocalAssessorError,
    LocalAssessmentRecord,
    LocalB31Assessor,
    _canonical_json,
    _sha256,
)


MAX_PACKET_BYTES = 64 * 1024
MAX_RUN_BYTES = 2 * 1024 * 1024
MAX_STORE_BYTES = 1024 * 1024 * 1024
_RUN_ID = re.compile(r"[0-9a-f]{32}\Z")
_BUNDLE_SCHEMA = "market-os.btc-local-assessment-run.v1"
_STORE_LOCK_NAME = ".writer.lock"


class LocalAssessmentStoreError(ValueError):
    """A local assessment bundle failed integrity, identity, or storage checks."""


class LocalAssessmentStoreCapacityError(LocalAssessmentStoreError):
    """The local assessment store reached its configured byte limit."""

    code = "store_capacity_exceeded"


@contextmanager
def _exclusive_store_lock(runs: Path) -> Iterator[None]:
    descriptor = os.open(runs / _STORE_LOCK_NAME, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        if os.name == "nt":
            import msvcrt

            if os.fstat(descriptor).st_size == 0:
                os.write(descriptor, b"\0")
            os.lseek(descriptor, 0, os.SEEK_SET)
            msvcrt.locking(descriptor, msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                os.lseek(descriptor, 0, os.SEEK_SET)
                msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(descriptor, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        os.close(descriptor)


def _store_usage_bytes(runs: Path) -> int:
    total = 0
    lock_path = runs / _STORE_LOCK_NAME
    for path in runs.rglob("*"):
        if path == lock_path:
            continue
        try:
            entry = path.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISREG(entry.st_mode) or stat.S_ISLNK(entry.st_mode):
            total += entry.st_size
    return total


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise LocalAssessmentStoreError(f"duplicate JSON field: {key}")
        value[key] = item
    return value


def _read_json(path: Path, byte_limit: int) -> Any:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > byte_limit:
        raise LocalAssessmentStoreError("assessment bundle is missing, linked, or exceeds its byte limit")
    try:
        return json.loads(path.read_bytes(), object_pairs_hook=_reject_duplicate_keys)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise LocalAssessmentStoreError("assessment bundle is not valid JSON") from exc


def _bundle_fingerprint(packet: Mapping[str, Any], record: Mapping[str, Any]) -> str:
    return _sha256(_canonical_json({"schema": _BUNDLE_SCHEMA, "packet": packet, "record": record}))


class _RecordedRuntime:
    def __init__(self, record: LocalAssessmentRecord) -> None:
        self.provider = record.provider
        self.model = record.model
        self.model_version = record.model_version
        self.runtime_version = record.runtime_version
        self.manifest_fingerprint = record.runtime_manifest_fingerprint
        self.record = record

    def start(self) -> None:
        if self.record.failure is not None and self.record.raw_completion_response is None and self.record.started_at_ms is None:
            failure = self.record.failure
            raise LocalAssessorError(
                str(failure["code"]),
                str(failure["message"]),
                retryable=bool(failure["retryable"]),
            )

    def complete(self, _messages: list[dict[str, str]], _schema: dict[str, Any], *, timeout_seconds: float) -> tuple[dict[str, Any], int]:
        if self.record.raw_completion_response is None:
            failure = self.record.failure or {}
            raise LocalAssessorError(
                str(failure.get("code", "local_runtime_failed")),
                str(failure.get("message", "recorded local completion is unavailable")),
                retryable=bool(failure.get("retryable", False)),
            )
        if not 1 <= timeout_seconds <= 300:
            raise ValueError("timeout_seconds must be between 1 and 300")
        return dict(self.record.raw_completion_response), self.record.latency_ms or 0


def _replay_clock(record: LocalAssessmentRecord):
    values = (
        record.eligibility_checked_at_ms if record.eligibility_checked_at_ms is not None else record.recorded_at_ms,
        record.started_at_ms if record.started_at_ms is not None else record.recorded_at_ms,
        record.received_at_ms if record.received_at_ms is not None else record.recorded_at_ms,
        record.recorded_at_ms,
    )
    index = 0

    def now_ms() -> int:
        nonlocal index
        value = values[min(index, len(values) - 1)]
        index += 1
        return value

    return now_ms


class LocalAssessmentStore:
    """Store bounded write-once bundles under a fail-closed aggregate byte cap."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.runs = self.root / "runs"

    def persist(self, packet: Mapping[str, Any], record: LocalAssessmentRecord) -> Path:
        if not isinstance(packet, Mapping) or len(_canonical_json(packet)) > MAX_PACKET_BYTES:
            raise LocalAssessmentStoreError("assessment packet is not an object within its byte limit")
        record_data = asdict(record)
        if record.schema != "market-os.btc-local-assessment-record.v1" or not _RUN_ID.fullmatch(record.run_id):
            raise LocalAssessmentStoreError("assessment record schema or run ID is invalid")
        if record.provider != LOCAL_PROVIDER or record.model != LOCAL_MODEL:
            raise LocalAssessmentStoreError("local assessment store accepts only the pinned local Qwen assessor identity")
        if record.decision_authority != "advisory_only" or record.eligible_for_market_fusion or record.eligible_for_paper_decision:
            raise LocalAssessmentStoreError("local evidence assessments must remain advisory and ineligible for fusion or paper decisions")
        if record.packet_fingerprint is not None:
            try:
                if packet_fingerprint(packet) != record.packet_fingerprint:
                    raise LocalAssessmentStoreError("assessment record packet fingerprint does not match its input")
            except (TypeError, ValueError) as exc:
                raise LocalAssessmentStoreError("assessment input packet fingerprint is invalid") from exc
        fingerprint = _bundle_fingerprint(packet, record_data)
        bundle = {
            "schema": _BUNDLE_SCHEMA,
            "packet": packet,
            "record": record_data,
            "bundle_fingerprint": fingerprint,
        }
        encoded = (json.dumps(bundle, ensure_ascii=True, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")
        if len(encoded) > MAX_RUN_BYTES:
            raise LocalAssessmentStoreError("assessment run bundle exceeds its byte limit")

        self.runs.mkdir(parents=True, exist_ok=True)
        destination = self.runs / f"{record.run_id}.json"
        try:
            with _exclusive_store_lock(self.runs):
                if destination.exists():
                    existing = self._load(record.run_id)
                    if existing["bundle_fingerprint"] == fingerprint:
                        return destination
                    raise LocalAssessmentStoreError("run ID already exists with different assessment content")

                used_bytes = _store_usage_bytes(self.runs)
                if used_bytes + len(encoded) > MAX_STORE_BYTES:
                    raise LocalAssessmentStoreCapacityError(
                        "[store_capacity_exceeded] assessment store byte limit would be exceeded: "
                        f"{used_bytes} + {len(encoded)} > {MAX_STORE_BYTES}"
                    )

                handle, temporary_name = tempfile.mkstemp(prefix=".assessment-", suffix=".tmp", dir=self.runs)
                temporary = Path(temporary_name)
                try:
                    with os.fdopen(handle, "wb") as stream:
                        if os.name != "nt":
                            os.chmod(temporary, 0o600)
                        stream.write(encoded)
                        stream.flush()
                        os.fsync(stream.fileno())
                    try:
                        os.link(temporary, destination)
                    except FileExistsError:
                        existing = self._load(record.run_id)
                        if existing["bundle_fingerprint"] != fingerprint:
                            raise LocalAssessmentStoreError("run ID already exists with different assessment content")
                    if os.name != "nt":
                        directory_fd = os.open(self.runs, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
                        try:
                            os.fsync(directory_fd)
                        finally:
                            os.close(directory_fd)
                    return destination
                finally:
                    temporary.unlink(missing_ok=True)
        except OSError as exc:
            raise LocalAssessmentStoreError("could not durably persist the local assessment bundle") from exc

    def _load(self, run_id: str) -> dict[str, Any]:
        if not _RUN_ID.fullmatch(run_id):
            raise LocalAssessmentStoreError("run ID must be 32 lowercase hexadecimal characters")
        bundle = _read_json(self.runs / f"{run_id}.json", MAX_RUN_BYTES)
        if not isinstance(bundle, dict) or set(bundle) != {"schema", "packet", "record", "bundle_fingerprint"} or bundle.get("schema") != _BUNDLE_SCHEMA:
            raise LocalAssessmentStoreError("assessment bundle schema or fields are invalid")
        packet, record_data, fingerprint = bundle["packet"], bundle["record"], bundle["bundle_fingerprint"]
        if not isinstance(packet, dict) or not isinstance(record_data, dict) or not isinstance(fingerprint, str):
            raise LocalAssessmentStoreError("assessment bundle fields have invalid types")
        if _bundle_fingerprint(packet, record_data) != fingerprint:
            raise LocalAssessmentStoreError("assessment bundle fingerprint mismatch")
        if record_data.get("run_id") != run_id:
            raise LocalAssessmentStoreError("assessment bundle run ID does not match its filename")
        return bundle

    def replay(self, run_id: str) -> dict[str, Any]:
        """Re-run packet gates and response normalization without any model call."""
        bundle = self._load(run_id)
        try:
            record = LocalAssessmentRecord(**bundle["record"])
        except (TypeError, ValueError) as exc:
            raise LocalAssessmentStoreError("assessment record does not match the current local schema") from exc
        if record.decision_authority != "advisory_only" or record.eligible_for_market_fusion or record.eligible_for_paper_decision:
            raise LocalAssessmentStoreError("persisted assessment carries forbidden decision authority")
        if record.provider != LOCAL_PROVIDER or record.model != LOCAL_MODEL:
            raise LocalAssessmentStoreError("persisted run does not identify the pinned local Qwen assessor")
        if record.packet_fingerprint is not None and packet_fingerprint(bundle["packet"]) != record.packet_fingerprint:
            raise LocalAssessmentStoreError("persisted packet fingerprint does not match its assessment")

        if record.failure is None:
            if record.raw_completion_response is None or record.response_fingerprint is None:
                raise LocalAssessmentStoreError("successful assessment is missing its raw local response")
            if _sha256(_canonical_json(record.raw_completion_response)) != record.response_fingerprint:
                raise LocalAssessmentStoreError("raw local response fingerprint mismatch")
            expected_run_id = _sha256(_canonical_json({
                "request": record.request_fingerprint,
                "response": record.response_fingerprint,
                "received_at_ms": record.received_at_ms,
            }))[:32]
        else:
            expected_run_id = _sha256(_canonical_json({
                "request": record.request_fingerprint,
                "error": record.failure["code"],
                "at": record.recorded_at_ms,
            }))[:32]
        if expected_run_id != record.run_id:
            raise LocalAssessmentStoreError("assessment record run ID fingerprint mismatch")

        replayed = LocalB31Assessor(_RecordedRuntime(record), clock=_replay_clock(record)).assess(bundle["packet"])
        if _canonical_json(asdict(replayed)) != _canonical_json(asdict(record)):
            raise LocalAssessmentStoreError("offline replay differs from the stored assessment record")
        return {
            "status": "verified",
            "verification": "offline-packet-gates-and-response-normalization",
            "run_id": run_id,
            "provider": record.provider,
            "model": record.model,
            "outcome": record.outcome,
            "packet_fingerprint": record.packet_fingerprint,
            "bundle_fingerprint": bundle["bundle_fingerprint"],
            "network_requests": 0,
            "inference_calls": 0,
        }
