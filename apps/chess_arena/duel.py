"""Engine-vs-engine chess duels for Chess Duel Arena.

Deterministic: the same engine configs always produce the same game,
because the vendored engine resets all of its search state on every
``best_move`` call.
"""

from __future__ import annotations

from .engine import ChessEngine

STARTPOS = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def play_duel(white: ChessEngine, black: ChessEngine, max_ply: int = 200) -> dict:
    """Play one duel from the start position.

    Returns ``{"winner", "reason", "moves", "plies", "final_fen"}`` where
    ``winner`` is ``"white"`` / ``"black"`` / ``"draw"`` and ``reason`` is
    ``"checkmate"`` / ``"stalemate"`` / ``"draw-ply-limit"`` /
    ``"insufficient-material"``.
    """
    fen = STARTPOS
    moves: list[str] = []
    engines = (white, black)
    for ply in range(max_ply):
        engine = engines[ply % 2]
        if engine.insufficient_material(fen):
            return {
                "winner": "draw",
                "reason": "insufficient-material",
                "moves": moves,
                "plies": ply,
                "final_fen": fen,
            }
        if not engine.legal_moves(fen):
            if engine.is_checkmate(fen):
                winner = "black" if ply % 2 == 0 else "white"
                reason = "checkmate"
            else:
                winner = "draw"
                reason = "stalemate"
            return {
                "winner": winner,
                "reason": reason,
                "moves": moves,
                "plies": ply,
                "final_fen": fen,
            }
        move = engine.best_move(fen)
        if move is None:  # pragma: no cover - guarded by the check above
            return {
                "winner": "draw",
                "reason": "stalemate",
                "moves": moves,
                "plies": ply,
                "final_fen": fen,
            }
        fen = engine.apply(fen, move)
        moves.append(move)
    return {
        "winner": "draw",
        "reason": "draw-ply-limit",
        "moves": moves,
        "plies": max_ply,
        "final_fen": fen,
    }


def play_duel_from_params(params: dict) -> dict:
    """Play a duel from a harness-style params dict.

    ``params``: ``{"white": {"name", "depth"}, "black": {"name", "depth"},
    "max_ply": int}``. The result is the ``play_duel`` dict plus the
    ``"white"`` / ``"black"`` engine names.
    """
    white_cfg = params.get("white") or {}
    black_cfg = params.get("black") or {}
    white = ChessEngine(
        str(white_cfg.get("name", "Forge-White")),
        int(white_cfg.get("depth", 5)),
    )
    black = ChessEngine(
        str(black_cfg.get("name", "Forge-Black")),
        int(black_cfg.get("depth", 5)),
    )
    result = play_duel(white, black, int(params.get("max_ply", 200)))
    result["white"] = white.name
    result["black"] = black.name
    return result
