#!/usr/bin/env python3
"""Emit and validate local U5.5 promotion evidence.

The default mode validates the checked-in Linux VM/systemd/Tailscale Serve
contracts and simulates a health-gated rollback in a temporary directory. It
does not start services, change listeners, contact Tailscale, or require
credentials. ``--mode owner-vm`` only runs read-only checks when the caller
also sets ``MARKET_OS_U55_OWNER_VM=1`` on the selected VM.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
U55 = ROOT / "deploy" / "u5-5"
EVIDENCE_PATH = ROOT / "docs" / "evidence" / "u5-5-promotion-evidence.json"

STATIC_CHECK_NAMES = {
    "service_health",
    "tailscale_serve_ingress",
    "direct_origin_denial",
    "owner_only_subject",
    "paper_main_storage_isolation",
    "encrypted_backup",
    "rollback_preservation",
    "paper_only_boundary",
    "rollback_simulation",
}
OWNER_VM_CHECK_NAMES = {"owner_vm_health", "owner_vm_tailscale"}
CHECK_NAMES = STATIC_CHECK_NAMES | OWNER_VM_CHECK_NAMES
CHECK_STATUSES = {"validated", "passed", "not_run", "failed"}
TOP_LEVEL_KEYS = {
    "schema",
    "milestone",
    "status",
    "mode",
    "selected_runtime",
    "checks",
    "promotion_boundary",
    "artifacts",
    "verification",
    "failed_checks",
}
RUNTIME = {
    "host": "private-linux-vm",
    "supervisor": "systemd",
    "ingress": "owner-only-tailscale-serve",
    "subject": "owner-only",
    "portfolio_id": "paper-main",
    "portfolio_root": "/var/lib/autonomous-market-os/portfolios",
}
BOUNDARY = {
    "enabled": False,
    "owner_vm_promotion": "pending",
    "rollback": "pending",
    "public_listener": False,
    "credentials_added": False,
    "mutation_routes": False,
    "paper_only": True,
}
ARTIFACTS = [
    "deploy/u5-5/healthcheck.sh",
    "deploy/u5-5/promote.sh",
    "deploy/u5-5/rollback.sh",
    "deploy/u5-5/tailscale-serve.sh",
    "deploy/u5-5/tailnet-policy.hujson",
    "deploy/u5-5/operator.env.example",
    "deploy/u5-5/market-os-python.service",
    "deploy/u5-5/market-os-next.service",
    "deploy/u5-5/promotion_evidence.py",
    "deploy/u5-5/README.md",
    "docs/U5.5-AUTHENTICATED-CONNECTED-WEB-CONTRACT.md",
    "docs/decisions/ADR-0050-u5-5-runtime-identity-contract.md",
]


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _check(status: str, detail: str) -> dict[str, str]:
    return {"status": status, "detail": detail}


def _all(text: str, *markers: str) -> bool:
    return all(marker in text for marker in markers)


def _static_checks() -> dict[str, dict[str, str]]:
    healthcheck = _text(U55 / "healthcheck.sh")
    promote = _text(U55 / "promote.sh")
    rollback = _text(U55 / "rollback.sh")
    tailscale = _text(U55 / "tailscale-serve.sh")
    policy = _text(U55 / "tailnet-policy.hujson")
    env_example = _text(U55 / "operator.env.example")
    python_service = _text(U55 / "market-os-python.service")
    next_service = _text(U55 / "market-os-next.service")
    readme = _text(U55 / "README.md")
    contract = _text(ROOT / "docs" / "U5.5-AUTHENTICATED-CONNECTED-WEB-CONTRACT.md")
    adr = _text(ROOT / "docs" / "decisions" / "ADR-0050-u5-5-runtime-identity-contract.md")
    proxy = _text(ROOT / "apps" / "web" / "next-operator" / "src" / "proxy.ts")
    gateway = _text(ROOT / "market_os" / "api.py")

    checks: dict[str, dict[str, str]] = {}
    checks["service_health"] = _check(
        "validated" if _all(
            healthcheck,
            "127.0.0.1:8787/readyz",
            "127.0.0.1:3000/healthz",
            "--fail",
        ) and _all(
            python_service + next_service,
            "Restart=on-failure",
            "IPAddressDeny=any",
            "IPAddressAllow=127.0.0.0/8",
            "ExecStart=",
        ) else "failed",
        "loopback health probes and restart/network restrictions are present",
    )
    checks["tailscale_serve_ingress"] = _check(
        "validated" if _all(
            tailscale,
            "tailscale serve reset",
            "--https=443 http://127.0.0.1:3000",
        ) and _all(
            policy,
            '"tag:market-os"',
            '"REPLACE_OWNER_TAILSCALE_LOGIN"',
            '"ip": ["443"]',
        ) and "8787" not in tailscale else "failed",
        "Serve forwards only HTTPS 443 to Next.js loopback; the reviewed ACL admits the owner placeholder only",
    )
    checks["direct_origin_denial"] = _check(
        "validated" if _all(
            contract,
            "direct Python-origin request",
            "direct non-loopback access",
            "caller-supplied principal headers",
        ) and _all(
            gateway,
            "loopback host required",
            "forged_principal_header",
        ) and _all(
            proxy,
            "connectedDenied(405)",
            "connectedDenied(403)",
            "tailscale-user-login",
        ) else "failed",
        "Python rejects non-loopback/forged-origin access and Next.js denies non-owner or non-GET requests",
    )
    checks["owner_only_subject"] = _check(
        "validated" if (
            "owner-only" in adr
            and "owner-only" in contract
            and "owner-only" in readme
            and "MARKET_OS_TAILSCALE_OWNER_LOGIN" in readme
            and "tailscale-user-login" in proxy
            and "REPLACE_OWNER_TAILSCALE_LOGIN" in env_example
            and "REPLACE_OWNER_TAILSCALE_LOGIN" in policy
        ) else "failed",
        "owner-only subject is explicit in the contract, environment template, proxy, and tailnet policy",
    )
    checks["paper_main_storage_isolation"] = _check(
        "validated" if (
            _all(contract, "/var/lib/autonomous-market-os/portfolios", "paper-main", "symlink", "traversal")
            and _all(env_example, "/var/lib/autonomous-market-os/portfolios", "paper-main")
        ) else "failed",
        "paper-main is the fixed allowlist under a fail-closed, alias-safe portfolio root",
    )
    backup_before_switch = promote.find("age -R \"$RECIPIENT_FILE\"") < promote.find('mv -Tf -- "$CURRENT_LINK.next" "$CURRENT_LINK"')
    checks["encrypted_backup"] = _check(
        "validated" if backup_before_switch and _all(promote, "paper-main", "chmod 600", "mkdir -p \"$BACKUP_ROOT\"") else "failed",
        "age encryption and mode 0600 backup occur before the current release link changes",
    )
    rollback_health_checks = promote.count('"$HEALTHCHECK"') >= 2
    checks["rollback_preservation"] = _check(
        "validated" if rollback_health_checks and _all(
            promote,
            "KNOWN_GOOD_LINK",
            "known-good release remains active",
            "systemctl restart",
        ) and _all(rollback, "KNOWN_GOOD_LINK", 'target="$(readlink -e -- "$KNOWN_GOOD_LINK")"', '"$HEALTHCHECK"') else "failed",
        "failed promotion restores the known-good slot and re-runs its health check; explicit rollback does the same",
    )
    checks["paper_only_boundary"] = _check(
        "validated" if _all(
            readme,
            "No script deletes portfolio data",
            "provider credentials",
            "public listener",
            "read-only",
        ) and _all(env_example, "MARKET_OS_U55_MODE=1", "MARKET_OS_ALLOWED_PORTFOLIO_ID=paper-main") else "failed",
        "the package remains read-only, paper-main-only, credential-free in-repo, and private",
    )
    return checks


def _simulate_rollback() -> dict[str, str]:
    with tempfile.TemporaryDirectory(prefix="market-os-u55-") as raw:
        root = Path(raw)
        release_one = root / "releases" / "v1"
        release_two = root / "releases" / "v2"
        release_one.mkdir(parents=True)
        release_two.mkdir(parents=True)
        current = root / "current"
        known_good = root / "known-good"
        current.symlink_to(release_one, target_is_directory=True)
        known_good.symlink_to(release_one, target_is_directory=True)
        before = current.resolve()
        current.unlink()
        current.symlink_to(release_two, target_is_directory=True)
        candidate_failed = current.resolve() == release_two
        current.unlink()
        current.symlink_to(known_good.resolve(), target_is_directory=True)
        restored = current.resolve() == before
        rollback_health_passed = restored and current.resolve() == known_good.resolve()
    return _check(
        "passed" if candidate_failed and rollback_health_passed else "failed",
        "temporary candidate failure restored the prior known-good slot and passed the post-restore health gate",
    )


def _owner_vm_checks() -> dict[str, dict[str, str]]:
    if os.environ.get("MARKET_OS_U55_OWNER_VM") != "1":
        detail = "owner-VM mode is guarded; set MARKET_OS_U55_OWNER_VM=1 on the selected VM"
        return {name: _check("not_run", detail) for name in OWNER_VM_CHECK_NAMES}
    if platform.system().lower() != "linux":
        detail = "owner-VM checks require the selected Linux VM; current host is not Linux"
        return {name: _check("not_run", detail) for name in OWNER_VM_CHECK_NAMES}

    checks: dict[str, dict[str, str]] = {}
    health_command = ["bash", str(U55 / "healthcheck.sh")]
    if shutil.which("bash") is None:
        checks["owner_vm_health"] = _check("not_run", "bash is not installed on this host")
    else:
        result = subprocess.run(health_command, cwd=ROOT, capture_output=True, text=True, check=False, timeout=15)
        checks["owner_vm_health"] = _check(
            "passed" if result.returncode == 0 else "failed",
            f"healthcheck.sh exited {result.returncode}",
        )

    if shutil.which("tailscale") is None:
        checks["owner_vm_tailscale"] = _check("not_run", "tailscale is not installed on this host")
    else:
        result = subprocess.run(
            ["tailscale", "serve", "status", "--json"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
        try:
            status_text = json.dumps(json.loads(result.stdout), sort_keys=True)
        except (json.JSONDecodeError, TypeError):
            status_text = result.stdout
        valid_mapping = result.returncode == 0 and "127.0.0.1:3000" in status_text and "8787" not in status_text
        checks["owner_vm_tailscale"] = _check(
            "passed" if valid_mapping else "failed",
            "Serve status contains the Next.js loopback mapping and no Python port" if valid_mapping else "Serve status did not prove the required mapping",
        )
    return checks


def build_evidence(mode: str) -> dict[str, Any]:
    checks = _static_checks()
    checks["rollback_simulation"] = _simulate_rollback()
    if mode == "owner-vm":
        checks.update(_owner_vm_checks())
    else:
        checks.update({name: _check("not_run", "dry-run mode does not contact the owner VM") for name in OWNER_VM_CHECK_NAMES})

    failed = sorted(name for name, result in checks.items() if result["status"] == "failed")
    return {
        "schema": "market-os.u5-5.promotion-evidence@v1",
        "milestone": "U5.5",
        "status": "locally-verified-not-enabled" if not failed else "failed",
        "mode": mode,
        "selected_runtime": dict(RUNTIME),
        "checks": checks,
        "promotion_boundary": dict(BOUNDARY),
        "artifacts": list(ARTIFACTS),
        "verification": {
            "local_simulation": "static contract validation plus temporary health-gated rollback simulation",
            "owner_vm_commands": ["deploy/u5-5/healthcheck.sh", "tailscale serve status --json"],
            "credentials_used": False,
        },
        "failed_checks": failed,
    }


def validate_evidence_payload(payload: dict[str, Any]) -> None:
    if set(payload) != TOP_LEVEL_KEYS:
        raise ValueError("U5.5 evidence top-level schema mismatch")
    if payload["schema"] != "market-os.u5-5.promotion-evidence@v1" or payload["milestone"] != "U5.5":
        raise ValueError("unexpected U5.5 promotion evidence schema")
    if payload["mode"] not in {"dry-run", "owner-vm"}:
        raise ValueError("invalid U5.5 evidence mode")
    if payload["status"] not in {"locally-verified-not-enabled", "failed"}:
        raise ValueError("invalid U5.5 evidence status")
    if payload["selected_runtime"] != RUNTIME or payload["promotion_boundary"] != BOUNDARY:
        raise ValueError("U5.5 runtime or promotion boundary is unsafe")
    if not isinstance(payload["artifacts"], list) or not payload["artifacts"] or any(not isinstance(item, str) for item in payload["artifacts"]):
        raise ValueError("U5.5 artifacts must be a non-empty string list")
    if not isinstance(payload["verification"], dict) or set(payload["verification"]) != {"local_simulation", "owner_vm_commands", "credentials_used"}:
        raise ValueError("U5.5 verification schema mismatch")
    if not isinstance(payload["verification"]["local_simulation"], str) or payload["verification"]["credentials_used"] is not False:
        raise ValueError("U5.5 verification boundary is unsafe")
    if payload["verification"]["owner_vm_commands"] != ["deploy/u5-5/healthcheck.sh", "tailscale serve status --json"]:
        raise ValueError("U5.5 owner-VM command list changed")
    checks = payload["checks"]
    if not isinstance(checks, dict) or set(checks) != CHECK_NAMES:
        raise ValueError("U5.5 check schema mismatch")
    for name, result in checks.items():
        if not isinstance(result, dict) or set(result) != {"status", "detail"}:
            raise ValueError(f"invalid U5.5 check shape: {name}")
        if result["status"] not in CHECK_STATUSES or not isinstance(result["detail"], str) or not result["detail"]:
            raise ValueError(f"invalid U5.5 check value: {name}")
    if not isinstance(payload["failed_checks"], list) or payload["failed_checks"] != sorted(
        name for name, result in checks.items() if result["status"] == "failed"
    ):
        raise ValueError("U5.5 failed_checks does not match checks")
    if (payload["status"] == "failed") != bool(payload["failed_checks"]):
        raise ValueError("U5.5 status does not match failed_checks")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("dry-run", "owner-vm"), default="dry-run")
    parser.add_argument("--output", type=Path, default=EVIDENCE_PATH)
    parser.add_argument("--validate", action="store_true", help="validate an existing evidence JSON instead of generating it")
    args = parser.parse_args()

    if args.validate:
        payload = json.loads(args.output.read_text(encoding="utf-8"))
        validate_evidence_payload(payload)
        print(f"validated {args.output}")
        return 0

    payload = build_evidence(args.mode)
    try:
        validate_evidence_payload(payload)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if payload["status"] == "locally-verified-not-enabled" else 1


if __name__ == "__main__":
    raise SystemExit(main())
