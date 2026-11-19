# Product — AgentEval Forge

## What this product is

AgentEval Forge is a spec-driven template for building and evaluating AI
agents with Kiro. It ships a reusable foundation (specs, steering, hooks,
MCP) and proves it with two small demo apps built from that same
foundation:

1. **Chess Duel Arena** — two mini chess engines duel; games are scored
   by the eval harness and shown on a web leaderboard.
2. **BTC Paper-Trading Bot** — a backtested paper-trading bot scored by
   the same harness (phase 2).

## Who it is for

- Developers who want to evaluate AI agents deterministically, without
  paying for an LLM judge at runtime.
- Hackathon builders who want a Kiro-native starting point: specs first,
  then code, then tests — with hooks enforcing the loop.

## Principles

- **Deterministic first.** Every evaluation must be reproducible: the
  same task file always produces the same score. No randomness, no
  network, no LLM calls in the scoring path.
- **Small and honest.** Prefer a tiny working feature over a large
  promised one. Never fake a capability (no mock scores, no placeholder
  "AI" that does nothing).
- **Specs before code.** New features start in `.kiro/specs/` with
  requirements (EARS), design, and tasks. Code that has no spec task
  does not get written.
- **No paid services at runtime.** The harness, the arena, and the
  trading bot must run fully offline with zero API keys.
- **English everywhere.** All user-facing text, docs, specs, and UI
  strings are in English (hackathon submission requirement).

## Out of scope

- Live trading with real money. The trading bot is paper-trading only.
- Online multiplayer. Chess duels are engine-vs-engine, local only.
- User accounts, auth, or hosted deployment. This is a local-first
  template; judges run it from a fresh clone.
