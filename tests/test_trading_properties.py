"""Hypothesis property tests for the trading backtest + judge."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from apps.trading_bot.backtest import run_backtest
from forge import judge

# Positive 1-minute closes; wide range so dips/bounces occur naturally.
_CLOSES = st.lists(
    st.floats(min_value=1.0, max_value=200_000.0, allow_nan=False,
              allow_infinity=False, allow_subnormal=False),
    min_size=1, max_size=300,
)


@given(closes=_CLOSES)
@settings(max_examples=50, deadline=None)
def test_backtest_properties(closes):
    r1 = run_backtest(closes)
    r2 = run_backtest(closes)
    assert r1 == r2  # deterministic

    assert r1["bars"] == len(closes)
    assert r1["trades"] == len(r1["trade_log"])
    assert r1["final_equity"] >= 0
    assert 0.0 <= r1["max_drawdown_pct"] <= 100.0 + 1e-9
    # PnL % is exactly the equity change by construction.
    assert r1["net_pnl_pct"] == pytest.approx(
        100.0 * (r1["final_equity"] - 1000.0) / 1000.0
    )
    if r1["trades"] == 0:
        assert r1["final_equity"] == pytest.approx(1000.0)
        assert r1["max_drawdown_pct"] == pytest.approx(0.0)
    # Trades alternate buy/sell, starting with a buy; quantities/fees sane.
    expected_side = "buy"
    for t in r1["trade_log"]:
        assert t["side"] == expected_side
        assert t["qty"] > 0
        assert t["fee"] >= 0
        assert t["price"] > 0
        expected_side = "sell" if expected_side == "buy" else "buy"
    if r1["round_trips"] == 0:
        assert r1["win_rate"] is None
    else:
        assert 0.0 <= r1["win_rate"] <= 1.0
    assert r1["open_position"] == (r1["trade_log"][-1]["side"] == "buy") \
        if r1["trade_log"] else r1["open_position"] is False


@given(closes=st.lists(
    st.floats(min_value=1.0, max_value=200_000.0, allow_nan=False,
              allow_infinity=False, allow_subnormal=False),
    min_size=106, max_size=300,
))
@settings(max_examples=30, deadline=None)
def test_backtest_no_trades_on_monotonic_rise(closes):
    rising = sorted(closes)
    r = run_backtest(rising)
    # A non-decreasing series can never drop, so the dip-buy never fires
    # (and < 1200 bars, no guardrail leg can fire either).
    assert r["trades"] == 0


_TRADES = st.integers(min_value=0, max_value=10)
_PNL = st.floats(min_value=-100.0, max_value=100.0, allow_nan=False)
_DD = st.floats(min_value=0.0, max_value=100.0, allow_nan=False)


@given(trades=_TRADES, pnl=_PNL, dd=_DD)
def test_judge_trading_is_deterministic_and_bounded(trades, pnl, dd):
    task = {"kind": "trading-backtest",
            "expected": {"min_trades": 1, "min_net_pnl_pct": 0.0,
                         "max_drawdown_pct": 50.0}}
    result = {"trades": trades, "net_pnl_pct": pnl, "max_drawdown_pct": dd}
    v1 = judge(task, result)
    v2 = judge(task, result)
    assert v1 == v2
    assert v1["score"] in (0.0, 1.0)
    assert v1["passed"] == (trades >= 1 and pnl >= 0.0 and dd <= 50.0)
