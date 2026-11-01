"""The prepared checks (M3): STUCK, NEVER REACHED with the one-setting explanation,
BROKEN, CONTRADICTION; their class (conflict / model warning / model error), the
requests behind each (attribution per kind), and the path-free fingerprint (M6)."""
from __future__ import annotations

import ast
import hashlib
import json
from dataclasses import dataclass, field, replace
from pathlib import Path

from .explore import Bounds, Graph, explore, orbit, replay, show_step, show_tuple
from .model import Loaded, Model, ModelError, State, natural_key, show_key

CONFLICT, WARNING, ERROR_CLS = "conflict", "warning", "error"
_CLASS_ORDER = {CONFLICT: 0, WARNING: 1, ERROR_CLS: 2}
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
                "detail": {k: v for k, v in self.detail.items() if k != "states"}, "line": self.line}

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


# ---------------------------------------------------------------------- small helpers
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
    """fn and the plain functions of its own file that it calls by name (transitively)."""
    seen, stack, out = set(), [fn], []
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
        return Report(self.loaded, g, raw, findings, holds, unknown, self.reach_facts(unknown), explained)

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
        ends = {}                                         # family -> (values, declared)
        for oi, o in enumerate(orbits):
            name = family[o[0]]
            if name is None:
                continue
            if name in model.terminals:
                ends[name] = (set(model.terminals[name]), True)
                continue
            never = values[oi] - leaves[oi]
            domain = self.field_by_key[keys[o[0]]].domain
            if never and all(isinstance(v, str) or v is None for v in domain):
                vals = {fr.ren(q, v) for (_, v) in never for q in range(P)}
                old = ends.get(name, (set(), False))[0]
                ends[name] = (old | vals, False)

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
            if name in model.terminals:                   # declared ends: other never-left values
                never = values[oi] - leaves[oi]
                for c_ in never:
                    nodes = [i * n + k for k, p in enumerate(o) for i in range(N) if cls(p, states[i][p]) == c_]
                    for q, w, where in self.expand(c_, nodes, o):
                        if w in model.terminals[name]:
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
                if name not in ends:
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
        return self.group(lines)

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
        return (f"progress {line['rule'].name!r}: from here it can never be satisfied again "
                f"({n} state{'s' if n != 1 else ''}, complete search)")

    def line_subject(self, line):
        if line["kind"] == "progress":
            return f"progress {line['rule'].base!r}"
        return f"{_subject_key(line['key'])} = {self.subject_value(line['value'])}"

    def group(self, lines) -> list[Finding]:
        """Roots and consequences (port of group_stuck), then one finding per root."""
        P = self.fr.P
        order = sorted(range(len(lines)), key=lambda n: (-len(lines[n]["where"]), lines[n]["first"]))
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
            line = lines[n]
            cons = sorted(under.get(n, []), key=lambda k: self.label(lines[k]))
            calls, state = self.witness(line["first"])
            members = [line] + [lines[k] for k in cons]
            sources = set()
            notes = []
            refused = []
            for m_ in members:
                sources |= self.stuck_sources(m_, calls)
                notes += [x for x in self.stuck_notes(m_) if x not in notes]
            if line["kind"] != "progress":
                refused = self.refused_at(line)
            subject = self.line_subject(line)
            detail = {
                "stuck": line["kind"], "label": self.label(line), "count": len(line["where"]),
                "consequences": [self.line_subject(lines[k]) for k in cons],
                "consequence_labels": [self.label(lines[k]) for k in cons],
                "refused": refused, "notes": notes,
                "progress_names": [m_["rule"].name for m_ in members if m_["kind"] == "progress"],
                "states": sorted({u // P for u in line["where"]}),
            }
            if line["kind"] == "progress":
                text = f"progress {line['rule'].base!r} can never be satisfied again"
                objects = (str(line["rule"].obj),) if line["rule"].obj is not None else ()
                ln = line["rule"].line
            else:
                verb = ("can never change again" if line["kind"] == "value"
                        else "is never left, and it is not a declared end")
                text = f"{subject} {verb}"
                objects = _key_objects(line["key"]) + _value_ids(line["value"], self.ids)
                detail["key"] = show_key(line["key"])
                detail["value"] = repr(line["value"])
                ln = self.field_by_key[line["key"]].line
            out.append(make_finding("STUCK", CONFLICT, self.mid, subject, text, objects=objects,
                                    sources=sources, path=self.steps(calls), state=state,
                                    detail=detail, line=ln))
        return out

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
            call, marked = replay(g, calls)[-1]
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

    def refused_at(self, line):
        """What the calls that change the stuck field answer at the witness state."""
        g, fr = self.g, self.fr
        u = line["first"]
        i, cid = divmod(u, fr.P)
        q = self.pos[line["key"]]
        p_rep = fr.dest(fr.inv(cid), q) if fr.P > 1 else q
        shift = cid
        out = []
        for c in sorted(self.closed_changers(p_rep)):
            v = g.out[i][c]
            cc = c if fr.P == 1 or shift == 0 else g.sym.call_perm[shift][c]
            step = show_step(g.calls[cc].step())
            if v <= -3:
                r = g.refusals[-1 - v]
                out.append({"call": step, "reason": r.reason, "source": r.source})
            elif v >= 0:
                out.append({"call": step, "reason": None, "source": None})
        return out

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
        explained, capped = ({}, [])
        if self.explain and (missing or reach_missing):
            explained, capped = self.explanations(missing, reach_missing)
        self.explanations_capped = capped
        out = []
        for item in missing + [("reach", r) for r in reach_missing]:
            out.append(self.never_finding(item, explained, capped))
        return out, reach_missing, explained

    def never_finding(self, item, explained, capped):
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
        detail = {"item": kind, "explained": how, "capped": list(capped)}
        if kind == "value":
            key, v = what
            f = self.field_by_key[key]
            cls, why = self.value_class(f, v)
            subject = f"value {_subject_key(key)} = {self.subject_value(v)}"
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
            subject = f"action {what}"
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
            subject = f"option {what!r}"
            text = f"option {what!r} is never offered"
            a = model.action_named(o.action)
            sources = {o.source, a.source if a else None}
            detail.update(label=f"option {what}")
            notes = self.notes(o) + setting_notes
            objects, line = (), o.line
        else:
            r = what
            cls = CONFLICT
            subject = f"reach {r.base!r}"
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
        out = []
        for name, value in self.model.settings.items():
            info = self.model.setting_info.get(name)
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

    def explanations(self, missing, reach_missing):
        """For each missing item, the one-setting changes that reach it (port of explain):
        the setting is changed in the live dict, domains keep the shipped values."""
        model = self.model
        found = {self._item_key(m): [] for m in missing}
        found.update({("reach", r.name): [] for r in reach_missing})
        capped = []
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
            if not vg.complete and not vg.stopped_early:
                capped.append(f"{name}={value}")
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
        return found, capped

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
            for call, marked in replay(g, calls):
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
            "steps": g.steps, "max_states": self.bounds.max_states,
            "symmetry": list(g.sym.kinds) if g.sym is not None else [],
            "settings": settings, "concurrency": concurrency(model),
            "ends": [[n, [repr(v) for v in vs], d] for n, vs, d in getattr(self, "terminal", [])],
            "world_can_end": bool(getattr(self, "world_can_end", False)),
            "note": model.note, "unknown": list(unknown),
            "explanations_capped": list(getattr(self, "explanations_capped", [])),
        }


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


def reach_line(reach: dict) -> str:
    """One line per model: completeness, renaming, settings and their origin, concurrency."""
    if reach["complete"]:
        head = f"complete, {_plural(reach['states'], 'state')}"
    else:
        head = (f"CAPPED at {reach['max_states']:,} states: UNKNOWN for "
                f"{', '.join(reach['unknown']) or 'nothing'}")
    if reach["symmetry"]:
        head += f" ({', '.join(k + 's' for k in reach['symmetry'])} explored up to renaming)"
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


def verify_symmetry(loaded: Loaded, bounds: Bounds, reduced: Report, *, explain: bool = True) -> dict:
    """`check --full`: explore a symmetric model again without reduction and compare the
    fingerprints (explain= as in the reduced run). A difference is a model error; a capped
    unreduced run verifies nothing."""
    if reduced.graph.sym is None:
        return {"verified": None, "text": "no interchangeable objects declared", "finding": None}
    plain = check_model(loaded, bounds, explain=explain, reduce=False)
    if not plain.graph.complete:
        return {"verified": None, "text": "symmetry not verified (unreduced search capped)", "finding": None}
    a = {f.id: f for f in reduced.findings}
    b = {f.id: f for f in plain.findings}
    only_reduced = sorted(set(a) - set(b))
    only_plain = sorted(set(b) - set(a))
    if not only_reduced and not only_plain:
        return {"verified": True, "text": f"symmetry verified ({len(plain.graph.states):,} states unreduced)",
                "finding": None}
    names = [a[i].subject for i in only_reduced] + [b[i].subject for i in only_plain]
    model = loaded.model
    text = ("the objects are not interchangeable: exploring without renaming gives other findings ("
            + "; ".join(names) + "); write the model symmetrically or use a plain list")
    finding = make_finding("MODEL ERROR", ERROR_CLS, model.id or model.name, "objects are not interchangeable",
                           text, detail={"only_reduced": only_reduced, "only_unreduced": only_plain},
                           line=model.line)
    return {"verified": False, "text": text, "finding": finding}
