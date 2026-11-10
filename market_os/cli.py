"""CLI transport for the same workflow exposed by the service API."""
from __future__ import annotations

import argparse
import json
import os
import re

from .api import serve
from .metrics import MetricsRegistry
from .store import RunStore
from .u55_access import U55AccessConfig
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
    inspect.add_argument("--resource", choices=("run", "documents", "passages", "claims", "unsupported-claims", "passage-claims", "citations", "research-brief", "model-summary", "inferences", "lineage"), default="run")
    inspect.add_argument("--id", dest="item_id")
    research_brief = commands.add_parser("research-brief")
    research_brief.add_argument("--source", required=True, help="validated cited-research JSON artifact")
    research_brief.add_argument("--markdown", required=True)
    research_brief.add_argument("--json", dest="json_path", required=True)
    benchmark = commands.add_parser("benchmark")
    benchmark_commands = benchmark.add_subparsers(dest="benchmark_command", required=True)
    benchmark_run = benchmark_commands.add_parser("run")
    benchmark_run.add_argument("--store-root", default=os.environ.get("MARKET_OS_STORE_ROOT", ".market_os"))
    benchmark_run.add_argument("--fixture", required=True)
    benchmark_report = benchmark_commands.add_parser("report")
    benchmark_report.add_argument("--store-root", default=os.environ.get("MARKET_OS_STORE_ROOT", ".market_os"))
    benchmark_report.add_argument("--fixture", required=True)
    benchmark_report.add_argument("--markdown", required=True)
    benchmark_report.add_argument("--json", dest="json_path", required=True)
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
    btc_catalog = btc_commands.add_parser("catalog")
    btc_catalog.add_argument("--limit", type=int, default=25)
    btc_catalog.add_argument("--after-dataset-revision")
    btc_catalog.add_argument("--store-root", default=os.environ.get("MARKET_OS_BTC_STORE_ROOT", ".market_os/btc-history"))
    btc_manifests = btc_commands.add_parser("manifests")
    btc_manifests.add_argument("dataset_revision")
    btc_manifests.add_argument("--limit", type=int, default=25)
    btc_manifests.add_argument("--after-manifest-id")
    btc_manifests.add_argument("--store-root", default=os.environ.get("MARKET_OS_BTC_STORE_ROOT", ".market_os/btc-history"))
    btc_manifest = btc_commands.add_parser("manifest")
    btc_manifest.add_argument("dataset_revision")
    btc_manifest.add_argument("manifest_id")
    btc_manifest.add_argument("--store-root", default=os.environ.get("MARKET_OS_BTC_STORE_ROOT", ".market_os/btc-history"))
    btc_manifest_records = btc_commands.add_parser("manifest-records")
    btc_manifest_records.add_argument("dataset_revision")
    btc_manifest_records.add_argument("manifest_id")
    btc_manifest_records.add_argument("resource", choices=("outcomes", "gaps", "provenance"))
    btc_manifest_records.add_argument("--limit", type=int, default=25)
    btc_manifest_records.add_argument("--after-outcome-index")
    btc_manifest_records.add_argument("--after-start-time-ms")
    btc_manifest_records.add_argument("--after-raw-page-sha256")
    btc_manifest_records.add_argument("--after-row-index")
    btc_manifest_records.add_argument("--store-root", default=os.environ.get("MARKET_OS_BTC_STORE_ROOT", ".market_os/btc-history"))
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
    b2_catalog = b2_commands.add_parser("catalog")
    b2_catalog.add_argument("--limit", type=int, default=25)
    b2_catalog.add_argument("--after-run-id")
    b2_catalog.add_argument("--store-root", default=os.environ.get("MARKET_OS_BTC_B2_STORE_ROOT", ".market_os/btc-b2"))
    b2_detail = b2_commands.add_parser("detail")
    b2_detail.add_argument("run_id")
    b2_detail.add_argument("--store-root", default=os.environ.get("MARKET_OS_BTC_B2_STORE_ROOT", ".market_os/btc-b2"))
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
    b3_catalog = b3_commands.add_parser("catalog")
    b3_catalog.add_argument("--limit", type=int, default=25)
    b3_catalog.add_argument("--after-run-id")
    b3_catalog.add_argument("--store-root", default=os.environ.get("MARKET_OS_BTC_B3_STORE_ROOT", ".market_os/btc-b3"))
    b3_detail = b3_commands.add_parser("detail")
    b3_detail.add_argument("run_id")
    b3_detail.add_argument("--store-root", default=os.environ.get("MARKET_OS_BTC_B3_STORE_ROOT", ".market_os/btc-b3"))
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
    b4 = commands.add_parser("b4-paper")
    b4_commands = b4.add_subparsers(dest="b4_command", required=True)
    b4_inspect = b4_commands.add_parser("inspect")
    b4_inspect.add_argument("portfolio_id")
    b4_inspect.add_argument("--resource", choices=("summary", "snapshot", "orders", "fills", "ledger", "risk", "approvals", "fingerprints", "replay", "policy", "genesis"), default="summary")
    b4_inspect.add_argument("--id", dest="item_id")
    b4_inspect.add_argument("--store-root", default=os.environ.get("MARKET_OS_B4_STORE_ROOT", ".market_os/b4-paper"))
    b4_backup = b4_commands.add_parser("backup")
    b4_backup.add_argument("portfolio_id")
    b4_backup.add_argument("--archive", required=True)
    b4_backup.add_argument("--store-root", default=os.environ.get("MARKET_OS_B4_STORE_ROOT", ".market_os/b4-paper"))
    b4_restore = b4_commands.add_parser("restore")
    b4_restore.add_argument("--archive", required=True)
    b4_restore.add_argument("--store-root", default=os.environ.get("MARKET_OS_B4_STORE_ROOT", ".market_os/b4-paper"))
    b4_migration = b4_commands.add_parser("migration-check")
    b4_migration.add_argument("portfolio_id")
    b4_migration.add_argument("--store-root", default=os.environ.get("MARKET_OS_B4_STORE_ROOT", ".market_os/b4-paper"))
    synthetic = commands.add_parser("synthetic")
    synthetic_commands = synthetic.add_subparsers(dest="synthetic_command", required=True)
    synthetic_run = synthetic_commands.add_parser("run")
    synthetic_run.add_argument("--fixture", required=True)
    synthetic_run.add_argument("--output", required=True)
    synthetic_report = synthetic_commands.add_parser("report")
    synthetic_report.add_argument("--fixture", required=True)
    synthetic_report.add_argument("--output-dir", required=True)
    synthetic_report.add_argument("--session-id", default="synthetic-session")
    synthetic_report.add_argument("--markdown")
    synthetic_report.add_argument("--json", dest="json_path")
    synthetic_economic = synthetic_commands.add_parser("economic-report")
    synthetic_economic.add_argument("--fixture", required=True)
    synthetic_economic.add_argument("--markdown", required=True)
    synthetic_economic.add_argument("--json", dest="json_path", required=True)
    synthetic_serve = synthetic_commands.add_parser("serve")
    synthetic_serve.add_argument("--store-root", required=True)
    synthetic_serve.add_argument("--host", default="127.0.0.1")
    synthetic_serve.add_argument("--port", type=int, default=8790)
    synthetic_inspect = synthetic_commands.add_parser("inspect")
    synthetic_inspect.add_argument("--replay-report", required=True)
    synthetic_inspect.add_argument("--resource", choices=("replay", "accounting"), default="accounting")
    synthetic_catalog = synthetic_commands.add_parser("catalog")
    synthetic_catalog.add_argument("--store-root", required=True)
    synthetic_compare = synthetic_commands.add_parser("compare")
    synthetic_compare.add_argument("--store-root", required=True)
    synthetic_compare.add_argument("--left", required=True)
    synthetic_compare.add_argument("--right", required=True)
    tools = commands.add_parser("tools")
    tools_commands = tools.add_subparsers(dest="tools_command", required=True)
    tools_report = tools_commands.add_parser("report")
    tools_report.add_argument("--fixture", required=True)
    tools_report.add_argument("--markdown", required=True)
    tools_report.add_argument("--json", dest="json_path", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "serve":
        workflow = MarketWorkflow(RunStore(args.store_root))
        serve(
            workflow,
            args.host,
            args.port,
            request_timeout=args.request_timeout,
            service_log_path=args.service_log,
            connected_access=U55AccessConfig.from_environment(),
            metrics=MetricsRegistry(),
        )
        return 0
    if args.command == "inspect":
        workflow = MarketWorkflow(RunStore(args.store_root))
        if args.resource == "run":
            result = workflow.inspect_run(args.run_id)
        else:
            result = workflow.inspect_resource(args.run_id, args.resource, args.item_id)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    if args.command == "research-brief":
        from .research_brief import render_research_brief_files

        result = render_research_brief_files(args.source, args.markdown, args.json_path)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    if args.command == "benchmark":
        from .quality_benchmark import BenchmarkStore, run_quality_benchmark

        if args.benchmark_command == "run":
            result = run_quality_benchmark(args.store_root, args.fixture)
        elif args.benchmark_command == "report":
            from .quality_report import render_quality_report

            benchmark = run_quality_benchmark(args.store_root, args.fixture)
            result = render_quality_report(benchmark, markdown_path=args.markdown, json_path=args.json_path)
        else:
            result = BenchmarkStore(args.store_root).inspect(args.benchmark_id, args.resource, args.item_id)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    if args.command == "b4-paper":
        from .portfolio_broker import B41Broker
        from .portfolio_backup import backup_portfolio, restore_portfolio
        from .portfolio_migration import preflight_portfolio

        try:
            if args.b4_command == "inspect":
                result = B41Broker.open(args.store_root, args.portfolio_id, read_only=True).inspect_jsonable(args.resource, args.item_id)
            elif args.b4_command == "backup":
                result = {"archive": str(backup_portfolio(args.store_root, args.portfolio_id, args.archive))}
            elif args.b4_command == "restore":
                result = {"portfolio_root": str(restore_portfolio(args.archive, args.store_root))}
            else:
                result = preflight_portfolio(args.store_root, args.portfolio_id)
        except (KeyError, OSError, TypeError, ValueError) as exc:
            raise SystemExit(f"B4 portfolio inspection failed: {exc}") from exc
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    if args.command == "synthetic":
        from pathlib import Path
        from .strategy_replay import StrategyReplayReport
        from .accounting import build_synthetic_accounting_report
        from .synthetic_catalog import catalog_sessions, compare_sessions
        from .synthetic_session_api import SyntheticSessionStore
        from .synthetic_session import load_synthetic_fixture, run_synthetic_fixture, write_synthetic_session_run
        from .synthetic_session_report import render_synthetic_session_report
        from .synthetic_server import serve_synthetic

        if args.synthetic_command == "run":
            try:
                result = write_synthetic_session_run(run_synthetic_fixture(load_synthetic_fixture(args.fixture)), args.output)
            except (OSError, TypeError, ValueError) as exc:
                raise SystemExit(f"synthetic session failed: {exc}") from exc
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        if args.synthetic_command == "report":
            try:
                root = Path(args.output_dir).resolve()
                session_dir = root / args.session_id
                fixture = load_synthetic_fixture(args.fixture)
                first_run = run_synthetic_fixture(fixture)
                second_run = run_synthetic_fixture(fixture)
                deterministic_replay = (
                    first_run.replay.fingerprint == second_run.replay.fingerprint
                    and first_run.accounting.fingerprint == second_run.accounting.fingerprint
                )
                write_synthetic_session_run(
                    first_run,
                    session_dir,
                )
                result = render_synthetic_session_report(
                    SyntheticSessionStore(root),
                    args.session_id,
                    markdown_path=args.markdown or root / "synthetic-session-report.md",
                    json_path=args.json_path or root / "synthetic-session-report.json",
                    deterministic_replay=deterministic_replay,
                )
            except (KeyError, OSError, TypeError, ValueError) as exc:
                raise SystemExit(f"synthetic session report failed: {exc}") from exc
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        if args.synthetic_command == "economic-report":
            from .synthetic_economic_report import render_synthetic_economic_report

            try:
                result = render_synthetic_economic_report(
                    args.fixture,
                    markdown_path=args.markdown,
                    json_path=args.json_path,
                )
            except (OSError, TypeError, ValueError) as exc:
                raise SystemExit(f"synthetic economic report failed: {exc}") from exc
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        if args.synthetic_command == "serve":
            try:
                serve_synthetic(args.store_root, args.host, args.port)
            except (OSError, TypeError, ValueError) as exc:
                raise SystemExit(f"synthetic server failed: {exc}") from exc
            return 0
        if args.synthetic_command == "catalog":
            try:
                result = catalog_sessions(SyntheticSessionStore(args.store_root))
            except (KeyError, OSError, TypeError, ValueError) as exc:
                raise SystemExit(f"synthetic catalog failed: {exc}") from exc
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        if args.synthetic_command == "compare":
            try:
                result = compare_sessions(SyntheticSessionStore(args.store_root), args.left, args.right)
            except (KeyError, OSError, TypeError, ValueError) as exc:
                raise SystemExit(f"synthetic comparison failed: {exc}") from exc
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0

        try:
            payload = json.loads(Path(args.replay_report).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise SystemExit(f"cannot read synthetic replay report: {exc}") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("fingerprint"), str):
            raise SystemExit("synthetic replay report must contain a top-level fingerprint")
        fingerprint = payload.pop("fingerprint")
        try:
            canonical_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
            replay_report = StrategyReplayReport(canonical_payload, fingerprint)
            result = replay_report.to_dict() if args.resource == "replay" else build_synthetic_accounting_report(replay_report).to_dict()
        except (TypeError, ValueError) as exc:
            raise SystemExit(f"invalid synthetic replay report: {exc}") from exc
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    if args.command == "tools":
        from .tool_registry_report import render_tool_registry_report

        try:
            result = render_tool_registry_report(
                args.fixture,
                markdown_path=args.markdown,
                json_path=args.json_path,
            )
        except (OSError, TypeError, ValueError) as exc:
            raise SystemExit(f"tool registry report failed: {exc}") from exc
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
        if args.btc_command == "catalog":
            from pathlib import Path

            if type(args.limit) is not int or not 1 <= args.limit <= 100:
                raise SystemExit("BTC history catalog limit must be an integer between 1 and 100")
            store_root = Path(args.store_root)
            if not (store_root / "catalog.duckdb").is_file():
                if args.after_dataset_revision is not None:
                    raise SystemExit("BTC history dataset revision not found")
                result = {
                    "datasets": [],
                    "page": {
                        "limit": args.limit,
                        "after_dataset_revision": None,
                        "has_more": False,
                        "next_after_dataset_revision": None,
                    },
                }
            else:
                result = HistoryStore(store_root, read_only=True).inspect_datasets_page(
                    limit=args.limit,
                    after_dataset_revision=args.after_dataset_revision,
                )
            print(json.dumps({"api_version": "market-os.btc-history-catalog@v1", **result}, indent=2, sort_keys=True))
            return 0
        if args.btc_command in {"manifests", "manifest", "manifest-records"}:
            from .btc_history import HistoryError, HistoryStore, MAX_CANDLES, MAX_JS_DATE_TIME_MS

            try:
                store = HistoryStore(args.store_root, read_only=True)
                if args.btc_command == "manifests":
                    if type(args.limit) is not int or not 1 <= args.limit <= 100:
                        raise HistoryError("invalid_page", "limit must be an integer between 1 and 100")
                    result = store.inspect_manifests_page(
                        args.dataset_revision,
                        limit=args.limit,
                        after_manifest_id=args.after_manifest_id,
                    )
                    api_version = "market-os.btc-history-manifests@v1"
                elif args.btc_command == "manifest":
                    result = {"manifest": store.inspect_manifest_record(args.dataset_revision, args.manifest_id)}
                    api_version = "market-os.btc-history-manifests@v1"
                else:
                    if type(args.limit) is not int or not 1 <= args.limit <= 100:
                        raise HistoryError("invalid_page", "limit must be an integer between 1 and 100")
                    cursor_flags = {
                        "outcomes": (args.after_start_time_ms, args.after_raw_page_sha256, args.after_row_index),
                        "gaps": (args.after_outcome_index, args.after_raw_page_sha256, args.after_row_index),
                        "provenance": (args.after_outcome_index, args.after_start_time_ms),
                    }
                    if any(value is not None for value in cursor_flags[args.resource]):
                        raise HistoryError("invalid_page", f"cursor does not belong to {args.resource}")

                    def decimal_cursor(raw: str | None, name: str, maximum: int, digits: int) -> int | None:
                        if raw is None:
                            return None
                        if not raw or not raw.isascii() or not raw.isdecimal() or len(raw) > digits:
                            raise HistoryError("invalid_page", f"{name} must be a bounded integer cursor")
                        value = int(raw)
                        if value > maximum:
                            raise HistoryError("invalid_page", f"{name} is outside the supported range")
                        return value

                    if args.resource == "outcomes":
                        result = store.inspect_manifest_outcomes_page(
                            args.dataset_revision,
                            args.manifest_id,
                            limit=args.limit,
                            after_outcome_index=decimal_cursor(args.after_outcome_index, "after_outcome_index", MAX_CANDLES * 2, 6),
                        )
                    elif args.resource == "gaps":
                        result = store.inspect_manifest_gaps_page(
                            args.dataset_revision,
                            args.manifest_id,
                            limit=args.limit,
                            after_start_time_ms=decimal_cursor(args.after_start_time_ms, "after_start_time_ms", MAX_JS_DATE_TIME_MS, 16),
                        )
                    else:
                        raw_hash = args.after_raw_page_sha256
                        if raw_hash is not None and re.fullmatch(r"[0-9a-f]{64}", raw_hash) is None:
                            raise HistoryError("invalid_page", "after_raw_page_sha256 must be a lowercase SHA-256 fingerprint")
                        result = store.inspect_manifest_provenance_page(
                            args.dataset_revision,
                            args.manifest_id,
                            limit=args.limit,
                            after_raw_page_sha256=raw_hash,
                            after_row_index=decimal_cursor(args.after_row_index, "after_row_index", 999, 3),
                        )
                    api_version = "market-os.btc-history-manifest-records@v1"
            except (KeyError, HistoryError, OSError, RuntimeError, TypeError, ValueError) as exc:
                label = "catalog" if args.btc_command == "manifests" else "detail" if args.btc_command == "manifest" else "records"
                raise SystemExit(f"BTC ingestion manifest {label} failed: {exc}") from exc
            print(json.dumps({"api_version": api_version, **result}, indent=2, sort_keys=True, default=str))
            return 0
        if args.btc_command == "b2":
            if args.b2_command == "catalog":
                from .btc_research_inspection import BtcResearchInspectionStore, ResearchInspectionError

                try:
                    result = BtcResearchInspectionStore(args.store_root, "b2").list_runs_page(
                        limit=args.limit,
                        after_run_id=args.after_run_id,
                    )
                except (KeyError, ResearchInspectionError, OSError, RuntimeError, TypeError, ValueError) as exc:
                    raise SystemExit(f"BTC b2 research catalog failed: {exc}") from exc
                print(json.dumps({"api_version": "market-os.btc-research-inspection@v1", **result}, indent=2, sort_keys=True, default=str))
                return 0
            if args.b2_command == "detail":
                from .btc_research_inspection import BtcResearchInspectionStore, ResearchInspectionError

                try:
                    result = BtcResearchInspectionStore(args.store_root, "b2").inspect_run(args.run_id)
                except (KeyError, ResearchInspectionError, OSError, RuntimeError, TypeError, ValueError) as exc:
                    raise SystemExit(f"BTC b2 research detail failed: {exc}") from exc
                print(json.dumps({"api_version": "market-os.btc-research-inspection@v1", **result}, indent=2, sort_keys=True, default=str))
                return 0

            from .btc_features import B2Config, B2Store, run_b2

            b2_store = B2Store(args.store_root, read_only=args.b2_command == "inspect")
            if args.b2_command == "run":
                history = HistoryStore(args.history_store_root, read_only=True)
                result = run_b2(history, args.dataset_revision, b2_store, B2Config(args.experiment_id))
            else:
                result = b2_store.inspect(args.run_id, args.resource, args.item_id)
            print(json.dumps(result, indent=2, sort_keys=True, default=str))
            return 0
        if args.btc_command == "b3":
            if args.b3_command == "catalog":
                from .btc_research_inspection import BtcResearchInspectionStore, ResearchInspectionError

                try:
                    result = BtcResearchInspectionStore(args.store_root, "b3").list_runs_page(
                        limit=args.limit,
                        after_run_id=args.after_run_id,
                    )
                except (KeyError, ResearchInspectionError, OSError, RuntimeError, TypeError, ValueError) as exc:
                    raise SystemExit(f"BTC b3 research catalog failed: {exc}") from exc
                print(json.dumps({"api_version": "market-os.btc-research-inspection@v1", **result}, indent=2, sort_keys=True, default=str))
                return 0
            if args.b3_command == "detail":
                from .btc_research_inspection import BtcResearchInspectionStore, ResearchInspectionError

                try:
                    result = BtcResearchInspectionStore(args.store_root, "b3").inspect_run(args.run_id)
                except (KeyError, ResearchInspectionError, OSError, RuntimeError, TypeError, ValueError) as exc:
                    raise SystemExit(f"BTC b3 research detail failed: {exc}") from exc
                print(json.dumps({"api_version": "market-os.btc-research-inspection@v1", **result}, indent=2, sort_keys=True, default=str))
                return 0

            from .btc_jev_evaluation import B3Store, RecordedJevAdapter, run_b3

            b3_store = B3Store(args.store_root, read_only=args.b3_command == "inspect")
            if args.b3_command == "run":
                history = HistoryStore(args.history_store_root, read_only=True)
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
            store = ConnectivityStore(args.store_root, read_only=args.connectivity_command == "inspect")
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
        store = HistoryStore(args.store_root, read_only=True)
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
