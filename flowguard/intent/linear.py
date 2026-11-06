"""Arithmetic across fields (R46): linear atoms, their planes, and cells that hit every region.

A comparison whose two sides are linear in the fields (sums, differences, constant multiples,
`due + timedelta(days=2)`, `(returned - due).days`, `timedelta(days=n)`, single-assigned locals)
is read exactly, in Fractions: dates as day numbers, datetimes and timedeltas in days. An atom over
one field is a bound on that field. An atom over two or more fields is a plane.

Fields joined by planes form a group whose cells are enumerated cylindrically: the last field is
solved at every plane (expr = c, with its neighbours c - e and c + e) for each combination of the
earlier fields' values, and each earlier field takes the values where two planes cross (the planes
projected one field down, `project`). This is exhaustive over the partition the atoms induce:
- for decimal, float, datetime and timedelta fields always (real elimination is exact);
- for integer and date fields when every field solved away has coefficient 1 in every plane it is
  in (the integer shadow then equals the real one, up to the offsets -2..2 added to each crossing).
Otherwise the group is labelled with the reason, and its cells are a sample.
"""
from __future__ import annotations

import ast
import itertools
import math
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal, localcontext
from fractions import Fraction

NUMERIC = ("int", "float", "dec", "date", "datetime", "td")
INTEGRAL = ("int", "date")              # a lattice of step 1 (dates as day numbers)
F0, F1 = Fraction(0), Fraction(1)
DAY_US = 86_400_000_000
TD_DAYS = {"days": F1, "seconds": Fraction(1, 86_400), "microseconds": Fraction(1, DAY_US),
           "milliseconds": Fraction(1, 86_400_000), "minutes": Fraction(1, 1_440), "hours": Fraction(1, 24),
           "weeks": Fraction(7)}
TD_ORDER = ("days", "seconds", "microseconds", "milliseconds", "minutes", "hours", "weeks")
OFFSETS = (-2, -1, 0, 1, 2)            # integer crossings: strict bounds on both sides move a crossing by up to 2


# ---------------------------------------------------------------- numbers

