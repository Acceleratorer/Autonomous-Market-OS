from __future__ import annotations

from market_os.orchestration.recovery import RecoveryReport, RecoveryProbeResult


def test_coordination_blockers_cannot_be_hidden_by_runtime_verified_flag() -> None:
    report = RecoveryReport(
        runtime_verified=True,
        probes=(
            RecoveryProbeResult(
                probe_name="multi-agent-coordination",
                runtime_version="openharness:test",
                environment_id="test",
                started_at="2026-10-13T00:00:00+00:00",
                finished_at="2026-10-13T00:00:01+00:00",
                expected_behavior="aggregate",
                observed_behavior="unsupported",
                passed=False,
                runtime_verified=True,
            ),
        ),
        blockers=("multi-agent-coordination",),
        promotion_status="Provisional",
    )

    assert report.promotable is False
    assert report.to_dict()["blockers"] == ["multi-agent-coordination"]
