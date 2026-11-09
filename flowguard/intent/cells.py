"""Cells (design 3.1, R46): points per field, completeness, enumeration, the smallest cell, outcome equality.

Points: bool both values; enums every literal seen plus <other>; Optional adds None; numbers, dates
and durations c-e, c, c+e per compared constant c plus one far below and one far above (decimals
and floats also 0, the plain value). Comparisons whose sides are linear in the fields (x + y > 10,
returned > due + 2 days, (returned - due).days >= 3) are read exactly (flowguard.intent.linear): an atom over one
field is a bound on it, and fields joined by atoms over two or more fields are enumerated together,
one cell in every region the atoms cut. A key is `complete` when every atom was read that way;
Unknown atoms (field products, loops, arbitrary calls) keep the whole induced grid but
are explicitly not exhaustive; a small grid never makes an unknown predicate complete.
"""
from __future__ import annotations

import ast
import builtins as _builtins
import enum
import inspect
import itertools
import math
import textwrap
import types
import typing
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from fractions import Fraction

from . import linear as L

OTHER = "<other>"
LITERAL_CALLS = {"D", "Decimal", "date", "datetime", "timedelta", "Refused"}


@dataclass
class Kind:
    name: str                  # bool int float dec str enum date datetime td
    optional: bool = False
    literals: tuple = ()       # declared enum values
    enum_type: object = None

    def accepts(self, v) -> bool:
        if v is None:
            return self.optional
        if self.name == "bool":
            return isinstance(v, bool)
        if self.name in ("int",):
            return isinstance(v, int) and not isinstance(v, bool)
        if self.name in ("float", "dec"):
            return isinstance(v, (int, float, Decimal)) and not isinstance(v, bool)
        if self.name == "str":
            return isinstance(v, str)
        if self.name == "enum":
            return (isinstance(v, self.enum_type) if self.enum_type else True)
        if self.name == "datetime":
            return isinstance(v, datetime)
        if self.name == "date":
            return isinstance(v, date) and not isinstance(v, datetime)
        if self.name == "td":
            return isinstance(v, timedelta)
        return True


def kind_of(spec) -> Kind:
    origin = typing.get_origin(spec)
    if origin in (typing.Union, types.UnionType):
        args = [a for a in typing.get_args(spec) if a is not type(None)]
        if len(args) == 1 and type(None) in typing.get_args(spec):
            k = kind_of(args[0])
            k.optional = True
            return k
    if origin is typing.Literal:
        return Kind("enum", literals=tuple(typing.get_args(spec)))
    if isinstance(spec, (tuple, list, set, frozenset)):
        return Kind("enum", literals=tuple(spec))
    if isinstance(spec, type) and issubclass(spec, enum.Enum):
        return Kind("enum", literals=tuple(spec), enum_type=spec)
    table = {bool: "bool", int: "int", float: "float", Decimal: "dec", str: "str", date: "date",
             datetime: "datetime", timedelta: "td"}
    if spec in table:
        return Kind(table[spec])
    raise ValueError(f"field type {spec!r} is not one of bool, int, float, Decimal, str, date, datetime, "
                     "timedelta, a tuple of literals, an Enum, or Optional[...] of these")


