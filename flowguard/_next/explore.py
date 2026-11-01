"""Breadth-first state-graph search (a port of the prototype's `explore`), symmetry
reduction over declared object ids, the state bound, and path replay."""
from __future__ import annotations

import itertools
import os
import time
from array import array
from dataclasses import dataclass
from operator import itemgetter
from pathlib import Path

from .model import Model, ModelError, RecordingState, Refused, State, show_key

BOUND = 0          # refusals[0]: the step was dropped by the state bound
ERROR = 1          # refusals[1]: the step raised a model error
_MAX_ERRORS = 20
_PKG_DIR = os.path.dirname(os.path.abspath(__file__))


@dataclass(frozen=True)
class Bounds:
    max_states: int = 200_000


@dataclass(frozen=True)
class Refusal:
    reason: str
    source: str | None
    file: str | None
    line: int | None


def show_step(step) -> str:
    name, params, args = step
    return f"{name}({', '.join(f'{p}={a!r}' for p, a in zip(params, args))})"


def _ren(v, mp):
    t = type(v)
    if t is str:
        return mp.get(v, v)
    if t is tuple:
        return tuple(_ren(x, mp) for x in v)
    if t is frozenset:
        return frozenset(_ren(x, mp) for x in v)
    return v


def _has_id(v, ids):
    t = type(v)
    if t is str:
        return v in ids
    if t is tuple or t is frozenset:
        return any(_has_id(x, ids) for x in v)
    return False


def _ren_key(key, mp):
    if isinstance(key, tuple):
        return (key[0],) + tuple(_ren(x, mp) for x in key[1:])
    return key


def _order(v):
    return (type(v).__name__, repr(v))


