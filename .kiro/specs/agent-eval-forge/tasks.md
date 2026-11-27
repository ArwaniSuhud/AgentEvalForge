# Tasks — AgentEval Forge

## Phase 1 (this build)

- [x] 1. Scaffold repo: README, MIT LICENSE, .gitignore (never ignores
  `.kiro/`), requirements.txt, folder layout.
- [x] 2. Write `.kiro/steering/` (product, tech, structure, security,
  testing).
- [x] 3. Write `.kiro/specs/agent-eval-forge/` requirements (EARS),
  design, and this task list.
- [x] 4. Write `.kiro/hooks/` (auto-test + lint on save) and
  `.kiro/settings/mcp.json` (fetch + GitHub).
- [x] 5. Build eval harness `forge/` (tasks, runner, judge, store,
  CLI) + sample task file `tasks/chess-duels.jsonl`.
- [x] 6. Build Chess Duel Arena `apps/chess_arena/` (vendored engine,
  duel runner, FastAPI server + static UI).
- [x] 7. Write tests: `tests/test_harness.py`,
  `tests/test_harness_properties.py` (Hypothesis),
  `tests/test_chess_arena.py`.
- [x] 8. End-to-end verification: `pip install -r requirements.txt`,
  `python -m forge run`, `python -m forge leaderboard`, `pytest -q`,
  boot the web server and hit `/api/leaderboard`. All green.

Note (2026-11-19): `duel-002` expected was corrected from `draw` to
`black` after two verified runs — same-depth (5v5) game ends in
checkmate for Black at ply 142. Full bundled run takes ~4 minutes
(duel-002 alone ~131s); the test suite uses tiny duels only.

## Phase 2 (done 2026-11-19)

- [x] 9. Demo app 2: BTC Paper-Trading Bot (`apps/trading_bot/`) —
  backtest executor `trading-backtest`, sample tasks, UI panel.
  Verified: `tasks/trading-backtests.jsonl` 4/4 PASS; full pytest
  suite 79 passed, 0 failed; chess-duel CLI 3/3 PASS (phase 1
  intact); web server verified (`/trading`, `POST /api/backtest`).
  real 25h BTC window (18–19 Nov 2026) is too calm for the tuned
  entry — only the bar-1400 guardrail leg fires (bt-004) — so
  bt-001/bt-003 use small synthetic fixtures with hand-designed
  price paths (labelled in README). The stop-loss is unreachable
  while `trail_bps < stop_loss_bps` (trailing stop always triggers
  first); kept as defence-in-depth.
- [x] 10. Polish: fresh-clone test, README screenshots, blog draft,
  demo video script, Devpost submission text. (done 2026-11-19,
  phase 3: fresh clone in /tmp — Python 3.12.3, venv + pip install
  OK, pytest 79 passed, trading 4/4 PASS, chess 3/3 PASS,
  leaderboard OK, GET /, /trading, /api/leaderboard, /api/games all
  200; screenshots in docs/screenshots/ linked from README;
  docs/blog-draft.md, docs/video-script.md (2:45),
  docs/submission-text.md.)
- [ ] 11. Submit on Devpost (user does this; assistant prepares text).

## Phase 3 — Kiro polish (done 2026-11-27)

- [x] 12. Executor ketiga "math-word" (`forge/runner.py`,
  `forge/judge.py`, `tasks/math-word.jsonl`,
  `tests/test_math_executor.py`) — deterministic word-problem
  evaluation with a tiny built-in arithmetic solver (AST walk, no
  `eval()`, no LLM, no network); judge passes iff the numeric answer
  matches within 1e-9. README executor list + run command updated.
  Verified: `pytest -q` 101 passed (79 baseline + 18 math + 4 UI);
  `python -m forge run --tasks tasks/math-word.jsonl` 8/8 PASS;
  chess 3/3 + trading 4/4 still PASS; existing executors/judge
  untouched.
- [x] 13. UI dashboard polish (`apps/chess_arena/static/forge.css`,
  both static pages, `apps/chess_arena/server.py`) — one shared
  stylesheet served at `/static/forge.css`, shared top nav on both
  pages (Chess Arena <-> Trading Bot, current page marked), and a
  "Recent trading backtests" section on the chess page fed by the
  existing `/api/backtests` endpoint (no new API). Duel/backtest
  forms unchanged. README screenshots captions updated.
  Verified: `pytest -q` 101 passed; local server serves `/`,
  `/trading`, `/static/forge.css`, `/api/leaderboard`, `/api/games`,
  `/api/backtests` all 200; leaderboard shows chess + trading results.
