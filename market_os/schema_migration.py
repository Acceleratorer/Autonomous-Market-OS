"""Copy-on-write B4.18 migration for synthetic local portfolio stores."""
from __future__ import annotations

from pathlib import Path
import hashlib
import json
import os
import shutil
import tempfile
from typing import Any, Mapping
from zipfile import ZipFile

from .portfolio_backup import BACKUP_SCHEMA, backup_portfolio
from .portfolio_broker import (
    B41Broker,
    B41Genesis,
    B41Policy,
    BrokerRejected,
    EVENT_SCHEMA,
    GENESIS_SCHEMA,
    SHARED_GENESIS_SCHEMA,
    SNAPSHOT_SCHEMA,
    SCHEMA,
    _canonical,
    _fingerprint,
    _is_reparse_point,
    _process_lock,
)

MIGRATION_SCHEMA = "market-os.b4-18.schema-migration@v1"
TARGET_BROKER_SCHEMA = "market-os.b4-18.paper-broker@v2"
TARGET_POLICY_SCHEMA = TARGET_BROKER_SCHEMA + ".policy"
TARGET_EVENT_SCHEMA = "market-os.b4-18.paper-portfolio-event@v2"
TARGET_SNAPSHOT_SCHEMA = "market-os.b4-18.portfolio-snapshot@v2"
TARGET_GENESIS_SCHEMA = "market-os.b4-18.paper-portfolio-genesis@v2"
TARGET_SHARED_GENESIS_SCHEMA = "market-os.b4-18.shared-portfolio-genesis@v2"
TRANSFORMER_VERSION = "b4.18-lossless-envelope-v1"
_FILES = ("genesis.json", "policy.json", "ledger.jsonl", "checkpoint.json")
_GENESIS_FIELDS = {
    "portfolio_id", "strategy_id", "fixture_lineage", "symbol", "quote_asset", "base_asset",
    "policy_fingerprint", "initial_cash_usdt", "initial_btc_quantity", "initial_average_entry_price",
    "synthetic_only", "schema", "shared_portfolio_id", "member_strategy_ids",
}
_POLICY_FIELDS = {
    "schema", "fee_bps_per_side", "spread_bps_per_side", "slippage_bps_per_side", "initial_cash_usdt",
    "initial_btc_quantity", "initial_average_entry_price", "max_order_notional_usdt", "price_quantum",
    "quantity_step", "minimum_notional_usdt", "max_inventory_btc", "max_loss_usdt", "max_drawdown_usdt",
    "loss_window_ms", "policy_version",
}
_SNAPSHOT_FIELDS = {
    "schema", "portfolio_id", "cash_usdt", "btc_quantity", "average_entry_price", "realized_pnl_usdt",
    "total_fees_usdt", "total_notional_usdt", "mark_price", "peak_equity", "last_event_time_ms",
    "equity_history", "revoked_approval_ids", "open_orders", "orders", "fills", "event_cursor",
}
_ORDER_FIELDS = {
    "portfolio_id", "order_id", "command_id", "idempotency_key", "side", "order_type", "quantity",
    "limit_price", "submitted_at_ms", "state", "command_fingerprint", "strategy_id",
}
_FILL_FIELDS = {"fill_id", "order_id", "event_id", "quantity", "price", "fee", "spread_cost", "strategy_id"}
_LEDGER_FIELDS = {
    "schema", "sequence", "portfolio_id", "kind", "payload", "result", "idempotency_key",
    "previous_event_fingerprint", "resulting_snapshot_fingerprint", "resulting_snapshot", "event_fingerprint",
}


