from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from market_os.model_summary import gate_summary, make_summary_request
from market_os.provider_selection import selected_workflow
from market_os.store import RunStore
from market_os.tests.test_model_summary import _synthesis
from market_os.workflow import MarketWorkflow


FIXTURE = Path(__file__).parent / "fixtures" / "model_summary" / "openai_responses.json"


def _records() -> dict:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert payload["label"].startswith("recorded synthetic")
    return payload


def _recorded(name: str, synthesis=None):
    from market_os.adapters.openai_summary import RecordedResponsesSummaryProvider

    return RecordedResponsesSummaryProvider(_records()[name], synthesis or _synthesis())


def test_recorded_response_parses_supported_inference_and_unsupported_statements() -> None:
    synthesis = _synthesis()
    summary = gate_summary(_recorded("valid", synthesis), "Inspect", synthesis, synthesis_artifact_id="artifact-cited")
    assert summary.provider.provider == "openai-recorded"
    assert summary.gate.status == "approved"
    assert summary.validation.supported_count == 1
    assert summary.validation.inference_count == 1
    assert summary.validation.unsupported_count == 1
    assert summary.usage.input_units == 44
    assert summary.usage.output_units == 38
    assert summary.usage.estimated_cost == pytest.approx(0.000468)
    assert summary.summary_text.startswith("SPY is a synthetic ETF fixture. Inference: ")


@pytest.mark.parametrize(
    ("case", "error_fragment"),
    [("missing-citation", "lacks evidence"), ("invalid-citation", "unknown citation"),
     ("quote-mismatch", "exact evidence quote"), ("cross-run", "unknown citation"),
     ("secret-like-output", "secret-like"), ("prompt-injection-like-output", "exact evidence quote"),
     ("oversized-output", "maximum length")],
)
def test_recorded_invalid_responses_are_rejected_without_publishing(case: str, error_fragment: str) -> None:
    synthesis = _synthesis()
    summary = gate_summary(_recorded(case, synthesis), "Inspect", synthesis, synthesis_artifact_id="artifact-cited")
    assert summary.gate.status == "rejected"
    assert summary.summary_text is None
    assert summary.gate.deterministic_fallback is True
    assert any(error_fragment in error for error in summary.validation.errors)


def test_recorded_malformed_response_is_rejected() -> None:
    synthesis = _synthesis()
    summary = gate_summary(_recorded("malformed-output", synthesis), "Inspect", synthesis, synthesis_artifact_id="artifact-cited")
    assert summary.gate.status == "rejected"
    assert any("malformed_model_output" in error for error in summary.validation.errors)


@pytest.mark.parametrize(("case", "kind"), [("provider-error", "error"), ("timeout", "timeout")])
def test_recorded_provider_failures_preserve_deterministic_fallback(case: str, kind: str) -> None:
    synthesis = _synthesis()
    summary = gate_summary(_recorded(case, synthesis), "Inspect", synthesis, synthesis_artifact_id="artifact-cited")
    assert summary.gate.status == "fallback"
    assert summary.failure.kind == kind
    assert summary.deterministic_fallback_fingerprint == synthesis.synthesis_fingerprint


def test_recorded_replay_has_stable_fingerprint_and_unknown_usage() -> None:
    synthesis = _synthesis()
    first = gate_summary(_recorded("unknown-usage", synthesis), "Inspect", synthesis, synthesis_artifact_id="artifact-cited")
    second = gate_summary(_recorded("unknown-usage", synthesis), "Inspect", synthesis, synthesis_artifact_id="artifact-cited")
    assert first.summary_fingerprint == second.summary_fingerprint
    assert first.usage.input_units is None
    assert first.usage.output_units is None


def test_default_selection_does_not_import_or_call_openai(tmp_path: Path, monkeypatch) -> None:
    import urllib.request

    monkeypatch.setattr(urllib.request, "urlopen", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("unexpected outbound HTTP")))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    selected = selected_workflow(MarketWorkflow(RunStore(tmp_path)), "fixture", "fixture")
    assert selected.summary_provider is None
    result = selected.run(selected.create_task("Offline", ["SPY"], "2026-01-02", "2026-01-06"))
    assert result["run"]["status"] == "completed"
    assert "model_summary" not in result
    probe = subprocess.run([sys.executable, "-c", "import sys, market_os.cli; assert 'market_os.adapters.openai_summary' not in sys.modules"], capture_output=True, text=True)
    assert probe.returncode == 0, probe.stderr


