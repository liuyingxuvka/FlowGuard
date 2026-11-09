"""What the tool computes on intent (design 3.2, 3.3, 3.6): rule against rule, rule against code,
the guards, distinct, and liveness. Each `run_*` returns a JSON-ready result with a verdict (red,
grey, ok) and at most a few lines; pytest items (flowguard.plugin) call them, nothing else runs them.
"""
from __future__ import annotations

import ast
import importlib.util
import inspect
import itertools
import os
import textwrap
import time
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from . import probe as P
from . import sites as S
from .cells import (Kind, Raised, base_value, build_space, coerce, read_predicate, same, show, show_cell,
                    smallest)
from .config import project_code
from .api import Refused, _AnchorBinding
from .sources import parse as parse_source
from .tracer import Footprint

CONFLICT = object()


class Case:
    """Internal lower-witness context used by the declared scenario argument plan."""

    __slots__ = ('_engine', '_rule', '_witness_index', '__dict__')

    def __init__(self, fields: dict, engine=None, rule=None, witness_index=0):
        self.__dict__.update(fields)
        self._engine, self._rule, self._witness_index = engine, rule, witness_index

    def witness(self, child):
        """An actual lower input, verified against its homes, with this cell's outcome."""
        if self._engine is None or self._rule is None:
            raise WitnessUnavailable('witness needs an engine-bound scenario case')
        child = self._engine.used_rule(self._rule, child)
        self._engine._used_witnesses.setdefault(self._rule.id, set()).add(child.id)
        name = self._engine.child_field(self._rule, child)
        if name not in self.__dict__:
            raise WitnessUnavailable(f'{self._rule.id} has no outcome field for {child.id}')
        inputs = self._engine._verified_witnesses(child, self.__dict__[name])
        choice = self._witness_index.get(child.id, 0) if isinstance(self._witness_index, dict) else self._witness_index
        index, nested = choice if isinstance(choice, tuple) else (choice, 0)
        return Case(inputs[index], self._engine, child, witness_index=nested)

    def __getitem__(self, name):
        return self.__dict__[name]

    def __contains__(self, name):
        return name in self.__dict__

    def get(self, name, default=None):
        return self.__dict__.get(name, default)

    def __repr__(self):
        return f"Case({show_cell(self.__dict__)})"


class PredicateError(Exception):
    pass


class WitnessUnavailable(Exception):
    """Insufficient lower evidence, never an apparent code disagreement."""


class ObservationUnavailable(WitnessUnavailable):
    def __init__(self, status, reasons):
        super().__init__('; '.join(reasons))
        self.status = status


def outcome_eq(a, b) -> bool:
    if isinstance(a, Raised) or isinstance(b, Raised):
        return (isinstance(a, Raised) and isinstance(b, Raised)
                and type(a.error) is type(b.error) and str(a.error) == str(b.error))
    if isinstance(a, Refused) or isinstance(b, Refused):
        return a == b
    return same(a, b)


def eval_rule(r, cell):
    if any(f not in cell for f in r.fields):
        return None
    try:
        return r.eval(cell)
    except Exception as e:   # a predicate that fails is the intent's own bug: red, with the cell
        raise PredicateError(f"{r.id} predicate raised {type(e).__name__}: {e} at {show_cell(cell)}") from e


@dataclass
class SiteUse:
    """One decision site of a home or of a project function it calls, as the rule's probe saw it."""
    target: str                 # module:Qual.name of the function holding the site
    fn: object                  # that function (unwrapped)
    site: S.Site
    own: bool                   # the home's own site (not a callee's)
    reached: bool = False       # it ran on some probe cell
    touched: bool = False       # its outcome differs between probe cells
    track: tuple | None = None  # (field, offset): its compared value carries this field
    link: tuple | None = None   # (field, field): it compares two fields with each other
    boundary: bool = False      # it flips exactly where the decision flips
    named: set = field(default_factory=set)   # rule fields its text names (home sites only)

    @property
    def key(self) -> tuple:
        return (self.target, self.site.key)


def _named(site: S.Site, kinds: dict) -> set:
    parts = site.names | {p for n in site.names for p in n.split("_") if p}
    return {f for f in kinds if f in parts}


def _shift(v, off, kind: Kind):
    """A code constant compared with `field + off`, moved onto the field itself."""
    if not off or not (isinstance(v, (int, float, Decimal)) and not isinstance(v, bool)):
        return v
    moved = Decimal(str(v)) - off
    return int(moved) if kind.name == "int" else float(moved) if kind.name == "float" else moved


def _ckey(c: dict) -> tuple:
    return tuple(sorted((k, type(v).__name__, repr(v)) for k, v in c.items()))


def _bump(v, sign: int = 1):
    """A copy of a constant moved far up (sign 1) or down (-1), or None when it is not a plain constant:
    the probe of perturbed(). Both ways, so a bound is crossed whichever side the cells lie on."""
    if isinstance(v, bool):
        return not v
    if isinstance(v, int):
        return v + sign * 7919
    if isinstance(v, float):
        return v + sign * 7919.5
    if isinstance(v, Decimal):
        return v + sign * Decimal(7919)
    if isinstance(v, str):
        return v + "\u2063flowguard" if sign > 0 else "\u2063flowguard" + v
    if isinstance(v, (date, datetime)):
        try:
            return v + sign * timedelta(days=3001)
        except OverflowError:
            return v - sign * timedelta(days=3001)
    if isinstance(v, timedelta):
        return v + sign * timedelta(days=3001)
    if isinstance(v, (tuple, list, frozenset, set)) and v and all(_bump(x, sign) is not None for x in v):
        return type(v)(_bump(x, sign) for x in v)
    if isinstance(v, dict) and v and any(_bump(x, sign) is not None for x in v.values()):
        return {k: (_bump(x, sign) if _bump(x, sign) is not None else x) for k, x in v.items()}
    return None


def _project_value(v, is_project) -> bool:
    """A project module, or a value defined in one."""
    if inspect.ismodule(v):
        return bool(getattr(v, "__file__", None)) and is_project(v.__file__)
    mod = __import__("sys").modules.get(getattr(v, "__module__", None) or "")
    return bool(getattr(mod, "__file__", None)) and is_project(mod.__file__)


def _at(file: str, line: int, where: str) -> bool:
    """A site at file:line matches equivalent="path.py:line" when the path is the file or its tail."""
    path, _, ln = where.rpartition(":")
    return int(ln) == line and (file == path or file.endswith("/" + path.lstrip("./")))


