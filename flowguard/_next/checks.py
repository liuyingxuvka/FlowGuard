"""The prepared checks (M3): STUCK, NEVER REACHED with the one-setting explanation,
BROKEN, CONTRADICTION; their class (conflict / model warning / model error), the
requests behind each (attribution per kind), and the path-free fingerprint (M6)."""
from __future__ import annotations

import ast
import hashlib
import inspect
import json
from dataclasses import dataclass, field, replace
from pathlib import Path

from .explore import Bounds, Graph, explore, orbit, replay, show_step, show_tuple
from .model import Loaded, Model, ModelError, Refused, State, natural_key, show_key

CONFLICT, WARNING, ERROR_CLS = "conflict", "warning", "error"
_CLASS_ORDER = {CONFLICT: 0, WARNING: 1, ERROR_CLS: 2}
_IN_PROCESS = ("states", "where")      # detail keys that hold graph indices (not saved)
_CONCURRENCY = ("threading", "asyncio", "multiprocessing", "concurrent.futures", "queue", "selectors",
                "socketserver")


# ---------------------------------------------------------------------- findings
def fingerprint(kind, model, subject, sources) -> str:
    data = json.dumps([kind, model, subject, sorted(sources, key=natural_key)], ensure_ascii=False,
                      separators=(",", ":"))
    return "C-" + hashlib.sha256(data.encode("utf-8")).hexdigest()[:12]


@dataclass(frozen=True)
class Finding:
    kind: str                 # STUCK, NEVER REACHED, BROKEN, CONTRADICTION, MODEL ERROR, ...
    cls: str                  # conflict | warning | error
    model: str
    subject: str              # path-free and object-free: "cond[*] = 'repair'", "always 'x'"
    text: str                 # the one-line symptom
    objects: tuple
    sources: tuple            # request ids, natural order
    path: tuple               # shown steps of the shortest witness
    state: str
    detail: dict
    line: int | None
    id: str

    def to_json(self) -> dict:
        return {"id": self.id, "kind": self.kind, "cls": self.cls, "model": self.model,
                "subject": self.subject, "text": self.text, "objects": list(self.objects),
                "sources": list(self.sources), "path": list(self.path), "state": self.state,
                "detail": {k: v for k, v in self.detail.items() if k not in _IN_PROCESS}, "line": self.line}

    @staticmethod
    def from_json(d: dict) -> "Finding":
        return Finding(d["kind"], d["cls"], d["model"], d["subject"], d["text"], tuple(d["objects"]),
                       tuple(d["sources"]), tuple(d["path"]), d["state"], dict(d["detail"]), d["line"],
                       d["id"])


def make_finding(kind, cls, model, subject, text, *, objects=(), sources=(), path=(), state="",
                 detail=None, line=None) -> Finding:
    srcs = tuple(sorted({s for s in sources if s}, key=natural_key))
    objs = tuple(sorted(set(objects), key=natural_key))
    return Finding(kind, cls, model, subject, text, objs, srcs, tuple(path), state, dict(detail or {}),
                   line, fingerprint(kind, model, subject, srcs))


def merge(raw: list[Finding]) -> list[Finding]:
    """Findings with one fingerprint become one: the shortest witness, all objects."""
    groups, order = {}, []
    for f in raw:
        if f.id not in groups:
            groups[f.id] = []
            order.append(f.id)
        groups[f.id].append(f)
    out = []
    for fid in order:
        members = groups[fid]
        best = min(members, key=lambda f: len(f.path))
        objs = tuple(sorted({o for f in members for o in f.objects}, key=natural_key))
        out.append(replace(best, objects=objs))
    return out


@dataclass
class Report:
    loaded: Loaded
    graph: Graph
    raw: list
    findings: list
    holds: list               # ("always 'x'", "holds" | "reached" | "unknown")
    unknown: list             # the checks a capped search could not decide
    reach: dict               # facts of the reach line; see reach_line()
    explained: dict = field(default_factory=dict)
    reached: list = field(default_factory=list)     # subjects of the model's items every instance of which is reached


# ---------------------------------------------------------------------- small helpers
def _owner(key):
    """The object a field key belongs to (key[1:]), None for a field of no object."""
    return key[1:] if isinstance(key, tuple) else None


def _subject_key(key):
    if isinstance(key, tuple):
        return f"{key[0]}[{','.join('*' for _ in key[1:])}]"
    return str(key)


def _mask(v, ids):
    t = type(v)
    if t is str and v in ids:
        return f"<{ids[v]}>"
    if t is tuple:
        return tuple(_mask(x, ids) for x in v)
    if t is frozenset:
        return frozenset(_mask(x, ids) for x in v)
    return v


def _key_objects(key):
    return tuple(str(x) for x in key[1:]) if isinstance(key, tuple) else ()


def _plural(n, word):
    return f"{n:,} {word}{'s' if n != 1 else ''}"


def _typed(v):
    return (type(v), v)


def _code_consts(code, out):
    for c in code.co_consts:
        if hasattr(c, "co_consts"):
            _code_consts(c, out)
        elif isinstance(c, (tuple, frozenset)):
            for x in c:
                try:
                    out.add(_typed(x))
                except TypeError:
                    pass
        else:
            try:
                out.add(_typed(c))
            except TypeError:
                pass
    return out


def _fn_consts(fns):
    out = set()
    for fn in fns:
        if fn is not None and hasattr(fn, "__code__"):
            _code_consts(fn.__code__, out)
    return out


def _with_helpers(fn):
    """fn and the plain functions of its own file that it calls by name (transitively).
    A wrapped action (functools.wraps, as mutation wraps them) counts as the function it wraps."""
    seen, stack, out = set(), [inspect.unwrap(fn)], []
    while stack:
        f = stack.pop()
        if id(f) in seen or not hasattr(f, "__code__"):
            continue
        seen.add(id(f))
        out.append(f)
        names = set()
        codes = [f.__code__]
        while codes:
            c = codes.pop()
            names.update(c.co_names)
            codes.extend(x for x in c.co_consts if hasattr(x, "co_consts"))
        for n in names:
            g = f.__globals__.get(n)
            if callable(g) and hasattr(g, "__code__") and g.__code__.co_filename == f.__code__.co_filename:
                stack.append(g)
    return out


def setting_variations(model: Model) -> list[tuple[str, object]]:
    """The one-setting changes an explanation tries (port of variations_of): a bool its
    other value; an int 0, 1, 2, v-1, v+1, 2v without negatives; vary= replaces the list."""
    out = []
    for name, value in model.settings.items():
        info = model.setting_info.get(name)
        vary = info.vary if info is not None else None
        if vary is not None:
            cands = list(vary)
        elif isinstance(value, bool):
            cands = [not value]
        elif isinstance(value, int):
            cands = [0, 1, 2, value - 1, value + 1, 2 * value]
        else:
            cands = []
        seen = []
        for c in cands:
            if c != value and c not in seen and not (isinstance(c, int) and not isinstance(c, bool) and c < 0):
                seen.append(c)
        out += [(name, c) for c in seen]
    return out


class _Frame:
    """Uniform renaming operations, trivial without symmetry."""

    def __init__(self, g: Graph):
        self.g = g
        self.sym = g.sym
        self.P = g.sym.n if g.sym is not None else 1
        self._stab = {}

    def dest(self, p, pos):
        return pos if p == 0 else self.sym.dest[p][pos]

    def ren(self, p, v):
        return v if p == 0 else self.sym.rename(p, v)

    def compose(self, a, b):
        return self.sym.compose(a, b) if self.sym is not None else 0

    def inv(self, p):
        return self.sym.inv[p] if self.sym is not None else 0

    def stab(self, i):
        s = self._stab.get(i)
        if s is None:
            s = self.sym.stabilizer(self.g.states[i]) if self.sym is not None else [0]
            self._stab[i] = s
        return s

    def coset(self, i, sigma):
        """Id of the unreduced state rename(sigma, states[i])."""
        if self.P == 1:
            return 0
        return min(self.compose(sigma, h) for h in self.stab(i))

    def unreduced(self, i, sigma):
        return i * self.P + self.coset(i, sigma)

    def all_cosets(self, i):
        if self.P == 1:
            return [0]
        return sorted({self.coset(i, s) for s in range(self.P)})


def _first_line(text):
    return text.split("\n", 1)[0]


