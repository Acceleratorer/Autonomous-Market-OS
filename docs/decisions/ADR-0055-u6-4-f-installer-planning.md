# ADR-0055: U6.4-F offline installer and Python runtime

**Date:** 2026-11-15
**Status:** Accepted; implementation authorized within the contract
**Scope:** Local, offline, synthetic paper-only desktop packaging

## Context

U6.4-C produces signed Windows/Linux directory artifacts. U6.4-D validates an
artifact without installing it, and U6.4-E simulates a staged copy, atomic
publication, storage reset, and post-copy verification. The artifact still uses
a Python source sidecar and a system Python 3.11+ interpreter.

The accepted implementation adds a portable offline installer and embedded
Python runtime. These changes affect machine/user state, permissions, runtime
provenance, upgrade, uninstall, and rollback, so the implementation reuses the
existing artifact checks and emits inspectable evidence.

## Decision

Implement U6.4-F within the accepted versioned installation contract in
[`docs/U6.4-F-INSTALLER-AND-PYTHON-RUNTIME-PLANNING.md`](../U6.4-F-INSTALLER-AND-PYTHON-RUNTIME-PLANNING.md):

- keep Python as the domain, accounting, persistence, recovery, and inspection
  authority;
- keep Electron as a thin adapter that coordinates process and installation
  lifecycle;
- distribute a signed portable `tar.gz` for Windows/Linux and install it per
  user without elevation or native service registration;
- bundle target-native CPython 3.11.x, with CI freezing one approved python.org
  patch per target and recording target archive and runtime-manifest SHA-256
  values in the signed runtime identity;
- preserve `python/.market_os` on upgrade and retain it through uninstall until
  the operator explicitly removes it;
- retain `<destination>.rollback` after an upgrade for manual operator restore;
- reuse U6.4-D preflight and U6.4-E staging, signature, manifest, storage, and
  rollback checks;
- return a machine-readable install result with target, version, manifest and
  runtime identities, storage outcome, rollback record, and boundary status;
- verify one target slice at a time on the existing matching offline CI
  runners.

## Consequences

The repository now has a bounded install contract. U6.4-D/E remain
authoritative, Python remains the domain authority, and the portable adapter
keeps platform mechanics local to Electron without reopening connected or live
execution.

## Rejected for this planning stage

- choosing MSI, AppImage, or distribution-specific package-manager integration;
- machine-wide installation or elevation;
- registering systemd, Windows services, or another native supervisor; and
- reopening connected access, providers, credentials, mutation, or live
  execution.

## Exit condition

The exit condition is matching Windows/Linux evidence for signed portable
installation, embedded-runtime provenance, fresh install, upgrade, manual
rollback, preserved state, verification failure recovery, and uninstall
retention, repair, and retry. The exact per-target CPython patches and runner
images are frozen in CI evidence.
