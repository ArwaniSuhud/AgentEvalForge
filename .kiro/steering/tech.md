# Tech — AgentEval Forge

## Stack

- **Language:** Python 3.12 (stdlib first; third-party only where listed).
- **Web:** FastAPI + Uvicorn. HTML/JS frontend with no build step
  (plain static files served by FastAPI).
- **Storage:** SQLite (stdlib `sqlite3`). One database file per run
  (`data/results.db` by default). No ORM.
- **Tests:** pytest + Hypothesis (property-based tests).
- **Eval harness:** pure Python, deterministic, no network, no LLM.

## Dependencies

Pinned in `requirements.txt`:

- `fastapi`, `uvicorn[standard]` — web UI and API.
- `pytest`, `hypothesis` — unit + property tests.
- `httpx` — test client transport for FastAPI tests.

No other runtime dependencies. Do not add one without a spec task
that justifies it.

## Conventions

- Python code follows the stdlib style: `snake_case` functions,
  `PascalCase` classes, type hints on public functions, docstrings on
  modules and public functions.
- Every module has a single responsibility and no hidden global state
  that leaks between runs (engines and stores are constructed per run).
- Determinism: any randomness must take an explicit seed; default
  seeds are fixed constants, never `time.time()` or `os.urandom()`.
- Errors are explicit: functions raise `ValueError` for bad input and
  never silently swallow exceptions in the scoring path.
- The eval harness never imports the web server, and the web server
  only reads results through `forge.store` — one direction of
  dependency, no cycles.