class MigrationRejected(ValueError):
    """A portfolio cannot be migrated safely."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value: Mapping[str, Any]) -> bytes:
    return (_canonical(value) + "\n").encode("utf-8")


def _allowlisted(value: Mapping[str, Any], fields: set[str], label: str) -> None:
    unknown = set(value) - fields
    if unknown:
        raise MigrationRejected(f"{label} contains unsupported fields")


def _required(value: Mapping[str, Any], fields: set[str], label: str) -> None:
    missing = fields - set(value)
    if missing:
        raise MigrationRejected(f"{label} is missing required fields")


def _validate_target_snapshot(snapshot: Mapping[str, Any], label: str) -> None:
    _allowlisted(snapshot, _SNAPSHOT_FIELDS | {"source_schema"}, label)
    _required(snapshot, _SNAPSHOT_FIELDS | {"source_schema"}, label)
    for order in snapshot["orders"]:
        if not isinstance(order, Mapping):
            raise MigrationRejected(f"{label} contains an invalid order")
        _allowlisted(order, _ORDER_FIELDS, f"{label} order")
        _required(order, {"portfolio_id", "order_id", "command_id", "idempotency_key", "side", "order_type", "quantity", "submitted_at_ms", "state", "command_fingerprint"}, f"{label} order")
    for fill in snapshot["fills"]:
        if not isinstance(fill, Mapping):
            raise MigrationRejected(f"{label} contains an invalid fill")
        _allowlisted(fill, _FILL_FIELDS, f"{label} fill")
        _required(fill, {"fill_id", "order_id", "event_id", "quantity", "price", "fee"}, f"{label} fill")


def _validate_source_shapes(genesis: Mapping[str, Any], policy: Mapping[str, Any]) -> None:
    _allowlisted(genesis, _GENESIS_FIELDS, "source genesis")
    _allowlisted(policy, _POLICY_FIELDS, "source policy")
    _required(genesis, {"portfolio_id", "strategy_id", "fixture_lineage", "policy_fingerprint", "schema", "synthetic_only"}, "source genesis")
    _required(policy, _POLICY_FIELDS, "source policy")


def _files_fingerprint(files: Mapping[str, bytes], *, portfolio_id: str | None = None) -> tuple[dict[str, str], str]:
    fingerprints = {name: _sha256(data) for name, data in sorted(files.items())}
    identity = {"backup_schema": BACKUP_SCHEMA, "portfolio_id": portfolio_id, "files": fingerprints}
    return fingerprints, _fingerprint(identity)


def _safe_destination(root: Path, portfolio_id: str, destination: str | Path | None) -> Path:
    candidate = root / ".migrations" / f"{portfolio_id}-b4-18-v2" if destination is None else Path(destination)
    if not candidate.is_absolute():
        candidate = root / candidate
    lexical = Path(os.path.abspath(candidate))
    if lexical == root or root not in lexical.parents or lexical == root / portfolio_id:
        raise MigrationRejected("migration destination must remain inside the store root")
    current = lexical
    while current != root:
        if current.exists() and _is_reparse_point(current):
            raise MigrationRejected("migration destination cannot use a symlink or reparse point")
        current = current.parent
    candidate = candidate.resolve()
    if candidate == root or root not in candidate.parents or candidate == root / portfolio_id:
        raise MigrationRejected("migration destination must remain inside the store root")
    return candidate


def _reject_reparse_ancestors(path: Path) -> None:
    current = Path(os.path.abspath(path))
    while True:
        if current.exists() and _is_reparse_point(current):
            raise MigrationRejected("migration path cannot use a symlink or reparse point")
        if current.parent == current:
            return
        current = current.parent


def _read_archive(archive: Path) -> dict[str, bytes]:
    try:
        with ZipFile(archive) as bundle:
            names = bundle.namelist()
            if len(names) != len(set(names)) or "manifest.json" not in names:
                raise MigrationRejected("backup archive members are invalid")
            manifest = json.loads(bundle.read("manifest.json"))
            if not isinstance(manifest, Mapping) or manifest.get("schema") != BACKUP_SCHEMA:
                raise MigrationRejected("backup schema is unsupported")
            files: dict[str, bytes] = {}
            for entry in manifest.get("files", []):
                if not isinstance(entry, Mapping) or entry.get("path") not in _FILES:
                    raise MigrationRejected("backup file manifest is invalid")
                name = str(entry["path"])
                if name in files or not isinstance(entry.get("size"), int) or isinstance(entry.get("size"), bool) or not isinstance(entry.get("sha256"), str):
                    raise MigrationRejected("backup file manifest is invalid")
                data = bundle.read(name)
                if len(data) != entry.get("size") or _sha256(data) != entry.get("sha256"):
                    raise MigrationRejected(f"backup file fingerprint mismatch: {name}")
                files[name] = data
            if not {"genesis.json", "policy.json"}.issubset(files) or set(names) != set(files) | {"manifest.json"}:
                raise MigrationRejected("backup file set is incomplete")
            return files
    except MigrationRejected:
        raise
    except Exception as exc:
        raise MigrationRejected("backup archive is malformed") from exc


def _transform_files(source_files: Mapping[str, bytes]) -> tuple[dict[str, bytes], int]:
    genesis = dict(json.loads(source_files["genesis.json"]))
    policy = dict(json.loads(source_files["policy.json"]))
    _validate_source_shapes(genesis, policy)
    source_genesis_schema = genesis.get("schema")
    if source_genesis_schema not in {GENESIS_SCHEMA, SHARED_GENESIS_SCHEMA}:
        raise MigrationRejected("source genesis schema is unsupported")
    if policy.get("schema") != SCHEMA + ".policy":
        raise MigrationRejected("source policy schema is unsupported")
    source_policy_fingerprint = genesis.get("policy_fingerprint")
    if not isinstance(source_policy_fingerprint, str):
        raise MigrationRejected("source policy fingerprint is missing")
    target_policy = {**policy, "schema": TARGET_POLICY_SCHEMA, "source_schema": policy["schema"]}
    target_policy_fingerprint = _fingerprint(target_policy)
    genesis["source_schema"] = source_genesis_schema
    genesis["source_policy_fingerprint"] = source_policy_fingerprint
    genesis["policy_fingerprint"] = target_policy_fingerprint
    genesis["schema"] = TARGET_SHARED_GENESIS_SCHEMA if source_genesis_schema == SHARED_GENESIS_SCHEMA else TARGET_GENESIS_SCHEMA
    policy.clear()
    policy.update(target_policy)
    target: dict[str, bytes] = {"genesis.json": _json_bytes(genesis), "policy.json": _json_bytes(policy)}
    ledger_count = 0
    if "ledger.jsonl" in source_files:
        rows: list[str] = []
        previous_target = "0" * 64
        for raw in source_files["ledger.jsonl"].decode("utf-8").splitlines():
            if not raw.strip():
                continue
            source = dict(json.loads(raw))
            _allowlisted(source, _LEDGER_FIELDS, "source ledger record")
            if source.get("schema") != EVENT_SCHEMA:
                raise MigrationRejected("source ledger schema is unsupported")
            source_event = source.pop("event_fingerprint", None)
            source_previous = source.get("previous_event_fingerprint")
            source_snapshot_fp = source.get("resulting_snapshot_fingerprint")
            snapshot = dict(source.get("resulting_snapshot", {}))
            _allowlisted(snapshot, _SNAPSHOT_FIELDS, "source snapshot")
            for order in snapshot.get("orders", []):
                if isinstance(order, Mapping):
                    _allowlisted(order, _ORDER_FIELDS, "source order")
            for fill in snapshot.get("fills", []):
                if isinstance(fill, Mapping):
                    _allowlisted(fill, _FILL_FIELDS, "source fill")
            if snapshot.get("schema") != SNAPSHOT_SCHEMA:
                raise MigrationRejected("source ledger snapshot schema is unsupported")
            snapshot["source_schema"] = snapshot["schema"]
            snapshot["schema"] = TARGET_SNAPSHOT_SCHEMA
            source["source_schema"] = source.pop("schema")
            source["schema"] = TARGET_EVENT_SCHEMA
            source["source_event_fingerprint"] = source_event
            source["source_previous_event_fingerprint"] = source_previous
            source["source_resulting_snapshot_fingerprint"] = source_snapshot_fp
            source["previous_event_fingerprint"] = previous_target
            source["resulting_snapshot"] = snapshot
            source["resulting_snapshot_fingerprint"] = _fingerprint(snapshot)
            source["event_fingerprint"] = _fingerprint({key: value for key, value in source.items() if key != "event_fingerprint"})
            previous_target = source["event_fingerprint"]
            rows.append(_canonical(source))
            ledger_count += 1
        target["ledger.jsonl"] = ("\n".join(rows) + "\n").encode("utf-8") if rows else b""
    if "checkpoint.json" in source_files:
        checkpoint = dict(json.loads(source_files["checkpoint.json"]))
        if checkpoint.get("schema") != SNAPSHOT_SCHEMA + ".checkpoint":
            raise MigrationRejected("source checkpoint schema is unsupported")
        snapshot = dict(checkpoint.get("snapshot", {}))
        _allowlisted(snapshot, _SNAPSHOT_FIELDS, "source checkpoint snapshot")
        if snapshot.get("schema") != SNAPSHOT_SCHEMA:
            raise MigrationRejected("source checkpoint snapshot schema is unsupported")
        checkpoint["source_snapshot_fingerprint"] = checkpoint.get("snapshot_fingerprint")
        snapshot["source_schema"] = snapshot["schema"]
        snapshot["schema"] = TARGET_SNAPSHOT_SCHEMA
        checkpoint["schema"] = TARGET_SNAPSHOT_SCHEMA + ".checkpoint"
        checkpoint["snapshot"] = snapshot
        checkpoint["snapshot_fingerprint"] = _fingerprint(snapshot)
        target["checkpoint.json"] = _json_bytes(checkpoint)
    return target, ledger_count


def _source_projection(target_files: Mapping[str, bytes]) -> dict[str, bytes]:
    genesis = dict(json.loads(target_files["genesis.json"]))
    source_schema = genesis.pop("source_schema", None)
    if source_schema not in {GENESIS_SCHEMA, SHARED_GENESIS_SCHEMA}:
        raise MigrationRejected("target genesis provenance is invalid")
    genesis["schema"] = source_schema
    genesis["policy_fingerprint"] = genesis.pop("source_policy_fingerprint", None)
    if not isinstance(genesis["policy_fingerprint"], str):
        raise MigrationRejected("target policy provenance is invalid")
    policy = dict(json.loads(target_files["policy.json"]))
    policy_schema = policy.pop("source_schema", None)
    if policy_schema != SCHEMA + ".policy":
        raise MigrationRejected("target policy provenance is invalid")
    policy["schema"] = policy_schema
    result: dict[str, bytes] = {"genesis.json": _json_bytes(genesis), "policy.json": _json_bytes(policy)}
    if "ledger.jsonl" in target_files:
        rows: list[str] = []
        for raw in target_files["ledger.jsonl"].decode("utf-8").splitlines():
            if not raw.strip():
                continue
            record = dict(json.loads(raw))
            record["schema"] = record.pop("source_schema", None)
            record["event_fingerprint"] = record.pop("source_event_fingerprint", None)
            record["previous_event_fingerprint"] = record.pop("source_previous_event_fingerprint", None)
            record["resulting_snapshot_fingerprint"] = record.pop("source_resulting_snapshot_fingerprint", None)
            snapshot = dict(record["resulting_snapshot"])
            snapshot["schema"] = snapshot.pop("source_schema", None)
            record["resulting_snapshot"] = snapshot
            rows.append(_canonical(record))
        result["ledger.jsonl"] = ("\n".join(rows) + "\n").encode("utf-8") if rows else b""
    if "checkpoint.json" in target_files:
        checkpoint = dict(json.loads(target_files["checkpoint.json"]))
        checkpoint["schema"] = SNAPSHOT_SCHEMA + ".checkpoint"
        checkpoint["snapshot_fingerprint"] = checkpoint.pop("source_snapshot_fingerprint")
        snapshot = dict(checkpoint["snapshot"])
        snapshot["schema"] = snapshot.pop("source_schema", None)
        checkpoint["snapshot"] = snapshot
        result["checkpoint.json"] = _json_bytes(checkpoint)
    return result


def _validate_target_envelope(target_files: Mapping[str, bytes]) -> None:
    if not {"genesis.json", "policy.json"}.issubset(target_files) or not set(target_files).issubset(set(_FILES)):
        raise MigrationRejected("target file set is invalid")
    if "checkpoint.json" in target_files and "ledger.jsonl" not in target_files:
        raise MigrationRejected("target checkpoint exists without portfolio ledger")
    target_genesis = json.loads(target_files["genesis.json"])
    target_policy = json.loads(target_files["policy.json"])
    _allowlisted(target_genesis, _GENESIS_FIELDS | {"source_schema", "source_policy_fingerprint"}, "target genesis")
    _allowlisted(target_policy, _POLICY_FIELDS | {"source_schema"}, "target policy")
    _required(target_genesis, {"portfolio_id", "strategy_id", "fixture_lineage", "policy_fingerprint", "schema", "synthetic_only", "source_schema", "source_policy_fingerprint"}, "target genesis")
    _required(target_policy, _POLICY_FIELDS | {"source_schema"}, "target policy")
    expected_genesis = TARGET_SHARED_GENESIS_SCHEMA if target_genesis.get("source_schema") == SHARED_GENESIS_SCHEMA else TARGET_GENESIS_SCHEMA
    if target_genesis.get("schema") != expected_genesis or target_policy.get("schema") != TARGET_POLICY_SCHEMA:
        raise MigrationRejected("target metadata schema is invalid")
    if target_genesis.get("source_schema") not in {GENESIS_SCHEMA, SHARED_GENESIS_SCHEMA} or not isinstance(target_genesis.get("source_policy_fingerprint"), str):
        raise MigrationRejected("target genesis provenance is incomplete")
    if target_policy.get("source_schema") != SCHEMA + ".policy":
        raise MigrationRejected("target policy provenance is incomplete")
    if target_genesis.get("policy_fingerprint") != _fingerprint(target_policy):
        raise MigrationRejected("target policy fingerprint is invalid")
    if "ledger.jsonl" in target_files:
        previous = "0" * 64
        for expected_sequence, raw in enumerate((line for line in target_files["ledger.jsonl"].decode("utf-8").splitlines() if line.strip()), 1):
            if not raw.strip():
                continue
            record = json.loads(raw)
            _allowlisted(record, _LEDGER_FIELDS | {"source_schema", "source_event_fingerprint", "source_previous_event_fingerprint", "source_resulting_snapshot_fingerprint"}, "target ledger record")
            _required(record, _LEDGER_FIELDS | {"source_schema", "source_event_fingerprint", "source_previous_event_fingerprint", "source_resulting_snapshot_fingerprint"}, "target ledger record")
            if record.get("schema") != TARGET_EVENT_SCHEMA or record.get("sequence") != expected_sequence or not isinstance(record.get("portfolio_id"), str):
                raise MigrationRejected("target ledger sequence or schema is invalid")
            if record.get("source_schema") != EVENT_SCHEMA or not all(isinstance(record.get(field), str) and len(record[field]) == 64 for field in ("source_event_fingerprint", "source_previous_event_fingerprint", "source_resulting_snapshot_fingerprint")):
                raise MigrationRejected("target ledger provenance is incomplete")
            if record.get("previous_event_fingerprint") != previous:
                raise MigrationRejected("target ledger ordering is invalid")
            snapshot = record.get("resulting_snapshot")
            if not isinstance(snapshot, Mapping) or snapshot.get("schema") != TARGET_SNAPSHOT_SCHEMA:
                raise MigrationRejected("target snapshot schema is invalid")
            _validate_target_snapshot(snapshot, "target snapshot")
            if snapshot.get("source_schema") != SNAPSHOT_SCHEMA:
                raise MigrationRejected("target snapshot provenance is incomplete")
            _allowlisted(snapshot, _SNAPSHOT_FIELDS | {"source_schema"}, "target snapshot")
            if record.get("resulting_snapshot_fingerprint") != _fingerprint(snapshot):
                raise MigrationRejected("target snapshot fingerprint is invalid")
            if record.get("event_fingerprint") != _fingerprint({key: value for key, value in record.items() if key != "event_fingerprint"}):
                raise MigrationRejected("target event fingerprint is invalid")
            previous = record["event_fingerprint"]
    if "checkpoint.json" in target_files:
        checkpoint = json.loads(target_files["checkpoint.json"])
        if checkpoint.get("schema") != TARGET_SNAPSHOT_SCHEMA + ".checkpoint":
            raise MigrationRejected("target checkpoint schema is invalid")
        snapshot = checkpoint.get("snapshot")
        if not isinstance(snapshot, Mapping) or snapshot.get("schema") != TARGET_SNAPSHOT_SCHEMA:
            raise MigrationRejected("target checkpoint snapshot schema is invalid")
        if snapshot.get("source_schema") != SNAPSHOT_SCHEMA or not isinstance(checkpoint.get("source_snapshot_fingerprint"), str):
            raise MigrationRejected("target checkpoint provenance is incomplete")
        _allowlisted(checkpoint, {"schema", "sequence", "snapshot_fingerprint", "snapshot", "source_snapshot_fingerprint"}, "target checkpoint")
        _required(checkpoint, {"schema", "sequence", "snapshot_fingerprint", "snapshot", "source_snapshot_fingerprint"}, "target checkpoint")
        _validate_target_snapshot(snapshot, "target checkpoint snapshot")
        if checkpoint.get("snapshot_fingerprint") != _fingerprint(snapshot):
            raise MigrationRejected("target checkpoint fingerprint is invalid")
        if not isinstance(checkpoint.get("sequence"), int) or isinstance(checkpoint.get("sequence"), bool) or checkpoint["sequence"] < 1:
            raise MigrationRejected("target checkpoint sequence is invalid")


def _target_policy(target: Mapping[str, Any]) -> B41Policy:
    policy = {key: target[key] for key in _POLICY_FIELDS}
    policy["schema"] = SCHEMA + ".policy"
    try:
        return B41Policy.from_dict(policy)
    except (BrokerRejected, KeyError, TypeError, ValueError) as exc:
        raise MigrationRejected("target policy values are invalid") from exc


def _target_genesis(target: Mapping[str, Any], policy: B41Policy, expected_portfolio_id: str) -> B41Genesis:
    source_schema = target.get("source_schema")
    if source_schema not in {GENESIS_SCHEMA, SHARED_GENESIS_SCHEMA}:
        raise MigrationRejected("target genesis provenance is invalid")
    values = {key: target[key] for key in _GENESIS_FIELDS if key in target}
    values["schema"] = source_schema
    values["policy_fingerprint"] = target.get("policy_fingerprint")
    if source_schema == SHARED_GENESIS_SCHEMA:
        values["strategy_id"] = "shared"
        values["member_strategy_ids"] = tuple(values.get("member_strategy_ids", ()))
    values.pop("source_schema", None)
    values.pop("source_policy_fingerprint", None)
    try:
        genesis = B41Genesis(**values)
    except (BrokerRejected, KeyError, TypeError, ValueError) as exc:
        raise MigrationRejected("target genesis values are invalid") from exc
    if genesis.portfolio_id != expected_portfolio_id:
        raise MigrationRejected("target portfolio identity mismatch")
    return genesis


def _recover_target(target_files: Mapping[str, bytes], expected_portfolio_id: str) -> dict[str, Any]:
    """Recover v2 records directly, independent of the v1 projection replay."""
    _validate_target_envelope(target_files)
    try:
        genesis_payload = json.loads(target_files["genesis.json"])
        policy_payload = json.loads(target_files["policy.json"])
    except (KeyError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
        raise MigrationRejected("target metadata is malformed") from exc
    _required(genesis_payload, {"portfolio_id", "source_schema", "source_policy_fingerprint", "schema", "policy_fingerprint"}, "target genesis")
    _required(policy_payload, _POLICY_FIELDS | {"source_schema"}, "target policy")
    if genesis_payload.get("policy_fingerprint") != _fingerprint(policy_payload):
        raise MigrationRejected("target policy fingerprint is invalid")
    policy = _target_policy(policy_payload)
    genesis = _target_genesis(genesis_payload, policy, expected_portfolio_id)
    source_policy = dict(policy_payload)
    source_policy["schema"] = source_policy.pop("source_schema")
    if genesis_payload.get("source_policy_fingerprint") != _fingerprint(source_policy):
        raise MigrationRejected("target source policy provenance is invalid")
    previous = "0" * 64
    snapshots: dict[int, Mapping[str, Any]] = {}
    records: list[Mapping[str, Any]] = []
    ledger = target_files.get("ledger.jsonl", b"")
    try:
        lines = ledger.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise MigrationRejected("target ledger is malformed") from exc
    sequence = 0
    for raw in lines:
        if not raw.strip():
            continue
        sequence += 1
        try:
            record = json.loads(raw)
        except (TypeError, UnicodeError, json.JSONDecodeError) as exc:
            raise MigrationRejected("target ledger is malformed") from exc
        if not isinstance(record, Mapping):
            raise MigrationRejected("target ledger is malformed")
        _required(record, _LEDGER_FIELDS | {"source_schema", "source_event_fingerprint", "source_previous_event_fingerprint", "source_resulting_snapshot_fingerprint"}, "target ledger record")
        if record.get("sequence") != sequence or record.get("portfolio_id") != expected_portfolio_id or record.get("previous_event_fingerprint") != previous:
            raise MigrationRejected("target ledger ordering or identity is invalid")
        snapshot = record.get("resulting_snapshot")
        if not isinstance(snapshot, Mapping) or snapshot.get("schema") != TARGET_SNAPSHOT_SCHEMA or snapshot.get("portfolio_id") != expected_portfolio_id:
            raise MigrationRejected("target snapshot identity is invalid")
        _validate_target_snapshot(snapshot, "target snapshot")
        orders = snapshot["orders"]
        order_ids = {order["order_id"] for order in orders}
        if any(order["portfolio_id"] != expected_portfolio_id for order in orders):
            raise MigrationRejected("target order portfolio identity is invalid")
        if any(fill["order_id"] not in order_ids for fill in snapshot["fills"]):
            raise MigrationRejected("target fill order identity is invalid")
        if record.get("resulting_snapshot_fingerprint") != _fingerprint(snapshot) or record.get("event_fingerprint") != _fingerprint({key: value for key, value in record.items() if key != "event_fingerprint"}):
            raise MigrationRejected("target ledger fingerprint is invalid")
        try:
            # Reuse the domain's strict scalar/order/fill/membership checks without replaying source bytes.
            probe = object.__new__(B41Broker)
            probe.genesis = genesis
            probe.policy = policy
            probe._restore_snapshot(snapshot | {"schema": SNAPSHOT_SCHEMA})
            probe._validate_shared_state()
        except (BrokerRejected, KeyError, TypeError, ValueError, ArithmeticError) as exc:
            raise MigrationRejected("target snapshot state is invalid") from exc
        snapshots[sequence] = snapshot
        records.append(record)
        previous = str(record["event_fingerprint"])
    if "checkpoint.json" in target_files:
        try:
            checkpoint = json.loads(target_files["checkpoint.json"])
        except (TypeError, UnicodeError, json.JSONDecodeError) as exc:
            raise MigrationRejected("target checkpoint is malformed") from exc
        _required(checkpoint, {"schema", "sequence", "snapshot_fingerprint", "snapshot", "source_snapshot_fingerprint"}, "target checkpoint")
        if not isinstance(checkpoint["sequence"], int) or isinstance(checkpoint["sequence"], bool) or not isinstance(checkpoint["snapshot"], Mapping) or checkpoint["snapshot"].get("schema") != TARGET_SNAPSHOT_SCHEMA or checkpoint["snapshot"].get("portfolio_id") != expected_portfolio_id or checkpoint["sequence"] not in snapshots or _canonical(checkpoint["snapshot"]) != _canonical(snapshots[checkpoint["sequence"]]):
            raise MigrationRejected("target checkpoint does not match ledger")
    final = snapshots[max(snapshots)] if snapshots else None
    semantic_fingerprint = None
    if final is not None:
        semantic = dict(final)
        semantic["schema"] = SNAPSHOT_SCHEMA
        semantic.pop("source_schema", None)
        semantic_fingerprint = _fingerprint(semantic)
    return {"status": "recovered", "portfolio_id": expected_portfolio_id, "event_count": len(records), "ledger_head": previous, "snapshot_fingerprint": semantic_fingerprint, "native_snapshot_fingerprint": _fingerprint(final) if final is not None else None}
def _validate_target(target_files: Mapping[str, bytes], source_root: Path, portfolio_id: str) -> dict[str, Any]:
    target_recovery = _recover_target(target_files, portfolio_id)
    projection = _source_projection(target_files)
    source = B41Broker.open(source_root, portfolio_id, read_only=True)
    with tempfile.TemporaryDirectory(prefix=".b4-18-validate-", dir=source_root) as temp_name:
        temp = Path(temp_name)
        portfolio = temp / portfolio_id
        portfolio.mkdir()
        for name, data in projection.items():
            (portfolio / name).write_bytes(data)
        (portfolio / ".writer.lock").touch()
        projected = B41Broker.open(temp, portfolio_id, read_only=True)
        if projected.snapshot() != source.snapshot() or projected.snapshot_fingerprint != source.snapshot_fingerprint:
            raise MigrationRejected("target replay equivalence failed")
        if target_recovery["snapshot_fingerprint"] is not None and target_recovery["snapshot_fingerprint"] != _fingerprint(projected.snapshot()):
            raise MigrationRejected("target-native and source-projection snapshots differ")
        return {"status": "passed", "target_native": target_recovery, "snapshot_fingerprint": projected.snapshot_fingerprint, "semantic_projection_fingerprint": _fingerprint(projected.snapshot())}


def validate_migrated_store(path: str | Path, *, promotion_path: str | Path | None = None) -> dict[str, Any]:
    """Validate a promoted target envelope without mutating it."""
    raw_root = Path(path)
    _reject_reparse_ancestors(raw_root)
    if _is_reparse_point(raw_root):
        raise MigrationRejected("migrated store must be a local directory")
    root = raw_root.resolve()
    if not root.is_dir():
        raise MigrationRejected("migrated store must be a local directory")
    expected_root = Path(promotion_path).resolve() if promotion_path is not None else root
    manifest_path = root / "migration.json"
    if not manifest_path.is_file() or _is_reparse_point(manifest_path):
        raise MigrationRejected("migration manifest is missing")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MigrationRejected("migration manifest is malformed") from exc
    if not isinstance(manifest, Mapping) or manifest.get("schema") != MIGRATION_SCHEMA or manifest.get("status") != "promoted":
        raise MigrationRejected("migration manifest is unsupported")
    _allowlisted(manifest, {"schema", "milestone", "status", "transformer_version", "migration_identity", "source", "target", "counts", "semantic_equivalence", "rollback"}, "migration manifest")
    _required(manifest, {"schema", "milestone", "status", "transformer_version", "migration_identity", "source", "target", "counts", "semantic_equivalence", "rollback"}, "migration manifest")
    target = manifest.get("target")
    source = manifest.get("source")
    rollback = manifest.get("rollback")
    if not isinstance(target, Mapping) or target.get("path") != str(expected_root) or not isinstance(source, Mapping) or not isinstance(rollback, Mapping):
        raise MigrationRejected("migration target identity is invalid")
    _required(rollback, {"path", "sha256", "verified"}, "migration rollback")
    _allowlisted(rollback, {"path", "sha256", "verified"}, "migration rollback")
    _required(target, {"broker_schema", "portfolio_id", "path", "fingerprint", "file_fingerprints"}, "migration target")
    _required(source, {"portfolio_id", "schema", "fingerprint", "file_fingerprints"}, "migration source")
    _allowlisted(target, {"broker_schema", "portfolio_id", "path", "fingerprint", "file_fingerprints"}, "migration target")
    _allowlisted(source, {"portfolio_id", "schema", "fingerprint", "file_fingerprints"}, "migration source")
    if target.get("broker_schema") != TARGET_BROKER_SCHEMA or source.get("schema") != SCHEMA or source.get("portfolio_id") != target.get("portfolio_id"):
        raise MigrationRejected("migration source or target schema identity is invalid")
    expected = target.get("file_fingerprints")
    if not isinstance(expected, Mapping):
        raise MigrationRejected("migration target fingerprints are missing")
    files: dict[str, bytes] = {}
    if not {"genesis.json", "policy.json"}.issubset(expected) or not set(expected).issubset(set(_FILES)):
        raise MigrationRejected("migration target file set is invalid")
    actual_names = {item.name for item in root.iterdir()}
    if actual_names != set(expected) | {"migration.json"}:
        raise MigrationRejected("migration target directory contents are invalid")
    for name in expected:
        if name not in _FILES:
            raise MigrationRejected("migration target file set is invalid")
        file_path = root / name
        if not file_path.is_file() or _is_reparse_point(file_path):
            raise MigrationRejected(f"migrated file is missing: {name}")
        data = file_path.read_bytes()
        if expected.get(name) != _sha256(data):
            raise MigrationRejected(f"migrated file fingerprint mismatch: {name}")
        files[name] = data
    if target.get("fingerprint") != _files_fingerprint(files)[1]:
        raise MigrationRejected("migration target fingerprint mismatch")
    rollback_path = Path(str(rollback.get("path", "")))
    expected_rollback = expected_root.with_name(expected_root.name + ".rollback.zip")
    if rollback_path.resolve() != expected_rollback.resolve():
        raise MigrationRejected("migration rollback path is invalid")
    _reject_reparse_ancestors(rollback_path)
    if _is_reparse_point(rollback_path) or not rollback_path.is_file():
        raise MigrationRejected("migration rollback archive is missing")
    rollback_files = _read_archive(rollback_path)
    source_fingerprints, source_fingerprint = _files_fingerprint(rollback_files, portfolio_id=str(source.get("portfolio_id")))
    if source.get("file_fingerprints") != source_fingerprints or source.get("fingerprint") != source_fingerprint:
        raise MigrationRejected("migration source fingerprint mismatch")
    if rollback.get("sha256") != _sha256(rollback_path.read_bytes()):
        raise MigrationRejected("migration rollback fingerprint mismatch")
    if rollback.get("verified") is not True:
        raise MigrationRejected("migration rollback is not verified")
    expected_identity = _fingerprint({"source_fingerprint": source_fingerprint, "target_schema": TARGET_BROKER_SCHEMA, "transformer_version": manifest.get("transformer_version")})
    if manifest.get("migration_identity") != expected_identity:
        raise MigrationRejected("migration identity mismatch")
    if manifest.get("transformer_version") != TRANSFORMER_VERSION or manifest.get("milestone") != "B4.18":
        raise MigrationRejected("migration transformer identity is unsupported")
    try:
        target_recovery = _recover_target(files, str(source.get("portfolio_id")))
    except (KeyError, TypeError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
        raise MigrationRejected("migrated target is malformed") from exc
    projection = _source_projection(files)
    with tempfile.TemporaryDirectory(prefix=".b4-18-recover-") as temp_name:
        temp = Path(temp_name)
        target_root = temp / "target"
        source_root = temp / "source"
        target_root.mkdir()
        source_root.mkdir()
        target_portfolio = target_root / str(source.get("portfolio_id"))
        target_portfolio.mkdir()
        for name, data in projection.items():
            (target_portfolio / name).write_bytes(data)
        (target_portfolio / ".writer.lock").touch()
        recovered = B41Broker.open(target_root, str(source.get("portfolio_id")), read_only=True)
        if recovered.snapshot_fingerprint != manifest.get("semantic_equivalence", {}).get("snapshot_fingerprint"):
            raise MigrationRejected("migration replay equivalence fingerprint mismatch")
        if target_recovery.get("snapshot_fingerprint") is not None and target_recovery.get("snapshot_fingerprint") != recovered.snapshot_fingerprint:
            raise MigrationRejected("migration target-native recovery fingerprint mismatch")
        source_portfolio = source_root / str(source.get("portfolio_id"))
        source_portfolio.mkdir()
        for name, data in rollback_files.items():
            (source_portfolio / name).write_bytes(data)
        (source_portfolio / ".writer.lock").touch()
        source_recovered = B41Broker.open(source_root, str(source.get("portfolio_id")), read_only=True)
        if source_recovered.genesis.policy_fingerprint != json.loads(files["genesis.json"]).get("source_policy_fingerprint"):
            raise MigrationRejected("migration source policy provenance mismatch")
        if source_recovered.snapshot().get("event_cursor") and target_recovery.get("snapshot_fingerprint") != source_recovered.snapshot_fingerprint:
            raise MigrationRejected("migration source snapshot provenance mismatch")
        if source_recovered.snapshot() != recovered.snapshot() or source_recovered.snapshot_fingerprint != recovered.snapshot_fingerprint:
            raise MigrationRejected("migration source and target semantic state differ")
        for resource in ("summary", "snapshot", "orders", "fills", "risk", "approvals", "reservations", "fingerprints", "replay", "genesis"):
            if recovered.inspect_jsonable(resource) != source_recovered.inspect_jsonable(resource):
                raise MigrationRejected("migration inspection equivalence failed")
    counts = manifest.get("counts")
    if not isinstance(counts, Mapping) or counts != {"files": len(files), "ledger_records": target_recovery.get("event_count")} :
        raise MigrationRejected("migration counts are invalid")
    semantic = manifest.get("semantic_equivalence")
    if not isinstance(semantic, Mapping):
        raise MigrationRejected("migration semantic evidence is invalid")
    _required(semantic, {"status", "target_native", "snapshot_fingerprint", "semantic_projection_fingerprint"}, "migration semantic evidence")
    _allowlisted(semantic, {"status", "target_native", "snapshot_fingerprint", "semantic_projection_fingerprint"}, "migration semantic evidence")
    if semantic.get("status") != "passed" or semantic.get("target_native") != target_recovery:
        raise MigrationRejected("migration target-native evidence is invalid")
    if semantic.get("snapshot_fingerprint") != recovered.snapshot_fingerprint or semantic.get("semantic_projection_fingerprint") != _fingerprint(recovered.snapshot()):
        raise MigrationRejected("migration semantic fingerprints are invalid")
    return dict(manifest)


def _migrate_portfolio_locked(store_root: str | Path, portfolio_id: str, destination: str | Path | None = None) -> dict[str, Any]:
    """Back up, transform, validate, and promote one portfolio copy-on-write."""
    root = Path(store_root).resolve()
    destination_path = _safe_destination(root, portfolio_id, destination)
    migration_root = root / ".migrations"
    migration_root.mkdir(parents=True, exist_ok=True)
    source_fd, source_name = tempfile.mkstemp(prefix=".b4-18-source-", suffix=".zip", dir=migration_root)
    os.close(source_fd)
    source_archive = Path(source_name)
    source_archive.unlink(missing_ok=True)
    try:
        backup_portfolio(root, portfolio_id, source_archive)
        source_files = _read_archive(source_archive)
        source_fingerprints, source_fingerprint = _files_fingerprint(source_files, portfolio_id=portfolio_id)
        identity = _fingerprint({"source_fingerprint": source_fingerprint, "target_schema": TARGET_BROKER_SCHEMA, "transformer_version": TRANSFORMER_VERSION})
        if destination_path.exists():
            try:
                manifest = validate_migrated_store(destination_path)
            except MigrationRejected as exc:
                raise MigrationRejected("migration destination exists but is invalid") from exc
            if manifest.get("migration_identity") != identity:
                raise MigrationRejected("migration identity conflict")
            return manifest
        for candidate in migration_root.iterdir():
            manifest_path = candidate / "migration.json"
            if candidate.is_dir() and manifest_path.is_file():
                existing = json.loads(manifest_path.read_text(encoding="utf-8"))
                if existing.get("migration_identity") == identity:
                    raise MigrationRejected("migration identity conflict")
        target_files, ledger_count = _transform_files(source_files)
        # Recheck the source manifest immediately before promotion so a concurrent
        # writer cannot publish a target derived from stale bytes.
        current_archive_fd, current_archive_name = tempfile.mkstemp(prefix=".b4-18-current-", suffix=".zip", dir=migration_root)
        os.close(current_archive_fd)
        current_archive = Path(current_archive_name)
        current_archive.unlink(missing_ok=True)
        try:
            backup_portfolio(root, portfolio_id, current_archive)
            current_files = _read_archive(current_archive)
            _, current_fingerprint = _files_fingerprint(current_files, portfolio_id=portfolio_id)
            if current_fingerprint != source_fingerprint:
                raise MigrationRejected("source changed during migration")
        finally:
            current_archive.unlink(missing_ok=True)
        target_fingerprints, target_fingerprint = _files_fingerprint(target_files)
        replay = _validate_target(target_files, root, portfolio_id)
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        rollback_path = destination_path.with_name(destination_path.name + ".rollback.zip")
        if rollback_path.is_symlink():
            raise MigrationRejected("rollback archive already exists")
        if rollback_path.exists():
            if _sha256(rollback_path.read_bytes()) != _sha256(source_archive.read_bytes()):
                raise MigrationRejected("rollback archive conflicts with source")
        else:
            shutil.copyfile(source_archive, rollback_path)
        rollback_digest = _sha256(rollback_path.read_bytes())
        temp = Path(tempfile.mkdtemp(prefix=f".{destination_path.name}.", dir=destination_path.parent))
        try:
            for name, data in target_files.items():
                (temp / name).write_bytes(data)
            manifest = {
                "schema": MIGRATION_SCHEMA,
                "milestone": "B4.18",
                "status": "promoted",
                "transformer_version": TRANSFORMER_VERSION,
                "migration_identity": identity,
                "source": {"portfolio_id": portfolio_id, "schema": SCHEMA, "fingerprint": source_fingerprint, "file_fingerprints": source_fingerprints},
                "target": {"broker_schema": TARGET_BROKER_SCHEMA, "portfolio_id": portfolio_id, "path": str(destination_path), "fingerprint": target_fingerprint, "file_fingerprints": target_fingerprints},
                "counts": {"files": len(target_files), "ledger_records": ledger_count},
                "semantic_equivalence": replay,
                "rollback": {"path": str(rollback_path), "sha256": rollback_digest, "verified": rollback_digest == _sha256(source_archive.read_bytes())},
            }
            (temp / "migration.json").write_bytes(_json_bytes(manifest))
            source_directory = root / portfolio_id
            with _process_lock(source_directory / ".writer.lock"):
                current_files = {
                    name: (source_directory / name).read_bytes()
                    for name in _FILES
                    if (source_directory / name).is_file()
                }
                if current_files != source_files:
                    raise MigrationRejected("source changed during migration")
                if destination_path.exists():
                    raise MigrationRejected("migration destination already exists")
                # Validate the complete staging tree before the final atomic rename.
                # After rename there is no second fallible transformation step.
                validate_migrated_store(temp, promotion_path=destination_path)
                temp.rename(destination_path)
            return manifest
        except Exception:
            shutil.rmtree(temp, ignore_errors=True)
            raise
    except MigrationRejected:
        raise
    except (BrokerRejected, OSError, TypeError, ValueError, json.JSONDecodeError, UnicodeError) as exc:
        raise MigrationRejected("portfolio migration failed closed") from exc
    finally:
        source_archive.unlink(missing_ok=True)


def migrate_portfolio(store_root: str | Path, portfolio_id: str, destination: str | Path | None = None) -> dict[str, Any]:
    """Serialize local migrations so promotion and retries cannot race."""
    root = Path(store_root).resolve()
    migration_root = root / ".migrations"
    migration_root.mkdir(parents=True, exist_ok=True)
    with _process_lock(migration_root / ".writer.lock"):
        return _migrate_portfolio_locked(root, portfolio_id, destination)


__all__ = ["MIGRATION_SCHEMA", "TARGET_BROKER_SCHEMA", "TARGET_EVENT_SCHEMA", "TARGET_GENESIS_SCHEMA", "TARGET_POLICY_SCHEMA", "TARGET_SHARED_GENESIS_SCHEMA", "TARGET_SNAPSHOT_SCHEMA", "TRANSFORMER_VERSION", "MigrationRejected", "migrate_portfolio", "validate_migrated_store"]
