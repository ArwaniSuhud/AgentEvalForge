# Structure — AgentEval Forge

```
agent-eval-forge/
├── README.md                 Project overview + quick start
├── LICENSE                   MIT
├── .gitignore                Python standard; NEVER ignores .kiro/
├── requirements.txt
├── .kiro/
│   ├── steering/             Product, tech, structure, security, testing
│   ├── specs/
│   │   └── agent-eval-forge/ requirements.md, design.md, tasks.md
│   ├── hooks/                auto-test + lint on file save
│   └── settings/mcp.json     fetch + GitHub MCP servers
├── forge/                    Eval harness package
│   ├── __init__.py
│   ├── __main__.py           `python -m forge`
│   ├── cli.py                `eval run` / `eval leaderboard` commands
│   ├── tasks.py              JSONL task loading + validation
│   ├── judge.py              Deterministic judge (pure functions)
│   ├── store.py              SQLite result storage + leaderboard query
│   └── runner.py             Task execution + recording
├── apps/
│   ├── chess_arena/          Demo app 1
│   │   ├── engine.py         Vendored mini chess engine (standalone)
│   │   ├── duel.py           Engine-vs-engine game runner
│   │   ├── server.py         FastAPI app (leaderboard UI + duel API)
│   │   └── static/index.html Frontend (no build step)
│   └── trading_bot/          Demo app 2 (phase 2)
├── tasks/                    Bundled eval task files (JSONL)
├── tests/                    pytest + Hypothesis tests
└── data/                     SQLite results (gitignored)
```

## Rules

- The `/.kiro` folder at the repo root must always be committed. Never
  add it to `.gitignore`.
- New demo apps go under `apps/<name>/` with the same shape:
  `engine/logic`, `runner`, `server.py`, `static/`.
- Shared evaluation code lives in `forge/` only — apps never duplicate
  judge or store logic.
- Task files in `tasks/` are versioned inputs: changing one is a
  deliberate act, recorded in the spec tasks.
- `data/` holds local run output only and is gitignored.