class Engine:
    """Per-run caches over one Model: spaces per key, resolved homes, probes, results per item."""

    def __init__(self, model):
        self.m = model
        self.is_project = project_code(model.cfg)
        from .sources import Archive
        self.archive = Archive(model.cfg.root)
        self._rr_space: dict = {}
        self._rr_info: dict = {}
        self._readings: dict = {}
        self._building: set = set()
        self._code_reasons: dict = {}
        self._axes: dict = {}
        self._copies: dict = {}
        root, flowguarddir = str(model.cfg.root) + os.sep, str(Path(__file__).resolve().parent) + os.sep
        self.test_side = lambda f: f.startswith(root) and f.endswith(".py") and not f.startswith(flowguarddir) and \
            "site-packages" not in f and not self.is_project(f)
        self._code_space: dict = {}
        self._sites: dict = {}
        self._cases: dict = {}
        self._home_runs: dict = {}
        self._pcells: dict = {}
        self._probes: dict = {}
        self.results: dict = {}
        self._witnesses, self._contracts = {}, {}
        self._used_witnesses = {}
        self._provisional = {}
        self._proven_rows = {}
        # The calls a `fields` anchor's tests reached: set by the pytest plugin for its session.
        self.call_sites = None

    def child_nodes(self, rule):
        nodes = set()
        for identifier in set(rule.uses) & self._used_witnesses.get(rule.id, set()):
            contract = self.contract_summary(identifier)
            nodes.update(contract['homes'])
            nodes.update(contract['footprint'])
        return nodes

    def provisional(self, declaration):
        if declaration.id in self._provisional:
            return self._provisional[declaration.id]
        from .sources import provisional
        path = self.m.cfg.root / self.m.file_of[declaration.id]
        pending = provisional(parse_source(declaration.source), self.m.cfg, path)
        if hasattr(declaration, 'live_rows'):
            from .history import confirmation, self_confirmed
            pending = pending or self_confirmed(self.m.cfg, declaration, self)['pending']
            evidence = confirmation(self.m.cfg, declaration, self)
            self._proven_rows[declaration.id] = evidence['proven_rows']
            if evidence['cleared']:
                pending = False
        confirmation = getattr(declaration, 'confirmed', None)
        if confirmation and self.archive.status(confirmation)[0]:
            pending = False
        self._provisional[declaration.id] = pending
        return pending

    def used_rule(self, parent, child):
        identifier = child.id if hasattr(child, 'id') else child
        seen = set()
        while identifier in self.m.superseded_by and identifier not in seen:
            seen.add(identifier)
            identifier = self.m.superseded_by[identifier]
        if identifier not in parent.uses or identifier not in self.m.rules:
            raise WitnessUnavailable(f'{parent.id} must declare uses=[{identifier}] before taking its witness')
        return self.m.rules[identifier]

    def child_field(self, parent, child):
        aliases = {child.id.lower()}
        for old in self.m.superseded_by:
            identifier, seen = old, set()
            while identifier in self.m.superseded_by and identifier not in seen:
                seen.add(identifier)
                identifier = self.m.superseded_by[identifier]
            if identifier == child.id:
                aliases.add(old.lower())
        candidates = [name for name in parent.fields if name == child.decides or name in aliases]
        if len(candidates) != 1:
            raise WitnessUnavailable(f'{parent.id} needs one outcome field named {child.decides!r} or {child.id.lower()!r}')
        return candidates[0]

    def witnesses(self, child, outcome):
        """The original two useful examples; execution checks use the full verified pool."""
        return self._verified_witnesses(child, outcome)[:2]

    def _verified_witnesses(self, child, outcome):
        key = (child.id, type(outcome).__name__, repr(outcome))
        if key in self._witnesses:
            return self._witnesses[key]
        if not child.homes or not self.rr_space(child.decides)[4]:
            raise WitnessUnavailable(f'{child.id} needs complete rules and a real home before providing witnesses')
        space = self.code_space(child.decides)
        if space[1] != 'complete':
            raise WitnessUnavailable(f'{child.id} needs a complete lower code partition before providing witnesses')
        candidates = [dict(row.inputs) for row in child.live_rows] + space[0]
        homes = []
        for home in child.homes:
            fn, _, gone = self.home_sites(home.target)
            if gone or not isinstance(home, _AnchorBinding):
                raise WitnessUnavailable(f'{child.id} needs source bindings reaching each real function')
            code = getattr(S.unwrap(fn), '__code__', None)
            if code is None:
                raise WitnessUnavailable(f'{child.id} home has no traceable Python function')
            homes.append((home, fn, code))
        verified, seen = [], set()
        for inputs in candidates:
            signature = _ckey(inputs)
            if signature in seen or not outcome_eq(self.effective(child, inputs), outcome):
                continue
            seen.add(signature)
            agrees = True
            for home, fn, code in homes:
                for indices in self._witness_variants(child, inputs):
                    with self._binding_footprint(home) as footprint:
                        actual = self.call(home, inputs, fn, indices)
                    unavailable = isinstance(actual, Raised) and isinstance(actual.error, WitnessUnavailable)
                    if unavailable or code is None or S.code_key(code) not in footprint.keys() or not same(outcome, actual):
                        agrees = False
                        break
                if not agrees:
                    break
            if agrees:
                verified.append(dict(inputs))
        if len(verified) < 2:
            raise WitnessUnavailable(f'{child.id} has only {len(verified)} different verified inputs for {show(outcome)}; two are required')
        # Keep a literal row first, then maximize differences among actual inputs.
        first = verified[0]
        second = max(range(1, len(verified)), key=lambda i: sum(not outcome_eq(verified[i][n], first[n]) for n in first))
        self._witnesses[key] = (first, verified[second], *(value for i, value in enumerate(verified[1:], 1) if i != second))
        return self._witnesses[key]

    def _witness_variants(self, rule, cell):
        """Every joint choice of verified lower inputs, including nested uses paths."""
        children = [self.used_rule(rule, identifier) for identifier in rule.uses]

        def choose(position, selected):
            if position == len(children):
                yield dict(selected)
                return
            child = children[position]
            outcome = cell[self.child_field(rule, child)]
            for index, inputs in enumerate(self._verified_witnesses(child, outcome)):
                for nested in self._witness_variants(child, inputs):
                    selected[child.id] = (index, nested)
                    yield from choose(position + 1, selected)
            selected.pop(child.id, None)

        yield from choose(0, {})

    def _composition_scope(self, rule):
        """Distinguish a closed type domain from supported open-domain partitions."""
        for identifier in rule.uses:
            child = self.used_rule(rule, identifier)
            if any(kind.name != 'bool' and not (kind.name == 'enum' and kind.enum_type)
                   for kind in self.kinds(child.decides).values()) or self._composition_scope(child) != 'finite':
                return 'partition'
        return 'finite'

    def contract_summary(self, child, *, parts=None):
        """Summarize checked items, or verify a lower contract needed by a parent.

        A pytest session supplies its actual complete item results. That path
        never executes a home again; parent witness checks remain in uses=.
        """
        child = self.m.rules[child] if isinstance(child, str) else child
        if parts is not None or child.id not in self._contracts:
            checked = parts is not None
            if not checked:
                parts = [self.run_rules(child)]
                for home in child.homes:
                    parts.extend(self.run_home(child, home, part) for part in ('rows', 'cells'))
                    if self.m.deep:
                        parts.append(self.run_live(child, home))
            outcomes = {}
            for cell in self.rr_space(child.decides)[0]:
                value = self.effective(child, cell)
                if value is not None and value is not CONFLICT:
                    outcomes[(type(value).__name__, repr(value))] = value
            reasons = []
            if checked:
                required = {('rules', None)} | {(part, h.target) for h in child.homes for part in (('rows', 'cells', 'live') if self.m.deep else ('rows', 'cells'))}
                if not required <= {(p['kind'], p.get('target')) for p in parts}:
                    reasons.append('not all declared contract items ran')
            else:
                for value in outcomes.values():
                    try:
                        self.witnesses(child, value)
                    except WitnessUnavailable as error:
                        reasons.append(str(error))
            verdicts = {part['verdict'] for part in parts}
            provisional = any(part.get('provisional') for part in parts)
            verdict = 'red' if 'red' in verdicts else 'grey' if 'grey' in verdicts or reasons or not child.homes else 'ok'
            self._contracts[child.id] = dict(verdict=verdict, outcomes=[list(key) for key in sorted(outcomes)],
                complete=self.rr_space(child.decides)[4], homes=[home.target for home in child.homes],
                footprint=sorted({node for part in parts for node in part.get('footprint', [])}), reasons=reasons, provisional=provisional)
        return self._contracts[child.id]

    def _outcome_cells(self, key, cells):
        allowed = {}
        for parent in self.m.active(key):
            for identifier in parent.uses:
                child = self.m.rules.get(identifier)
                if child is None:
                    continue
                name = self.child_field(parent, child)
                outcomes = [self.effective(child, cell) for cell in self.rr_space(child.decides)[0]]
                allowed.setdefault(name, []).extend(v for v in outcomes if v is not None and v is not CONFLICT)
        return [cell for cell in cells if all(any(outcome_eq(cell[name], value) for value in values) for name, values in allowed.items())]

    def run_states(self, declaration):
        from flowguard.structure import build
        from contextlib import closing
        from .sources import authority
        valid, why = authority(parse_source(declaration.source), None, self.m.cfg, self.archive)
        red, grey = [], [] if valid else [why]
        from .anchors import value_gate
        with closing(build(self.m.cfg.root, roots=self.m.cfg.roots)) as graph:
            writes = [row for row in graph.assignments(include_unknown=True) if row['field'] == declaration.target
                      and (row.get('literal') or row.get('values'))]
            table = {declaration.target: dict(name=declaration.target, values=tuple(declaration.values),
                                              where=f'states() {self.m.file_of.get(declaration.id, "")}:{declaration.line}')}
            red.extend(issue.message for issue in value_gate(table, writes))
        if not writes:
            grey.append(f'no literal writes found for {declaration.target} -> check the field binding')
        return dict(kind='states', verdict='red' if red else 'grey' if grey else 'ok', red=red, grey=grey,
                    info=[], n=len(writes), files=sorted({write['file'] for write in writes}), provisional=valid and self.provisional(declaration))

    def run_structure(self, declaration):
        from flowguard.structure import build
        from contextlib import closing
        from .sources import authority
        valid, why = authority(parse_source(declaration.source), None, self.m.cfg, self.archive)
        red, grey = [], [] if valid else [why]
        files = set()
        coverage = None
        with closing(build(self.m.cfg.root, roots=self.m.cfg.roots)) as graph:
            violations = declaration.pred(graph)
            if not isinstance(violations, (list, tuple, set, dict)):
                raise TypeError(f'{declaration.id}: a structure rule returns its violating nodes, not a boolean')
            for node in violations:
                if isinstance(node, dict):
                    identity = f'{node["file"]}:{node["line"]}'
                    name = node.get('node', node.get('id', identity))
                    files.add(node['file'])
                else:
                    identity = name = str(node)
                if identity not in declaration.allowed and name not in declaration.allowed:
                    red.append(f'{declaration.id}: {identity} {name} -> fix it or allow this node with a reason')
            coverage = graph.query_coverage()
            if not coverage['queried']:
                coverage['complete'] = False
            if not coverage['queried'] and not red:
                grey.append('structure rule queried no source facts -> bind the check to the code it constrains')
            for issue in coverage['issues']:
                affected = issue['files']
                location = affected[0] if affected else 'mapped sources'
                if len(affected) > 1:
                    location += f' and {len(affected) - 1} more files'
                grey.append(f'{issue["query"]} query incomplete for {issue["language"]}: '
                            f'{issue["reason"]} ({location}) -> use a supported explicit scope or reader')
        return dict(kind='structure', verdict='red' if red else 'grey' if grey else 'ok', red=red, grey=grey,
                    info=[], n=len(violations), files=sorted(files), listing=True, query_coverage=coverage,
                    provisional=valid and self.provisional(declaration))

    # ------------------------------------------------------------ cells

    def kinds(self, key: str) -> dict:
        return self.m.kinds.get(key, {})

    def readings(self, key: str) -> dict:
        """{rule id: cells.Reading} for the rules of a key, read once."""
        if key not in self._readings:
            kinds = self.kinds(key)
            self._readings[key] = {r.id: read_predicate(r.pred, {f: kinds[f] for f in r.fields})
                                   for r in self.m.key(key)}
        return self._readings[key]

    def rr_space(self, key: str):
        """(cells, label, points, constants, complete) for rule against rule (design 3.1, R46)."""
        if key not in self._rr_space:
            kinds = self.kinds(key)
            consts, planes, links, hints, reasons, notes = {f: [] for f in kinds}, [], set(), {}, [], []
            self._building.add(key)
            for r in self.m.key(key):
                rd = self.readings(key)[r.id]
                for f, vals in rd.consts.items():
                    consts[f] += vals
                planes += rd.planes
                links |= rd.links
                for f, vals in rd.hints.items():
                    hints.setdefault(f, []).extend(vals)
                reasons += [f"{r.id}: {x}" for x in rd.reasons]
                for row in r.all_rows:   # literals seen in rows join enums
                    for f, v in row.inputs.items():
                        if isinstance(v, str):
                            consts[f].append(v)
                for child in r.uses:     # decomposition: a field named after a used rule's key ranges over its outcomes
                    q = self.m.rules.get(child)
                    if q is None or q.decides in self._building:
                        continue
                    name = self.child_field(r, q)
                    outs = {}
                    for c in self.rr_space(q.decides)[0]:
                        try:
                            v = eval_rule(q, c)
                        except PredicateError:
                            continue
                        if v is not None and kinds[name].accepts(v):
                            outs[(type(v).__name__, repr(v))] = v
                    consts[name] += list(outs.values())
                    notes.append(f"{r.id}: field {name} ranges over the {len(outs)} outcomes of {q.id} (uses)")
            self._building.discard(key)
            sp = build_space(kinds, consts, planes, links, reasons, hints, seed=key)
            self._rr_space[key] = (self._outcome_cells(key, sp.cells), sp.label, sp.pts, consts, sp.complete)
            self._rr_info[key] = dict(planes=planes, links=links, hints=hints, reasons=list(reasons),
                                      space_reasons=sp.reasons, notes=notes)
        return self._rr_space[key]

    def home_sites(self, target: str):
        """(callable, its decision sites, why it is gone or None)."""
        if target not in self._sites:
            try:
                fn = S.resolve(target)
            except (ImportError, AttributeError) as e:   # a gone anchor: red on the screen with its reason
                self._sites[target] = (None, [], f"{type(e).__name__}: {e}")
                return self._sites[target]
            try:
                found = S.sites_of(fn)
            except (OSError, TypeError, S.NotMutable):   # no readable source: no sites, said by liveness
                found = []
            self._sites[target] = (fn, found, None)
        return self._sites[target]

    def code_space(self, key: str):
        """Cells for rule against code (design 3.1): the key's constants and planes plus the constants of
        the sites the rules' probes reached, each on the field it was seen to carry. A moved code
        constant that is on no field keeps the space from being exhaustive."""
        if key not in self._code_space:
            self.rr_space(key)
            info = self._rr_info[key]
            consts = {f: list(v) for f, v in self._rr_space[key][3].items()}
            links = set(info["links"])
            planes = list(info["planes"])
            kinds = self.kinds(key)
            reasons = list(info["reasons"])
            for r in self.m.key(key):
                for h in r.homes:
                    if not self.m.deep:
                        fn, _, gone = self.home_sites(h.target)
                        if gone:
                            continue  # The home item reports the missing target.
                        try:
                            reading = read_predicate(S.unwrap(fn), kinds)
                        except (OSError, TypeError, ValueError, SyntaxError):
                            reasons.append(f'{h.target}: code boundaries unavailable; run check --deep')
                            continue
                        for name, values in reading.consts.items():
                            consts[name].extend(values)
                        links.update(reading.links)
                        planes.extend(reading.planes)
                        reasons.extend(f'{h.target}: {reason}' for reason in reading.reasons)
                        continue
                    pr = self.probe(r, h) or {}
                    reasons.extend(reason for reason in pr.get('unmeasured', []) if reason not in reasons)
                    child_nodes = self.child_nodes(r)
                    for u in pr.get("uses", []):
                        if not u.own and u.target in child_nodes:
                            continue
                        if u.link:
                            links.add(frozenset(u.link))
                        vals = [v for v in S.site_constants(u.site) if not S.covered_constant(v)]
                        if not vals:
                            continue
                        if u.track:
                            f, off = u.track
                            consts[f] += [_shift(coerce(v, kinds[f]), off, kinds[f]) for v in vals]
                        elif u.named:
                            for f in u.named:
                                consts[f] += [coerce(v, kinds[f]) for v in vals]
                        elif u.touched:   # moved by the rule's cells, but on no single field: every field of its kind
                            for f, k in kinds.items():
                                if S.compatible(u.site.const, k):
                                    consts[f] += [coerce(v, k) for v in vals]
                            if any(S.orderable(v) for v in vals):
                                file = self.m.cfg.rel(u.fn.__code__.co_filename)
                                why = f"code constant {show(vals[0])} at {file}:{u.site.line} ({u.site.text[:40]}) " \
                                      "is on no field"
                                if why not in reasons:
                                    reasons.append(why)
            sp = build_space(kinds, consts, planes, links, reasons, info["hints"], seed="code:" + key)
            self._code_space[key] = (self._outcome_cells(key, sp.cells), sp.label, sp.pts)
            self._code_reasons[key] = sp.reasons
        return self._code_space[key]

    def exhaustive_reason(self, rule, reasons: list) -> str:
        """The reasons a space is not exhaustive, this rule's own first, at most two named."""
        own = [x[len(rule.id) + 2:] for x in reasons if x.startswith(rule.id + ": ")]
        rest = [x for x in reasons if not x.startswith(rule.id + ": ")]
        shown = (own + rest)[:2]
        more = len(own) + len(rest) - len(shown)
        return "; ".join(shown) + (f"; +{more} more" if more else "")

    # ------------------------------------------------------------ the effective decision

    def effective(self, rule, cell):
        """The answer the active rules of rule's key give at cell, from rule's point of view."""
        vals = {}
        for q in self.m.active(rule.decides):
            if q is not rule and self.m.distinct_pair(rule.id, q.id):
                continue
            v = eval_rule(q, cell)
            if v is not None:
                vals[q.id] = v
        win = {a: v for a, v in vals.items() if not any(self.m.overrides(b, a) for b in vals if b != a)}
        if not win:
            return None
        first = next(iter(win.values()))
        return first if all(outcome_eq(first, v) for v in win.values()) else CONFLICT

    # ------------------------------------------------------------ rule against rule

    def check_key(self, key: str) -> dict:
        if ("key", key) in self.results:
            return self.results[("key", key)]
        t0 = time.perf_counter()
        cells, label, pts, _, _ = self.rr_space(key)
        rules = self.m.key(key)
        act = self.m.active(key)
        out = dict(cells=len(cells), label=label, conflicts=[], overrides=[], gaps=None, superseded=[], self={},
                   contradicted={}, errors={})
        vals = {}
        for r in rules:
            try:
                vals[r.id] = [eval_rule(r, c) for c in cells]
            except PredicateError as e:
                out["errors"][r.id] = str(e)
        live = [r for r in act if r.id in vals]
        overriding = [r for r in live if r.overrides]

        def third(i, pair) -> bool:
            """A rule outside the pair answers at cell i and overrides one of the pair: it decides there."""
            return any(p.id not in pair and vals[p.id][i] is not None and self.m.overrides(p.id, x)
                       for p in overriding for x in pair)
        for a, b in itertools.combinations(live, 2):
            va, vb = vals[a.id], vals[b.id]
            both = [i for i, c in enumerate(cells) if va[i] is not None and vb[i] is not None]
            if self.m.distinct_pair(a.id, b.id):
                continue
            win = a if self.m.overrides(a.id, b.id) else b if self.m.overrides(b.id, a.id) else None
            bad = [i for i in both if not outcome_eq(va[i], vb[i]) and not third(i, (a.id, b.id))]
            if not bad:
                continue
            if win is not None:
                lose = b if win is a else a
                out["overrides"].append(dict(winner=win.id, loser=lose.id, n=len(bad)))
                continue
            i = cells.index(smallest([cells[i] for i in bad], pts))
            sa, sb = parse_source(a.source), parse_source(b.source)
            out["conflicts"].append(dict(a=a.id, b=b.id, n=len(bad), of=len(both), cell=show_cell(cells[i]),
                                         va=show(va[i]), vb=show(vb[i]),
                                         ask_owner=sa.kind == "owner" and sb.kind == "owner",
                                         rids=list(sa.rids + sb.rids)))
        if live:
            gap = [i for i in range(len(cells)) if all(vals[r.id][i] is None for r in live)]
            if gap:
                c = smallest([cells[i] for i in gap], pts)
                out["gaps"] = dict(n=len(gap), cell=show_cell(c), total=[r.id for r in live if r.total],
                                   cells=[show_cell(cells[i]) for i in gap])
        # The classes each rule gives no result for (another rule may decide them): `show RULE` lists them.
        out["silent"] = {r.id: [show_cell(cells[i]) for i, value in enumerate(vals[r.id]) if value is None]
                         for r in rules if r.id in vals}
        for new in act:
            for old in new.supersedes:
                if old in vals and new.id in vals:
                    ch = [i for i in range(len(cells)) if not (vals[old][i] is None and vals[new.id][i] is None)
                          and (vals[old][i] is None or vals[new.id][i] is None
                               or not outcome_eq(vals[old][i], vals[new.id][i]))]
                    if ch:
                        i = cells.index(smallest([cells[i] for i in ch], pts))
                        out["superseded"].append(dict(new=new.id, old=old, n=len(ch), of=len(cells),
                                                      cell=show_cell(cells[i]), old_v=show(vals[old][i]),
                                                      new_v=show(vals[new.id][i])))
        for r in rules:
            if r.id in out["errors"]:
                continue
            for row in r.live_rows:
                got = eval_rule(r, row.inputs)
                if not outcome_eq(row.expect, got):
                    out["self"].setdefault(r.id, []).append(dict(line=row.line, why=row.why, expect=show(row.expect),
                                                                 got=show(got)))
                    continue
                try:
                    eff = self.effective(r, row.inputs)
                except PredicateError as e:
                    out["errors"][r.id] = str(e)
                    continue
                if eff is not None and eff is not CONFLICT and not outcome_eq(row.expect, eff):
                    by = self.m.superseded_by.get(r.id) or "an overriding rule"
                    out["contradicted"].setdefault(r.id, []).append(dict(line=row.line, why=row.why,
                                                                         expect=show(row.expect), eff=show(eff), by=by))
        out["seconds"] = round(time.perf_counter() - t0, 4)
        self.results[("key", key)] = out
        return out

    def independence(self, rule) -> list[str]:
        """Grey reasons when the predicate restates the code: it enters project code, names a project
        module or constant, or its answers change when a project global changes (however it reads it)."""
        reasons = []
        cells = self.rr_space(rule.decides)[0] + [r.inputs for r in rule.live_rows]   # all of them: no code runs
        with Footprint(self.is_project, inside=S.code_key(rule.pred.__code__)) as fp:
            before = self._answers(rule, cells)
        entered = {entry for entry in fp.entered if entry[:2] != S.code_key(Refused.__init__.__code__)}
        if entered:
            q = sorted(entered)[0]
            reasons.append(f"circular: the predicate enters project code ({self.qual(q)})")
        borrowed = self.borrowed(rule)
        borrowed += [x for x in self.perturbed(rule, cells, before) if not any(x.split(" ")[0] in b for b in borrowed)]
        if borrowed:
            reasons.append(f"rule borrows the code's value: {', '.join(borrowed[:2])}")
        return reasons

    def _answers(self, rule, cells) -> list:
        out = []
        for c in cells:
            try:
                out.append(("v", repr(eval_rule(rule, c))))
            except PredicateError as e:
                out.append(("raised", type(e.__cause__).__name__))
        return out

    def project_globals(self) -> list:
        """(owner, name, value, label) for every constant a predicate could borrow: the globals of loaded
        project modules, the class attributes of their classes, and names test-side modules imported
        from project code (copies made at import time)."""
        out = []
        for mod in list(__import__("sys").modules.values()):
            f = getattr(mod, "__file__", None)
            if not isinstance(f, str):
                continue
            if self.is_project(f):
                for name, v in list(vars(mod).items()):
                    if name.startswith("__"):
                        continue
                    if _bump(v) is not None:
                        out.append((mod, name, v, f"{mod.__name__}.{name}"))
                    elif inspect.isclass(v) and v.__module__ == mod.__name__ and not issubclass(v, __import__("enum").Enum):
                        out += [(v, a, x, f"{mod.__name__}.{name}.{a}") for a, x in list(vars(v).items())
                                if not a.startswith("__") and _bump(x) is not None]
            elif self.test_side(f):
                for name in self._imported_from_project(mod):
                    v = vars(mod).get(name)
                    if _bump(v) is not None:
                        out.append((mod, name, v, f"{name} (from project code, via {mod.__name__})"))
        return out

    def _imported_from_project(self, mod) -> set:
        key = getattr(mod, "__file__", "")
        if key in self._copies:
            return self._copies[key]
        names = set()
        try:
            tree = ast.parse(Path(key).read_text(encoding="utf-8"))
        except (OSError, SyntaxError, ValueError):
            tree = None
        for n in (tree.body if tree else []):
            if isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
                src = __import__("sys").modules.get(n.module)
                if src is not None and self.is_project(getattr(src, "__file__", "") or ""):
                    names |= {a.asname or a.name for a in n.names}
            elif isinstance(n, ast.Assign):   # LIMIT = members.DEFAULT_SEATS - 2: a copy computed from project code
                roots = {x.id for x in ast.walk(n.value) if isinstance(x, ast.Name)}
                if any(_project_value(vars(mod).get(r), self.is_project) for r in roots):
                    names |= {x.id for t in n.targets for x in ast.walk(t) if isinstance(x, ast.Name)}
        self._copies[key] = names
        return names

    def perturbed(self, rule, cells, before) -> list[str]:
        """Labels of project globals the predicate's answers depend on: each is moved (numbers by a
        large step, texts and dates too, containers element-wise) and the predicate re-run on the cells.
        Every read path sees the moved value, so it is caught however the predicate reaches it."""
        found = self.project_globals()
        if not found:
            return []

        def moved(group, sign) -> bool:
            done = []
            try:
                for owner, name, v, _ in group:
                    try:
                        setattr(owner, name, _bump(v, sign))
                        done.append((owner, name, v))
                    except (AttributeError, TypeError):   # a read-only name cannot be moved: it is not tried
                        continue
                return self._answers(rule, cells) != before
            finally:
                for owner, name, v in reversed(done):
                    setattr(owner, name, v)

        def changes(group) -> bool:
            return moved(group, 1) or moved(group, -1)
        if not changes(found):
            return []
        out, stack = [], [found]
        while stack and len(out) < 2:   # split the moved set in halves until single names remain
            group = stack.pop()
            if len(group) == 1:
                out.append(f"{group[0][3]} (its answers change with it)")
                continue
            half = len(group) // 2
            for part in (group[half:], group[:half]):
                if changes(part):
                    stack.append(part)
        return out

    def borrowed(self, rule) -> list[str]:
        names, stack = set(), [rule.pred.__code__]
        while stack:
            co = stack.pop()
            names |= set(co.co_names)
            stack += [c for c in co.co_consts if inspect.iscode(c)]
        g = rule.pred.__globals__
        out = []
        imported = self._project_imports(rule)
        for n in sorted(names):
            v = g.get(n)
            if v is Refused:
                continue  # The declared refusal value is model syntax, not a borrowed decision.
            mod = getattr(v, "__file__", None) if inspect.ismodule(v) else None
            owner = getattr(v, "__module__", None) if not inspect.ismodule(v) else None
            ofile = getattr(__import__("sys").modules.get(owner), "__file__", None) if isinstance(owner, str) else None
            if mod and self.is_project(mod):
                out.append(f"{n} (project module {v.__name__})")
            elif (ofile and self.is_project(ofile)) or n in imported:
                out.append(f"{n} from {imported.get(n) or owner}")
        try:   # a.b.c through modules: helpers.members reaches a project module through a test module
            tree = ast.parse(textwrap.dedent(inspect.getsource(rule.pred)))
        except (OSError, TypeError, SyntaxError):
            tree = None
        for n in (ast.walk(tree) if tree else []):
            if not isinstance(n, ast.Attribute):
                continue
            chain, x = [], n
            while isinstance(x, ast.Attribute):
                chain.append(x.attr)
                x = x.value
            if not isinstance(x, ast.Name) or not inspect.ismodule(g.get(x.id)):
                continue
            obj, path = g[x.id], x.id
            for attr in reversed(chain):
                obj, path = getattr(obj, attr, None), f"{path}.{attr}"
                if inspect.ismodule(obj) and self.is_project(getattr(obj, "__file__", "") or ""):
                    hit = f"{path} (project module {obj.__name__})"
                    if hit not in out and not path.split(".")[0] in {o.split(" ")[0] for o in out}:
                        out.append(hit)
                    break
                if not inspect.ismodule(obj):
                    break
        return out

    def _project_imports(self, rule) -> dict:
        try:
            tree = ast.parse(Path(rule.file).read_text(encoding="utf-8"))
        except OSError:
            return {}
        out = {}
        for n in ast.walk(tree):
            if isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
                try:
                    spec = importlib.util.find_spec(n.module)
                except (ImportError, ValueError):
                    continue
                if spec and spec.origin and self.is_project(spec.origin):
                    for a in n.names:
                        out[a.asname or a.name] = n.module
        return out

    def qual(self, entered) -> str:
        f, _, q = entered
        rel = self.m.cfg.rel(f)
        mod = rel[:-3].replace("/", ".")
        for r in self.m.cfg.roots:
            pre = self.m.cfg.rel(r) + "."
            if mod.startswith(pre):
                mod = mod[len(pre):]
        return f"{mod.removesuffix('.__init__')}:{q}"

    def run_rules(self, rule) -> dict:
        k = self.check_key(rule.decides)
        red, grey = [], []
        if rule.id in k["errors"]:
            red.append(k["errors"][rule.id])
        for s in k["self"].get(rule.id, []):
            red.append(f"self: {rule.id} says {s['got']} on its own row L{s['line']} \"{s['why']}\" "
                       f"(row expects {s['expect']})")
        for s in k["contradicted"].get(rule.id, []):
            red.append(f"row {rule.id} L{s['line']} \"{s['why']}\" expects {s['expect']}; the decision of "
                       f"{s['by']} is {s['eff']}: update the row or retire it with a reason")
        for c in k["conflicts"]:
            if rule.id in (c["a"], c["b"]):
                tail = f" (owner {', '.join(c['rids'])}) -> ask owner" if c["ask_owner"] else ""
                red.append(f"conflict {c['a']} vs {c['b']} at {c['cell']}: {c['va']} vs {c['vb']} "
                           f"({c['n']} of {c['of']} shared cells){tail}")
        g = k["gaps"]
        if g and rule.total and rule.id in g["total"]:
            red.append(f"gap in {rule.decides} (total=True): no rule decides {g['n']} cells, smallest {g['cell']}")
        grey += self.independence(rule)
        grey += getattr(self.m, 'scenario_issues', {}).get(rule.id, [])
        from .sources import authority
        valid, source_reason = authority(parse_source(rule.source), rule.confirmed, self.m.cfg, self.archive, rule.quote)
        if not valid:
            (red if 'quote gone' in source_reason else grey).append(source_reason)
        in_model = any(getattr(relation.rule, 'id', relation.rule) == rule.id
                       for model in self.m.flows.values() for relation in model.relations)
        if not rule.homes and not in_model:
            grey.append('model only -> bind the actual code home')
        info = [f"{o['winner']} overrides {o['loser']} on {o['n']} cells" for o in k["overrides"]
                if rule.id in (o["winner"], o["loser"])]
        info += [f"{s['new']} supersedes {s['old']}: {s['n']} of {s['of']} cells change, smallest {s['cell']} "
                 f"({s['old_v']} -> {s['new_v']})" for s in k["superseded"] if rule.id in (s["new"], s["old"])]
        if g and not rule.total:
            info.append(f"{g['n']} cells of {rule.decides} have no rule (python -m flowguard show --gaps {rule.decides})")
        rr = self._rr_info[rule.decides]
        if k["label"] != "complete":
            grey.append(f"not exhaustively checked ({k['label']}): "
                        f"{self.exhaustive_reason(rule, rr['space_reasons'])}")
        info += [n[len(rule.id) + 2:] for n in rr["notes"] if n.startswith(rule.id + ": ")]
        pending = valid and self.provisional(rule)
        return dict(kind="rules", verdict="red" if red else "grey" if grey else "ok", red=red, grey=grey, info=info,
                    cells=k["cells"], label=k["label"], seconds=k["seconds"],
                    sampled_by=[x for x in rr["space_reasons"] if x.startswith(rule.id + ": ")], provisional=pending,
                    proven_rows=self._proven_rows.get(rule.id, []))

    def run_flow(self, model, events=(), issues=(), *, _context=None, _scopes=None):
        from .flow import check_flow
        from .sources import authority
        _context = _context if _context is not None else dict(stack=[], proofs={}, children={})
        contracts = {}
        for node in model.nodes:
            lower = getattr(node.model, 'id', node.model)
            if lower in self.m.rules:
                contracts[lower] = self.contract_summary(lower)
        index = self.m.anchor_index
        result = check_flow(model, index, events, rules=self.m.rules, contracts=contracts, engine=self,
                            _context=_context, _scopes=_scopes)
        result['info'].append('scope: observed anchor paths and declared finite model; '
                              'unexecuted source routes remain unverified (there is no static path proof)')
        valid, reason = authority(parse_source(model.source), None, self.m.cfg, self.archive, None)
        if not valid:
            result['red' if 'quote gone' in reason else 'grey'].append(reason)
        result['grey'].extend(issues)
        result['verdict'] = 'red' if result['red'] else 'grey' if result['grey'] else 'ok'
        children = list(_context['children'].values())
        result['files'] = sorted({anchor.file for anchor in index.entries
                                  if anchor.name in {node.reference for node in model.nodes}}.union(
                                      *(set(child.get('files', ())) for child in children)))
        result['footprint'] = sorted({anchor.target for anchor in index.entries
                                      if anchor.name in {node.reference for node in model.nodes}}.union(
                                          *(set(child.get('footprint', ())) for child in children)))
        result['drivers'] = sorted({event.case for event in events
                                    if event.anchor in {node.reference for node in model.nodes}}.union(
                                        *(set(child.get('drivers', ())) for child in children)))
        return result

    def run_anchor_distinct(self, declaration):
        from .differences import anchor_distinct
        result = anchor_distinct(self.m.cfg.root, declaration, index=self.m.anchor_index,
                                 cfg=self.m.cfg, archive=self.archive)
        result.update(kind='anchor_distinct', verdict='red' if result['status'] == 'red'
                      else 'grey' if result['status'] == 'grey' else 'ok')
        source_gap = result.get('source_reason') if not (result.get('source_verified') or result.get('provisional')) else None
        result['red'] = [reason for reason in result['reasons'] if reason != source_gap] if result['status'] == 'red' else []
        result['grey'] = ([source_gap] if source_gap else []) + (result['reasons'] if result['status'] == 'grey' else [])
        result['info'] = [declaration.why, f'scope: {result["scope"]}; behavior checked: {result["behavior_checked"]}']
        entries = [anchor for anchor in self.m.anchor_index.entries
                   if any(value in (anchor.name, anchor.target) for value in (declaration.a, declaration.b))]
        result['footprint'] = sorted({anchor.target for anchor in entries})
        result['files'] = sorted({anchor.file for anchor in entries})
        return result

    # ------------------------------------------------------------ rule against code

    def cases(self, rule, home, part: str) -> list:
        """(cell, expected, label) for one home: the rows, or the cells where the decision has an answer."""
        if (rule.id, part) not in self._cases:
            self._cases[(rule.id, part)] = self._cases_of(rule, part)
        return self._cases[(rule.id, part)]

    def _cases_of(self, rule, part: str) -> list:
        if part == "rows":
            out = [(dict(r.inputs), r.expect, f"row L{r.line}") for r in rule.live_rows]
            for old in rule.supersedes:   # agreeing old rows carry over to the new rule's homes
                for r in self.m.rules[old].live_rows if old in self.m.rules else []:
                    if set(r.inputs) <= set(rule.fields):
                        eff = self.effective(rule, r.inputs)
                        if eff is not None and eff is not CONFLICT and outcome_eq(r.expect, eff):
                            out.append((dict(r.inputs), r.expect, f"row {old} L{r.line}"))
            return out
        cells = self.code_space(rule.decides)[0]
        out = []
        for c in cells:
            eff = self.effective(rule, c)
            if eff is not None and eff is not CONFLICT:
                out.append((c, eff, "cell"))
        return out

    def call(self, home, cell, fn, witness_index=0):
        if hasattr(home, 'scenario'):
            try:
                from .calibration import _observe_scenario_current
                import copy
                def arguments(plan, case):
                    values = {}
                    def supply(parameter, value):
                        if parameter in values and not outcome_eq(values[parameter], value):
                            raise WitnessUnavailable(f'{home.name}: several rule fields disagree on scenario argument {parameter}')
                        values[parameter] = value
                    for name, parameter in plan['fields'].items():
                        supply(parameter, case[name])
                    for identifier, lower in plan['children'].items():
                        child = self.used_rule(case._rule, identifier)
                        if self.child_field(case._rule, child) != lower['field']:
                            raise WitnessUnavailable(f'{home.name}: lower outcome field does not match the existing contract')
                        for parameter, value in arguments(lower['plan'], case.witness(identifier)).items():
                            supply(parameter, value)
                    return values
                values = arguments(home.argument_plan, Case(cell, self, home.rule, witness_index))
                requested = copy.copy(home)
                requested.requested_inputs = {name: cell[name] for name in home.observed_fields}
                observed = _observe_scenario_current(self.m.cfg.root, requested, values)
                if observed.status != 'ok':
                    raise ObservationUnavailable(observed.status, observed.reasons)
                return observed.value
            except WitnessUnavailable as error:
                return Raised(error)
            except Exception as error:
                return Raised(WitnessUnavailable(f'scenario backend did not provide an observation: {type(error).__name__}: {error}'))
        if isinstance(home, _AnchorBinding):
            from .anchors import observe
            try:
                if home.anchor is None:
                    raise WitnessUnavailable(f'anchor gone: {home.name}')
                names = {parameter.name for parameter in home.anchor.inputs}
                values = {name: value for name, value in cell.items() if name in names}
                for identifier in home.rule.uses:
                    child = self.used_rule(home.rule, identifier)
                    field = self.child_field(home.rule, child)
                    choices = self._verified_witnesses(child, cell[field])
                    choice = witness_index.get(child.id, 0) if isinstance(witness_index, dict) else witness_index
                    index = choice[0] if isinstance(choice, tuple) else choice
                    supplied = {name: value for name, value in choices[index].items() if name in names}
                    for name in values.keys() & supplied.keys():
                        if not outcome_eq(values[name], supplied[name]):
                            raise WitnessUnavailable(f'{home.name}: ambiguous lower input {name}')
                    if supplied:
                        self._used_witnesses.setdefault(home.rule.id, set()).add(child.id)
                        values.update(supplied)
                if values.keys() != names:
                    raise WitnessUnavailable(f'{home.name}: no source-bound input for {sorted(names - values.keys())}')
                observed = observe(self.m.cfg.root, home.anchor, values)
                if observed.status != 'ok':
                    raise ObservationUnavailable(observed.status, observed.reasons)
                return observed.value
            except WitnessUnavailable as error:
                return Raised(error)
            except Exception as error:
                return Raised(WitnessUnavailable(f'anchor backend did not provide an observation: {type(error).__name__}: {error}'))
        raise TypeError('a source anchor or Flow scenario binding is required; rebuild the original test')

    @contextmanager
    def _binding_footprint(self, home, *, probe=False):
        """Keep every declared business root, without recording its test driver."""
        if not hasattr(home, 'scenario'):
            fn = self.home_sites(home.target)[0]
            code = getattr(S.unwrap(fn), '__code__', None) if fn is not None else None
            with Footprint(self.is_project, inside=S.code_key(code) if probe and code else None) as footprint:
                yield footprint
            return
        keys = set()
        for target in home.targets:
            fn = self.home_sites(target)[0]
            code = getattr(S.unwrap(fn), '__code__', None) if fn is not None else None
            if code:
                keys.add(S.code_key(code))
        with ExitStack() as scopes:
            footprints = [scopes.enter_context(Footprint(self.is_project, inside=key))
                          for key in sorted(keys or {('<unavailable source anchor>', 0)} )]
            try:
                yield footprints[0]
            finally:
                for other in footprints[1:]:
                    footprints[0].entered.update(other.entered)
                    footprints[0].edges.update(other.edges)
                    footprints[0].call_lines.update(other.call_lines)

    def anchor_errors(self, home):
        if not isinstance(home, _AnchorBinding):
            return []
        if home.anchor is None:
            return [f'anchor gone: {home.name}']
        issues = [*home.anchor.issues, *self.m.anchor_index.issues]
        if hasattr(home, 'scenario'):
            issues += list(home.scenario.issues)
        names = {home.name, home.scenario.name} if hasattr(home, 'scenario') else {home.name}
        return list(dict.fromkeys(issue.message for issue in issues
                                  if issue.level == 'red' and issue.name in names))

    def run_home(self, rule, home, part: str) -> dict:
        t0 = time.perf_counter()
        if errors := self.anchor_errors(home):
            return dict(kind=part, verdict='red', red=errors, grey=[], info=[])
        fn, sites, gone = self.home_sites(home.target)
        if gone:
            return dict(kind=part, verdict="red", red=[f"home gone: {home.target} ({gone})"], grey=[], info=[])
        if isinstance(home, _AnchorBinding) and home.anchor is not None and home.anchor.fields:
            res = self._at_calls(rule, home, part)
            res['seconds'] = round(time.perf_counter() - t0, 4)
            self.results[(rule.id, home.target, part)] = res
            return res
        try:
            cases = self.cases(rule, home, part)
        except PredicateError as e:
            return dict(kind=part, verdict="red", red=[str(e)], grey=[], info=[])
        bad, runs, witness_errors, inadequate = [], [], set(), []
        observation_errors = set()
        parent_calls = 0
        with self._binding_footprint(home) as fp:
            for cell, exp, label in cases:
                first, failure = [], None
                try:
                    for indices in self._witness_variants(rule, cell):
                        got = self.call(home, cell, fn, indices)
                        parent_calls += 1
                        runs.append((cell, exp, indices, same(exp, got)))
                        if isinstance(got, Raised) and isinstance(got.error, WitnessUnavailable):
                            (observation_errors if getattr(got.error, 'status', '') == 'red' else witness_errors).add(str(got.error))
                            continue
                        if not same(exp, got) and failure is None:
                            failure = (cell, exp, got, label)
                        if first and not outcome_eq(first[0], got):
                            inadequate.append((cell, first[0], got))
                        elif not first:
                            first.append(got)
                except WitnessUnavailable as error:
                    witness_errors.add(str(error))
                if failure:
                    bad.append(failure)
        self._home_runs[(rule.id, home.target, part)] = runs
        base = S.unwrap(fn)
        code = getattr(base, "__code__", None)   # a C function or slot wrapper has no code to enter
        entered = code is not None and S.code_key(code) in fp.keys()
        red, grey, info = [], [], []
        red.extend(sorted(observation_errors))
        grey.extend(f'{reason} -> strengthen or split the lower contract' for reason in sorted(witness_errors))
        if inadequate:
            cell, first, second = inadequate[0]
            red.append(f'{rule.id} depends on more of {", ".join(rule.uses)} than its outcome at {show_cell(cell)}: '
                       f'{first!r} vs {second!r} -> declare the extra outcome or dependency')
        pts = self.code_space(rule.decides)[2]
        if bad and entered:
            first = smallest([b[0] for b in bad], pts) if part == "cells" else bad[0][0]
            cell, exp, got, label = next(b for b in bad if b[0] is first)
            red.append(f"{home.short}: {len(bad)} of {len(cases)} {part} disagree; smallest {show_cell(cell)} -> "
                       f"rule {show(exp)}, code {got!r}" + (f" ({label})" if label != "cell" else ""))
        if not entered and cases and not witness_errors:
            errors = [got.error for _, _, got, _ in bad if isinstance(got, Raised)]
            first_error = f'; {len(errors)} raised, first {type(errors[0]).__name__}: {errors[0]}' if errors else ''
            red.append(f"binding never enters {home.target}{first_error} -> repair the source anchor or Flow scenario")
        label = self.code_space(rule.decides)[1] if part == "cells" else f"{len(cases)} rows"
        if part == "cells" and label != "complete" and cases:
            grey.append(f"not exhaustively checked ({label}): "
                        f"{self.exhaustive_reason(rule, self._code_reasons.get(rule.decides, []))}")
        res = dict(kind=part, verdict="red" if red else "grey" if grey else "ok", red=red, grey=grey, info=info,
                   n=len(cases), bad=len(bad), entered=entered, label=label,
                   footprint=sorted({self.qual(e) for e in fp.entered}),
                   files=sorted({self.m.cfg.rel(e[0]) for e in fp.entered}), seconds=round(time.perf_counter() - t0, 4))
        if rule.uses:
            scope = self._composition_scope(rule)
            res['composition'] = dict(scope=scope, parent_calls=parent_calls,
                                      checked_all_witnesses=not witness_errors, finite_domain=scope == 'finite')
            if part == 'cells':
                info.append(f'joint lower inputs: {parent_calls} real home calls over ' +
                            ('closed finite domains' if scope == 'finite' else
                             'all verified partition representatives; open domains are not enumerated value by value'))
            res['contracts'] = {identifier: self.contract_summary(identifier) for identifier in rule.uses}
            for identifier, contract in res['contracts'].items():
                if cases and identifier not in self._used_witnesses.get(rule.id, set()):
                    res['grey'].append(f'{identifier} declared but no verified witness was used -> connect the lower Rule outcome through uses and a Flow relation')
                if contract['verdict'] != 'ok':
                    res['grey'].append(f'{identifier} lower contract is {contract["verdict"]} -> fix its source, homes or liveness before reusing it')
            if res['grey'] and res['verdict'] == 'ok':
                res['verdict'] = 'grey'
            res['provisional'] = any(contract.get('provisional') for contract in res['contracts'].values())
        self.results[(rule.id, home.target, part)] = res
        return res

    def _at_calls(self, rule, home, part: str) -> dict:
        """A `fields` anchor's rule fields come from each call's own arguments, so the rule is checked on
        the calls the tests reached (the real call and its replayed input classes), not by calling the
        anchor: `cells` checks every such call against the rule, `rows` each literal row a call reached."""
        names = ', '.join(name for name, _ in home.anchor.fields)
        if self.call_sites is None:
            return dict(kind=part, verdict='grey', red=[], info=[], n=0, bad=0, entered=False,
                        grey=[f'{home.short}: fields（{names}）在测试走到的调用上求值，需要普通 pytest 会话 -> 运行项目的测试'])
        calls, reasons = self.call_sites(rule, home)
        tests = sorted({test for _, _, test in calls})
        red, grey, bad, checked = [], [f'{home.short}: {reason}' for reason in reasons], [], 0
        try:
            if part == 'cells':
                for inputs, outcome, _ in calls:
                    expected = self.effective(rule, inputs)
                    if expected is None or expected is CONFLICT:
                        continue        # no opinion here; a conflict is the [rules] item's red
                    checked += 1
                    if not same(expected, outcome):
                        bad.append(({name: inputs[name] for name in rule.fields}, expected, outcome, 'cell'))
                cases = checked
            else:
                cases = 0
                for cell, expected, label in self.cases(rule, home, 'rows'):
                    reached = [outcome for inputs, outcome, _ in calls
                               if all(name in inputs and outcome_eq(inputs[name], value) for name, value in cell.items())]
                    if not reached:
                        grey.append(f'{home.short}: {label}（{show_cell(cell)}）没有被测试走到的调用核对；'
                                    f'fields 只在调用上求值，回归行和规则的核对见 [rules]')
                        continue
                    cases += 1
                    checked += len(reached)
                    bad.extend((cell, expected, outcome, label) for outcome in reached if not same(expected, outcome))
        except PredicateError as error:
            return dict(kind=part, verdict='red', red=[str(error)], grey=[], info=[], n=0, bad=0, entered=True)
        if bad:
            first = smallest([b[0] for b in bad], self.rr_space(rule.decides)[2])
            cell, expected, got, label = next(b for b in bad if b[0] is first)
            red.append(f'{home.short}: {len(bad)} of {checked} calls disagree; smallest {show_cell(cell)} -> '
                       f'rule {show(expected)}, code {got!r}' + (f' ({label})' if label != 'cell' else ''))
        if not checked and not grey:
            grey.append(f'{home.short}: 没有被测试走到、读得出 fields（{names}）且规则表了态的调用')
        info = [f'checked on {checked} calls the tests reached ({len(tests)} tests); fields {names} are read from each '
                'call\'s own arguments, and classes the tests did not reach are not checked']
        files = sorted({test.partition('::')[0] for test in tests} | {home.anchor.file})
        return dict(kind=part, verdict='red' if red else 'grey' if grey else 'ok', red=red, grey=grey, info=info,
                    n=cases, bad=len(bad), entered=bool(calls), label=f'{checked} calls', tests=tests,
                    footprint=[home.target], files=files)

    # ------------------------------------------------------------ probes (design 3.1 constants, 3.6 realized sites)

    def probe_cells(self, rule):
        """(cells, lines): lines through the base cell and the rule's rows; along a line one field
        takes each of its points. Numeric lines are in point order; other fields give pairs."""
        if rule.id in self._pcells:
            return self._pcells[rule.id]
        pts = self.rr_space(rule.decides)[2]
        names = sorted(pts)
        base = {n: base_value(pts[n]) for n in names}
        bases = [base] + list(self.rr_space(rule.decides)[0]) + [dict(base, **r.inputs) for r in rule.live_rows]
        try:
            if eval_rule(rule, base) is None:   # a partial rule: walk through cells where it answers
                bases += [c for c in self.rr_space(rule.decides)[0] if eval_rule(rule, c) is not None]
        except PredicateError:
            pass   # the [rules] item reports the predicate's error
        seen, uniq = set(), []
        for b in bases:
            if _ckey(b) not in seen:
                seen.add(_ckey(b))
                uniq.append(b)
        cells, index, lines, first, axes = [], {}, [], set(), []

        def at(c):
            k = _ckey(c)
            if k not in index:
                index[k] = len(cells)
                cells.append(c)
            return index[k]
        for nb, b in enumerate(uniq):
            first |= {i for i in [at(b)] if i is not None}
            for n in names:
                ids = [i for i in (at(dict(b, **{n: v})) for v in pts[n]) if i is not None]
                if nb == 0:
                    first |= set(ids)
                    axes.append((n, ids))
                ordered = self.kinds(rule.decides)[n].name not in ("bool", "enum", "str")
                lines += [ids] if ordered else [list(p) for p in itertools.combinations(ids, 2)]
        # `first`: the lines through the base cell and every base cell, enough to find what the home calls
        self._pcells[rule.id] = (cells, lines, sorted(first))
        self._axes[rule.id] = axes
        return self._pcells[rule.id]

    def probe(self, rule, home) -> dict | None:
        """Run the rule's probe cells through the home, then again with the home and the project
        functions it entered instrumented (sites.probe_code): what every site did (flowguard.probe)."""
        k = (rule.id, home.target)
        if k in self._probes:
            return self._probes[k]
        fn, sites, gone = self.home_sites(home.target)
        base = S.unwrap(fn) if fn is not None else None
        if gone or getattr(base, "__code__", None) is None:
            self._probes[k] = None
            return None
        base_cells, base_lines, _ = self.probe_cells(rule)
        samples, witness_lines = [], []
        for cell in base_cells:
            group = []
            try:
                for indices in self._witness_variants(rule, cell):
                    group.append(len(samples))
                    samples.append((cell, indices))
            except WitnessUnavailable:
                # Let the ordinary home call preserve the unavailable-witness reason.
                group.append(len(samples))
                samples.append((cell, {}))
            witness_lines.append(group)
        cells = [cell for cell, _ in samples]
        lines = [[witness_lines[i][0] for i in line] for line in base_lines]
        answers = []
        for c in cells:
            try:
                e = self.effective(rule, c)
            except PredicateError:
                e = None
            answers.append(None if e is CONFLICT else e)
        actuals = []
        with self._binding_footprint(home, probe=True) as fp:
            for cell, indices in samples:
                actuals.append(self.call(home, cell, fn, indices))
        funcs, roots, unmeasured = [], set(), []
        for target in getattr(home, 'targets', (home.target,)):
            obj, own_sites, missing = self.home_sites(target)
            obj = S.unwrap(obj) if obj is not None else None
            if missing or getattr(obj, '__code__', None) is None:
                unmeasured.append(f'{target}: a declared measurement root could not be probed')
                continue
            key = S.code_key(obj.__code__)
            if key in roots:
                continue
            roots.add(key)
            funcs.append((target, obj, own_sites, True))
        for f, line, q in sorted(fp.entered):
            if (f, line) in roots or "<" in q :
                continue
            target = self.qual((f, line, q))
            try:
                obj = S.unwrap(S.resolve(target))
                if S.code_key(obj.__code__) != (f, line):
                    continue
                fs = S.sites_of(obj)
            except (ImportError, AttributeError, OSError, TypeError, SyntaxError, S.NotMutable):
                continue   # a callee that cannot be read again is not probed (and never realized)
            if fs:
                funcs.append((target, obj, fs, False))
        codes = []
        for fi, (target, obj, fs, own) in enumerate(funcs):
            try:
                codes.append(S.probe_code(obj, fi, fs, home=own))
            except (S.NotMutable, SyntaxError, OSError, TypeError, NameError):
                codes.append(None)   # not mutable: its sites stay unread
        P.start()
        try:
            with ExitStack() as stack:
                for (_, obj, _, _), code in zip(funcs, codes):
                    if code is not None:
                        stack.enter_context(S.installed(obj, code))
                for i, (c, indices) in enumerate(samples):
                    P.CASE = i
                    self.call(home, c, fn, indices)
        finally:
            rec = P.take()
        kinds = self.kinds(rule.decides)
        uses = []
        for fi, (target, obj, fs, own) in enumerate(funcs):
            for si, s in enumerate(fs):
                per = rec.get((fi, si), {})
                u = SiteUse(target, obj, s, own, reached=bool(per), touched=P.touched(per),
                            boundary=(P.boundary(per, lines, answers, outcome_eq) or
                                      bool(rule.uses) and P.boundary(per, witness_lines, actuals, outcome_eq)),
                            named=_named(s, kinds))
                if s.kind in ("cmp", "in") and per:
                    left, right = P.tracks(per, 1, cells, kinds), P.tracks(per, 2, cells, kinds)
                    if left and right and left[0] != right[0]:
                        u.link = (left[0], right[0])
                    elif s.has_const:
                        u.track = left if s.const_side == "right" else right
                uses.append(u)
        self._probes[k] = dict(uses=uses, entered={self.qual(e) for e in fp.entered} | {home.target},
                               mutable={t: c is not None for (t, _, _, _), c in zip(funcs, codes)}, n=len(cells),
                               answers=answers, unmeasured=unmeasured)
        return self._probes[k]

    def realized(self, rule, home) -> list[SiteUse]:
        """Sites reached by rule fields, or following a rule/output boundary.

        Joint lower witnesses can expose an output boundary hidden by the upper
        fields; those actual changes belong to this contract too.
        """
        pr = self.probe(rule, home)
        if pr is None:
            return []
        if not pr["mutable"].get(home.target):   # the home cannot be instrumented (a closure): read its sites statically
            return [u for u in pr["uses"] if u.own and u.named]
        child_nodes = self.child_nodes(rule)
        return [u for u in pr["uses"] if (u.own or u.target not in child_nodes) and (u.boundary or
                (u.own and u.reached and (u.named or (u.track and u.site.has_const))))]

    # ------------------------------------------------------------ liveness

    def run_live(self, rule, home) -> dict:
        t0 = time.perf_counter()
        if errors := self.anchor_errors(home):
            return dict(kind='live', verdict='red', red=errors, grey=[], info=[], k=0, n=0)
        if isinstance(home, _AnchorBinding) and home.anchor is not None and home.anchor.fields:
            return dict(kind='live', verdict='grey', red=[], info=[], k=0, n=0, sites=[], mutants=0,
                        grey=[f'{home.short}: fields 锚点的规则在测试走到的调用上核对，变异存活检查需要能直接调用的锚点'])
        fn, sites, gone = self.home_sites(home.target)
        if gone:
            return dict(kind="live", verdict="red", red=[f"home gone: {home.target}"], grey=[], info=[], k=0, n=0)
        base = S.unwrap(fn)
        if getattr(base, "__code__", None) is None:
            return dict(kind="live", verdict="grey", red=[], grey=[f"not mutable: {home.target} has no Python code"],
                        info=[], k=0, n=0, sites=[], mutants=0)
        real = self.realized(rule, home)
        pr = self.probe(rule, home) or {"uses": [], "mutable": {}}
        # the rule's own items only (its homes whose probe entered the function): no credit from other rules
        suites: dict = {}

        def suite(target):
            if target not in suites:
                suites[target] = []
                for h in rule.homes:
                    hp = self.probe(rule, h)
                    if h.target != target and not (hp and target in hp["entered"]):
                        continue
                    hfn = self.home_sites(h.target)[0]
                    for part in ("rows", "cells"):
                        try:
                            cs = self.cases(rule, h, part)
                        except PredicateError:
                            continue
                        runs = self._home_runs.get((rule.id, h.target, part))
                        if runs is None:
                            runs = []
                            for cell, expected, _ in cs:
                                try:
                                    for indices in self._witness_variants(rule, cell):
                                        runs.append((cell, expected, indices,
                                                     same(expected, self.call(h, cell, hfn, indices))))
                                except WitnessUnavailable:
                                    pass  # The home/contract item reports incomplete lower inputs.
                            self._home_runs[(rule.id, h.target, part)] = runs
                        suites[target].append((h, hfn, runs))
            return suites[target]
        per_site: dict = {}
        muts = 0
        for target, group in itertools.groupby(sorted(real, key=lambda u: (not u.own, u.target)), key=lambda u: u.target):
            group = list(group)
            obj = group[0].fn
            runs = suite(target)   # the unmutated outcomes, before any mutant is installed
            for mu in S.mutants_of([u.site for u in group], {u.site.key for u in group}):
                muts += 1
                entry = dict(label=mu.label, killed=None, why="", mutable=False)
                try:
                    code = S.mutant_code(obj, mu)
                except (S.NotMutable, SyntaxError, OSError, TypeError, NameError) as e:
                    entry["why"] = f"not mutable: {e}"
                else:
                    entry['mutable'] = True
                    with S.installed(obj, code):
                        unavailable, checked_any = [], False
                        for h, hfn, checked in runs:
                            for c, expected, indices, ok in checked:
                                if not ok:
                                    continue
                                got = self.call(h, c, hfn, indices)
                                if isinstance(got, Raised) and isinstance(got.error, WitnessUnavailable):
                                    unavailable.append(str(got.error))
                                    continue
                                checked_any = True
                                if not same(expected, got):
                                    entry['killed'] = True
                                    break
                            if entry['killed']:
                                break
                        if entry['killed'] is not True:
                            entry['killed'] = None if unavailable or not checked_any else False
                            if entry['killed'] is None:
                                entry['why'] = ('observation unavailable: ' + '; '.join(dict.fromkeys(unavailable))
                                                if unavailable else 'no passing baseline input was measured')
                per_site.setdefault((target, mu.site.key), []).append(entry)
        rows, k, n, grey, info = [], 0, 0, list(pr.get('unmeasured', [])), []
        realized_keys = {u.key for u in real}
        listed = [u for u in pr["uses"] if u.own or u.named or u.key in realized_keys] or \
            [SiteUse(home.target, base, s, True) for s in sites]
        declared = [(w, why, "rule") for w, why in rule.equivalent] + [(w, why, "home") for w, why in home.equivalent]
        used = set()
        for u in listed:
            ms = per_site.get(u.key)
            is_real = u.key in realized_keys
            live = None if not ms else any(m["killed"] for m in ms)
            mutable = bool(ms) and any(m.get('mutable', m['killed'] is not None) for m in ms)
            where = "" if u.own else u.target
            file = self.m.cfg.rel(u.fn.__code__.co_filename)
            eq = next(((w, why) for w, why, _ in declared if _at(file, u.site.line, w)), None)
            if eq:
                used.add(eq[0])
            rows.append(dict(line=u.site.line, text=u.site.text, realized=is_real, live=live, mutable=mutable,
                             where=where, mutants=ms or [], equivalent=eq[1] if eq and not live else None))
            if not is_real:
                continue
            if eq and not live:   # design 3.6: an equivalent mutant needs a reason; with one it blocks nothing
                info.append(f"equivalent: {file}:{u.site.line} {u.site.text[:40]} ({eq[1]})")
                continue
            if eq and live:
                info.append(f"{file}:{u.site.line} is declared equivalent but a mutant is killed there: "
                            "the equivalent= entry can go")
            n += 1
            if live:
                k += 1
            elif ms and not mutable:
                grey.append(f"not mutable: {u.target.replace(':', '.')} L{u.site.line} {u.site.text} "
                            f"({ms[0]['why'][13:]})")
            elif ms:
                survivors = [m for m in ms if m['killed'] is False]
                unknown = [m for m in ms if m['killed'] is None and m.get('mutable')]
                if survivors:
                    grey.append(f"not live: no item fails when {survivors[0]['label']} ({file}:{u.site.line})")
                if unknown:
                    grey.append(f"not measured: {unknown[0]['label']} ({file}:{u.site.line}): {unknown[0]['why']}")
            elif not pr["mutable"].get(u.target, True):
                grey.append(f"not mutable: {u.target.replace(':', '.')} L{u.site.line} {u.site.text}")
            else:
                grey.append(f"not measured: {u.target.replace(':', '.')} L{u.site.line} {u.site.text} "
                            "(no applicable mutant)")
        for w, why, scope in declared:
            if w not in used and (scope == "home" or home is rule.homes[0]):
                info.append(f"equivalent={w!r} names no decision site of {home.target} or what it calls")
        if not real:
            grey.append('nothing to require: 0 realized decision sites -> bind the real decision or declare why equivalent')
            callees = len({u.target for u in pr["uses"] if not u.own})
            info.append(f"no decision site turns on {rule.id}'s cells in {home.target} or the {callees} functions "
                        "with sites it calls: liveness has nothing to require")
        for u in listed:
            if u.named and not u.reached and not any(_at(self.m.cfg.rel(u.fn.__code__.co_filename), u.site.line, w) for w, _, _ in declared):
                grey.append(f'unreached site {self.m.cfg.rel(u.fn.__code__.co_filename)}:{u.site.line} {u.site.text} -> add a reaching row or equivalent reason')
        grey += self.two_names(rule, home, realized_keys, info)
        res = dict(kind="live", verdict="grey" if grey else "ok", red=[], grey=grey, info=info, k=k, n=n,
                   sites=rows, mutants=muts, seconds=round(time.perf_counter() - t0, 4))
        self.results[(rule.id, home.target, "live")] = res
        return res

    def two_names(self, rule, home, mine: set, info: list) -> list[str]:
        """Design 3.2 grouping by computation: a rule of another key homed at the same function that
        realizes one of this rule's sites may be the same decision under a second name. Two rules
        that only share the function (two decisions in one function) are not grouped. A distinct or
        `uses` between them answers the question."""
        out = []
        for q in self.m.rules.values():
            if q.id in self.m.superseded_by or rule.id in self.m.superseded_by:
                continue
            if q.decides == rule.decides or not any(h.target == home.target for h in q.homes):
                continue
            if self.m.distinct_pair(rule.id, q.id) or q.id in rule.uses or rule.id in q.uses:
                continue
            qh = next(h for h in q.homes if h.target == home.target)
            shared = sorted({u.key for u in self.realized(q, qh)} & mine)
            if shared:
                u = next(x for x in self.probe(rule, home)["uses"] if x.key == shared[0])
                out.append(f"one decision under two names? {rule.id} / {q.id} both turn on "
                           f"{u.target.replace(':', '.')} L{u.site.line} {u.site.text[:40]} "
                           "(merge the keys, or say distinct)")
            else:
                info.append(f"{rule.id} and {q.id} share {home.target} but turn on different sites")
        return out
