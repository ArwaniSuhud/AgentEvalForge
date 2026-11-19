"""BTC paper-trading bot + deterministic backtest.

A Python port of the author's make.fun ``btc-race-24h`` bot (the entry
that won $15 USDC, 8th place, 2026-11-15; same approach re-tuned for
the 2026-11-18 race, +$17.25 on $1,000 paper). Strategy: dip-buy mean
reversion on 1-minute BTC closes.

- Entry (flat only): over the last ``window`` closes the price fell
  >= ``drop_bps`` from the window high (or from the close ``window``
  bars ago) AND has recovered >= ``recovery_bps`` off the window low.
  Full cash in, one order, long only, no leverage.
- Exit (holding): take profit at +``take_profit_bps`` vs the entry
  fill, or trailing stop ``trail_bps`` below the post-entry peak, or
  stop-loss ``stop_loss_bps`` below the entry fill.
- Guardrail legs (only while no buy has filled yet, so they never
  change a run that already traded): from bar ``fallback_bar`` accept
  a shallower ``fallback_drop_bps`` dip; from ``momentum_bar`` accept
  a +``momentum_bps`` / window momentum leg; at ``last_resort_bar``
  buy regardless. A race entry needs >= 1 filled trade to be ranked,
  so these legs buy that lottery ticket instead of sitting out a calm
  window.

Fill model (offline approximation, documented): decisions are made on
a bar's close and fills execute at that same close, minus a
``fee_bps`` fee per side. The live race bot filled at the *next* bar's
open through the race harness; with close-only data this
close-to-close model is the honest offline equivalent. It is fully
deterministic: the same price series and config always give the same
result.

Data: no network at runtime. Prices come from a bundled static CSV
(``tasks/data/btc-1m-sample.csv`` — real BTCUSDT 1-minute closes from
Binance public market data, 2026-11-18 14:17 UTC -> 2026-11-19 15:16
UTC, 1500 bars). Any CSV with a ``close`` column works.
"""

from __future__ import annotations

import csv
from pathlib import Path

__all__ = [
    "DEFAULT_CONFIG",
    "BacktestError",
    "backtest_from_params",
    "load_prices",
    "run_backtest",
]

# Repo root = two levels up from this file (apps/trading_bot/backtest.py).
_ROOT = Path(__file__).resolve().parents[2]

#: Tuned defaults: the 2026-11-18 race config (window 105, drop 2.15%,
#: take-profit +1.9%, trailing stop 1.0%, stop-loss 1.2%).
DEFAULT_CONFIG: dict = {
    "window": 105,
    "drop_bps": 215,
    "recovery_bps": 20,
    "take_profit_bps": 190,
    "trail_bps": 100,
    "stop_loss_bps": 120,
    "fee_bps": 4,
    "starting_cash": 1000.0,
    "fallback_bar": 1000,
    "fallback_drop_bps": 120,
    "momentum_bar": 1200,
    "momentum_bps": 80,
    "last_resort_bar": 1400,
}

DEFAULT_DATASET = "tasks/data/btc-1m-sample.csv"


class BacktestError(ValueError):
    """Raised for invalid backtest input (bad prices, bad config)."""


def load_prices(path) -> list[float]:
    """Load closes from a CSV file with a ``close`` column.

    ``path`` is resolved relative to the repo root when it is not
    absolute. The header row is skipped; every close must be a
    positive number. Returns the closes in file order.
    """
    p = Path(path)
    if not p.is_absolute():
        p = _ROOT / p
    closes: list[float] = []
    try:
        fh = p.open("r", encoding="utf-8", newline="")
    except FileNotFoundError as exc:
        raise BacktestError(f"dataset not found: {path}") from exc
    with fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None or "close" not in reader.fieldnames:
            raise BacktestError(f"dataset {path} has no 'close' column")
        for line_no, row in enumerate(reader, start=2):
            raw = (row.get("close") or "").strip()
            try:
                close = float(raw)
            except ValueError as exc:
                raise BacktestError(
                    f"dataset {path} line {line_no}: invalid close {raw!r}"
                ) from exc
            if close <= 0:
                raise BacktestError(
                    f"dataset {path} line {line_no}: close must be positive, got {close}"
                )
            closes.append(close)
    if not closes:
        raise BacktestError(f"dataset {path} has no price rows")
    return closes


def _validate_config(cfg: dict) -> dict:
    """Merge user overrides over DEFAULT_CONFIG and validate ranges."""
    merged = dict(DEFAULT_CONFIG)
    for key, value in (cfg or {}).items():
        if key not in DEFAULT_CONFIG:
            raise BacktestError(f"unknown backtest config key: {key!r}")
        merged[key] = value
    if int(merged["window"]) < 1:
        raise BacktestError("window must be >= 1")
    for key in ("drop_bps", "recovery_bps", "take_profit_bps", "trail_bps",
                "stop_loss_bps", "fee_bps", "fallback_drop_bps", "momentum_bps"):
        if float(merged[key]) < 0:
            raise BacktestError(f"{key} must be >= 0")
    if float(merged["starting_cash"]) <= 0:
        raise BacktestError("starting_cash must be > 0")
    for key in ("fallback_bar", "momentum_bar", "last_resort_bar"):
        if int(merged[key]) < 0:
            raise BacktestError(f"{key} must be >= 0")
    return merged