# ---------------------------------------------------------------------- the check
class _Run:
    def __init__(self, loaded: Loaded, bounds: Bounds, explain: bool, reduce: bool, progress):
        self.loaded = loaded
        self.model = loaded.model
        self.bounds = bounds
        self.explain = explain
        self.reduce = reduce
        self.g = explore(self.model, bounds, reduce=reduce, progress=progress)
        self.fr = _Frame(self.g)
        self.mid = self.model.id or self.model.name
        self.ids = {i: k for k, idl in self.model.kinds.items() for i in idl}
        self.errors = []                       # ModelError raised while checking (rule code)
        self.field_by_key = {f.key: f for f in self.model.fields}
        self.keys = self.g.keys
        self.pos = {k: p for p, k in enumerate(self.keys)}
        self.explanation_errors = []           # model errors seen in one-setting variants
        self.reach_raised = set()              # reach rules whose predicate raised (undecided)
        self._closed_changers = {}

    # -------------------------------------------------------------- helpers
    def subject_value(self, v):
        return repr(_mask(v, self.ids)) if self.ids else repr(v)

    def state_dict(self, i):
        return State(zip(self.keys, self.g.states[i]))

    def model_error(self, text, err=None, line=None):
        file, ln = None, line
        if err is not None:
            from .explore import _location
            file, ln = _location(err, self.model.root)
        self.errors.append(ModelError(text, file, ln))

    def witness(self, u, last=None):
        P = self.fr.P
        i, cid = divmod(u, P)
        to = cid if P > 1 else None
        calls = self.g.path_calls(i, last, to)
        state = show_tuple(self.g, self.g.end_state(i, to))
        return calls, state

    def steps(self, calls):
        return tuple(show_step(self.g.calls[c].step()) for c in calls)

    def notes(self, *items):
        out = []
        for it in items:
            note = getattr(it, "note", None)
            if note and note not in out:
                out.append(note)
        return out

    # -------------------------------------------------------------- run
    def run(self) -> Report:
        g, model = self.g, self.model
        raw = []
        holds, unknown = [], []
        stuck_names = set()
        reach_missing = []
        explained = {}
        if g.complete:
            stuck = self.stuck()
            raw += stuck
            stuck_names = {n for f in stuck for n in f.detail.get("progress_names", [])}
            never, reach_missing, explained = self.never()
            raw += never
        else:
            unknown += ["STUCK", "NEVER REACHED"]
            reach_missing = [r for r in self.reach_unreached()]
        raw += self.broken()
        raw += self.contradictions()
        raw += self.settings_warning()
        raw += self.error_findings()
        for r in model.rules:
            label = f"{r.kind} {r.name!r}"
            if r.kind in ("always", "only_when", "after"):
                if r.name not in g.broken:
                    holds.append((label, "holds" if g.complete else "unknown"))
            elif r.kind == "progress":
                if not g.complete:
                    holds.append((label, "unknown"))
                elif r.name not in stuck_names:
                    holds.append((label, "holds"))
            elif r.kind == "reach":
                if r.name not in {x.name for x in reach_missing}:
                    holds.append((label, "reached"))
                elif not g.complete:
                    holds.append((label, "unknown"))
        if not g.complete:
            seen = set()
            for r in model.rules:
                label = None
                if r.kind == "progress":
                    label = f"progress {r.base!r}"
                elif r.kind == "reach" and r in reach_missing:
                    label = f"reach {r.base!r}"
                elif r.kind in ("always", "only_when", "after") and r.name not in g.broken:
                    label = f"{r.kind} {r.base!r}"
                if label and label not in seen:
                    seen.add(label)
                    unknown.append(label)
        findings = merge(raw)
        findings.sort(key=lambda f: _CLASS_ORDER[f.cls])
        return Report(self.loaded, g, raw, findings, holds, unknown, self.reach_facts(unknown), explained,
                      self.reached_subjects(reach_missing))

    # -------------------------------------------------------------- STUCK
    def orbits(self):
        width = len(self.keys)
        done, out = set(), []
        for p in range(width):
            if p in done:
                continue
            o = sorted({self.fr.dest(q, p) for q in range(self.fr.P)})
            done.update(o)
            out.append(o)
        return out

    def stuck(self) -> list[Finding]:
        g, fr, model = self.g, self.fr, self.model
        keys, states = self.keys, g.states
        width, N, P = len(keys), len(states), fr.P
        sym = g.sym
        family = [k[0] if isinstance(k, tuple) else None for k in keys]
        # nodes (i, k) of each position orbit; the class of (position, value)
        orbits = self.orbits()
        orbit_of = {}
        for oi, o in enumerate(orbits):
            for k, p in enumerate(o):
                orbit_of[p] = (oi, k)
        all_ids = set(self.ids)
        idfree = []
        for o in orbits:
            idfree.append(sym is None or not any(
                any(_has(v, all_ids) for v in self.field_by_key[keys[p]].domain) for p in o))

        def cls(p, v):
            oi = orbit_of[p][0]
            if P == 1:
                return (p, v)
            if idfree[oi]:
                return (orbits[oi][0], v)
            best = None
            for q in range(P):
                cand = (sym.dest[q][p], sym._rank_of(sym.rename(q, v)))
                if best is None or cand < best:
                    best, bq = cand, q
            return (best[0], sym.rename(bq, v))

        changing = [bytearray(N) for _ in range(width)]   # changing[p][i]: some step changes p at i
        changers = [set() for _ in range(width)]          # calls that change p (rep frame)
        for i, row in enumerate(g.out):
            si = states[i]
            prow = g.perm[i] if g.perm is not None else None
            cache = {}
            for c, j in enumerate(row):
                if j < 0:
                    continue
                p_ = prow[c] if prow is not None else 0
                diff = cache.get((j, p_))
                if diff is None:
                    raw_t = states[j] if p_ == 0 else sym.apply(sym.inv[p_], states[j])
                    diff = [p for p in range(width) if si[p] != raw_t[p]]
                    cache[(j, p_)] = diff
                for p in diff:
                    changing[p][i] = 1
                    changers[p].add(c)
        self._changers = changers
        leaves, values = [set() for _ in orbits], [set() for _ in orbits]
        for oi, o in enumerate(orbits):
            for p in o:
                ch = changing[p]
                for i in range(N):
                    c_ = cls(p, states[i][p])
                    values[oi].add(c_)
                    if ch[i]:
                        leaves[oi].add(c_)
        obj_pos = {None: list(range(width))}              # an object (key[1:]) -> its positions; a field
        for p, k in enumerate(keys):                      # of no object belongs to the whole model (None)
            if isinstance(k, tuple) and len(k) > 1:
                obj_pos.setdefault(k[1:], []).append(p)
        ends = {}                                         # family -> (values, declared)
        self.frozen_ends = []                             # (class, nodes, orbit): undeclared, the object freezes
        self.narrowed = []                                # (class, nodes, orbit, lost, kept): it loses steps for good
        for oi, o in enumerate(orbits):
            f0 = self.field_by_key[keys[o[0]]]
            name, plain = f0.family, family[o[0]] is None
            if name in model.terminals:
                if not plain:
                    ends[name] = (set(model.terminals[name]), True)
                continue
            # a value held from the start that no state leaves: no step ever changes the field
            # (a constant, or a counter nothing advances), so no step enters it and it ends nothing
            never = values[oi] - leaves[oi] - {cls(p, states[0][p]) for p in o}
            if not never:
                continue
            text = all(isinstance(v, str) or v is None for v in f0.domain)
            n = len(o)
            for c_ in sorted(never, key=repr):
                # a value no state leaves ends its object's life when only finitely many changes
                # of the object can follow it (no cycle changes the object while it holds the
                # value): the object comes to a halt there. When the object can go on changing
                # for ever (a flag set once on a book still lent and returned) it is a one-way
                # marker and ends nothing.
                nodes = [i * n + k for k, p in enumerate(o) for i in range(N) if cls(p, states[i][p]) == c_]
                halted = self.halts(nodes, o, obj_pos)
                if halted is None:
                    # it goes on changing there; still a dead end when it can never again take a
                    # step it took before (a side flag that toggles keeps no life going)
                    lost, kept = self.lost_steps(c_, nodes, o, obj_pos, cls, own=not text)
                    if lost:
                        self.narrowed.append((c_, nodes, o, lost, kept))
                    continue
                # where its object has come to a declared end (a retired tool's repair count)
                # the value ends nothing more: the life is over by design
                halted = [x for x in halted if not self.at_declared_end(x // n, _owner(keys[o[x % n]]), obj_pos)]
                if not halted:
                    continue
                self.frozen_ends.append((c_, halted, o))
                if not plain:                                 # the end of an object's life (exemptions)
                    old = ends.get(name, (set(), False))[0]
                    ends[name] = (old | {fr.ren(q, c_[1]) for q in range(P)}, False)

        def is_end(p, v):
            return v in ends[family[p]][0]

        objects = {}
        for p in range(width):
            if family[p] in ends and len(keys[p]) == 2:
                objects.setdefault(keys[p][1], []).append(p)
        fin_cache = {}

        def finishable(obj):
            """(pair graph, marks) for the life-cycle object obj's orbit."""
            items = orbit(g, obj)
            sig = tuple(items)
            if sig not in fin_cache:
                pg = g.pair_graph(items, lambda q, x: fr.ren(q, x))
                seeds = [i * pg.n + k for i, t in enumerate(states) for k, x in enumerate(items)
                         if any(is_end(p, t[p]) for p in objects[x])]
                fin_cache[sig] = (pg, {x: k for k, x in enumerate(items)},
                                  pg.reverse_reach(seeds) if seeds else bytearray(N * pg.n))
            return fin_cache[sig]

        ended = bytearray(N)
        if objects:
            for i, t in enumerate(states):
                if all(any(is_end(p, t[p]) for p in ps) for ps in objects.values()):
                    ended[i] = 1
        self.world_can_end = any(ended)
        self.terminal = []
        listed = set()
        found = []                                        # (key, value, first u, where_u, kind)
        for oi, o in enumerate(orbits):
            for p in o:
                if family[p] in ends and family[p] not in listed:
                    listed.add(family[p])
                    self.terminal.append((family[p], sorted(ends[family[p]][0], key=repr), ends[family[p]][1]))
            pg = g.pair_graph(o, lambda q, x: fr.dest(q, x))
            n = pg.n
            name = family[o[0]]
            fam = self.field_by_key[keys[o[0]]].family
            if fam in model.terminals:                    # declared ends: other never-left values
                never = values[oi] - leaves[oi] - {cls(p, states[0][p]) for p in o}
                for c_ in never:
                    nodes = [i * n + k for k, p in enumerate(o) for i in range(N) if cls(p, states[i][p]) == c_]
                    for q, w, where in self.expand(c_, nodes, o):
                        if w in model.terminals[fam]:
                            continue
                        found.append((keys[q], w, min(where), frozenset(where), "dead end"))
            cand = [(i, k) for k, p in enumerate(o) for i in range(N)
                    if not changing[p][i] and cls(p, states[i][p]) in leaves[oi]]
            if not cand:
                continue
            ok = pg.reverse_reach([i * n + k for k, p in enumerate(o) for i in range(N) if changing[p][i]])
            by_cls = {}
            for i, k in cand:
                p = o[k]
                if ok[i * n + k]:
                    continue
                key = keys[p]
                if name not in model.terminals:           # an undeclared end of the field keeps the exemption
                    owners = [x for x in (key[1:] if isinstance(key, tuple) else ()) if x in objects]
                    if any(_fin(finishable(x), i, x) for x in owners):
                        continue
                    if ended[i]:
                        continue
                by_cls.setdefault(cls(p, states[i][p]), []).append(i * n + k)
            for c_, nodes in by_cls.items():
                for q, w, where in self.expand(c_, nodes, o):
                    found.append((keys[q], w, min(where), frozenset(where), "value"))
        lines = []
        for key, value, first, where, kind in sorted(found, key=lambda f: (show_key(f[0]), repr(f[1]))):
            lines.append({"kind": kind, "key": key, "value": value, "first": first, "where": where})
        prog_rules = [r for r in model.rules if r.kind == "progress"]
        for r, where in self.progress_lost(prog_rules):
            lines.append({"kind": "progress", "rule": r, "first": min(where), "where": frozenset(where)})
        lines += self.undeclared_ends()
        return self.group(lines)

    def halts(self, nodes, o, obj_pos):
        """For the (state, position) nodes holding a value no state leaves: the nodes where the
        position's object can never change again, or None when the object can change for ever
        while it holds the value (a cycle among those nodes changes it). The nodes are closed
        under steps (the value is never left), so with no such cycle every one of them leads
        to a node where the object has halted."""
        g, fr, keys = self.g, self.fr, self.keys
        states, sym = g.states, g.sym
        n = len(o)
        obj = _owner(keys[o[0]])                          # None: a field of no object, the whole model
        items = orbit(g, obj)
        pg = g.pair_graph(items, lambda q, x: fr.ren(q, x))
        idx = {x: k for k, x in enumerate(items)}
        of = {}                                           # object node -> its position node
        for x in nodes:
            i, k = divmod(x, n)
            of[i * pg.n + idx[_owner(keys[o[k]])]] = x
        succ, moves = {}, set()                           # edges among the nodes; those that change the object
        for u in of:
            i, ko = divmod(u, pg.n)
            si = states[i]
            prow = g.perm[i] if g.perm is not None else None
            mine = obj_pos[items[ko]]
            out = []
            for c, j in enumerate(g.out[i]):
                if j < 0:
                    continue
                p_ = prow[c] if prow is not None else 0
                w = j * pg.n + pg.trans[p_][ko]
                raw = states[j] if p_ == 0 else sym.apply(sym.inv[p_], states[j])
                if any(si[q] != raw[q] for q in mine):
                    moves.add((u, w))
                out.append(w)
            succ[u] = out
        comp = _components(list(of), succ)
        if any(comp[u] == comp.get(w) for u, w in moves):
            return None
        live = pg.reverse_reach([u for u, _ in moves])
        return [of[u] for u in sorted(of) if not live[u]]

    def at_declared_end(self, i, obj, obj_pos) -> bool:
        """Whether at state i the object's life has ended by design: one of its fields holds a
        value m.terminal declares. The whole model (obj None) has ended when a field of no
        object holds one, or when every object with declared ends holds one of them."""
        keys, t, ends = self.keys, self.g.states[i], self.model.terminals

        def holds(q):
            fam = self.field_by_key[keys[q]].family
            return fam in ends and t[q] in ends[fam]
        if obj is not None:
            return any(holds(q) for q in obj_pos[obj])
        if any(holds(q) for q in obj_pos[None] if _owner(keys[q]) is None):
            return True
        lives = {_owner(keys[q]) for q in obj_pos[None]
                 if _owner(keys[q]) is not None and self.field_by_key[keys[q]].family in ends}
        return bool(lives) and all(any(holds(q) for q in obj_pos[x]) for x in lives)

    def lost_steps(self, c_, nodes, o, obj_pos, cls, own=False):
        """For a value no state leaves, at which its object goes on changing for ever: (the
        actions that change the object somewhere but never once it holds the value, the ones
        that still change it there). An action whose every change of the object enters the
        value is left out (the step that sets a one-way flag is not lost). Nothing lost: a
        one-way marker, the object still does all it did (a flag set on the first loan).
        own (a number or flag field): an action whose every change of the object changes this
        field alone and counts it toward the value (_counts_toward) is left out too; it is the
        field's own step (a clock that runs out, a total that stops), and losing it at the
        last value ends nothing else. A step that takes the number away from the value (a
        place coded 0 shelf, 1 loan, 2 repair: give_back 1 -> 0) is no count and is lost."""
        g, keys, states, sym = self.g, self.keys, self.g.states, self.g.sym
        n = len(o)
        held = set(nodes)
        changes, after, entering, counts = set(), set(), {}, {}
        for i, row in enumerate(g.out):
            si = states[i]
            prow = g.perm[i] if g.perm is not None else None
            for c, j in enumerate(row):
                if j < 0:
                    continue
                p_ = prow[c] if prow is not None else 0
                raw = states[j] if p_ == 0 else sym.apply(sym.inv[p_], states[j])
                name = g.calls[c].action.name
                for k, p in enumerate(o):
                    moved = [q for q in obj_pos[_owner(keys[p])] if si[q] != raw[q]]
                    if not moved:
                        continue
                    changes.add(name)
                    if i * n + k in held:
                        after.add(name)
                    enters = cls(p, si[p]) != c_ and cls(p, raw[p]) == c_
                    entering[name] = entering.get(name, True) and enters
                    counts[name] = counts.get(name, True) and moved == [p] and _counts_toward(si[p], raw[p], c_[1])
        return sorted(a for a in changes - after if not entering[a] and not (own and counts[a])), sorted(after)

    def expand(self, c_, nodes, o):
        """The concrete (position, value, unreduced states) of a class seen at pair nodes."""
        fr, g, keys = self.fr, self.g, self.keys
        n = len(o)
        if fr.P == 1:
            p, v = c_
            return [(p, v, [x // n for x in nodes])]
        out = {}
        for x in nodes:
            i, k = divmod(x, n)
            p = o[k]
            v = g.states[i][p]
            for s in range(fr.P):
                q, w = fr.dest(s, p), fr.ren(s, v)
                out.setdefault((q, _typed(w)), (q, w, set()))[2].add(fr.unreduced(i, s))
        return sorted(out.values(), key=lambda e: (e[0], repr(e[1])))

    def progress_lost(self, rules):
        """(rule, unreduced states) for every progress rule some reachable state loses."""
        g, fr = self.g, self.fr
        states = g.states
        N = len(states)
        done = set()
        out = []
        for r in rules:
            if r.name in done:
                continue
            if r.obj is None:
                group, items = [r], [None]
            else:
                items = orbit(g, r.obj)
                group = [x for x in rules if x.base == r.base and x.obj in items]
            for x in group:
                done.add(x.name)
            pg = g.pair_graph(items, lambda q, x: fr.ren(q, x)) if r.obj is not None else None
            n = len(items)
            try:
                goal_nodes = []
                for i in range(N):
                    s = State(zip(self.keys, states[i]))
                    for k, x in enumerate(items):
                        if (r.goal(s) if x is None else r.goal(s, x)):
                            goal_nodes.append(i * n + k)
            except Exception as err:  # model code
                self.model_error(f"progress {r.base!r} raised {type(err).__name__}: {err}", err, r.line)
                continue
            if pg is None:
                ok = bytearray(N)
                stack = list(goal_nodes)
                for s_ in stack:
                    ok[s_] = 1
                while stack:
                    x = stack.pop()
                    for y in g.rev(x):
                        if not ok[y]:
                            ok[y] = 1
                            stack.append(y)
            else:
                ok = pg.reverse_reach(goal_nodes)
            try:
                bad = []
                for i in range(N):
                    s = None
                    for k, x in enumerate(items):
                        if ok[i * n + k]:
                            continue
                        if s is None:
                            s = State(zip(self.keys, states[i]))
                        if (r.when(s) if x is None else r.when(s, x)):
                            bad.append(i * n + k)
            except Exception as err:  # model code
                self.model_error(f"progress {r.base!r} raised {type(err).__name__}: {err}", err, r.line)
                continue
            if not bad:
                continue
            for rule in group:
                where = set()
                for x in bad:
                    i, k = divmod(x, n)
                    item = items[k]
                    if rule.obj is None:
                        where.update(i * fr.P + c for c in fr.all_cosets(i))
                    else:
                        for s in range(fr.P):
                            if fr.ren(s, item) == rule.obj:
                                where.add(fr.unreduced(i, s))
                if where:
                    out.append((rule, where))
        out.sort(key=lambda e: rules.index(e[0]))
        return out

    def label(self, line):
        n = len(line["where"])
        if line["kind"] == "value":
            return (f"{show_key(line['key'])} = {line['value']!r}: other states leave this value, but here it "
                    f"can never change again ({n} state{'s' if n != 1 else ''}, complete search)")
        if line["kind"] == "dead end":
            return (f"{show_key(line['key'])} = {line['value']!r}: no state ever leaves this value, and it is "
                    f"not a declared end ({n} state{'s' if n != 1 else ''}, complete search)")
        who = "the object" if isinstance(line.get("key"), tuple) else "the model"
        if line["kind"] == "end" and line.get("lost"):
            return (f"{show_key(line['key'])} = {line['value']!r}: no state ever leaves this value, {who} "
                    f"can never again {', '.join(line['lost'])} there, and no end is declared "
                    f"({n} state{'s' if n != 1 else ''}, complete search)")
        if line["kind"] == "end":
            return (f"{show_key(line['key'])} = {line['value']!r}: no state ever leaves this value, {who} "
                    f"comes to a halt there, and no end is declared ({n} state{'s' if n != 1 else ''}, "
                    f"complete search)")
        return (f"progress {line['rule'].name!r}: from here it can never be satisfied again "
                f"({n} state{'s' if n != 1 else ''}, complete search)")

    def line_subject(self, line):
        if line["kind"] == "progress":
            return f"progress {line['rule'].base!r}"
        return f"{_subject_key(line['key'])} = {self.subject_value(line['value'])}"

    def group(self, lines) -> list[Finding]:
        """Roots and consequences (port of group_stuck), then one finding per root. Among lines
        stuck in as many states, a counter value is never the root while another value is
        (it is folded under it), nor a flag while a state field's value is: the report is named
        by the object's state (G2); next, a value no state leaves (the cause) comes before a
        value that only stops changing there."""
        P = self.fr.P

        def aside(line):                                   # 2: a counter, 1: a flag, 0: a state field
            if line["kind"] == "progress":
                return 0
            domain = self.field_by_key[line["key"]].domain
            return 2 if _is_counter(domain) else 1 if all(isinstance(v, bool) for v in domain) else 0
        order = sorted(range(len(lines)), key=lambda n: (-len(lines[n]["where"]), aside(lines[n]),
                                                         lines[n]["kind"] not in ("end", "dead end"),
                                                         lines[n]["first"]))
        roots, under = [], {}
        for n in order:
            where = lines[n]["where"]
            host = next((r for r in roots if where <= lines[r]["where"]), None)
            if host is None:
                roots.append(n)
            else:
                under.setdefault(host, []).append(n)
        plen = {}
        for line in lines:
            u = line["first"]
            if u not in plen:
                plen[u] = len(self.g.path_calls(u // P))
        roots.sort(key=lambda n: (plen[lines[n]["first"]], lines[n]["first"]))
        out = []
        for n in roots:
            cons = sorted(under.get(n, []), key=lambda k: self.label(lines[k]))
            out.append(self.stuck_finding(lines[n], [lines[k] for k in cons]))
        return out

    def stuck_finding(self, line, cons) -> Finding:
        """One STUCK conflict: the stuck object's state in its witness, every call that would
        change the object and refuses there (and, later, where a consequence sets in), the
        step that entered it, and the consequences with counter values folded."""
        P = self.fr.P
        calls, state = self.witness(line["first"])
        members = [line] + cons
        sources, notes = set(), []
        for m_ in members:
            sources |= self.stuck_sources(m_, calls)
            notes += [x for x in self.stuck_notes(m_) if x not in notes]
        who, plain = self.object_state(line)
        refused = self.refused_object(line["first"], self.object_positions(line), self.stuck_object(line))
        said = {(r["call"].partition("(")[0], r["reason"], r["source"]) for r in refused}
        shown, folded = [], []
        later = []
        for c in cons:
            if c["kind"] != "progress" and _is_counter(self.field_by_key[c["key"]].domain):
                folded.append(c)
                continue
            shown.append(c)
            if c["kind"] == "progress":
                continue
            for r in self.refused_object(c["first"], self.object_positions(c), self.stuck_object(c)):
                k = (r["call"].partition("(")[0], r["reason"], r["source"])
                if k not in said:
                    said.add(k)
                    later.append(dict(r, at=self.line_subject(c)))
        sources |= {r["source"] for r in refused + later}     # what the report names refusing is its cause
        subject = self.line_subject(line)
        detail = {
            "stuck": line["kind"], "label": self.label(line), "count": len(line["where"]),
            "consequences": [self.line_subject(c) for c in cons],
            "consequence_labels": [self.label(c) for c in cons],
            "shown_consequences": [self.line_subject(c) for c in shown],
            "folded": {"count": len(folded),
                       "fields": list(dict.fromkeys(_subject_key(c["key"]) for c in folded))},
            "object_state": plain, "refused": refused, "later": later, "entered": self.entered(calls),
            "notes": notes,
            "progress_names": [m_["rule"].name for m_ in members if m_["kind"] == "progress"],
            "states": sorted({u // P for u in line["where"]}),
            "where": sorted(line["where"]),        # unreduced ids i * P + renaming (pictures)
        }
        head = f"{who} stuck with {plain}" if who else f"stuck with {plain}"
        if line["kind"] == "progress":
            text = f"{head}: progress {line['rule'].base!r} can never be satisfied again"
            objects = (str(line["rule"].obj),) if line["rule"].obj is not None else ()
            ln = line["rule"].line
        else:
            if line["kind"] == "value":
                text = f"{head}: {subject} can never change again"
            elif line["kind"] == "dead end":
                text = f"{head}: {subject} is never left, and it is not a declared end"
            else:
                fam = self.field_by_key[line["key"]].family
                if line.get("lost"):
                    kept = line["kept"]
                    how = (f"from here {who or 'the model'} can never again {', '.join(line['lost'])} (only "
                           f"{', '.join(kept)} still change{'s' if len(kept) == 1 else ''} it)")
                    detail.update(lost=list(line["lost"]), kept=list(kept))
                else:
                    how = f"from here nothing{f' of {who}' if who else ''} ever changes again"
                text = (f"{head}: {subject} is never left, and {how}; no end is declared "
                        f"(m.terminal({fam!r}, [{line['value']!r}]) if it ends a life on purpose)")
            objects = _key_objects(line["key"]) + _value_ids(line["value"], self.ids)
            detail["key"] = show_key(line["key"])
            detail["value"] = repr(line["value"])
            ln = self.field_by_key[line["key"]].line
        return make_finding("STUCK", CONFLICT, self.mid, subject, text, objects=objects, sources=sources,
                            path=self.steps(calls), state=state, detail=detail, line=ln)

    def object_positions(self, line):
        """The positions (concrete frame) of the stuck object's fields: the key's object, the
        progress rule's object, or every field that belongs to no object."""
        if line["kind"] == "progress":
            obj = line["rule"].obj
            obj = None if obj is None else (obj,)
        else:
            obj = line["key"][1:] if isinstance(line["key"], tuple) else None
        if obj is None:
            return [p for p, k in enumerate(self.keys) if not isinstance(k, tuple)] or list(range(len(self.keys)))
        return [p for p, k in enumerate(self.keys) if isinstance(k, tuple) and k[1:] == obj]

    def object_state(self, line):
        """(who, its fields at the witness): ("T1", "cond='repair', branch='library'")."""
        P = self.fr.P
        i, cid = divmod(line["first"], P)
        end = self.g.end_state(i, cid if P > 1 else None)
        positions = self.object_positions(line)
        if line["kind"] == "progress":
            who = str(line["rule"].obj) if line["rule"].obj is not None else ""
        else:
            who = ",".join(str(x) for x in line["key"][1:]) if isinstance(line["key"], tuple) else ""
        if not who:
            return "", show_tuple(self.g, end)
        return who, ", ".join(f"{self.keys[q][0]}={end[q]!r}" for q in positions)

    def refused_object(self, u, positions, obj=None):
        """Every call refused at the concrete state u that bears on the stuck object, once per
        action, reason and source, in call order: a call that changes one of its positions
        somewhere, and any other call whose arguments name no object but the stuck one (an
        exit that never works anywhere, such as a repair refused by its own guard, changes
        nothing anywhere and would otherwise go unnamed)."""
        g, fr = self.g, self.fr
        i, cid = divmod(u, fr.P)
        cands = set()
        for q in positions:
            cands |= self.closed_changers(fr.dest(fr.inv(cid), q) if fr.P > 1 else q)
        mine = set(obj or ())
        found = []
        for c in range(len(g.calls)):
            v = g.out[i][c]
            if v > -3:                                # possible here, or dropped by the bound / an error
                continue
            cc = c if fr.P == 1 or cid == 0 else g.sym.call_perm[cid][c]
            named = {x for x in g.calls[cc].args if isinstance(x, str) and x in self.ids}
            if c in cands or named <= mine:
                found.append((cc, g.refusals[-1 - v]))
        out, seen = [], set()
        for cc, r in sorted(found, key=lambda x: x[0]):
            k = (g.calls[cc].action.name, r.reason, r.source)
            if k in seen:
                continue
            seen.add(k)
            out.append({"call": show_step(g.calls[cc].step()), "reason": r.reason, "source": r.source})
        return out

    def stuck_object(self, line):
        """The concrete ids of the stuck object (empty for the fields of no object)."""
        if line["kind"] == "progress":
            return () if line["rule"].obj is None else (line["rule"].obj,)
        key = line["key"]
        return tuple(x for x in key[1:] if isinstance(x, str) and x in self.ids) if isinstance(key, tuple) else ()

    def entered(self, calls):
        """The step that entered the stuck set, with its action's and its marked effects' sources."""
        if not calls:
            return None
        try:
            call, marked = replay(self.g, calls)[-1]
        except ModelError:                            # stuck_sources records it
            return {"call": self.steps(calls)[-1], "sources": []}
        srcs = sorted({s for s in {call.action.source} | marked if s}, key=natural_key)
        return {"call": show_step(call.step()), "sources": srcs}

    def closed_changers(self, p):
        """Calls that change position p somewhere (in p's frame, renamings included)."""
        out = self._closed_changers.get(p)
        if out is None:
            fr = self.fr
            out = set()
            for q in range(fr.P):
                p0 = fr.dest(fr.inv(q), p)                # the position that q maps to p
                for c in self._changers[p0]:
                    out.add(c if q == 0 else self.g.sym.call_perm[q][c])
            self._closed_changers[p] = out
        return out

    def stuck_sources(self, line, calls):
        g, fr = self.g, self.fr
        out = set()
        if calls:                                  # the step that entered the stuck set
            try:
                call, marked = replay(g, calls)[-1]
            except ModelError as err:
                self.errors.append(err)
            else:
                out.add(call.action.source)
                out |= marked
        if line["kind"] == "progress":
            out.add(line["rule"].source)
            return out
        f = self.field_by_key[line["key"]]
        out.add(f.value_sources.get(line["value"], f.source))
        out.add(f.source)
        q = self.pos[line["key"]]
        for u in line["where"]:
            i, cid = divmod(u, fr.P)
            p_rep = fr.dest(fr.inv(cid), q) if fr.P > 1 else q
            for c in self.closed_changers(p_rep):
                v = g.out[i][c]
                if v <= -3:
                    out.add(g.refusals[-1 - v].source)
        return out

    def stuck_notes(self, line):
        if line["kind"] == "progress":
            return self.notes(line["rule"])
        return self.notes(self.field_by_key[line["key"]])

    # -------------------------------------------------------------- NEVER REACHED
    def reach_unreached(self):
        """reach rules no explored state satisfies."""
        g = self.g
        out = []
        for r in self.model.rules:
            if r.kind != "reach":
                continue
            objs = [None] if r.obj is None else orbit(g, r.obj)
            try:
                hit = any((r.pred(State(zip(self.keys, t))) if x is None else r.pred(State(zip(self.keys, t)), x))
                          for t in g.states for x in objs)
            except Exception as err:  # model code
                self.model_error(f"reach {r.base!r} raised {type(err).__name__}: {err}", err, r.line)
                self.reach_raised.add(r.name)
                continue
            if not hit:
                out.append(r)
        return out

    def value_class(self, f, v):
        """(class, why) of an unreached field value: a conflict when the value has a source
        or a declared end or a sourced rule names it; otherwise a model warning."""
        if v in f.value_sources:
            return CONFLICT, f"value source {f.value_sources[v]}"
        if f.family in self.model.terminals and v in self.model.terminals[f.family]:
            return CONFLICT, "declared end"
        tv = _typed(v)
        for r in self.model.rules:
            if r.source is None:
                continue
            consts = self._rule_consts(r)
            if tv in consts and _typed(f.family) in consts:
                return CONFLICT, f"named by {r.kind} {r.base!r}"
        return WARNING, None

    def _rule_consts(self, r):
        cache = self.__dict__.setdefault("_rc", {})
        if r.name not in cache:
            cache[r.name] = _fn_consts([r.pred, r.when, r.goal])
        return cache[r.name]

    def never(self):
        g, model = self.g, self.model
        values = g.reached_values()
        missing = []
        for f in model.fields:
            for v in f.domain:
                if (f.key, v) not in values:
                    missing.append(("value", (f.key, v)))
        missing += [("action", a.name) for a in model.actions if a.name not in g.done_actions]
        missing += [("option", o.name) for o in model.options if o.name not in g.offered]
        reach_missing = self.reach_unreached()
        explained, capped, cut = ({}, [], [])
        if self.explain and (missing or reach_missing):
            explained, capped, cut = self.explanations(missing, reach_missing)
        self.explanations_capped, self.explanations_cut = capped, cut
        out = []
        for item in missing + [("reach", r) for r in reach_missing]:
            out.append(self.never_finding(item, explained, capped, cut))
        return out, reach_missing, explained

    def reached_subjects(self, reach_missing) -> list:
        """The NEVER REACHED subjects of the items this model defines that the explored
        states reach, every instance of them, capped or not: a reaching path is a fact, so
        it disproves a stored NEVER REACHED conflict with that subject. An item the model
        does not define (renamed or removed) is in neither list and decides nothing; a reach
        rule that raised is not reached (it decided nothing)."""
        g, model = self.g, self.model
        values = g.reached_values()
        items = [(("value", (f.key, v)), (f.key, v) in values) for f in model.fields for v in f.domain]
        items += [(("action", a.name), a.name in g.done_actions) for a in model.actions]
        items += [(("option", o.name), o.name in g.offered) for o in model.options]
        items += [(("reach", r), r not in reach_missing and r.name not in self.reach_raised)
                  for r in model.rules if r.kind == "reach"]
        missed = {self.never_subject(item) for item, hit in items if not hit}
        return sorted({self.never_subject(item) for item, hit in items if hit} - missed)

    def never_subject(self, item) -> str:
        kind, what = item
        if kind == "value":
            return f"value {_subject_key(what[0])} = {self.subject_value(what[1])}"
        if kind == "action":
            return f"action {what}"
        if kind == "option":
            return f"option {what!r}"
        return f"reach {what.base!r}"

    def never_finding(self, item, explained, capped, cut=()):
        g, model = self.g, self.model
        kind, what = item
        how = explained.get(self._item_key(item)) if self.explain else None
        setting_srcs, setting_notes = set(), []
        for h in how or []:
            info = model.setting_info.get(h.split("=", 1)[0])
            if info is not None:
                setting_srcs.add(info.source)
                if info.note and info.note not in setting_notes:
                    setting_notes.append(info.note)
        # a variant that reached the item decided it; it is UNKNOWN only for the items it did not reach
        detail = {"item": kind, "explained": how, "capped": [c for c in capped if c not in (how or [])],
                  "cut": [c for c in cut if c not in (how or [])],
                  "explanation_errors": list(self.explanation_errors)}
        if kind == "value":
            key, v = what
            f = self.field_by_key[key]
            cls, why = self.value_class(f, v)
            subject = self.never_subject(item)
            text = f"{_subject_key(key)} = {self.subject_value(v)} is never reached"
            sources = {f.value_sources.get(v, f.source), model.terminal_sources.get(f.family)
                       if why == "declared end" else None}
            if why and why.startswith("named by"):
                rname = why.split("'", 1)[1].rsplit("'", 1)[0]
                sources |= {r.source for r in model.rules if r.base == rname}
            tv = _typed(v)
            for a in model.actions:                   # the actions whose effects would write it
                consts = _fn_consts(_with_helpers(a.fn))
                if tv in consts and _typed(f.family) in consts:
                    sources.add(a.source)
            detail.update(key=show_key(key), value=repr(v), why=why, label=f"value {show_key(key)} = {v!r}")
            notes = self.notes(f) + setting_notes
            objects, line = _key_objects(key), f.line
        elif kind == "action":
            a = model.action_named(what)
            cls = CONFLICT
            subject = self.never_subject(item)
            text = f"action {what} never happens"
            sources = {a.source}
            calls = [c.index for c in g.calls if c.action.name == what]
            for row in g.out:
                for c in calls:
                    v = row[c]
                    if v <= -3:
                        sources.add(g.refusals[-1 - v].source)
            detail.update(label=f"action {what}")
            notes = self.notes(a) + setting_notes
            objects, line = (), a.line
        elif kind == "option":
            o = next(o for o in model.options if o.name == what)
            cls = CONFLICT
            subject = self.never_subject(item)
            text = f"option {what!r} is never offered"
            a = model.action_named(o.action)
            sources = {o.source, a.source if a else None}
            detail.update(label=f"option {what}")
            notes = self.notes(o) + setting_notes
            objects, line = (), o.line
        else:
            r = what
            cls = CONFLICT
            subject = self.never_subject(item)
            text = f"reach {r.base!r}: no reachable state has it"
            sources = {r.source}
            detail.update(label=f"reach {r.name!r}", rule=r.name)
            notes = self.notes(r) + setting_notes
            objects, line = ((str(r.obj),) if r.obj is not None else ()), r.line
        sources |= setting_srcs
        detail["notes"] = notes
        return make_finding("NEVER REACHED", cls, self.mid, subject, text, objects=objects, sources=sources,
                            detail=detail, line=line)

    @staticmethod
    def _item_key(item):
        kind, what = item
        return ("reach", what.name) if kind == "reach" else item

    def variations(self):
        return setting_variations(self.model)

    def explanations(self, missing, reach_missing):
        """For each missing item, the one-setting changes that reach it (port of explain):
        the setting is changed in the live dict, domains keep the shipped values."""
        model = self.model
        found = {self._item_key(m): [] for m in missing}
        found.update({("reach", r.name): [] for r in reach_missing})
        capped, cut = [], []
        targets = {"value": [w for k, w in missing if k == "value"],
                   "action": {w for k, w in missing if k == "action"},
                   "option": {w for k, w in missing if k == "option"},
                   "reach": list(reach_missing)}
        cap = min(self.bounds.max_states, max(20_000, len(self.g.states)))
        for name, value in self.variations():
            old = model.settings[name]
            model.settings[name] = value
            try:
                if model.valid is not None:
                    try:
                        ok = model.valid(model.settings)
                    except Exception as err:  # model code
                        self.model_error(f"valid() raised {type(err).__name__}: {err} with {name}={value!r}", err)
                        continue
                    if not ok:
                        continue
                vg = explore(model, Bounds(cap), check_domains=False, targets=targets, reduce=self.reduce)
            finally:
                model.settings[name] = old
            if vg.cut:                                  # a model error cut the variant's search short
                cut.append(f"{name}={value}")
            elif not vg.complete and not vg.stopped_early:
                capped.append(f"{name}={value}")
            if vg.errors:
                self.explanation_errors.append(f"{name}={value}: {vg.errors[0].text}")
            values = vg.reached_values()
            for item in missing:
                kind, what = item
                hit = (what in values if kind == "value" else what in vg.done_actions if kind == "action"
                       else what in vg.offered)
                if hit:
                    found[item].append(f"{name}={value}")
            for r in reach_missing:
                objs = [None] if r.obj is None else orbit(vg, r.obj)
                try:
                    hit = any((r.pred(State(zip(vg.keys, t))) if x is None else r.pred(State(zip(vg.keys, t)), x))
                              for t in vg.states for x in objs)
                except Exception:  # noqa: BLE001 - the main run reports this rule's errors
                    hit = False
                if hit:
                    found[("reach", r.name)].append(f"{name}={value}")
        return found, capped, cut

    # -------------------------------------------------------------- BROKEN, CONTRADICTION
    def broken(self) -> list[Finding]:
        g, model = self.g, self.model
        rules = {r.name: r for r in model.rules}
        out = []
        for name, (i, c) in sorted(g.broken.items(), key=lambda x: x[1][0]):
            r = rules[name]
            calls = g.path_calls(i, c)
            state = show_tuple(g, g.end_state(i))
            sources = {r.source}
            try:
                steps = replay(g, calls)
            except ModelError as err:
                self.errors.append(err)
                steps = []
            for call, marked in steps:
                sources.add(call.action.source)
                sources |= marked
            subject = f"{r.kind} {r.base!r}"
            out.append(make_finding("BROKEN", CONFLICT, self.mid, subject, f"{subject} is broken by an order of steps",
                                    sources=sources, path=self.steps(calls), state=state,
                                    detail={"rule": r.kind, "name": name, "notes": self.notes(r),
                                            "states": [i]}, line=r.line))
        return out

    def contradictions(self) -> list[Finding]:
        g, fr = self.g, self.fr
        out = []
        for name, (i, k, r) in sorted(g.contra.items(), key=lambda x: x[1][0]):
            o, args = g.option_calls[k]
            rho = g.rho(i)
            a = self.model.action_named(o.action)
            named = dict(zip(o.params, args))
            cargs = tuple(fr.ren(rho, named[p]) for p in a.params)
            step = show_step((a.name, a.params, cargs))
            ref = g.refusals[r]
            calls = g.path_calls(i)
            subject = f"option {name!r}"
            out.append(make_finding(
                "CONTRADICTION", CONFLICT, self.mid, subject,
                f"option {name!r} is offered, but {step} refuses: {ref.reason!r}",
                objects=tuple(str(x) for x in cargs if x in self.ids), sources={o.source, ref.source},
                path=self.steps(calls), state=show_tuple(g, g.end_state(i)),
                detail={"option": name, "call": step, "reason": ref.reason, "refusal_source": ref.source,
                        "action_source": a.source if a else None, "notes": self.notes(o), "states": [i]},
                line=o.line))
        return out

    # -------------------------------------------------------------- warnings, errors
    def undeclared_ends(self):
        """G8: the STUCK lines of the values no state leaves, in a field no m.terminal declares
        ends for, where the object (the whole model, for a field of no object) comes to a halt
        or can never again take a step it took before (only a side flag still toggles). They
        are grouped with the other STUCK lines: a counter that stops where the object halts
        (a repair count, a clamped wait) is folded under the value that names its state, and
        one dead end is one finding."""
        lines = []
        for c_, nodes, o in self.frozen_ends:
            for q, w, where in self.expand(c_, nodes, o):
                lines.append({"kind": "end", "key": self.keys[q], "value": w, "first": min(where),
                              "where": frozenset(where)})
        for c_, nodes, o, lost, kept in self.narrowed:
            for q, w, where in self.expand(c_, nodes, o):
                lines.append({"kind": "end", "key": self.keys[q], "value": w, "first": min(where),
                              "where": frozenset(where), "lost": lost, "kept": kept})
        return lines

    def settings_warning(self):
        model = self.model
        literal = [n for n, s in model.setting_info.items() if s.origin == "model only"]
        if not (model.covers and literal and model.config is None):
            return []
        names = ", ".join(f"{n}={model.settings[n]!r}" for n in literal)
        return [make_finding("SETTINGS", WARNING, self.mid, "settings are not imported from the code",
                             f"settings are not imported from the code: {names} are the model's own values; "
                             f"give the model config= to read them from the code", detail={"settings": literal},
                             line=model.line)]

    def error_findings(self):
        g = self.g
        out = []
        for e in list(g.errors) + self.errors:
            path, state = (), ""
            if e.at is not None:
                i, c = e.at
                calls = g.path_calls(i, c)
                path, state = self.steps(calls), show_tuple(g, g.end_state(i))
            subject = f"{e.where()}: {e.text}" if e.where() else e.text
            out.append(make_finding("MODEL ERROR", ERROR_CLS, self.mid, subject, e.text, path=path, state=state,
                                    detail={"file": e.file}, line=e.line))
        return out

    # -------------------------------------------------------------- the reach line
    def reach_facts(self, unknown):
        g, model = self.g, self.model
        settings = [{"name": n, "value": repr(s.value), "origin": s.origin, "where": s.where, "source": s.source}
                    for n, s in model.setting_info.items()]
        return {
            "model": self.mid, "name": model.name, "complete": g.complete, "states": len(g.states),
            "capped": g.bounded, "cut": g.cut,
            "steps": g.steps, "max_states": self.bounds.max_states,
            "symmetry": list(g.sym.kinds) if g.sym is not None else [],
            "symmetry_doubt": model.__dict__.get("_symmetry_doubt"),
            "kinds": list(model.kinds),
            "settings": settings, "concurrency": concurrency(model),
            "ends": [[n, [repr(v) for v in vs], d] for n, vs, d in getattr(self, "terminal", [])],
            "world_can_end": bool(getattr(self, "world_can_end", False)),
            "note": model.note, "unknown": list(unknown),
            "explanations_capped": list(getattr(self, "explanations_capped", [])),
            "explanations_cut": list(getattr(self, "explanations_cut", [])),
            "explanation_errors": list(self.explanation_errors),
        }


def _components(nodes, succ) -> dict:
    """Strongly connected components (iterative Tarjan): node -> component number."""
    index, low, comp, on, stack = {}, {}, {}, set(), []
    counter = 0
    for root in nodes:
        if root in index:
            continue
        work = [(root, iter(succ.get(root, ())))]
        index[root] = low[root] = counter
        counter += 1
        stack.append(root)
        on.add(root)
        while work:
            v, it = work[-1]
            advanced = False
            for w in it:
                if w not in succ:
                    continue
                if w not in index:
                    index[w] = low[w] = counter
                    counter += 1
                    stack.append(w)
                    on.add(w)
                    work.append((w, iter(succ.get(w, ()))))
                    advanced = True
                    break
                if w in on:
                    low[v] = min(low[v], index[w])
            if advanced:
                continue
            work.pop()
            if work:
                low[work[-1][0]] = min(low[work[-1][0]], low[v])
            if low[v] == index[v]:
                while True:
                    w = stack.pop()
                    on.discard(w)
                    comp[w] = index[v]
                    if w == v:
                        break
    return comp


def _counts_toward(a, b, end) -> bool:
    """Whether a step of a number from a to b counts toward end without passing it (a clock
    that runs out, a total that stops, a count down to 0)."""
    if not all(isinstance(x, (int, float)) for x in (a, b, end)):    # bool is an int
        return False
    return a < b <= end or a > b >= end


def _is_counter(domain) -> bool:
    """A numeric field (no bool): its stuck values are folded in a report."""
    return all(isinstance(v, int) and not isinstance(v, bool) for v in domain)


def _has(v, ids):
    t = type(v)
    if t is str:
        return v in ids
    if t is tuple or t is frozenset:
        return any(_has(x, ids) for x in v)
    return False


def _value_ids(v, ids):
    t = type(v)
    if t is str:
        return (v,) if v in ids else ()
    if t is tuple or t is frozenset:
        return tuple(x for y in v for x in _value_ids(y, ids))
    return ()


def _fin(fin, i, obj):
    pg, idx, marks = fin
    return bool(marks[i * pg.n + idx[obj]])


def concurrency(model: Model) -> list[str]:
    """Where the covered code is concurrent (the model checks one order of steps)."""
    if model.root is None:
        return []
    out = []
    seen = set()
    for entry in model.covers:
        file = entry.partition(":")[0]
        if file in seen:
            continue
        seen.add(file)
        path = Path(model.root) / file
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        hits = []
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef):
                hits.append((node.lineno, "has async def"))
            elif isinstance(node, ast.Await):
                hits.append((node.lineno, "awaits"))
            elif isinstance(node, ast.Import):
                for a in node.names:
                    if a.name in _CONCURRENCY or a.name.split(".")[0] in _CONCURRENCY:
                        hits.append((node.lineno, f"imports {a.name}"))
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                if node.module in _CONCURRENCY or node.module.split(".")[0] in _CONCURRENCY:
                    hits.append((node.lineno, f"imports {node.module}"))
        if hits:
            line, what = min(hits)
            out.append(f"{file}:{line} {what}")
    return out


def explanation_text(detail: dict) -> str | None:
    """The one-setting explanation of a NEVER REACHED item as one phrase (None when none was
    tried): the changes that reach it, and the changes whose search could not decide it
    (capped, or cut short by a model error). With an undecided change nothing is "only"
    and nothing is "no": "no complete one-setting change reaches it; undecided: n=60
    (capped)", the same form as the never-taken line warning."""
    how = detail.get("explained")
    if how is None:
        return None
    undecided = [f"{c} (capped)" for c in detail.get("capped") or []] + \
                [f"{c} (cut short by a model error)" for c in detail.get("cut") or []]
    if how:
        text = f"reached {'with' if undecided else 'only with'} {', '.join(how)}"
    else:
        text = "no complete one-setting change reaches it" if undecided else "no one-setting change reaches it"
    return text + (f"; undecided: {', '.join(undecided)}" if undecided else "")


def reach_line(reach: dict) -> str:
    """One line per model: completeness, renaming, settings and their origin, concurrency."""
    if reach["complete"]:
        head = f"complete, {_plural(reach['states'], 'state')}"
    else:
        how = (f"CUT SHORT by {_plural(reach['cut'], 'model error')}" if reach.get("cut")
               else f"CAPPED at {reach['max_states']:,} states")
        head = f"{how}: UNKNOWN for {', '.join(reach['unknown']) or 'nothing'}"
    if reach["symmetry"]:
        head += f" ({', '.join(k + 's' for k in reach['symmetry'])} explored up to renaming)"
    elif reach.get("symmetry_doubt"):
        head += (f" ({', '.join(k + 's' for k in reach['kinds'])} not explored up to renaming (in doubt: "
                 f"{reach['symmetry_doubt']}); every renaming explored)")
    parts = [head]
    if reach["settings"]:
        shown = []
        for s in reach["settings"]:
            origin = s["where"] if s["origin"] == "code" else "model only"
            shown.append(f"{s['name']}={s['value']} ({origin})")
        parts.append("settings " + ", ".join(shown))
    if reach["concurrency"]:
        parts.append(f"concurrency not checked ({'; '.join(reach['concurrency'])})")
    return f"{reach['model']}: " + "; ".join(parts)


def check_model(loaded: Loaded, bounds: Bounds = Bounds(), *, explain: bool = True, reduce: bool = True,
                progress=None) -> Report:
    """Explore one loaded model and run every prepared check on it."""
    return _Run(loaded, bounds, explain, reduce, progress).run()


def _on(f: Finding) -> str:
    return f.subject + (f" on {', '.join(f.objects)}" if f.objects else "")


def verify_symmetry(loaded: Loaded, bounds: Bounds, reduced: Report, *, explain: bool = True) -> dict:
    """`check --full`: explore a symmetric model again without reduction and compare the
    fingerprints (explain= as in the reduced run). A difference is a model error; a capped
    unreduced run verifies nothing."""
    if reduced.graph.sym is None:
        doubt = loaded.model.__dict__.get("_symmetry_doubt")
        text = f"not reduced, so nothing to verify (in doubt: {doubt})" if doubt else "no interchangeable objects declared"
        return {"verified": None, "text": text, "finding": None}
    plain = check_model(loaded, bounds, explain=explain, reduce=False)
    if not plain.graph.complete:
        return {"verified": None, "text": "symmetry not verified (unreduced search capped)", "finding": None}
    a = {f.id: f for f in reduced.findings}
    b = {f.id: f for f in plain.findings}
    # a finding on other objects is another finding: under renaming every object has it or none
    only_reduced = sorted(i for i in a if i not in b or b[i].objects != a[i].objects)
    only_plain = sorted(i for i in b if i not in a or a[i].objects != b[i].objects)
    if not only_reduced and not only_plain:
        return {"verified": True, "text": f"symmetry verified ({len(plain.graph.states):,} states unreduced)",
                "finding": None}
    names = list(dict.fromkeys([_on(a[i]) for i in only_reduced] + [_on(b[i]) for i in only_plain]))
    model = loaded.model
    text = ("the objects are not interchangeable: exploring without renaming gives other findings ("
            + "; ".join(names) + "); write the model symmetrically or use a plain list")
    finding = make_finding("MODEL ERROR", ERROR_CLS, model.id or model.name, "objects are not interchangeable",
                           text, detail={"only_reduced": only_reduced, "only_unreduced": only_plain},
                           line=model.line)
    return {"verified": False, "text": text, "finding": finding}


# ---------------------------------------------------------------------- replaying a stored conflict
REPLAYED, GONE, UNDECIDED = "reproduces", "gone", "undecided"


def replay_spec(f: Finding) -> dict | None:
    """What conflicts.json keeps to replay a conflict on a later model: its kind's own
    condition at the end of its shrunk path (None: a conflict no path shows)."""
    d = f.detail
    if f.kind == "STUCK":
        if d.get("stuck") == "progress":
            return {"stuck": "progress", "rule": (d.get("progress_names") or [None])[0]}
        return {"stuck": d.get("stuck"), "key": d.get("key"), "value": d.get("value")}
    if f.kind == "BROKEN":
        return {"rule": d.get("name"), "kind": d.get("rule")}
    if f.kind == "CONTRADICTION":
        return {"option": d.get("option"), "call": d.get("call")}
    return None


def replay_conflict(model: Model, entry: dict, bounds: Bounds) -> tuple[str, str]:
    """Run a stored conflict's shrunk path on the model as it is now and test the conflict's
    own condition where it ends: (REPLAYED | GONE | UNDECIDED, why). GONE needs evidence: a
    step refused now, or the condition no longer holding where the path ends. A call, field,
    rule or option the model no longer has under its stored name decides nothing (a rename
    is no evidence), nor does model code that raises. A STUCK conflict is tested on every
    state reachable from there, so a capped search there decides nothing."""
    spec = entry.get("replay")
    keys = tuple(f.key for f in model.fields)
    calls = {show_step(c.step()): c for c in model.calls()}
    t = tuple(f.init for f in model.fields)
    before, last = t, None
    for n, step in enumerate(entry.get("path", []), 1):
        call = calls.get(step)
        if call is None:
            return UNDECIDED, f"step {n} {step} is no call of the model now"
        w = State(zip(keys, t))
        try:
            call.action.fn(w, *call.args)
        except Refused as why:
            return GONE, f"step {n} {step} is refused now: {why.reason!r}"
        except Exception as err:  # model code: the core part reports it as a model error
            return UNDECIDED, f"step {n} {step} raises {type(err).__name__} now"
        if len(w) != len(keys):
            return UNDECIDED, f"step {n} {step} writes an unknown field now"
        before, last, t = t, call, tuple(w[k] for k in keys)
    s = State(zip(keys, t))
    try:
        if "stuck" in spec:
            return _replay_stuck(model, spec, t, keys, bounds)
        if "option" in spec:
            return _replay_contradiction(model, spec, s, calls)
        return _replay_broken(model, spec, State(zip(keys, before)), s, last)
    except Exception as err:  # model code (a rule or an option): the core part reports it
        return UNDECIDED, f"replaying raised {type(err).__name__}: {err}"


def _replay_stuck(model, spec, t, keys, bounds):
    g = explore(model, bounds, start=t, reduce=False)
    if spec["stuck"] == "progress":
        rule = next((r for r in model.rules if r.kind == "progress" and r.name == spec["rule"]), None)
        if rule is None:
            return UNDECIDED, f"progress {spec['rule']!r} is no rule of the model now"
        hit = any((rule.goal(State(zip(keys, x))) if rule.obj is None else rule.goal(State(zip(keys, x)), rule.obj))
                  for x in g.states)
        if hit:
            return GONE, f"from where its path ends, progress {spec['rule']!r} can be satisfied again"
    else:
        pos = next((p for p, k in enumerate(keys) if show_key(k) == spec["key"]), None)
        if pos is None:
            return UNDECIDED, f"{spec['key']} is no field of the model now"
        if repr(t[pos]) != spec["value"]:
            return GONE, f"its path ends with {spec['key']}={t[pos]!r} now, not {spec['value']}"
        moved = next((x for x in g.states if x[pos] != t[pos]), None)
        if moved is not None:
            return GONE, f"from where its path ends, {spec['key']} can change again (to {moved[pos]!r})"
    if not g.complete:
        return UNDECIDED, f"the search from where its path ends is {g.unfinished()}"
    return REPLAYED, "its stored path still reproduces it"


def _replay_contradiction(model, spec, s, calls):
    option = next((o for o in model.options if o.name == spec["option"]), None)
    call = calls.get(spec["call"])
    if option is None or call is None:
        return UNDECIDED, f"option {spec['option']!r} or {spec['call']} is no longer in the model"
    named = dict(zip(call.action.params, call.args))
    if not option.offered(s, *[named[p] for p in option.params]):
        return GONE, f"where its path ends, option {spec['option']!r} is not offered now"
    try:
        call.action.fn(State(s), *call.args)
    except Refused:
        return REPLAYED, "its stored path still reproduces it"
    return GONE, f"where its path ends, {spec['call']} works now"


def _replay_broken(model, spec, before, after, last):
    rule = next((r for r in model.rules if r.name == spec["rule"]), None)
    if rule is None:
        return UNDECIDED, f"rule {spec['rule']!r} is no rule of the model now"
    if rule.kind == "always":
        ok = rule.pred(after)
    elif last is None:
        return UNDECIDED, "its path is empty"
    elif rule.kind == "only_when":
        ok = last.action.name != rule.action or rule.pred(before, *last.args)
    elif rule.action == "*":
        ok = rule.pred(before, after, last.action.name, last.args)
    else:
        ok = last.action.name != rule.action or rule.pred(before, after, *last.args)
    if ok:
        return GONE, f"its stored path no longer breaks {rule.kind} {rule.base!r}"
    return REPLAYED, "its stored path still reproduces it"