def epsilon(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return 1
    if isinstance(v, Decimal):
        exp = v.as_tuple().exponent
        return Decimal(1).scaleb(exp if isinstance(exp, int) and exp < 0 else 0)
    if isinstance(v, float):
        text = repr(v)
        d = len(text.split(".")[1]) if "." in text and "e" not in text else 2
        return 10.0 ** -max(2, min(d, 9))
    if isinstance(v, datetime):
        return timedelta(seconds=1)
    if isinstance(v, date):
        return timedelta(days=1)
    if isinstance(v, timedelta):
        return timedelta(days=1) if v.total_seconds() % 86400 == 0 else timedelta(seconds=1)
    return None


def far(v, below: bool):
    if isinstance(v, (int, float, Decimal)) and not isinstance(v, bool):
        span = max(abs(v) * 10, 100)
        span = type(v)(span) if not isinstance(v, int) else int(span)
        return v - span if below else v + span
    if isinstance(v, date):
        return v - timedelta(days=365) if below else v + timedelta(days=365)
    if isinstance(v, timedelta):
        return v - timedelta(days=100) if below else v + timedelta(days=100)
    return None


def coerce(v, kind: Kind):
    """A constant seen next to a field, in the field's own type (an int bound on a Decimal field is a Decimal)."""
    if kind.name == "dec" and isinstance(v, (int, float)) and not isinstance(v, bool):
        return Decimal(str(v))
    if kind.name == "float" and isinstance(v, (int, Decimal)) and not isinstance(v, bool):
        return float(v)
    if kind.name == "int" and isinstance(v, timedelta) and v.total_seconds() % 86400 == 0:
        return v.days
    return v


def points(kind: Kind, consts, dense: bool = False) -> list:
    """Values that hit every side of every constant the field is compared with. `dense` (a field
    compared with another field) adds a midpoint between neighbours, so two or three fields can be
    ordered every way inside one interval, and never leaves fewer than three ordered values."""
    out = []
    if kind.name == "bool":
        out = [False, True]
    elif kind.name in ("enum", "str"):
        out = list(kind.literals) + [c for c in consts if (
            isinstance(c, kind.enum_type) if kind.enum_type else isinstance(c, (str, enum.Enum)))]
        if not kind.enum_type:
            other = OTHER
            while other in out:
                other += "_"
            out.append(other)
    else:
        eps = {}   # 50 and 50.00 are one bound; its step is the finer of the two (0.01)
        for c in consts:
            c = coerce(c, kind)
            if kind.accepts(c) and c is not None and not (
                isinstance(c, (float, Decimal)) and not math.isfinite(c)
            ):
                e = epsilon(c)
                eps[c] = e if c not in eps or eps[c] is None or (e is not None and e < eps[c]) else eps[c]
        cs = sorted(eps)
        for c in cs:
            e = eps[c]
            out.append(c)
            if e is not None:
                for sign in (-1, 1):
                    try:
                        out.append(c + sign * e)
                    except (ValueError, OverflowError):
                        pass  # date/datetime domain ends have no representable neighbour
        if cs:
            for c, below in ((cs[0], True), (cs[-1], False)):
                try:
                    out.append(far(c, below))
                except (ValueError, OverflowError):
                    pass  # the boundary already represents this finite type's endpoint
            if kind.name in ("dec", "float"):   # the plain amount: a witness reads owed=0, not owed=49.99
                finest = min((eps[c] for c in cs if eps[c] is not None), default=None)
                out.append(Decimal(0).quantize(finest) if kind.name == "dec" and finest is not None else
                           Decimal(0) if kind.name == "dec" else 0.0)
        else:
            out = {"int": [0, 1], "float": [0.0, 1.0], "dec": [Decimal("0"), Decimal("1")],
                   "date": [date(2026, 1, 1)], "datetime": [datetime(2026, 1, 1)],
                   "td": [timedelta(0), timedelta(days=1)]}[kind.name]
    seen, uniq = set(), []
    for v in out:
        key = (type(v).__name__, v)
        if key not in seen:
            seen.add(key)
            uniq.append(v)
    if kind.name not in ("bool", "enum", "str"):
        uniq.sort()
        if dense and uniq:
            if len(uniq) < 3:   # a field ordered against another needs below, equal and above
                e = epsilon(uniq[0])
                uniq = sorted({uniq[0] - e, *uniq, uniq[-1] + e}) if e is not None else uniq
            mids = [_mid(a, b) for a, b in zip(uniq, uniq[1:])]
            uniq = sorted({_k(v): v for v in uniq + [m for m in mids if m is not None]}.values())
    if kind.optional:
        uniq.append(None)
    return uniq


def representatives(kind: Kind) -> list:
    """Fixed values for a numeric input whose classes cannot be read from its comparisons: zero, small
    whole numbers on both sides, the halves between them and, for floats, NaN and both infinities.
    Every one is run; agreement on them is a finite sample, never a proof of equal behavior."""
    if kind.name == "float":
        return [-2.5, -2.0, -1.5, -1.0, -0.5, 0.0, 0.5, 1.0, 1.5, 2.0, 2.5, math.nan, math.inf, -math.inf]
    if kind.name == "dec":
        return [Decimal(text) for text in ("-2.5", "-2", "-1.5", "-1", "-0.5", "0", "0.5", "1", "1.5", "2", "2.5")]
    if kind.name == "int":
        return [-2, -1, 0, 1, 2]
    return []


def _mid(a, b):
    """A value strictly between a and b, or None when the type has none (5 and 6 as ints)."""
    if isinstance(a, int) and isinstance(b, int):
        m = (a + b) // 2
    elif isinstance(a, (date, datetime)) and isinstance(b, (date, datetime)):
        m = a + (b - a) // 2
    else:
        m = a + (b - a) / 2
    return m if a < m < b else None


# ---------------------------------------------------------------- predicate reading

def func_ast(fn) -> ast.FunctionDef:
    src = textwrap.dedent(inspect.getsource(fn))
    node = ast.parse(src).body[0]
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        node.decorator_list = []   # @rule(...) is not the predicate
        node.returns = None
        return node
    raise ValueError(f"cannot read the source of {fn.__qualname__}")


def _names(node) -> set:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def const_value(node, env: dict, local: set):
    """Fold an expression that reads no field and no local: literals, globals, attributes, D("50.00")."""
    if _names(node) & local:
        return None
    for n in ast.walk(node):
        if isinstance(n, ast.Call) and not (isinstance(n.func, (ast.Name, ast.Attribute)) and
                                             (n.func.id if isinstance(n.func, ast.Name) else n.func.attr)
                                             in LITERAL_CALLS | {"int", "float"}):
            return None
        if isinstance(n, (ast.Lambda, ast.NamedExpr, ast.Await, ast.Yield, ast.ListComp, ast.GeneratorExp)):
            return None
    try:
        return ("ok", eval(compile(ast.Expression(node), "<flowguard constant>", "eval"), env))
    except Exception:   # a name that is not a constant here: no bound to read  # fg2: handler-listed
        return None


def pairs_of(test) -> list:
    """(left, op, right) for every comparison, chained ones split."""
    out = []
    for n in ast.walk(test):
        if isinstance(n, ast.Compare):
            left = n.left
            for op, right in zip(n.ops, n.comparators):
                out.append((left, op, right, n))
                left = right
    return out


@dataclass
class Reading:
    """What one predicate compares (flowguard.intent.linear reads the arithmetic)."""
    consts: dict                                  # field -> constants it is bounded by or compared with
    planes: list = field(default_factory=list)    # atoms over two or more fields (linear.Plane)
    hints: dict = field(default_factory=dict)     # field -> the constants written in its planes
    links: set = field(default_factory=set)       # non-numeric fields compared with each other
    reasons: list = field(default_factory=list)   # what forces sampling: each atom or construct, once

    @property
    def complete(self) -> bool:
        return not self.reasons


OPS = {ast.Lt: "<", ast.LtE: "<=", ast.Gt: ">", ast.GtE: ">=", ast.Eq: "==", ast.NotEq: "!=", ast.In: "in",
       ast.NotIn: "not in", ast.Is: "is", ast.IsNot: "is not"}
LOOPS = (ast.For, ast.AsyncFor, ast.While, ast.With, ast.AsyncWith, ast.Try, ast.Lambda, ast.ListComp, ast.SetComp,
         ast.DictComp, ast.GeneratorExp)


def _kinds(fields: dict) -> dict:
    return {f: k if isinstance(k, Kind) else kind_of(k) for f, k in fields.items()}


def _bound(t: Fraction, kind: Kind, hints: list) -> list:
    """A bound on one field solved from a linear atom (2 * x > 9: x at 4.5), as field values."""
    if kind.name in L.INTEGRAL and t.denominator != 1:
        return [v for v in (L.from_num(Fraction(math.floor(t)), kind), L.from_num(Fraction(math.ceil(t)), kind))
                if v is not None]
    v = L.from_num(t, kind, L.step_of(kind, hints))
    return [] if v is None else [v]


def read_predicate(fn, fields: dict, node=None) -> Reading:
    """Read the predicate's atoms: single-field bounds and literals (consts), linear atoms over two or
    more fields (planes), non-numeric field-field comparisons (links), and the reasons the cells
    cannot be exhaustive (each non-linear atom, loop, call or computed return value, by its text).
    `node` optionally supplies an already parsed function syntax tree."""
    node = func_ast(fn) if node is None else node
    kinds = _kinds(fields)
    env = {**vars(_builtins), **fn.__globals__}
    stores = Counter(n.id for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store))
    defs = {}
    for n in ast.walk(node):
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) and \
                stores[n.targets[0].id] == 1 and n.targets[0].id not in kinds:
            defs[n.targets[0].id] = n.value
    local = set(kinds) | set(stores)
    tables = {}   # a local assigned once to a constant (a lookup table) folds like a global
    for name, value in defs.items():
        cv = const_value(value, env, local)
        if cv is not None:
            tables[name] = cv[1]
    env = {**env, **tables}
    local = local - set(tables)
    fold = lambda x: const_value(x, env, local)   # noqa: E731
    rd = L.Reader(kinds, env, local, defs, fold)
    out = Reading(consts={f: [] for f in kinds})
    covered: set = set()
    def_values = {id(x) for v in defs.values() for x in ast.walk(v)}
    finite = {f for f, k in kinds.items() if k.name in ("bool", "enum")}   # the cells hold their whole domain

    def why(text, node=None):
        if node is not None and fields_in(node) <= finite:
            return   # it reads only fields whose every value is a cell: exhaustive whatever it computes
        if text not in out.reasons:
            out.reasons.append(text)

    def lookup(e) -> bool:
        """TABLE.get(field, default) or TABLE[field]: literal membership on the field; its keys are points."""
        if isinstance(e, ast.Call) and isinstance(e.func, ast.Attribute) and e.func.attr == "get" and e.args \
                and bare(e.args[0]) and all(fold(a) is not None for a in e.args[1:]) and not e.keywords:
            table, key = fold(e.func.value), bare(e.args[0])
        elif isinstance(e, ast.Subscript) and bare(e.slice):
            table, key = fold(e.value), bare(e.slice)
        else:
            return False
        if table is None or not isinstance(table[1], (dict, tuple, list)):
            return False
        keys = list(table[1]) if isinstance(table[1], dict) else list(range(len(table[1])))
        out.consts[key].extend(keys)
        cover(e)
        return True

    def fields_in(x, seen=()) -> set:
        names = _names(x)
        got = names & set(kinds)
        for d in names & set(defs):
            if d not in seen:
                got |= fields_in(defs[d], (*seen, d))
        return got

    def cover(*xs):
        for x in xs:
            covered.update(id(y) for y in ast.walk(x))

    def bare(x):
        return x.id if isinstance(x, ast.Name) and x.id in kinds else None

    for cmp in [n for n in ast.walk(node) if isinstance(n, ast.Compare)]:
        left = cmp.left
        for op, right in zip(cmp.ops, cmp.comparators):
            text = f"{ast.unparse(left)} {OPS.get(type(op), '?')} {ast.unparse(right)}"
            fl, fr = fields_in(left), fields_in(right)
            a, b = left, right
            left = right
            if not fl and not fr:
                continue
            cover(a, b)
            if isinstance(op, (ast.In, ast.NotIn)):
                cv = fold(b)
                if cv is not None and isinstance(cv[1], (tuple, list, set, frozenset)) and not fr:
                    if bare(a):
                        out.consts[bare(a)].extend(cv[1])
                        continue
                    lin = rd.lin(a)
                    nums = [L.to_num(v) for v in cv[1]]
                    if lin is not None and lin.coefs and all(x is not None for x in nums):
                        for x in nums:
                            _atom(out, kinds, lin.plus(L.Lin({}, x), -1), text, [*cv[1]])
                        continue
                why(f"{text} (membership of a computed value)", cmp)
                continue
            if isinstance(op, (ast.Is, ast.IsNot)):
                if not ((bare(a) and fold(b) is not None) or (bare(b) and fold(a) is not None)):
                    why(f"{text} (identity of a computed value)", cmp)
                continue
            done = False
            for x, y in ((a, b), (b, a)):   # field op literal: the literal as written (50.00 keeps its cents)
                cv = fold(y)
                if bare(x) and cv is not None and not fields_in(y):
                    out.consts[bare(x)].append(cv[1])
                    if isinstance(op, (ast.Lt, ast.LtE, ast.Gt, ast.GtE)) and kinds[bare(x)].name == "str":
                        why(f"{text} (ordered strings need a finite declared domain)", cmp)
                    done = True
                    break
            if done:
                continue
            if bare(a) and bare(b) and not (kinds[bare(a)].name in L.NUMERIC and kinds[bare(b)].name in L.NUMERIC):
                out.links.add(frozenset((bare(a), bare(b))))
                continue
            la, lb = rd.lin(a), rd.lin(b)
            if la is not None and lb is not None:
                lits = [c[1] for c in (fold(z) for z in ast.walk(cmp) if isinstance(z, (ast.Constant, ast.Call)))
                        if c is not None]
                _atom(out, kinds, la.plus(lb, -1), text, lits)
                continue
            why(f"{text} (not linear)", cmp)
            for x, y in ((a, b), (b, a)):   # a sample still tries the constant on each field it names
                cv = fold(y)
                if cv is not None:
                    for f in fields_in(x):
                        out.consts[f].append(cv[1])
    covered |= rd.used

    def returned(e) -> bool:
        if e is not None and (fields_in(e) <= finite or lookup(e)):
            return True
        if e is None or fold(e) is not None or isinstance(e, (ast.Compare, ast.BoolOp)) or \
                (isinstance(e, ast.UnaryOp) and isinstance(e.op, ast.Not)):
            return True if not isinstance(e, ast.BoolOp) else all(returned(v) for v in e.values)
        if isinstance(e, ast.IfExp):
            return returned(e.body) and returned(e.orelse)
        if isinstance(e, ast.Name):
            if e.id in kinds:
                return kinds[e.id].name not in L.NUMERIC
            if e.id in defs:
                return returned(defs[e.id])
        return not fields_in(e)
    for n in ast.walk(node):
        if isinstance(n, ast.Return) and n.value is not None:
            if not returned(n.value):
                why(f"returns {ast.unparse(n.value)[:60]} (a computed value)")
                cover(n.value)
        for t in _tests(n):   # a number, duration or text used as a truth value: its empty value is a boundary
            empty = {"int": 0, "float": 0, "dec": 0, "td": timedelta(0), "str": ""}.get(kinds[bare(t)].name) \
                if bare(t) else None
            if empty is not None:
                out.consts[bare(t)].append(empty)
    for n in ast.walk(node):
        if id(n) in covered or id(n) in def_values:
            continue
        if isinstance(n, LOOPS):
            why(f"{type(n).__name__.lower()} in the predicate", n)
        elif isinstance(n, ast.AugAssign) or (isinstance(n, ast.Assign) and not (
                len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) and n.targets[0].id in defs)):
            why(f"{ast.unparse(n)[:60]} (a name assigned more than once)", n)
        elif isinstance(n, ast.Call) and fields_in(n) and not _literal_call(n) and not lookup(n):
            why(f"calls {ast.unparse(n.func)} on a field", n)
        elif isinstance(n, (ast.BinOp, ast.Subscript, ast.Attribute)) and fields_in(n) and fold(n) is None \
                and not lookup(n):
            why(f"{ast.unparse(n)[:60]} outside a linear comparison", n)
    return out


