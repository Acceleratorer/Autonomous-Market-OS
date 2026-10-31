from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
import base64
import hashlib
import http.client
import hmac
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest

from market_os.api import MAX_POST_BODY_BYTES, make_handler
from market_os.store import RunStore
from market_os.workflow import MarketWorkflow
from market_os.u55_access import (
    RequestRateLimiter,
    U55AccessConfig,
    U55AccessError,
    U55_ALLOWED_PORTFOLIO_ID,
    make_signed_headers,
)
from market_os.portfolio_broker import B41Broker
from market_os.tests.test_portfolio_broker import policy
from market_os.portfolio_broker import B41Genesis


def access_config(tmp_path: Path) -> U55AccessConfig:
    portfolio_root = tmp_path / "portfolios"
    (portfolio_root / U55_ALLOWED_PORTFOLIO_ID).mkdir(parents=True)
    return U55AccessConfig(
        owner_subject="owner@example.test",
        portfolio_root=portfolio_root,
        assertion_secret=b"s" * 32,
        session_state_path=tmp_path / "session" / "jti.json",
    )


def test_allowed_owner_can_consume_one_assertion_and_replay_is_denied(tmp_path: Path) -> None:
    config = access_config(tmp_path)
    headers = make_signed_headers(
        config.owner_subject,
        config.assertion_secret,
        now=1_000,
        jti="owner-jti-0000001",
    )

    principal = config.authorize_principal(headers, now=1_001)

    assert principal.subject == config.owner_subject
    assert config.resolve_allowed_portfolio("paper-main").name == "paper-main"
    with pytest.raises(U55AccessError, match="already been used") as replay:
        config.authorize_principal(headers, now=1_002)
    assert replay.value.reason_code == "jti_replayed"


@pytest.mark.parametrize(
    ("headers", "reason"),
    [
        ({}, "principal_missing"),
        (
            {
                "X-Market-OS-Principal": "not-base64",
                "X-Market-OS-Principal-Signature": "0" * 64,
            },
            "principal_forged",
        ),
    ],
)
def test_missing_or_malformed_assertion_fails_closed(
    tmp_path: Path,
    headers: dict[str, str],
    reason: str,
) -> None:
    config = access_config(tmp_path)
    with pytest.raises(U55AccessError) as failure:
        config.authorize_principal(headers, now=1_000)
    assert failure.value.reason_code == reason


def test_typed_malformed_principal_fails_closed(tmp_path: Path) -> None:
    config = access_config(tmp_path)
    payload = {
        "assertion_method": "tailscale-serve-v1",
        "audience": "market-os-python",
        "expires_at": "not-an-integer",
        "issued_at": 1_000,
        "issuer": "tailscale-serve",
        "jti": "typed-malformed-jti-1",
        "subject": config.owner_subject,
        "version": "market-os.u5-5.principal@v1",
    }
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"),
    ).rstrip(b"=").decode("ascii")
    with pytest.raises(U55AccessError) as failure:
        config.authorize_principal(
            {
                "X-Market-OS-Principal": encoded,
                "X-Market-OS-Principal-Signature": hmac.new(
                    config.assertion_secret,
                    encoded.encode("ascii"),
                    hashlib.sha256,
                ).hexdigest(),
            },
            now=1_000,
        )
    assert failure.value.reason_code == "principal_malformed"


def test_unknown_subject_is_denied_before_jti_consumption(tmp_path: Path) -> None:
    config = access_config(tmp_path)
    headers = make_signed_headers(
        "unknown@example.test",
        config.assertion_secret,
        now=1_000,
        jti="unknown-jti-00001",
    )

    with pytest.raises(U55AccessError) as failure:
        config.authorize_principal(headers, now=1_001)

    assert failure.value.reason_code == "unknown_subject"
    config.authorize_principal(
        make_signed_headers(
            config.owner_subject,
            config.assertion_secret,
            now=1_000,
            jti="owner-jti-0000002",
        ),
        now=1_001,
    )


def test_expired_assertion_is_denied_after_clock_tolerance(tmp_path: Path) -> None:
    config = access_config(tmp_path)
    headers = make_signed_headers(
        config.owner_subject,
        config.assertion_secret,
        now=1_000,
        jti="expired-jti-00001",
    )

    with pytest.raises(U55AccessError) as failure:
        config.authorize_principal(headers, now=1_961)

    assert failure.value.reason_code == "principal_expired"


