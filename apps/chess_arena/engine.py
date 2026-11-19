"""Vendored standalone chess engine for Chess Duel Arena.

Origin: the author's tiny-chess engine (``~/workspace/make-fun/tiny-chess-01/engine.py``,
7,918 bytes), a 0x88 board, sunfish-style alpha-beta + quiescence search
engine written for the make.fun tiny-chess bounty. Only the search core
is reused here (``F``, ``A``, ``G``, ``M``, ``U``, ``E``, ``K``, ``W``,
``R``, ``O``, ``C`` plus the piece-square tables and constants); the
make.fun network protocol (``P()`` and the ``while True`` game loop that
talks to ``MAKEFUN_ENV_URL``) was removed, so this module has no network
dependency and no I/O at import time.

Changes vs. the original:
- ``C(fen, legal_moves, depth=9)``: iterative deepening now runs
  ``1..depth`` instead of the hardcoded ``1..9``.
- Determinism: at the start of every search ``C`` clears the
  transposition table ``t``, the killer/history tables ``k``/``h`` and
  the repetition set ``p``, so a result never depends on earlier calls.
- A ``ChessEngine`` wrapper class exposes a clean API (UCI legal moves,
  best move, apply, mate/stalemate/insufficient-material detection) and
  FEN round-tripping with halfmove/fullmove clocks.
"""

from __future__ import annotations

V = (0, 100, 320, 330, 500, 900, 20000)
J = (31, 33, 14, 18, -31, -33, -14, -18)
Z = (1, -1, 16, -16, 15, 17, -15, -17)
X = (15, 17, -15, -17)
Y = (1, -1, 16, -16)
Q = [s for s in range(128) if not s & 136]
B = bytearray(128)
g = [4, 116]
S = 1
c = 0
e = -1
N = 0
L = 150000
n = [0, 0]
v = 0
t = {}
k = [[0, 0] for _ in range(128)]
h = [[0] * 128 for _ in range(13)]
u = []
p = set()


class D(Exception):
    pass


y = [[0] * 128 for _ in range(7)]
for s in Q:
    f = s & 7
    d = s >> 4
    m = min(f, 7 - f) + min(d, 7 - d)
    y[0][s] = [0, 0, 4, 8, 14, 24, 40, 0][d] + ([0, 0, 0, 10, 15, 10, 5, 0][d] if f in (3, 4) else 0)
    y[1][s] = 6 * m - 20
    y[2][s] = 4 * m - 8
    y[3][s] = 15 if d == 6 else (5 if d == 0 and f in (3, 4) else 0)
    y[4][s] = 2 * m - 6
    y[5][s] = [20, 25, 10, 0, 0, 10, 25, 20][f] if d == 0 else max(-50, -15 * d)
    y[6][s] = 8 * m - 24
w = [[0] * 128 for _ in range(13)]
for o in range(1, 13):
    z = o if o < 7 else o - 6
    if z < 6:
        for s in Q:
            w[o][s] = (V[z] + y[z - 1][s]) if o < 7 else -(V[z] + y[z - 1][s ^ 112])


def F(f):
    global S, c, e, v
    a = f.split()
    d = a[0].split("/")
    B[:] = b"\0" * 128
    for i, o in enumerate(d):
        z = 0
        for ch in o:
            if ch.isdigit():
                z += int(ch)
            else:
                B[(7 - i) * 16 + z] = "PNBRQKpnbrqk".index(ch) + 1
                z += 1
    S = 1 if a[1] == "w" else -1
    c = 0
    for ch in a[2]:
        if ch in "KQkq":
            c |= 1 << "KQkq".index(ch)
    e = -1 if a[3] == "-" else (ord(a[3][0]) - 97) + (int(a[3][1]) - 1) * 16
    g[0] = next(s for s in Q if B[s] == 6)
    g[1] = next(s for s in Q if B[s] == 12)
    n[0] = sum(1 for s in Q if 1 < B[s] < 6)
    n[1] = sum(1 for s in Q if 7 < B[s] < 12)
    v = sum(V[B[s] if B[s] < 7 else B[s] - 6] for s in Q if B[s] and 1 < (B[s] if B[s] < 7 else B[s] - 6) < 6)


