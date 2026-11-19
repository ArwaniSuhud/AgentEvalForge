"""Deterministic eval harness for AgentEval Forge.

No LLM, no network, no randomness in the scoring path.
"""

from .judge import judge
from .runner import EXECUTORS, register, run_tasks
from .store import init_db, leaderboard, recent_games, record_result
from .tasks import TaskValidationError, load_tasks, write_tasks

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "TaskValidationError",
    "load_tasks",
    "write_tasks",
    "judge",
    "init_db",
    "record_result",
    "leaderboard",
    "recent_games",
    "EXECUTORS",
    "register",
    "run_tasks",
]
