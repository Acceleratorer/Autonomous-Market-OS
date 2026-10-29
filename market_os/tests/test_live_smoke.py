from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import m2_8_live_smoke as smoke
import ci_checks


def _clear_smoke_environment(monkeypatch) -> None:
    for name in (
        "OPENAI_API_KEY",
        "MARKET_OS_OPENAI_LIVE_APPROVED",
        "MARKET_OS_OPENAI_MODEL",
        "MARKET_OS_OPENAI_MAX_REQUESTS",
        "MARKET_OS_OPENAI_MAX_OUTPUT_TOKENS",
        "MARKET_OS_OPENAI_MAX_INPUT_BYTES",
        "MARKET_OS_OPENAI_MAX_SPEND_USD",
        "MARKET_OS_OPENAI_REQUEST_TIMEOUT_SECONDS",
        "MARKET_OS_OPENAI_MAX_RETRIES",
        "MARKET_OS_OPENAI_DATA_RETENTION_ACK",
        "MARKET_OS_NON_PRODUCTION",
        "MARKET_OS_PAPER_ONLY",
        smoke.LIVE_SMOKE_APPROVAL,
    ):
        monkeypatch.delenv(name, raising=False)


def test_offline_preparation_writes_redacted_synthetic_evidence_without_transport(tmp_path, monkeypatch) -> None:
    import urllib.request

    _clear_smoke_environment(monkeypatch)
    monkeypatch.setattr(urllib.request, "build_opener", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("unexpected transport")))
    evidence_path = tmp_path / "m2.8-evidence.json"

    assert smoke.main(["--evidence", str(evidence_path)]) == 0

    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["status"] == "pending-approval"
    assert evidence["live_smoke_run"] is False
    assert evidence["request_count"] == 0
    assert evidence["data_class"] == "synthetic-internal"
    assert evidence["payload_bytes"] <= evidence["max_input_bytes"]
    assert evidence["redaction"]["raw_request"] == "omitted"


def test_live_execution_requires_the_separate_m2_8_approval(monkeypatch) -> None:
    _clear_smoke_environment(monkeypatch)
    with pytest.raises(ValueError, match=smoke.LIVE_SMOKE_APPROVAL):
        smoke._config_values(execute=True)


def test_live_execution_refuses_offline_placeholder_key(monkeypatch) -> None:
    _clear_smoke_environment(monkeypatch)
    monkeypatch.setenv(smoke.LIVE_SMOKE_APPROVAL, "1")
    monkeypatch.setenv("OPENAI_API_KEY", "offline-validation-placeholder")
    monkeypatch.setenv("MARKET_OS_OPENAI_LIVE_APPROVED", "1")
    monkeypatch.setenv("MARKET_OS_OPENAI_MODEL", "gpt-6.1-sol")
    monkeypatch.setenv("MARKET_OS_OPENAI_MAX_REQUESTS", "1")
    monkeypatch.setenv("MARKET_OS_OPENAI_MAX_OUTPUT_TOKENS", "512")
    monkeypatch.setenv("MARKET_OS_OPENAI_MAX_INPUT_BYTES", "16000")
    monkeypatch.setenv("MARKET_OS_OPENAI_MAX_SPEND_USD", "0.02")
    monkeypatch.setenv("MARKET_OS_OPENAI_REQUEST_TIMEOUT_SECONDS", "20")
    monkeypatch.setenv("MARKET_OS_OPENAI_MAX_RETRIES", "0")
    monkeypatch.setenv("MARKET_OS_OPENAI_DATA_RETENTION_ACK", "1")
    monkeypatch.setenv("MARKET_OS_NON_PRODUCTION", "1")
    monkeypatch.setenv("MARKET_OS_PAPER_ONLY", "1")
    with pytest.raises(ValueError, match="placeholder"):
        smoke._config_values(execute=True)


def test_smoke_passage_is_exactly_from_the_cited_synthetic_document() -> None:
    corpus = json.loads(smoke.CORPUS.read_text(encoding="utf-8"))
    document = corpus["documents"][0]
    synthesis = smoke._synthesis()

    assert synthesis.passages[0].text == document["content"]
    assert synthesis.passages[0].document_id == document["document_id"]


def test_live_smoke_execution_reservation_is_one_shot(tmp_path, monkeypatch) -> None:
    path = tmp_path / "evidence.json"
    monkeypatch.setattr(smoke, "EVIDENCE", path)
    path.write_text(json.dumps({
        "status": "pending-approval",
        "request_count": 0,
        "execution_reserved": False,
        "payload_sha256": "a" * 64,
        "synthesis_fingerprint": "b" * 64,
    }), encoding="utf-8")
    smoke._reserve_execution(path, "a" * 64, "b" * 64)
    with pytest.raises(ValueError, match="already been consumed"):
        smoke._reserve_execution(path, "a" * 64, "b" * 64)


def test_evidence_validator_accepts_one_approved_executed_request(tmp_path, monkeypatch) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    evidence = json.loads(smoke.EVIDENCE.read_text(encoding="utf-8"))
    evidence.update(
        {
            "status": "Passed with fallback — transport completed but deterministic fallback was required",
            "live_smoke_run": True,
            "request_count": 1,
            "approval": {"adapter": True, "m2_8_execution": True},
            "execution_reserved": True,
        }
    )
    (evidence_dir / "m2.8-live-smoke.json").write_text(json.dumps(evidence), encoding="utf-8")
    monkeypatch.setattr(ci_checks, "EVIDENCE", evidence_dir)

    ci_checks.validate_m2_8_evidence()


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        ("MARKET_OS_OPENAI_MAX_REQUESTS", "2", "MAX_REQUESTS=1"),
        ("MARKET_OS_OPENAI_MAX_RETRIES", "1", "MAX_RETRIES=0"),
        ("MARKET_OS_OPENAI_MAX_SPEND_USD", "0.0201", "spend limit"),
        ("MARKET_OS_OPENAI_REQUEST_TIMEOUT_SECONDS", "20.1", "timeout"),
    ],
)
def test_m2_8_bounds_reject_overrides(monkeypatch, name: str, value: str, message: str) -> None:
    _clear_smoke_environment(monkeypatch)
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError, match=message):
        smoke._config_values(execute=False)