def A(s, b):
    if b > 0:
        if not (s - 15) & 136 and B[s - 15] == 1:
            return 1
        if not (s - 17) & 136 and B[s - 17] == 1:
            return 1
    else:
        if not (s + 15) & 136 and B[s + 15] == 7:
            return 1
        if not (s + 17) & 136 and B[s + 17] == 7:
            return 1
    for o in J:
        z = s + o
        if not z & 136 and B[z] == (2 if b > 0 else 8):
            return 1
    for o in Z:
        z = s + o
        if not z & 136 and B[z] == (6 if b > 0 else 12):
            return 1
    for o in X:
        z = s + o
        while not z & 136:
            q = B[z]
            if q:
                if q == (3 if b > 0 else 9) or q == (5 if b > 0 else 11):
                    return 1
                break
            z += o
    for o in Y:
        z = s + o
        while not z & 136:
            q = B[z]
            if q:
                if q == (4 if b > 0 else 10) or q == (5 if b > 0 else 11):
                    return 1
                break
            z += o
    return 0


def G(C):
    m = []
    for s in Q:
        o = B[s]
        if not o or (o < 7) != (S > 0):
            continue
        z = o if o < 7 else o - 6
        if z == 1:
            d = 16 if S > 0 else -16
            l = 7 if S > 0 else 0
            f = 1 if S > 0 else 6
            t = s + d
            if not C and not t & 136 and not B[t]:
                if (t >> 4) == l:
                    m.append(s | t << 7 | 5 << 14)
                    m.append(s | t << 7 | 2 << 14)
                else:
                    m.append(s | t << 7)
                    if (s >> 4) == f and not B[s + 2 * d]:
                        m.append(s | (s + 2 * d) << 7)
            for a in (d - 1, d + 1):
                t = s + a
                if t & 136:
                    continue
                q = B[t]
                if q and (q < 7) != (S > 0):
                    if (t >> 4) == l:
                        m.append(s | t << 7 | 5 << 14)
                        m.append(s | t << 7 | 2 << 14)
                    else:
                        m.append(s | t << 7)
                elif t == e:
                    m.append(s | t << 7)
        elif z == 2 or z == 6:
            for o in J if z == 2 else Z:
                t = s + o
                if t & 136:
                    continue
                q = B[t]
                if not q:
                    if not C:
                        m.append(s | t << 7)
                elif (q < 7) != (S > 0):
                    m.append(s | t << 7)
            if z == 6:
                if S > 0 and s == 4:
                    if c & 1 and not B[5] and not B[6] and not A(4, -1) and not A(5, -1) and not A(6, -1):
                        m.append(4 | 6 << 7)
                    if c & 2 and not B[3] and not B[2] and not B[1] and not A(4, -1) and not A(3, -1) and not A(2, -1):
                        m.append(4 | 2 << 7)
                elif S < 0 and s == 116:
                    if c & 4 and not B[117] and not B[118] and not A(116, 1) and not A(117, 1) and not A(118, 1):
                        m.append(116 | 118 << 7)
                    if c & 8 and not B[115] and not B[114] and not B[113] and not A(116, 1) and not A(115, 1) and not A(114, 1):
                        m.append(116 | 114 << 7)
        else:
            for o in X if z == 3 else Y if z == 4 else X + Y:
                t = s + o
                while not t & 136:
                    q = B[t]
                    if not q:
                        if not C:
                            m.append(s | t << 7)
                    else:
                        if (q < 7) != (S > 0):
                            m.append(s | t << 7)
                        break
                    t += o
    return m


