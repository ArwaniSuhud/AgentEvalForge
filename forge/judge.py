"""Deterministic judge: pure function, no randomness, no network."""

from __future__ import annotations

__all__ = ["judge"]

_DECISIVE = ("white", "black")


def _judge_chess(task: dict, result: dict) -> dict:
    try:
        expected_winner = task["expected"]["winner"]
    except (KeyError, TypeError) as exc:
        raise ValueError("task['expected']['winner'] is required for chess-duel") from exc
    try:
        actual_winner = result["winner"]
    except (KeyError, TypeError) as exc:
        raise ValueError("result['winner'] is required for chess-duel") from exc

    if actual_winner == expected_winner:
        score, passed = 1.0, True
    elif actual_winner == "draw" and expected_winner in _DECISIVE:
        score, passed = 0.5, False
    else:
        score, passed = 0.0, False

    return {
        "passed": passed,
        "score": score,
        "details": {
            "kind": "chess-duel",
            "expected_winner": expected_winner,
            "actual_winner": actual_winner,
        },
    }


def _judge_trading(task: dict, result: dict) -> dict:
    """Score a trading-backtest result.

    ``expected``: ``{"min_trades": int, "min_net_pnl_pct": float,
    "max_drawdown_pct": float}`` — all optional, defaults 0 / -100 / 100.
    Passed (score 1.0) when the run made at least ``min_trades`` trades,
    its net PnL % is at least ``min_net_pnl_pct`` (a negative floor is
    how a bounded-loss scenario passes), and its max drawdown % is at
    most ``max_drawdown_pct``. Otherwise score 0.0. No partial credit:
    a backtest either behaved within its risk envelope or it did not.
    """
    expected = task.get("expected")
    if not isinstance(expected, dict):
        raise ValueError("task['expected'] is required for trading-backtest")
    try:
        trades = result["trades"]
        net_pnl_pct = result["net_pnl_pct"]
        max_drawdown_pct = result["max_drawdown_pct"]
    except (KeyError, TypeError) as exc:
        raise ValueError(
            "result['trades'/'net_pnl_pct'/'max_drawdown_pct'] are required "
            "for trading-backtest"
        ) from exc

    min_trades = int(expected.get("min_trades", 0))
    min_pnl = float(expected.get("min_net_pnl_pct", -100.0))
    max_dd = float(expected.get("max_drawdown_pct", 100.0))
    passed = trades >= min_trades and net_pnl_pct >= min_pnl and max_drawdown_pct <= max_dd
    return {
        "passed": passed,
        "score": 1.0 if passed else 0.0,
        "details": {
            "kind": "trading-backtest",
            "min_trades": min_trades,
            "actual_trades": trades,
            "min_net_pnl_pct": min_pnl,
            "actual_net_pnl_pct": net_pnl_pct,
            "max_drawdown_pct": max_dd,
            "actual_max_drawdown_pct": max_drawdown_pct,
        },
    }


def _judge_math(task: dict, result: dict) -> dict:
    """Score a math-word result.

    ``expected``: ``{"answer": number}``. Passed (score 1.0) when the
    numeric answer matches the expected answer within 1e-9; otherwise
    score 0.0. No partial credit: an answer is either right or it is not.
    """
    expected = task.get("expected")
    if not isinstance(expected, dict) or "answer" not in expected:
        raise ValueError("task['expected']['answer'] is required for math-word")
    try:
        actual = result["answer"]
    except (KeyError, TypeError) as exc:
        raise ValueError("result['answer'] is required for math-word") from exc
    try:
        expected_answer = float(expected["answer"])
        actual_answer = float(actual)
    except (TypeError, ValueError) as exc:
        raise ValueError("math-word answers must be numeric") from exc

    passed = abs(actual_answer - expected_answer) <= 1e-9
    return {
        "passed": passed,
        "score": 1.0 if passed else 0.0,
        "details": {
            "kind": "math-word",
            "expected_answer": expected_answer,
            "actual_answer": actual_answer,
            "reason": (
                f"answer {actual_answer} matches expected {expected_answer} within 1e-9"
                if passed
                else f"answer {actual_answer} != expected {expected_answer}"
            ),
        },
    }


def judge(task: dict, result: dict) -> dict:
    """Score ``result`` against ``task["expected"]``.

    Returns {"passed": bool, "score": float, "details": dict} with
    score always in [0, 1].

    chess-duel rules:
    - actual winner == expected winner -> passed, score 1.0
    - actual draw while expected is decisive (white/black) -> 0.5, not passed
    - anything else -> 0.0, not passed

    trading-backtest rules: see ``_judge_trading``.

    math-word rules: see ``_judge_math`` — the numeric answer must
    match ``expected["answer"]`` within 1e-9.

    Unknown kind raises ValueError.
    """
    kind = task.get("kind") if isinstance(task, dict) else None
    if kind == "chess-duel":
        return _judge_chess(task, result)
    if kind == "trading-backtest":
        return _judge_trading(task, result)
    if kind == "math-word":
        return _judge_math(task, result)
    raise ValueError(f"unknown kind for judge: {kind!r}")