class Symmetry:
    """The renaming group of the declared object ids (m.objects), acting on states."""

    @staticmethod
    def of(model: Model) -> "Symmetry | None":
        cached = model.__dict__.get("_symmetry", False)
        if cached is not False:
            return cached
        sym = Symmetry(model) if model.kinds else None
        if sym is not None and sym.n == 1:
            sym = None
        model.__dict__["_symmetry"] = sym
        return sym

    def __init__(self, model: Model):
        keys = [f.key for f in model.fields]
        width = len(keys)
        all_ids = {i for idl in model.kinds.values() for i in idl}
        where = model.path

        def err(text, line=None):
            from .model import _rel
            return ModelError(text, _rel(where) if where else None, line)

        def mentions(kind_ids):
            if any(_has_id(k, kind_ids) for k in keys):
                return True
            if any(_has_id(v, kind_ids) for f in model.fields for v in f.domain):
                return True
            return any(_has_id(v, kind_ids) for a in model.actions for d in a.domains for v in d)
        self.kinds = [k for k, idl in model.kinds.items() if mentions(set(idl))]
        self.ids = [i for k in self.kinds for i in model.kinds[k]]
        per_kind = [list(itertools.permutations(model.kinds[k])) for k in self.kinds]
        self.maps = []
        for combo in itertools.product(*per_kind):
            mp = {}
            for k, images in zip(self.kinds, combo):
                mp.update(zip(model.kinds[k], images))
            self.maps.append(mp)
        self.n = len(self.maps)
        self.ident = tuple(self.ids)
        self.code = {tuple(mp[i] for i in self.ids): p for p, mp in enumerate(self.maps)}
        pos = {k: p for p, k in enumerate(keys)}
        self.dest = []
        for mp in self.maps:
            d = array("l", [0]) * width
            for p, k in enumerate(keys):
                q = pos.get(_ren_key(k, mp))
                if q is None:
                    raise err(f"field {show_key(k)} has no counterpart {show_key(_ren_key(k, mp))}: "
                              f"declare fields over every id of a kind (over=)")
                d[p] = q
            self.dest.append(d)
        self.src = []
        for d in self.dest:
            s = array("l", [0]) * width
            for p in range(width):
                s[d[p]] = p
            self.src.append(s)
        self._getters = [itemgetter(*s) if width > 1 else (lambda t, _i=s[0]: (t[_i],)) for s in self.src]
        renames = any(_has_id(v, all_ids) for f in model.fields for v in f.domain)
        self.value_ren = [renames and p != 0 for p in range(self.n)]
        self.inv = [self.code[tuple(next(x for x in self.ids if mp[x] == i) for i in self.ids)]
                    for mp in self.maps]
        # domains, action and option arguments must be closed under renaming
        dom = {f.key: set(f.domain) for f in model.fields}
        for mp in self.maps[1:]:
            for f in model.fields:
                if {_ren(v, mp) for v in f.domain} != dom[_ren_key(f.key, mp)]:
                    raise err(f"field {show_key(f.key)}: its domain lists only some ids of a kind",
                              f.line)
            for a in model.actions:
                for prm, d in zip(a.params, a.domains):
                    if {_ren(v, mp) for v in d} != set(d):
                        raise err(f"action {a.name}: {prm}= lists only some ids of a kind; give all "
                                  f"of them (or use a plain list)", a.line)
            for o in model.options:
                for prm, d in zip(o.params, o.domains):
                    if {_ren(v, mp) for v in d} != set(d):
                        raise err(f"option {o.name!r}: {prm}= lists only some ids of a kind", o.line)
        init = model.init_state()
        for p in range(1, self.n):
            if self.apply(p, init) != init:
                raise err("the start state tells objects of a kind apart: every object of a kind "
                          "must start alike (or use a plain list)", model.line)
        calls = model.calls()
        cindex = {(c.action.index, c.args): c.index for c in calls}
        self.call_perm = []
        for mp in self.maps:
            row = array("l", [0]) * len(calls)
            for c in calls:
                row[c.index] = cindex[(c.action.index, tuple(_ren(x, mp) for x in c.args))]
            self.call_perm.append(row)
        self._comp = {}
        # ranks: a total order on values by (type name, repr), extended for new values
        seen, vals = set(), []
        for f in model.fields:
            for v in f.domain:
                for mp in self.maps:
                    w = _ren(v, mp)
                    k = (type(w), w)
                    if k not in seen:
                        seen.add(k)
                        vals.append(w)
        vals.sort(key=_order)
        self._rank = {}
        self._rvals = []
        self._rmap = [[] for _ in range(self.n)]
        for v in vals:
            self._new_rank(v)
        for v in vals:
            self._fill_rmap(self._rank[(type(v), v)])

    def _new_rank(self, v):
        r = len(self._rvals)
        self._rank[(type(v), v)] = r
        self._rvals.append(v)
        for rm in self._rmap:
            rm.append(None)
        return r

    def _fill_rmap(self, r):
        v = self._rvals[r]
        for p, mp in enumerate(self.maps):
            w = _ren(v, mp)
            k = (type(w), w)
            q = self._rank.get(k)
            if q is None:
                q = self._new_rank(w)
                self._fill_rmap(q)
            self._rmap[p][r] = q

    def _rank_of(self, v):
        k = (type(v), v)
        r = self._rank.get(k)
        if r is None:
            r = self._new_rank(v)
            self._fill_rmap(r)
        return r

    def apply(self, p, t):
        if p == 0:
            return t
        new = self._getters[p](t)
        if self.value_ren[p]:
            mp = self.maps[p]
            new = tuple(_ren(v, mp) for v in new)
        return new

    def canon(self, t):
        """(representative, p) with apply(p, t) == representative."""
        rk = self._rank
        rt = tuple([rk.get((type(v), v)) for v in t])
        if None in rt:
            rt = tuple(self._rank_of(v) for v in t)
        best, bp = rt, 0
        getters, vr, rmap = self._getters, self.value_ren, self._rmap
        for p in range(1, self.n):
            c = getters[p](rt)
            if vr[p]:
                rm = rmap[p]
                c = tuple([rm[x] for x in c])
            if c < best:
                best, bp = c, p
        return (t, 0) if bp == 0 else (self.apply(bp, t), bp)

    def compose(self, a, b):
        """The index of a after b (x -> a(b(x)))."""
        if a == 0:
            return b
        if b == 0:
            return a
        k = (a, b)
        r = self._comp.get(k)
        if r is None:
            ma, mb = self.maps[a], self.maps[b]
            r = self.code[tuple(ma[mb[i]] for i in self.ids)]
            self._comp[k] = r
        return r

    def rename(self, p, v):
        return v if p == 0 else _ren(v, self.maps[p])

    def stabilizer(self, t):
        return [p for p in range(self.n) if self.apply(p, t) == t]


