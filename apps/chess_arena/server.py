"""FastAPI web UI for Chess Duel Arena + BTC Paper-Trading Bot.

- ``GET /`` serves the static leaderboard/duel page.
- ``GET /trading`` serves the static backtest page.
- ``GET /api/leaderboard`` / ``GET /api/games`` read the forge store
  (combined: chess duels + trading backtests).
- ``GET /api/backtests`` lists recent trading-backtest results.
- ``POST /api/duel`` plays one engine-vs-engine duel and records it
  in SQLite via ``forge.store.record_result`` (agent ``chess-arena``,
  run_id ``web``).
- ``POST /api/backtest`` runs one BTC backtest over the bundled
  static price data and records it (agent ``trading-bot``,
  run_id ``web``).

Run from the repo root: ``uvicorn apps.chess_arena.server:app``.

The results DB path comes from env ``FORGE_DB`` (default
``data/results.db`` relative to the repo root).
"""

from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel

# Repo root = two levels up from this file (apps/chess_arena/server.py).
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from forge import store as _store  # noqa: E402
from forge.judge import judge as _judge  # noqa: E402

from apps.chess_arena.duel import play_duel  # noqa: E402
from apps.chess_arena.engine import ChessEngine  # noqa: E402
from apps.trading_bot.backtest import backtest_from_params  # noqa: E402

_db_env = os.environ.get("FORGE_DB")
if _db_env:
    _db_path = Path(_db_env)
    DB_PATH = _db_path if _db_path.is_absolute() else _ROOT / _db_path
else:
    DB_PATH = _ROOT / "data" / "results.db"

_STATIC_DIR = Path(__file__).resolve().parent / "static"
_TRADING_STATIC_DIR = _ROOT / "apps" / "trading_bot" / "static"

app = FastAPI(title="AgentEval Forge — Chess Duel Arena & BTC Paper-Trading Bot")

_duel_lock = threading.Lock()
_backtest_lock = threading.Lock()


class DuelRequest(BaseModel):
    white_depth: int = 5
    black_depth: int = 2
    max_ply: int = 200


class BacktestRequest(BaseModel):
    dataset: str = "tasks/data/btc-1m-sample.csv"
    start_bar: int = 0
    end_bar: int | None = None
    window: int = 105
    drop_bps: int = 215
    recovery_bps: int = 20
    take_profit_bps: int = 190
    trail_bps: int = 100
    stop_loss_bps: int = 120
    fee_bps: int = 4
    starting_cash: float = 1000.0


def _engine_name(depth: int) -> str:
    return "Forge-Deep" if depth >= 5 else "Forge-Quick"


@app.get("/")
def index():
    return FileResponse(_STATIC_DIR / "index.html")


@app.get("/trading")
def trading_index():
    return FileResponse(_TRADING_STATIC_DIR / "index.html")


@app.get("/static/forge.css")
def shared_css():
    """Shared stylesheet used by both demo pages."""
    return FileResponse(_STATIC_DIR / "forge.css", media_type="text/css")


@app.get("/api/leaderboard")
def api_leaderboard():
    return _store.leaderboard(DB_PATH)


@app.get("/api/games")
def api_games():
    return _store.recent_games(DB_PATH)


@app.get("/api/backtests")
def api_backtests():
    return [g for g in _store.recent_games(DB_PATH) if g["kind"] == "trading-backtest"]


@app.post("/api/duel")
def api_duel(req: DuelRequest):
    white_depth = min(max(int(req.white_depth), 1), 9)
    black_depth = min(max(int(req.black_depth), 1), 9)
    max_ply = min(max(int(req.max_ply), 1), 1000)
    white = ChessEngine(_engine_name(white_depth), white_depth)
    black = ChessEngine(_engine_name(black_depth), black_depth)
    started = time.time()
    with _duel_lock:
        result = play_duel(white, black, max_ply)
        duration_ms = int((time.time() - started) * 1000)
        result = dict(result)
        result["white"] = white.name
        result["black"] = black.name
        # The arena agent plays White (harness convention), so score the
        # duel like the judge would with expected winner "white": 1.0 for
        # a white win, 0.5 for a draw, 0.0 for a black win.
        winner = result["winner"]
        score = 1.0 if winner == "white" else 0.5 if winner == "draw" else 0.0
        _store.record_result(
            DB_PATH,
            run_id="web",
            agent="chess-arena",
            task_id="web-duel",
            kind="chess-duel",
            winner=winner,
            score=score,
            passed=winner == "white",
            details={
                "white": {"name": white.name, "depth": white_depth},
                "black": {"name": black.name, "depth": black_depth},
                "max_ply": max_ply,
                "reason": result["reason"],
                "plies": result["plies"],
                "moves": result["moves"],
                "final_fen": result["final_fen"],
            },
            duration_ms=duration_ms,
        )
    return result


# ---------------------------------------------------------------- trading
_ALLOWED_DATASETS = {
    "tasks/data/btc-1m-sample.csv",
    "tasks/data/btc-dip-bounce.csv",
    "tasks/data/btc-crash.csv",
}


@app.post("/api/backtest")
def api_backtest(req: BacktestRequest):
    if req.dataset not in _ALLOWED_DATASETS:
        return {"error": f"unknown dataset: {req.dataset!r}"}
    params = {
        "dataset": req.dataset,
        "start_bar": max(int(req.start_bar), 0),
        "config": {
            "window": min(max(int(req.window), 1), 500),
            "drop_bps": min(max(int(req.drop_bps), 0), 10000),
            "recovery_bps": min(max(int(req.recovery_bps), 0), 10000),
            "take_profit_bps": min(max(int(req.take_profit_bps), 0), 10000),
            "trail_bps": min(max(int(req.trail_bps), 0), 10000),
            "stop_loss_bps": min(max(int(req.stop_loss_bps), 0), 10000),
            "fee_bps": min(max(int(req.fee_bps), 0), 1000),
            "starting_cash": max(float(req.starting_cash), 1.0),
        },
    }
    if req.end_bar is not None:
        params["end_bar"] = max(int(req.end_bar), 0)
    started = time.time()
    with _backtest_lock:
        result = backtest_from_params(params)
        duration_ms = int((time.time() - started) * 1000)
        # Web runs are scored like a harness task that expects at least
        # one profitable trade: pass = made >= 1 trade and did not lose.
        verdict = _judge(
            {"kind": "trading-backtest",
             "expected": {"min_trades": 1, "min_net_pnl_pct": 0.0,
                          "max_drawdown_pct": 100.0}},
            result,
        )
        result = dict(result)
        result["score"] = verdict["score"]
        result["passed"] = verdict["passed"]
        _store.record_result(
            DB_PATH,
            run_id="web",
            agent="trading-bot",
            task_id="web-backtest",
            kind="trading-backtest",
            winner=None,
            score=verdict["score"],
            passed=verdict["passed"],
            details={
                "dataset": result["dataset"],
                "start_bar": result["start_bar"],
                "end_bar": result["end_bar"],
                "bars": result["bars"],
                "trades": result["trades"],
                "net_pnl": result["net_pnl"],
                "net_pnl_pct": result["net_pnl_pct"],
                "max_drawdown_pct": result["max_drawdown_pct"],
                "win_rate": result["win_rate"],
                "open_position": result["open_position"],
                "trade_log": result["trade_log"],
            },
            duration_ms=duration_ms,
        )
    return result
