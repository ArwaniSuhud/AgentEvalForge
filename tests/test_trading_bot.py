"""Tests for the BTC paper-trading bot + backtest harness integration."""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apps.trading_bot.backtest import (
    BacktestError,
    backtest_from_params,
    load_prices,
    run_backtest,
)
from forge import judge, run_tasks
from forge.runner import EXECUTORS

ROOT = Path(__file__).resolve().parents[1]

#: Small-window config so hand-built series stay short.
SMALL = {
    "window": 5,
    "drop_bps": 200,
    "recovery_bps": 20,
    "take_profit_bps": 190,
    "trail_bps": 100,
    "stop_loss_bps": 120,
    "fee_bps": 4,
    "starting_cash": 1000.0,
}


# ---------------------------------------------------------------- load_prices
def _write_csv(path: Path, rows: list[str]) -> Path:
    path.write_text("timestamp_ms,open,high,low,close,volume\n" + "\n".join(rows) + "\n", encoding="utf-8")
    return path


def test_load_prices_valid(tmp_path):
    p = _write_csv(tmp_path / "p.csv", [
        "1,100,100,100,100.5,1",
        "2,100.5,101,100,101.25,2",
    ])
    assert load_prices(p) == [100.5, 101.25]


def test_load_prices_missing_file(tmp_path):
    with pytest.raises(BacktestError, match="not found"):
        load_prices(tmp_path / "nope.csv")


def test_load_prices_no_close_column(tmp_path):
    p = (tmp_path / "p.csv")
    p.write_text("timestamp_ms,open\n1,100\n", encoding="utf-8")
    with pytest.raises(BacktestError, match="no 'close' column"):
        load_prices(p)


def test_load_prices_bad_close(tmp_path):
    p = _write_csv(tmp_path / "p.csv", ["1,100,100,100,abc,1"])
    with pytest.raises(BacktestError, match="invalid close"):
        load_prices(p)


def test_load_prices_non_positive_close(tmp_path):
    p = _write_csv(tmp_path / "p.csv", ["1,100,100,100,0,1"])
    with pytest.raises(BacktestError, match="must be positive"):
        load_prices(p)


def test_load_prices_empty(tmp_path):
    p = _write_csv(tmp_path / "p.csv", [])
    with pytest.raises(BacktestError, match="no price rows"):
        load_prices(p)


# ---------------------------------------------------------------- run_backtest
def test_flat_series_no_trades():
    r = run_backtest([100.0] * 300)
    assert r["trades"] == 0
    assert r["final_equity"] == pytest.approx(1000.0)
    assert r["net_pnl_pct"] == pytest.approx(0.0)
    assert r["max_drawdown_pct"] == pytest.approx(0.0)
    assert r["open_position"] is False


def test_rising_series_no_trades():
    r = run_backtest([100.0 + 0.1 * i for i in range(300)])
    assert r["trades"] == 0
    assert r["final_equity"] == pytest.approx(1000.0)


def test_dip_bounce_hits_take_profit():
    # Sharp -3% drop in one bar, bounce, rally past +1.9% take-profit.
    closes = [100.0] * 6 + [97.0, 97.3, 98.0, 99.0, 99.5] + [99.5] * 3
    r = run_backtest(closes, SMALL)
    assert r["trades"] == 2
    buy, sell = r["trade_log"]
    assert buy["side"] == "buy" and buy["bar"] == 7 and buy["price"] == pytest.approx(97.3)
    assert buy["fee"] == pytest.approx(0.4)  # 4 bps of $1000
    assert buy["qty"] == pytest.approx(999.6 / 97.3)
    assert sell["side"] == "sell" and sell["reason"] == "take-profit"
    assert r["net_pnl_pct"] > 0
    assert r["round_trips"] == 1
    assert r["win_rate"] == pytest.approx(1.0)


def test_falling_after_entry_exits_with_bounded_loss():
    closes = [100.0] * 6 + [97.0, 97.3, 97.0, 96.0] + [96.0] * 3
    r = run_backtest(closes, SMALL)
    assert r["trades"] == 2
    assert r["trade_log"][1]["reason"] in ("trailing-stop", "stop-loss")
    assert r["net_pnl_pct"] < 0
    assert r["net_pnl_pct"] > -2.0  # loss bounded by the exit discipline
    assert r["win_rate"] == pytest.approx(0.0)


def test_backtest_is_deterministic():
    closes = load_prices(ROOT / "tasks" / "data" / "btc-dip-bounce.csv")
    assert run_backtest(closes) == run_backtest(closes)


def test_backtest_invalid_inputs():
    with pytest.raises(BacktestError):
        run_backtest([])
    with pytest.raises(BacktestError):
        run_backtest([100.0, -5.0])
    with pytest.raises(BacktestError):
        run_backtest([100.0] * 10, {"window": 0})
    with pytest.raises(BacktestError):
        run_backtest([100.0] * 10, {"fee_bps": -1})
    with pytest.raises(BacktestError):
        run_backtest([100.0] * 10, {"starting_cash": 0})
    with pytest.raises(BacktestError, match="unknown backtest config key"):
        run_backtest([100.0] * 10, {"nope": 1})


def test_last_resort_guardrail_buys_on_flat_series():
    # Flat 1500-bar series: no dip ever, so only the last-resort leg
    # (bar 1400, no fill yet) buys.
    r = run_backtest([100.0] * 1500)
    assert r["trades"] == 1
    assert r["trade_log"][0]["bar"] == 1400
    assert r["trade_log"][0]["side"] == "buy"
    assert r["open_position"] is True


