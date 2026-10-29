from __future__ import annotations

import json
import urllib.parse
from decimal import Decimal
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from market_os.api import make_handler
from market_os.btc_history import MAX_MANIFEST_INSPECTION_BYTES, HistoryStore
from market_os.portfolio_broker import B41Broker, B41Genesis, B41Order, BrokerStale
from market_os.paper_venue import BUY, LIMIT
from market_os.store import RunStore
from market_os.workflow import MarketWorkflow
from market_os.tests.test_portfolio_broker import approval, buy, event as market_event, genesis, policy


BTC_HISTORY_FIXTURE = Path(__file__).parent / "fixtures" / "btc_paper" / "history.json"


def _copy_portfolio(source: Path, target: Path) -> None:
    target.mkdir(parents=True)
    for path in source.iterdir():
        if path.is_file():
            (target / path.name).write_bytes(path.read_bytes())


def test_operator_shell_reads_summary_and_keeps_get_only_boundary(tmp_path: Path) -> None:
    portfolio = genesis()
    source = tmp_path / "source" / portfolio.portfolio_id
    broker = B41Broker(source.parent, portfolio, policy())
    order = buy()
    broker.submit_order(order, approval(order))
    workflow_root = tmp_path / "workflow"
    _copy_portfolio(source, workflow_root / "b4-paper" / portfolio.portfolio_id)
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(MarketWorkflow(RunStore(workflow_root))))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        shell = urlopen(f"{base}/operator/{portfolio.portfolio_id}/", timeout=2)
        body = shell.read().decode("utf-8")
        assert shell.status == 200
        assert shell.headers["Content-Type"] == "text/html; charset=utf-8"
        assert shell.headers["X-Request-ID"]
        assert shell.headers["X-Content-Type-Options"] == "nosniff"
        assert shell.headers["Referrer-Policy"] == "no-referrer"
        assert "connect-src 'self'" in shell.headers["Content-Security-Policy"]
        assert "Paper portfolio monitor" in body
        assert "/operator/operator.js" in body
        assert "Portfolio context" in body
        assert "Reservations" in body
        assert "Risk audit" in body
        assert "order-latest" in body
        assert "risk-latest" in body
        assert 'role="group" aria-label="Order pages"' in body
        assert 'role="group" aria-label="Risk outcome pages"' in body
        assert 'role="group" aria-label="Strategy member pages"' in body
        assert 'role="group" aria-label="Reservation pages"' in body
        assert 'role="region" aria-label="Portfolio-wide reservation detail" tabindex="0"' in body
        assert 'role="region" aria-label="Portfolio orders" tabindex="0"' in body
        assert "<form" not in body.lower()

        catalog_page = urlopen(f"{base}/operator/", timeout=2)
        catalog_body = catalog_page.read().decode("utf-8")
        assert catalog_page.status == 200
        assert portfolio.portfolio_id in catalog_body
        assert "Local paper portfolios" in catalog_body
        assert "operator.css" in catalog_body
        catalog = json.loads(urlopen(f"{base}/v1/b4/portfolios", timeout=2).read())
        assert catalog["portfolios"][0]["portfolio_id"] == portfolio.portfolio_id
        assert catalog["portfolios"][0]["mode"] == "isolated"
        assert catalog["portfolios"][0]["member_count"] == 1
        assert "strategy_ids" not in catalog["portfolios"][0]
        assert catalog["page"]["has_more"] is False

        script = urlopen(f"{base}/operator/app.js", timeout=2)
        assert script.headers["Content-Type"] == "text/javascript; charset=utf-8"
        script_body = script.read().decode("utf-8")
        assert "v1/b4/portfolios" in script_body
        assert "order_before_id" in script_body
        assert "v2/b4/portfolios" in script_body
        assert "member_after_strategy_id" in script_body
        assert "reservation_before_order_id" in script_body
        assert 'credentials: "omit"' in script_body

        canonical_script = urlopen(f"{base}/operator/operator.js", timeout=2)
        assert canonical_script.status == 200

        styles = urlopen(f"{base}/operator/styles.css", timeout=2)
        assert styles.headers["Content-Type"] == "text/css; charset=utf-8"

        canonical_styles = urlopen(f"{base}/operator/operator.css", timeout=2)
        assert canonical_styles.status == 200

        genesis_payload = json.loads(urlopen(f"{base}/v1/b4/portfolios/{portfolio.portfolio_id}/genesis", timeout=2).read())
        assert genesis_payload["portfolio_id"] == portfolio.portfolio_id
        reservations_payload = json.loads(urlopen(f"{base}/v1/b4/portfolios/{portfolio.portfolio_id}/reservations", timeout=2).read())
        assert reservations_payload["portfolio_id"] == portfolio.portfolio_id
        orders_payload = json.loads(urlopen(f"{base}/v1/b4/portfolios/{portfolio.portfolio_id}/orders", timeout=2).read())
        assert orders_payload["orders"][0]["order_id"] == order.order_id
        risk_payload = json.loads(urlopen(f"{base}/v1/b4/portfolios/{portfolio.portfolio_id}/risk", timeout=2).read())
        assert "records" in risk_payload

        summary = json.loads(urlopen(f"{base}/v1/b4/portfolios/{portfolio.portfolio_id}/summary", timeout=2).read())
        assert summary["open_orders"] == 1

        inspection = json.loads(urlopen(
            f"{base}/v1/b4/portfolios/{portfolio.portfolio_id}/inspection?risk_limit=8&order_limit=25",
            timeout=2,
        ).read())
        assert inspection["api_version"] == "market-os.b4-portfolio-inspection@v1"
        assert inspection["summary"]["portfolio_id"] == portfolio.portfolio_id
        assert "event_cursor" not in inspection["summary"]
        assert len(inspection["orders"]["orders"]) == 1
        assert len(inspection["risk"]["records"]) <= 8

        isolated_v2 = json.loads(urlopen(
            f"{base}/v2/b4/portfolios/{portfolio.portfolio_id}/inspection",
            timeout=2,
        ).read())
        assert isolated_v2["api_version"] == "market-os.b4-portfolio-inspection@v2"
        assert isolated_v2["members"]["strategy_ids"] == [portfolio.strategy_id]
        assert isolated_v2["members"]["page"]["total_count"] == 1
        assert isolated_v2["reservations"]["page"]["total_count"] == 1

        for invalid_query in ("order_limit=101", "order_limit=10&order_limit=20", "unknown=1"):
            with pytest.raises(HTTPError) as invalid_request:
                urlopen(f"{base}/v1/b4/portfolios/{portfolio.portfolio_id}/inspection?{invalid_query}", timeout=2)
            assert invalid_request.value.code == 400
        for cursor_query in ("order_before_id=missing-order", "risk_before_sequence=99999"):
            with pytest.raises(HTTPError) as invalid_cursor:
                urlopen(f"{base}/v1/b4/portfolios/{portfolio.portfolio_id}/inspection?{cursor_query}", timeout=2)
            assert invalid_cursor.value.code == 400

        with pytest.raises(HTTPError) as query:
            urlopen(f"{base}/operator/{portfolio.portfolio_id}/?token=fixture-secret", timeout=2)
        assert query.value.code == 400

        with pytest.raises(HTTPError) as post:
            urlopen(Request(f"{base}/operator/{portfolio.portfolio_id}/", data=b"{}", method="POST"), timeout=2)
        assert post.value.code == 404

        with pytest.raises(HTTPError) as missing:
            urlopen(f"{base}/operator/{portfolio.portfolio_id}/private.txt", timeout=2)
        assert missing.value.code == 404

        with pytest.raises(HTTPError) as traversal:
            urlopen(f"{base}/operator/{portfolio.portfolio_id}/%2e%2e/app.js", timeout=2)
        assert traversal.value.code == 404
    finally:
        server.shutdown()


