"""Tests for the forge eval harness (tasks, judge, store, runner, CLI)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from forge import judge, leaderboard, load_tasks, recent_games, record_result, run_tasks, write_tasks
from forge.runner import EXECUTORS, register
from forge.tasks import TaskValidationError

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------- tasks
def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_load_tasks_valid(tmp_path):
    p = _write(tmp_path / "t.jsonl", (
        '{"id": "a", "kind": "chess-duel", "params": {"x": 1}, "expected": {"winner": "white"}}\n'
        '\n'
        '{"id": "b", "kind": "chess-duel", "params": {}, "expected": {"winner": "draw"}}\n'
    ))
    tasks = load_tasks(p)
    assert [t["id"] for t in tasks] == ["a", "b"]
    assert tasks[0]["params"] == {"x": 1}


def test_load_tasks_bundled_file():
    tasks = load_tasks(ROOT / "tasks" / "chess-duels.jsonl")
    assert [t["id"] for t in tasks] == ["duel-001", "duel-002", "duel-003"]
    assert all(t["kind"] == "chess-duel" for t in tasks)
    assert [t["expected"]["winner"] for t in tasks] == ["white", "black", "black"]
    assert all(t["params"]["max_ply"] == 200 for t in tasks)


def test_load_tasks_invalid_json(tmp_path):
    p = _write(tmp_path / "t.jsonl", '{"id": "a", "kind": "k", "params": {}, "expected": {}}\n{not json\n')
    with pytest.raises(TaskValidationError) as excinfo:
        load_tasks(p)
    assert "line 2" in str(excinfo.value)


def test_load_tasks_missing_field(tmp_path):
    p = _write(tmp_path / "t.jsonl", '{"id": "a", "kind": "k", "params": {}}\n')
    with pytest.raises(TaskValidationError) as excinfo:
        load_tasks(p)
    assert "line 1" in str(excinfo.value)
    assert "expected" in str(excinfo.value)


def test_load_tasks_wrong_type(tmp_path):
    p = _write(tmp_path / "t.jsonl", '{"id": "a", "kind": "k", "params": [], "expected": {}}\n')
    with pytest.raises(TaskValidationError) as excinfo:
        load_tasks(p)
    assert "line 1" in str(excinfo.value)
    assert "params" in str(excinfo.value)


def test_load_tasks_duplicate_id(tmp_path):
    p = _write(tmp_path / "t.jsonl", (
        '{"id": "dup", "kind": "k", "params": {}, "expected": {}}\n'
        '{"id": "dup", "kind": "k", "params": {}, "expected": {}}\n'
    ))
    with pytest.raises(TaskValidationError) as excinfo:
        load_tasks(p)
    assert "line 2" in str(excinfo.value)
    assert "dup" in str(excinfo.value)


def test_load_tasks_non_object_line(tmp_path):
    p = _write(tmp_path / "t.jsonl", '[1, 2, 3]\n')
    with pytest.raises(TaskValidationError) as excinfo:
        load_tasks(p)
    assert "line 1" in str(excinfo.value)


def test_write_tasks_round_trip(tmp_path):
    tasks = [
        {"id": "a", "kind": "chess-duel", "params": {"depth": 5}, "expected": {"winner": "white"}},
        {"id": "b", "kind": "chess-duel", "params": {}, "expected": {"winner": "draw"}},
    ]
    p = tmp_path / "out.jsonl"
    write_tasks(p, tasks)
    assert load_tasks(p) == tasks


# ---------------------------------------------------------------- judge
def _task(expected_winner):
    return {"id": "t", "kind": "chess-duel", "params": {}, "expected": {"winner": expected_winner}}


@pytest.mark.parametrize(
    "expected,actual,passed,score",
    [
        ("white", "white", True, 1.0),
        ("black", "black", True, 1.0),
        ("draw", "draw", True, 1.0),
        ("white", "black", False, 0.0),
        ("black", "white", False, 0.0),
        ("draw", "white", False, 0.0),
        ("white", "draw", False, 0.5),  # draw vs decisive expected: partial credit
        ("black", "draw", False, 0.5),
    ],
)
def test_judge_chess_duel(expected, actual, passed, score):
    out = judge(_task(expected), {"winner": actual})
    assert out["passed"] is passed
    assert out["score"] == score
    assert 0.0 <= out["score"] <= 1.0
    assert out["details"]["expected_winner"] == expected
    assert out["details"]["actual_winner"] == actual


def test_judge_unknown_kind_raises():
    with pytest.raises(ValueError):
        judge({"id": "t", "kind": "nope", "params": {}, "expected": {}}, {"winner": "white"})


def test_judge_score_always_in_range():
    for expected in ("white", "black", "draw"):
        for actual in ("white", "black", "draw"):
            assert 0.0 <= judge(_task(expected), {"winner": actual})["score"] <= 1.0


# ---------------------------------------------------------------- store
def _record(db, **kw):
    base = dict(run_id="run-1", agent="agent-a", task_id="t1", kind="chess-duel",
                winner="white", score=1.0, passed=True, details={}, duration_ms=5)
    base.update(kw)
    record_result(db, **base)


def test_store_round_trip(tmp_path):
    db = tmp_path / "r.db"
    _record(db, task_id="duel-001", details={"plies": 42})
    rows = recent_games(db)
    assert len(rows) == 1
    r = rows[0]
    assert r["task_id"] == "duel-001"
    assert r["agent"] == "agent-a"
    assert r["kind"] == "chess-duel"
    assert r["winner"] == "white"
    assert r["score"] == 1.0
    assert r["passed"] is True
    assert r["details"] == {"plies": 42}
    assert r["created_at"]


def test_store_recent_games_order(tmp_path):
    db = tmp_path / "r.db"
    _record(db, task_id="first")
    _record(db, task_id="second")
    _record(db, task_id="third")
    assert [r["task_id"] for r in recent_games(db)] == ["third", "second", "first"]
    assert [r["task_id"] for r in recent_games(db, limit=2)] == ["third", "second"]


def test_leaderboard_math_chess(tmp_path):
    db = tmp_path / "r.db"
    _record(db, task_id="t1", winner="white", score=1.0, passed=True)
    _record(db, task_id="t2", winner="draw", score=0.5, passed=False)
    _record(db, task_id="t3", winner="black", score=0.0, passed=False)
    rows = leaderboard(db)
    assert len(rows) == 1
    row = rows[0]
    assert row["agent"] == "agent-a"
    assert row["games"] == 3
    assert row["wins"] == 1
    assert row["draws"] == 1
    assert row["losses"] == 1
    assert row["wins"] + row["draws"] + row["losses"] == row["games"]
    assert row["avg_score"] == pytest.approx(0.5)
    assert row["pass_rate"] == pytest.approx(1 / 3)


def test_leaderboard_math_non_chess(tmp_path):
    db = tmp_path / "r.db"
    _record(db, kind="trading-backtest", winner=None, score=1.0, passed=True)
    _record(db, kind="trading-backtest", winner=None, score=0.0, passed=False)
    row = leaderboard(db)[0]
    assert row["games"] == 2
    assert row["wins"] == 1
    assert row["losses"] == 1
    assert row["draws"] == 0
    assert row["wins"] + row["draws"] + row["losses"] == row["games"]


def test_leaderboard_ordering(tmp_path):
    db = tmp_path / "r.db"
    _record(db, agent="low", score=0.0, passed=False)
    _record(db, agent="high", score=1.0, passed=True)
    _record(db, agent="high", score=1.0, passed=True)
    rows = leaderboard(db)
    assert [r["agent"] for r in rows] == ["high", "low"]


def test_leaderboard_empty_db(tmp_path):
    assert leaderboard(tmp_path / "empty.db") == []


# ---------------------------------------------------------------- runner
def test_runner_unknown_kind_no_crash(tmp_path):
    db = tmp_path / "r.db"
    tasks = [{"id": "x1", "kind": "mystery-kind", "params": {}, "expected": {}}]
    results = run_tasks(tasks, agent="agent-a", db_path=db, run_id="run-test")
    assert len(results) == 1
    r = results[0]
    assert r["passed"] is False
    assert r["score"] == 0.0
    assert r["details"]["reason"] == "unknown_kind"
    assert r["run_id"] == "run-test"
    assert recent_games(db)[0]["task_id"] == "x1"


def test_runner_registered_executor(tmp_path, monkeypatch):
    db = tmp_path / "r.db"
    monkeypatch.setitem(EXECUTORS, "echo-duel", lambda params: {"winner": params["winner"]})
    try:
        tasks = [{"id": "e1", "kind": "echo-duel", "params": {"winner": "white"},
                  "expected": {"winner": "white"}}]
        # judge only knows chess-duel; use chess-duel kind via a stub executor instead
        monkeypatch.setitem(EXECUTORS, "chess-duel", lambda params: {"winner": params["winner"]})
        tasks = [{"id": "e1", "kind": "chess-duel", "params": {"winner": "white"},
                  "expected": {"winner": "white"}}]
        results = run_tasks(tasks, agent="agent-a", db_path=db, run_id="run-test")
        assert results[0]["passed"] is True
        assert results[0]["score"] == 1.0
        assert results[0]["winner"] == "white"
        assert results[0]["duration_ms"] >= 0
    finally:
        monkeypatch.delitem(EXECUTORS, "echo-duel", raising=False)
        # restore the real lazy chess-duel executor
        from forge.runner import _chess_duel_executor
        EXECUTORS["chess-duel"] = _chess_duel_executor


def test_runner_executor_error_no_crash(tmp_path, monkeypatch):
    db = tmp_path / "r.db"

    def boom(params):
        raise RuntimeError("kaboom")

    monkeypatch.setitem(EXECUTORS, "chess-duel", boom)
    try:
        tasks = [{"id": "e1", "kind": "chess-duel", "params": {},
                  "expected": {"winner": "white"}}]
        results = run_tasks(tasks, agent="agent-a", db_path=db, run_id="run-test")
        assert results[0]["passed"] is False
        assert results[0]["score"] == 0.0
        assert results[0]["details"]["reason"] == "executor_error"
    finally:
        from forge.runner import _chess_duel_executor
        EXECUTORS["chess-duel"] = _chess_duel_executor


def test_runner_default_run_id(tmp_path, monkeypatch):
    db = tmp_path / "r.db"
    monkeypatch.setitem(EXECUTORS, "chess-duel", lambda params: {"winner": "draw"})
    try:
        results = run_tasks(
            [{"id": "e1", "kind": "chess-duel", "params": {}, "expected": {"winner": "draw"}}],
            agent="agent-a", db_path=db,
        )
        assert results[0]["run_id"].startswith("run-")
    finally:
        from forge.runner import _chess_duel_executor
        EXECUTORS["chess-duel"] = _chess_duel_executor


def test_register_adds_executor():
    register("tmp-kind-xyz", lambda params: {"winner": "draw"})
    assert EXECUTORS["tmp-kind-xyz"] is not None
    del EXECUTORS["tmp-kind-xyz"]


# ---------------------------------------------------------------- CLI
def _run_cli(*argv, cwd=ROOT):
    return subprocess.run(
        [sys.executable, "-m", "forge", *argv],
        cwd=str(cwd), capture_output=True, text=True, timeout=120,
    )


def test_cli_run_smoke(tmp_path):
    # Tiny duels (depth 1 vs 1, 8 plies) finish by ply-limit draw, so
    # they are fast and deterministic. The executor is built now, so
    # the CLI must report PASS lines and exit 0.
    tasks_file = _write(tmp_path / "tiny.jsonl", (
        '{"id": "smoke-1", "kind": "chess-duel", "params": {"white": {"name": "Forge-Quick", "depth": 1}, "black": {"name": "Forge-Quick", "depth": 1}, "max_ply": 8}, "expected": {"winner": "draw"}}\n'
        '{"id": "smoke-2", "kind": "chess-duel", "params": {"white": {"name": "Forge-Quick", "depth": 1}, "black": {"name": "Forge-Quick", "depth": 1}, "max_ply": 8}, "expected": {"winner": "draw"}}\n'
    ))
    db = tmp_path / "r.db"
    proc = _run_cli("run", "--tasks", str(tasks_file),
                    "--db", str(db), "--agent", "forge-arena")
    assert proc.returncode == 0, proc.stderr
    assert "PASS smoke-1 chess-duel score=1.00" in proc.stdout
    assert "PASS smoke-2 chess-duel score=1.00" in proc.stdout


def test_cli_run_missing_file(tmp_path):
    proc = _run_cli("run", "--tasks", str(tmp_path / "nope.jsonl"),
                    "--db", str(tmp_path / "r.db"), "--agent", "a")
    assert proc.returncode != 0


def test_cli_run_invalid_file(tmp_path):
    bad = tmp_path / "bad.jsonl"
    bad.write_text('{"id": "x"}\n', encoding="utf-8")
    proc = _run_cli("run", "--tasks", str(bad), "--db", str(tmp_path / "r.db"), "--agent", "a")
    assert proc.returncode != 0
    assert "line 1" in proc.stderr


def test_cli_leaderboard_table_and_json(tmp_path):
    db = tmp_path / "r.db"
    _record(db, agent="agent-a", winner="white", score=1.0, passed=True)
    proc = _run_cli("leaderboard", "--db", str(db))
    assert proc.returncode == 0, proc.stderr
    assert "agent-a" in proc.stdout
    assert "avg_score" in proc.stdout
    proc = _run_cli("leaderboard", "--db", str(db), "--format", "json")
    assert proc.returncode == 0, proc.stderr
    rows = json.loads(proc.stdout)
    assert rows[0]["agent"] == "agent-a"
    assert rows[0]["games"] == 1
    assert rows[0]["wins"] == 1
