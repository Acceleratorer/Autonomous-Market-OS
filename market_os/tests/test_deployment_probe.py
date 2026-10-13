from __future__ import annotations

from pathlib import Path

from market_os.deployment_probe import run_probe


def test_deployment_probe_records_service_evidence_and_blockers(tmp_path: Path) -> None:
    report = run_probe(tmp_path / "deployment.json")

    names = {probe["name"] for probe in report["probes"]}
    assert {"service-readiness", "health-endpoint", "task-api", "startup-recovery", "clean-restart"} <= names
    assert report["promotion_status"] == "Provisional"
    assert {"resource-limits", "service-request-timeouts", "service-logging", "filesystem-permissions"} <= set(report["blockers"])
    assert {"bounded-wrapper-startup", "bounded-wrapper-shutdown", "structured-logs"} <= names
