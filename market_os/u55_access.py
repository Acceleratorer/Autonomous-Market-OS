"""Fail-closed U5.5 connected read-only access boundary.

The local operator remains unchanged unless the connected mode is explicitly
enabled.  In connected mode, Next.js sends a short-lived, HMAC-authenticated
principal envelope to the loopback Python gateway.  The browser never sees
the envelope or its signing secret.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
import re
import stat
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping


U55_ACCESS_VERSION = "market-os.u5-5.connected-access@v1"
U55_PRINCIPAL_VERSION = "market-os.u5-5.principal@v1"
U55_ISSUER = "tailscale-serve"
U55_AUDIENCE = "market-os-python"
U55_ASSERTION_METHOD = "tailscale-serve-v1"
U55_ALLOWED_PORTFOLIO_ID = "paper-main"
U55_SESSION_TTL_SECONDS = 15 * 60
U55_CLOCK_TOLERANCE_SECONDS = 60
U55_PRINCIPAL_HEADER = "X-Market-OS-Principal"
U55_SIGNATURE_HEADER = "X-Market-OS-Principal-Signature"
U55_TAILSCALE_IDENTITY_HEADERS = frozenset(
    {
        "tailscale-user-login",
        "tailscale-user-name",
        "tailscale-user-profile-pic",
        "x-user",
        "x-principal",
    }
)
_SUBJECT_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._@:+-]{0,191}\Z")
_JTI_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{15,127}\Z")
_PORTFOLIO_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")


class U55AccessError(ValueError):
    """A fail-closed connected-access rejection with a safe reason code."""

    def __init__(self, message: str, reason_code: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


def _is_reparse_point(path: Path) -> bool:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    is_junction = getattr(path, "is_junction", None)
    reparse_attribute = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return (
        stat.S_ISLNK(info.st_mode)
        or bool(getattr(info, "st_file_attributes", 0) & reparse_attribute)
        or (callable(is_junction) and is_junction())
    )


def _canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    if not isinstance(value, str) or not value or len(value) > 4096:
        raise U55AccessError("principal envelope is malformed", "principal_malformed")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise U55AccessError("principal envelope is malformed", "principal_malformed")
    try:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (ValueError, binascii.Error) as exc:
        raise U55AccessError("principal envelope is malformed", "principal_malformed") from exc


def _header_values(headers: Mapping[str, Any], name: str) -> list[str]:
    if hasattr(headers, "get_all"):
        values = headers.get_all(name, [])
        return [value for value in values if isinstance(value, str)]
    lowered = name.lower()
    values: list[str] = []
    for key, value in headers.items():
        if str(key).lower() == lowered:
            if isinstance(value, str):
                values.append(value)
            elif isinstance(value, (list, tuple)):
                values.extend(item for item in value if isinstance(item, str))
    return values


def _has_header(headers: Mapping[str, Any], name: str) -> bool:
    return bool(_header_values(headers, name))


def _subject_hash(subject: str | None) -> str | None:
    if subject is None:
        return None
    return hashlib.sha256(subject.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class U55Principal:
    issuer: str
    subject: str
    audience: str
    issued_at: int
    expires_at: int
    jti: str
    assertion_method: str = U55_ASSERTION_METHOD
    version: str = U55_PRINCIPAL_VERSION

    def payload(self) -> dict[str, Any]:
        return {
            "assertion_method": self.assertion_method,
            "audience": self.audience,
            "expires_at": self.expires_at,
            "issued_at": self.issued_at,
            "issuer": self.issuer,
            "jti": self.jti,
            "subject": self.subject,
            "version": self.version,
        }


def encode_principal(principal: U55Principal) -> str:
    return _b64url_encode(_canonical_json(principal.payload()))


def sign_principal(principal: U55Principal, secret: bytes | str) -> str:
    key = secret.encode("utf-8") if isinstance(secret, str) else secret
    if len(key) < 32:
        raise ValueError("U5.5 assertion secret must be at least 32 bytes")
    encoded = encode_principal(principal).encode("ascii")
    return hmac.new(key, encoded, hashlib.sha256).hexdigest()


def build_principal(
    subject: str,
    *,
    now: int | None = None,
    ttl_seconds: int = U55_SESSION_TTL_SECONDS,
    jti: str | None = None,
) -> U55Principal:
    if _SUBJECT_PATTERN.fullmatch(subject) is None:
        raise ValueError("U5.5 subject is malformed")
    issued_at = int(time.time()) if now is None else now
    if isinstance(issued_at, bool) or not isinstance(issued_at, int):
        raise ValueError("U5.5 principal time is malformed")
    if ttl_seconds != U55_SESSION_TTL_SECONDS:
        raise ValueError("U5.5 principal TTL is fixed at 15 minutes")
    selected_jti = jti or hashlib.sha256(f"{subject}:{issued_at}:{time.time_ns()}".encode()).hexdigest()
    if _JTI_PATTERN.fullmatch(selected_jti) is None:
        raise ValueError("U5.5 jti is malformed")
    return U55Principal(
        issuer=U55_ISSUER,
        subject=subject,
        audience=U55_AUDIENCE,
        issued_at=issued_at,
        expires_at=issued_at + ttl_seconds,
        jti=selected_jti,
    )


@dataclass
class JtiRegistry:
    """Bounded, hashed replay/revocation state for one Python service."""

    path: Path
    clock_tolerance_seconds: int = U55_CLOCK_TOLERANCE_SECONDS
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def _validate_path(self) -> None:
        if not self.path.is_absolute():
            raise U55AccessError("session state path must be absolute", "session_state_invalid")
        if _is_reparse_point(self.path):
            raise U55AccessError("session state path must be local", "session_state_invalid")
        parent = self.path.parent
        if _is_reparse_point(parent):
            raise U55AccessError("session state directory must be local", "session_state_invalid")

    @staticmethod
    def _digest(jti: str) -> str:
        return hashlib.sha256(jti.encode("utf-8")).hexdigest()

    def _load(self) -> tuple[dict[str, int], set[str]]:
        self._validate_path()
        if not self.path.exists():
            return {}, set()
        if not self.path.is_file():
            raise U55AccessError("session state is not a file", "session_state_invalid")
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise U55AccessError("session state is malformed", "session_state_invalid") from exc
        if not isinstance(payload, dict) or payload.get("version") != U55_ACCESS_VERSION:
            raise U55AccessError("session state is malformed", "session_state_invalid")
        used = payload.get("used")
        revoked = payload.get("revoked")
        if (
            not isinstance(used, dict)
            or not isinstance(revoked, list)
            or any(
                not isinstance(key, str)
                or not re.fullmatch(r"[0-9a-f]{64}", key)
                or isinstance(value, bool)
                or not isinstance(value, int)
                for key, value in used.items()
            )
            or any(not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value) for value in revoked)
        ):
            raise U55AccessError("session state is malformed", "session_state_invalid")
        return dict(used), set(revoked)

    def _write(self, used: dict[str, int], revoked: set[str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if _is_reparse_point(self.path.parent):
            raise U55AccessError("session state directory must be local", "session_state_invalid")
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        payload = {
            "version": U55_ACCESS_VERSION,
            "used": dict(sorted(used.items())),
            "revoked": sorted(revoked),
        }
        try:
            temporary.write_bytes(_canonical_json(payload) + b"\n")
            with temporary.open("r+b") as handle:
                handle.flush()
                os.fsync(handle.fileno())
            temporary.replace(self.path)
        except OSError as exc:
            raise U55AccessError("session state cannot be written", "session_state_unavailable") from exc

    def consume(self, jti: str, expires_at: int, *, now: int) -> None:
        if _JTI_PATTERN.fullmatch(jti) is None:
            raise U55AccessError("jti is malformed", "jti_malformed")
        if expires_at <= now - self.clock_tolerance_seconds:
            raise U55AccessError("principal is expired", "principal_expired")
        with self._lock:
            used, revoked = self._load()
            used = {
                digest: expiry
                for digest, expiry in used.items()
                if expiry >= now - self.clock_tolerance_seconds
            }
            digest = self._digest(jti)
            if digest in revoked:
                raise U55AccessError("jti has been revoked", "jti_revoked")
            if digest in used:
                raise U55AccessError("jti has already been used", "jti_replayed")
            used[digest] = expires_at
            self._write(used, revoked)

    def revoke(self, jti: str) -> None:
        if _JTI_PATTERN.fullmatch(jti) is None:
            raise ValueError("jti is malformed")
        with self._lock:
            used, revoked = self._load()
            revoked.add(self._digest(jti))
            self._write(used, revoked)


@dataclass
class RequestRateLimiter:
    """Bound one connected subject to a small rolling request window."""

    max_requests: int = 120
    window_seconds: int = 60
    _requests: dict[str, deque[int]] = field(default_factory=dict, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def allow(self, subject: str, *, now: int | None = None) -> bool:
        current_time = int(time.time()) if now is None else now
        key = _subject_hash(subject)
        if key is None:
            return False
        with self._lock:
            requests = self._requests.setdefault(key, deque())
            while requests and requests[0] <= current_time - self.window_seconds:
                requests.popleft()
            if len(requests) >= self.max_requests:
                return False
            requests.append(current_time)
            return True


@dataclass(frozen=True)
class U55AccessConfig:
    """Concrete owner-approved U5.5 policy."""

    owner_subject: str
    portfolio_root: Path
    assertion_secret: bytes = field(repr=False)
    session_state_path: Path
    allowed_portfolio_id: str = U55_ALLOWED_PORTFOLIO_ID
    session_ttl_seconds: int = U55_SESSION_TTL_SECONDS
    clock_tolerance_seconds: int = U55_CLOCK_TOLERANCE_SECONDS
    issuer: str = U55_ISSUER
    audience: str = U55_AUDIENCE
    assertion_method: str = U55_ASSERTION_METHOD
    jti_registry: JtiRegistry = field(init=False, repr=False)
    rate_limiter: RequestRateLimiter = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if _SUBJECT_PATTERN.fullmatch(self.owner_subject) is None:
            raise ValueError("U5.5 owner subject is malformed")
        if self.allowed_portfolio_id != U55_ALLOWED_PORTFOLIO_ID:
            raise ValueError("U5.5 portfolio allowlist must remain paper-main")
        if not self.portfolio_root.is_absolute():
            raise ValueError("U5.5 portfolio root must be absolute")
        if len(self.assertion_secret) < 32:
            raise ValueError("U5.5 assertion secret must be at least 32 bytes")
        if self.session_ttl_seconds != U55_SESSION_TTL_SECONDS:
            raise ValueError("U5.5 session expiry must be 15 minutes")
        if self.clock_tolerance_seconds != U55_CLOCK_TOLERANCE_SECONDS:
            raise ValueError("U5.5 clock tolerance must be 60 seconds")
        if self.issuer != U55_ISSUER or self.audience != U55_AUDIENCE:
            raise ValueError("U5.5 principal issuer or audience is invalid")
        if self.assertion_method != U55_ASSERTION_METHOD:
            raise ValueError("U5.5 assertion method is invalid")
        object.__setattr__(self, "jti_registry", JtiRegistry(self.session_state_path, self.clock_tolerance_seconds))
        object.__setattr__(self, "rate_limiter", RequestRateLimiter())

    @classmethod
    def from_environment(cls) -> "U55AccessConfig | None":
        enabled = os.environ.get("MARKET_OS_U55_MODE", "").strip().lower()
        if enabled not in {"1", "true"}:
            return None
        owner_subject = os.environ.get("MARKET_OS_TAILSCALE_OWNER_LOGIN", "")
        secret = os.environ.get("MARKET_OS_INTERNAL_ASSERTION_SECRET", "")
        portfolio_root = os.environ.get("MARKET_OS_PORTFOLIO_ROOT", "")
        session_state_path = os.environ.get(
            "MARKET_OS_SESSION_STATE_PATH",
            "/var/lib/autonomous-market-os/session/u5-5-jti.json",
        )
        if not owner_subject or not secret or not portfolio_root:
            raise ValueError("U5.5 mode requires owner identity, assertion secret, and portfolio root")
        config = cls(
            owner_subject=owner_subject,
            portfolio_root=Path(portfolio_root),
            assertion_secret=secret.encode("utf-8"),
            session_state_path=Path(session_state_path),
        )
        config.validate_storage_root()
        return config

    def validate_storage_root(self) -> Path:
        root = self.portfolio_root
        if _is_reparse_point(root):
            raise U55AccessError("portfolio root must be local", "storage_root_invalid")
        try:
            resolved = root.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise U55AccessError("portfolio root cannot be resolved", "storage_root_invalid") from exc
        if resolved != root or not resolved.is_dir():
            raise U55AccessError("portfolio root must be a real directory", "storage_root_invalid")
        return resolved

    def resolve_allowed_portfolio(self, portfolio_id: str) -> Path:
        if not isinstance(portfolio_id, str) or _PORTFOLIO_PATTERN.fullmatch(portfolio_id) is None:
            raise U55AccessError("portfolio identifier is malformed", "portfolio_authorization_denied")
        if portfolio_id != self.allowed_portfolio_id:
            raise U55AccessError("portfolio is not allowlisted", "portfolio_not_allowlisted")
        root = self.validate_storage_root()
        candidate = root / portfolio_id
        if candidate.parent != root or _is_reparse_point(candidate):
            raise U55AccessError("portfolio path alias is not allowed", "storage_alias_denied")
        if not candidate.is_dir():
            raise U55AccessError("allowlisted portfolio is unavailable", "portfolio_storage_missing")
        try:
            resolved = candidate.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise U55AccessError("portfolio path cannot be resolved", "storage_alias_denied") from exc
        if resolved.parent != root or resolved != candidate:
            raise U55AccessError("portfolio path alias is not allowed", "storage_alias_denied")
        return resolved

    def authorize_principal(
        self,
        headers: Mapping[str, Any],
        *,
        now: int | None = None,
    ) -> U55Principal:
        if any(_has_header(headers, name) for name in U55_TAILSCALE_IDENTITY_HEADERS):
            raise U55AccessError(
                "raw ingress identity headers are not trusted by Python",
                "forged_principal_header",
            )
        envelope_values = _header_values(headers, U55_PRINCIPAL_HEADER)
        signature_values = _header_values(headers, U55_SIGNATURE_HEADER)
        if len(envelope_values) != 1 or len(signature_values) != 1:
            raise U55AccessError("principal assertion is missing", "principal_missing")
        encoded = envelope_values[0]
        signature = signature_values[0]
        if not re.fullmatch(r"[0-9a-f]{64}", signature):
            raise U55AccessError("principal signature is malformed", "principal_malformed")
        try:
            encoded_bytes = encoded.encode("ascii", "strict")
        except UnicodeEncodeError as exc:
            raise U55AccessError("principal signature is malformed", "principal_malformed") from exc
        expected_signature = hmac.new(
            self.assertion_secret,
            encoded_bytes,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(signature, expected_signature):
            raise U55AccessError("principal signature is invalid", "principal_forged")
        try:
            payload = json.loads(_b64url_decode(encoded))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise U55AccessError("principal envelope is malformed", "principal_malformed") from exc
        if not isinstance(payload, dict):
            raise U55AccessError("principal envelope is malformed", "principal_malformed")
        expected_fields = {
            "assertion_method",
            "audience",
            "expires_at",
            "issued_at",
            "issuer",
            "jti",
            "subject",
            "version",
        }
        if set(payload) != expected_fields:
            raise U55AccessError("principal envelope is malformed", "principal_malformed")
        if any(
            not isinstance(payload.get(name), str)
            for name in {"assertion_method", "audience", "issuer", "jti", "subject", "version"}
        ) or any(
            isinstance(payload.get(name), bool) or not isinstance(payload.get(name), int)
            for name in {"issued_at", "expires_at"}
        ):
            raise U55AccessError("principal envelope is malformed", "principal_malformed")
        principal = U55Principal(
            issuer=payload["issuer"],
            subject=payload["subject"],
            audience=payload["audience"],
            issued_at=payload["issued_at"],
            expires_at=payload["expires_at"],
            jti=payload["jti"],
            assertion_method=payload["assertion_method"],
            version=payload["version"],
        )
        if (
            principal.version != U55_PRINCIPAL_VERSION
            or principal.issuer != self.issuer
            or principal.audience != self.audience
            or principal.assertion_method != self.assertion_method
            or _SUBJECT_PATTERN.fullmatch(principal.subject) is None
            or _JTI_PATTERN.fullmatch(principal.jti) is None
            or isinstance(principal.issued_at, bool)
            or not isinstance(principal.issued_at, int)
            or isinstance(principal.expires_at, bool)
            or not isinstance(principal.expires_at, int)
            or principal.expires_at <= principal.issued_at
            or principal.expires_at - principal.issued_at != self.session_ttl_seconds
        ):
            raise U55AccessError("principal envelope is malformed", "principal_malformed")
        if principal.subject != self.owner_subject:
            raise U55AccessError("subject is not allowlisted", "unknown_subject")
        current_time = int(time.time()) if now is None else now
        if principal.issued_at > current_time + self.clock_tolerance_seconds:
            raise U55AccessError("principal is not yet valid", "principal_not_yet_valid")
        if principal.expires_at < current_time - self.clock_tolerance_seconds:
            raise U55AccessError("principal is expired", "principal_expired")
        self.jti_registry.consume(principal.jti, principal.expires_at, now=current_time)
        return principal

    def audit_subject(self, principal: U55Principal | None) -> str | None:
        return _subject_hash(principal.subject if principal else None)


def make_signed_headers(
    subject: str,
    secret: bytes | str,
    *,
    now: int | None = None,
    jti: str | None = None,
) -> dict[str, str]:
    principal = build_principal(subject, now=now, jti=jti)
    encoded = encode_principal(principal)
    return {
        U55_PRINCIPAL_HEADER: encoded,
        U55_SIGNATURE_HEADER: sign_principal(principal, secret),
    }


def connected_path_portfolio_id(path: str) -> str | None:
    parts = path.strip("/").split("/")
    if len(parts) < 4 or parts[0] not in {"v1", "v2", "v3"} or parts[1:3] != ["b4", "portfolios"]:
        return None
    return parts[3] if parts[3] else None


def is_connected_read_path(path: str) -> bool:
    if path in {"/healthz", "/readyz", "/v1/b4/portfolios"}:
        return True
    portfolio_id = connected_path_portfolio_id(path)
    return portfolio_id is not None and path.startswith(("/v1/", "/v2/", "/v3/"))


__all__ = [
    "JtiRegistry",
    "RequestRateLimiter",
    "U55AccessConfig",
    "U55AccessError",
    "U55Principal",
    "U55_ACCESS_VERSION",
    "U55_ALLOWED_PORTFOLIO_ID",
    "U55_ASSERTION_METHOD",
    "U55_AUDIENCE",
    "U55_CLOCK_TOLERANCE_SECONDS",
    "U55_ISSUER",
    "U55_PRINCIPAL_HEADER",
    "U55_PRINCIPAL_VERSION",
    "U55_SESSION_TTL_SECONDS",
    "U55_SIGNATURE_HEADER",
    "build_principal",
    "connected_path_portfolio_id",
    "encode_principal",
    "is_connected_read_path",
    "make_signed_headers",
    "sign_principal",
]