def _literal_call(n) -> bool:
    name = n.func.id if isinstance(n.func, ast.Name) else n.func.attr if isinstance(n.func, ast.Attribute) else ""
    return name in LITERAL_CALLS and name not in ("timedelta",)


def _tests(n) -> list:
    if isinstance(n, (ast.If, ast.IfExp, ast.While, ast.Assert)):
        return [n.test]
    if isinstance(n, ast.BoolOp):
        return list(n.values)
    if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.Not):
        return [n.operand]
    return []


def _atom(out: Reading, kinds: dict, d, text: str, lits: list) -> None:
    """A linear atom d(fields) <op> 0: a bound when it names one field, a plane when it names more."""
    if not d.coefs:
        return
    if len(d.coefs) == 1:
        (f, c), = d.coefs.items()
        out.consts[f].extend(_bound(-d.k / c, kinds[f], lits))
        return
    out.planes.append(L.Plane(d.coefs, d.k, text))
    for f in d.coefs:
        out.hints.setdefault(f, []).extend(v for v in lits if isinstance(v, (Decimal, float)))


def comparable(a: Kind, b: Kind) -> bool:
    num = ("int", "float", "dec")
    return (a.name in num and b.name in num) or a.name == b.name


def linked_groups(links, kinds: dict) -> list[set]:
    """Fields joined by direct comparisons (union of the pairs), only between comparable kinds."""
    groups: list[set] = []
    for pair in links:
        a, b = sorted(pair)
        if a not in kinds or b not in kinds or not comparable(kinds[a], kinds[b]):
            continue
        hit = [g for g in groups if g & {a, b}]
        merged = set().union({a, b}, *hit)
        groups = [g for g in groups if g not in hit] + [merged]
    return groups


