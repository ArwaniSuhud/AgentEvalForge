# Design — AgentEval Forge

## Overview

Two layers, one direction of dependency:

```
apps/chess_arena/  (demo app 1: engine + duel runner + FastAPI UI)
apps/trading_bot/  (demo app 2: backtest engine + static data + UI)
        │  both use
        ▼
forge/             (eval harness: tasks, runner, judge, store, CLI)
        │  uses
        ▼
SQLite (data/results.db)
```

The harness knows nothing about chess or trading. Each app knows
nothing about SQL. The arena's duel runner is registered as the
`chess-duel` executor and the trading backtest as the
`trading-backtest` executor; the harness only sees tasks, results,
and scores.

## Eval harness (`forge/`)

### Task format (JSONL, one task per line)

```json
{"id": "duel-001", "kind": "chess-duel", "params": {"white": {"name": "Forge-Deep", "depth": 5}, "black": {"name": "Forge-Quick", "depth": 2}, "max_ply": 200}, "expected": {"winner": "white"}}
```

- `id` — unique within the file.
- `kind` — executor key (`chess-duel`; `trading-backtest`).
- `params` — executor-specific input. For `trading-backtest`:
  `{"dataset": "tasks/data/....csv", "start_bar": int, "end_bar": int,
  "config": {strategy overrides}}`.
- `expected` — what the judge compares against. For `chess-duel`,
  `expected.winner` is `white`, `black`, or `draw`. For
  `trading-backtest`, `expected` is `{"min_trades": int,
  "min_net_pnl_pct": float, "max_drawdown_pct": float}`.

### Modules

| Module | Responsibility |
|---|---|
| `tasks.py` | Parse + validate JSONL; `load_tasks(path) -> list[dict]`; `TaskValidationError`. |
| `runner.py` | `EXECUTORS` registry (`kind -> callable`); `run_tasks(tasks, agent, db_path)` executes each task, times it, judges it, stores it. Unknown kind → failed result, reason `unknown_kind`. |
| `judge.py` | Pure functions. `judge(task, result) -> {"passed": bool, "score": float, "details": dict}`. Chess-duel rule: `passed = (actual.winner == expected.winner)`; score `1.0` if passed else `0.0` (draws score `0.5` when expected is a decisive result but the game draws — partial credit, still deterministic). Trading-backtest rule: passed when `trades >= min_trades` and `net_pnl_pct >= min_net_pnl_pct` and `max_drawdown_pct <= max_drawdown_pct`; score `1.0` / `0.0`, no partial credit. |
| `store.py` | `init_db(path)`, `record_result(...)`, `leaderboard(db_path, limit)` returning rows `{agent, games, wins, draws, losses, avg_score, pass_rate}` ordered by `avg_score DESC, games DESC`. All SQL parameterized. `recent_games(db_path, limit)` for the UI. |
| `cli.py` | `argparse` with `run` and `leaderboard` subcommands; `run` prints a per-task summary line and exits non-zero if any task failed validation. |

### Determinism

- No randomness anywhere in the scoring path. The chess engine is a
  deterministic alpha-beta search; the same duel configs always give
  the same game.
- The judge is a pure function of `(task, result)` — tested by a
  Hypothesis property test that calls it twice on generated inputs.

## Chess Duel Arena (`apps/chess_arena/`)

### Engine (`engine.py`)

A vendored, standalone adaptation of the author's tiny-chess engine
(0x88 board representation, alpha-beta + quiescence search, transposition
table, killer/history heuristics). The make.fun network protocol loop is
removed; the search core (`F`, `G`, `M`, `U`, `E`, `W`, `R`, `O`, `C`)
is kept intact and wrapped in a small class:

```python
class ChessEngine:
    def __init__(self, name: str, depth: int = 5): ...
    def legal_moves(self, fen: str) -> list[str]   # UCI, king-safe only
    def best_move(self, fen: str) -> str | None    # UCI or None if no moves
    def apply(self, fen: str, uci: str) -> str     # returns new FEN
    def is_checkmate(self, fen) -> bool
    def is_stalemate(self, fen) -> bool
```

FEN round-tripping is implemented from the internal board state
(piece placement, side to move, castling rights, en-passant square,
halfmove clock, fullmove number).

### Duel runner (`duel.py`)

```python
def play_duel(white: ChessEngine, black: ChessEngine, max_ply: int = 200) -> dict
# -> {"winner": "white"|"black"|"draw", "reason": "checkmate"|"stalemate"|"draw-ply-limit"|"insufficient-material",
#     "moves": [uci, ...], "plies": int, "final_fen": str}
```

