"""Bounded, fixture-first BTC public connectivity adapters.

This module has no execution authority.  Offline parsing is the default; live
transport is available only through explicit probe calls with bounded budgets.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import http.client
import json
import math
from pathlib import Path
import socket
import time
from typing import Any, Callable, Mapping, Protocol
from urllib.parse import urlencode, urlsplit
import urllib.error
import urllib.request

from .btc_history import HistoryError, parse_kline_row
from .btc_paper import BTC_SYMBOL, ClosedCandle


CONNECTIVITY_API_VERSION = "market-os.u3-api-connectivity.v1"
BINANCE_PROVIDER = "binance_public"
BINANCE_HOST = "data-api.binance.vision"
BINANCE_BASE_URL = f"https://{BINANCE_HOST}"
BINANCE_TICKER_PATH = "/api/v3/ticker/price"
BINANCE_KLINE_PATH = "/api/v3/klines"
BINANCE_ALLOWED_PATHS = frozenset({BINANCE_TICKER_PATH, BINANCE_KLINE_PATH})
TYPESAFE_PROVIDER = "typesafe"
TYPESAFE_HOST = "api.typesafe.ai"
TYPESAFE_BASE_URL = f"https://{TYPESAFE_HOST}"
TYPESAFE_SYSTEM_ONE_PATH = "/v1/systemone"
JEV_QUESTION_VERSION = "btc.connectivity.synthetic-descriptive.v1"
JEV_SEMANTIC_BOUNDARY = "descriptive_experimental_assessment"
JEV_MODEL_VERSIONS = frozenset({"jev-1.14.0", "jev-1.13.0"})
MAX_BINANCE_RESPONSE_BYTES = 256 * 1024
MAX_TYPESAFE_RESPONSE_BYTES = 256 * 1024
MAX_BINANCE_ATTEMPTS = 3
MAX_RETRY_AFTER_SECONDS = 60.0
JEV_MAX_SPEND_USD = 0.05
JEV_INPUT_COST_PER_MILLION = 0.042


def _json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha(value: Any) -> str:
    return _sha_bytes(_json(value))


def _utc(value: str, field_name: str) -> datetime:
    if not isinstance(value, str):
        raise ConnectivityError("invalid_timestamp", f"{field_name} must be an ISO-8601 UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ConnectivityError("invalid_timestamp", f"{field_name} must be an ISO-8601 UTC timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(None):
        raise ConnectivityError("invalid_timestamp", f"{field_name} must be an ISO-8601 UTC timestamp")
    return parsed


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _finite_decimal(value: Any, field_name: str, *, positive: bool = False) -> Decimal:
    if isinstance(value, bool):
        raise ConnectivityError("invalid_payload", f"{field_name} must be a decimal string")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ConnectivityError("invalid_payload", f"{field_name} must be a decimal string") from exc
    if not result.is_finite() or (positive and result <= 0) or (not positive and result < 0):
        raise ConnectivityError("invalid_payload", f"{field_name} is outside its valid range")
    return result


class ConnectivityError(ValueError):
    """Safe, categorized provider or contract failure."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        provider: str | None = None,
        status: int | None = None,
        retryable: bool = False,
        retry_after: float | None = None,
        attempts: int = 0,
    ) -> None:
        self.code = code
        self.provider = provider
        self.status = status
        self.retryable = retryable
        self.retry_after = retry_after
        self.attempts = attempts
        super().__init__(message)


@dataclass(frozen=True)
class TimeoutConfig:
    connect_seconds: float = 5.0
    read_seconds: float = 10.0

    def __post_init__(self) -> None:
        if not all(math.isfinite(value) and 0 < value <= 30 for value in (self.connect_seconds, self.read_seconds)):
            raise ValueError("connect and read timeouts must be in (0, 30]")


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: dict[str, str]
    body: bytes
    received_at: str


class HttpTransport(Protocol):
    def request(self, method: str, url: str, *, headers: Mapping[str, str], body: bytes | None, timeout: TimeoutConfig, max_bytes: int) -> HttpResponse: ...


class _BoundedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, *, read_timeout: float, **kwargs: Any) -> None:
        self._read_timeout = read_timeout
        super().__init__(host, **kwargs)

    def connect(self) -> None:
        super().connect()
        if self.sock is not None:
            self.sock.settimeout(self._read_timeout)


class _BoundedHTTPSHandler(urllib.request.HTTPSHandler):
    def __init__(self, read_timeout: float) -> None:
        super().__init__()
        self._read_timeout = read_timeout

    def https_open(self, request: urllib.request.Request):
        return self.do_open(
            lambda host, **kwargs: _BoundedHTTPSConnection(host, read_timeout=self._read_timeout, **kwargs),
            request,
        )


