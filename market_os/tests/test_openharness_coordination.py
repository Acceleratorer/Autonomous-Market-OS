from __future__ import annotations

from market_os.orchestration.recovery import RecoveryReport, RecoveryProbeResult
from market_os.orchestration.openharness_adapter import AgentResult, aggregate_agent_results


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


def test_multi_agent_aggregation_preserves_partial_failures_and_deduplicates() -> None:
    values = [
        AgentResult.success("researcher", "task-1", "run-1", 1, {"finding": "x"}, artifacts=("a1",)),
        AgentResult.success("researcher", "task-1", "run-1", 1, {"finding": "x"}, artifacts=("a1",)),
        AgentResult.failed("risk", "task-1", "run-1", 2, "limit unavailable"),
        AgentResult.success("other", "task-1", "run-1", 3, {"finding": "x"}),
    ]

    aggregate = aggregate_agent_results(values)

    assert aggregate.api_version == "market-os.multi-agent.v1"
    assert aggregate.status == "partial"
    assert [item.agent_id for item in aggregate.results] == ["researcher", "risk", "other"]
    assert len(aggregate.duplicates) == 1
    assert aggregate.results[1].error == {"code": "agent_failed", "message": "limit unavailable"}
    assert aggregate.artifacts == ("a1",)


def test_multi_agent_aggregation_marks_conflicting_same_agent_result() -> None:
    aggregate = aggregate_agent_results(
        [
            AgentResult.success("researcher", "task-1", "run-1", 1, {"finding": "x"}),
            AgentResult.success("researcher", "task-1", "run-1", 2, {"finding": "y"}),
        ]
    )

    assert aggregate.status == "failed"
    assert aggregate.conflicts[0]["agent_id"] == "researcher"