def to_num(v):
    """A value as a Fraction in its field's unit (dates and times in days), or None."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, int):
        return Fraction(v)
    if isinstance(v, Decimal):
        return Fraction(v) if v.is_finite() else None
    if isinstance(v, float):
        return Fraction(repr(v)) if math.isfinite(v) else None
    if isinstance(v, datetime):
        midnight = datetime.combine(v.date(), time(), tzinfo=v.tzinfo)
        return Fraction(v.toordinal()) + Fraction((v - midnight) // timedelta(microseconds=1), DAY_US)
    if isinstance(v, date):
        return Fraction(v.toordinal())
    if isinstance(v, timedelta):
        return Fraction(v // timedelta(microseconds=1), DAY_US)
    return None


def from_num(x: Fraction, kind, step: Fraction | None = None):
    """The field value of a number (None when it is outside the type's range)."""
    name = kind.name
    try:
        if name == "int":
            return int(x)
        if name == "date":
            return date.fromordinal(int(x))
        if name == "float":
            return float(x)
        if name == "dec":
            return _decimal(x, step)
        if name == "datetime":
            day = math.floor(x)
            return datetime.fromordinal(day) + timedelta(microseconds=round((x - day) * DAY_US))
        if name == "td":
            return timedelta(microseconds=round(x * DAY_US))
    except (ValueError, OverflowError):
        return None
    return None


def _decimal(x: Fraction, step) -> Decimal:
    with localcontext() as ctx:
        ctx.prec = 40
        d = Decimal(x.numerator) / Decimal(x.denominator)
        if step:
            exp = Decimal(step.numerator) / Decimal(step.denominator)
            q = d.quantize(exp.normalize() if exp.normalize().as_tuple().exponent < 0 else Decimal(1))
            if Fraction(q) == x:
                return q
        return d.normalize() if d == d.to_integral_value() else d


def step_of(kind, consts) -> Fraction:
    """The step between neighbouring points of a field: 1 for integers and dates, else the finest step
    of its constants (0.01 for D("50.00")), at most 1."""
    if kind.name in INTEGRAL:
        return F1
    if kind.name == "datetime":
        return Fraction(1, 86_400)
    if kind.name == "td":
        whole = all(to_num(c) is None or to_num(c).denominator == 1 for c in consts)
        return F1 if whole else Fraction(1, 86_400)
    best = F1 if kind.name == "dec" else Fraction(1, 100)
    for c in consts:
        if isinstance(c, Decimal) and c.is_finite():
            e = c.as_tuple().exponent
            if isinstance(e, int) and e < 0:
                best = min(best, Fraction(1, 10 ** -e))
        elif isinstance(c, float) and math.isfinite(c):
            text = repr(c)
            if "." in text and "e" not in text:
                best = min(best, Fraction(1, 10 ** min(len(text.split(".")[1]), 9)))
    return best


def far_num(x: Fraction, kind, below: bool) -> Fraction:
    if kind.name in ("date", "datetime"):
        span = Fraction(365)
    elif kind.name == "td":
        span = Fraction(100)
    else:
        span = max(abs(x) * 10, Fraction(100))
        if kind.name == "int":
            span = Fraction(math.ceil(span))
    return x - span if below else x + span


# ---------------------------------------------------------------- linear forms

@dataclass
class Lin:
    coefs: dict          # field -> Fraction (no zero entries)
    k: Fraction

    def scaled(self, s: Fraction) -> "Lin":
        return Lin({f: c * s for f, c in self.coefs.items()}, self.k * s)

    def plus(self, other: "Lin", sign: int = 1) -> "Lin":
        out = dict(self.coefs)
        for f, c in other.coefs.items():
            out[f] = out.get(f, F0) + sign * c
        return Lin({f: c for f, c in out.items() if c != 0}, self.k + sign * other.k)


class Reader:
    """Reads one predicate's expressions as linear forms over its numeric fields."""

    def __init__(self, kinds: dict, env: dict, local: set, defs: dict, fold):
        self.kinds, self.env, self.local, self.defs, self.fold = kinds, env, local, defs, fold
        self.used: set = set()          # ids of the def values substituted while reading

    def lin(self, n, depth: int = 0) -> Lin | None:
        if depth > 50:
            return None
        if isinstance(n, ast.Name):
            if n.id in self.kinds:
                return Lin({n.id: F1}, F0) if self.kinds[n.id].name in NUMERIC else None
            if n.id in self.defs:
                value = self.defs[n.id]
                got = self.lin(value, depth + 1)
                if got is not None:
                    self.used |= {id(x) for x in ast.walk(value)}
                return got
        cv = self.fold(n)
        if cv is not None:
            v = to_num(cv[1])
            return Lin({}, v) if v is not None else None
        if isinstance(n, ast.BinOp):
            a, b = self.lin(n.left, depth + 1), self.lin(n.right, depth + 1)
            if a is None or b is None:
                return None
            if isinstance(n.op, ast.Add):
                return a.plus(b)
            if isinstance(n.op, ast.Sub):
                return a.plus(b, -1)
            if isinstance(n.op, ast.Mult):
                if not a.coefs:
                    return b.scaled(a.k)
                if not b.coefs:
                    return a.scaled(b.k)
                return None                                  # a product of two fields: not linear
            if isinstance(n.op, ast.Div) and not b.coefs and b.k != 0:
                return a.scaled(1 / b.k)
            return None
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.USub, ast.UAdd)):
            a = self.lin(n.operand, depth + 1)
            return None if a is None else a.scaled(Fraction(-1 if isinstance(n.op, ast.USub) else 1))
        if isinstance(n, ast.Attribute) and n.attr == "days":
            a = self.lin(n.value, depth + 1)   # whole days of a difference of dates: exact
            if a is not None and all(self.kinds[f].name in INTEGRAL and c.denominator == 1 for f, c in a.coefs.items()) \
                    and a.k.denominator == 1:
                return a
            return None
        if isinstance(n, ast.Call):
            if isinstance(n.func, ast.Attribute) and n.func.attr == "total_seconds" and not n.args and not n.keywords:
                a = self.lin(n.func.value, depth + 1)
                return None if a is None else a.scaled(Fraction(86_400))
            name = n.func.id if isinstance(n.func, ast.Name) else n.func.attr if isinstance(n.func, ast.Attribute) \
                else ""
            if name == "timedelta":
                out = Lin({}, F0)
                parts = list(zip(TD_ORDER, n.args)) + [(k.arg, k.value) for k in n.keywords]
                for unit, arg in parts:
                    if unit not in TD_DAYS:
                        return None
                    a = self.lin(arg, depth + 1)
                    if a is None:
                        return None
                    out = out.plus(a.scaled(TD_DAYS[unit]))
                return out
        return None


