"""Known-bad, always on (FG-811, M1): every model is made wrong on purpose, one change at a
time, and checked again. A mutant no check catches is reported, so a model whose checks
cannot fail is visible. Runs in `check --full` and `release` (part kind `mutate`).

Operators, one mutant per site:
  drop guard         one `need(...)` statement of the model file is removed;
  widen guard        one conjunct of `need(A and B, ...)` is dropped, or one `<` / `>` in its
                     condition becomes `<=` / `>=`;
  remove transition  an action is wrapped so that one field family it writes keeps its value;
  end unreachable    every action is wrapped to refuse a step that newly sets a declared end.

A mutant is caught when its check (explain=False) has a conflict or model error
fingerprint the original does not have; equivalent when its graph equals the original's
(not listed); unknown when its search is capped; otherwise it survives and is one model
warning. A capped original decides nothing: UNKNOWN.
"""
from __future__ import annotations

import ast
import functools
from collections import Counter
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable

from .checks import CONFLICT, ERROR_CLS, WARNING, check_model, make_finding, merge
from .explore import Bounds, Graph
from .model import Loaded, Model, ModelError, Refused, load_model
from .parts import PartContext, PartResult, part_digest, register
from .routes import model_error_result


@dataclass(frozen=True)
class Mutant:
    op: str                          # drop guard | widen guard | remove transition | end unreachable
    what: str                        # the change, with its line
    subject: str                     # the change without a line (the survivor's fingerprint subject)
    line: int | None
    sources: tuple
    transform: Callable | None       # an AST transform of the model file (guards)
    wrap: Callable | None            # Model -> Model (transitions, ends)


@dataclass
class MutationReport:
    complete: bool
    findings: list                   # one model warning per surviving mutant
    outcomes: list                   # every mutant: op, what, outcome, the new findings that caught it
    unknown: list = field(default_factory=list)


# ---------------------------------------------------------------------- guard sites (AST)
def _pos(node):
    return (node.lineno, node.col_offset, node.end_lineno, node.end_col_offset)


def _is_need(node):
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "need"


def _reason(call):
    if len(call.args) > 1 and isinstance(call.args[1], ast.Constant) and isinstance(call.args[1].value, str):
        return call.args[1].value
    for k in call.keywords:
        if k.arg == "reason" and isinstance(k.value, ast.Constant):
            return str(k.value.value)
    return "refused"


def _need_statements(tree):
    """(statement, need call, enclosing function) of every `need(...)` statement, in line order."""
    out = []

    def visit(node, fname):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                visit(child, child.name)
                continue
            if isinstance(child, ast.Expr) and _is_need(child.value):
                out.append((child, child.value, fname))
            visit(child, fname)
    visit(tree, None)
    return sorted(out, key=lambda x: _pos(x[0]))


class _Edit(ast.NodeTransformer):
    """Replace the one node of a type at a position (the same source parses the same way)."""

    def __init__(self, kind, pos, edit):
        self.kind, self.pos, self.edit, self.done = kind, pos, edit, False

    def generic_visit(self, node):
        node = super().generic_visit(node)
        if isinstance(node, self.kind) and _pos(node) == self.pos and not self.done:
            self.done = True
            return self.edit(node)
        return node


def _transform(kind, pos, edit):
    """The load transform of one guard mutant."""
    def apply(tree):
        t = _Edit(kind, pos, edit)
        tree = t.visit(tree)
        if not t.done:
            raise RuntimeError(f"mutation site {kind.__name__} at {pos} not found in the model file")
        return tree
    return apply


def _drop_statement(node):
    """The `need(...)` statement becomes `pass`."""
    return ast.copy_location(ast.Pass(), node)


