from __future__ import annotations

import argparse
import json

from ark95x import Ark95xOmniOrchestrator, EmeraldSyncEngine, RevenueIntelligence, load_config
from ark95x.n95_revenue import RevenueRecord


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ark95x", description="ARK95X unified entrypoint")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("sync", help="Run Emerald sync delta scan")

    omni = sub.add_parser("omni", help="Dispatch an omni task")
    omni.add_argument("--type", default="generic", help="Task type, e.g. analysis/search/reasoning")
    omni.add_argument("--task-id", default="task-local", help="Task id")

    rev = sub.add_parser("revenue", help="Revenue module actions")
    rev_sub = rev.add_subparsers(dest="action", required=True)

    add = rev_sub.add_parser("add", help="Add revenue record")
    add.add_argument("--account", required=True)
    add.add_argument("--amount", required=True, type=float)
    add.add_argument("--category", default="general")
    add.add_argument("--status", default="lead")
    add.add_argument("--source", default="manual")

    rev_sub.add_parser("summary", help="Show revenue summary")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    config = load_config()

    if args.command == "sync":
        engine = EmeraldSyncEngine(config)
        print(json.dumps(engine.sync(), indent=2))
        return

    if args.command == "omni":
        omni = Ark95xOmniOrchestrator(config)
        payload = {"type": args.type, "task_id": args.task_id}
        print(json.dumps(omni.dispatch_sync(payload), indent=2))
        return

    if args.command == "revenue":
        revenue = RevenueIntelligence(config)
        if args.action == "add":
            record = RevenueRecord(
                account=args.account,
                amount=args.amount,
                category=args.category,
                status=args.status,
                source=args.source,
            )
            print(json.dumps(revenue.add_record(record), indent=2))
            return

        if args.action == "summary":
            print(json.dumps(revenue.summary(), indent=2))
            return


if __name__ == "__main__":
    main()