def M(o):
    global S, c, e, v
    f = o & 127
    t = (o >> 7) & 127
    q = (o >> 14) & 7
    a = B[f]
    z = B[t]
    d = t
    if (a == 1 or a == 7) and t == e and not z:
        d = t - 16 if S > 0 else t + 16
        z = B[d]
        B[d] = 0
    i = 0 if S > 0 else 1
    if q:
        n[i] += 1
        v += V[q]
    if z:
        x = z if z < 7 else z - 6
        if 1 < x < 6:
            n[1 - i] -= 1
            v -= V[x]
    u.append((f, t, q, z, d, c, e, g[0], g[1]))
    B[t] = q + (6 if a == 7 else 0) if q else a
    B[f] = 0
    if a == 6 or a == 12:
        g[0 if S > 0 else 1] = t
        if abs(t - f) == 2:
            if t > f:
                B[t - 1] = B[t + 1]
                B[t + 1] = 0
            else:
                B[t + 1] = B[t - 2]
                B[t - 2] = 0
    if f == 4:
        c &= ~3
    elif f == 116:
        c &= ~12
    elif f == 7:
        c &= ~1
    elif f == 0:
        c &= ~2
    elif f == 119:
        c &= ~4
    elif f == 112:
        c &= ~8
    if t == 7:
        c &= ~1
    elif t == 0:
        c &= ~2
    elif t == 119:
        c &= ~4
    elif t == 112:
        c &= ~8
    e = f + 16 if (a == 1 and t - f == 32) else f - 16 if (a == 7 and f - t == 32) else -1
    S = -S


def U():
    global S, c, e, v
    f, t, q, z, d, c, e, g[0], g[1] = u.pop()
    o = B[t]
    B[f] = o if not q else (1 if S < 0 else 7)
    B[t] = 0
    B[d] = z
    if o in (6, 12) and abs(t - f) == 2:
        if t > f:
            B[t + 1] = B[t - 1]
            B[t - 1] = 0
        else:
            B[t - 2] = B[t + 1]
            B[t + 1] = 0
    S = -S
    i = 0 if S > 0 else 1
    if q:
        n[i] -= 1
        v -= V[q]
    if z:
        x = z if z < 7 else z - 6
        if 1 < x < 6:
            n[1 - i] += 1
            v += V[x]


def E():
    s = 0
    a = 0
    b = 0
    z = 0
    I = 0
    for q in Q:
        o = B[q]
        if not o:
            continue
        s += w[o][q]
        if o == 3:
            a += 1
        elif o == 9:
            b += 1
        elif o == 6:
            z = q
        elif o == 12:
            I = q
    if a > 1:
        s += 30
    if b > 1:
        s -= 30
    h = v if v < 6400 else 6400
    s += (y[5][z] * h + y[6][z] * (6400 - h)) // 6400 - (y[5][I ^ 112] * h + y[6][I ^ 112] * (6400 - h)) // 6400
    return s


def K():
    return (bytes(B), S, c, e)


def W(a, b, l):
    global N
    N += 1
    if N > L:
        raise D
    if A(g[0 if S > 0 else 1], -S):
        x = -100000
        for o in O(G(0), 0, l):
            M(o)
            if A(g[0 if S < 0 else 1], S):
                U()
                continue
            s = -W(-b, -a, l + 1)
            U()
            if s > x:
                x = s
            if s > a:
                a = s
            if a >= b:
                break
        return x if x > -100000 else -100000 + l
    s = S * E()
    if s >= b:
        return b
    if s > a:
        a = s
    if l > 32:
        return a
    for o in O(G(1), 0, l):
        M(o)
        if A(g[0 if S < 0 else 1], S):
            U()
            continue
        s = -W(-b, -a, l + 1)
        U()
        if s > a:
            a = s
        if a >= b:
            break
    return a


