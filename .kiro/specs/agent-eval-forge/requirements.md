# Requirements — AgentEval Forge

Spec-driven requirements for the Skeleton Crew submission (Kiroween 2026).
Written in EARS format (Easy Approach to Requirements Syntax).

## 1. Eval harness (`forge/`)

### R1 — Task files
- **R1.1** WHEN the runner is given a JSONL task file, THE SYSTEM SHALL
  load every line as one task with fields `id`, `kind`, `params`,
  `expected`.
- **R1.2** WHEN a task line is missing a required field or is not valid
  JSON, THE SYSTEM SHALL reject the file with a clear error naming the
  line number.
- **R1.3** WHEN two tasks in one file share the same `id`, THE SYSTEM
  SHALL reject the file as invalid.

### R2 — Execution
- **R2.1** WHEN a task is run, THE SYSTEM SHALL dispatch it to the
  executor registered for its `kind` (e.g. `chess-duel`).
- **R2.2** WHEN a task has an unknown `kind`, THE SYSTEM SHALL record
  the task as failed with reason `unknown_kind` instead of crashing.
- **R2.3** WHEN a task runs, THE SYSTEM SHALL record wall-clock
  duration in milliseconds.

### R3 — Deterministic judge
- **R3.1** WHEN the judge scores a result, THE SYSTEM SHALL return a
  score in `[0, 1]` and a boolean `passed`, computed only from the
  task's `expected` field and the executor's actual result.
- **R3.2** WHEN the judge is called twice with the same inputs, THE
  SYSTEM SHALL return identical outputs (determinism).
- **R3.3** THE SYSTEM SHALL NOT call any LLM, network service, or
  random source during judging.

### R4 — Storage and leaderboard
- **R4.1** WHEN a task finishes, THE SYSTEM SHALL persist its result
  (agent, task id, score, passed, details, duration) in SQLite.
- **R4.2** WHEN the leaderboard is requested, THE SYSTEM SHALL return
  one row per agent with games played, wins, draws, losses, average
  score, and pass rate, ordered by average score descending.
- **R4.3** WHEN the leaderboard is computed, wins + draws + losses
  SHALL equal games played for every agent.

### R5 — CLI
- **R5.1** THE SYSTEM SHALL provide `python -m forge run --tasks
  <file> --db <file> --agent <name>` to execute a task file.
- **R5.2** THE SYSTEM SHALL provide `python -m forge leaderboard --db
  <file>` to print the leaderboard (human table and `--format json`).

## 2. Chess Duel Arena (`apps/chess_arena/`)

### R6 — Engine
- **R6.1** THE SYSTEM SHALL reuse the author's tiny-chess engine
  (0x88 board, alpha-beta search) as a standalone module with no
  network dependency.
- **R6.2** WHEN asked for legal moves from a position, THE SYSTEM SHALL
  return only moves that do not leave the mover's king in check.
- **R6.3** WHEN asked for the best move, THE SYSTEM SHALL return a
  legal move in UCI notation.
- **R6.4** THE SYSTEM SHALL support different strength configs (search
  depth) so two engine instances can play at different levels.

### R7 — Duels
- **R7.1** WHEN a duel is played, THE SYSTEM SHALL alternate moves
  between the two engine configs from the standard start position
  until checkmate, stalemate, draw, or the ply limit (default 200).
- **R7.2** WHEN a duel ends, THE SYSTEM SHALL report winner
  (`white` / `black` / `draw`), reason, the full move list, and ply
  count.
- **R7.3** WHEN the same duel configs are played twice, THE SYSTEM
  SHALL produce identical results (determinism).

### R8 — Web UI
- **R8.1** THE SYSTEM SHALL serve a web page at `/` showing the
  leaderboard and recent games.
- **R8.2** THE SYSTEM SHALL expose `GET /api/leaderboard` returning
  the leaderboard as JSON.
- **R8.3** THE SYSTEM SHALL expose `POST /api/duel` to run one duel
  and store its result.
- **R8.4** THE SYSTEM SHALL expose `GET /api/games` returning recent
  duel results.

## 3. Template quality

### R9 — Repo
- **R9.1** THE SYSTEM SHALL include a README, an MIT LICENSE, and a
  `.gitignore` that does not ignore `.kiro/`.
- **R9.2** THE SYSTEM SHALL include a `.kiro/` folder at the root with
  steering, specs, hooks, and MCP settings.
- **R9.3** THE SYSTEM SHALL run end-to-end from a fresh clone with
  only `pip install -r requirements.txt` and no API keys.

### R10 — Tests
- **R10.1** THE SYSTEM SHALL include pytest unit tests for the
  harness, the judge, the store, the engine, duels, and the API.
- **R10.2** THE SYSTEM SHALL include at least one Hypothesis
  property-based test asserting a meaningful invariant (judge
  determinism and/or leaderboard consistency).
- **R10.3** THE SYSTEM SHALL pass the full test suite (`pytest -q`)
  with zero failures before a phase is reported complete.
