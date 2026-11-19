"""SQLite result store (stdlib sqlite3 only, all queries parameterized)."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

__all__ = ["init_db", "record_result", "leaderboard", "recent_games"]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    agent TEXT,
    task_id TEXT,
    kind TEXT,
    winner TEXT,
    score REAL,
    passed INTEGER,
    details TEXT,
    duration_ms INTEGER,
    created_at TEXT
)
"""


def _connect(db_path):
    path = Path(db_path)
    if path.parent and str(path.parent) not in ("", "."):
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(path) -> None:
    """Create the ``results`` table if it does not exist yet."""
    with _connect(path) as conn:
        conn.execute(_SCHEMA)
        conn.commit()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def record_result(
    db_path,
    *,
    run_id,
    agent,
    task_id,
    kind,
    winner,
    score,
    passed,
    details,
    duration_ms,
) -> None:
    """Insert one result row. ``details`` is stored as JSON text."""
    init_db(db_path)
    with _connect(db_path) as conn:
        conn.execute(
            """INSERT INTO results
               (run_id, agent, task_id, kind, winner, score, passed,
                details, duration_ms, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run_id,
                agent,
                task_id,
                kind,
                winner,
                float(score),
                1 if passed else 0,
                json.dumps(details, ensure_ascii=False),
                int(duration_ms),
                _utc_now_iso(),
            ),
        )
        conn.commit()


def leaderboard(db_path, limit: int = 50) -> list[dict]:
    """One row per agent: agent, games, wins, draws, losses, avg_score, pass_rate.

    Ordered by avg_score DESC, games DESC. Convention: the evaluated
    agent always plays White, so for chess-duel rows wins = winner
    'white', draws = 'draw', losses = any other outcome ('black' or a
    failed run with no winner). For non-chess kinds wins = passed rows,
    losses = failed rows, draws = 0. In all cases
    wins + draws + losses == games.
    """
    init_db(db_path)
    with _connect(db_path) as conn:
        rows = conn.execute(
            """SELECT agent,
                      COUNT(*) AS games,
                      SUM(CASE
                            WHEN kind = 'chess-duel' AND winner = 'white' THEN 1
                            WHEN kind != 'chess-duel' AND passed = 1 THEN 1
                            ELSE 0 END) AS wins,
                      SUM(CASE
                            WHEN kind = 'chess-duel' AND winner = 'draw' THEN 1
                            ELSE 0 END) AS draws,
                      SUM(CASE
                            WHEN kind = 'chess-duel' AND COALESCE(winner, '') NOT IN ('white', 'draw') THEN 1
                            WHEN kind != 'chess-duel' AND passed = 0 THEN 1
                            ELSE 0 END) AS losses,
                      AVG(score) AS avg_score,
                      AVG(passed) AS pass_rate
               FROM results
               GROUP BY agent
               ORDER BY avg_score DESC, games DESC
               LIMIT ?""",
            (int(limit),),
        ).fetchall()
    out = []
    for r in rows:
        games = int(r["games"])
        out.append(
            {
                "agent": r["agent"],
                "games": games,
                "wins": int(r["wins"] or 0),
                "draws": int(r["draws"] or 0),
                "losses": int(r["losses"] or 0),
                "avg_score": float(r["avg_score"]) if r["avg_score"] is not None else 0.0,
                "pass_rate": float(r["pass_rate"]) if r["pass_rate"] is not None else 0.0,
            }
        )
    return out


def recent_games(db_path, limit: int = 20) -> list[dict]:
    """Most recent result rows (newest first by id)."""
    init_db(db_path)
    with _connect(db_path) as conn:
        rows = conn.execute(
            """SELECT task_id, agent, kind, winner, score, passed, details, created_at
               FROM results
               ORDER BY id DESC
               LIMIT ?""",
            (int(limit),),
        ).fetchall()
    out = []
    for r in rows:
        try:
            details = json.loads(r["details"]) if r["details"] else {}
        except json.JSONDecodeError:
            details = {}
        out.append(
            {
                "task_id": r["task_id"],
                "agent": r["agent"],
                "kind": r["kind"],
                "winner": r["winner"],
                "score": float(r["score"]) if r["score"] is not None else 0.0,
                "passed": bool(r["passed"]),
                "details": details,
                "created_at": r["created_at"],
            }
        )
    return out
