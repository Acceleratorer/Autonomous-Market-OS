"""Read-only schema migration preflight for the synthetic B4 portfolio store."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .portfolio_backup import BACKUP_SCHEMA
from .portfolio_broker import B41Broker, BrokerRejected, SCHEMA


MIGRATION_SCHEMA = "market-os.b4-12.migration-preflight@v1"


class MigrationRejected(ValueError):
    """A portfolio cannot be classified safely for migration."""


def preflight_portfolio(store_root: str | Path, portfolio_id: str) -> dict[str, Any]:
    """Classify one portfolio without changing any persisted bytes."""
    try:
        broker = B41Broker.open(store_root, portfolio_id, read_only=True)
    except (BrokerRejected, OSError, TypeError, ValueError) as exc:
        raise MigrationRejected("portfolio schema is unsupported or recovery failed") from exc
    return {
        "schema": MIGRATION_SCHEMA,
        "portfolio_id": broker.genesis.portfolio_id,
        "source_schema": SCHEMA,
        "target_schema": SCHEMA,
        "genesis_schema": broker.genesis.schema,
        "backup_schema": BACKUP_SCHEMA,
        "status": "current",
        "requires_migration": False,
        "history_immutable": True,
        "action": "none",
    }


__all__ = ["MIGRATION_SCHEMA", "MigrationRejected", "preflight_portfolio"]