class UrllibTransport:
    """Stdlib urllib HTTPS transport with literal allowlists and no redirects."""

    def request(self, method: str, url: str, *, headers: Mapping[str, str], body: bytes | None, timeout: TimeoutConfig, max_bytes: int) -> HttpResponse:
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname not in {BINANCE_HOST, TYPESAFE_HOST}:
            raise ConnectivityError("endpoint_not_allowed", "HTTPS endpoint host is not allowlisted")
        allowed_methods = {BINANCE_HOST: {"GET"}, TYPESAFE_HOST: {"POST"}}[parsed.hostname]
        if method not in allowed_methods:
            raise ConnectivityError("method_not_allowed", "provider method is not allowlisted")
        allowed_paths = {BINANCE_HOST: BINANCE_ALLOWED_PATHS, TYPESAFE_HOST: {TYPESAFE_SYSTEM_ONE_PATH}}[parsed.hostname]
        if parsed.path not in allowed_paths:
            raise ConnectivityError("endpoint_not_allowed", "provider path is not allowlisted")
        request = urllib.request.Request(url, data=body, headers=dict(headers), method=method)

        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *_args: Any, **_kwargs: Any) -> None:
                return None

        opener = urllib.request.build_opener(NoRedirect, _BoundedHTTPSHandler(timeout.read_seconds))
        try:
            # urllib exposes one operation timeout; keep it bounded by the
            # configured connect/read envelope and bound the response body.
            with opener.open(request, timeout=min(30.0, timeout.connect_seconds + timeout.read_seconds)) as response:
                raw = response.read(max_bytes + 1)
                status = response.status
                response_headers = {key: value for key, value in response.headers.items()}
            if len(raw) > max_bytes:
                raise ConnectivityError("response_too_large", "provider response exceeds the bounded byte limit")
            return HttpResponse(status, response_headers, raw, _iso_now())
        except urllib.error.HTTPError as response:
            raw = response.read(max_bytes + 1)
            if len(raw) > max_bytes:
                raise ConnectivityError("response_too_large", "provider response exceeds the bounded byte limit")
            return HttpResponse(response.code, {key: value for key, value in response.headers.items()}, raw, _iso_now())
        except (TimeoutError, socket.timeout) as exc:
            raise ConnectivityError("timeout", "provider request timed out", retryable=True) from exc
        except (urllib.error.URLError, OSError) as exc:
            raise ConnectivityError("transport", "provider connection failed", retryable=True) from exc


@dataclass(frozen=True)
class BinanceTicker:
    symbol: str
    price: str
    received_at: str
    response_fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BinanceKlineResult:
    candles: tuple[ClosedCandle, ...]
    gaps: tuple[tuple[int, int], ...]
    excluded_open_candles: int
    received_at: str
    response_fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "candles": [asdict(item) for item in self.candles],
            "gaps": [list(item) for item in self.gaps],
            "excluded_open_candles": self.excluded_open_candles,
            "received_at": self.received_at,
            "response_fingerprint": self.response_fingerprint,
        }


def _load_json(raw: bytes, label: str) -> Any:
    try:
        return json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ConnectivityError("invalid_response", f"{label} response is not valid UTF-8 JSON") from exc


def parse_ticker_payload(raw: bytes, *, received_at: str) -> BinanceTicker:
    _utc(received_at, "received_at")
    payload = _load_json(raw, "ticker")
    if not isinstance(payload, dict) or set(payload) != {"symbol", "price"}:
        raise ConnectivityError("invalid_ticker", "ticker response must contain exactly symbol and price")
    if payload["symbol"] != BTC_SYMBOL:
        raise ConnectivityError("invalid_ticker", "ticker symbol must be BTCUSDT")
    price = _finite_decimal(payload["price"], "ticker.price", positive=True)
    if not isinstance(payload["price"], str):
        raise ConnectivityError("invalid_ticker", "ticker.price must preserve the provider decimal string")
    return BinanceTicker(BTC_SYMBOL, format(price, "f"), received_at, _sha_bytes(raw))


def _epoch_ms(value: datetime) -> int:
    return int(value.timestamp() * 1000)


def parse_kline_payload(raw: bytes, *, received_at: str) -> BinanceKlineResult:
    received = _utc(received_at, "received_at")
    payload = _load_json(raw, "kline")
    if not isinstance(payload, list) or not payload:
        raise ConnectivityError("invalid_kline", "kline response must be a non-empty array")
    finalized: list[tuple[ClosedCandle, int]] = []
    seen: set[int] = set()
    excluded = 0
    as_of_ms = _epoch_ms(received)
    for row in payload:
        if not isinstance(row, list) or len(row) != 12:
            raise ConnectivityError("invalid_kline", "kline rows must contain exactly 12 fields")
        open_ms = row[0]
        if isinstance(open_ms, bool) or not isinstance(open_ms, int):
            raise ConnectivityError("invalid_kline", "kline open timestamp must be integer milliseconds")
        if open_ms in seen:
            raise ConnectivityError("duplicate_kline", "kline response contains a duplicate candle")
        seen.add(open_ms)
        try:
            candle, _ancillary = parse_kline_row(row, received_at=received_at, as_of_ms=as_of_ms)
        except HistoryError as exc:
            if exc.code == "not_closed":
                excluded += 1
                continue
            message = str(exc)
            if "aligned" in message:
                message = "invalid close timestamp or aligned-minute boundary"
            elif "outside its valid range" in message or "OHLC range" in message:
                message = "invalid OHLCV values"
            raise ConnectivityError("invalid_kline", message) from exc
        except (TypeError, ValueError) as exc:
            raise ConnectivityError("invalid_kline", str(exc)) from exc
        finalized.append((candle, open_ms))
    opens = [open_ms for _candle, open_ms in finalized]
    if opens != sorted(opens):
        raise ConnectivityError("kline_ordering", "kline ordering is not ascending")
    gaps = tuple((previous + 60_000, current) for previous, current in zip(opens, opens[1:]) if current != previous + 60_000)
    if gaps:
        raise ConnectivityError("kline_gap", "kline gap detected in finalized response")
    return BinanceKlineResult(tuple(candle for candle, _open_ms in finalized), gaps, excluded, received_at, _sha_bytes(raw))


