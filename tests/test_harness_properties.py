"""Hypothesis property tests for the forge eval harness."""

from __future__ import annotations

import tempfile
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from forge import judge, leaderboard, load_tasks, record_result, write_tasks

WINNERS = st.sampled_from(["white", "black", "draw"])


# ---------------------------------------------------------------- (a) judge is deterministic
@given(expected=WINNERS, actual=WINNERS)
def test_judge_deterministic(expected, actual):
    task = {"id": "t", "kind": "chess-duel", "params": {}, "expected": {"winner": expected}}
    result = {"winner": actual}
    first = judge(task, result)
    second = judge(task, result)
    assert first == second
    assert 0.0 <= first["score"] <= 1.0
    assert first["passed"] == (actual == expected)


@given(expected=WINNERS, actual=WINNERS)
def test_judge_score_shape(expected, actual):
    task = {"id": "t", "kind": "chess-duel", "params": {}, "expected": {"winner": expected}}
    out = judge(task, {"winner": actual})
    if actual == expected:
        assert out["score"] == 1.0 and out["passed"] is True
    elif actual == "draw":
        assert out["score"] == 0.5 and out["passed"] is False
    else:
        assert out["score"] == 0.0 and out["passed"] is False


# ---------------------------------------------------------------- (b) leaderboard is consistent
@st.composite
def _random_rows(draw):
    n = draw(st.integers(min_value=0, max_value=30))
    agents = draw(st.lists(
        st.sampled_from(["agent-a", "agent-b", "agent-c"]),
        min_size=n, max_size=n,
    ))
    rows = []
    for agent in agents:
        kind = draw(st.sampled_from(["chess-duel", "other-kind"]))
        if kind == "chess-duel":
            winner = draw(WINNERS)
            passed = winner == "white"  # arbitrary but consistent-ish
        else:
            winner = None
            passed = draw(st.booleans())
        rows.append({
            "agent": agent,
            "kind": kind,
            "winner": winner,
            "score": draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False)),
            "passed": passed,
        })
    return rows


@given(rows=_random_rows())
@settings(max_examples=50)
def test_leaderboard_consistent(rows):
    # NOTE: tmp_path fixture cannot be used with @given (Hypothesis
    # health check); use a fresh temp dir per generated example instead.
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "r.db"
        for i, r in enumerate(rows):
            record_result(
                db, run_id="run-prop", agent=r["agent"], task_id=f"t{i}", kind=r["kind"],
                winner=r["winner"], score=r["score"], passed=r["passed"],
                details={}, duration_ms=1,
            )
        board = leaderboard(db)
    total_games = sum(row["games"] for row in board)
    assert total_games == len(rows)
    for row in board:
        assert row["wins"] + row["draws"] + row["losses"] == row["games"]
        assert 0.0 <= row["avg_score"] <= 1.0
        assert 0.0 <= row["pass_rate"] <= 1.0
        assert row["games"] >= 1


# ---------------------------------------------------------------- (c) JSONL round-trip
@st.composite
def _random_tasks(draw):
    n = draw(st.integers(min_value=0, max_value=10))
    ids = draw(st.lists(
        st.sampled_from([f"task-{i}" for i in range(100)]),
        min_size=n, max_size=n, unique=True,
    ))
    tasks = []
    for task_id in ids:
        tasks.append({
            "id": task_id,
            "kind": draw(st.sampled_from(["chess-duel", "other-kind"])),
            "params": {"depth": draw(st.integers(min_value=1, max_value=5))},
            "expected": {"winner": draw(WINNERS)},
        })
    return tasks


@given(tasks=_random_tasks())
@settings(max_examples=50)
def test_jsonl_round_trip(tasks):
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "tasks.jsonl"
        write_tasks(path, tasks)
        assert load_tasks(path) == tasks
