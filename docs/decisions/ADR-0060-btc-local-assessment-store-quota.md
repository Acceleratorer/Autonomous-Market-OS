# ADR-0060: Bounded Local BTC Assessment Store

- **Status:** Accepted
- **Date:** 2026-11-26
- **Scope:** One local BTC assessment store root

## Context

Each persisted assessment bundle is already limited to 2 MiB, but the number of
write-once run files was unbounded. Automatic pruning would silently remove
evidence needed for audit and offline replay.

## Decision

1. Limit aggregate regular-file and symlink entry sizes under `runs/` to 1 GiB
   per store root. The coordination lock file is excluded; temporary files are
   counted so an interrupted write cannot be ignored.
2. Serialize store writers with an OS advisory lock while checking the quota
   and committing the bundle.
3. When a new run would exceed the limit, reject it with the typed
   `store_capacity_exceeded` failure. Preserve committed evidence and never
   prune automatically.
4. Keep identical run-ID retries idempotent even when the store is full; reject
   the same run ID if its bundle fingerprint differs.

## Consequences

- The 1 GiB ceiling bounds file bytes managed by one store root. It is not a
  filesystem quota and does not count directory metadata or filesystem
  allocation overhead.
- At capacity, new assessments fail closed until the owner explicitly archives
  or removes data, or selects another store root. Existing records remain
  available for verification and offline replay.
- This applies to the existing local Qwen assessor store. It does not establish
  Jev identity, change the Jev connectivity boundary, or authorize packet
  egress.

## References

- [Local assessment store](../../market_os/btc_local_assessor_store.py)
- [Store quota and replay tests](../../market_os/tests/test_btc_local_assessor.py)
- [Goal prompt](../GOAL-PROMPT.md)