class PairGraph:
    """Nodes (state i, item k) over one orbit of items (positions or object ids); an edge
    i -> j reached through renaming p links (i, k) to (j, trans[p][k])."""

    def __init__(self, graph: "Graph", items: list, trans: list):
        self.graph = graph
        self.items = list(items)
        self.n = len(items)
        self.trans = trans
        self._rev = None
        self._owner = self

    def node(self, i, k):
        return i * self.n + k

    def rev(self):
        if self._owner is not self:
            return self._owner.rev()
        if self._rev is None:
            g, n = self.graph, self.n
            rev = [[] for _ in range(len(g.states) * n)]
            for i, row in enumerate(g.out):
                prow = g.perm[i] if g.perm is not None else None
                seen = set()
                for c, j in enumerate(row):
                    if j < 0:
                        continue
                    p = prow[c] if prow is not None else 0
                    if (j, p) in seen:
                        continue
                    seen.add((j, p))
                    tr = self.trans[p]
                    for k in range(n):
                        rev[j * n + tr[k]].append(i * n + k)
            self._rev = rev
        return self._rev

    def reverse_reach(self, seeds) -> bytearray:
        rev = self.rev()
        mark = bytearray(len(rev))
        stack = []
        for s in seeds:
            if not mark[s]:
                mark[s] = 1
                stack.append(s)
        while stack:
            x = stack.pop()
            for y in rev[x]:
                if not mark[y]:
                    mark[y] = 1
                    stack.append(y)
        return mark