Plays from the start position, alternating engines, until mate,
stalemate, insufficient material (K vs K, K+B vs K, K+N vs K), or the
ply limit (draw). No randomness: identical configs → identical games.

### Web server (`server.py`)

FastAPI app:

- `GET /` — serves `static/index.html` (leaderboard + recent games,
  "Run a duel" button; plain `fetch()` calls, no build step).
- `GET /api/leaderboard` — `forge.store.leaderboard()`.
- `GET /api/games` — `forge.store.recent_games()`.
- `POST /api/duel` — body `{"white_depth": 5, "black_depth": 2,
  "max_ply": 200}`; plays a duel, records it under agent name
  `chess-arena`, returns the duel result. A simple in-process lock
  serializes concurrent duel runs.

The DB path is configurable via env `FORGE_DB` (default
`data/results.db`, resolved relative to the repo root).

## BTC Paper-Trading Bot (`apps/trading_bot/`)

### Backtest engine (`backtest.py`)

A Python port of the author's make.fun `btc-race-24h` bot (dip-buy
mean reversion; won $15 USDC, 8th place, 2026-11-15; re-tuned for the
2026-11-18 race, +$17.25 on $1,000 paper). Pure functions, no I/O in
the scoring path, no network, no randomness:

```python
def load_prices(path) -> list[float]   # closes from a CSV with a `close` column
def run_backtest(closes, config=None) -> dict
# -> {"bars", "trades", "buy_fills", "final_equity", "net_pnl",
#     "net_pnl_pct", "max_drawdown_pct", "win_rate", "round_trips",
#     "open_position", "open_qty", "open_entry", "first_close",
#     "last_close", "trade_log": [{bar, side, price, qty, notional, fee, reason}]}
def backtest_from_params(params) -> dict   # harness entry point (adds "winner": None)
```

Strategy (defaults = the 2026-11-18 race config): window 105 bars,
drop 215 bps, recovery 20 bps, take-profit 190 bps, trailing stop
100 bps, stop-loss 120 bps, fee 4 bps/side, $1,000 starting cash.
Guardrails before the first fill: shallower 120 bps dip from bar
1000, +80 bps momentum leg from bar 1200, buy regardless at bar
1400. One decision per bar; fills at the signal bar's close
(close-to-close model — the live bot filled at the next bar's open;
documented in the module docstring and README). Long only, full cash
in, one position at a time. Note: with `trail_bps < stop_loss_bps`
the stop-loss can never trigger (the trailing stop is tighter and
the peak never falls below the entry) — it is kept as
defence-in-depth for configs where that ordering changes.

### Price data (`tasks/data/`)

- `btc-1m-sample.csv` — 1500 real BTCUSDT 1-minute closes, Binance
  public market data, 2026-11-18 14:17 UTC → 2026-11-19 15:16 UTC.
- `btc-dip-bounce.csv`, `btc-crash.csv` — small synthetic fixtures
  with hand-designed price paths (take-profit win / bounded-loss
  exit); the real window is too calm for either.
- Bundled scenarios in `tasks/trading-backtests.jsonl` (`bt-001` …
  `bt-004`); `expected` values set from verified runs.

### Web UI (in `apps/chess_arena/server.py`)

- `GET /trading` — serves `apps/trading_bot/static/index.html`
  (combined leaderboard, recent backtests, run-a-backtest form with
  presets; plain `fetch()` calls, no build step).
- `GET /api/backtests` — recent `trading-backtest` results.
- `POST /api/backtest` — body `{"dataset", "start_bar", "end_bar",
  ...strategy params}`; only the three bundled datasets are
  accepted; runs the backtest, scores it with the harness judge
  (web rule: pass = ≥ 1 trade and no loss), records it under agent
  `trading-bot`, returns the result. Serialized with a lock.

## Testing

- `tests/test_harness.py` — task validation, judge rules, store
  round-trip, leaderboard math, CLI smoke test.
- `tests/test_harness_properties.py` — Hypothesis: judge
  determinism, leaderboard consistency, JSONL round-trip.
- `tests/test_chess_arena.py` — startpos has 20 legal moves,
  fool's mate is checkmate, `best_move` is always legal, duel
  determinism, duel termination, API endpoints via `TestClient`.
- `tests/test_trading_bot.py` — price loading + validation,
  backtest entry/exit/fee/guardrail behaviour, bundled-fixture
  metrics, trading judge rules, runner + CLI end-to-end, API
  endpoints via `TestClient`.
- `tests/test_trading_properties.py` — Hypothesis: backtest
  determinism and invariants (equity ≥ 0, drawdown in [0, 100],
  PnL % consistent with equity, trades alternate buy/sell from a
  buy, no trades on a monotonic rise), judge determinism.