# ---------------------------------------------------------------- planes

class Plane:
    """sum(coef * field) + k = 0, normalised: integer coefficients with gcd 1, the first positive."""
    __slots__ = ("coefs", "k", "text")

    def __init__(self, coefs: dict, k: Fraction, text: str = ""):
        coefs = {f: Fraction(c) for f, c in coefs.items() if c != 0}
        k = Fraction(k)
        if coefs:
            lcm = 1
            for c in coefs.values():
                lcm = lcm * c.denominator // math.gcd(lcm, c.denominator)
            ints = {f: int(c * lcm) for f, c in coefs.items()}
            g = 0
            for c in ints.values():
                g = math.gcd(g, abs(c))
            sign = 1 if ints[min(ints)] > 0 else -1
            coefs = {f: Fraction(sign * c, g) for f, c in ints.items()}
            k = k * lcm * sign / g
        self.coefs, self.k, self.text = coefs, k, text

    @property
    def key(self):
        return (tuple(sorted(self.coefs.items())), self.k)

    def root(self, v: str, values: dict) -> Fraction:
        rest = self.k + sum(c * values[f] for f, c in self.coefs.items() if f != v)
        return -rest / self.coefs[v]

    def __repr__(self):
        return f"Plane({self.coefs}, {self.k})"


def _unique(planes) -> list:
    seen, out = set(), []
    for p in planes:
        if p.coefs and p.key not in seen:
            seen.add(p.key)
            out.append(p)
    return out


def project(planes: list, v: str, kind) -> tuple[list, bool]:
    """The planes one field down: those without v, and where each two planes with v cross. For an
    integer field also the crossings moved by -2..2 (the integer shadow). Exact for a real field,
    and for an integer field whose coefficient is 1 in every plane it is in."""
    with_v = [p for p in planes if v in p.coefs]
    out = [p for p in planes if v not in p.coefs]
    integral = kind.name in INTEGRAL
    exact = not integral or all(abs(p.coefs[v]) == 1 for p in with_v)
    for p, q in itertools.combinations(with_v, 2):
        pv, qv = p.coefs[v], q.coefs[v]
        fields = (set(p.coefs) | set(q.coefs)) - {v}
        coefs = {f: -p.coefs.get(f, F0) / pv + q.coefs.get(f, F0) / qv for f in fields}
        k = -p.k / pv + q.k / qv
        if not any(coefs.values()):
            continue
        for d in (OFFSETS if integral else (0,)):
            out.append(Plane(coefs, k - d))
    return _unique(out), exact


def candidates(roots: list, kind, step: Fraction) -> list:
    """Values of one field that hit both sides of and the place of every root, and the far sides."""
    roots = sorted(set(roots))
    if not roots:
        return DEFAULTS[kind.name]()
    vals = set()
    if kind.name in INTEGRAL:
        for t in roots:
            if t.denominator == 1:
                vals |= {t - 1, t, t + 1}
            else:
                vals |= {Fraction(math.floor(t)), Fraction(math.ceil(t))}
    else:
        vals |= set(roots) | {roots[0] - step, roots[-1] + step}
        for a, b in zip(roots, roots[1:]):
            if b - a > 2 * step:
                vals |= {a + step, b - step}
            else:
                vals.add((a + b) / 2)
    lo, hi = min(vals), max(vals)
    vals |= {far_num(lo, kind, True), far_num(hi, kind, False)}
    return sorted(vals)


