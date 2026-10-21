"""CLI transport for the same workflow exposed by the service API."""
from __future__ import annotations

import argparse
import json
import os

from .api import serve
from .store import RunStore
from .workflow import MarketWorkflow


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="market-os")
    commands = parser.add_subparsers(dest="command", required=True)
    research = commands.add_parser("research")
    research.add_argument("objective")
    research.add_argument("--symbols", nargs="+", required=True)
    research.add_argument("--start", default="2026-01-02")
    research.add_argument("--end", default="2026-01-06")
    research.add_argument("--provider", choices=("fixture", "vibe-trading", "lightrag"), default="fixture")
    research.add_argument("--backtest-provider", choices=("fixture", "vibe-trading"))
    research.add_argument("--summary-provider", choices=("deterministic-test", "openai-recorded", "openai"))
    server = commands.add_parser("serve")
    server.add_argument("--host", default=os.environ.get("MARKET_OS_HOST", "127.0.0.1"))
    server.add_argument("--port", type=int, default=int(os.environ.get("MARKET_OS_PORT", "8787")))
    server.add_argument("--store-root", default=os.environ.get("MARKET_OS_STORE_ROOT", ".market_os"))
    server.add_argument("--request-timeout", type=float, default=float(os.environ.get("MARKET_OS_REQUEST_TIMEOUT", "5")))
    server.add_argument("--service-log", default=os.environ.get("MARKET_OS_SERVICE_LOG"))
    inspect = commands.add_parser("inspect")
    inspect.add_argument("run_id")
    inspect.add_argument("--store-root", default=os.environ.get("MARKET_OS_STORE_ROOT", ".market_os"))
    inspect.add_argument("--resource", choices=("run", "documents", "passages", "claims", "unsupported-claims", "passage-claims", "citations", "model-summary", "inferences", "lineage"), default="run")
    inspect.add_argument("--id", dest="item_id")
    benchmark = commands.add_parser("benchmark")
    benchmark_commands = benchmark.add_subparsers(dest="benchmark_command", required=True)
    benchmark_run = benchmark_commands.add_parser("run")
    benchmark_run.add_argument("--store-root", default=os.environ.get("MARKET_OS_STORE_ROOT", ".market_os"))
    benchmark_run.add_argument("--fixture", required=True)
    benchmark_inspect = benchmark_commands.add_parser("inspect")
    benchmark_inspect.add_argument("benchmark_id")
    benchmark_inspect.add_argument("--store-root", default=os.environ.get("MARKET_OS_STORE_ROOT", ".market_os"))
    benchmark_inspect.add_argument(
        "--resource",
        choices=(
            "cases",
            "metrics",
            "failed-cases",
            "benchmark-failures",
            "candidate-quality-failures",
            "evaluation",
            "thresholds",
            "fingerprint",
        ),
        default="metrics",
    )
    benchmark_inspect.add_argument("--id", dest="item_id")
    btc = commands.add_parser("btc-paper")
    btc_commands = btc.add_subparsers(dest="btc_command", required=True)
    btc_replay = btc_commands.add_parser("replay")
    btc_replay.add_argument("--fixture", required=True)
    btc_ingest = btc_commands.add_parser("ingest")
    btc_ingest.add_argument("--fixture", required=True)
    btc_ingest.add_argument("--store-root", default=os.environ.get("MARKET_OS_BTC_STORE_ROOT", ".market_os/btc-history"))
    btc_acquire = btc_commands.add_parser("acquire")
    btc_acquire.add_argument("--start-ms", type=int, required=True)
    btc_acquire.add_argument("--end-ms", type=int, required=True)
    btc_acquire.add_argument("--page-size", type=int, default=1000)
    btc_acquire.add_argument("--max-pages", type=int, default=44)
    btc_acquire.add_argument("--max-requests", type=int, default=44)
    btc_acquire.add_argument("--max-rows", type=int, default=43_200)
    btc_acquire.add_argument("--max-runtime-seconds", type=int, default=900)
    btc_acquire.add_argument("--max-attempts", type=int, default=1)
    btc_acquire.add_argument("--allow-historical-ingest", action="store_true")
    btc_acquire.add_argument("--authorization-file")
    btc_acquire.add_argument("--execution-approval")
    btc_acquire.add_argument("--no-resume", action="store_true")
    btc_acquire.add_argument("--store-root", default=os.environ.get("MARKET_OS_BTC_STORE_ROOT", ".market_os/btc-history"))
    btc_readiness = btc_commands.add_parser("historical-readiness")
    btc_readiness.add_argument("--cutoff-ms", type=int, required=True)
    btc_inspect = btc_commands.add_parser("inspect")
    btc_inspect.add_argument("dataset_id")
    btc_inspect.add_argument("--resource", choices=("manifest", "candles", "outcomes", "provenance", "gaps", "replay"), default="manifest")
    btc_inspect.add_argument("--start-ms", type=int)
    btc_inspect.add_argument("--end-ms", type=int)
    btc_inspect.add_argument("--store-root", default=os.environ.get("MARKET_OS_BTC_STORE_ROOT", ".market_os/btc-history"))
    b2 = btc_commands.add_parser("b2")
    b2_commands = b2.add_subparsers(dest="b2_command", required=True)
    b2_run = b2_commands.add_parser("run")
    b2_run.add_argument("--dataset-revision", required=True)
    b2_run.add_argument("--history-store-root", default=os.environ.get("MARKET_OS_BTC_STORE_ROOT", ".market_os/btc-history"))
    b2_run.add_argument("--store-root", default=os.environ.get("MARKET_OS_BTC_B2_STORE_ROOT", ".market_os/btc-b2"))
    b2_run.add_argument("--experiment-id", default="btc-b2-offline")
    b2_inspect = b2_commands.add_parser("inspect")
    b2_inspect.add_argument("run_id")
    b2_inspect.add_argument("--resource", choices=("manifest", "config", "features", "labels", "splits", "predictions", "metrics", "calibration", "lineage", "artifacts"), default="manifest")
    b2_inspect.add_argument("--id", dest="item_id")
    b2_inspect.add_argument("--store-root", default=os.environ.get("MARKET_OS_BTC_B2_STORE_ROOT", ".market_os/btc-b2"))
    b3 = btc_commands.add_parser("b3")
    b3_commands = b3.add_subparsers(dest="b3_command", required=True)
    b3_run = b3_commands.add_parser("run")
    b3_run.add_argument("--dataset-revision", required=True)
    b3_run.add_argument("--history-store-root", default=os.environ.get("MARKET_OS_BTC_STORE_ROOT", ".market_os/btc-history"))
    b3_run.add_argument("--fixture", required=True)
    b3_run.add_argument("--store-root", default=os.environ.get("MARKET_OS_BTC_B3_STORE_ROOT", ".market_os/btc-b3"))
    b3_run.add_argument("--experiment-id", default="btc-b3-jev-offline")
    b3_inspect = b3_commands.add_parser("inspect")
    b3_inspect.add_argument("run_id")
    b3_inspect.add_argument("--resource", choices=("manifest", "config", "fixture_cases", "responses", "abstentions", "splits", "predictions", "metrics", "calibration", "control_baselines", "matched_controls", "report", "lineage", "artifacts", "fingerprints", "replay"), default="manifest")
    b3_inspect.add_argument("--id", dest="item_id")
    b3_inspect.add_argument("--store-root", default=os.environ.get("MARKET_OS_BTC_B3_STORE_ROOT", ".market_os/btc-b3"))
    connectivity = btc_commands.add_parser("connectivity")
    connectivity_commands = connectivity.add_subparsers(dest="connectivity_command", required=True)
    connectivity_offline = connectivity_commands.add_parser("offline")
    connectivity_offline.add_argument("--store-root", default=os.environ.get("MARKET_OS_BTC_CONNECTIVITY_STORE_ROOT", ".market_os/btc-connectivity"))
    connectivity_binance = connectivity_commands.add_parser("binance")
    connectivity_binance.add_argument("--operation", choices=("ticker", "kline"), required=True)
    connectivity_binance.add_argument("--allow-live-probe", action="store_true")
    connectivity_binance.add_argument("--store-root", default=os.environ.get("MARKET_OS_BTC_CONNECTIVITY_STORE_ROOT", ".market_os/btc-connectivity"))
    connectivity_jev = connectivity_commands.add_parser("jev")
    connectivity_jev.add_argument("--allow-live-probe", action="store_true")
    connectivity_jev.add_argument("--model-version", required=True)
    connectivity_jev.add_argument("--max-spend-usd", type=float, required=True)
    connectivity_jev.add_argument("--paper-only", action="store_true")
    connectivity_jev.add_argument("--store-root", default=os.environ.get("MARKET_OS_BTC_CONNECTIVITY_STORE_ROOT", ".market_os/btc-connectivity"))
    connectivity_inspect = connectivity_commands.add_parser("inspect")
    connectivity_inspect.add_argument("probe_id")
    connectivity_inspect.add_argument("--resource", choices=("manifest", "result", "fingerprints", "replay"), default="manifest")
    connectivity_inspect.add_argument("--store-root", default=os.environ.get("MARKET_OS_BTC_CONNECTIVITY_STORE_ROOT", ".market_os/btc-connectivity"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "serve":
        workflow = MarketWorkflow(RunStore(args.store_root))
        serve(workflow, args.host, args.port, request_timeout=args.request_timeout, service_log_path=args.service_log)
        return 0
    if args.command == "inspect":
        workflow = MarketWorkflow(RunStore(args.store_root))
        if args.resource == "run":
            result = workflow.inspect_run(args.run_id)
        else:
            result = workflow.inspect_resource(args.run_id, args.resource, args.item_id)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    if args.command == "benchmark":
        from .quality_benchmark import BenchmarkStore, run_quality_benchmark

        if args.benchmark_command == "run":
            result = run_quality_benchmark(args.store_root, args.fixture)
        else:
            result = BenchmarkStore(args.store_root).inspect(args.benchmark_id, args.resource, args.item_id)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    if args.command == "btc-paper":
        from dataclasses import asdict
        from pathlib import Path
        from .btc_history import HistoryStore, plan_historical_readiness
        from .btc_paper import replay_fixture

        if args.btc_command == "replay":
            try:
                fixture = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise SystemExit(f"cannot read BTC replay fixture: {exc}") from exc
            result = replay_fixture(fixture)
            print(json.dumps(asdict(result), indent=2, sort_keys=True))
            return 0
        if args.btc_command == "ingest":
            store = HistoryStore(args.store_root)
            try:
                fixture = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
                result = store.ingest_fixture(fixture)
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise SystemExit(f"cannot read BTC history fixture: {exc}") from exc
            print(json.dumps(asdict(result), indent=2, sort_keys=True))
            return 0
        if args.btc_command == "acquire":
            if not args.allow_historical_ingest:
                raise SystemExit("historical acquisition requires --allow-historical-ingest")
            if not args.authorization_file:
                raise SystemExit("historical acquisition requires --authorization-file")
            authorization_path = Path(args.authorization_file).resolve()
            required_authorization_path = (Path(__file__).resolve().parent.parent / "approved-policy.json").resolve()
            if authorization_path != required_authorization_path:
                raise SystemExit("historical acquisition requires the repository approved-policy.json")
            try:
                authorization = json.loads(authorization_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise SystemExit(f"cannot read historical authorization: {exc}") from exc
            store = HistoryStore(args.store_root)
            result = store.acquire(
                args.start_ms,
                args.end_ms,
                page_size=args.page_size,
                max_pages=args.max_pages,
                max_requests=args.max_requests,
                max_rows=args.max_rows,
                max_runtime_seconds=args.max_runtime_seconds,
                max_attempts=args.max_attempts,
                allow_historical_ingest=True,
                authorization=authorization,
                execution_approval=args.execution_approval,
                resume=not args.no_resume,
            )
            print(json.dumps(asdict(result), indent=2, sort_keys=True))
            return 0
        if args.btc_command == "historical-readiness":
            print(json.dumps(plan_historical_readiness(args.cutoff_ms), indent=2, sort_keys=True))
            return 0
        if args.btc_command == "b2":
            from .btc_b2 import B2Config, B2Store, run_b2

            b2_store = B2Store(args.store_root)
            if args.b2_command == "run":
                history = HistoryStore(args.history_store_root)
                result = run_b2(history, args.dataset_revision, b2_store, B2Config(args.experiment_id))
            else:
                result = b2_store.inspect(args.run_id, args.resource, args.item_id)
            print(json.dumps(result, indent=2, sort_keys=True, default=str))
            return 0
        if args.btc_command == "b3":
            from .btc_b3 import B3Store, RecordedJevAdapter, run_b3

            b3_store = B3Store(args.store_root)
            if args.b3_command == "run":
                history = HistoryStore(args.history_store_root)
                result = run_b3(history, args.dataset_revision, RecordedJevAdapter.from_path(args.fixture), b3_store, experiment_id=args.experiment_id)
            else:
                result = b3_store.inspect(args.run_id, args.resource, args.item_id)
            print(json.dumps(result, indent=2, sort_keys=True, default=str))
            return 0
        if args.btc_command == "connectivity":
            from .btc_connectivity import (
                BinancePublicAdapter,
                ConnectivityStore,
                FixtureConnectivityAdapter,
                TypeSafeHttpAdapter,
                binance_probe,
                jev_probe,
                offline_probe,
            )
            store = ConnectivityStore(args.store_root)
            fixture_root = Path(__file__).parent / "tests" / "fixtures" / "btc_connectivity"
            if args.connectivity_command == "offline":
                result = offline_probe(FixtureConnectivityAdapter.from_paths(fixture_root / "ticker.json", fixture_root / "klines.json", fixture_root / "jev_response.json"))
                persisted = store.persist(result)
                print(json.dumps(persisted, indent=2, sort_keys=True, default=str))
                return 0
            if args.connectivity_command == "inspect":
                print(json.dumps(store.inspect(args.probe_id, args.resource), indent=2, sort_keys=True, default=str))
                return 0
            if args.connectivity_command == "binance":
                if not args.allow_live_probe:
                    raise SystemExit("Binance connectivity requires --allow-live-probe")
                result = binance_probe(BinancePublicAdapter(), args.operation)
                print(json.dumps(store.persist(result), indent=2, sort_keys=True, default=str))
                return 0
            result = jev_probe(
                TypeSafeHttpAdapter(),
                model=args.model_version,
                api_key=os.environ.get("TYPESAFE_API_KEY"),
                allow_live_probe=args.allow_live_probe,
                paper_only=args.paper_only,
                max_spend_usd=args.max_spend_usd,
                reservation_path=Path(args.store_root) / "jev-live.reservation.json",
            )
            print(json.dumps(store.persist(result), indent=2, sort_keys=True, default=str))
            return 0
        store = HistoryStore(args.store_root)
        resource = args.resource
        if resource == "manifest":
            result = store.inspect_manifest(args.dataset_id)
        elif resource == "candles":
            result = store.inspect_candles(args.dataset_id, start_time_ms=args.start_ms, end_time_ms=args.end_ms)
        elif resource == "outcomes":
            result = store.inspect_outcomes(args.dataset_id)
        elif resource == "provenance":
            result = store.inspect_provenance(args.dataset_id)
        elif resource == "gaps":
            result = store.inspect_gaps(args.dataset_id)
        else:
            result = store.replay(args.dataset_id)
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
        return 0
    workflow = MarketWorkflow()
    if args.command == "research":
        from .provider_selection import selected_workflow

        if args.summary_provider is None:
            workflow = selected_workflow(workflow, args.provider, args.backtest_provider)
        else:
            workflow = selected_workflow(workflow, args.provider, args.backtest_provider, args.summary_provider)
    task = workflow.create_task(args.objective, args.symbols, args.start, args.end)
    print(json.dumps(workflow.run(task), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