def run_backtest(closes: list[float], config: dict | None = None) -> dict:
    """Run the dip-buy strategy over ``closes`` (1-minute closes).

    Pure function: no I/O, no randomness, no clock. Returns a metrics
    dict with ``bars``, ``trades``, ``final_equity``, ``net_pnl``,
    ``net_pnl_pct``, ``max_drawdown_pct``, ``win_rate``,
    ``open_position`` and the full ``trade_log``.
    """
    if not closes:
        raise BacktestError("closes must not be empty")
    for i, c in enumerate(closes):
        if not isinstance(c, (int, float)) or c <= 0:
            raise BacktestError(f"closes[{i}] must be a positive number, got {c!r}")
    cfg = _validate_config(config or {})
    window = int(cfg["window"])
    starting_cash = float(cfg["starting_cash"])
    fee = float(cfg["fee_bps"]) / 10000.0

    cash = starting_cash
    qty = 0.0
    entry_px: float | None = None
    peak = 0.0
    buy_fills = 0
    trade_log: list[dict] = []
    round_trips: list[float] = []  # net PnL per closed round trip
    trip_entry_cost = 0.0  # cash spent on the open round trip (fees incl.)

    equity_peak = starting_cash
    max_drawdown_pct = 0.0

    def _equity(close: float) -> float:
        return cash + qty * close

    for i, close in enumerate(closes):
        exited_this_bar = False
        # --- exits first when holding -------------------------------------
        if qty > 0:
            if close > peak:
                peak = close
            ret_bps = (close / entry_px - 1.0) * 10000.0
            reason = None
            if ret_bps >= float(cfg["take_profit_bps"]):
                reason = "take-profit"
            elif close <= peak * (1.0 - float(cfg["trail_bps"]) / 10000.0):
                reason = "trailing-stop"
            elif ret_bps <= -float(cfg["stop_loss_bps"]):
                reason = "stop-loss"
            if reason is not None:
                proceeds = qty * close
                sell_fee = proceeds * fee
                cash += proceeds - sell_fee
                round_trips.append(cash - trip_entry_cost)
                trade_log.append({
                    "bar": i, "side": "sell", "price": close, "qty": qty,
                    "notional": proceeds, "fee": sell_fee, "reason": reason,
                })
                qty = 0.0
                entry_px = None
                peak = 0.0
                trip_entry_cost = 0.0
                exited_this_bar = True

        # --- entries when flat --------------------------------------------
        # One decision per bar (like the race bot: one order per batch):
        # a bar that sold does not also buy.
        if qty == 0 and not exited_this_bar and i >= window:
            window_closes = closes[i - window + 1: i + 1]
            hi = max(window_closes)
            lo = min(window_closes)
            ref = closes[i - window]
            drop_bps = float(cfg["fallback_drop_bps"]) if (
                buy_fills == 0 and i >= int(cfg["fallback_bar"])
            ) else float(cfg["drop_bps"])
            dropped = ((hi - close) / hi >= drop_bps / 10000.0
                       or (ref - close) / ref >= drop_bps / 10000.0)
            recovered = (close - lo) / lo >= float(cfg["recovery_bps"]) / 10000.0
            ok = dropped and recovered
            if not ok and buy_fills == 0 and i >= int(cfg["momentum_bar"]) \
                    and (close - ref) / ref >= float(cfg["momentum_bps"]) / 10000.0:
                ok = True
            if not ok and buy_fills == 0 and i >= int(cfg["last_resort_bar"]):
                ok = True
            if ok and cash > 0:
                buy_fee = cash * fee
                spend = cash - buy_fee
                qty = spend / close
                entry_px = close
                peak = close
                buy_fills += 1
                trip_entry_cost = cash
                trade_log.append({
                    "bar": i, "side": "buy", "price": close, "qty": qty,
                    "notional": spend, "fee": buy_fee, "reason": "dip-buy",
                })
                cash = 0.0

        # --- equity / drawdown tracking ------------------------------------
        eq = _equity(close)
        if eq > equity_peak:
            equity_peak = eq
        dd = (equity_peak - eq) / equity_peak * 100.0 if equity_peak > 0 else 0.0
        if dd > max_drawdown_pct:
            max_drawdown_pct = dd

    last_close = closes[-1]
    final_equity = cash + qty * last_close
    net_pnl = final_equity - starting_cash
    wins = sum(1 for p in round_trips if p > 0)
    return {
        "bars": len(closes),
        "trades": len(trade_log),
        "buy_fills": buy_fills,
        "final_equity": final_equity,
        "net_pnl": net_pnl,
        "net_pnl_pct": net_pnl / starting_cash * 100.0,
        "max_drawdown_pct": max_drawdown_pct,
        "win_rate": (wins / len(round_trips)) if round_trips else None,
        "round_trips": len(round_trips),
        "open_position": qty > 0,
        "open_qty": qty,
        "open_entry": entry_px,
        "first_close": closes[0],
        "last_close": last_close,
        "trade_log": trade_log,
    }


def backtest_from_params(params: dict) -> dict:
    """Harness entry point: run a backtest from a params dict.

    ``params``: ``{"dataset": str, "start_bar": int, "end_bar": int,
    "config": {...overrides...}}``. ``start_bar``/``end_bar`` slice the
    dataset (Python slice semantics, ``end_bar`` exclusive). Returns
    the ``run_backtest`` dict plus ``"winner": None`` (the harness
    expects a ``winner`` key; trading results are scored on PnL, not
    on a winner) and the dataset/slice used.
    """
    params = params or {}
    dataset = str(params.get("dataset", DEFAULT_DATASET))
    closes = load_prices(dataset)
    start = int(params.get("start_bar", 0))
    end = params.get("end_bar")
    end = len(closes) if end is None else int(end)
    if start < 0 or end < start or end > len(closes):
        raise BacktestError(
            f"invalid slice start_bar={start} end_bar={end} for {len(closes)} bars"
        )
    sliced = closes[start:end]
    if not sliced:
        raise BacktestError("slice is empty: no bars to backtest")
    result = run_backtest(sliced, params.get("config"))
    result["winner"] = None
    result["dataset"] = dataset
    result["start_bar"] = start
    result["end_bar"] = end
    return result