SYNTHETIC_JEV_REQUEST: dict[str, Any] = {
    "model": "jev-1.14.0",
    "state": {
        "symbol": BTC_SYMBOL,
        "note": "synthetic connectivity fixture; descriptive assessment only",
        "past_5m_return": 0.0021,
        "rsi_14": 58.2,
        "volume_zscore_30m": 1.25,
    },
    "questions": {
        "descriptive_regime": {
            "type": "choice",
            "instructions": "Classify observed momentum context only; do not predict future prices.",
            "criteria": {
                "positive_momentum": "Recent observed momentum is positive",
                "negative_momentum": "Recent observed momentum is negative",
                "mixed_or_uncertain": "Signals are mixed or insufficient",
            },
        },
        "evidence_is_limited": {
            "type": "noul",
            "instructions": "The supplied synthetic indicators alone are insufficient to assert a future BTC move.",
        },
        "context_score": {
            "type": "score",
            "instructions": "Rate the descriptive strength of the observed momentum context.",
            "criteria": ["Weak observed context", "Mixed observed context", "Strong observed context"],
        },
    },
}


@dataclass(frozen=True)
class JevRequest:
    model: str
    question_version: str
    payload: dict[str, Any]
    fingerprint: str


@dataclass(frozen=True)
class JevAssessment:
    provider: str
    requested_model: str
    resolved_model: str
    question_version: str
    request_fingerprint: str
    response_fingerprint: str | None
    request_started_at: str
    response_received_at: str
    latency_ms: int | None
    answers: dict[str, dict[str, Any]]
    usage: dict[str, int | None]
    cost_usd: float | None
    validation_status: str
    abstention: bool
    semantic_boundary: str = JEV_SEMANTIC_BOUNDARY
    failure: dict[str, str] | None = None

    def __post_init__(self) -> None:
        if self.provider != TYPESAFE_PROVIDER or self.question_version != JEV_QUESTION_VERSION:
            raise ValueError("unsupported Jev assessment identity")
        if self.resolved_model not in JEV_MODEL_VERSIONS:
            raise ValueError("unsupported Jev resolved model")
        for name, value in (("request_fingerprint", self.request_fingerprint), ("response_fingerprint", self.response_fingerprint)):
            if value is None:
                continue
            if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
                raise ValueError(f"{name} must be a lowercase SHA-256 fingerprint")
        started = _utc(self.request_started_at, "request_started_at")
        received = _utc(self.response_received_at, "response_received_at")
        if received < started:
            raise ValueError("response_received_at cannot precede request_started_at")
        if self.latency_ms is not None and (isinstance(self.latency_ms, bool) or self.latency_ms < 0):
            raise ValueError("latency_ms must be non-negative")
        if self.cost_usd is not None and (not math.isfinite(self.cost_usd) or self.cost_usd < 0):
            raise ValueError("cost_usd must be non-negative")
        if self.validation_status not in {"valid", "abstained", "invalid", "unavailable"}:
            raise ValueError("invalid Jev validation status")
        if self.semantic_boundary != JEV_SEMANTIC_BOUNDARY:
            raise ValueError("invalid Jev semantic boundary")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_jev_request(*, model: str = "jev-1.14.0") -> JevRequest:
    if model not in JEV_MODEL_VERSIONS:
        raise ConnectivityError("unsupported_model", "Jev probe requires a versioned supported model")
    payload = json.loads(json.dumps(SYNTHETIC_JEV_REQUEST))
    payload["model"] = model
    return JevRequest(model, JEV_QUESTION_VERSION, payload, _sha(payload))


def _probabilities(value: Any, field_name: str) -> dict[str, float]:
    if not isinstance(value, dict) or not value:
        raise ConnectivityError("invalid_jev_response", f"{field_name} probabilities must be an object")
    result: dict[str, float] = {}
    for key, raw in value.items():
        if not isinstance(key, (str, int)):
            raise ConnectivityError("invalid_jev_response", f"{field_name} probability labels are invalid")
        if isinstance(raw, bool):
            raise ConnectivityError("invalid_jev_response", f"{field_name} probabilities must be finite")
        try:
            parsed = float(raw)
        except (TypeError, ValueError) as exc:
            raise ConnectivityError("invalid_jev_response", f"{field_name} probabilities must be finite") from exc
        if not math.isfinite(parsed) or not 0 <= parsed <= 1:
            raise ConnectivityError("invalid_jev_response", f"{field_name} probabilities must be in [0,1]")
        result[str(key)] = parsed
    if not math.isclose(sum(result.values()), 1.0, abs_tol=1e-6):
        raise ConnectivityError("invalid_jev_response", f"{field_name} probabilities must sum to one")
    return result


