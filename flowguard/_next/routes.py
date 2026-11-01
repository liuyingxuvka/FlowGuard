"""M15 in the model (FG-813): one route per function.

Every call runs once more in every explored state, with the model's own lines traced,
and the calls are compared with each other. Port of the prototype's branch check (v3) on
the core's `Graph` (no second exploration engine):

  DUPLICATE ROUTE       two calls with the same enabled states and the same successors   conflict
  SUBSUMED ACTION       every change a call makes, another call makes from the same state  conflict
  FALLBACK ROUTE        two actions never possible together that make the same change   conflict
  STATUS-ONLY FALLBACK  the same, on the status field only                               warning
  SAME-RESULT BRANCH    an `if` whose forced True and forced False give the same outcome  warning
  NEVER TAKEN           lines of an action or helper that no call runs                   warning
  DEAD GUARD            a need(...) checked in reachable states that never refuses        warning

`m.second_route(a, b, source=, why=)` is the only way to keep a pair of routes: it is then
listed (declared routes), not reported. A capped graph decides nothing: UNKNOWN.

With interchangeable objects the calls run on the representative states only; a pair of
calls matches only if every renamed copy of the pair matches too, so the findings are the
ones the unreduced graph gives.
"""
from __future__ import annotations

import ast
import itertools
import os
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .checks import CONFLICT, ERROR_CLS, WARNING, make_finding, merge, setting_variations
from .explore import BOUND, ERROR, Bounds, Graph, explore, show_step, show_tuple
from .model import Model, ModelError, Refused, State, load_model, natural_key, show_key
from .parts import PartContext, PartResult, part_digest, register

_PKG = __name__.rpartition(".")[0]
_FORCE: dict = {}                      # (file, line) of an if -> forced value, while probing
_CLASS_ORDER = {CONFLICT: 0, WARNING: 1, ERROR_CLS: 2}


def _force(where, value):
    """What a wrapped `if` test evaluates to: itself, unless the probe forces it."""
    return _FORCE.get(where, value)


# ---------------------------------------------------------------------- the load transform
class ForceIfs:
    """Load transform (`load_model(..., transform=ForceIfs(path))`): every `if T:` and
    `a if T else b` of the model file becomes `if __fg_force__((file, line), T):`, which
    changes nothing while nothing is forced. After the load, `ifs` maps (file, line) of
    each wrapped test to what it reads ("state", "argument" or "constant"), its function
    and its text."""

    def __init__(self, path):
        self.file = str(Path(path).resolve())
        self.ifs = {}

    def __call__(self, tree: ast.Module) -> ast.Module:
        _Wrap(self).visit(tree)
        body = tree.body
        at = 0
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                and isinstance(body[0].value.value, str):
            at = 1
        while at < len(body) and isinstance(body[at], ast.ImportFrom) and body[at].module == "__future__":
            at += 1
        imp = ast.ImportFrom(module=f"{_PKG}.routes", names=[ast.alias("_force", "__fg_force__")], level=0)
        body.insert(at, ast.copy_location(imp, body[at] if at < len(body) else tree))
        return tree


class _Wrap(ast.NodeTransformer):
    def __init__(self, owner: ForceIfs):
        self.owner = owner
        self.stack = []                            # (function name, state name, parameter names)

    def visit_FunctionDef(self, node):
        names = [a.arg for a in node.args.args]
        self.stack.append((node.name, names[:1], names[1:]))
        self.generic_visit(node)
        self.stack.pop()
        return node

    def _wrap(self, node, text):
        used = {n.id for n in ast.walk(node.test) if isinstance(n, ast.Name)}
        fname, state, params = self.stack[-1] if self.stack else (None, [], [])
        reads = "state" if used & set(state) else "argument" if used & set(params) else "constant"
        where = (self.owner.file, node.test.lineno)
        self.owner.ifs[where] = {"reads": reads, "function": fname, "test": text}
        call = ast.Call(func=ast.Name("__fg_force__", ast.Load()),
                        args=[ast.Tuple([ast.Constant(where[0]), ast.Constant(where[1])], ast.Load()), node.test],
                        keywords=[])
        node.test = ast.copy_location(call, node.test)
        return node

    def visit_If(self, node):
        text = ast.unparse(node.test)
        self.generic_visit(node)
        return self._wrap(node, text)

    def visit_IfExp(self, node):
        text = ast.unparse(node.test)
        self.generic_visit(node)
        return self._wrap(node, text)


