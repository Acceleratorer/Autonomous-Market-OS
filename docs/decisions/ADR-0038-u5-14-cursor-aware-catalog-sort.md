# ADR-0038: U5.14 Cursor-Aware Catalog Sorting

**Status:** Accepted locally  
**Date:** 2026-10-29

## Context

U5.11 bounded portfolio catalog output but sorted every eligible directory on
each page, then discarded names at or before the exclusive cursor. Directory
enumeration and validated portfolio recovery remain necessary under current
contracts.

## Decision

- Validate the supplied cursor as a direct child of the catalog root; reject
  drive-qualified paths, symlink/reparse directories, and symlink policy files.
  Broker open repeats the root-containment check before recovery. Reparse
  detection reads Windows file attributes for Python 3.11 compatibility, and
  writer-lock opens reject symlink and dangling-symlink paths.
- Treat the current local filesystem account and its permissions as the trust
  boundary; hostile concurrent replacement of store directories between
  pathname validation and subsequent opens is out of scope.
- Filter entries at or before the cursor while iterating the root, before
  sorting the remaining eligible paths.
- Sort and filter by the same case-sensitive portfolio ID string order on all
  platforms. Preserve page, skip-count, error, and recovery semantics.
- Do not add a cache or sidecar index and do not reduce full cold recovery.

## Consequences

Later pages allocate and sort fewer candidate paths; the first page is
unchanged. Directory enumeration remains O(n), and each cursor or displayed
candidate still undergoes validated cold recovery. Synthetic measurements and
limits are recorded in [U5.14](../U5.14-CURSOR-AWARE-CATALOG-SORT.md) and
`docs/evidence/u5-14-cursor-aware-catalog-sort.json`.
