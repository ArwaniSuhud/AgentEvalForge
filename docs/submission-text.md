# AgentEval Forge — Devpost Submission Text

*(Paste-ready. Category: Skeleton Crew — Kiroween 2026.)*

## Project description

AgentEval Forge is a spec-driven template for building and evaluating AI
agents with Kiro — plus two demo apps built from the same foundation.

The core is a small deterministic eval harness (`forge/`). A task is one
JSONL line with `id`, `kind`, `params`, and `expected`. The runner dispatches
each task to the executor registered for its `kind`, times it, and scores it
with a judge that is a pure function: no randomness, no network, no LLM at
runtime. Chess duels are scored on whether the actual winner matches the
expected winner (a draw against a decisive expectation scores 0.5);
trading backtests pass when they make at least the expected number of
trades, stay at or above the expected PnL floor, and stay within the
expected maximum drawdown. Results are stored in SQLite, and
`forge leaderboard` aggregates them per agent — games, wins, draws,
losses, average score, pass rate — combined across both demo apps.
Re-running the same task file always produces the same scores.

The two demo apps prove the template with real work, not placeholders.
Chess Duel Arena pits two instances of a mini chess engine (0x88 board,
alpha-beta search with quiescence) against each other at different search
depths, from the standard start position to checkmate, stalemate, draw, or
the 200-ply limit. The engine is adapted from the author's tiny-chess
engine that was a finalist in the make.fun tiny-chess competition. The BTC
Paper-Trading Bot is a Python port of the author's make.fun `btc-race-24h`
entry (8th place, $15 USDC): a dip-buy mean-reversion strategy backtested
offline on 1,500 real BTCUSDT 1-minute closes from Binance public market
data (18–19 November 2026), plus two small synthetic fixtures, clearly
labelled, that exercise a take-profit win (+1.84% PnL) and a bounded-loss
exit (−0.97% PnL). Both apps share a FastAPI web UI with a combined
leaderboard and one-click runs in the browser.

## How we used Kiro

This project was built spec-first in the Kiro IDE, and the Kiro-native
parts are committed in the repository under `.kiro/`, so judges can inspect
them directly.

- **Specs (`.kiro/specs/agent-eval-forge/`)** — requirements written in
  EARS format (`requirements.md`: R1–R10, covering task files, execution,
  the deterministic judge, storage, the CLI, the chess engine, duels, the
  web UI, and tests), a design document (`design.md`) describing the
  harness modules, the engine, the duel runner, the backtest engine, and
  the API, and a task list (`tasks.md`) with Phase 1 and Phase 2 checked
  off. New features started in the spec; code followed the task list.
- **Steering (`.kiro/steering/`)** — five rule files every session
  followed: `product.md` (deterministic first, small and honest, specs
  before code, no paid services at runtime), `tech.md` (Python 3.12,
  FastAPI + Uvicorn, SQLite via the standard library, pytest +
  Hypothesis), `structure.md` (repo layout, `.kiro/` must always be
  committed), `security.md` (no credentials in the repo, no network at
  runtime, paper trading only), and `testing.md` (every feature ships
  with tests; green before done).
- **Hooks (`.kiro/hooks/`)** — two JSON hook definitions that trigger on
  file save for Python files: `auto-test.json` runs
  `pytest -q tests/ -x --tb=short`, and `lint-on-save.json` runs a
  compile check with `py_compile` on the saved file. The "lint" hook is a
  compile check, not a full linter.
- **MCP (`.kiro/settings/mcp.json`)** — configuration for two MCP
  servers, `fetch` and `github`, both run through `npx`. The GitHub
  server reads its token from the `GITHUB_PERSONAL_ACCESS_TOKEN`
  environment variable; no token is stored in the repo. These servers are
  for use inside Kiro sessions only — the shipped apps never call them.
- **IDE** — the project was written, run, and tested in the Kiro IDE:
  the specs, steering, hooks, and MCP files above, the `forge/` harness,
  both demo apps, and the test suite were all developed there.
- **Property-based testing** — the suite (79 tests, recorded in the spec
  tasks file) includes Hypothesis property tests asserting judge
  determinism, leaderboard consistency (wins + draws + losses = games
  played, average score in [0, 1]), JSONL round-trips, and backtest
  invariants (equity never below zero, drawdown in [0, 100], trades
  alternating buy/sell from a buy).

What we did **not** use or claim: no Kiro Crew / multi-agent
orchestration, no autonomous agent mode, and no other Kiro feature that
does not appear in the repository. Everything above can be verified by
reading `.kiro/` in the submitted repo.

## How to run (for judges)

From a fresh clone, in the repo root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run the bundled chess-duel eval tasks (takes ~4 minutes; the 5v5 duel alone ~131s)
python -m forge run --tasks tasks/chess-duels.jsonl --db data/results.db --agent forge-arena

# Run the bundled trading-backtest eval tasks (fast, offline)
python -m forge run --tasks tasks/trading-backtests.jsonl --db data/results.db --agent forge-trading

# Show the leaderboard (combined: chess + trading)
python -m forge leaderboard --db data/results.db

# Start the web UI
uvicorn apps.chess_arena.server:app --reload --port 8000
# open http://localhost:8000 (Chess Duel Arena)
# open http://localhost:8000/trading (BTC Paper-Trading Bot)
```

Run the tests with `pytest -q` (79 tests). In the web UI, the "Run a
duel" form defaults to White depth 5, Black depth 2, max ply 200, and
the trading page offers presets for the full real sample, the calm
slice, the dip-bounce fixture, and the crash fixture.

## Notes

- **No API keys. No paid services. No network at runtime.** The harness,
  the chess engine, and the trading bot run fully offline on bundled
  static data. The only network use is installing dependencies with
  `pip`, and the optional MCP servers (fetch/GitHub) used inside Kiro
  sessions — never by the shipped apps.
- **Deterministic.** No randomness, no LLM calls, and no network in the
  scoring path. The same task file always produces the same scores; the
  property tests assert this.
- **Paper trading only.** The trading bot simulates trades against
  historical data. It never holds real funds, keys, or exchange
  credentials, and it is not live trading.
- **Honest fixtures.** The two synthetic price files
  (`btc-dip-bounce.csv`, `btc-crash.csv`) are small, hand-designed, and
  labelled as synthetic in the README; the real 25-hour BTC window is
  too calm for the tuned entry, so its only trade is a guardrail buy at
  bar 1400 (still open, −0.51% PnL) — that result is reported in the
  README rather than hidden.