# ---------------------------------------------------------------------- measuring
@dataclass
class Observation:
    """What every call does in every explored state (measured, not judged)."""
    model: Model
    graph: Graph
    ifs: dict                    # the wrapped ifs of the traced files
    files: tuple                 # the files the model's actions are written in (traced)
    outcome: list                # outcome[c][i]: ("ok", raw successor) | ("refused", reason, (file, line)) | ("error", what)
    ran: list                    # ran[c][i]: frozenset of (file, line) the call ran
    errors: frozenset            # (c, i) the graph records as a model error (no step there)


def _call(fn, keys, base, args):
    w = State(zip(keys, base))
    try:
        fn(w, *args)
    except Refused as why:
        return ("refused", str(why.reason), why.where)
    except Exception as err:  # model code: the core part reports it as a model error
        return ("error", type(err).__name__)
    if len(w) != len(keys):
        return ("error", "unknown field")
    return ("ok", tuple(w[k] for k in keys))


def _run_calls(states, keys, calls, files):
    """Every call in every state, tracing the lines of `files` it runs."""
    srcs = set(files)
    current = []
    interned = {}

    def local(frame, event, arg):
        if event == "line":
            current.append((frame.f_code.co_filename, frame.f_lineno))
        return local

    def tracer(frame, event, arg):
        if event == "call" and frame.f_code.co_filename in srcs:
            return local
        return None

    outcome, ran = [], []
    old = sys.gettrace()
    sys.settrace(tracer)
    try:
        for call in calls:
            fn, args = call.action.fn, call.args
            row_o, row_r = [], []
            for base in states:
                del current[:]
                row_o.append(_call(fn, keys, base, args))
                lines = frozenset(current)
                row_r.append(interned.setdefault(lines, lines))
            outcome.append(row_o)
            ran.append(row_r)
    finally:
        sys.settrace(old)
    return outcome, ran


def _action_files(model):
    return tuple(sorted({os.path.abspath(a.fn.__code__.co_filename) for a in model.actions}))


def _rel(model, file):
    if model.root is not None:
        try:
            return Path(file).resolve().relative_to(Path(model.root).resolve()).as_posix()
        except ValueError:
            pass
    return str(file)


def observe(model: Model, graph: Graph, ifs: dict) -> Observation:
    """Run every call in every state of `graph` (explored from `model`) once more."""
    if graph.model is not model:
        raise ValueError("observe() needs the graph explored from this model")
    if not graph.complete:
        raise ValueError("a capped graph decides no route")
    files = _action_files(model)
    outcome, ran = _run_calls(graph.states, graph.keys, graph.calls, files)
    errors = set()
    for i, row in enumerate(graph.out):
        for c, v in enumerate(row):
            o = outcome[c][i]
            if v >= 0:
                same = o[0] == "ok" and o[1] == graph.raw_successor(i, c)
            elif v == -1 - ERROR:
                same = o[0] != "refused"
                errors.add((c, i))
            elif v == -1 - BOUND:
                same = False
            else:
                same = o[0] == "refused" and o[1] == graph.refusals[-1 - v].reason
            if not same:
                call = graph.calls[c]
                raise ModelError(f"{show_step(call.step())} gives another result when run again in the state "
                                 f"{show_tuple(graph, graph.states[i])}: the model does not give the same "
                                 f"result twice", _rel(model, call.action.fn.__code__.co_filename),
                                 call.action.line)
    return Observation(model, graph, {w: v for w, v in ifs.items() if w[0] in files}, files, outcome, ran,
                       frozenset(errors))


# ---------------------------------------------------------------------- renaming
class _Group:
    """The renamings of a symmetric graph acting on calls, states and changes; trivial
    without symmetry. A concrete state is (representative i, renaming q)."""

    def __init__(self, g: Graph):
        self.g, self.sym = g, g.sym
        self.P = g.sym.n if g.sym is not None else 1
        self._stab = {}

    def call(self, p, c):
        return c if p == 0 else self.sym.call_perm[p][c]

    def inv(self, p):
        return 0 if p == 0 else self.sym.inv[p]

    def delta(self, p, d):
        if p == 0:
            return d
        dest, ren = self.sym.dest[p], self.sym.rename
        return frozenset((dest[q], ren(p, old), ren(p, new)) for q, old, new in d)

    def stab(self, i):
        s = self._stab.get(i)
        if s is None:
            s = self.sym.stabilizer(self.g.states[i])
            self._stab[i] = s
        return s

    def coset(self, i, p):
        if self.P == 1:
            return 0
        return min(self.sym.compose(p, h) for h in self.stab(i))

    def cosets(self, i):
        if self.P == 1:
            return (0,)
        return tuple(sorted({self.coset(i, p) for p in range(self.P)}))

    def state(self, i, q):
        return self.g.states[i] if q == 0 else self.sym.apply(q, self.g.states[i])

    def concrete(self, c):
        """(i, q, x) for every concrete state rename(q, states[i]): call c there is call x
        at the representative."""
        for i in range(len(self.g.states)):
            for q in self.cosets(i):
                yield i, q, self.call(self.inv(q), c)


