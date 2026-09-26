from __future__ import annotations

import argparse
import json

from .client import FortnoxClient
from .orchestrator import Orchestrator


def main() -> None:
    parser = argparse.ArgumentParser(prog="fortnox")
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan", help="Analyze a request without calling Fortnox")
    plan.add_argument("request")
    args = parser.parse_args()
    if args.command == "plan":
        intent = Orchestrator(FortnoxClient()).plan(args.request)
        print(json.dumps(intent.__dict__, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