def test_raw_ingress_or_forged_principal_header_is_never_trusted_by_python(tmp_path: Path) -> None:
    config = access_config(tmp_path)
    headers = make_signed_headers(
        config.owner_subject,
        config.assertion_secret,
        now=1_000,
        jti="forged-header-0001",
    )
    headers["Tailscale-User-Login"] = config.owner_subject

    with pytest.raises(U55AccessError) as failure:
        config.authorize_principal(headers, now=1_001)

    assert failure.value.reason_code == "forged_principal_header"


def test_cross_portfolio_and_traversal_are_denied_without_storage_open(tmp_path: Path) -> None:
    config = access_config(tmp_path)

    for portfolio_id, reason in (
        ("other-portfolio", "portfolio_not_allowlisted"),
        ("../paper-main", "portfolio_authorization_denied"),
    ):
        with pytest.raises(U55AccessError) as failure:
            config.resolve_allowed_portfolio(portfolio_id)
        assert failure.value.reason_code == reason


def test_symlinked_portfolio_and_invalid_root_fail_closed(tmp_path: Path) -> None:
    config = access_config(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    link = config.portfolio_root / "paper-main"
    if not hasattr(os, "symlink"):
        pytest.skip("symlink support is unavailable")
    try:
        link.rmdir()
        os.symlink(outside, link, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink creation is unavailable: {exc}")

    with pytest.raises(U55AccessError) as alias:
        config.resolve_allowed_portfolio("paper-main")
    assert alias.value.reason_code == "storage_alias_denied"

    invalid = U55AccessConfig(
        owner_subject=config.owner_subject,
        portfolio_root=tmp_path / "missing-root",
        assertion_secret=config.assertion_secret,
        session_state_path=tmp_path / "session-2" / "jti.json",
    )
    with pytest.raises(U55AccessError) as root:
        invalid.validate_storage_root()
    assert root.value.reason_code == "storage_root_invalid"


def test_owner_named_paper_main_portfolio_recovers_read_only(tmp_path: Path) -> None:
    approved_policy = policy()
    genesis = B41Genesis.create_named(
        U55_ALLOWED_PORTFOLIO_ID,
        "owner",
        "u5-5-owner-paper-main-v1",
        approved_policy,
    )
    B41Broker(tmp_path, genesis, approved_policy)

    recovered = B41Broker.open(tmp_path, U55_ALLOWED_PORTFOLIO_ID, read_only=True)

    assert recovered.genesis.portfolio_id == U55_ALLOWED_PORTFOLIO_ID
    assert recovered.read_only is True


def test_connected_rate_limiter_is_bounded_and_rolls_forward() -> None:
    limiter = RequestRateLimiter(max_requests=2, window_seconds=60)

    assert limiter.allow("owner@example.test", now=100)
    assert limiter.allow("owner@example.test", now=100)
    assert limiter.allow("owner@example.test", now=100) is False
    assert limiter.allow("owner@example.test", now=161)


def connected_server(tmp_path: Path) -> tuple[ThreadingHTTPServer, Thread, U55AccessConfig, Path]:
    config = access_config(tmp_path)
    genesis = B41Genesis.create_named(
        U55_ALLOWED_PORTFOLIO_ID,
        "owner",
        "u5-5-owner-paper-main-v1",
        policy(),
    )
    B41Broker(config.portfolio_root, genesis, policy())
    log_path = tmp_path / "logs" / "connected.jsonl"
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        make_handler(
            MarketWorkflow(RunStore(tmp_path / "state")),
            service_log_path=log_path,
            connected_access=config,
        ),
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, config, log_path


def request(
    server: ThreadingHTTPServer,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    method: str = "GET",
    body: bytes | None = None,
) -> tuple[int, bytes]:
    request_value = urllib.request.Request(
        f"http://127.0.0.1:{server.server_port}{path}",
        headers=headers or {},
        method=method,
        data=body,
    )
    try:
        with urllib.request.urlopen(request_value, timeout=2) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def test_connected_http_allows_only_signed_owner_paper_main_gets(tmp_path: Path) -> None:
    server, thread, config, log_path = connected_server(tmp_path)
    try:
        status, body = request(
            server,
            "/v1/b4/portfolios",
            headers=make_signed_headers(
                config.owner_subject,
                config.assertion_secret,
                jti="catalog-owner-jti-1",
            ),
        )
        assert status == 200
        catalog = json.loads(body)
        assert [item["portfolio_id"] for item in catalog["portfolios"]] == ["paper-main"]

        status, body = request(
            server,
            "/v3/b4/portfolios/paper-main/inspection",
            headers=make_signed_headers(
                config.owner_subject,
                config.assertion_secret,
                jti="detail-owner-jti-1",
            ),
        )
        assert status == 200
        assert json.loads(body)["portfolio_id"] == "paper-main"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert any(record["event"] == "request.allowed" for record in records)
    assert any(
        record["event"] == "portfolio.authorization"
        and record["reason_code"] == "allowed"
        and record["portfolio_id"] == "paper-main"
        for record in records
    )


@pytest.mark.parametrize(
    ("path", "headers", "reason"),
    [
        ("/v1/b4/portfolios", {}, "principal_missing"),
        (
            "/v1/b4/portfolios",
            make_signed_headers("unknown@example.test", b"s" * 32, jti="unknown-http-jti-1"),
            "unknown_subject",
        ),
        (
            "/v1/b4/portfolios",
            {
                **make_signed_headers("owner@example.test", b"s" * 32, jti="forged-http-jti-1"),
                "Tailscale-User-Login": "owner@example.test",
            },
            "forged_principal_header",
        ),
    ],
)
def test_connected_http_denies_missing_unknown_and_forged_identity(
    tmp_path: Path,
    path: str,
    headers: dict[str, str],
    reason: str,
) -> None:
    server, thread, _config, log_path = connected_server(tmp_path)
    try:
        status, _body = request(server, path, headers=headers)
        assert status == 403
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert any(record["reason_code"] == reason for record in records)


def test_connected_http_denies_expired_replayed_cross_portfolio_and_mutation(
    tmp_path: Path,
) -> None:
    server, thread, config, log_path = connected_server(tmp_path)
    try:
        expired = make_signed_headers(
            config.owner_subject,
            config.assertion_secret,
            now=1,
            jti="expired-http-jti-1",
        )
        assert request(server, "/v1/b4/portfolios", headers=expired)[0] == 403
        assert request(server, "/metrics", headers={})[0] == 404

        replay = make_signed_headers(
            config.owner_subject,
            config.assertion_secret,
            jti="replay-http-jti-1",
        )
        assert request(server, "/v1/b4/portfolios", headers=replay)[0] == 200
        assert request(server, "/v3/b4/portfolios/other/inspection", headers=replay)[0] == 403

        assert request(
            server,
            "/v1/b4/portfolios/other/inspection",
            headers=make_signed_headers(
                config.owner_subject,
                config.assertion_secret,
                jti="cross-http-jti-1",
            ),
        )[0] == 403
        assert request(
            server,
            "/v1/tasks",
            headers=make_signed_headers(
                config.owner_subject,
                config.assertion_secret,
                jti="mutation-http-jti-1",
            ),
            method="POST",
            body=b"{}",
        )[0] == 405
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    log_text = log_path.read_text(encoding="utf-8")
    records = [json.loads(line) for line in log_text.splitlines()]
    assert any(record["reason_code"] == "principal_expired" for record in records)
    assert any(record["reason_code"] == "jti_replayed" for record in records)
    assert any(record["reason_code"] == "portfolio_not_allowlisted" for record in records)
    assert any(record["reason_code"] == "mutation_disabled" for record in records)
    assert "s" * 32 not in log_text
    assert "X-Market-OS-Principal" not in log_text
    assert str(config.portfolio_root) not in log_text


def test_connected_http_rejects_oversized_mutation_body_before_parsing(tmp_path: Path) -> None:
    server, thread, _config, _log_path = connected_server(tmp_path)
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=2)
    try:
        connection.putrequest("POST", "/v1/tasks")
        connection.putheader("Host", "127.0.0.1")
        connection.putheader("Content-Length", str(MAX_POST_BODY_BYTES + 1))
        connection.endheaders()
        response = connection.getresponse()
        assert response.status == 405
        response.read()
    finally:
        connection.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_promotion_and_rollback_procedure_keeps_known_good_release(tmp_path: Path) -> None:
    del tmp_path
    root = Path(__file__).resolve().parents[2]
    promote = (root / "deploy" / "u5-5" / "promote.sh").read_text(encoding="utf-8")
    rollback = (root / "deploy" / "u5-5" / "rollback.sh").read_text(encoding="utf-8")

    assert 'age -R "$RECIPIENT_FILE"' in promote
    assert 'KNOWN_GOOD_LINK="$APP_ROOT/known-good"' in promote
    assert 'if ! "$HEALTHCHECK"; then' in promote
    assert 'readlink -e -- "$KNOWN_GOOD_LINK"' in promote
    assert "known-good release remains active" in promote
    assert 'target="$(readlink -e -- "$KNOWN_GOOD_LINK")"' in rollback
    assert '"$HEALTHCHECK"' in rollback
