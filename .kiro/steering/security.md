# Security — AgentEval Forge

- **No credentials in the repo.** No API keys, tokens, passwords, or
  private keys — in code, in tests, in specs, or in git history. The
  project must run with zero secrets.
- **No network at runtime.** The harness, the chess engine, and the
  trading bot never make outbound network calls. The only network use
  is the developer installing dependencies and the optional MCP servers
  (fetch/GitHub) used inside Kiro sessions, never by the shipped apps.
- **Paper trading only.** The trading bot (phase 2) simulates trades
  against historical data. It must never hold real funds, keys, or
  exchange credentials, and its README must say so.
- **Validate all input.** Task JSONL files, API request bodies, and
  query parameters are validated before use; malformed input is
  rejected with a clear error, never executed.
- **SQLite safety.** All SQL uses parameterized queries. The database
  file path comes from CLI flags or constants, never from untrusted
  input.
- **No `eval`/`exec` on untrusted data.** Task files describe data,
  not code. The JSONL loader parses JSON only.
- **Dependencies.** Only the packages in `requirements.txt`; no
  new dependency without a spec task and a review of what it does.