def _answer(value: Any, question: str, *, allowed_options: set[str] | None = None, allowed_levels: set[str] | None = None) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("type") not in {"choice", "noul", "score"}:
        raise ConnectivityError("invalid_jev_response", f"answer {question} has an unsupported type")
    kind = value["type"]
    if kind == "choice":
        if set(value) != {"type", "choice", "probabilities", "confidence"}:
            raise ConnectivityError("invalid_jev_response", f"choice answer {question} has an invalid shape")
        probabilities = _probabilities(value["probabilities"], question)
        if allowed_options is not None and set(probabilities) != allowed_options:
            raise ConnectivityError("invalid_jev_response", f"choice answer {question} labels do not match the request")
        choice = value["choice"]
        if not isinstance(choice, str) or choice not in probabilities:
            raise ConnectivityError("invalid_jev_response", f"choice answer {question} has an unknown choice")
        if choice != max(probabilities, key=probabilities.get):
            raise ConnectivityError("invalid_jev_response", f"choice answer {question} is inconsistent")
        try:
            confidence = float(value["confidence"])
        except (TypeError, ValueError) as exc:
            raise ConnectivityError("invalid_jev_response", f"choice answer {question} confidence is invalid") from exc
        if not math.isfinite(confidence) or not 0 <= confidence <= 1:
            raise ConnectivityError("invalid_jev_response", f"choice answer {question} confidence is invalid")
        return {"type": kind, "choice": choice, "probabilities": probabilities, "confidence": confidence}
    if kind == "noul":
        if set(value) != {"type", "noul"}:
            raise ConnectivityError("invalid_jev_response", f"noul answer {question} has an invalid shape")
        try:
            noul = float(value["noul"])
        except (TypeError, ValueError) as exc:
            raise ConnectivityError("invalid_jev_response", f"noul answer {question} is invalid") from exc
        if not math.isfinite(noul) or not 0 <= noul <= 1:
            raise ConnectivityError("invalid_jev_response", f"noul answer {question} is invalid")
        return {"type": kind, "noul": noul}
    if set(value) != {"type", "score", "confidence", "legend", "probabilities"}:
        raise ConnectivityError("invalid_jev_response", f"score answer {question} has an invalid shape")
    try:
        score = float(value["score"])
        confidence = float(value["confidence"])
    except (TypeError, ValueError) as exc:
        raise ConnectivityError("invalid_jev_response", f"score answer {question} is invalid") from exc
    if not math.isfinite(score) or not math.isfinite(confidence) or not 0 <= confidence <= 1:
        raise ConnectivityError("invalid_jev_response", f"score answer {question} is invalid")
    probabilities = _probabilities(value["probabilities"], question)
    if allowed_levels is not None and set(probabilities) != allowed_levels:
        raise ConnectivityError("invalid_jev_response", f"score answer {question} levels do not match the request")
    if not isinstance(value["legend"], dict) or set(value["legend"]) != set(probabilities):
        raise ConnectivityError("invalid_jev_response", f"score answer {question} legend is inconsistent")
    try:
        level_values = [int(key) for key in probabilities]
    except (TypeError, ValueError) as exc:
        raise ConnectivityError("invalid_jev_response", f"score answer {question} levels are invalid") from exc
    if any(str(level) not in value["legend"] for level in level_values) or not level_values:
        raise ConnectivityError("invalid_jev_response", f"score answer {question} levels are invalid")
    if sorted(level_values) != list(range(len(level_values))) or not min(level_values) <= score <= max(level_values):
        raise ConnectivityError("invalid_jev_response", f"score answer {question} is outside its levels")
    expected_score = sum(level * probabilities[str(level)] for level in level_values)
    if not math.isclose(score, expected_score, abs_tol=1e-6):
        raise ConnectivityError("invalid_jev_response", f"score answer {question} is inconsistent")
    return {"type": kind, "score": score, "confidence": confidence, "legend": value["legend"], "probabilities": probabilities}


def parse_jev_response(
    payload: Any,
    request: JevRequest,
    *,
    received_at: str | None = None,
    request_started_at: str | None = None,
    latency_ms: int | None = None,
    cost_usd: float | None = None,
    estimate_cost: bool = False,
    raw_bytes: bytes | None = None,
) -> JevAssessment:
    if not isinstance(payload, dict) or set(payload) != {"model", "answers", "usage"}:
        raise ConnectivityError("invalid_jev_response", "Jev response must contain exactly model, answers, and usage")
    model = payload["model"]
    if model not in JEV_MODEL_VERSIONS:
        raise ConnectivityError("unsupported_model", "Jev response model is not a supported version")
    if not isinstance(payload["answers"], dict) or set(payload["answers"]) != set(request.payload["questions"]):
        raise ConnectivityError("invalid_jev_response", "Jev answers do not match the fixed question set")
    usage = payload["usage"]
    if not isinstance(usage, dict) or set(usage) != {"input_tokens", "output_tokens"}:
        raise ConnectivityError("invalid_jev_response", "Jev usage has an invalid shape")
    normalized_usage: dict[str, int | None] = {}
    for name in ("input_tokens", "output_tokens"):
        value = usage[name]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ConnectivityError("invalid_jev_response", f"usage.{name} is invalid")
        normalized_usage[name] = value
    questions = request.payload["questions"]
    answers = {
        question: _answer(
            value,
            question,
            allowed_options=set(questions[question]["criteria"]) if questions[question]["type"] == "choice" else None,
            allowed_levels={str(index) for index in range(len(questions[question]["criteria"]))} if questions[question]["type"] == "score" else None,
        )
        for question, value in payload["answers"].items()
    }
    response_time = received_at or _iso_now()
    started_time = request_started_at or response_time
    calculated_cost = cost_usd
    if estimate_cost and calculated_cost is None and normalized_usage["input_tokens"] is not None:
        calculated_cost = normalized_usage["input_tokens"] * JEV_INPUT_COST_PER_MILLION / 1_000_000
    raw = raw_bytes if raw_bytes is not None else _json(payload)
    return JevAssessment(
        TYPESAFE_PROVIDER,
        request.model,
        model,
        request.question_version,
        request.fingerprint,
        _sha_bytes(raw),
        started_time,
        response_time,
        latency_ms,
        answers,
        normalized_usage,
        calculated_cost,
        "valid",
        False,
    )


def _retry_after(headers: Mapping[str, str]) -> float | None:
    value = next((raw for key, raw in headers.items() if key.lower() == "retry-after"), None)
    if value is None:
        return None
    try:
        result = float(value)
    except ValueError:
        return None
    return max(0.0, result)