# ---------------------------------------------------------------------- judging
@dataclass
class RouteReport:
    complete: bool
    findings: list               # merged Findings, conflicts first
    declared: list               # declared second routes and what each one keeps
    info: dict                   # measurements (--json only)
    unknown: list = field(default_factory=list)
    raw: list = field(default_factory=list)    # one Finding per call, group, line or guard (before merging)


def check_routes(model: Model, graph: Graph, ifs: dict, *, explain: bool = True) -> RouteReport:
    """The route checks of one model; `model` is loaded with ForceIfs (its `ifs`) and
    `graph` is explored from it. A capped graph gives UNKNOWN."""
    if not graph.complete:
        return RouteReport(False, [], _declared(model, {}), {}, ["routes"])
    return judge(observe(model, graph, ifs), explain=explain)


def _declared(model, kept):
    out = []
    for sr in model.second_routes:
        pair = frozenset(sr.actions)
        out.append({"actions": list(sr.actions), "source": sr.source, "why": sr.why, "line": sr.line,
                    "keeps": kept.get(pair, [])})
    return out


def _describe(keys, delta):
    return ", ".join(f"{show_key(keys[p])}: {old!r} -> {new!r}" for p, old, new in sorted(delta, key=lambda d: d[0]))


def _code_objects(path, action_names):
    """Each function of the file: (name, is an action, def line, its own statement lines)."""
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    funcs = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        body = set()

        def own(stmts):
            for stmt in stmts:
                if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    continue
                if (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant)
                        and isinstance(stmt.value.value, str)):
                    continue
                body.add(stmt.lineno)
                for name in ("body", "orelse", "finalbody"):
                    own(getattr(stmt, name, []) or [])
                for h in getattr(stmt, "handlers", []) or []:
                    own(h.body)
        own(node.body)
        funcs.append((node.name, node.name in action_names, node.lineno, body))
    return funcs


def _need_calls(path):
    """(first line, last line, function, source= literal, code) of every need(...) call."""
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    out = []

    def visit(node, fname):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                visit(child, child.name)
                continue
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Name) and child.func.id == "need":
                src = next((k.value.value for k in child.keywords if k.arg == "source"
                            and isinstance(k.value, ast.Constant)), None)
                out.append((child.lineno, child.end_lineno, fname, src, ast.unparse(child)))
            visit(child, fname)
    visit(tree, None)
    return sorted(out, key=lambda x: (x[0], x[1]))


def _statement_texts(path):
    """line -> the first line of the code of the statement starting there (no comments)."""
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.stmt):
            out.setdefault(node.lineno, ast.unparse(node).split("\n", 1)[0])
    return out


def _lines(obs):
    ran, refused = set(), set()
    for row in obs.ran:
        for lines in row:
            ran |= lines
    for row in obs.outcome:
        for o in row:
            if o[0] == "refused" and o[2]:
                refused.add((os.path.abspath(o[2][0]), o[2][1]))
    return ran, refused


def judge(obs: Observation, *, explain: bool = True, others=()) -> RouteReport:
    """The route findings of one observation. `others`: observations of other models whose
    actions are written in the same files (lines only they run are not NEVER TAKEN)."""
    return _Judge(obs, explain, others).run()