def field_points(kinds: dict, consts: dict, links) -> tuple[dict, bool]:
    """Points per field; linked fields share each other's constants (dense), so equality and both
    orders occur. Complete only if no linked group has more than three fields. (The engine reads
    numeric links as planes, build_space; this stays for literal fields and callers of the old form.)"""
    consts = {f: list(v) for f, v in consts.items()}
    groups = linked_groups(links, kinds)
    for g in groups:
        shared = [coerce(v, kinds[f]) for f in g for v in consts[f]]
        for f in g:
            consts[f] = [coerce(v, kinds[f]) for v in shared]
    linked = set().union(*groups) if groups else set()
    pts = {f: points(k, consts[f], dense=f in linked) for f, k in kinds.items()}
    return pts, all(len(g) <= 3 for g in groups)


# ---------------------------------------------------------------- the space of a key

@dataclass
class Space:
    cells: list
    label: str
    total: int
    pts: dict
    reasons: list

    @property
    def complete(self) -> bool:
        return self.label == "complete"


def _groups(planes: list, kinds: dict) -> list[list]:
    parent: dict = {}

    def find(x):
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for p in planes:
        fs = [f for f in p.coefs if f in kinds]
        for f in fs[1:]:
            parent[find(f)] = find(fs[0])
    comps: dict = {}
    for f in parent:
        comps.setdefault(find(f), []).append(f)
    return [sorted(g) for g in comps.values() if len(g) > 1]


