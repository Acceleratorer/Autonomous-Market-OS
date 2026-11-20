# ADR-0059: Portable BTC Assessor Runtime Bundles

- **Status:** Accepted
- **Date:** 2026-11-20
- **Scope:** BTC local assessor CPython runtime on Windows x64 and Linux x64

## Context

The BTC assessor runtime is locked to a target-specific CPython 3.11.18 source
build. CI verified both targets, but kept only small JSON evidence artifacts.
The runtime's Python path files also recorded the temporary project checkout's
absolute path, so an extracted runtime could not reliably follow the project to
a different local directory.

## Decision

1. Keep the Windows `_pth` file focused on the runtime and `site-packages`,
   selecting the active file beside `python311.dll` when present and otherwise
   using the executable-level file. Store the project import as
   `market-os-source.pth` in `site-packages`, with an entry relative to its
   final location. Linux uses the same `site-packages` import path.
2. Package the verified runtime beside its CI evidence: ZIP for Windows x64
   and tar.gz for Linux x64. Preserve Linux file modes and internal symlinks;
   reject symlinks in the Windows bundle and Linux links that escape the tree.
3. Record the bundle filename, format, byte length, and SHA-256 in the evidence
   JSON. Retain the combined target artifact for seven days for local retrieval.
4. Keep the existing 3.11.9 local runtime as historical evidence until a
   matching 3.11.18 bundle is downloaded, extracted, and verified against the
   runtime lock. Bundle verification proves imports and hashes only; it does
   not claim model inference or OS-level network isolation.

## Consequences

- Both runtimes use the same relative source import through `site-packages`, so
  the Windows `_pth` file stays limited to the embedded runtime layout.
- The two target runtimes can be transferred from CI into the local project
  without rebuilding CPython or retaining the original checkout path.
- The target artifact digest and the inner runtime archive digest are distinct;
  verify both when retrieving a bundle and then run the lock-backed
  `--verify-only` command after extraction.
- Runtime preparation and packaging make no Jev call, packet assessment, or
  market-data request. Jev remains connectivity-only under ADR-0058.

## References

- [BTC assessor Python runtime lock](../../market_os/models/btc_assessor_python_runtime.lock.json)
- [Runtime preparation and verification](../../market_os/btc_assessor_python_runtime.py)
- [ADR-0057: Strict recorded availability for BTC evidence](ADR-0057-btc-strict-recorded-availability.md)
- [ADR-0058: Jev connectivity-only and local BTC packet assessment](ADR-0058-btc-jev-connectivity-only-local-assessor.md)
