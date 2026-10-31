"""Local HMAC capability authorization for paper broker mutations.

This is a trusted in-process capability seam, not human authentication or a
network-facing identity system.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any, Callable, Mapping

from .portfolio_broker import B41Approval, B41Broker, B41Order, BrokerRejected, _fingerprint, _identifier, _text


CAPABILITY_SCHEMA = "market-os.b4-19.local-capability@v1"
CAPABILITY_PREFIX = "b4.19"
CAPABILITY_FIELDS = frozenset({
    "schema", "subject", "portfolio_id", "operation", "command_fingerprint",
    "idempotency_key", "issued_at_ms", "expires_at_ms",
})
OPERATIONS = frozenset({"order.submit", "order.cancel", "approval.revoke"})


def _canonical(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padded = value + "=" * (-len(value) % 4)
    try:
        decoded = base64.b64decode(padded.encode("ascii"), altchars=b"-_", validate=True)
    except (ValueError, UnicodeEncodeError) as exc:
        raise BrokerRejected("local mutation capability is malformed", "capability.invalid") from exc
    if _b64encode(decoded) != value:
        raise BrokerRejected("local mutation capability is malformed", "capability.invalid")
    return decoded


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate field")
        result[key] = value
    return result


def _command(operation: str, *, portfolio_id: str, command_fingerprint: str, idempotency_key: str) -> dict[str, Any]:
    if operation not in OPERATIONS:
        raise BrokerRejected("local mutation operation is not supported", "capability.operation_mismatch")
    if not isinstance(command_fingerprint, str) or len(command_fingerprint) != 64 or any(char not in "0123456789abcdef" for char in command_fingerprint):
        raise BrokerRejected("command fingerprint is malformed", "capability.command_mismatch")
    try:
        _identifier(portfolio_id, "portfolio_id")
        _text(idempotency_key, "idempotency_key")
    except BrokerRejected as exc:
        raise BrokerRejected("command identity is malformed", "capability.invalid") from exc
    return {"operation": operation, "portfolio_id": portfolio_id,
            "command_fingerprint": command_fingerprint, "idempotency_key": idempotency_key}


class LocalMutationAuthority:
    """Issue and verify local capabilities for one stable in-process subject."""

    def __init__(self, broker: B41Broker, signing_key: bytes, subject: str,
                 clock_ms: Callable[[], int] | None = None) -> None:
        if not isinstance(signing_key, bytes) or len(signing_key) < 32:
            raise ValueError("local mutation signing key must contain at least 32 bytes")
        try:
            _identifier(subject, "subject")
        except BrokerRejected as exc:
            raise ValueError("local mutation subject must be a stable identifier") from exc
        self.broker = broker
        self._signing_key = signing_key
        self.subject = subject
        self._clock_ms = clock_ms or (lambda: time.time_ns() // 1_000_000)

    def issue(self, operation: str, *, portfolio_id: str, command_fingerprint: str,
              idempotency_key: str, issued_at_ms: int, expires_at_ms: int) -> str:
        if portfolio_id != self.broker.genesis.portfolio_id:
            raise BrokerRejected("local mutation portfolio does not match", "capability.portfolio_mismatch")
        command = _command(operation, portfolio_id=portfolio_id,
                           command_fingerprint=command_fingerprint, idempotency_key=idempotency_key)
        if isinstance(issued_at_ms, bool) or not isinstance(issued_at_ms, int) or issued_at_ms < 0:
            raise ValueError("issued_at_ms must be a non-negative integer")
        if isinstance(expires_at_ms, bool) or not isinstance(expires_at_ms, int) or expires_at_ms <= issued_at_ms:
            raise ValueError("expires_at_ms must be after issued_at_ms")
        payload = {"schema": CAPABILITY_SCHEMA, "subject": self.subject, **command,
                   "issued_at_ms": issued_at_ms, "expires_at_ms": expires_at_ms}
        encoded = _b64encode(_canonical(payload))
        signature = _b64encode(hmac.new(self._signing_key, encoded.encode("ascii"), hashlib.sha256).digest())
        return f"{CAPABILITY_PREFIX}.{encoded}.{signature}"

    def _verify(self, token: str, *, operation: str, portfolio_id: str,
                command_fingerprint: str, idempotency_key: str) -> dict[str, str]:
        try:
            if not isinstance(token, str):
                raise ValueError("token")
            parts = token.split(".")
            if len(parts) != 4 or parts[0] != "b4" or parts[1] != "19" or len(token) > 4096:
                raise ValueError("shape")
            encoded, supplied_signature = parts[2], _b64decode(parts[3])
            raw_payload = _b64decode(encoded)
            payload = json.loads(raw_payload, object_pairs_hook=_unique_object)
            if not isinstance(payload, dict) or frozenset(payload) != CAPABILITY_FIELDS or _canonical(payload) != raw_payload:
                raise ValueError("payload")
            expected_signature = hmac.new(self._signing_key, encoded.encode("ascii"), hashlib.sha256).digest()
            if not hmac.compare_digest(supplied_signature, expected_signature):
                raise ValueError("signature")
            if payload["schema"] != CAPABILITY_SCHEMA:
                raise ValueError("schema")
            if not isinstance(payload["subject"], str):
                raise ValueError("subject")
            if payload["operation"] not in OPERATIONS:
                raise ValueError("operation")
            _command(payload["operation"], portfolio_id=payload["portfolio_id"],
                     command_fingerprint=payload["command_fingerprint"],
                     idempotency_key=payload["idempotency_key"])
            issued_at_ms, expires_at_ms = payload["issued_at_ms"], payload["expires_at_ms"]
            if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in (issued_at_ms, expires_at_ms)) or expires_at_ms <= issued_at_ms:
                raise ValueError("validity")
        except (ValueError, TypeError, KeyError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise BrokerRejected("local mutation capability is invalid", "capability.invalid") from exc

        if payload["subject"] != self.subject:
            raise BrokerRejected("local mutation subject does not match", "capability.subject_mismatch")
        if payload["portfolio_id"] != portfolio_id:
            raise BrokerRejected("local mutation portfolio does not match", "capability.portfolio_mismatch")
        if payload["operation"] != operation:
            raise BrokerRejected("local mutation operation does not match", "capability.operation_mismatch")
        if payload["command_fingerprint"] != command_fingerprint:
            raise BrokerRejected("local mutation command does not match", "capability.command_mismatch")
        if payload["idempotency_key"] != idempotency_key:
            raise BrokerRejected("local mutation idempotency key does not match", "capability.idempotency_mismatch")
        now_ms = self._clock_ms()
        if isinstance(now_ms, bool) or not isinstance(now_ms, int) or now_ms < 0:
            raise BrokerRejected("local mutation time is invalid", "capability.invalid")
        if issued_at_ms > now_ms:
            raise BrokerRejected("local mutation capability is not yet valid", "capability.not_yet_valid")
        if expires_at_ms <= now_ms:
            raise BrokerRejected("local mutation capability has expired", "capability.expired")
        return {"subject": self.subject, "operation": operation,
                "capability_fingerprint": hashlib.sha256(token.encode("ascii")).hexdigest()}

    def submit_order(self, order: B41Order, approval: B41Approval, token: str) -> dict[str, Any]:
        context = self._verify(token, operation="order.submit", portfolio_id=order.portfolio_id,
                               command_fingerprint=order.command_fingerprint,
                               idempotency_key=order.idempotency_key)
        return self.broker.submit_order(order, approval, _authorization_context=context)

    def cancel_order(self, portfolio_id: str, order_id: str, command_id: str, idempotency_key: str,
                     submitted_at_ms: int, approval: B41Approval, token: str, *,
                     strategy_id: str | None = None) -> dict[str, Any]:
        projection: dict[str, Any] = {"portfolio_id": portfolio_id, "order_id": order_id,
                                      "command_id": command_id, "idempotency_key": idempotency_key,
                                      "submitted_at_ms": submitted_at_ms}
        if strategy_id is not None:
            projection["strategy_id"] = strategy_id
        fingerprint = _fingerprint(projection)
        context = self._verify(token, operation="order.cancel", portfolio_id=portfolio_id,
                               command_fingerprint=fingerprint, idempotency_key=idempotency_key)
        return self.broker.cancel_order(portfolio_id, order_id, command_id, idempotency_key,
                                        submitted_at_ms, approval, strategy_id,
                                        _authorization_context=context)

    def revoke_approval(self, approval_id: str, command_id: str, idempotency_key: str,
                        revoked_at_ms: int, token: str, *,
                        approver_id: str = "owner") -> dict[str, Any]:
        fingerprint = _fingerprint({"approval_id": approval_id, "command_id": command_id,
                                    "idempotency_key": idempotency_key,
                                    "revoked_at_ms": revoked_at_ms})
        context = self._verify(token, operation="approval.revoke", portfolio_id=self.broker.genesis.portfolio_id,
                               command_fingerprint=fingerprint, idempotency_key=idempotency_key)
        return self.broker.revoke_approval(approval_id, command_id, idempotency_key,
                                           revoked_at_ms, approver_id,
                                           _authorization_context=context)


__all__ = ["LocalMutationAuthority", "CAPABILITY_SCHEMA"]