def build_space(kinds: dict, consts: dict, planes=(), links=(), reasons=(), hints=None, seed: str = "") -> Space:
    """Enumerate every induced cell, without a cap. Unreadable atoms remain incomplete.

    The seed is accepted for callers identifying a space; enumeration is deterministic.
    Linear groups enumerate one representative in each region rather than multiplying
    each group's projected coordinate lists (which would create redundant cells).
    """
    kinds = _kinds(kinds)
    if kinds and all(kind.name == 'bool' or (kind.name == 'enum' and kind.enum_type) for kind in kinds.values()):
        # This is the actual finite type domain, not a partition or a sample.
        # Arbitrary inner arithmetic cannot hide an input when every value runs.
        pts = {name: points(kind, consts.get(name, [])) for name, kind in kinds.items()}
        cells, label, total = enumerate_cells(pts, complete=True)
        return Space(cells, label, total, pts, [])
    reasons, hints = list(reasons), dict(hints or {})
    consts = {f: list(consts.get(f, [])) for f in kinds}
    planes = [p for p in planes if set(p.coefs) <= set(kinds)]
    literal = set()
    for pair in links:
        a, b = sorted(pair)
        if a in kinds and b in kinds and kinds[a].name in L.NUMERIC and kinds[b].name in L.NUMERIC:
            planes.append(L.Plane({a: 1, b: -1}, 0, f"{a} vs {b}"))
        else:
            literal.add(pair)
    for g in linked_groups(literal, kinds):
        shared = [coerce(v, kinds[f]) for f in g for v in consts[f]]
        for f in g:
            consts[f] = [coerce(v, kinds[f]) for v in shared]
    groups = _groups(planes, kinds)
    grouped = {f for g in groups for f in g}
    pts = {f: points(kinds[f], consts[f]) for f in kinds if f not in grouped}
    # Distinct unseen strings are required to represent all equality partitions
    # when several unbounded strings are compared with one another.
    for g in linked_groups(literal, kinds):
        if all(kinds[f].name == "str" for f in g):
            unseen = [_other_string(i, consts) for i in range(len(g))]
            for f in g:
                pts[f] = list(dict.fromkeys(pts[f] + unseen))
    lists = []
    for g in groups:
        gp = [p for p in planes if set(p.coefs) <= set(g)]
        gc = {f: [coerce(v, kinds[f]) for v in consts[f]] for f in g}
        cells, why = L.group_cells(g, gp, kinds, gc, hints)
        reasons += [w for w in why if w not in reasons]
        for f in g:
            vals = {_k(c[f]): c[f] for c in cells if c[f] is not None}
            pts[f] = sorted(vals.values()) + ([None] if kinds[f].optional else [])
        lists.append((g, cells))
    names = sorted(f for f in kinds if f not in {x for g, _ in lists for x in g})
    cells = [_merge(combo, names) for combo in itertools.product(
        *(pts[n] for n in names), *(c for _, c in lists))]
    total = len(cells)
    label = "complete" if not reasons else f"grid {total} of {total}"
    return Space(cells, label, total, pts, reasons)


