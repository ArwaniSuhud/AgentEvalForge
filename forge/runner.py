"""Task runner: dispatch tasks to registered executors, judge, store."""

from __future__ import annotations

import time
from datetime import datetime, timezone

from .judge import judge
from .store import init_db, record_result

__all__ = ["EXECUTORS", "register", "run_tasks", "_chess_duel_executor"]


def _default_run_id() -> str:
    # run-<UTC timestamp ISO basic>, e.g. run-20261119T220000Z
    return "run-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def register(kind: str, fn) -> None:
    """Register an executor callable for ``kind``. Executor takes params dict."""
    EXECUTORS[kind] = fn


def _chess_duel_executor(params: dict) -> dict:
    """Lazy chess-duel executor.

    Import is inside the function (not top-level) so the harness works
    even when the arena app is not built yet. The arena builder provides
    ``apps.chess_arena.duel.play_duel_from_params``.
    """
    from apps.chess_arena.duel import play_duel_from_params

    return play_duel_from_params(params)


def _trading_backtest_executor(params: dict) -> dict:
    """Lazy trading-backtest executor.

    Import is inside the function (not top-level) so the harness works
    even when the trading app is not built yet. The trading app
    provides ``apps.trading_bot.backtest.backtest_from_params``.
    """
    from apps.trading_bot.backtest import backtest_from_params

    return backtest_from_params(params)


EXECUTORS: dict[str, object] = {
    "chess-duel": _chess_duel_executor,
    "trading-backtest": _trading_backtest_executor,
}


def run_tasks(tasks, *, agent: str, db_path, run_id: str | None = None) -> list[dict]:
    """Run each task through its executor, judge it, store the result.

    One result dict per task. Unknown kinds and executor failures never
    crash the run: they produce a failed result (score 0.0) with a
    ``reason`` of ``unknown_kind`` / ``executor_error`` in details.
    """
    if run_id is None:
        run_id = _default_run_id()
    init_db(db_path)
    results: list[dict] = []

    for task in tasks:
        task_id = task.get("id")
        kind = task.get("kind")
        started = time.monotonic()
        executor = EXECUTORS.get(kind)

        if executor is None:
            duration_ms = int((time.monotonic() - started) * 1000)
            result = {
                "run_id": run_id,
                "agent": agent,
                "task_id": task_id,
                "kind": kind,
                "winner": None,
                "score": 0.0,
                "passed": False,
                "details": {"reason": "unknown_kind", "kind": kind},
                "duration_ms": duration_ms,
            }
            _store(db_path, result)
            results.append(result)
            continue

        try:
            raw = executor(task.get("params", {}))
            if not isinstance(raw, dict):
                raise TypeError(f"executor for {kind!r} must return a dict, got {type(raw).__name__}")
            verdict = judge(task, raw)
            winner = raw.get("winner")
            details = dict(verdict["details"])
            # Keep any extra executor info (plies, moves, ...) alongside.
            for key, value in raw.items():
                if key != "winner":
                    details.setdefault(key, value)
            result = {
                "run_id": run_id,
                "agent": agent,
                "task_id": task_id,
                "kind": kind,
                "winner": winner,
                "score": float(verdict["score"]),
                "passed": bool(verdict["passed"]),
                "details": details,
                "duration_ms": int((time.monotonic() - started) * 1000),
            }
        except Exception as exc:  # executor import error, judge error, ...
            result = {
                "run_id": run_id,
                "agent": agent,
                "task_id": task_id,
                "kind": kind,
                "winner": None,
                "score": 0.0,
                "passed": False,
                "details": {"reason": "executor_error", "error": f"{type(exc).__name__}: {exc}"},
                "duration_ms": int((time.monotonic() - started) * 1000),
            }
        _store(db_path, result)
        results.append(result)

    return results


def _store(db_path, result: dict) -> None:
    record_result(
        db_path,
        run_id=result["run_id"],
        agent=result["agent"],
        task_id=result["task_id"],
        kind=result["kind"],
        winner=result["winner"],
        score=result["score"],
        passed=result["passed"],
        details=result["details"],
        duration_ms=result["duration_ms"],
    )
