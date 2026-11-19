# Testing — AgentEval Forge

- **Every feature ships with tests.** A new executor, judge rule, or
  endpoint lands together with its tests in the same change.
- **Unit tests (pytest)** cover: task loading/validation, judge rules
  (including edge cases), SQLite store round-trips, engine move
  legality, duel termination, and API endpoints.
- **Property-based tests (Hypothesis)** cover invariants that unit
  tests cannot enumerate:
  - the judge is deterministic: same input always gives the same output;
  - leaderboard aggregation is consistent: wins + draws + losses equal
    games played, and average score stays in `[0, 1]`;
  - task JSONL round-trips: write then read returns the same tasks.
- **No network in tests.** Tests run fully offline; the FastAPI
  `TestClient` is used in-process.
- **Fast.** The full suite must finish in under a minute on a normal
  laptop, so the auto-test hook can run on every save.
- **Green before done.** A task is not finished while any test fails
  or while coverage of new code is missing. Run `pytest -q` before
  reporting a phase complete.
- **Determinism is tested, not assumed.** Any test that depends on
  ordering, timing, or randomness must fix its seed and assert the
  same result across repeated runs.
