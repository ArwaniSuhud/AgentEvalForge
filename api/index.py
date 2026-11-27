"""Vercel serverless entrypoint for AgentEval Forge.

Vercel's Python runtime serves ``api/index.py`` as a serverless function.
The app's SQLite database is bundled read-only in the deployment, so on
cold start we copy it to /tmp (the only writable directory) and point the
app at the copy via FORGE_DB. Reads (leaderboard, games) and web writes
(duel/backtest) then work against the /tmp copy; the seeded results are
preserved because the copy starts from the bundled file.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_BUNDLED_DB = _ROOT / "data" / "results.db"
_TMP_DB = Path("/tmp") / "forge-results.db"

if _BUNDLED_DB.exists() and not _TMP_DB.exists():
    shutil.copyfile(_BUNDLED_DB, _TMP_DB)

if _TMP_DB.exists():
    os.environ["FORGE_DB"] = str(_TMP_DB)

from apps.chess_arena.server import app  # noqa: E402

__all__ = ["app"]
