from __future__ import annotations

import json
from pathlib import Path

import pytest

from market_os.contracts import (
    API_VERSION,
    Artifact,
    BacktestResult,
    ContractError,
    Evidence,
    Order,
    OrderPlan,
    ResearchResult,
    RiskDecision,
    Run,
    RunEvent,
    Task,
    error_response,
    from_json,
    to_json,
)

FIXTURES = Path(__file__).parent / "fixtures" / "contracts"


def fixture(name: str) -> str:
    return (FIXTURES / f"{name}.json").read_text(encoding="utf-8")


def test_representative_fixtures_decode_for_every_current_contract() -> None:
    types = {"task": Task, "run": Run, "run_event": RunEvent, "artifact": Artifact, "evidence": Evidence, "research_result": ResearchResult, "backtest_result": BacktestResult, "order": Order, "order_plan": OrderPlan, "risk_decision": RiskDecision}
    for name, contract_type in types.items():
        value = from_json(fixture(name), contract_type)
        assert json.loads(to_json(value)).get("api_version", API_VERSION) == API_VERSION


def test_stable_json_serialization_is_key_sorted_and_round_trips() -> None:
    first = from_json(fixture("task"), Task)
    encoded = to_json(first)
    assert encoded == to_json(first)
    assert encoded.startswith('{"api_version":"market-os.v1"')
    assert from_json(encoded, Task) == first


def test_backward_compatible_read_defaults_optional_fields_and_current_version() -> None:
    payload = json.loads(fixture("task"))
    payload.pop("api_version")
    payload.pop("idempotency_key")
    task = from_json(json.dumps(payload), Task)
    assert task.api_version == API_VERSION
    assert task.idempotency_key is None


@pytest.mark.parametrize(
    ("name", "contract_type", "expected_code"),
    [
        ("task_missing_id", Task, "missing_field"),
        ("task_bad_version", Task, "unsupported_version"),
        ("task_naive_timestamp", Task, "invalid_timestamp"),
        ("task_bad_symbol", Task, "invalid_symbol"),
        ("task_live", Task, "live_disabled"),
        ("run_bad_status", Run, "invalid_status"),
        ("run_event_bad_cost", RunEvent, "invalid_number"),
        ("order_negative", Order, "invalid_number"),
        ("order_plan_live", OrderPlan, "live_disabled"),
        ("risk_missing_reason", RiskDecision, "missing_reason"),
    ],
)
def test_invalid_payloads_are_rejected_with_stable_codes(name: str, contract_type: type, expected_code: str) -> None:
    with pytest.raises(ContractError) as exc:
        from_json(fixture(name), contract_type)
    assert exc.value.code == expected_code


def test_unknown_and_missing_fields_are_rejected() -> None:
    payload = json.loads(fixture("task"))
    payload["surprise"] = True
    with pytest.raises(ContractError) as unknown:
        from_json(json.dumps(payload), Task)
    assert unknown.value.code == "unknown_field"
    payload = json.loads(fixture("task"))
    payload.pop("objective")
    with pytest.raises(ContractError) as missing:
        from_json(json.dumps(payload), Task)
    assert missing.value.code == "missing_field"


def test_error_response_is_json_compatible() -> None:
    response = error_response(ContractError("invalid_date", "start is invalid", field="start"), request_id="req-1")
    assert response["code"] == "invalid_date"
    assert json.dumps(response)