def _approved_environment() -> dict[str, str]:
    return {
        "OPENAI_API_KEY": "synthetic-test-key",
        "MARKET_OS_OPENAI_LIVE_APPROVED": "1",
        "MARKET_OS_OPENAI_MODEL": "gpt-6.1-sol",
        "MARKET_OS_OPENAI_MAX_REQUESTS": "1",
        "MARKET_OS_OPENAI_MAX_OUTPUT_TOKENS": "512",
        "MARKET_OS_OPENAI_MAX_INPUT_BYTES": "16000",
        "MARKET_OS_OPENAI_MAX_SPEND_USD": "0.02",
        "MARKET_OS_OPENAI_REQUEST_TIMEOUT_SECONDS": "20",
        "MARKET_OS_OPENAI_MAX_RETRIES": "0",
        "MARKET_OS_OPENAI_DATA_RETENTION_ACK": "1",
        "MARKET_OS_NON_PRODUCTION": "1",
        "MARKET_OS_PAPER_ONLY": "1",
    }


def test_live_adapter_requires_approval_before_network(monkeypatch) -> None:
    import urllib.request
    from market_os.adapters.openai_summary import OpenAIConfigError, OpenAIResponsesSummaryProvider

    calls = []
    monkeypatch.setattr(urllib.request, "urlopen", lambda *args, **kwargs: calls.append(args))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(OpenAIConfigError, match="approval"):
        OpenAIResponsesSummaryProvider.from_environment({})
    assert calls == []