def guard_mutants(model: Model) -> list[Mutant]:
    tree = ast.parse(Path(model.path).read_text(encoding="utf-8"))
    sources = {a.name: a.source for a in model.actions}
    out = []
    seen = Counter()
    for stmt, call, fname in _need_statements(tree):
        reason = _reason(call)
        src = next((k.value.value for k in call.keywords if k.arg == "source" and isinstance(k.value, ast.Constant)),
                   sources.get(fname))
        where = f"{fname}, line {call.lineno}"
        base = f"{reason!r} in {fname}"
        seen[base] += 1
        tag = "" if seen[base] == 1 else f" #{seen[base]}"
        out.append(Mutant("drop guard", f"drop guard {reason!r} ({where})", f"drop guard {base}{tag}", call.lineno,
                          (src,), _transform(ast.Expr, _pos(stmt), _drop_statement), None))
        if not call.args:
            continue
        cond = call.args[0]
        if isinstance(cond, ast.BoolOp) and isinstance(cond.op, ast.And):
            for k, part in enumerate(cond.values):
                text = ast.unparse(part)
                out.append(Mutant("widen guard", f"widen guard {reason!r} ({where}): drop `{text}`",
                                  f"widen guard {base}{tag}: drop {text}", call.lineno, (src,),
                                  _transform(ast.BoolOp, _pos(cond), functools.partial(_without, k)), None))
        for node in ast.walk(cond):
            if not isinstance(node, ast.Compare):
                continue
            for j, op in enumerate(node.ops):
                if isinstance(op, (ast.Lt, ast.Gt)):
                    sym, wide = ("<", "<=") if isinstance(op, ast.Lt) else (">", ">=")
                    text = ast.unparse(node)
                    out.append(Mutant("widen guard", f"widen guard {reason!r} ({where}): `{sym}` -> `{wide}` in `{text}`",
                                      f"widen guard {base}{tag}: {sym} -> {wide} in {text}", call.lineno, (src,),
                                      _transform(ast.Compare, _pos(node), functools.partial(_widen, j)), None))
    return out


def _without(k, node):
    rest = [v for n, v in enumerate(node.values) if n != k]
    if len(rest) == 1:
        return rest[0]
    return ast.copy_location(ast.BoolOp(ast.And(), rest), node)


def _widen(j, node):
    ops = list(node.ops)
    ops[j] = ast.LtE() if isinstance(ops[j], ast.Lt) else ast.GtE()
    return ast.copy_location(ast.Compare(node.left, ops, node.comparators), node)


# ---------------------------------------------------------------------- transitions and ends
def _keep(fn, keys):
    @functools.wraps(fn)
    def kept(s, *args):
        old = [s[k] for k in keys]
        fn(s, *args)
        for k, v in zip(keys, old):
            s[k] = v
    return kept


def _refuse_end(fn, keys, family, value):
    @functools.wraps(fn)
    def guarded(s, *args):
        before = [s[k] for k in keys]
        fn(s, *args)
        if any(b != value and s[k] == value for k, b in zip(keys, before)):
            raise Refused(f"mutant: {family}={value!r} made unreachable", None, (None, None))
    return guarded


def _families_written(model: Model, graph: Graph):
    """action name -> the field families its explored steps change, in declaration order."""
    fam = [f.family for f in model.fields]
    written = {}
    for i, row in enumerate(graph.out):
        base = graph.states[i]
        for c, v in enumerate(row):
            if v < 0:
                continue
            succ = graph.raw_successor(i, c)
            name = graph.calls[c].action.name
            for p in range(len(base)):
                if base[p] != succ[p]:
                    written.setdefault(name, set()).add(fam[p])
    order = list(dict.fromkeys(fam))
    return {a.name: [f for f in order if f in written.get(a.name, ())] for a in model.actions}


def transition_mutants(model: Model, graph: Graph) -> list[Mutant]:
    out = []
    for a in model.actions:
        for family in _families_written(model, graph)[a.name]:
            keys = [f.key for f in model.fields if f.family == family]

            def wrap(m, _a=a.name, _keys=keys):
                return m.replace_actions([act if act.name != _a else _replace_fn(act, _keep(act.fn, _keys))
                                          for act in m.actions])
            what = f"remove transition: {a.name} keeps {family} unchanged"
            out.append(Mutant("remove transition", f"{what} (line {a.line})", what, a.line, (a.source,), None, wrap))
    return out