class Graph:
    """The explored state graph. With symmetry, states are representatives and perm[i][c]
    is the renaming that maps call c's raw successor to states[out[i][c]]."""

    def __init__(self, model, keys, calls, sym):
        self.model = model
        self.keys = keys
        self.calls = calls
        self.sym = sym
        self.states = []
        self.out = []
        self.perm = [] if sym is not None else None
        self.refusals = [Refusal("dropped by the state bound", None, None, None),
                         Refusal("model error", None, None, None)]
        self.parent = []
        self.complete = True
        self.stopped_early = False
        self.errors = []
        self.broken = {}
        self.contra = {}
        self.offered = set()
        self.done_actions = set()
        self.option_calls = []
        self.seconds = 0.0
        self.steps = 0
        self.max_states = 0
        self.init = None
        self._pairs = {}
        self._staterev = None

    # ------------------------------------------------------------------ reading
    def outcome(self, i, c):
        v = self.out[i][c]
        return v if v >= 0 else self.refusals[-1 - v]

    def raw_successor(self, i, c):
        j = self.out[i][c]
        if j < 0:
            raise ValueError(f"call {c} from state {i} has no successor")
        if self.perm is None:
            return self.states[j]
        p = self.perm[i][c]
        return self.states[j] if p == 0 else self.sym.apply(self.sym.inv[p], self.states[j])

    def succ(self, i):
        return {j for j in self.out[i] if j >= 0}

    def rev(self, j):
        if self._staterev is None:
            rev = [[] for _ in self.states]
            for i, row in enumerate(self.out):
                for x in {j for j in row if j >= 0}:
                    rev[x].append(i)
            self._staterev = rev
        return self._staterev[j]

    def _chain(self, i):
        steps = []
        while self.parent[i] is not None:
            prev, c, p = self.parent[i]
            steps.append((c, p))
            i = prev
        steps.reverse()
        return steps

    def rho(self, i):
        """The renaming from states[i] to the concrete state the replayed run ends in."""
        if self.sym is None:
            return 0
        r = 0
        for c, p in self._chain(i):
            r = self.sym.compose(r, self.sym.inv[p])
        return r

    def path_calls(self, i, last=None, to=None):
        """Concrete call indices of a real run from the start to state i (renamings
        replayed); with to=q the run ends in rename(q, states[i]); last is appended."""
        chain = self._chain(i)
        if self.sym is None:
            out = [c for c, _ in chain]
            return out + ([last] if last is not None else [])
        sym = self.sym
        r = 0
        rhos = []
        for c, p in chain:
            rhos.append(r)
            r = sym.compose(r, sym.inv[p])
        shift = 0 if to is None else sym.compose(to, sym.inv[r])
        out = [sym.call_perm[sym.compose(shift, rk)][c] for (c, _), rk in zip(chain, rhos)]
        if last is not None:
            out.append(sym.call_perm[sym.compose(shift, r)][last])
        return out

    def path(self, i, last=None, to=None):
        return [self.calls[c].step() for c in self.path_calls(i, last, to)]

    def end_state(self, i, to=None):
        if self.sym is None:
            return self.states[i]
        return self.sym.apply(to if to is not None else self.rho(i), self.states[i])

    def pair_graph(self, items, act) -> PairGraph:
        """The (state, item) graph for an orbit of items; act(p, item) renames an item."""
        idx = {x: k for k, x in enumerate(items)}
        n = self.sym.n if self.sym is not None else 1
        trans = [array("l", [idx[act(p, x)] for x in items]) for p in range(n)]
        sig = (len(items), tuple(tuple(t) for t in trans))
        pg = PairGraph(self, items, trans)
        first = self._pairs.setdefault(sig, pg)
        pg._owner = first                         # same edges: share the reverse adjacency
        return pg

    def pairs(self, kind) -> PairGraph:
        ids = list(self.model.kinds[kind])
        return self.pair_graph(ids, lambda p, x: self.sym.rename(p, x) if self.sym else x)

    def reached_values(self):
        """(key, value) pairs some reachable state has, closed under renaming."""
        out = set()
        keys = self.keys
        for t in self.states:
            out.update(zip(keys, t))
        if self.sym is not None:
            base = list(out)
            pos = {k: p for p, k in enumerate(keys)}
            for p in range(1, self.sym.n):
                d = self.sym.dest[p]
                for k, v in base:
                    out.add((keys[d[pos[k]]], self.sym.rename(p, v)))
        return out


def show_tuple(graph, t) -> str:
    diff = [f"{show_key(k)}={v!r}" for k, v, v0 in zip(graph.keys, t, graph.init) if v != v0]
    return ", ".join(diff) if diff else "(the start state)"


def show_state(graph, i, to=None) -> str:
    """The concrete state a replayed run to i ends in, as its differences from the start."""
    return show_tuple(graph, graph.end_state(i, to))


def _location(err, root):
    tb = err.__traceback__
    best = None
    while tb is not None:
        fn = os.path.abspath(tb.tb_frame.f_code.co_filename)
        if os.path.dirname(fn) != _PKG_DIR:
            best = (fn, tb.tb_lineno)
        tb = tb.tb_next
    if best is None:
        return None, None
    return _relfile(best[0], root), best[1]


def _relfile(fn, root):
    if fn is None:
        return None
    if root is not None:
        try:
            return Path(fn).resolve().relative_to(root).as_posix()
        except ValueError:
            pass
    return fn