def test_explicit_openai_selection_fails_closed_without_approval(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(Exception, match="approval|OPENAI_API_KEY"):
        selected_workflow(MarketWorkflow(RunStore(tmp_path)), "lightrag", "fixture", "openai")


def test_recorded_selection_requires_an_explicit_synthetic_fixture(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("MARKET_OS_OPENAI_RECORDED_RESPONSE", raising=False)
    with pytest.raises(Exception, match="recorded"):
        selected_workflow(MarketWorkflow(RunStore(tmp_path)), "lightrag", "fixture", "openai-recorded")


@pytest.mark.parametrize(
    ("override", "message"),
    [({"MARKET_OS_OPENAI_MODEL": "unknown-model"}, "model"), ({"MARKET_OS_OPENAI_MAX_REQUESTS": "0"}, "request"),
     ({"MARKET_OS_OPENAI_MAX_OUTPUT_TOKENS": "513"}, "output"), ({"MARKET_OS_OPENAI_MAX_SPEND_USD": "0"}, "spend"),
     ({"MARKET_OS_OPENAI_REQUEST_TIMEOUT_SECONDS": "0"}, "timeout"), ({"MARKET_OS_NON_PRODUCTION": "0"}, "non-production"),
     ({"MARKET_OS_OPENAI_DATA_RETENTION_ACK": "0"}, "retention"), ({"MARKET_OS_PAPER_ONLY": "0"}, "paper-only")],
)
def test_invalid_live_configuration_fails_before_transport(monkeypatch, override: dict[str, str], message: str) -> None:
    import urllib.request
    from market_os.adapters.openai_summary import OpenAIConfigError, OpenAIResponsesSummaryProvider

    calls = []
    monkeypatch.setattr(urllib.request, "urlopen", lambda *args, **kwargs: calls.append(args))
    config = _approved_environment()
    config.update(override)
    with pytest.raises(OpenAIConfigError, match=message):
        OpenAIResponsesSummaryProvider.from_environment(config)
    assert calls == []


def test_live_adapter_refuses_request_over_budget_before_transport(monkeypatch) -> None:
    import urllib.request
    from market_os.adapters.openai_summary import OpenAIConfig, OpenAIResponsesSummaryProvider, OpenAIRequestError

    calls = []
    monkeypatch.setattr(urllib.request, "urlopen", lambda *args, **kwargs: calls.append(args))
    config = OpenAIConfig.from_mapping({**_approved_environment(), "MARKET_OS_OPENAI_MAX_SPEND_USD": "0.000001"})
    provider = OpenAIResponsesSummaryProvider(config)
    synthesis = _synthesis()
    with pytest.raises(OpenAIRequestError, match="budget"):
        provider.generate(make_summary_request("Inspect", synthesis, "test"), synthesis)
    assert calls == []


def test_live_adapter_reserves_cumulative_spend_before_each_request(monkeypatch) -> None:
    from market_os.adapters.openai_summary import OpenAIConfig, OpenAIRequestError, OpenAIResponsesSummaryProvider

    config = OpenAIConfig.from_mapping({
        **_approved_environment(),
        "MARKET_OS_OPENAI_MAX_REQUESTS": "2",
        "MARKET_OS_OPENAI_MAX_RETRIES": "0",
        "MARKET_OS_OPENAI_MAX_SPEND_USD": "0.02",
    })
    provider = OpenAIResponsesSummaryProvider(config)
    response = _records()["unknown-usage"]
    calls = []

    def respond(_encoded: bytes) -> dict:
        calls.append(True)
        return response

    monkeypatch.setattr(provider, "_post", respond)
    synthesis = _synthesis()
    request = make_summary_request("Inspect", synthesis, "test")
    provider.generate(request, synthesis)
    with pytest.raises(OpenAIRequestError, match="budget"):
        provider.generate(request, synthesis)
    assert calls == [True]


def test_live_payload_is_bounded_redacted_and_stored_false(monkeypatch) -> None:
    from market_os.adapters.openai_summary import OpenAIConfig, OpenAIResponsesSummaryProvider

    config = OpenAIConfig.from_mapping({
        **_approved_environment(),
        "MARKET_OS_OPENAI_MAX_REQUESTS": "2",
        "MARKET_OS_OPENAI_MAX_RETRIES": "1",
        "MARKET_OS_OPENAI_MAX_SPEND_USD": "0.05",
    })
    provider = OpenAIResponsesSummaryProvider(config)
    synthesis = _synthesis()
    payload = provider._request_payload(make_summary_request("Inspect", synthesis, "test"), synthesis)
    encoded = json.dumps(payload)
    assert payload["store"] is False
    assert "synthetic-test-key" not in encoded
    assert "synthetic-test-key" not in repr(config)
    assert "OPENAI_API_KEY" not in encoded
    assert len(encoded.encode()) <= config.max_input_bytes


def test_missing_paper_only_acknowledgement_fails_closed(monkeypatch) -> None:
    from market_os.adapters.openai_summary import OpenAIConfig, OpenAIConfigError

    config = _approved_environment()
    del config["MARKET_OS_PAPER_ONLY"]
    with pytest.raises(OpenAIConfigError, match="paper-only"):
        OpenAIConfig.from_mapping(config)


def test_transient_retry_is_bounded(monkeypatch) -> None:
    from market_os.adapters.openai_summary import OpenAIConfig, OpenAIRequestError, OpenAIResponsesSummaryProvider

    config = OpenAIConfig.from_mapping({
        **_approved_environment(),
        "MARKET_OS_OPENAI_MAX_REQUESTS": "2",
        "MARKET_OS_OPENAI_MAX_RETRIES": "1",
        "MARKET_OS_OPENAI_MAX_SPEND_USD": "0.05",
    })
    provider = OpenAIResponsesSummaryProvider(config)
    attempts = []

    def fail(*_args, **_kwargs):
        attempts.append(True)
        raise urllib.error.HTTPError("https://api.openai.com/v1/responses", 503, "synthetic", {}, None)

    import urllib.error
    monkeypatch.setattr(provider, "_post", fail)
    synthesis = _synthesis()
    with pytest.raises(OpenAIRequestError, match="HTTP 503"):
        provider.generate(make_summary_request("Inspect", synthesis, "test"), synthesis)
    assert len(attempts) == 2