class _Judge:
    def __init__(self, obs, explain, others):
        self.obs, self.explain, self.others = obs, explain, list(others)
        self.model, self.g = obs.model, obs.graph
        self.G = _Group(self.g)
        self.keys = self.g.keys
        self.states = self.g.states
        self.calls = self.g.calls
        self.mid = self.model.id or self.model.name
        self.ids = {i: k for k, idl in self.model.kinds.items() for i in idl}
        self.label = [show_step(c.step()) for c in self.calls]
        self.name = [c.action.name for c in self.calls]
        self.declared = {frozenset(sr.actions): sr for sr in self.model.second_routes}
        self.kept = defaultdict(list)            # declared pair -> kinds it keeps
        self.info = {}
        self.findings = []
        n = len(self.calls)
        self.succ = [{} for _ in range(n)]       # call -> {rep: raw successor}
        self.refused = [{} for _ in range(n)]    # call -> {rep: reason}
        self.rd = [{} for _ in range(n)]         # call -> {change at the representative: [reps]}
        self.dat = [{} for _ in range(n)]        # call -> {rep: change there}
        for c in range(n):
            for i, o in enumerate(obs.outcome[c]):
                if (c, i) in obs.errors:
                    continue
                if o[0] == "ok":
                    self.succ[c][i] = o[1]
                    base = self.states[i]
                    d = frozenset((p, base[p], o[1][p]) for p in range(len(base)) if base[p] != o[1][p])
                    if d:
                        self.rd[c].setdefault(d, []).append(i)
                        self.dat[c][i] = d
                elif o[0] == "refused":
                    self.refused[c][i] = o[1]
        self.en = [frozenset(s) for s in self.succ]
        self._together = {}
        self._deltas = {}

    # ------------------------------------------------------------------ helpers
    def objects(self, calls):
        return sorted({str(x) for c in calls for x in self.calls[c].args if isinstance(x, str) and x in self.ids},
                      key=natural_key)

    def sources(self, calls):
        return {self.calls[c].action.source for c in calls}

    def is_declared(self, pairs, kind):
        """Every pair of action names is a declared second route (then recorded as kept)."""
        pairs = [frozenset(p) for p in pairs]
        if not pairs or any(len(p) < 2 for p in pairs):
            return False
        if all(p in self.declared for p in pairs):
            for p in pairs:
                if kind not in self.kept[p]:
                    self.kept[p].append(kind)
            return True
        return False

    def together(self, a, b):
        """Some concrete state where both calls are possible."""
        k = (a, b)
        r = self._together.get(k)
        if r is None:
            G = self.G
            r = any(self.en[G.call(p, a)] & self.en[G.call(p, b)] for p in range(G.P))
            self._together[k] = r
        return r

    def deltas(self, c):
        """The concrete changes call c makes (ordered set)."""
        d = self._deltas.get(c)
        if d is None:
            G, d = self.G, {}
            for p in range(G.P):
                for delta in self.rd[G.call(G.inv(p), c)]:
                    d.setdefault(G.delta(p, delta), None)
            self._deltas[c] = d
        return d

    def states_of(self, c, ds):
        """The concrete states (i, q) where call c makes one of the changes ds."""
        G, out = self.G, set()
        for D in ds:
            for p in range(G.P):
                x = G.call(G.inv(p), c)
                for i in self.rd[x].get(G.delta(G.inv(p), D), ()):
                    out.add((i, G.coset(i, p)))
        return sorted(out)

    def enabled_count(self, c):
        return sum(1 for i, _, x in self.G.concrete(c) if i in self.succ[x])

    def example(self, c):
        for i, q, x in self.G.concrete(c):
            d = self.dat[x].get(i)
            if d is not None:
                return _describe(self.keys, self.G.delta(q, d))
        return ""

    def path_to(self, s):
        i, q = s
        to = q if self.G.P > 1 else None
        return tuple(show_step(st) for st in self.g.path(i, to=to)), show_tuple(self.g, self.G.state(i, q))

    def add(self, kind, cls, subject, text, *, calls=(), sources=(), path=(), state="", detail=None, line=None):
        self.findings.append(make_finding(kind, cls, self.mid, subject, text, objects=self.objects(calls),
                                          sources=sources, path=path, state=state, detail=detail or {},
                                          line=line))

    # ------------------------------------------------------------------ run
    def run(self) -> RouteReport:
        dup_members = self.duplicates()
        self.subsumed(dup_members)
        groups, seen = self.fallbacks()
        self.status_only(groups, seen)
        self.same_result()
        self.never_taken()
        self.info["routes"] = self.routes_per_action()
        self.info["states"] = len(self.states)
        self.info["calls"] = len(self.calls)
        findings = merge(self.findings)
        findings.sort(key=lambda f: _CLASS_ORDER[f.cls])
        return RouteReport(True, findings, _declared(self.model, self.kept), self.info, [], list(self.findings))

    # ------------------------------------------------------------------ DUPLICATE ROUTE
    def duplicates(self):
        G, n = self.G, len(self.calls)
        sig_id = {}
        sig = [sig_id.setdefault(frozenset(self.succ[c].items()), len(sig_id)) for c in range(n)]
        edge = [any(t != self.states[i] for i, t in self.succ[c].items()) for c in range(n)]
        by_sig = {}
        for c in range(n):
            if any(edge[G.call(p, c)] for p in range(G.P)):
                by_sig.setdefault(tuple(sig[G.call(p, c)] for p in range(G.P)), []).append(c)
        dups = [ns for ns in by_sig.values() if len(ns) > 1]
        groups = {}
        for ns in dups:
            groups.setdefault(tuple(sorted({self.name[c] for c in ns})), []).append(ns)
        for names, gs in groups.items():
            ns = gs[0]
            if len(names) == 1:
                params = self.calls[ns[0]].action.params
                differ = [p for k, p in enumerate(params) if len({self.calls[c].args[k] for g in gs for c in g}) > 1]
                subject = f"{names[0]}({', '.join(differ)})"
                kind_text = "one action, parameter values that change nothing"
            else:
                subject = " == ".join(names)
                kind_text = "different actions"
            if self.is_declared(itertools.combinations(names, 2), "DUPLICATE ROUTE"):
                continue
            count = self.enabled_count(ns[0])
            text = (f"{' == '.join(self.label[c] for c in ns)}  ({kind_text}"
                    + (f"; {len(gs)} such groups" if len(gs) > 1 else "") + ")")
            example = self.example(ns[0])
            members = [c for g in gs for c in g]
            self.add("DUPLICATE ROUTE", CONFLICT, subject, text, calls=members, sources=self.sources(members),
                     detail={"calls": [[self.label[c] for c in g] for g in gs], "made_from": count, "example": example,
                             "report": [text, f"the same successor from each of the same {count} states, "
                                              f"for example: {example}"]},
                     line=self.calls[ns[0]].action.line)
        return {c for ns in dups for c in ns}

    # ------------------------------------------------------------------ SUBSUMED ACTION
    def subsumed(self, dup_members):
        G, n = self.G, len(self.calls)
        made_by = defaultdict(set)
        for c in range(n):
            for i, t in self.succ[c].items():
                if t != self.states[i]:
                    made_by[(i, t)].add(c)
        all_shared, any_shared, edge = [], [], []
        for c in range(n):
            es = [(i, t) for i, t in self.succ[c].items() if t != self.states[i]]
            edge.append(bool(es))
            all_shared.append(all(len(made_by[e]) > 1 for e in es))
            any_shared.append(any(len(made_by[e]) > 1 for e in es))
        overlap = []
        for c in range(n):
            if c in dup_members or not any(edge[G.call(p, c)] for p in range(G.P)):
                continue
            full = all(all_shared[G.call(p, c)] for p in range(G.P))
            if not full and not any(any_shared[G.call(p, c)] for p in range(G.P)):
                continue
            total = shared = 0
            others = Counter()
            for i, q, x in G.concrete(c):
                t = self.succ[x].get(i)
                if t is None or t == self.states[i]:
                    continue
                total += 1
                e = made_by[(i, t)]
                if len(e) > 1:
                    shared += 1
                    for y in e:
                        if y != x:
                            others[G.call(q, y)] += 1
            if not full:
                overlap.append((c, shared, total, others))
                continue
            names = sorted({self.name[o] for o in others})
            if self.is_declared([(self.name[c], o) for o in names], "SUBSUMED ACTION"):
                continue
            cover = ", ".join(f"{self.label[o]} ({k})" for o, k in others.most_common(3))
            text = f"{self.label[c]}: all {total} of its state changes are also made from the same state by: {cover}"
            self.add("SUBSUMED ACTION", CONFLICT, self.name[c], text, calls=[c],
                     sources=self.sources([c]) | self.sources(others),
                     detail={"call": self.label[c], "changes": total,
                             "covered_by": [[self.label[o], k] for o, k in others.most_common()], "report": [text]},
                     line=self.calls[c].action.line)
        self.info["partial_overlaps"] = [
            {"call": self.label[c], "shared": k, "of": tot, "with": [self.label[o] for o, _ in oth.most_common(2)]}
            for c, k, tot, oth in sorted(overlap, key=lambda x: -x[1] / x[2])]

    # ------------------------------------------------------------------ FALLBACK ROUTE
    def separating(self, sa, sb):
        ta = [self.G.state(i, q) for i, q in sa]
        tb = [self.G.state(i, q) for i, q in sb]
        out = []
        for p, key in enumerate(self.keys):
            va = {t[p] for t in ta}
            vb = {t[p] for t in tb}
            if not va & vb:
                out.append((key, sorted(va, key=repr), sorted(vb, key=repr)))
        return out

    def refused_counts(self, x, sy):
        G = self.G
        return Counter(self.refused[G.call(G.inv(q), x)][i] for i, q in sy if i in self.refused[G.call(G.inv(q), x)])

    def fallbacks(self):
        n = len(self.calls)
        by_delta = {}
        for c in range(n):
            for D in self.deltas(c):
                by_delta.setdefault(D, []).append(c)
        pairs = {}
        for D, ns in by_delta.items():
            for a, b in itertools.combinations(ns, 2):
                if not self.together(a, b):
                    pairs.setdefault((a, b), []).append(D)
        fallback, decided = [], []
        for (a, b), ds in pairs.items():
            sa, sb = self.states_of(a, ds), self.states_of(b, ds)
            sep = self.separating(sa, sb)
            if self.name[a] == self.name[b]:
                diff = [(x, y) for x, y in zip(self.calls[a].args, self.calls[b].args) if x != y]
                if any([x] == va and [y] == vb for x, y in diff for _, va, vb in sep):
                    decided.append((a, b))      # a parameter the state decides: bring(who=M1) needs holder=M1
                    continue
            fallback.append((a, b, ds, sa, sb, sep))
        groups = {}
        for item in fallback:
            groups.setdefault((self.name[item[0]], self.name[item[1]]), []).append(item)
        for (na, nb), items in sorted(groups.items(), key=lambda x: -len(x[1])):
            if self.is_declared([(na, nb)], "FALLBACK ROUTE"):
                continue
            a, b, ds, sa, sb, sep = items[0]
            head = (f"{self.label[a]} and {self.label[b]} are never possible in the same state, and make the same "
                    f"change" + (f" ({len(items)} such pairs of calls)" if len(items) > 1 else ""))
            report = [head, f"for example: {_describe(self.keys, ds[0])} (made from {len(sa)} and {len(sb)} states)"]
            refusals = []
            for x, y, sy in ((a, b, sb), (b, a, sa)):
                why = self.refused_counts(x, sy)
                if why:
                    reason, k = why.most_common(1)[0]
                    refusals.append({"refuses": self.label[x], "where": self.label[y], "reason": reason, "states": k,
                                     "of": len(sy)})
                    report.append(f"where {self.label[y]} does it, {self.label[x]} refuses: {reason!r} "
                                  f"({k} of {len(sy)} states)")
            decided_by = [[show_key(k), [repr(v) for v in va], [repr(v) for v in vb]] for k, va, vb in sep[:3]]
            if sep:
                report.append("decided by: " + "; ".join(f"{show_key(k)} {va} vs {vb}" for k, va, vb in sep[:3]))
            path, state = self.path_to(min(sb))
            report.append(f"shortest path to a state where {self.label[b]} is the route ({len(path)} steps): "
                          + (" ; ".join(path) or "(start)"))
            subject = " / ".join(sorted([na, nb]))
            text = head + ("; decided by " + ", ".join(show_key(k) for k, _, _ in sep[:3]) if sep else "")
            members = [c for it in items for c in it[:2]]
            self.add("FALLBACK ROUTE", CONFLICT, subject, text, calls=members, sources=self.sources(members),
                     path=path, state=state,
                     detail={"calls": [self.label[a], self.label[b]], "pairs": len(items),
                             "example": _describe(self.keys, ds[0]), "made_from": [len(sa), len(sb)],
                             "refusals": refusals, "decided_by": decided_by, "route": self.label[b],
                             "report": report},
                     line=self.calls[b].action.line)
        if decided:
            names = Counter(self.name[a] for a, _ in decided)
            self.info["decided_by_the_state"] = {
                "pairs": len(decided), "example": [self.label[decided[0][0]], self.label[decided[0][1]]],
                "per_action": dict(names)}
        seen = {(a, b) for a, b, *_ in fallback} | set(decided)
        return groups, seen

    def status_only(self, groups, seen):
        domains = {f.key: f.domain for f in self.model.fields}
        fam = [k[0] if isinstance(k, tuple) else k for k in self.keys]
        texty = {p for p, k in enumerate(self.keys) if all(isinstance(v, str) or v is None for v in domains[k])
                 and len([v for v in domains[k] if v is not None]) >= 2}
        changers = {}                        # family -> actions changing it, in the order first seen
        for c in range(len(self.calls)):
            for d in self.rd[c]:
                for p, _, _ in sorted(d, key=lambda x: x[0]):
                    if p in texty:
                        changers.setdefault(fam[p], set()).add(self.name[c])
        top = max(changers, key=lambda f: len(changers[f]), default=None)
        self.info["status_field"] = top
        status = {p for p in texty if fam[p] == top}
        by_core = {}
        for c in range(len(self.calls)):
            for D in self.deltas(c):
                core = frozenset(x for x in D if x[0] in status)
                if core:
                    by_core.setdefault(core, {})[c] = None
        tier2 = {}
        for core, per in by_core.items():
            for a, b in itertools.combinations(sorted(per), 2):
                if ((a, b) in seen or self.together(a, b) or self.name[a] == self.name[b]
                        or (self.name[a], self.name[b]) in groups):
                    continue
                tier2.setdefault((self.name[a], self.name[b]), []).append((a, b, core))
        for (na, nb), items in tier2.items():
            if self.is_declared([(na, nb)], "STATUS-ONLY FALLBACK"):
                continue
            a, b, core = items[0]
            extra = sorted({show_key(self.keys[x[0]]) for c in (a, b) for D in self.deltas(c)
                            if frozenset(y for y in D if y[0] in status) == core for x in D if x[0] not in status})
            text = (f"{self.label[a]} and {self.label[b]}: {_describe(self.keys, core)}; they also change: "
                    f"{', '.join(extra) or '-'}" + (f" ({len(items)} such pairs of calls)" if len(items) > 1 else ""))
            members = [c for it in items for c in it[:2]]
            self.add("STATUS-ONLY FALLBACK", WARNING, f"{' / '.join(sorted([na, nb]))} on {top}", text,
                     calls=members, sources=self.sources(members),
                     detail={"calls": [self.label[a], self.label[b]], "status": top,
                             "change": _describe(self.keys, core), "also": extra, "report": [text]},
                     line=self.calls[b].action.line)

    # ------------------------------------------------------------------ SAME-RESULT BRANCH
    def same_result(self):
        obs = self.obs
        ifs = obs.ifs
        at = defaultdict(list)
        for c in range(len(self.calls)):
            for i, lines in enumerate(obs.ran[c]):
                for w in lines:
                    if w in ifs:
                        at[w].append((c, i))
        probed = {}
        for where in sorted(at, key=lambda w: (w[0], w[1])):
            cs = at[where]
            changed = Counter()
            for forced in (True, False):
                _FORCE[where] = forced
                try:
                    for c, i in cs:
                        call = self.calls[c]
                        if _call(call.action.fn, self.keys, self.states[i], call.args) != obs.outcome[c][i]:
                            changed[forced] += 1
                finally:
                    del _FORCE[where]
            probed[where] = (len(cs), changed[True], changed[False], sorted({self.name[c] for c, _ in cs}))
        switches, matter = [], []
        for (f, ln), (k, ct, cf, acts) in sorted(probed.items(), key=lambda x: (x[0][0], x[0][1])):
            info = ifs[(f, ln)]
            if ct or cf:
                matter.append({"line": ln, "changed": ct + cf, "of": 2 * k})
                continue
            text = _line_text(f, ln)
            if info["reads"] == "constant":
                switches.append({"line": ln, "calls": k, "text": text})
                continue
            what = f"line {ln} ({', '.join(acts)}; the condition reads the {info['reads']}): {text}"
            srcs = {a.source for a in self.model.actions if a.name in acts}
            self.add("SAME-RESULT BRANCH", WARNING, f"{info['function']}: if {info['test']}",
                     f"{what}  (forced True and forced False: the same outcome in all {k} calls that check it)",
                     sources=srcs, detail={"file": _rel(self.model, f), "line": ln, "function": info["function"],
                                           "calls": k, "reads": info["reads"],
                                           "report": [what, f"forced True and forced False: the same outcome in all "
                                                            f"{k} calls that check it"]},
                     line=ln)
        self.info["ifs"] = {"checked": len(probed), "in_files": len(ifs), "setting_only": switches,
                            "matter": matter}

    # ------------------------------------------------------------------ NEVER TAKEN, DEAD GUARD
    def never_taken(self):
        obs = self.obs
        ran_here, refused_here = _lines(obs)
        ran_any, refused_any = set(ran_here), set(refused_here)
        for o in self.others:
            r, f = _lines(o)
            ran_any |= r
            refused_any |= f
        action_names = {a.name for a in self.model.actions}
        sources = {a.name: a.source for a in self.model.actions}
        never, elsewhere, dead, dead_elsewhere = [], [], [], []
        for src in obs.files:
            anywhere = {ln for f, ln in ran_any if f == src}
            here = {ln for f, ln in ran_here if f == src}
            for fname, is_action, _, body in _code_objects(src, action_names):
                if not is_action and not body & anywhere:
                    continue                         # a helper no action calls, or a rule
                if body - anywhere:
                    never.append((src, fname, sorted(body - anywhere)))
                if (body & anywhere) - here and (is_action or body & here):
                    elsewhere.append({"function": fname, "lines": sorted((body & anywhere) - here)})
            r_any = {ln for f, ln in refused_any if f == src}
            r_here = {ln for f, ln in refused_here if f == src}
            for lo, hi, fname, nsrc, code in _need_calls(src):
                span = range(lo, hi + 1)
                if any(ln in anywhere for ln in span) and not any(ln in r_any for ln in span):
                    dead.append((src, lo, fname, nsrc, code))
                elif any(ln in here for ln in span) and not any(ln in r_here for ln in span):
                    dead_elsewhere.append(lo)
        how, undecided = ({}, [])
        if never and self.explain:
            how, undecided = self.explain_never({(src, ln) for src, _, ms in never for ln in ms})
        for src, fname, missing in never:
            code = _statement_texts(src)
            texts = [f"{ln}: {_line_text(src, ln)}" for ln in missing]
            runs = sorted({v for ln in missing for v in how.get((src, ln), [])})
            if runs:
                tail = f"runs only with {', '.join(runs)}"
            elif not self.explain:
                tail = "one-setting changes not tried"
            elif undecided:
                tail = f"no complete one-setting change runs it; undecided: {', '.join(undecided)}"
            else:
                tail = "no one-setting change runs it either"
            text = (f"{fname}: line(s) {missing} never run in any reachable state ("
                    + "; ".join(texts[:3]) + f")  ({tail})")
            self.add("NEVER TAKEN", WARNING, f"{fname}: " + "; ".join(code.get(ln, "") for ln in missing[:3]),
                     text, sources={sources.get(fname)},
                     detail={"file": _rel(self.model, src), "function": fname, "lines": missing, "runs_with": runs,
                             "undecided": undecided, "report": [text]},
                     line=missing[0])
        for src, lo, fname, nsrc, code in dead:
            text = _line_text(src, lo)
            self.add("DEAD GUARD", WARNING, f"{fname}: {code}", f"line {lo}: {text}  (checked, never refuses)",
                     sources={nsrc or sources.get(fname)},
                     detail={"file": _rel(self.model, src), "function": fname, "line": lo,
                             "report": [f"line {lo}: {text}  (checked, never refuses)"]},
                     line=lo)
        self.info["lines_only_other_models_run"] = elsewhere
        self.info["guards_refusing_only_in_other_models"] = dead_elsewhere

    def explain_never(self, wanted):
        """The one-setting changes whose complete exploration runs the wanted lines."""
        model, g = self.model, self.g
        found, undecided = defaultdict(list), []
        cap = min(g.max_states, max(20_000, len(g.states)))
        for name, value in setting_variations(model):
            old = model.settings[name]
            model.settings[name] = value
            try:
                if model.valid is not None:
                    try:
                        ok = model.valid(model.settings)
                    except Exception as err:  # model code: the variant is not decided
                        undecided.append(f"{name}={value!r} (valid() raised {type(err).__name__})")
                        continue
                    if not ok:
                        continue
                vg = explore(model, Bounds(cap), check_domains=False, reduce=g.sym is not None)
                if not vg.complete:
                    undecided.append(f"{name}={value!r} (capped)")
                    continue
                _, ran = _run_calls(vg.states, vg.keys, vg.calls, self.obs.files)
            finally:
                model.settings[name] = old
            lines = set()
            for row in ran:
                for ls in row:
                    lines |= ls
            for w in wanted & lines:
                found[w].append(f"{name}={value}")
        return found, undecided

    def routes_per_action(self):
        routes = defaultdict(set)
        for c in range(len(self.calls)):
            for i, o in enumerate(self.obs.outcome[c]):
                if o[0] == "ok":
                    routes[self.name[c]].add(self.obs.ran[c][i])
        return {a.name: len(routes.get(a.name, ())) for a in self.model.actions}