def R(d, a, b, l):
    global N, S, e
    N += 1
    if N > L:
        raise D
    if d <= 0:
        return W(a, b, l)
    j = K()
    if j in p:
        return 0
    p.add(j)
    o = t.get(j)
    m = 0
    if o and o[0] >= d:
        if o[1] == 0:
            p.discard(j)
            return o[2]
        if o[1] == 1 and o[2] >= b:
            p.discard(j)
            return o[2]
        if o[1] == 2 and o[2] <= a:
            p.discard(j)
            return o[2]
        m = o[3]
    if d >= 3 and n[0 if S > 0 else 1] and not A(g[0 if S > 0 else 1], -S):
        s0 = S
        e0 = e
        S = -S
        e = -1
        try:
            s = -R(d - 3 - (d > 6), -b, -b + 1, l + 1)
        finally:
            S = s0
            e = e0
        if s >= b:
            p.discard(j)
            return b
    x = -100000
    f = 2
    F = 0
    T = 0
    if d <= 2 and not A(g[0 if S > 0 else 1], -S):
        F = S * E() + 150 * d
    for o in O(G(0), m, l):
        if F and x > -100000 and not B[(o >> 7) & 127] and (o >> 7) & 127 != e and (o >> 14) == 0 and F < a:
            continue
        q = B[(o >> 7) & 127] or (o >> 14)
        M(o)
        if A(g[0 if S < 0 else 1], S):
            U()
            continue
        T += 1
        if T == 1:
            s = -R(d - 1, -b, -a, l + 1)
        else:
            d2 = d - 2 if T > 3 and d >= 3 and not q else d - 1
            s = -R(d2, -a - 1, -a, l + 1)
            if s > a and (d2 < d - 1 or s < b):
                s = -R(d - 1, -b, -a, l + 1)
        U()
        if s > x:
            x = s
            m = o
        if s > a:
            a = s
            f = 0
        if a >= b:
            f = 1
            if not B[(o >> 7) & 127] and (o >> 14) == 0:
                k[l][1] = k[l][0]
                k[l][0] = o
                h[B[o & 127]][(o >> 7) & 127] += d * d
            break
    if x == -100000:
        x = -100000 + l if A(g[0 if S > 0 else 1], -S) else 0
    if len(t) > 300000:
        t.clear()
    t[j] = (d, f, x, m)
    p.discard(j)
    return x


def O(m, b, l):
    def s(o):
        if o == b:
            return 999999
        f = o & 127
        z = (o >> 7) & 127
        q = B[z]
        if q:
            return 10000 + 10 * V[q if q < 7 else q - 6] - V[B[f] if B[f] < 7 else B[f] - 6]
        if o == k[l][0]:
            return 9000
        if o == k[l][1]:
            return 8000
        return h[B[f]][z]

    return sorted(m, key=s, reverse=True)


def C(f, l, depth=9):
    """Pick the best move (UCI) from ``l`` for position ``f``.

    Iterative deepening, depths 1..``depth``. Every search starts from
    a clean slate (transposition table, killer/history tables and the
    repetition set are all reset) so the result is deterministic and
    independent of any earlier search.
    """
    global N, p, L, t, k, h
    if not l:
        return None
    F(f)
    # Determinism: never let state from a previous search leak in.
    t.clear()
    k = [[0, 0] for _ in range(128)]
    h = [[0] * 128 for _ in range(13)]
    p = set()
    if len(l) == 1:
        return l[0]
    m = int(f.split()[5])
    L = 250000 if m < 20 else 200000 if m < 40 else 120000
    w = l[0]
    s = {}
    N = 0
    for d in range(1, depth + 1):
        p = {K()}
        try:
            r = []
            a = -100000
            for o in sorted(l, key=lambda x: -s.get(x, 0)):
                z = (ord(o[0]) - 97) + (int(o[1]) - 1) * 16
                I = (ord(o[2]) - 97) + (int(o[3]) - 1) * 16
                q = "nbrq".index(o[4]) + 2 if len(o) == 5 else 0
                M(z | I << 7 | q << 14)
                v = -R(d - 1, -100000, -a, 1)
                if v > a:
                    v = -R(d - 1, -100000, 100000, 1)
                F(f)
                r.append((v, o))
                if v > a:
                    a = v
            r.sort(key=lambda x: -x[0])
            w = r[0][1]
            s = dict(r)
        except D:
            F(f)
            break
    return w


# ---------------------------------------------------------------------------
# UCI helpers + wrapper class
# ---------------------------------------------------------------------------

_PROMO_INT_TO_UCI = {2: "n", 3: "b", 4: "r", 5: "q"}


def _square_to_uci(s: int) -> str:
    return chr(97 + (s & 7)) + str((s >> 4) + 1)


