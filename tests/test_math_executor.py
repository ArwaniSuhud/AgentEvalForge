"""Tests for the math-word executor + judge (forge polish, option A).

The executor is a tiny deterministic arithmetic solver: no LLM, no
network, no randomness. The judge passes iff the numeric answer
matches ``expected["answer"]`` within 1e-9.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from forge import judge, load_tasks, recent_games, run_tasks
from forge.runner import EXECUTORS, _math_word_executor

ROOT = Path(__file__).resolve().parents[1]


def test_math_word_executor_registered():
    assert EXECUTORS.get("math-word") is _math_word_executor


def test_math_word_solver_steps():
    result = _math_word_executor({"problem": "x", "expression": "(3 + 4) * 2"})
    assert result["answer"] == 14.0
    assert result["steps"] == ["3 + 4 = 7", "7 * 2 = 14"]
    assert result["problem"] == "x"


def test_math_word_solver_decimal_and_problem_fallback():
    result = _math_word_executor({"expression": "15 / 4"})
    assert result["answer"] == 3.75
    assert result["steps"] == ["15 / 4 = 3.75"]
    assert result["problem"] == "15 / 4"  # falls back to the expression


@pytest.mark.parametrize(
    "bad",
    [
        {},
        {"expression": ""},
        {"expression": "   "},
        {"expression": 42},
        {"expression": "3 +"},
        {"expression": "3 + foo"},
        {"expression": "2 ** 3"},
        {"expression": "1 / 0"},
        {"expression": "__import__('os')"},
    ],
)
def test_math_word_malformed_params_raise(bad):
    with pytest.raises(ValueError):
        _math_word_executor(bad)


def test_bundled_math_word_tasks_all_pass():
    tasks = load_tasks(ROOT / "tasks" / "math-word.jsonl")
    assert [t["id"] for t in tasks] == [f"mw-00{i}" for i in range(1, 9)]
    assert all(t["kind"] == "math-word" for t in tasks)
    for task in tasks:
        result = _math_word_executor(task["params"])
        verdict = judge(task, result)
        assert verdict["passed"] is True, task["id"]
        assert verdict["score"] == 1.0
        assert verdict["details"]["kind"] == "math-word"


def test_judge_math_wrong_answer_fails():
    task = {"id": "t", "kind": "math-word", "params": {}, "expected": {"answer": 7}}
    verdict = judge(task, {"answer": 8.0})
    assert verdict["passed"] is False
    assert verdict["score"] == 0.0
    assert "expected" in verdict["details"]["reason"]


def test_judge_math_tolerance():
    task = {"id": "t", "kind": "math-word", "params": {}, "expected": {"answer": 7}}
    assert judge(task, {"answer": 7.0000000001})["passed"] is True  # 1e-10 < 1e-9
    assert judge(task, {"answer": 7.000000002})["passed"] is False  # 2e-9 > 1e-9


def test_judge_math_missing_answer_raises():
    with pytest.raises(ValueError):
        judge(
            {"id": "t", "kind": "math-word", "params": {}, "expected": {"answer": 7}},
            {},
        )
    with pytest.raises(ValueError):
        judge(
            {"id": "t", "kind": "math-word", "params": {}, "expected": {}},
            {"answer": 7},
        )


def test_runner_math_word_end_to_end(tmp_path):
    db = tmp_path / "r.db"
    tasks = load_tasks(ROOT / "tasks" / "math-word.jsonl")
    results = run_tasks(tasks, agent="forge-math", db_path=db, run_id="run-test")
    assert len(results) == 8
    assert all(r["passed"] for r in results)
    assert all(r["score"] == 1.0 for r in results)
    assert all(r["kind"] == "math-word" for r in results)
    rows = recent_games(db)
    assert len(rows) == 8
    assert rows[0]["task_id"] == "mw-008"


def test_cli_run_math_word(tmp_path):
    db = tmp_path / "r.db"
    proc = subprocess.run(
        [sys.executable, "-m", "forge", "run", "--tasks",
         str(ROOT / "tasks" / "math-word.jsonl"), "--db", str(db),
         "--agent", "forge-math"],
        cwd=str(ROOT), capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.count("PASS") == 8
    assert "PASS mw-001 math-word score=1.00" in proc.stdout
    assert "PASS mw-008 math-word score=1.00" in proc.stdout