DEFAULTS = {"int": lambda: [F0, F1], "float": lambda: [F0, F1], "dec": lambda: [F0, F1],
            "date": lambda: [to_num(date(2026, 1, 1))], "datetime": lambda: [to_num(datetime(2026, 1, 1))],
            "td": lambda: [F0, F1]}


def _choose(remaining: list, planes: list, kinds: dict) -> str:
    """The field to solve away next: exact first, then the one in fewest planes."""
    def cost(f):
        mine = [p for p in planes if f in p.coefs]
        exact = kinds[f].name not in INTEGRAL or all(abs(p.coefs[f]) == 1 for p in mine)
        return (not exact, len(mine), f)
    return min(remaining, key=cost)


def cylinder(fields: list, planes: list, kinds: dict, steps: dict) -> tuple[list, bool]:
    """(cells over `fields` as numbers, exact): one cell in every region of the arrangement of
    `planes` (exact) or an explicitly incomplete grid."""
    remaining, h, levels, order_rev, exact = list(fields), list(planes), {}, [], True
    while len(remaining) > 1:
        v = _choose(remaining, h, kinds)
        levels[v] = [p for p in h if v in p.coefs]
        h, ok = project(h, v, kinds[v])
        exact = exact and ok
        remaining.remove(v)
        order_rev.append(v)
    first = remaining[0]
    levels[first] = [p for p in h if first in p.coefs]
    order = [first] + order_rev[::-1]
    out: list = []

    def walk(i, values):
        v = order[i]
        roots = [p.root(v, values) for p in levels[v]]
        for x in candidates(roots, kinds[v], steps[v]):
            nxt = dict(values, **{v: x})
            if i + 1 == len(order):
                out.append(nxt)
            else:
                walk(i + 1, nxt)
    walk(0, {})
    return out, exact


def group_cells(fields: list, planes: list, kinds: dict, consts: dict, hints: dict) -> tuple[list, list]:
    """(cells as field values, reasons) for one group of fields joined by planes. The fields' own
    numeric constants are planes too; an Optional field is also tried absent, without its planes.
    `hints` holds the constants written in each field's planes (their decimals set the step)."""
    steps = {f: step_of(kinds[f], list(consts.get(f, [])) + list(hints.get(f, []))) for f in fields}
    own = []
    for f in fields:
        for c in consts.get(f, []):
            n = to_num(c)
            if n is not None:
                own.append(Plane({f: F1}, -n))
    reasons: list = []
    seen: set = set()
    out: list = []
    optional = [f for f in fields if kinds[f].optional]
    for absent in itertools.chain.from_iterable(itertools.combinations(optional, r) for r in range(len(optional) + 1)):
        present = [f for f in fields if f not in absent]
        ps = _unique([p for p in planes + own if not set(p.coefs) & set(absent)])
        if present:
            nums, exact = cylinder(present, ps, kinds, steps)
            if not exact:
                bad = sorted({p.text for p in planes if p.text and not set(p.coefs) & set(absent)})[:2]
                why = (f"integer fields {', '.join(present)} with coefficients other than 1"
                       + (f" in {'; '.join(bad)}" if bad else ""))
                if why not in reasons:
                    reasons.append(why)
        else:
            nums = [{}]
        for n in nums:
            cell = {f: None for f in absent}
            ok = True
            for f, x in n.items():
                v = from_num(x, kinds[f], steps[f])
                if v is None:
                    ok = False
                    break
                cell[f] = v
            key = tuple((f, type(cell[f]).__name__, repr(cell[f])) for f in fields)
            if ok and key not in seen:
                seen.add(key)
                out.append(cell)
    return out, reasons
