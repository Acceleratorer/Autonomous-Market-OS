"""Build a local, timestamp-honest document corpus from an approved B1 run."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .btc_history import HistoryStore
from .btc_evidence_packet import SourceTimeBounds, observation_id_for_b2_feature
from .providers import DocumentRecord, LicenseMetadata, Provenance


SOURCE_CORPUS_SCHEMA = "market-os.btc-source-corpus.v1"
SOURCE_DOCUMENT_SCHEMA = "market-os.btc-source-document.v1"
APPROVED_DATASET_REVISION = "btc-history-9c58a3ac5cfd05c7398e"
APPROVED_MANIFEST_ID = "btc-history-manifest-6307b278cdc684f4dc42"
MAX_ROWS = 43_200
DEPENDENCY_GROUP_ID = "binance-vision:BTCUSDT:1m"
_UTC = timezone.utc


class SourceCorpusError(ValueError):
    """The local B1 data cannot produce the bounded BTC source corpus."""


@dataclass(frozen=True)
class LoadedBTCCorpus:
    """Hydrated local documents and their event/availability lineage."""

    dataset_revision: str
    documents: tuple[DocumentRecord, ...]
    contents_by_document_id: Mapping[str, str]
    source_time_bounds: Mapping[str, SourceTimeBounds]
    canonical_fingerprints: Mapping[str, str]

    def for_b2_feature(self, feature: Mapping[str, Any]) -> "LoadedBTCCorpus":
        """Return only the six B1 candle documents referenced by one B2 row."""
        observation_id_for_b2_feature(feature)
        if feature.get("dataset_revision") != self.dataset_revision:
            raise SourceCorpusError("B2 feature and source corpus dataset revisions do not match")
        document_id_by_fingerprint = {
            fingerprint: document_id
            for document_id, fingerprint in self.canonical_fingerprints.items()
        }
        if len(document_id_by_fingerprint) != len(self.canonical_fingerprints):
            raise SourceCorpusError("source corpus canonical candle fingerprints are not unique")
        references = feature["input_refs"]
        document_ids: list[str] = []
        for reference in references:
            document_id = document_id_by_fingerprint.get(reference["canonical_fingerprint"])
            if document_id is None:
                raise SourceCorpusError("B2 feature references a candle outside the source corpus")
            document_ids.append(document_id)
        if len(document_ids) != 6 or len(set(document_ids)) != 6:
            raise SourceCorpusError("B2 feature must map to exactly six unique candle documents")
        documents_by_id = {document.document_id: document for document in self.documents}
        return LoadedBTCCorpus(
            self.dataset_revision,
            tuple(documents_by_id[document_id] for document_id in document_ids),
            {document_id: self.contents_by_document_id[document_id] for document_id in document_ids},
            {document_id: self.source_time_bounds[document_id] for document_id in document_ids},
            {document_id: self.canonical_fingerprints[document_id] for document_id in document_ids},
        )


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _timestamp_ms(value: str, field: str) -> int:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError) as exc:
        raise SourceCorpusError(f"{field} must be an ISO-8601 UTC timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != _UTC.utcoffset(None):
        raise SourceCorpusError(f"{field} must use UTC")
    return int(parsed.timestamp() * 1000)


def build_btc_source_corpus(
    history_store_root: str | Path = ".market_os/btc-history",
    *,
    dataset_revision: str = APPROVED_DATASET_REVISION,
    manifest_id: str = APPROVED_MANIFEST_ID,
) -> dict[str, Any]:
    """Materialize the approved B1 candles as local docs with unknown publish times preserved.

    Each document contains one finalized candle. ``source_published_at`` stays
    null because B1 retained event time and local receipt time, not the original
    Binance publication time. The artifact is not a point-in-time feature feed.
    """
    if dataset_revision != APPROVED_DATASET_REVISION or manifest_id != APPROVED_MANIFEST_ID:
        raise SourceCorpusError("this corpus builder is restricted to the approved B1 dataset and manifest")
    root = Path(history_store_root).expanduser().resolve()
    if str(root).startswith("\\\\"):
        raise SourceCorpusError("BTC research data must remain on a local volume")

    store = HistoryStore(root, read_only=True)
    source_manifest = store.inspect_manifest(manifest_id)
    if (
        source_manifest.get("dataset_revision") != dataset_revision
        or source_manifest.get("manifest_id") != manifest_id
        or (source_manifest.get("venue"), source_manifest.get("symbol"), source_manifest.get("interval"))
        != ("BINANCE_SPOT", "BTCUSDT", "1m")
    ):
        raise SourceCorpusError("B1 manifest identity does not match the approved BTCUSDT Spot 1m scope")
    start_ms = int(datetime(2026, 10, 19, tzinfo=_UTC).timestamp() * 1000)
    end_ms = int(datetime(2026, 11, 18, tzinfo=_UTC).timestamp() * 1000)
    if (
        source_manifest.get("requested_start_ms") != start_ms
        or source_manifest.get("requested_end_ms_exclusive") != end_ms
        or source_manifest.get("observed_start_ms") != start_ms
        or source_manifest.get("observed_end_ms_exclusive") != end_ms
        or source_manifest.get("canonical_candle_count") != MAX_ROWS
        or source_manifest.get("gaps") not in ({}, [])
    ):
        raise SourceCorpusError("B1 manifest is outside the approved contiguous 30-day and row-count bounds")

    archive_by_date: dict[str, dict[str, Any]] = {}
    source_archives = source_manifest.get("raw_source_artifacts")
    if not isinstance(source_archives, list) or len(source_archives) != 30:
        raise SourceCorpusError("B1 manifest must contain exactly 30 approved daily archives")
    expected_dates = {
        (datetime(2026, 10, 19, tzinfo=_UTC) + timedelta(days=offset)).date().isoformat()
        for offset in range(30)
    }
    for archive in source_archives:
        if not isinstance(archive, dict):
            raise SourceCorpusError("B1 archive metadata must be an object")
        archive_date = archive.get("date")
        digest = archive.get("archive_sha256")
        if (
            not isinstance(archive_date, str)
            or not isinstance(digest, str)
            or len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest)
            or archive_date in archive_by_date
        ):
            raise SourceCorpusError("B1 daily archive identity or SHA-256 is invalid")
        archive_by_date[archive_date] = archive
    if set(archive_by_date) != expected_dates or any(archive.get("row_count") != 1440 for archive in archive_by_date.values()):
        raise SourceCorpusError("B1 source archives do not match the approved 30 complete UTC dates")

    candles = store.inspect_candles(dataset_revision)
    if len(candles) != MAX_ROWS:
        raise SourceCorpusError("canonical B1 row count does not match the approved 43,200-row bound")

    rows: list[dict[str, Any]] = []
    expected_open_ms = start_ms
    for candle in candles:
        open_ms = candle["open_time_ms"]
        close_ms = candle["close_time_ms"]
        if isinstance(open_ms, bool) or not isinstance(open_ms, int) or isinstance(close_ms, bool) or not isinstance(close_ms, int):
            raise SourceCorpusError("B1 candle event timestamps must be integer milliseconds")
        if open_ms != expected_open_ms or close_ms != open_ms + 60_000:
            raise SourceCorpusError("B1 candles are not the approved contiguous sequence of closed one-minute rows")
        expected_open_ms += 60_000
        archive_date = datetime.fromtimestamp(open_ms / 1000, _UTC).date().isoformat()
        archive = archive_by_date.get(archive_date)
        if archive is None:
            raise SourceCorpusError("B1 candle has no matching daily archive")
        local_received_at = candle.get("received_at")
        available_at = candle.get("availability_timestamp")
        received_ms = _timestamp_ms(local_received_at, "B1 local receipt timestamp")
        available_ms = _timestamp_ms(available_at, "B1 availability timestamp")
        if available_ms < max(received_ms, close_ms):
            raise SourceCorpusError("B1 availability timestamp precedes local receipt or candle close")

        source_ref = f"binance-vision:BTCUSDT-1m-{archive_date}.zip#sha256={archive['archive_sha256']}"
        document_id = f"btc-{dataset_revision}-{open_ms}"
        content = "\n".join((
            "Instrument: BTCUSDT Spot, one-minute finalized candle",
            f"Event start UTC milliseconds: {open_ms}",
            f"Event end UTC milliseconds: {close_ms}",
            f"Open: {candle['open_decimal']}",
            f"High: {candle['high_decimal']}",
            f"Low: {candle['low_decimal']}",
            f"Close: {candle['close_decimal']}",
            f"Base volume: {candle['volume_decimal']}",
            f"B1 canonical candle SHA-256: {candle['canonical_fingerprint']}",
            f"Binance Vision archive: {archive['archive_filename']}",
        ))
        rows.append({
            "schema": SOURCE_DOCUMENT_SCHEMA,
            "document_id": document_id,
            "title": f"BTCUSDT Spot 1m candle at {open_ms} UTC ms",
            "publisher": "Binance Vision daily archive",
            "source_ref": source_ref,
            "content": content,
            "content_hash": _sha256(content.encode("utf-8")),
            "market": {"venue": "binance", "symbol": "BTCUSDT", "market_type": "spot", "interval": "1m"},
            "event_time": {"event_start_ms": open_ms, "event_end_ms": close_ms},
            "source_published_at": None,
            "publication_time_status": "unknown-not-captured",
            "availability": {
                "available_at_ms": available_ms,
                "available_at": available_at,
                "local_received_at": local_received_at,
                "timestamp_basis": "local raw-artifact timestamp; exact HTTP response time was not retained",
            },
            "dependency_group_id": DEPENDENCY_GROUP_ID,
            "provenance": {
                "provider": "binance_vision_archive",
                "dataset_revision": dataset_revision,
                "manifest_id": manifest_id,
                "archive_date": archive_date,
                "archive_sha256": archive["archive_sha256"],
                "canonical_candle_sha256": candle["canonical_fingerprint"],
            },
        })

    documents_raw = b"".join(_canonical(row) + b"\n" for row in rows)
    source_manifest_projection = {
        "manifest_id": manifest_id,
        "dataset_revision": dataset_revision,
        "canonical_fingerprint": source_manifest["canonical_fingerprint"],
    }
    manifest_core = {
        "schema": SOURCE_CORPUS_SCHEMA,
        "status": "local-corpus-built-source-publication-time-unknown",
        "local_only": True,
        "personal_noncommercial_research": True,
        "redistribution": "not-permitted-by-owner-scope",
        "source_publication_time_status": "unknown-not-captured",
        "dataset_revision": dataset_revision,
        "source_manifest": source_manifest_projection,
        "source_manifest_fingerprint": _sha256(_canonical(source_manifest_projection)),
        "document_count": len(rows),
        "dependency_group_id": DEPENDENCY_GROUP_ID,
        "first_event_start_ms": rows[0]["event_time"]["event_start_ms"],
        "last_event_end_ms": rows[-1]["event_time"]["event_end_ms"],
        "local_availability_min_ms": min(row["availability"]["available_at_ms"] for row in rows),
        "local_availability_max_ms": max(row["availability"]["available_at_ms"] for row in rows),
        "documents_sha256": _sha256(documents_raw),
        "documents_bytes": len(documents_raw),
    }
    corpus_manifest = {**manifest_core, "corpus_fingerprint": _sha256(_canonical(manifest_core))}

    output_dir = root.parent / "btc-evidence-corpus" / dataset_revision
    documents_path = output_dir / "documents.jsonl"
    manifest_path = output_dir / "manifest.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_raw = _canonical(corpus_manifest) + b"\n"
    if documents_path.exists() or manifest_path.exists():
        if (
            documents_path.is_file()
            and manifest_path.is_file()
            and documents_path.read_bytes() == documents_raw
            and manifest_path.read_bytes() == manifest_raw
        ):
            return {"output_dir": str(output_dir), **corpus_manifest}
        raise SourceCorpusError("immutable local BTC source corpus already exists with different content")
    documents_path.write_bytes(documents_raw)
    manifest_path.write_bytes(manifest_raw)
    return {"output_dir": str(output_dir), **corpus_manifest}


def load_btc_source_corpus(corpus_dir: str | Path) -> LoadedBTCCorpus:
    """Verify and hydrate corpus rows using conservative local availability.

    The upstream publication time remains unknown. ``DocumentRecord`` requires
    ``published_at``, so this projection sets it to the recorded local
    availability timestamp; the packet builder will consequently reject these
    retrospective rows for any earlier historical B2 decision.
    """
    root = Path(corpus_dir).expanduser().resolve()
    if str(root).startswith("\\\\"):
        raise SourceCorpusError("BTC research data must remain on a local volume")
    manifest_path = root / "manifest.json"
    documents_path = root / "documents.jsonl"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        documents_raw = documents_path.read_bytes()
    except (OSError, json.JSONDecodeError) as exc:
        raise SourceCorpusError("local BTC source corpus is incomplete or unreadable") from exc
    if not isinstance(manifest, dict) or manifest.get("schema") != SOURCE_CORPUS_SCHEMA:
        raise SourceCorpusError("unsupported BTC source corpus manifest")
    if (
        manifest.get("dataset_revision") != APPROVED_DATASET_REVISION
        or manifest.get("local_only") is not True
        or manifest.get("personal_noncommercial_research") is not True
        or manifest.get("redistribution") != "not-permitted-by-owner-scope"
        or manifest.get("source_publication_time_status") != "unknown-not-captured"
    ):
        raise SourceCorpusError("this loader only accepts corpora with explicit unknown source publication time")
    manifest_core = {key: value for key, value in manifest.items() if key != "corpus_fingerprint"}
    if manifest.get("corpus_fingerprint") != _sha256(_canonical(manifest_core)):
        raise SourceCorpusError("BTC source corpus manifest fingerprint mismatch")
    if len(documents_raw) != manifest.get("documents_bytes") or _sha256(documents_raw) != manifest.get("documents_sha256"):
        raise SourceCorpusError("BTC source corpus document artifact fingerprint mismatch")

    documents: list[DocumentRecord] = []
    contents: dict[str, str] = {}
    source_bounds: dict[str, SourceTimeBounds] = {}
    canonical_fingerprints: dict[str, str] = {}
    for line_number, line in enumerate(documents_raw.splitlines(), 1):
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SourceCorpusError(f"invalid corpus document JSON at line {line_number}") from exc
        if not isinstance(record, dict) or record.get("schema") != SOURCE_DOCUMENT_SCHEMA:
            raise SourceCorpusError(f"unsupported corpus document at line {line_number}")
        document_id = record.get("document_id")
        content = record.get("content")
        source_ref = record.get("source_ref")
        event_time = record.get("event_time")
        availability = record.get("availability")
        provenance = record.get("provenance")
        if (
            not isinstance(document_id, str) or not document_id.strip()
            or not isinstance(content, str) or not content.strip()
            or not isinstance(source_ref, str) or not source_ref.strip()
            or not isinstance(event_time, dict)
            or not isinstance(availability, dict)
            or not isinstance(provenance, dict)
            or record.get("market") != {"venue": "binance", "symbol": "BTCUSDT", "market_type": "spot", "interval": "1m"}
            or record.get("source_published_at") is not None
            or record.get("dependency_group_id") != DEPENDENCY_GROUP_ID
        ):
            raise SourceCorpusError(f"incomplete corpus document at line {line_number}")
        if document_id in contents:
            raise SourceCorpusError(f"duplicate corpus document ID at line {line_number}")
        content_hash = record.get("content_hash")
        if not isinstance(content_hash, str) or _sha256(content.encode("utf-8")) != content_hash:
            raise SourceCorpusError(f"corpus document content hash mismatch at line {line_number}")
        if provenance.get("dataset_revision") != manifest.get("dataset_revision"):
            raise SourceCorpusError(f"corpus document dataset lineage mismatch at line {line_number}")
        for field in ("archive_sha256", "canonical_candle_sha256"):
            digest = provenance.get(field)
            if not isinstance(digest, str) or len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
                raise SourceCorpusError(f"corpus document {field} is invalid at line {line_number}")
        canonical_fingerprints[document_id] = provenance["canonical_candle_sha256"]
        event_start_ms = event_time.get("event_start_ms")
        event_end_ms = event_time.get("event_end_ms")
        available_at = availability.get("available_at")
        available_at_ms = availability.get("available_at_ms")
        if (
            isinstance(event_start_ms, bool) or not isinstance(event_start_ms, int)
            or isinstance(event_end_ms, bool) or not isinstance(event_end_ms, int)
            or event_end_ms != event_start_ms + 60_000
            or isinstance(available_at_ms, bool) or not isinstance(available_at_ms, int)
            or _timestamp_ms(available_at, "corpus available_at") != available_at_ms
            or available_at_ms < event_end_ms
        ):
            raise SourceCorpusError(f"invalid event or availability timestamps at line {line_number}")
        title = record.get("title")
        if not isinstance(title, str) or not title.strip():
            raise SourceCorpusError(f"corpus document title is missing at line {line_number}")
        document = DocumentRecord(
            document_id=document_id,
            title=title,
            publisher="Binance Vision",
            source_ref=source_ref,
            published_at=available_at,
            retrieved_at=available_at,
            symbols=("BTCUSDT",),
            media_type="text/plain",
            content_hash=content_hash,
            license=LicenseMetadata(
                classification="owner-scoped-local-research",
                attribution="Binance Vision",
                restrictions=("local-only", "personal-noncommercial", "no-redistribution"),
            ),
            provenance=Provenance(
                provider="binance_vision_archive",
                source_ref=source_ref,
                retrieved_at=available_at,
            ),
            content_ref=f"{documents_path.as_posix()}#{document_id}",
        )
        documents.append(document)
        contents[document_id] = content
        source_bounds[document_id] = SourceTimeBounds(
            event_start_ms=event_start_ms,
            event_end_ms=event_end_ms,
            dependency_group_id=DEPENDENCY_GROUP_ID,
            available_at_ms=available_at_ms,
        )
    if len(documents) != MAX_ROWS or len(documents) != manifest.get("document_count"):
        raise SourceCorpusError("BTC source corpus document count is outside the approved bound")
    return LoadedBTCCorpus(
        manifest["dataset_revision"],
        tuple(documents),
        contents,
        source_bounds,
        canonical_fingerprints,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the approved local BTC source corpus from B1")
    parser.add_argument("--history-store-root", default=".market_os/btc-history")
    parser.add_argument("--dataset-revision", default=APPROVED_DATASET_REVISION)
    parser.add_argument("--manifest-id", default=APPROVED_MANIFEST_ID)
    args = parser.parse_args()
    print(json.dumps(build_btc_source_corpus(
        args.history_store_root,
        dataset_revision=args.dataset_revision,
        manifest_id=args.manifest_id,
    ), sort_keys=True))


if __name__ == "__main__":
    main()
