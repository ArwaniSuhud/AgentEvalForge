"""CLI: `python -m forge run ...` and `python -m forge leaderboard ...`."""

from __future__ import annotations

import argparse
import json
import sys

from .runner import run_tasks
from .store import leaderboard
from .tasks import TaskValidationError, load_tasks

__all__ = ["main", "build_parser"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="forge", description="AgentEval Forge eval harness")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="Run tasks from a JSONL file")
    p_run.add_argument("--tasks", required=True, help="Path to tasks JSONL file")
    p_run.add_argument("--db", required=True, help="Path to SQLite results DB")
    p_run.add_argument("--agent", required=True, help="Agent name to record results under")
    p_run.add_argument("--run-id", default=None, help="Run id (default: auto-generated)")

    p_lb = sub.add_parser("leaderboard", help="Show the leaderboard")
    p_lb.add_argument("--db", required=True, help="Path to SQLite results DB")
    p_lb.add_argument("--format", choices=["table", "json"], default="table",
                      help="Output format (default: table)")
    return parser


def _cmd_run(args) -> int:
    try:
        tasks = load_tasks(args.tasks)
    except FileNotFoundError:
        print(f"error: tasks file not found: {args.tasks}", file=sys.stderr)
        return 2
    except TaskValidationError as exc:
        print(f"error: invalid tasks file: {exc}", file=sys.stderr)
        return 2

    results = run_tasks(tasks, agent=args.agent, db_path=args.db, run_id=args.run_id)
    for r in results:
        verdict = "PASS" if r["passed"] else "FAIL"
        print(f"{verdict} {r['task_id']} {r['kind']} score={r['score']:.2f} ({r['duration_ms']}ms)")
    # Exit 0 when the file was valid, even if some tasks failed scoring.
    return 0


def _cmd_leaderboard(args) -> int:
    rows = leaderboard(args.db)
    if args.format == "json":
        print(json.dumps(rows, indent=2))
        return 0
    if not rows:
        print("No results yet.")
        return 0
    headers = ["agent", "games", "wins", "draws", "losses", "avg_score", "pass_rate"]
    table = [
        [
            r["agent"],
            str(r["games"]),
            str(r["wins"]),
            str(r["draws"]),
            str(r["losses"]),
            f"{r['avg_score']:.2f}",
            f"{r['pass_rate']:.2f}",
        ]
        for r in rows
    ]
    widths = [max(len(h), max(len(row[i]) for row in table)) for i, h in enumerate(headers)]
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    print(fmt.format(*headers))
    print(fmt.format(*["-" * w for w in widths]))
    for row in table:
        print(fmt.format(*row))
    return 0


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "run":
        return _cmd_run(args)
    if args.command == "leaderboard":
        return _cmd_leaderboard(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
