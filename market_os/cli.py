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
    server = commands.add_parser("serve")
    server.add_argument("--host", default=os.environ.get("MARKET_OS_HOST", "127.0.0.1"))
    server.add_argument("--port", type=int, default=int(os.environ.get("MARKET_OS_PORT", "8787")))
    server.add_argument("--store-root", default=os.environ.get("MARKET_OS_STORE_ROOT", ".market_os"))
    server.add_argument("--request-timeout", type=float, default=float(os.environ.get("MARKET_OS_REQUEST_TIMEOUT", "5")))
    server.add_argument("--service-log", default=os.environ.get("MARKET_OS_SERVICE_LOG"))
    inspect = commands.add_parser("inspect")
    inspect.add_argument("run_id")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "serve":
        workflow = MarketWorkflow(RunStore(args.store_root))
        serve(workflow, args.host, args.port, request_timeout=args.request_timeout, service_log_path=args.service_log)
        return 0
    workflow = MarketWorkflow()
    if args.command == "inspect":
        print(json.dumps(workflow.inspect_run(args.run_id), indent=2, sort_keys=True))
        return 0
    task = workflow.create_task(args.objective, args.symbols, args.start, args.end)
    print(json.dumps(workflow.run(task), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