def test_v2_inspection_bounds_members_and_reservations(tmp_path: Path) -> None:
    member_ids = [f"strategy-{index:03d}" for index in range(27)]
    portfolio = B41Genesis.create_shared("shared-api-pages", "synthetic-fixture-v1", member_ids, policy())
    source = tmp_path / "source" / portfolio.portfolio_id
    broker = B41Broker(source.parent, portfolio, policy())
    for index in range(27):
        order_id = f"reservation-{index:03d}"
        order = B41Order(
            portfolio.portfolio_id,
            order_id,
            f"cmd-{order_id}",
            f"key-{order_id}",
            BUY,
            LIMIT,
            Decimal("0.1"),
            Decimal("100"),
            900,
            strategy_id=member_ids[index],
        )
        assert broker.submit_order(order, approval(order))["state"] == "open"
    workflow_root = tmp_path / "workflow"
    _copy_portfolio(source, workflow_root / "b4-paper" / portfolio.portfolio_id)
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(MarketWorkflow(RunStore(workflow_root))))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    root = f"{base}/v2/b4/portfolios/{portfolio.portfolio_id}/inspection"
    try:
        first = json.loads(urlopen(root, timeout=2).read())
        assert first["api_version"] == "market-os.b4-portfolio-inspection@v2"
        assert "member_strategy_ids" not in first["genesis"]
        assert first["members"]["strategy_ids"] == member_ids[:25]
        assert first["members"]["page"]["total_count"] == 27
        assert [row["order_id"] for row in first["reservations"]["reservations"]] == [
            f"reservation-{index:03d}" for index in range(26, 1, -1)
        ]
        assert first["reservations"]["page"]["total_count"] == 27
        assert first["reservations"]["cash_usdt"] == "270.27"

        legacy = json.loads(urlopen(
            f"{base}/v1/b4/portfolios/{portfolio.portfolio_id}/inspection",
            timeout=2,
        ).read())
        assert len(legacy["genesis"]["member_strategy_ids"]) == 25
        assert legacy["genesis"]["members_page"]["total_count"] == 27
        assert legacy["genesis"]["members_page"]["has_more"] is True
        assert len(legacy["reservations"]["reservations"]) == 25
        assert legacy["reservations"]["page"]["total_count"] == 27
        assert legacy["reservations"]["page"]["has_more"] is True

        query = urllib.parse.urlencode({
            "member_after_strategy_id": member_ids[24],
            "reservation_before_order_id": "reservation-002",
        })
        last = json.loads(urlopen(f"{root}?{query}", timeout=2).read())
        assert last["members"]["strategy_ids"] == member_ids[25:]
        assert [row["order_id"] for row in last["reservations"]["reservations"]] == ["reservation-001", "reservation-000"]
        assert last["members"]["page"]["has_more"] is False
        assert last["reservations"]["page"]["has_more"] is False

        for query in (
            "member_limit=101",
            "member_limit=25&member_limit=20",
            "member_after_strategy_id=missing-member",
            "reservation_before_order_id=missing-order",
            "unknown=1",
        ):
            with pytest.raises(HTTPError) as invalid:
                urlopen(f"{root}?{query}", timeout=2)
            assert invalid.value.code == 400
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_v3_inspection_exposes_latest_bounded_equity_history_and_preserves_v1_v2(tmp_path: Path) -> None:
    workflow_root = tmp_path / "workflow"
    portfolio_root = workflow_root / "b4-paper"

    latest_policy = policy(
        initial_btc_quantity=Decimal("0.1"),
        initial_average_entry_price=Decimal("100"),
    )
    latest_genesis = B41Genesis.create("equity-latest", "synthetic-fixture-v1", latest_policy)
    latest_broker = B41Broker(portfolio_root, latest_genesis, latest_policy)
    for index in range(110):
        latest_broker.process_market_event(
            market_event(
                f"equity-event-{index:03d}",
                time_ms=1_000 + index * 1_000,
                bid=100 + index,
                ask=101 + index,
                last=100.5 + index,
            )
        )

    duplicate_genesis = B41Genesis.create("equity-duplicate-time", "synthetic-fixture-v1", policy())
    duplicate_broker = B41Broker(portfolio_root, duplicate_genesis, policy())
    duplicate_broker.process_market_event(market_event("equity-same-time"))

    empty_genesis = B41Genesis.create("equity-empty", "synthetic-fixture-v1", policy())
    B41Broker(portfolio_root, empty_genesis, policy())

    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(MarketWorkflow(RunStore(workflow_root))))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        latest_id = latest_genesis.portfolio_id
        v1 = json.loads(urlopen(f"{base}/v1/b4/portfolios/{latest_id}/inspection", timeout=2).read())
        v2 = json.loads(urlopen(f"{base}/v2/b4/portfolios/{latest_id}/inspection", timeout=2).read())
        v3 = json.loads(urlopen(f"{base}/v3/b4/portfolios/{latest_id}/inspection", timeout=2).read())

        assert v1["api_version"] == "market-os.b4-portfolio-inspection@v1"
        assert v2["api_version"] == "market-os.b4-portfolio-inspection@v2"
        assert "equity_history" not in v1
        assert "equity_history" not in v2
        assert v3["api_version"] == "market-os.b4-portfolio-inspection@v3"
        assert v3["equity_history"]["portfolio_id"] == latest_id
        assert v3["equity_history"]["page"] == {
            "limit": 100,
            "returned_count": 100,
            "total_count": 111,
            "has_more": True,
            "scope": "latest",
        }
        latest_points = v3["equity_history"]["points"]
        assert len(latest_points) == 100
        assert latest_points[0]["event_time_ms"] == 11_000
        assert latest_points[-1]["event_time_ms"] == 110_000
        assert latest_points[0]["equity_usdt"] == "10011.050"
        assert latest_points[-1]["equity_usdt"] == "10020.950"
        timestamps = [point["event_time_ms"] for point in latest_points]
        assert timestamps == sorted(timestamps)
        assert all(isinstance(point["equity_usdt"], str) for point in latest_points)
        assert v3["equity_history"]["minimum_equity_usdt"] == latest_points[0]["equity_usdt"]
        assert v3["equity_history"]["maximum_equity_usdt"] == latest_points[-1]["equity_usdt"]
        assert Decimal(v3["equity_history"]["minimum_equity_usdt"]) < Decimal(
            v3["equity_history"]["maximum_equity_usdt"]
        )

        duplicate = json.loads(urlopen(
            f"{base}/v3/b4/portfolios/{duplicate_genesis.portfolio_id}/inspection",
            timeout=2,
        ).read())["equity_history"]
        assert duplicate["page"]["total_count"] == 2
        assert [point["event_time_ms"] for point in duplicate["points"]] == [1_000, 1_000]

        empty = json.loads(urlopen(
            f"{base}/v3/b4/portfolios/{empty_genesis.portfolio_id}/inspection",
            timeout=2,
        ).read())["equity_history"]
        assert empty["points"] == []
        assert empty["minimum_equity_usdt"] is None
        assert empty["maximum_equity_usdt"] is None
        assert empty["page"]["total_count"] == 0

        with pytest.raises(HTTPError) as unsupported_limit:
            urlopen(f"{base}/v3/b4/portfolios/{latest_id}/inspection?equity_limit=101", timeout=2)
        assert unsupported_limit.value.code == 400

        with pytest.raises(HTTPError) as post:
            urlopen(Request(f"{base}/v3/b4/portfolios/{latest_id}/inspection", data=b"{}", method="POST"), timeout=2)
        assert post.value.code == 404
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_portfolio_catalog_pages_are_bounded_and_exclusive(tmp_path: Path) -> None:
    workflow_root = tmp_path / "workflow"
    portfolio_root = workflow_root / "b4-paper"
    portfolios = [
        B41Genesis.create(f"catalog-strategy-{index:02d}", "synthetic-fixture-v1", policy())
        for index in range(4)
    ]
    shared = B41Genesis.create_shared(
        "catalog-shared",
        "synthetic-fixture-v1",
        [f"shared-strategy-{index:03d}" for index in range(127)],
        policy(),
    )
    corrupt = B41Genesis.create("catalog-corrupt", "synthetic-fixture-v1", policy())
    for item in (*portfolios, shared, corrupt):
        B41Broker(portfolio_root, item, policy())
    corrupt_broker = B41Broker.open(portfolio_root, corrupt.portfolio_id)
    corrupt_broker.ledger_path.write_text("{malformed ledger record}\n", encoding="utf-8")

    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(MarketWorkflow(RunStore(workflow_root))))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        first = json.loads(urlopen(f"{base}/v1/b4/portfolios?limit=2", timeout=2).read())
        assert len(first["portfolios"]) == 2
        assert first["page"] == {
            "limit": 2,
            "after_portfolio_id": None,
            "has_more": True,
            "next_after_portfolio_id": first["portfolios"][-1]["portfolio_id"],
            "skipped_count": first["page"]["skipped_count"],
        }
        assert first["page"]["skipped_count"] >= 0
        assert all("strategy_ids" not in item for item in first["portfolios"])

        cursor = urllib.parse.quote(first["page"]["next_after_portfolio_id"])
        second = json.loads(urlopen(f"{base}/v1/b4/portfolios?limit=2&after_portfolio_id={cursor}", timeout=2).read())
        assert len(second["portfolios"]) == 2
        assert second["portfolios"][0]["portfolio_id"] > first["portfolios"][-1]["portfolio_id"]
        assert second["page"]["has_more"] is True

        cursor = urllib.parse.quote(second["page"]["next_after_portfolio_id"])
        last = json.loads(urlopen(f"{base}/v1/b4/portfolios?limit=2&after_portfolio_id={cursor}", timeout=2).read())
        assert len(last["portfolios"]) == 1
        assert last["page"]["has_more"] is False
        shared_row = next(item for item in (*first["portfolios"], *second["portfolios"], *last["portfolios"]) if item["mode"] == "shared")
        assert shared_row["member_count"] == 127

        html_page = urlopen(f"{base}/operator/?limit=2&after_portfolio_id={cursor}", timeout=2).read().decode("utf-8")
        assert last["portfolios"][0]["portfolio_id"] in html_page
        assert 'aria-label="Portfolio pages"' in html_page
        assert 'href="/operator/?limit=2" aria-label="First portfolio page"' in html_page
        assert '</span> <a href="/operator/?limit=2"' in html_page
        assert "/operator/" in html_page

        complete = json.loads(urlopen(f"{base}/v1/b4/portfolios?limit=100", timeout=2).read())
        assert len(complete["portfolios"]) == 5
        assert complete["page"]["skipped_count"] == 1
        warning_html = urlopen(f"{base}/operator/?limit=100", timeout=2).read().decode("utf-8")
        assert "Skipped 1 unreadable portfolio candidate while filling this page." in warning_html

        for query in (
            "limit=101",
            "limit=2&limit=3",
            "after_portfolio_id=missing",
            f"after_portfolio_id={corrupt.portfolio_id}",
            "unknown=1",
        ):
            with pytest.raises(HTTPError) as invalid:
                urlopen(f"{base}/v1/b4/portfolios?{query}", timeout=2)
            assert invalid.value.code == 400
        with pytest.raises(HTTPError) as invalid_html_cursor:
            urlopen(f"{base}/operator/?limit=2&after_portfolio_id={corrupt.portfolio_id}", timeout=2)
        assert invalid_html_cursor.value.code == 400
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_portfolio_catalog_does_not_provision_a_missing_writer_lock(tmp_path: Path) -> None:
    workflow_root = tmp_path / "workflow"
    portfolio_root = workflow_root / "b4-paper"
    portfolio = genesis()
    broker = B41Broker(portfolio_root, portfolio, policy())
    lock_path = broker.lock_path
    lock_path.unlink()
    persisted_files = {path.name: path.read_bytes() for path in broker.root.iterdir() if path.is_file()}
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(MarketWorkflow(RunStore(workflow_root))))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        payload = json.loads(urlopen(f"http://127.0.0.1:{server.server_port}/v1/b4/portfolios?limit=100", timeout=2).read())
        assert payload["portfolios"] == []
        assert payload["page"]["skipped_count"] == 1
        assert not lock_path.exists()
        assert {path.name: path.read_bytes() for path in broker.root.iterdir() if path.is_file()} == persisted_files
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_btc_dataset_catalog_is_bounded_read_only_and_does_not_initialize_empty_store(tmp_path: Path) -> None:
    workflow_root = tmp_path / "workflow"
    history_root = workflow_root / "btc-history"
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(MarketWorkflow(RunStore(workflow_root))))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}/v1/btc/history/datasets"
    try:
        empty = json.loads(urlopen(base, timeout=2).read())
        assert empty["api_version"] == "market-os.btc-history-catalog@v1"
        assert empty["datasets"] == []
        assert empty["page"] == {
            "limit": 25,
            "after_dataset_revision": None,
            "has_more": False,
            "next_after_dataset_revision": None,
        }
        assert not history_root.exists()

        store = HistoryStore(history_root)
        fixture_template = json.loads(BTC_HISTORY_FIXTURE.read_text(encoding="utf-8"))
        revisions = []
        for index in range(3):
            fixture = json.loads(json.dumps(fixture_template))
            fixture["pages"][0][0][5] = f"10.{index + 1}"
            revisions.append(store.ingest_fixture(fixture).dataset_revision)
        expected = sorted(revisions)
        catalog_path = history_root / "catalog.duckdb"
        catalog_mtime = catalog_path.stat().st_mtime_ns

        first = json.loads(urlopen(f"{base}?limit=2", timeout=2).read())
        assert [item["dataset_revision"] for item in first["datasets"]] == expected[:2]
        assert first["page"] == {
            "limit": 2,
            "after_dataset_revision": None,
            "has_more": True,
            "next_after_dataset_revision": expected[1],
        }
        assert "parquet_path" not in first["datasets"][0]
        assert "parquet_sha256" not in first["datasets"][0]

        cursor = urllib.parse.quote(first["page"]["next_after_dataset_revision"])
        second = json.loads(urlopen(f"{base}?limit=2&after_dataset_revision={cursor}", timeout=2).read())
        assert [item["dataset_revision"] for item in second["datasets"]] == expected[2:]
        assert second["page"]["has_more"] is False
        assert second["page"]["next_after_dataset_revision"] is None
        assert catalog_path.stat().st_mtime_ns == catalog_mtime

        for query in (
            "limit=101",
            "limit=2&limit=3",
            "after_dataset_revision=invalid",
            "unknown=1",
            "store_root=outside",
        ):
            with pytest.raises(HTTPError) as invalid:
                urlopen(f"{base}?{query}", timeout=2)
            assert invalid.value.code == 400
        with pytest.raises(HTTPError) as missing_cursor:
            urlopen(f"{base}?after_dataset_revision=btc-history-00000000000000000000", timeout=2)
        assert missing_cursor.value.code == 404
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_btc_dataset_catalog_rejects_malformed_store_and_unrenderable_timestamps(tmp_path: Path) -> None:
    workflow_root = tmp_path / "workflow"
    history_root = workflow_root / "btc-history"
    history_root.parent.mkdir(parents=True)
    history_root.write_text("not a HistoryStore directory", encoding="utf-8")
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(MarketWorkflow(RunStore(workflow_root))))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}/v1/btc/history/datasets"
    try:
        with pytest.raises(HTTPError) as malformed_store:
            urlopen(base, timeout=2)
        assert malformed_store.value.code == 409
        assert json.loads(malformed_store.value.read())["error"]["code"] == "btc_history_catalog_integrity_error"

        history_root.unlink()
        store = HistoryStore(history_root)
        fixture = json.loads(BTC_HISTORY_FIXTURE.read_text(encoding="utf-8"))
        dataset = store.ingest_fixture(fixture)
        with store._connect() as db:
            db.execute(
                "UPDATE datasets SET last_close_time_ms=? WHERE dataset_revision=?",
                [8_640_000_000_000_001, dataset.dataset_revision],
            )

        with pytest.raises(HTTPError) as invalid_timestamp:
            urlopen(base, timeout=2)
        assert invalid_timestamp.value.code == 409
        assert json.loads(invalid_timestamp.value.read())["error"]["code"] == "btc_history_catalog_integrity_error"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_btc_manifest_pages_and_detail_are_bounded_read_only_and_hash_checked(tmp_path: Path) -> None:
    workflow_root = tmp_path / "workflow"
    history_root = workflow_root / "btc-history"
    store = HistoryStore(history_root)
    fixture = json.loads(BTC_HISTORY_FIXTURE.read_text(encoding="utf-8"))
    first = store.ingest_fixture(fixture)
    second = store._ingest_pages(
        fixture["pages"],
        captured_at=fixture["received_at"],
        as_of_ms=fixture["as_of_ms"],
        requested_start_ms=fixture["requested_start_ms"],
        requested_end_ms=fixture["requested_end_ms_exclusive"],
        endpoint_class="synthetic-fixture",
        source_identity="binance.spot.rest.klines.synthetic-fixture-retry",
    )
    assert second.dataset_revision == first.dataset_revision
    assert second.manifest_id != first.manifest_id
    catalog_path = history_root / "catalog.duckdb"
    catalog_mtime = catalog_path.stat().st_mtime_ns

    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(MarketWorkflow(RunStore(workflow_root))))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}/v1/btc/history/datasets/{first.dataset_revision}/manifests"
    try:
        first_page = json.loads(urlopen(f"{base}?limit=1", timeout=2).read())
        assert first_page["api_version"] == "market-os.btc-history-manifests@v1"
        assert len(first_page["manifests"]) == 1
        assert first_page["page"]["has_more"] is True
        cursor = first_page["page"]["next_after_manifest_id"]
        assert cursor == first_page["manifests"][0]["manifest_id"]

        second_page = json.loads(urlopen(f"{base}?limit=1&after_manifest_id={cursor}", timeout=2).read())
        assert len(second_page["manifests"]) == 1
        assert second_page["page"]["has_more"] is False
        assert second_page["manifests"][0]["manifest_id"] != cursor
        assert second_page["dataset_revision"] == first.dataset_revision

        detail_url = f"{base}/{first.manifest_id}"
        detail_response = json.loads(urlopen(detail_url, timeout=2).read())
        detail = detail_response["manifest"]
        assert detail_response["api_version"] == "market-os.btc-history-manifests@v1"
        assert detail["manifest_id"] == first.manifest_id
        assert detail["dataset_revision"] == first.dataset_revision
        assert detail["canonical_candle_count"] == 10
        assert detail["raw_page_count"] == 1
        original_manifest = json.loads((history_root / "manifests" / f"{first.manifest_id}.json").read_text(encoding="utf-8"))
        assert detail["gap_count"] == len(original_manifest["gaps"])
        assert detail["endpoint_class"] == "synthetic-fixture"
        assert not {"raw_page_fingerprints", "gaps", "parent_revisions", "parquet_path", "manifest_path"} & set(detail)

        for query in (
            "limit=101",
            "limit=1&limit=2",
            "after_manifest_id=invalid",
            "unknown=1",
            "store_root=outside",
        ):
            with pytest.raises(HTTPError) as invalid:
                urlopen(f"{base}?{query}", timeout=2)
            assert invalid.value.code == 400
        with pytest.raises(HTTPError) as wrong_dataset:
            wrong_dataset_url = base.replace(first.dataset_revision, "btc-history-00000000000000000000") + f"/{first.manifest_id}"
            urlopen(wrong_dataset_url, timeout=2)
        assert wrong_dataset.value.code == 404
        with pytest.raises(HTTPError) as detail_query:
            urlopen(f"{detail_url}?unknown=1", timeout=2)
        assert detail_query.value.code == 400
        assert catalog_path.stat().st_mtime_ns == catalog_mtime

        manifest_path = history_root / "manifests" / f"{first.manifest_id}.json"
        manifest_path.write_bytes(manifest_path.read_bytes() + b" ")
        with pytest.raises(HTTPError) as tampered:
            urlopen(detail_url, timeout=2)
        assert tampered.value.code == 409
        error = json.loads(tampered.value.read())["error"]
        assert error["code"] == "btc_history_manifests_integrity_error"
        assert "manifests" not in error["message"]

        manifest_path.write_bytes(b"x" * (MAX_MANIFEST_INSPECTION_BYTES + 1))
        with pytest.raises(HTTPError) as oversized:
            urlopen(detail_url, timeout=2)
        assert oversized.value.code == 409
        assert json.loads(oversized.value.read())["error"]["code"] == "btc_history_manifests_integrity_error"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_btc_manifest_route_normalizes_configured_store_path_resolution_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow_root = tmp_path / "workflow"
    store = HistoryStore(workflow_root / "btc-history")
    fixture = json.loads(BTC_HISTORY_FIXTURE.read_text(encoding="utf-8"))
    dataset = store.ingest_fixture(fixture)
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(MarketWorkflow(RunStore(workflow_root))))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}/v1/btc/history/datasets/{dataset.dataset_revision}/manifests"
    original_resolve = Path.resolve

    def fail_store_resolution(path: Path, *args: object, **kwargs: object) -> Path:
        if path == workflow_root:
            raise RuntimeError(f"symlink loop at {workflow_root}")
        return original_resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", fail_store_resolution)
    try:
        with pytest.raises(HTTPError) as invalid_path:
            urlopen(base, timeout=2)
        assert invalid_path.value.code == 409
        error = json.loads(invalid_path.value.read())["error"]
        assert error["code"] == "btc_history_manifests_integrity_error"
        assert str(workflow_root) not in error["message"]
        assert "symlink loop" not in error["message"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_btc_dataset_candle_pages_are_bounded_and_use_the_configured_store(tmp_path: Path) -> None:
    workflow_root = tmp_path / "workflow"
    history_root = workflow_root / "btc-history"
    store = HistoryStore(history_root)
    fixture = json.loads(BTC_HISTORY_FIXTURE.read_text(encoding="utf-8"))
    dataset = store.ingest_fixture(fixture)
    expected = store.inspect_candles(dataset.dataset_revision)
    catalog_path = history_root / "catalog.duckdb"
    catalog_mtime = catalog_path.stat().st_mtime_ns

    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(MarketWorkflow(RunStore(workflow_root))))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}/v1/btc/history/datasets/{dataset.dataset_revision}/candles"
    try:
        first = json.loads(urlopen(f"{base}?limit=3", timeout=2).read())
        assert first["api_version"] == "market-os.btc-history-candles@v1"
        assert first["dataset"]["dataset_revision"] == dataset.dataset_revision
        assert len(first["candles"]) == 3
        assert first["candles"][0]["open"] == expected[0]["open_decimal"]
        assert first["page"] == {
            "limit": 3,
            "after_open_time_ms": None,
            "has_more": True,
            "next_after_open_time_ms": expected[2]["open_time_ms"],
        }
        assert all("parquet_path" not in candle and "canonical_fingerprint" not in candle for candle in first["candles"])

        cursor = first["page"]["next_after_open_time_ms"]
        second = json.loads(urlopen(f"{base}?limit=3&after_open_time_ms={cursor}", timeout=2).read())
        assert [candle["open_time_ms"] for candle in second["candles"]] == [
            candle["open_time_ms"] for candle in expected[3:6]
        ]
        assert second["page"]["after_open_time_ms"] == cursor
        assert second["page"]["has_more"] is True

        for query in (
            "limit=101",
            "limit=2&limit=3",
            "after_open_time_ms=8640000000000001",
            "store_root=outside",
            "unknown=1",
        ):
            with pytest.raises(HTTPError) as invalid:
                urlopen(f"{base}?{query}", timeout=2)
            assert invalid.value.code == 400
        with pytest.raises(HTTPError) as missing_cursor:
            urlopen(f"{base}?after_open_time_ms={expected[-1]['open_time_ms'] + 1}", timeout=2)
        assert missing_cursor.value.code == 404
        assert catalog_path.stat().st_mtime_ns == catalog_mtime

        with store._connect() as db:
            db.execute(
                "UPDATE datasets SET parquet_path=? WHERE dataset_revision=?",
                ["../outside.parquet", dataset.dataset_revision],
            )
        with pytest.raises(HTTPError) as invalid_parquet_path:
            urlopen(base, timeout=2)
        assert invalid_parquet_path.value.code == 409

        with store._connect() as db:
            db.execute(
                "UPDATE datasets SET parquet_path=? WHERE dataset_revision=?",
                [f"datasets/{dataset.dataset_revision}/candles.parquet", dataset.dataset_revision],
            )
        parquet_path = history_root / "datasets" / dataset.dataset_revision / "candles.parquet"
        parquet_path.write_bytes(parquet_path.read_bytes() + b"tampered")
        with pytest.raises(HTTPError) as invalid_parquet_hash:
            urlopen(base, timeout=2)
        assert invalid_parquet_hash.value.code == 409
        error = json.loads(invalid_parquet_hash.value.read())["error"]
        assert error["code"] == "btc_history_candles_integrity_error"
        assert "candles.parquet" not in error["message"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_btc_dataset_candle_page_rejects_path_resolution_loop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workflow_root = tmp_path / "workflow"
    history_root = workflow_root / "btc-history"
    store = HistoryStore(history_root)
    fixture = json.loads(BTC_HISTORY_FIXTURE.read_text(encoding="utf-8"))
    dataset = store.ingest_fixture(fixture)
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(MarketWorkflow(RunStore(workflow_root))))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}/v1/btc/history/datasets/{dataset.dataset_revision}/candles"
    original_resolve = Path.resolve

    def fail_dataset_resolution(path: Path, *args, **kwargs):
        if path.name == "datasets" and path.parent == history_root:
            raise RuntimeError("symlink loop")
        return original_resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", fail_dataset_resolution)
    try:
        with pytest.raises(HTTPError) as invalid_path:
            urlopen(base, timeout=2)
        assert invalid_path.value.code == 409
        error = json.loads(invalid_path.value.read())["error"]
        assert error["code"] == "btc_history_candles_integrity_error"
        assert "symlink loop" not in error["message"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_catalog_state_change_returns_conflict(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workflow_root = tmp_path / "workflow"
    portfolio = B41Genesis.create("catalog-race", "synthetic-fixture-v1", policy())
    B41Broker(workflow_root / "b4-paper", portfolio, policy())
    original = B41Broker.inspect_summary_compact

    def stale_summary(broker: B41Broker) -> dict[str, object]:
        if broker.genesis.portfolio_id == portfolio.portfolio_id:
            raise BrokerStale("stale portfolio snapshot; reload before inspection")
        return original(broker)

    monkeypatch.setattr(B41Broker, "inspect_summary_compact", stale_summary)
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(MarketWorkflow(RunStore(workflow_root))))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    encoded_cursor = urllib.parse.quote(portfolio.portfolio_id)
    try:
        for path in (
            "/v1/b4/portfolios",
            f"/v1/b4/portfolios?after_portfolio_id={encoded_cursor}",
            "/operator/",
            f"/operator/?after_portfolio_id={encoded_cursor}",
        ):
            with pytest.raises(HTTPError) as conflict:
                urlopen(f"{base}{path}", timeout=2)
            assert conflict.value.code == 409
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_legacy_portfolio_resources_are_bounded_with_cursors(tmp_path: Path) -> None:
    member_ids = [f"legacy-strategy-{index:03d}" for index in range(27)]
    portfolio = B41Genesis.create_shared("legacy-pages", "synthetic-fixture-v1", member_ids, policy())
    source = tmp_path / "source" / portfolio.portfolio_id
    broker = B41Broker(source.parent, portfolio, policy())
    for index in range(27):
        order_id = f"legacy-order-{index:03d}"
        order = B41Order(
            portfolio.portfolio_id,
            order_id,
            f"cmd-{order_id}",
            f"key-{order_id}",
            BUY,
            LIMIT,
            Decimal("0.1"),
            Decimal("100"),
            900,
            strategy_id=member_ids[index],
        )
        assert broker.submit_order(order, approval(order))["state"] == "open"
    rejected_order = B41Order(
        portfolio.portfolio_id,
        "legacy-rejected-order",
        "cmd-legacy-rejected-order",
        "key-legacy-rejected-order",
        BUY,
        LIMIT,
        Decimal("0.1000001"),
        Decimal("100"),
        900,
        strategy_id=member_ids[0],
    )
    assert broker.submit_order(rejected_order, approval(rejected_order))["state"] == "rejected"

    workflow_root = tmp_path / "workflow"
    _copy_portfolio(source, workflow_root / "b4-paper" / portfolio.portfolio_id)
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(MarketWorkflow(RunStore(workflow_root))))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}/v1/b4/portfolios/{portfolio.portfolio_id}"
    try:
        genesis = json.loads(urlopen(f"{base}/genesis?member_limit=10", timeout=2).read())
        assert len(genesis["member_strategy_ids"]) == 10
        assert genesis["members_page"]["total_count"] == 27
        assert genesis["members_page"]["has_more"] is True

        reservations = json.loads(urlopen(f"{base}/reservations?reservation_limit=10", timeout=2).read())
        assert len(reservations["reservations"]) == 10
        assert reservations["page"]["total_count"] == 27
        assert reservations["page"]["has_more"] is True

        orders = json.loads(urlopen(f"{base}/orders?order_limit=10", timeout=2).read())
        assert len(orders["orders"]) == 10
        assert orders["page"]["has_more"] is True

        approvals = json.loads(urlopen(f"{base}/approvals?approval_limit=10", timeout=2).read())
        assert len(approvals["records"]) == 10
        assert approvals["page"]["total_count"] == 28
        assert approvals["page"]["has_more"] is True

        risk = json.loads(urlopen(f"{base}/risk?risk_limit=10", timeout=2).read())
        assert len(risk["records"]) == 1
        assert risk["records"][0]["result"]["reason_code"] == "order.quantity_step"
        assert risk["page"]["total_count"] == 1

        fills = json.loads(urlopen(f"{base}/fills?fill_limit=10", timeout=2).read())
        assert fills["fills"] == []
        assert fills["page"]["total_count"] == 0
        assert fills["page"]["has_more"] is False

        ledger = json.loads(urlopen(f"{base}/ledger?ledger_limit=10", timeout=2).read())
        assert len(ledger["events"]) == 10
        assert ledger["page"]["has_more"] is True

        older_cursor = ledger["page"]["next_before_sequence"]
        older = json.loads(urlopen(f"{base}/ledger?ledger_limit=10&ledger_before_sequence={older_cursor}", timeout=2).read())
        assert len(older["events"]) == 10
        assert older["events"][-1]["sequence"] < ledger["events"][0]["sequence"]

        compact = json.loads(urlopen(f"{base}/summary", timeout=2).read())
        assert "event_cursor" not in compact
        assert compact["market_event_count"] == 0

        aggregate = json.loads(urlopen(
            f"{base}/inspection?member_limit=10&reservation_limit=10&order_limit=10&risk_limit=10",
            timeout=2,
        ).read())
        assert aggregate["api_version"] == "market-os.b4-portfolio-inspection@v1"
        assert len(aggregate["genesis"]["member_strategy_ids"]) == 10
        assert len(aggregate["reservations"]["reservations"]) == 10
        assert len(aggregate["orders"]["orders"]) == 10
        assert aggregate["genesis"]["members_page"]["total_count"] == 27
        assert aggregate["reservations"]["page"]["total_count"] == 27
        assert len(aggregate["risk"]["records"]) == 1

        with pytest.raises(HTTPError) as unbounded_snapshot:
            urlopen(f"{base}/snapshot", timeout=2)
        assert unbounded_snapshot.value.code == 400
        with pytest.raises(HTTPError) as invalid_cursor:
            urlopen(f"{base}/reservations?reservation_before_order_id=missing", timeout=2)
        assert invalid_cursor.value.code == 400
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