def _other_string(i, consts):
    used = {v for values in consts.values() for v in values if isinstance(v, str)}
    value = OTHER if i == 0 else f"<other:{i}>"
    while value in used:
        value += "_"
    return value


def _merge(combo, names) -> dict:
    cell = dict(zip(names, combo[:len(names)]))
    for part in combo[len(names):]:
        cell.update(part)
    return cell


def _ckey(r: dict) -> tuple:
    return tuple((u, repr(sorted(v.items(), key=lambda kv: kv[0])) if isinstance(v, dict) else repr(v))
                 for u, v in sorted(r.items()))


# ---------------------------------------------------------------- enumeration

def enumerate_cells(pts: dict, complete: bool, seed: str = "") -> tuple[list, str, int]:
    """Run the entire product. Unknown predicates never become complete by size."""
    names = sorted(pts)
    cells = [dict(zip(names, combo)) for combo in itertools.product(*(pts[n] for n in names))]
    total = len(cells)
    return cells, "complete" if complete else f"grid {total} of {total}", total


def _k(v):
    return (type(v).__name__, v)


def base_index(vals: list) -> int:
    """The plain value of a field: the number nearest 0, else the first value (False, the first literal)."""
    nums = [v for v in vals if isinstance(v, (int, float, Decimal)) and not isinstance(v, bool)]
    if nums:
        return vals.index(min(nums, key=lambda v: (abs(v), v)))
    return 0