def _line_text(path, line):
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return lines[line - 1].strip() if 0 < line <= len(lines) else ""


# ---------------------------------------------------------------------- the part
def model_error_result(spec, root, err: ModelError, reads) -> PartResult:
    """A part whose model does not load (or misbehaves): the model error, nothing else."""
    subject = f"{err.where()}: {err.text}" if err.where() else err.text
    finding = make_finding("MODEL ERROR", ERROR_CLS, spec.model, subject, err.text, detail={"file": err.file},
                           line=err.line)
    return PartResult(spec.kind, spec.model, part_digest(root, spec, list(reads)), True, [finding.to_json()],
                      {"loaded": False}, sorted(reads), [])


def routes_part(ctx: PartContext) -> PartResult:
    """Load the model with its ifs wrapped, explore it, run the route checks."""
    root, spec = Path(ctx.root), ctx.spec
    max_states = spec.option("max_states", Bounds().max_states)
    force = ForceIfs(ctx.path)
    try:
        loaded = load_model(ctx.path, root, transform=force)
    except ModelError as err:
        return model_error_result(spec, root, err, err.reads)
    graph = explore(loaded.model, Bounds(max_states),
                    progress=lambda d: ctx.progress({"model": spec.model, "kind": spec.kind, **d}))
    try:
        report = check_routes(loaded.model, graph, force.ifs)
    except ModelError as err:
        return model_error_result(spec, root, err, loaded.reads)
    info = {"loaded": True, "complete": report.complete, "unknown": list(report.unknown),
            "declared_routes": report.declared, "measured": report.info, "states": len(graph.states)}
    reads = list(loaded.reads)
    return PartResult(spec.kind, spec.model, part_digest(root, spec, reads), report.complete,
                      [f.to_json() for f in report.findings], info, reads, [])


register("routes", routes_part)
