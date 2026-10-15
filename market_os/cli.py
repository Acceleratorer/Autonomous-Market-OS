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
    research.add_argument("--summary-provider", choices=("deterministic-test",))
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
    benchmark_inspect.add_argument("--resource", choices=("cases", "metrics", "failed-cases", "thresholds", "fingerprint"), default="metrics")
    benchmark_inspect.add_argument("--id", dest="item_id")
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
