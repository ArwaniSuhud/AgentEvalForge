"""Tests for Chess Duel Arena (apps/chess_arena/).

Engine/duel tests run against small depths so the suite stays fast;
the API test uses a short duel (max_ply=8) for the same reason.
"""

import importlib
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from apps.chess_arena.duel import (  # noqa: E402
    STARTPOS,
    play_duel,
    play_duel_from_params,
)
from apps.chess_arena.engine import ChessEngine  # noqa: E402

MIDGAME = "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3"


def test_startpos_has_20_legal_moves():
    engine = ChessEngine("test", depth=1)
    moves = engine.legal_moves(STARTPOS)
    assert len(moves) == 20
    assert len(set(moves)) == 20
    for expected in ("e2e4", "d2d4", "g1f3", "b1c3", "e2e3"):
        assert expected in moves


def test_apply_round_trips_fen():
    engine = ChessEngine("test", depth=1)
    assert (
        engine.apply(STARTPOS, "e2e4")
        == "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
    )
    assert (
        engine.apply(STARTPOS, "g1f3")
        == "rnbqkbnr/pppppppp/8/8/8/5N2/PPPPPPPP/RNBQKB1R b KQkq - 1 1"
    )


def test_apply_rejects_illegal_move():
    engine = ChessEngine("test", depth=1)
    with pytest.raises(ValueError):
        engine.apply(STARTPOS, "e2e5")  # pawn cannot jump three squares
    with pytest.raises(ValueError):
        engine.apply(STARTPOS, "a2a1")  # backwards pawn move


def test_fools_mate_is_checkmate():
    engine = ChessEngine("test", depth=1)
    fen = STARTPOS
    for move in ("f2f3", "e7e5", "g2g4", "d8h4"):
        fen = engine.apply(fen, move)
    assert engine.is_checkmate(fen)
    assert not engine.is_stalemate(fen)
    assert engine.legal_moves(fen) == []
    assert engine.best_move(fen) is None


def test_stalemate_position():
    engine = ChessEngine("test", depth=1)
    fen = "7k/5Q2/6K1/8/8/8/8/8 b - - 0 1"
    assert engine.is_stalemate(fen)
    assert not engine.is_checkmate(fen)


def test_insufficient_material():
    engine = ChessEngine("test", depth=1)
    assert engine.insufficient_material("8/8/4k3/8/8/3NK3/8/8 w - - 0 1")  # K+N vs K
    assert engine.insufficient_material("8/8/4k3/8/8/3BK3/8/8 w - - 0 1")  # K+B vs K
    assert engine.insufficient_material("8/8/4k3/8/8/4K3/8/8 w - - 0 1")  # K vs K
    assert not engine.insufficient_material(STARTPOS)
    assert not engine.insufficient_material(MIDGAME)


def test_best_move_is_always_legal():
    engine = ChessEngine("test", depth=2)
    for fen in (STARTPOS, MIDGAME):
        move = engine.best_move(fen)
        assert move is not None
        assert move in engine.legal_moves(fen)


def test_best_move_is_deterministic():
    engine = ChessEngine("test", depth=3)
    first = engine.best_move(MIDGAME)
    second = engine.best_move(MIDGAME)
    assert first == second


def test_duel_is_deterministic():
    params = {
        "white": {"name": "Forge-Deep", "depth": 1},
        "black": {"name": "Forge-Quick", "depth": 1},
        "max_ply": 20,
    }
    first = play_duel_from_params(params)
    second = play_duel_from_params(params)
    assert first == second


def test_duel_terminates_with_valid_outcome():
    result = play_duel(
        ChessEngine("Forge-Deep", 2), ChessEngine("Forge-Quick", 1), max_ply=10
    )
    assert result["plies"] <= 10
    assert result["plies"] == len(result["moves"])
    assert result["winner"] in ("white", "black", "draw")
    assert result["reason"] in (
        "checkmate",
        "stalemate",
        "draw-ply-limit",
        "insufficient-material",
    )
    assert isinstance(result["final_fen"], str) and len(result["final_fen"].split()) == 6


def test_duel_from_params_adds_engine_names():
    result = play_duel_from_params(
        {
            "white": {"name": "Forge-Deep", "depth": 1},
            "black": {"name": "Forge-Quick", "depth": 1},
            "max_ply": 4,
        }
    )
    assert result["white"] == "Forge-Deep"
    assert result["black"] == "Forge-Quick"
    assert result["plies"] == 4


# ---------------------------------------------------------------------------
# API tests (TestClient, in-process; isolated temp DB via FORGE_DB + reload)
# ---------------------------------------------------------------------------


@pytest.fixture()
def api_client(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_DB", str(tmp_path / "results.db"))
    import apps.chess_arena.server as server

    importlib.reload(server)
    with TestClient(server.app) as client:
        yield client


def test_api_index_returns_html(api_client):
    res = api_client.get("/")
    assert res.status_code == 200
    assert "Chess Duel Arena" in res.text


def test_api_leaderboard_and_games_empty(api_client):
    for path in ("/api/leaderboard", "/api/games"):
        res = api_client.get(path)
        assert res.status_code == 200
        assert res.json() == []


def test_api_duel_records_result(api_client):
    res = api_client.post(
        "/api/duel",
        json={"white_depth": 2, "black_depth": 1, "max_ply": 8},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["winner"] in ("white", "black", "draw")
    assert body["reason"] in (
        "checkmate",
        "stalemate",
        "draw-ply-limit",
        "insufficient-material",
    )
    assert body["plies"] == 8
    assert len(body["moves"]) == 8
    assert body["white"] == "Forge-Quick"
    assert body["black"] == "Forge-Quick"

    # The duel is persisted: visible through the store's leaderboard.
    from forge.store import leaderboard, recent_games

    import apps.chess_arena.server as server

    rows = leaderboard(server.DB_PATH)
    assert len(rows) == 1
    assert rows[0]["agent"] == "chess-arena"
    assert rows[0]["games"] == 1
    assert rows[0]["wins"] + rows[0]["draws"] + rows[0]["losses"] == 1

    games = recent_games(server.DB_PATH)
    assert len(games) == 1
    assert games[0]["kind"] == "chess-duel"
    assert games[0]["winner"] == body["winner"]

    # ...and through the API itself.
    assert api_client.get("/api/leaderboard").json()[0]["agent"] == "chess-arena"
    assert len(api_client.get("/api/games").json()) == 1
