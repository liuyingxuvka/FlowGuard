"""Site probes (design 3.1 and 3.6): what the decision sites of a home, and of the project functions
it calls, do while the rule's probe cells run.

The probe cells are lines through a few plain cells (the base cell and the rule's rows): along each
line one field takes every one of its points while the others stay fixed. Each function that the
home entered gets an instrumented copy (sites.probe_code, installed by swapping __code__ like a
mutant, restored in finally) that records, per cell, the outcome of every site and the values of a
comparison's two operands, but only while the home itself runs (the home's copy marks its own
calls), so the adapter's builders calling the same functions are not counted. From that the
engine reads:

- reached: the site ran on some cell;
- touched: its outcome differs between cells, so the rule's cells move it;
- tracked: one operand carries a rule field (the same value on every cell, or a fixed offset), so
  its constant bounds that field;
- boundary: it flips between two neighbouring cells of one line exactly where the decision flips,
  so it takes part in the rule's decision even when it lives in a callee.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

CASE = None          # the index of the cell being probed, or None outside a probe
DEPTH = 0            # how many calls of the home are running: sites count only inside the home
REC: dict = {}       # (function index, site index) -> {cell index: (outcomes, left values, right values)}


def enter():
    global DEPTH
    DEPTH += 1


def leave():
    global DEPTH
    DEPTH -= 1


def _slot(fi, si):
    per = REC.setdefault((fi, si), {})
    s = per.get(CASE)
    if s is None:
        s = per[CASE] = (set(), [], [])
    return s


def out(fi, si, v):
    if CASE is not None and DEPTH:
        try:
            _slot(fi, si)[0].add(bool(v))
        except Exception:   # an outcome without a truth value is not recorded  # flowguard: handler-listed
            pass
    return v


def lv(fi, si, v):
    if CASE is not None and DEPTH:
        vals = _slot(fi, si)[1]
        vals.append(v)
    return v


def rv(fi, si, v):
    if CASE is not None and DEPTH:
        vals = _slot(fi, si)[2]
        vals.append(v)
    return v


def start():
    global CASE, DEPTH
    REC.clear()
    CASE, DEPTH = None, 0


def take() -> dict:
    global CASE, DEPTH
    CASE, DEPTH = None, 0
    rec = {k: dict(v) for k, v in REC.items()}
    REC.clear()
    return rec


# ---------------------------------------------------------------- reading the records

def _num(v):
    return isinstance(v, (int, float, Decimal)) and not isinstance(v, bool)


def _as_field(v, kind):
    """A recorded value in the field's terms: a whole-day timedelta is a number of days for an int field."""
    if kind.name == "int" and isinstance(v, timedelta) and v.total_seconds() % 86400 == 0:
        return v.days
    return v


def _equal(a, b) -> bool:
    if _num(a) and _num(b):
        return Decimal(str(a)) == Decimal(str(b))
    if type(a) is not type(b) and not (isinstance(a, date) and isinstance(b, date)):
        return False
    return a == b


def tracks(per_case: dict, side: int, cells: list, kinds: dict):
    """(field, offset) when the operand on `side` (1 left, 2 right) carries one field's value on
    every cell it was recorded (offset 0), or that value plus a fixed number; else None."""
    for f, kind in kinds.items():
        if kind.name == "bool":
            continue
        pairs = [(cells[i][f], [_as_field(v, kind) for v in rec[side]]) for i, rec in per_case.items()
                 if rec[side] and cells[i].get(f) is not None]
        if len({repr(fv) for fv, _ in pairs}) < 2:
            continue
        if all(any(_equal(fv, v) for v in vs) for fv, vs in pairs):
            return f, 0
        if _num(pairs[0][0]) and all(len(vs) == 1 and _num(vs[0]) for _, vs in pairs):
            offs = {Decimal(str(vs[0])) - Decimal(str(fv)) for fv, vs in pairs}
            if len(offs) == 1:
                return f, offs.pop()
    return None


def boundary(per_case: dict, lines: list, answers: list, same) -> bool:
    """The site flips between two neighbouring cells of a line where the decision flips too. It
    must flip cleanly, one outcome on each cell: a shared helper that runs several times with
    mixed outcomes (a row lookup, a transaction depth) is not where the decision is made."""
    for line in lines:
        for i, j in zip(line, line[1:]):
            a, b = answers[i], answers[j]
            if a is None or b is None or same(a, b):
                continue
            oi, oj = per_case.get(i), per_case.get(j)
            if oi and oj and len(oi[0]) == 1 and len(oj[0]) == 1 and oi[0] != oj[0]:
                return True
    return False


def touched(per_case: dict) -> bool:
    return len({frozenset(rec[0]) for rec in per_case.values() if rec[0]}) > 1