def classify_provider_status(provider: str, status: int, headers: Mapping[str, str] | None = None) -> ConnectivityError:
    retry_after = _retry_after(headers or {})
    if status in {401, 403}:
        code = "auth" if provider == TYPESAFE_PROVIDER else "forbidden"
        return ConnectivityError(code, f"{provider} rejected the request", provider=provider, status=status)
    if status == 451:
        return ConnectivityError("regional_restriction", f"{provider} request is regionally restricted", provider=provider, status=status)
    if status == 429:
        return ConnectivityError("rate_limited", f"{provider} rate limit reached", provider=provider, status=status, retryable=True, retry_after=retry_after)
    if 500 <= status <= 599:
        return ConnectivityError("server_error", f"{provider} returned a server error", provider=provider, status=status, retryable=True, retry_after=retry_after)
    if 400 <= status <= 499:
        return ConnectivityError("invalid_request", f"{provider} rejected the request", provider=provider, status=status)
    return ConnectivityError("unexpected_status", f"{provider} returned unexpected HTTP status", provider=provider, status=status)


def _request_with_retries(
    transport: HttpTransport,
    provider: str,
    method: str,
    url: str,
    *,
    headers: Mapping[str, str],
    body: bytes | None,
    timeout: TimeoutConfig,
    max_bytes: int,
    attempts: int,
    wait: Callable[[float], None],
) -> tuple[HttpResponse, int]:
    if attempts < 1:
        raise ValueError("attempts must be positive")
    last_error: ConnectivityError | None = None
    for attempt in range(attempts):
        try:
            response = transport.request(method, url, headers=headers, body=body, timeout=timeout, max_bytes=max_bytes)
        except (TimeoutError, OSError) as exc:
            error = ConnectivityError(
                "timeout" if isinstance(exc, TimeoutError) else "transport",
                "provider request failed",
                provider=provider,
                retryable=True,
            )
            error.attempts = attempt + 1
            last_error = error
            if attempt + 1 >= attempts:
                raise error from exc
            wait(min(0.5 * (2**attempt), MAX_RETRY_AFTER_SECONDS))
            continue
        except ConnectivityError as exc:
            exc.attempts = attempt + 1
            last_error = exc
            if not exc.retryable or attempt + 1 >= attempts:
                raise
            wait(min(exc.retry_after or 0.5, MAX_RETRY_AFTER_SECONDS))
            continue
        if 200 <= response.status < 300:
            return response, attempt + 1
        error = classify_provider_status(provider, response.status, response.headers)
        last_error = error
        if not error.retryable or attempt + 1 >= attempts:
            raise error
        delay = error.retry_after
        if delay is None:
            delay = min(0.5 * (2**attempt), MAX_RETRY_AFTER_SECONDS)
        if delay > MAX_RETRY_AFTER_SECONDS:
            raise ConnectivityError("retry_after_exceeds_policy", "provider retry delay exceeds the local cap", provider=provider, retry_after=delay)
        wait(delay)
    raise last_error or ConnectivityError("retry_exhausted", "provider retry budget exhausted", provider=provider)


class BinancePublicAdapter:
    """Public Binance Spot ticker/kline adapter; no auth or order endpoints."""

    def __init__(self, transport: HttpTransport | None = None, *, timeout: TimeoutConfig = TimeoutConfig(), wait: Callable[[float], None] = time.sleep) -> None:
        self.transport = transport or UrllibTransport()
        self.timeout = timeout
        self.wait = wait

    @staticmethod
    def _url(path: str, params: Mapping[str, str]) -> str:
        if path not in BINANCE_ALLOWED_PATHS:
            raise ConnectivityError("endpoint_not_allowed", "Binance path is not allowlisted", provider=BINANCE_PROVIDER)
        if path == BINANCE_TICKER_PATH and set(params) != {"symbol"}:
            raise ConnectivityError("invalid_request", "ticker request parameters are not allowlisted", provider=BINANCE_PROVIDER)
        if path == BINANCE_KLINE_PATH and set(params) != {"symbol", "interval", "limit"}:
            raise ConnectivityError("invalid_request", "kline request parameters are not allowlisted", provider=BINANCE_PROVIDER)
        if params.get("symbol") != BTC_SYMBOL:
            raise ConnectivityError("invalid_request", "Binance adapter supports BTCUSDT only", provider=BINANCE_PROVIDER)
        if path == BINANCE_KLINE_PATH and params.get("interval") != "1m":
            raise ConnectivityError("invalid_request", "Binance adapter supports 1m klines only", provider=BINANCE_PROVIDER)
        return f"{BINANCE_BASE_URL}{path}?{urlencode(params)}"

    def ticker(self) -> tuple[BinanceTicker, int]:
        url = self._url(BINANCE_TICKER_PATH, {"symbol": BTC_SYMBOL})
        response, attempts = _request_with_retries(
            self.transport,
            BINANCE_PROVIDER,
            "GET",
            url,
            headers={"Accept": "application/json"},
            body=None,
            timeout=self.timeout,
            max_bytes=MAX_BINANCE_RESPONSE_BYTES,
            attempts=MAX_BINANCE_ATTEMPTS,
            wait=self.wait,
        )
        return parse_ticker_payload(response.body, received_at=response.received_at), attempts

    def klines(self, *, limit: int = 100) -> tuple[BinanceKlineResult, int]:
        if not 1 <= limit <= 1000:
            raise ConnectivityError("invalid_request", "kline limit must be between 1 and 1000", provider=BINANCE_PROVIDER)
        url = self._url(BINANCE_KLINE_PATH, {"symbol": BTC_SYMBOL, "interval": "1m", "limit": str(limit)})
        response, attempts = _request_with_retries(
            self.transport,
            BINANCE_PROVIDER,
            "GET",
            url,
            headers={"Accept": "application/json"},
            body=None,
            timeout=self.timeout,
            max_bytes=MAX_BINANCE_RESPONSE_BYTES,
            attempts=MAX_BINANCE_ATTEMPTS,
            wait=self.wait,
        )
        return parse_kline_payload(response.body, received_at=response.received_at), attempts