def end_mutants(model: Model) -> list[Mutant]:
    out = []
    for family, values in model.terminals.items():
        keys = [f.key for f in model.fields if f.family == family]
        for value in values:
            def wrap(m, _keys=keys, _family=family, _value=value):
                return m.replace_actions([_replace_fn(act, _refuse_end(act.fn, _keys, _family, _value))
                                          for act in m.actions])
            what = f"make end {family}={value!r} unreachable"
            out.append(Mutant("end unreachable", what, what, None, (model.terminal_sources.get(family),), None, wrap))
    return out


def _replace_fn(action, fn):
    return replace(action, fn=fn)


def mutants(loaded: Loaded, graph: Graph) -> list[Mutant]:
    model = loaded.model
    return guard_mutants(model) + transition_mutants(model, graph) + end_mutants(model)


# ---------------------------------------------------------------------- running them
def _same_graph(a: Graph, b: Graph) -> bool:
    return (a.states == b.states and a.out == b.out and a.refusals == b.refusals and a.perm == b.perm
            and a.complete == b.complete)


def _blocking(report):
    return {f.id: f for f in report.findings if f.cls in (CONFLICT, ERROR_CLS)}


def run_mutants(loaded: Loaded, bounds: Bounds, *, progress=None) -> MutationReport:
    """Check the original and every mutant (explain=False) and sort the mutants."""
    model = loaded.model
    original = check_model(loaded, bounds, explain=False)
    if not original.graph.complete:
        return MutationReport(False, [], [], ["mutation"])
    known = _blocking(original)
    findings, outcomes, unknown = [], [], []
    mid = model.id or model.name
    for n, mutant in enumerate(mutants(loaded, original.graph)):
        if progress is not None:
            progress({"mutant": n + 1})
        if mutant.transform is not None:
            try:
                mloaded = load_model(model.path, model.root, transform=mutant.transform)
            except ModelError as err:     # the mutant itself is a model error the original does not have
                outcomes.append({"op": mutant.op, "what": mutant.what, "outcome": "caught",
                                 "by": [f"MODEL ERROR {err}"]})
                continue
        else:
            mloaded = Loaded(mutant.wrap(model), loaded.reads)
        report = check_model(mloaded, bounds, explain=False)
        if not report.graph.complete:
            unknown.append(mutant.what)
            outcomes.append({"op": mutant.op, "what": mutant.what, "outcome": "unknown", "by": []})
            continue
        new = [f for fid, f in _blocking(report).items() if fid not in known]
        if new:
            outcomes.append({"op": mutant.op, "what": mutant.what, "outcome": "caught",
                             "by": [f"{f.kind} {f.subject}" for f in new]})
        elif _same_graph(original.graph, report.graph):
            outcomes.append({"op": mutant.op, "what": mutant.what, "outcome": "equivalent", "by": []})
        else:
            outcomes.append({"op": mutant.op, "what": mutant.what, "outcome": "survived", "by": []})
            tail = "without it" if mutant.op == "drop guard" else "with it"
            findings.append(make_finding(
                "MUTANT SURVIVES", WARNING, mid, mutant.subject,
                f"mutant survives: {mutant.what}: no rule or generic check fails {tail}",
                sources=mutant.sources, detail={"op": mutant.op, "what": mutant.what}, line=mutant.line))
    return MutationReport(not unknown, merge(findings), outcomes, ["mutation"] if unknown else [])


# ---------------------------------------------------------------------- the part
def mutate_part(ctx: PartContext) -> PartResult:
    """Load the model and run every mutant (only with --full and in release)."""
    root, spec = Path(ctx.root), ctx.spec
    max_states = spec.option("max_states", Bounds().max_states)
    try:
        loaded = load_model(ctx.path, root)
    except ModelError as err:
        return model_error_result(spec, root, err, err.reads)
    report = run_mutants(loaded, Bounds(max_states),
                         progress=lambda d: ctx.progress({"model": spec.model, "kind": spec.kind, **d}))
    counts = Counter(o["outcome"] for o in report.outcomes)
    info = {"loaded": True, "complete": report.complete, "unknown": list(report.unknown),
            "mutants": report.outcomes, "counts": {k: counts[k] for k in sorted(counts)}}
    reads = list(loaded.reads)
    return PartResult(spec.kind, spec.model, part_digest(root, spec, reads), report.complete,
                      [f.to_json() for f in report.findings], info, reads, [])


register("mutate", mutate_part, full_only=True)