def base_value(vals: list):
    """The plain value: None for an Optional field (the absent case), else as base_index."""
    return None if None in vals else vals[base_index(vals)]


def off_base(vals: list, v) -> int:
    """How far v is from the plain value: 0 at the base. An Optional field is plain when absent
    (None); a present value weighs more than any step along the field's own points."""
    if None in vals:
        return 0 if v is None else len(vals) + abs(_index(vals, v) - base_index([x for x in vals if x is not None]))
    return abs(_index(vals, v) - base_index(vals))


def smallest(cells: list, pts: dict):
    """The disagreeing cell nearest to the plain case: fewest fields off their base value, then nearest."""
    def key(c):
        off = [off_base(pts[n], c[n]) for n in sorted(c) if n in pts]
        return (sum(1 for o in off if o), sum(off), repr(sorted(c.items(), key=lambda kv: kv[0])))
    return min(cells, key=key)


def _index(vals, v):
    for i, x in enumerate(vals):
        if type(x) is type(v) and x == v:
            return i
    return 0


# ---------------------------------------------------------------- outcomes

class Raised:
    """An exception as an outcome, compared by type and message."""

    def __init__(self, error: BaseException):
        self.error = error

    def __repr__(self):
        msg = str(self.error)
        return f"raised {type(self.error).__name__}" + (f"({msg[:60]!r})" if msg else "")


def same(expected, got) -> bool:
    from .api import Refused
    if isinstance(expected, Refused):
        return isinstance(got, Raised) and expected.matches(got.error)
    if isinstance(got, Raised) or isinstance(got, Refused):
        return False
    if isinstance(expected, bool) or isinstance(got, bool):
        return type(expected) is type(got) and expected == got
    if isinstance(expected, (int, float, Decimal)) and isinstance(got, (int, float, Decimal)):
        if expected != expected and got != got:      # NaN answers NaN: one outcome, though NaN != NaN
            return True
        return Decimal(str(expected)) == Decimal(str(got))
    return expected == got


def show(v) -> str:
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    if isinstance(v, timedelta):
        return f"{v.days}d" if v.total_seconds() % 86400 == 0 else str(v)
    if isinstance(v, bool):
        return "T" if v else "F"
    return repr(v) if isinstance(v, str) else str(v)


def show_cell(c: dict) -> str:
    return " ".join(f"{k}={show(v)}" for k, v in sorted(c.items()))