class FixtureConnectivityAdapter:
    """Deterministic adapter for offline connectivity checks."""

    def __init__(self, *, ticker_payload: bytes, kline_payload: bytes, jev_response: dict[str, Any], recorded_cases: dict[str, dict[str, Any]] | None = None) -> None:
        self.ticker_payload = ticker_payload
        self.kline_payload = kline_payload
        self.jev_response = jev_response
        self.recorded_cases = recorded_cases or {}

    @classmethod
    def from_paths(cls, ticker_path: str | Path, kline_path: str | Path, jev_path: str | Path) -> "FixtureConnectivityAdapter":
        return cls(
            ticker_payload=Path(ticker_path).read_bytes(),
            kline_payload=Path(kline_path).read_bytes(),
            jev_response=json.loads(Path(jev_path).read_text(encoding="utf-8")),
        )

    @classmethod
    def from_recorded_cases(cls, ticker_path: str | Path, kline_path: str | Path, cases_path: str | Path) -> "FixtureConnectivityAdapter":
        fixture = json.loads(Path(cases_path).read_text(encoding="utf-8"))
        if not isinstance(fixture, dict) or fixture.get("schema") != "market-os.u3-api-recorded-jev.v1":
            raise ConnectivityError("invalid_fixture", "recorded Jev fixture schema is unsupported")
        cases = fixture.get("cases")
        if not isinstance(cases, list):
            raise ConnectivityError("invalid_fixture", "recorded Jev fixture cases must be an array")
        normalized = {
            str(case["case_id"]): case
            for case in cases
            if isinstance(case, dict) and isinstance(case.get("case_id"), str)
        }
        valid = next((case.get("response") for case in cases if isinstance(case, dict) and case.get("kind") == "valid"), None)
        if not isinstance(valid, dict):
            raise ConnectivityError("invalid_fixture", "recorded Jev fixture needs a valid case")
        return cls(
            ticker_payload=Path(ticker_path).read_bytes(),
            kline_payload=Path(kline_path).read_bytes(),
            jev_response=valid,
            recorded_cases=normalized,
        )

    def ticker(self) -> BinanceTicker:
        return parse_ticker_payload(self.ticker_payload, received_at="2026-01-01T00:02:00+00:00")

    def klines(self) -> BinanceKlineResult:
        return parse_kline_payload(self.kline_payload, received_at="2026-01-01T00:03:00+00:00")

    def jev(self) -> JevAssessment:
        return parse_jev_response(self.jev_response, build_jev_request(), received_at="2026-01-01T00:04:00+00:00")

    def evaluate_jev(self, case_id: str) -> JevAssessment:
        case = self.recorded_cases.get(case_id)
        if case is None:
            raise ConnectivityError("invalid_fixture", f"recorded Jev case is missing: {case_id}")
        request = build_jev_request()
        timestamp = "2026-01-01T00:04:00+00:00"
        if case.get("kind") == "unavailable":
            return JevAssessment(
                TYPESAFE_PROVIDER,
                request.model,
                request.model,
                request.question_version,
                request.fingerprint,
                None,
                timestamp,
                timestamp,
                None,
                {},
                {"input_tokens": None, "output_tokens": None},
                None,
                "unavailable",
                True,
                failure={"code": "provider_unavailable", "reason": "recorded provider is unavailable"},
            )
        response = case.get("response")
        raw = _json(response)
        try:
            parsed = parse_jev_response(response, request, received_at=timestamp, raw_bytes=raw)
        except ConnectivityError as exc:
            return JevAssessment(
                TYPESAFE_PROVIDER,
                request.model,
                request.model,
                request.question_version,
                request.fingerprint,
                _sha_bytes(raw),
                timestamp,
                timestamp,
                None,
                {},
                {"input_tokens": None, "output_tokens": None},
                None,
                "invalid",
                True,
                failure={"code": exc.code, "reason": str(exc)},
            )
        if case.get("kind") == "abstaining":
            return replace(
                parsed,
                validation_status="abstained",
                abstention=True,
                failure={"code": "explicit_abstention", "reason": "recorded case abstains"},
            )
        return parsed


@dataclass
class JevLiveBudget:
    max_requests: int = 1
    max_spend_usd: float = JEV_MAX_SPEND_USD
    requests: int = 0
    reserved_spend_usd: float = 0.0

    def reserve(self, payload: bytes) -> None:
        if self.max_requests != 1 or self.requests >= self.max_requests:
            raise ConnectivityError("request_budget_exhausted", "Jev probe permits exactly one request", provider=TYPESAFE_PROVIDER)
        estimated = len(payload) / 4 * JEV_INPUT_COST_PER_MILLION / 1_000_000
        if not math.isfinite(estimated) or estimated > self.max_spend_usd or estimated > JEV_MAX_SPEND_USD:
            raise ConnectivityError("budget_exceeded", "Jev request exceeds the strict spend ceiling", provider=TYPESAFE_PROVIDER)
        self.reserved_spend_usd = estimated


