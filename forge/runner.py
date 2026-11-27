"""Task runner: dispatch tasks to registered executors, judge, store."""

from __future__ import annotations

import ast
import operator
import time
from datetime import datetime, timezone

from .judge import judge
from .store import init_db, record_result

__all__ = ["EXECUTORS", "register", "run_tasks", "_chess_duel_executor", "_math_word_executor"]


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


_MATH_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}
_MATH_SYMBOLS = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/"}


def _fmt_num(value: float) -> str:
    """Render a number without a trailing '.0' when it is integral."""
    return str(int(value)) if float(value).is_integer() else repr(value)


def _eval_math_expr(expr: str) -> tuple[float, list[str]]:
    """Evaluate a small arithmetic expression safely (AST walk, no eval()).

    Only + - * / , parentheses and plain numbers are allowed. Returns
    ``(answer, steps)`` where ``steps`` records each sub-operation
    bottom-up, e.g. ``"(3 + 4) * 2"`` -> ``["3 + 4 = 7", "7 * 2 = 14"]``.
    """
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"invalid math expression {expr!r}: {exc.msg}") from exc

    steps: list[str] = []

    def _eval(node) -> float:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
                raise ValueError(
                    f"invalid math expression {expr!r}: only plain numbers are allowed"
                )
            return float(node.value)
        if isinstance(node, ast.BinOp):
            op = _MATH_OPS.get(type(node.op))
            if op is None:
                raise ValueError(
                    f"invalid math expression {expr!r}: only + - * / are allowed"
                )
            left = _eval(node.left)
            right = _eval(node.right)
            if isinstance(node.op, ast.Div) and right == 0:
                raise ValueError(f"invalid math expression {expr!r}: division by zero")
            value = op(left, right)
            steps.append(
                f"{_fmt_num(left)} {_MATH_SYMBOLS[type(node.op)]} {_fmt_num(right)} = {_fmt_num(value)}"
            )
            return value
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = _eval(node.operand)
            return +value if isinstance(node.op, ast.UAdd) else -value
        raise ValueError(
            f"invalid math expression {expr!r}: only + - * /, parentheses and numbers are allowed"
        )

    return _eval(tree), steps


def _math_word_executor(params: dict) -> dict:
    """Deterministic word-problem executor (fully offline).

    ``params``: ``{"problem": str, "expression": str}`` — ``expression``
    is a small arithmetic expression (+ - * / and parentheses) that
    encodes the problem; it is solved by the tiny built-in solver
    above (no LLM, no network). Returns
    ``{"answer": float, "steps": [str, ...], "problem": str}``.
    ``problem`` falls back to the expression when it is absent.
    """
    if not isinstance(params, dict):
        raise ValueError("math-word params must be an object with 'expression'")
    expression = params.get("expression")
    if not isinstance(expression, str) or not expression.strip():
        raise ValueError("math-word params['expression'] must be a non-empty string")
    answer, steps = _eval_math_expr(expression)
    return {
        "answer": answer,
        "steps": steps,
        "problem": params.get("problem") or expression.strip(),
    }


EXECUTORS: dict[str, object] = {
    "chess-duel": _chess_duel_executor,
    "trading-backtest": _trading_backtest_executor,
    "math-word": _math_word_executor,
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