def _move_to_uci(o: int) -> str:
    uci = _square_to_uci(o & 127) + _square_to_uci((o >> 7) & 127)
    promo = (o >> 14) & 7
    if promo:
        uci += _PROMO_INT_TO_UCI[promo]
    return uci


def _board_to_fen(halfmove: int = 0, fullmove: int = 1) -> str:
    """Build the 6-field FEN of the current internal board state."""
    rows = []
    for rank in range(7, -1, -1):
        empty = 0
        row = ""
        for f in range(8):
            piece = B[rank * 16 + f]
            if piece == 0:
                empty += 1
            else:
                if empty:
                    row += str(empty)
                    empty = 0
                row += "PNBRQKpnbrqk"[piece - 1]
        if empty:
            row += str(empty)
        rows.append(row)
    side = "w" if S > 0 else "b"
    castling = "".join(
        ch for bit, ch in ((1, "K"), (2, "Q"), (4, "k"), (8, "q")) if c & bit
    ) or "-"
    ep = "-" if e == -1 else _square_to_uci(e)
    return f"{'/'.join(rows)} {side} {castling} {ep} {halfmove} {fullmove}"


class ChessEngine:
    """A named chess engine instance (search depth = strength)."""

    def __init__(self, name: str, depth: int = 5):
        self.name = name
        self.depth = depth

    @staticmethod
    def _parse_clocks(fen: str) -> tuple[int, int]:
        parts = fen.split()
        try:
            halfmove = int(parts[4])
        except (IndexError, ValueError):
            halfmove = 0
        try:
            fullmove = int(parts[5])
        except (IndexError, ValueError):
            fullmove = 1
        return halfmove, fullmove

    def _side_to_move_in_check(self) -> bool:
        """True if the side to move's king is attacked (board already loaded)."""
        return bool(A(g[0 if S > 0 else 1], -S))

    def legal_moves(self, fen: str) -> list[str]:
        """All king-safe legal moves in UCI notation."""
        F(fen)
        moves = []
        for o in G(0):
            M(o)
            if A(g[0 if S < 0 else 1], S):
                U()
                continue
            U()
            moves.append(_move_to_uci(o))
        return moves

    def best_move(self, fen: str) -> str | None:
        """Best legal move in UCI, or None if the side to move has none."""
        moves = self.legal_moves(fen)
        if not moves:
            return None
        return C(fen, moves, self.depth)

    def apply(self, fen: str, uci: str) -> str:
        """Return the FEN after playing ``uci`` from ``fen``.

        Raises ValueError for an illegal move.
        """
        halfmove, fullmove = self._parse_clocks(fen)
        F(fen)
        target = None
        for o in G(0):
            if _move_to_uci(o) != uci:
                continue
            M(o)
            if A(g[0 if S < 0 else 1], S):
                U()
                continue
            U()
            target = o
            break
        if target is None:
            raise ValueError(f"illegal move {uci} in {fen}")
        frm = target & 127
        to = (target >> 7) & 127
        piece = B[frm]
        captured = B[to]
        ep_capture = piece in (1, 7) and to == e and captured == 0
        was_black = S < 0
        M(target)
        new_halfmove = (
            0 if (piece in (1, 7) or captured or ep_capture) else halfmove + 1
        )
        new_fullmove = fullmove + 1 if was_black else fullmove
        return _board_to_fen(new_halfmove, new_fullmove)

    def is_checkmate(self, fen: str) -> bool:
        return not self.legal_moves(fen) and self._in_check(fen)

    def is_stalemate(self, fen: str) -> bool:
        return not self.legal_moves(fen) and not self._in_check(fen)

    def _in_check(self, fen: str) -> bool:
        F(fen)
        return self._side_to_move_in_check()

    def insufficient_material(self, fen: str) -> bool:
        """K vs K, K+B vs K, or K+N vs K (either colour)."""
        F(fen)
        rest = [B[s] for s in Q if B[s] not in (0, 6, 12)]
        if not rest:
            return True
        return len(rest) == 1 and rest[0] in (2, 3, 8, 9)
