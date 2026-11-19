# Building AgentEval Forge with Kiro: Specs First, Then Code

*Draft blog post — AgentEval Forge, Kiroween 2026 (Skeleton Crew)*

Most tools I built started the messy way: code first, explanation later. AgentEval Forge started the other way — a template for building and evaluating AI agents with Kiro, whose first artefact was a spec, not code.

Under `.kiro/specs/agent-eval-forge/` there are three files: `requirements.md` in EARS format, `design.md`, and `tasks.md`, a checked-off list of the work in two phases. The requirements are deliberately plain — "WHEN the runner is given a JSONL task file, THE SYSTEM SHALL load every line as one task" — because a requirement I cannot test is just a wish. The design maps the pieces: a deterministic harness in `forge/`, two demo apps, SQLite underneath.

That order paid off with the second demo app: the harness already knew how to load, dispatch, judge, and store a task, so I only registered a new executor, `trading-backtest`, beside `chess-duel`.

## Steering: the rules every session follows

Specs describe one project; steering describes how I work on it — five files under `.kiro/steering/`: product, tech, structure, security, testing. Product says deterministic first, small and honest, specs before code, no paid services. Tech pins the stack — Python 3.12, FastAPI, SQLite, pytest plus Hypothesis — and forbids a new dependency without a spec task justifying it. Security says no credentials in the repo, no network at runtime. Testing says every feature ships with its tests. I wrote them in the Kiro IDE and committed them with the template.

## Hooks and MCP: a small loop, honestly described

The repo has two hook definitions in `.kiro/hooks/`, both JSON files that run on file save for Python files: `auto-test.json` runs `pytest -q tests/ -x --tb=short`; `lint-on-save.json` runs a compile check with `py_compile`. That is all they do — the "lint" hook is a compile check, not a full linter.

MCP is equally modest: `.kiro/settings/mcp.json` configures fetch and GitHub servers via `npx`, the latter reading its token from `GITHUB_PERSONAL_ACCESS_TOKEN` — no token in the repo, and only for use inside Kiro sessions.

## A judge that does not need an LLM

The heart of the project is the harness in `forge/`. A task is one JSONL line with `id`, `kind`, `params`, and `expected`. The runner dispatches it, times it, and hands it to a judge that is a pure function: no randomness, no network, no LLM. A chess duel scores on whether the actual winner matches the expected winner (a draw against a decisive expectation scores 0.5). A trading backtest passes when it makes at least the expected number of trades, its net PnL is at or above the expected floor, and its drawdown stays within its limit. Scores land in SQLite, and `forge leaderboard` aggregates them per agent across both demo apps.

Determinism is tested, not just claimed. The suite has 79 tests (recorded in the spec tasks file), including Hypothesis property tests: identical judge inputs give identical outputs, leaderboard rows always satisfy wins + draws + losses = games played, and backtest invariants hold — equity never below zero, drawdown in [0, 100], trades alternating buy and sell from a buy.

## Two demo apps from real work

Chess Duel Arena reuses my mini chess engine — a 0x88 board, alpha-beta search with quiescence, a transposition table, and killer/history heuristics — adapted from the tiny-chess engine that was a finalist in the make.fun tiny-chess competition. Two instances play from the start position at different depths until checkmate, stalemate, draw, or 200 plies. The bundled tasks are honest: the 5-versus-5 duel ends in checkmate for Black at ply 142, and its expected winner was corrected to `black` after two verified runs.

The BTC Paper-Trading Bot is a Python port of my make.fun `btc-race-24h` entry, which placed 8th and won $15 USDC. It is dip-buy mean reversion: buy a dip of at least 2.15% off the 105-bar high once price recovers 0.2% off the window low, then exit at a 1.9% take-profit, a 1.0% trailing stop, or a 1.2% stop-loss, with a 4 bps fee per side on $1,000 of paper cash. It runs offline on 1,500 real BTCUSDT 1-minute closes from Binance public market data (18–19 November 2026), plus two small synthetic fixtures, clearly labelled, for a take-profit win (+1.84% PnL) and a bounded-loss exit (−0.97% PnL). The real 25-hour window is almost too calm: its only trade is a guardrail buy at bar 1400, still open at −0.51%.

Both apps share one FastAPI web UI on port 8000 — the arena at `/`, the trading bot at `/trading` — with a combined leaderboard and buttons to run a duel or a backtest. Plain static HTML; no build step.

## What I would steal for the next project

Three things. First, the spec before the code: EARS requirements forced me to decide what "done" meant before I had code to defend. Second, the steering files: five short documents that keep every session honest about scope, secrets, and tests. Third, the deterministic judge: once scoring is a pure function, arguing about a result becomes arguing about the data.

AgentEval Forge is a template, not a product — deliberately small. Clone it, run `pytest -q` and the two bundled eval files, and open the leaderboard at `http://localhost:8000`. Then add your own executor — spec first — and let the harness score it.

*Try it: clone the repository, follow the README quick start, and run your first eval — no API keys required.*