class TypeSafeHttpAdapter:
    def __init__(self, transport: HttpTransport | None = None, *, timeout: TimeoutConfig = TimeoutConfig(), budget: JevLiveBudget | None = None) -> None:
        self.transport = transport or UrllibTransport()
        self.timeout = timeout
        self.budget = budget or JevLiveBudget()

    def assess(self, *, api_key: str, request: JevRequest, allow_live_probe: bool, paper_only: bool) -> tuple[JevAssessment, int]:
        if not allow_live_probe:
            raise ConnectivityError("live_probe_required", "Jev live probe requires --allow-live-probe", provider=TYPESAFE_PROVIDER)
        if not paper_only:
            raise ConnectivityError("paper_only_required", "Jev live probe requires paper-only mode", provider=TYPESAFE_PROVIDER)
        if not isinstance(api_key, str) or not api_key.strip():
            raise ConnectivityError("missing_credential", "TYPESAFE_API_KEY is required for the live Jev probe", provider=TYPESAFE_PROVIDER)
        payload = _json(request.payload)
        self.budget.reserve(payload)
        self.budget.requests += 1
        started_at = _iso_now()
        response, attempts = _request_with_retries(
            self.transport,
            TYPESAFE_PROVIDER,
            "POST",
            f"{TYPESAFE_BASE_URL}{TYPESAFE_SYSTEM_ONE_PATH}",
            headers={"Accept": "application/json", "Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
            body=payload,
            timeout=self.timeout,
            max_bytes=MAX_TYPESAFE_RESPONSE_BYTES,
            attempts=1,
            wait=lambda _seconds: None,
        )
        received_at = response.received_at
        latency_ms = max(0, int((_utc(received_at, "response_received_at") - _utc(started_at, "request_started_at")).total_seconds() * 1000))
        return parse_jev_response(
            _load_json(response.body, "Jev"),
            request,
            request_started_at=started_at,
            received_at=received_at,
            latency_ms=latency_ms,
            estimate_cost=True,
            raw_bytes=response.body,
        ), attempts


@dataclass(frozen=True)
class ProbeRecord:
    probe_id: str
    mode: str
    provider: str
    operation: str
    endpoint: str
    status: str
    started_at: str
    finished_at: str
    request_count: int
    retry_count: int
    request_fingerprint: str | None
    response_fingerprint: str | None
    result: dict[str, Any] | None
    error: dict[str, Any] | None
    credential_status: str
    cost_status: str
    paper_only: bool
    api_version: str = CONNECTIVITY_API_VERSION

    def __post_init__(self) -> None:
        if not self.probe_id or not self.provider or not self.endpoint or self.request_count < 0 or self.retry_count < 0:
            raise ValueError("invalid connectivity probe identity or counters")
        _utc(self.started_at, "started_at")
        _utc(self.finished_at, "finished_at")
        if self.mode not in {"offline", "binance-public", "jev-live"}:
            raise ValueError("invalid connectivity probe mode")
        if self.api_version != CONNECTIVITY_API_VERSION:
            raise ValueError("unsupported connectivity API version")
        if self.paper_only is not True:
            raise ValueError("connectivity probes are paper-only")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ConnectivityStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.runs = self.root / "runs"
        self.runs.mkdir(parents=True, exist_ok=True)

    def _directory(self, probe_id: str) -> Path:
        path = (self.runs / probe_id).resolve()
        if not path.is_relative_to(self.runs.resolve()):
            raise ValueError("invalid connectivity probe ID")
        return path

    @staticmethod
    def _write(path: Path, value: Any) -> dict[str, Any]:
        raw = _json(value)
        if path.exists() and path.read_bytes() != raw:
            raise ValueError(f"immutable connectivity artifact collision: {path.name}")
        if not path.exists():
            path.write_bytes(raw)
        return {"path": path.name, "sha256": _sha_bytes(raw), "size_bytes": len(raw)}

    def persist(self, record: ProbeRecord) -> dict[str, Any]:
        directory = self._directory(record.probe_id)
        directory.mkdir(parents=True, exist_ok=True)
        result_artifact = self._write(directory / "result.json", record.result or {})
        manifest = record.to_dict()
        manifest["result"] = None
        artifact_entry = {"kind": "result", **result_artifact}
        manifest["artifacts"] = [artifact_entry]
        manifest["replay_fingerprint"] = _sha({"record": manifest, "result": artifact_entry})
        self._write(directory / "manifest.json", manifest)
        return manifest

    def inspect(self, probe_id: str, resource: str = "manifest") -> dict[str, Any]:
        directory = self._directory(probe_id)
        manifest_path = directory / "manifest.json"
        if not manifest_path.is_file():
            raise KeyError(probe_id)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if resource == "manifest":
            return manifest
        if resource == "result":
            return json.loads((directory / "result.json").read_text(encoding="utf-8"))
        if resource == "fingerprints":
            return {key: manifest.get(key) for key in ("request_fingerprint", "response_fingerprint", "replay_fingerprint")}
        if resource == "replay":
            result_artifact = manifest["artifacts"][0]
            raw = (directory / result_artifact["path"]).read_bytes()
            if _sha_bytes(raw) != result_artifact["sha256"]:
                raise ValueError("connectivity result fingerprint mismatch")
            expected = _sha({"record": {key: value for key, value in manifest.items() if key != "replay_fingerprint"}, "result": result_artifact})
            if expected != manifest["replay_fingerprint"]:
                raise ValueError("connectivity replay fingerprint mismatch")
            return {"probe_id": probe_id, "replayed": True, "network_requests": 0, "provider_requests": 0, "replay_fingerprint": expected}
        raise KeyError(resource)


def _probe_id(mode: str, operation: str, request_fingerprint: str | None) -> str:
    return f"connectivity-{_sha({"mode": mode, "operation": operation, "request": request_fingerprint})[:20]}"


def offline_probe(adapter: FixtureConnectivityAdapter) -> ProbeRecord:
    started = "2026-01-01T00:00:00.000+00:00"
    ticker = adapter.ticker()
    klines = adapter.klines()
    jev = adapter.jev()
    finished = started
    request_fingerprint = _sha({"ticker": ticker.symbol, "klines": klines.response_fingerprint, "jev": jev.request_fingerprint})
    return ProbeRecord(
        _probe_id("offline", "all", request_fingerprint),
        "offline",
        "fixture",
        "all",
        "fixture://btc-connectivity",
        "valid",
        started,
        finished,
        0,
        0,
        request_fingerprint,
        _sha({"ticker": ticker.to_dict(), "klines": klines.to_dict(), "jev": jev.to_dict()}),
        {"ticker": ticker.to_dict(), "klines": klines.to_dict(), "jev": jev.to_dict(), "execution": {"action": "none", "paper_only": True}},
        None,
        "not-required",
        "not-applicable-offline",
        True,
    )


def binance_probe(adapter: BinancePublicAdapter, operation: str) -> ProbeRecord:
    if operation not in {"ticker", "kline"}:
        raise ConnectivityError("invalid_operation", "Binance operation must be ticker or kline", provider=BINANCE_PROVIDER)
    started = _iso_now()
    try:
        if operation == "ticker":
            result, attempts = adapter.ticker()
            normalized = result.to_dict()
            response_fp = result.response_fingerprint
        else:
            result, attempts = adapter.klines()
            normalized = result.to_dict()
            response_fp = result.response_fingerprint
        finished = _iso_now()
        request_fp = _sha({"provider": BINANCE_PROVIDER, "operation": operation, "symbol": BTC_SYMBOL, "interval": "1m"})
        endpoint = f"{BINANCE_BASE_URL}{BINANCE_TICKER_PATH if operation == 'ticker' else BINANCE_KLINE_PATH}"
        return ProbeRecord(_probe_id("binance-public", operation, request_fp), "binance-public", BINANCE_PROVIDER, operation, endpoint, "valid", started, finished, attempts, max(0, attempts - 1), request_fp, response_fp, {**normalized, "execution": {"action": "none", "paper_only": True}}, None, "not-required", "not-applicable-public-read", True)
    except ConnectivityError as exc:
        finished = _iso_now()
        request_fp = _sha({"provider": BINANCE_PROVIDER, "operation": operation, "symbol": BTC_SYMBOL, "interval": "1m"})
        endpoint = f"{BINANCE_BASE_URL}{BINANCE_TICKER_PATH if operation == 'ticker' else BINANCE_KLINE_PATH}"
        return ProbeRecord(_probe_id("binance-public", operation, request_fp), "binance-public", BINANCE_PROVIDER, operation, endpoint, "failed", started, finished, max(1, exc.attempts), max(0, exc.attempts - 1), request_fp, None, None, {"code": exc.code, "message": str(exc), "status": exc.status, "retryable": exc.retryable, "retry_after": exc.retry_after}, "not-required", "not-applicable-public-read", True)


def jev_probe(adapter: TypeSafeHttpAdapter, *, model: str, api_key: str | None, allow_live_probe: bool, paper_only: bool, max_spend_usd: float) -> ProbeRecord:
    if max_spend_usd != JEV_MAX_SPEND_USD:
        raise ConnectivityError("budget_required", f"Jev probe requires exact max spend ${JEV_MAX_SPEND_USD:.2f}", provider=TYPESAFE_PROVIDER)
    if not allow_live_probe:
        raise ConnectivityError("live_probe_required", "Jev live probe requires --allow-live-probe", provider=TYPESAFE_PROVIDER)
    if not paper_only:
        raise ConnectivityError("paper_only_required", "Jev live probe requires paper-only mode", provider=TYPESAFE_PROVIDER)
    if not api_key or not api_key.strip():
        raise ConnectivityError("missing_credential", "TYPESAFE_API_KEY is required for the live Jev probe", provider=TYPESAFE_PROVIDER)
    request = build_jev_request(model=model)
    started = _iso_now()
    try:
        assessment, attempts = adapter.assess(api_key=api_key or "", request=request, allow_live_probe=allow_live_probe, paper_only=paper_only)
        finished = _iso_now()
        return ProbeRecord(_probe_id("jev-live", "systemone", request.fingerprint), "jev-live", TYPESAFE_PROVIDER, "systemone", f"{TYPESAFE_BASE_URL}{TYPESAFE_SYSTEM_ONE_PATH}", "valid", started, finished, attempts, 0, request.fingerprint, assessment.response_fingerprint, {**assessment.to_dict(), "execution": {"action": "none", "paper_only": True}}, None, "present", f"reserved-up-to-${max_spend_usd:.2f}", True)
    except ConnectivityError as exc:
        finished = _iso_now()
        return ProbeRecord(_probe_id("jev-live", "systemone", request.fingerprint), "jev-live", TYPESAFE_PROVIDER, "systemone", f"{TYPESAFE_BASE_URL}{TYPESAFE_SYSTEM_ONE_PATH}", "failed", started, finished, adapter.budget.requests, 0, request.fingerprint, None, None, {"code": exc.code, "message": str(exc), "status": exc.status, "retryable": exc.retryable, "retry_after": exc.retry_after}, "present" if api_key else "missing", f"capped-at-${max_spend_usd:.2f}", True)
