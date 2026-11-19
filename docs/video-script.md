# AgentEval Forge — Demo Video Script

**Total runtime: 2 minutes 45 seconds (2:45). No long voiceover — screen recording
+ on-screen text overlays + short captions. Record everything from this repo only:
the `forge` CLI and the web UI at `http://localhost:8000`.**

**Recording notes (read before filming):**

- Record from a fresh terminal in the repo root, with the virtual environment
  already created and dependencies installed (`python3 -m venv .venv`,
  `source .venv/bin/activate`, `pip install -r requirements.txt`).
- The full bundled chess run takes about 4 minutes (the 5v5 duel alone takes
  ~131 seconds — see `.kiro/specs/agent-eval-forge/tasks.md`), so do **not**
  run the full chess file on camera. Run only the trading file live, and show
  the chess results from a pre-run `data/results.db` (run the chess file
  off-camera beforehand). On camera, run one short duel from the web UI with
  shallow depths (White 2, Black 2, max ply 60) and cut to the result.
- The trading backtest is fast (offline, static data). The leaderboard command
  is instant.
- Keep the terminal font large. Do not type passwords or tokens at any point —
  none are needed.

---

## Scene 1 — 0:00–0:15 (15s) — Hook

**On screen:** Terminal in the repo root. Title card overlay on the recording.

**Overlay text:** `AgentEval Forge — evaluate agents without an LLM judge.`

**Action:** Type `ls` (or show the repo tree) so `.kiro/`, `forge/`, `apps/`,
`tasks/` and `tests/` are visible. Hold the shot.

**Caption:** `A spec-driven eval template, built with Kiro.`

## Scene 2 — 0:15–0:35 (20s) — Specs first

**On screen:** Open `.kiro/specs/agent-eval-forge/requirements.md` in the editor.
Scroll slowly past the EARS requirements (R1–R3 visible).

**Overlay text:** `Specs first. Requirements in EARS format — then design, then tasks.`

**Action:** Click through the three files in the specs folder:
`requirements.md` → `design.md` → `tasks.md`, pausing on the checked-off
Phase 1 and Phase 2 task lists.

**Caption:** `Every feature starts as a checked task, not a guess.`

## Scene 3 — 0:35–0:55 (20s) — Steering, hooks, MCP

**On screen:** File tree of `.kiro/`: `steering/`, `hooks/`, `settings/mcp.json`.

**Overlay text:** `Steering: product, tech, structure, security, testing.`

**Action:** Open `.kiro/steering/testing.md`, then `.kiro/hooks/auto-test.json`
(show the `pytest -q tests/ -x --tb=short` command and `when: fileSaved`),
then `.kiro/settings/mcp.json` (show the `fetch` and `github` servers).

**Caption:** `Hooks run the tests on save. MCP is fetch + GitHub config only.`

## Scene 4 — 0:55–1:20 (25s) — Run the trading eval (live CLI)

**On screen:** Terminal.

**Overlay text:** `No API keys. No network. Deterministic scores.`

**Action:** Run exactly:

```bash
python -m forge run --tasks tasks/trading-backtests.jsonl --db data/results.db --agent forge-trading
```

Show all four lines: `PASS bt-001 … PASS bt-002 … PASS bt-003 … PASS bt-004`.
Then run:

```bash
python -m forge leaderboard --db data/results.db
```

Show the table with `forge-trading` (and `forge-arena`, pre-run off-camera).

**Caption:** `4/4 backtests pass — same file, same scores, every run.`

## Scene 5 — 1:20–1:50 (30s) — Chess Arena in the browser

**On screen:** Browser at `http://localhost:8000` (server already running:
`uvicorn apps.chess_arena.server:app --reload --port 8000`).

**Overlay text:** `Chess Duel Arena — two mini engines, one leaderboard.`

**Action:** Show the leaderboard and recent-games tables. In the "Run a duel"
form set White depth `2`, Black depth `2`, Max ply `60`, and click
**Run a duel**. Cut (jump-cut, with a "running…" caption) to the result box:
`Winner: … / Plies: … / Moves: …`. Point at the leaderboard refreshing.

**Caption:** `Depth 5 vs depth 2 in the bundled tasks. The 5v5 duel ends in checkmate for Black at ply 142.`

## Scene 6 — 1:50–2:20 (30s) — BTC Paper-Trading Bot in the browser

**On screen:** Browser at `http://localhost:8000/trading`.

**Overlay text:** `BTC Paper-Trading Bot — backtested offline on real BTC data.`

**Action:** Click the **Dip-bounce fixture** preset, then **Run backtest**.
Show the result: `Trades: 2 … Net PnL: +1.84% … take-profit`. Then click the
**Crash fixture** preset, run it, and show `Trades: 2 … Net PnL: −0.97% …
trailing-stop (bounded loss)`.

**Caption:** `1,500 real BTC 1-minute closes. Synthetic fixtures labelled. Paper money only.`

## Scene 7 — 2:20–2:45 (25s) — Tests + close

**On screen:** Terminal.

**Overlay text:** `79 tests green — including Hypothesis property tests.`

**Action:** Run `pytest -q` and show the final line (`79 passed`). Cut to a
closing title card with the repo name.

**Overlay text (closing card):** `AgentEval Forge — clone it, run it, add your own executor.`

**Caption:** `Deterministic evals. No API keys. Specs included.`