# ---------------------------------------------------------------- from_params
def test_backtest_from_params_bundled_fixtures():
    bounce = backtest_from_params({"dataset": "tasks/data/btc-dip-bounce.csv"})
    assert bounce["trades"] == 2
    assert bounce["net_pnl_pct"] == pytest.approx(1.8446, abs=1e-3)
    assert bounce["winner"] is None

    crash = backtest_from_params({"dataset": "tasks/data/btc-crash.csv"})
    assert crash["trades"] == 2
    assert crash["net_pnl_pct"] == pytest.approx(-0.9702, abs=1e-3)

    full = backtest_from_params({"dataset": "tasks/data/btc-1m-sample.csv"})
    assert full["bars"] == 1500
    assert full["trades"] == 1
    assert full["net_pnl_pct"] == pytest.approx(-0.5058, abs=1e-3)

    calm = backtest_from_params({
        "dataset": "tasks/data/btc-1m-sample.csv", "start_bar": 0, "end_bar": 300,
    })
    assert calm["trades"] == 0
    assert calm["bars"] == 300


def test_backtest_from_params_bad_slice():
    with pytest.raises(BacktestError, match="invalid slice"):
        backtest_from_params({"dataset": "tasks/data/btc-crash.csv", "start_bar": 300, "end_bar": 100})
    with pytest.raises(BacktestError, match="slice is empty"):
        backtest_from_params({"dataset": "tasks/data/btc-crash.csv", "start_bar": 200, "end_bar": 200})
    with pytest.raises(BacktestError, match="not found"):
        backtest_from_params({"dataset": "tasks/data/nope.csv"})


# ---------------------------------------------------------------- judge
def test_judge_trading_pass_and_fail():
    task = {"kind": "trading-backtest",
            "expected": {"min_trades": 2, "min_net_pnl_pct": 1.0, "max_drawdown_pct": 1.0}}
    good = {"trades": 2, "net_pnl_pct": 1.84, "max_drawdown_pct": 0.04}
    v = judge(task, good)
    assert v["passed"] is True and v["score"] == 1.0
    bad = {"trades": 2, "net_pnl_pct": 0.5, "max_drawdown_pct": 0.04}
    assert judge(task, bad)["passed"] is False
    assert judge(task, bad)["score"] == 0.0
    few = {"trades": 0, "net_pnl_pct": 0.0, "max_drawdown_pct": 0.0}
    assert judge(task, few)["passed"] is False


def test_judge_trading_defaults_and_missing_keys():
    # Empty expected: any result passes (defaults 0 / -100 / 100).
    assert judge({"kind": "trading-backtest", "expected": {}},
                {"trades": 0, "net_pnl_pct": -50.0, "max_drawdown_pct": 99.0})["passed"] is True
    with pytest.raises(ValueError, match="required for trading-backtest"):
        judge({"kind": "trading-backtest", "expected": {}}, {"trades": 0})


def test_judge_unknown_kind_still_raises():
    with pytest.raises(ValueError, match="unknown kind"):
        judge({"kind": "nope", "expected": {}}, {})


# ---------------------------------------------------------------- runner + CLI
def test_runner_registers_trading_executor():
    assert "trading-backtest" in EXECUTORS


def test_runner_runs_trading_tasks(tmp_path):
    from forge.tasks import load_tasks
    from forge.store import leaderboard

    tasks = load_tasks(ROOT / "tasks" / "trading-backtests.jsonl")
    assert [t["id"] for t in tasks] == ["bt-001", "bt-002", "bt-003", "bt-004"]
    db = tmp_path / "r.db"
    results = run_tasks(tasks, agent="test-bot", db_path=db)
    assert len(results) == 4
    assert all(r["passed"] for r in results)
    rows = leaderboard(db)
    assert len(rows) == 1 and rows[0]["agent"] == "test-bot"
    assert rows[0]["wins"] == 4 and rows[0]["losses"] == 0


def test_cli_runs_bundled_trading_tasks(tmp_path):
    db = tmp_path / "cli.db"
    proc = subprocess.run(
        [sys.executable, "-m", "forge", "run",
         "--tasks", str(ROOT / "tasks" / "trading-backtests.jsonl"),
         "--db", str(db), "--agent", "cli-bot"],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.count("PASS bt-") == 4


# ---------------------------------------------------------------- API
@pytest.fixture()
def api_client(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_DB", str(tmp_path / "results.db"))
    import apps.chess_arena.server as server

    importlib.reload(server)
    with TestClient(server.app) as client:
        yield client


def test_api_trading_page_returns_html(api_client):
    res = api_client.get("/trading")
    assert res.status_code == 200
    assert "BTC Paper-Trading Bot" in res.text


def test_api_backtests_empty(api_client):
    res = api_client.get("/api/backtests")
    assert res.status_code == 200
    assert res.json() == []


def test_api_backtest_records_result(api_client):
    res = api_client.post("/api/backtest", json={
        "dataset": "tasks/data/btc-dip-bounce.csv",
    })
    assert res.status_code == 200
    body = res.json()
    assert body["trades"] == 2
    assert body["net_pnl_pct"] == pytest.approx(1.8446, abs=1e-3)
    assert body["passed"] is True

    from forge.store import leaderboard, recent_games
    import apps.chess_arena.server as server

    rows = leaderboard(server.DB_PATH)
    assert len(rows) == 1 and rows[0]["agent"] == "trading-bot"
    assert rows[0]["wins"] == 1
    backtests = api_client.get("/api/backtests").json()
    assert len(backtests) == 1
    assert backtests[0]["kind"] == "trading-backtest"
    games = recent_games(server.DB_PATH)
    assert games[0]["kind"] == "trading-backtest"


def test_api_backtest_unknown_dataset(api_client):
    res = api_client.post("/api/backtest", json={"dataset": "tasks/data/nope.csv"})
    assert res.status_code == 200
    assert "error" in res.json()
