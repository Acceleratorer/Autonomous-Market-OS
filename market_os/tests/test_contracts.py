from __future__ import annotations

import json

import pytest

from market_os.contracts import (
    API_VERSION,
    Approval,
    ContractError,
    OrderPlan,
    Run,
    Task,
    error_response,
    order_plan_from_dict,
    task_from_dict,
    to_dict,
)


def test_task_json_boundary_normalizes_arrays_and_preserves_version() -> None:
    task = task_from_dict({
        "task_id": "task-example-1",
        "objective": "Compare candidates",
        "symbols": ["SPY", "QQQ"],
        "start": "2026-01-02",
        "end": "2026-01-06",
        "created_at": "2026-10-13T00:00:00+00:00",
        "execution_mode": "paper",
        "api_version": API_VERSION,
    })
    assert task.symbols == ("SPY", "QQQ")
    assert json.loads(json.dumps(to_dict(task)))["api_version"] == API_VERSION


def test_invalid_version_and_live_mode_are_rejected_with_stable_codes() -> None:
    base = {
        "task_id": "task-1", "objective": "Research", "symbols": ("SPY",),
        "start": "2026-01-02", "end": "2026-01-06",
        "created_at": "2026-10-13T00:00:00+00:00",
    }
    with pytest.raises(ContractError) as version_error:
        Task(**base, api_version="market-os.v2")
    assert version_error.value.code == "unsupported_version"
    with pytest.raises(ContractError) as live_error:
        Task(**base, execution_mode="live")
    assert live_error.value.code == "live_disabled"


def test_terminal_contracts_require_error_or_decision_metadata() -> None:
    with pytest.raises(ContractError, match="include error"):
        Run("run-1", "task-1", "failed", "2026-10-13T00:00:00+00:00", "2026-10-13T00:01:00+00:00")
    with pytest.raises(ContractError, match="decided_by"):
        Approval("approval-1", "run-1", "approved", "user", "2026-10-13T00:00:00+00:00")


def test_error_response_is_json_compatible() -> None:
    error = ContractError("invalid_date", "start is invalid", field="start")
    response = error_response(error, request_id="req-1")
    assert response["code"] == "invalid_date"
    assert response["field"] == "start"
    assert json.dumps(response)


def test_order_plan_parser_cannot_create_live_plan() -> None:
    with pytest.raises(ContractError, match="live execution"):
        order_plan_from_dict({"mode": "live", "orders": [], "total_notional": 0})