def explore(model: Model, bounds: Bounds = Bounds(), *, targets=None, check_domains=True,
            reduce=True, progress=None, start=None) -> Graph:
    """Every action with every argument in every reachable state, breadth first.
    targets (one-setting explanations): stop as soon as every target is seen. start: begin
    at this state instead of the model's start (the replay of a stored conflict)."""
    t0 = time.perf_counter()
    keys = tuple(f.key for f in model.fields)
    width = len(keys)
    domains = [set(f.domain) for f in model.fields]
    init = tuple(f.init for f in model.fields) if start is None else tuple(start)
    calls = model.calls()
    sym = Symmetry.of(model) if reduce else None
    g = Graph(model, keys, calls, sym)
    g.init = init
    g.max_states = bounds.max_states
    root = model.root
    refusals, rindex = g.refusals, {}
    states, index, parent = [init], {init: 0}, [None]
    g.states, g.parent = states, parent
    out, perms = g.out, g.perm
    errors = g.errors
    broken, contra = g.broken, g.contra
    done_actions, offered = g.done_actions, g.offered
    always = [r for r in model.rules if r.kind == "always"]
    only_when, after, after_any = {}, {}, []
    for r in model.rules:
        if r.kind == "only_when":
            only_when.setdefault(r.action, []).append(r)
        elif r.kind == "after":
            if r.action == "*":
                after_any.append(r)
            else:
                after.setdefault(r.action, []).append(r)
    specs = [(c.action.fn, c.args, c.action.name, c.action.source,
              only_when.get(c.action.name, ()), after.get(c.action.name, ())) for c in calls]
    cindex = {(c.action.name, c.args): c.index for c in calls}
    by_name = {a.name: a for a in model.actions}
    for o in model.options:
        for args in itertools.product(*o.domains):
            g.option_calls.append((o, args))
    opt_specs = []                     # option arguments go to the action by parameter name
    for o, args in g.option_calls:
        act = by_name[o.action]
        named = dict(zip(o.params, args))
        aargs = tuple(named[p] for p in act.params)
        opt_specs.append((o, args, aargs, cindex.get((o.action, aargs)), act))
    ncalls = len(calls)
    zero = array("l", [0]) * ncalls
    max_states = bounds.max_states

    def model_error(text, i, c, err=None):
        if len(errors) < _MAX_ERRORS:
            file, line = _location(err, root) if err is not None else (None, None)
            errors.append(ModelError(text, file, line, at=(i, c)))

    def safe(rule, args, i, c):
        try:
            return bool(rule.pred(*args))
        except Exception as err:  # model code: reported, and the rule is not taken as broken
            model_error(f"rule {rule.base!r} raised {type(err).__name__}: {err}", i, c, err)
            return True

    def refusal(why, action_source):
        source = why.source if why.source is not None else action_source
        key = (str(why.reason), source, why.where[0], why.where[1])
        r = rindex.get(key)
        if r is None:
            r = len(refusals)
            rindex[key] = r
            refusals.append(Refusal(str(why.reason), source, _relfile(why.where[0], root), why.where[1]))
        return r

    seen = set()
    reach_left = []
    if targets is not None:
        reach_left = list(targets.get("reach", ()))

    def note_targets(t):
        if sym is None:
            seen.update(zip(keys, t))
        else:
            for p in range(sym.n):
                seen.update(zip(keys, sym.apply(p, t)))
        if reach_left:
            s = State(zip(keys, t))
            for r in list(reach_left):
                objs = [None] if r.obj is None else _orbit(sym, r.obj)
                try:
                    hit = any((r.pred(s) if x is None else r.pred(s, x)) for x in objs)
                except Exception:  # noqa: BLE001 - errors of reach rules are reported by the main run
                    hit = False
                if hit:
                    reach_left.remove(r)

    def all_targets_seen():
        return (all(t in seen for t in targets["value"]) and set(targets["action"]) <= done_actions
                and set(targets["option"]) <= offered and not reach_left)

    i = counted = 0
    while i < len(states):
        if targets is not None and i % 200 == 0:
            for t in states[counted:]:
                note_targets(t)
            counted = len(states)
            if all_targets_seen():
                g.stopped_early = True
                break
        base = states[i]
        s = State(zip(keys, base))
        for r in always:
            if r.name in broken:
                continue
            try:
                ok = r.pred(s)
            except Exception as err:  # model code
                model_error(f"always {r.base!r} raised {type(err).__name__}: {err}", i, None, err)
                continue
            if not ok:
                broken[r.name] = (i, None)
        row = zero[:]
        prow = zero[:] if sym is not None else None
        for c in range(ncalls):
            fn, args, aname, asrc, ow_rules, af_rules = specs[c]
            w = State(s)
            try:
                fn(w, *args)
            except Refused as why:
                row[c] = -1 - refusal(why, asrc)
                continue
            except Exception as err:  # model code: a model error at (state, call)
                model_error(f"action {show_step(calls[c].step())} raised {type(err).__name__}: {err}",
                            i, c, err)
                row[c] = -1 - ERROR
                continue
            try:
                if len(w) != width:
                    raise KeyError
                t = tuple([w[k] for k in keys])
            except KeyError:
                extra = sorted(set(map(str, w)) ^ set(map(str, keys)))
                model_error(f"action {show_step(calls[c].step())} wrote unknown field(s) {extra}", i, c)
                row[c] = -1 - ERROR
                continue
            if check_domains:
                bad = [(keys[p], t[p]) for p in range(width) if t[p] != base[p] and t[p] not in domains[p]]
                if bad:
                    model_error("effect outside the domain: " + ", ".join(
                        f"{show_step(calls[c].step())} sets {show_key(k)}={v!r}, not in its domain"
                        for k, v in bad), i, c)
                    row[c] = -1 - ERROR
                    continue
            done_actions.add(aname)
            for r in ow_rules:
                if r.name not in broken and not safe(r, (s,) + args, i, c):
                    broken[r.name] = (i, c)
            for r in af_rules:
                if r.name not in broken and not safe(r, (s, w) + args, i, c):
                    broken[r.name] = (i, c)
            for r in after_any:
                if r.name not in broken and not safe(r, (s, w, aname, args), i, c):
                    broken[r.name] = (i, c)
            p = 0
            if sym is not None:
                t, p = sym.canon(t)
            j = index.get(t)
            if j is None:
                if len(states) >= max_states:
                    g.complete = False
                    row[c] = -1 - BOUND
                    continue
                j = len(states)
                index[t] = j
                states.append(t)
                parent.append((i, c, p))
            row[c] = j
            if prow is not None:
                prow[c] = p
        out.append(row)
        if perms is not None:
            perms.append(prow)
        for k, (o, args, aargs, ci, act) in enumerate(opt_specs):
            try:
                shown = o.offered(s, *args)
            except Exception as err:  # model code
                model_error(f"option {o.name!r}{args} raised {type(err).__name__}: {err}", i, None, err)
                continue
            if not shown:
                continue
            offered.add(o.name)
            if o.name in contra:
                continue
            if ci is not None:                       # the call already ran in this state
                v = row[ci]
                if v <= -1 - 2:
                    contra[o.name] = (i, k, -1 - v)
                continue
            w = State(s)
            try:
                act.fn(w, *aargs)
            except Refused as why:
                contra[o.name] = (i, k, refusal(why, act.source))
            except Exception as err:  # model code
                model_error(f"option {o.name!r}: {show_step((act.name, act.params, aargs))} raised "
                            f"{type(err).__name__}: {err}", i, None, err)
        i += 1
        if progress is not None and i % 1000 == 0:
            progress({"states": len(states)})
    if g.stopped_early:
        g.complete = False                       # states found but not expanded stay listed
    g.seconds = time.perf_counter() - t0
    g.steps = sum(len({j for j in row if j >= 0}) for row in out)
    return g


def _orbit(sym, x):
    if sym is None:
        return [x]
    out = []
    for p in range(sym.n):
        y = sym.rename(p, x)
        if y not in out:
            out.append(y)
    return out


def orbit(graph: Graph, x) -> list:
    return _orbit(graph.sym, x)


def replay(graph: Graph, call_indices) -> list[tuple]:
    """Replay a concrete run once with a recording state: (call, marked effect sources)
    per step. The search itself never records."""
    keys = graph.keys
    t = graph.init
    out = []
    for n, c in enumerate(call_indices, 1):
        call = graph.calls[c]
        w = RecordingState(zip(keys, t))
        try:
            call.action.fn(w, *call.args)
            t = tuple(w[k] for k in keys)
        except Exception as err:  # model code: a step of a found run must work again
            file, line = _location(err, graph.model.root)
            raise ModelError(f"replaying step {n} {show_step(call.step())} raised {type(err).__name__}: "
                             f"{err} (the model does not give the same result twice)", file, line) from err
        out.append((call, {src for _, _, src in w.writes if src is not None}))
    return out
