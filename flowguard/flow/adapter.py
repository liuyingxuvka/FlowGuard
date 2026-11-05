"""Bind flow witnesses to the one native producer and existing conformance comparator."""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
import json
from pathlib import Path
import random
from typing import Callable

from ..conformance import ConformanceRule, default_conformance_rules, replay_trace
from ..export import to_jsonable
from ..native import session
from ..native.capture import plain
from ..native.inputs import footprint_identity
from ..replay import ReplayInput, ReplayObservation
from ..trace import Trace, TraceStep
from .explore import Refusal
from .model import ModelError

_CONSTRUCT = "<native construction>"
_SCOPE = "finite native calls; no original-conflict closure proof"


def fields(snapshot: dict, *, names=None, receiver="system") -> dict:
    """A finite scalar/container view of selected fields, without invoking SUT getters.

    A project with object-valued fields supplies its own projection over the complete
    snapshot graph; an unavailable view is never replaced with a default value.
    """
    graph = snapshot["graph"]
    objects = graph["nodes"][graph["root"]["ref"]]
    value = next(value for name, value in objects["items"] if name == receiver)
    node = graph["nodes"][value["ref"]]
    values = dict(node["attributes"])
    selected = tuple(values) if names is None else tuple(names)
    return {name: plain({"root": values[name], "nodes": graph["nodes"]}) for name in selected}


def _rename(value, names):
    if isinstance(value, str):
        return names.get(value, value)
    if isinstance(value, dict):
        return {_rename(k, names): _rename(v, names) for k, v in value.items()}
    if isinstance(value, (tuple, list, set, frozenset)):
        return type(value)(_rename(v, names) for v in value)
    return value


def trace_calls(graph, call_indices) -> Trace:
    """Convert concrete call indices without re-running model or production code."""
    index = {state: i for i, state in enumerate(graph.states)}
    state = graph.init
    steps = []
    for number, ci in enumerate(call_indices, 1):
        call = graph.calls[ci]
        representative, permutation = (graph.sym.canon(state) if graph.sym is not None else (state, 0))
        i = index[representative]
        if i >= len(graph.out):
            raise ModelError(f"native witness step {number} starts in an unexplored model state")
        c = graph.sym.call_perm[permutation][ci] if graph.sym is not None else ci
        outcome = graph.outcome(i, c)
        old = dict(zip(graph.keys, state))
        if isinstance(outcome, Refusal):
            if -1 - graph.out[i][c] < 2:
                raise ModelError(f"native witness step {number} has a capped or erroneous model outcome")
            output, label, reason = None, "refusal", outcome.reason
        else:
            successor = graph.raw_successor(i, c)
            state = (graph.sym.apply(graph.sym.inv[permutation], successor)
                     if graph.sym is not None else successor)
            output = graph.outputs.get((i, c))
            if graph.sym is not None:
                output = _rename(output, graph.sym.maps[graph.sym.inv[permutation]])
            label, reason = "success", ""
        steps.append(TraceStep(None, call.action.name, dict(zip(call.action.params, call.args)),
                               output, old, dict(zip(graph.keys, state)), label, reason))
    metadata = {"model": graph.model.id or graph.model.name}
    if graph.model.__dict__.get('_saved_sample_context') is not None:
        metadata['saved_sample'] = graph.model.__dict__['_saved_sample_context']
    return Trace(tuple(steps), dict(zip(graph.keys, graph.init)), metadata=metadata)


def witness_trace(graph, state: int, last=None, to=None) -> Trace:
    trace = trace_calls(graph, graph.path_calls(state, last, to))
    if last is None and trace.final_state != dict(zip(graph.keys, graph.end_state(state, to))):
        raise ModelError("the concrete flow witness did not reach its recorded end state")
    return trace


@dataclass
class NativeCheckpoint:
    prefix: tuple
    snapshot: dict
    footprint: dict
    start: dict


@dataclass
class AdapterBinding:
    model: object
    spec: dict
    state: Callable
    operations: dict
    output: Callable | None = None
    outcome: Callable | None = None
    dispatch: Callable | None = None
    start: dict = field(default_factory=dict)
    prefix: tuple = ()

    def __post_init__(self):
        if not callable(self.state):
            raise ModelError("adapter state projection must be callable")
        self.spec = copy.deepcopy(dict(self.spec))
        self.operations = dict(self.operations)
        self.start, self.prefix = copy.deepcopy(self.start), copy.deepcopy(self.prefix)
        for action, operation in self.operations.items():
            if not isinstance(action, str) or not isinstance(operation, (str, dict)):
                raise ModelError("adapter operations map model action names to native names or recipes")
        self.spec.setdefault("capture_shape", {"wire": 2, "queries": {}})

    def native_spec(self):
        spec = copy.deepcopy(self.spec)
        if "root" not in spec:
            if self.model.root is None:
                raise ModelError("adapter needs the loaded model's project root")
            spec["root"] = str(self.model.root)
        return spec

    def recipe(self, value: ReplayInput) -> dict:
        if not isinstance(value, ReplayInput):
            raise TypeError("native dispatch accepts ReplayInput, never a TraceStep/oracle")
        target = self.operations[value.function_name]
        target = {"name": target} if isinstance(target, str) else dict(target)
        recipe = (dict(self.dispatch(value)) if self.dispatch is not None else
                  {**target, "kwargs": {**copy.deepcopy(target.get("kwargs", {})),
                                         **copy.deepcopy(value.function_input)}})
        if (recipe.get("name") != target.get("name") or
                recipe.get("receiver", "system") != target.get("receiver", "system")):
            raise ModelError("adapter dispatch changed its declared native operation")
        try:
            json.dumps(recipe, allow_nan=False)
        except (TypeError, ValueError) as error:
            raise ModelError(f"adapter dispatch needs a finite native input recipe: {error}") from error
        return recipe

    def execute(self, inputs, *, timeout=30) -> dict:
        """The same production route for conformance, walks, and later replay/probe callers."""
        recipes = [*copy.deepcopy(self.prefix), *(self.recipe(value) for value in inputs)]
        return session.replay(self.native_spec(), recipes, self.start, timeout=timeout)

    def snapshot(self, run) -> NativeCheckpoint:
        evidence = run.native.get("rule_captures", {}).get("native_evidence", {})
        if evidence.get("status") != "current" or "footprint" not in run.native:
            raise session.UnsupportedWorld("checkpoint needs current complete native observations")
        recipes = (*copy.deepcopy(self.prefix), *(self.recipe(value) for value in run.inputs))
        return NativeCheckpoint(recipes, copy.deepcopy(run.native["final"]),
                                copy.deepcopy(run.native["footprint"]), copy.deepcopy(self.start))

    def restore(self, checkpoint: NativeCheckpoint, *, tail=()) -> dict:
        if not isinstance(checkpoint, NativeCheckpoint) or footprint_identity(checkpoint.footprint) is None:
            raise session.UnsupportedWorld("checkpoint is stale or its source evidence is missing")
        # The native owner validates complete snapshot reconstruction from public calls.
        # Neither model state nor model output enters the constructor/operation inputs.
        return session.restore(self.native_spec(), checkpoint.prefix, checkpoint.snapshot,
                               checkpoint.start, tuple(self.recipe(value) for value in tail))


@dataclass
class AdapterRun:
    status: str
    inputs: tuple
    trace: Trace
    native: dict
    conformance: object = None
    reason: str = ""
    seed: int | None = None
    step_budget: int | None = None

    def to_dict(self):
        return {"schema": "flowguard.native-conformance.v1", "status": self.status,
                "scope": _SCOPE, "reason": self.reason, "trace": self.trace.to_dict(),
                "inputs": [{"function": s.function_name, "arguments": to_jsonable(s.function_input),
                            "external_input": to_jsonable(s.external_input)} for s in self.inputs],
                "conformance": self.conformance.to_dict() if self.conformance is not None else None,
                "native": self.native, "seed": self.seed, "step_budget": self.step_budget}


class _RecordedAdapter:
    """Present already captured facts to replay_trace; this class executes no SUT code."""
    def __init__(self, graph, binding, actual, inputs):
        self.graph, self.binding, self.actual, self.inputs = graph, binding, actual, inputs
        self.offset = len(binding.prefix)
        self.position = -1
        self.last = None

    def project(self, snapshot):
        state = dict(self.binding.state(snapshot))
        domains = {f.key: f.domain for f in self.graph.model.fields}
        if set(state) != set(domains):
            raise ValueError(f"state projection is not total: model={list(domains)!r}, actual={list(state)!r}")
        for key, value in state.items():
            if value not in domains[key]:
                raise ValueError(f"real {key!r}={value!r} is outside the model domain {domains[key]!r}")
        return state

    def reset(self, initial_state):
        self.position = -1                # expected initial_state is never production input
        self.last = None

    def observe_state(self):
        snapshot = (self.actual["steps"][self.offset - 1]["after"] if self.offset else self.actual["initial"])
        return self.last.observed_state if self.last is not None else self.project(snapshot)

    def observe_output(self):
        return self.last.observed_output if self.last is not None else None

    def apply_step(self, value: ReplayInput):
        if self.position == -1:
            self.position = 0
            snapshot = (self.actual["steps"][self.offset - 1]["after"] if self.offset else self.actual["initial"])
            failed = next((step for step in self.actual['steps'][:self.offset] if step['outcome'] != 'success'), None)
            self.last = ReplayObservation(_CONSTRUCT, None, self.project(snapshot),
                failed['outcome'] if failed else 'construct',
                failed.get('exception',{}).get('message','') if failed and failed.get('exception') else '')
            return self.last
        if value != self.inputs[self.position]:
            raise ValueError("conformance input differs from its native captured input")
        row = self.actual["steps"][self.offset + self.position]
        self.position += 1
        output = self.binding.output(row) if self.binding.output is not None else plain(row["value"])
        outcome = self.binding.outcome(row) if self.binding.outcome is not None else row["outcome"]
        if outcome not in ("success", "refusal", "crash"):
            raise ValueError(f"unknown projected native outcome {outcome!r}")
        self.last = ReplayObservation(value.function_name, output, self.project(row["after"]), outcome,
                                      row.get("exception", {}).get("message", "") if row.get("exception") else "",
                                      metadata={"native_outcome": row["outcome"], "call": row["call"]})
        return self.last


def _operation_in_scope(covers, ancestry, entry, declaration):
    """Select a public binding using its actual declaring class and receiver MRO.

    Class/file scopes include that class's inherited surface. A method scope
    names its real declaration; a sibling with the same prefix is unrelated.
    None means provenance cannot decide membership, never that it is absent.
    """
    from ..map.flow_sources import binding_matches

    if not covers:
        return True  # An unscoped binding explicitly keeps the whole receiver.
    if ancestry is None:
        return None
    owner = next((i for i, row in enumerate(ancestry) if row["owner"] == entry["owner"]), None)
    if owner is None:
        return None
    uncertain = False
    if declaration is not None and not any(row["owner"] == declaration["owner"] for row in ancestry):
        # A constructor may return another supported class. Its actual surface
        # cannot silently disappear from a covered declared class's inventory.
        for path, symbol in covers:
            if "." not in symbol and (not symbol or symbol == declaration["symbol"]):
                if declaration["path"] is None or Path(declaration["path"]).resolve() == path:
                    uncertain = True
    for path, symbol in covers:
        if "." in symbol:
            if symbol.rsplit(".", 1)[1] != entry["name"]:
                continue
            candidates = ancestry[owner:owner + 1]
        else:
            # A covered base class does not acquire new methods declared by a
            # subclass, while a covered receiver includes its inherited methods.
            candidates = ancestry[:owner + 1]
        for source in candidates:
            if symbol and (symbol.rsplit(".", 1)[0] if "." in symbol else symbol) != source["symbol"]:
                continue
            if source["path"] is None:
                uncertain = True
                continue
            # Compare paths as paths (including Windows drive/case semantics),
            # then reuse the existing symbol-boundary matcher without a drive colon.
            anchor = "#" + source["symbol"] + "." + entry["name"]
            if Path(source["path"]).resolve() == path and binding_matches(":" + symbol, anchor):
                return True
    return None if uncertain else False


def _missing_operations(binding, actual):
    declared = set()
    for action in binding.model.actions:
        if action.name not in binding.operations:
            return [f"model action {action.name} has no native operation"], []
        target = binding.operations[action.name]
        target = {"name": target} if isinstance(target, str) else target
        declared.add((target.get("receiver", "system"), target["name"]))
    declared.update((row.get("receiver", "system"), row["name"]) for row in binding.prefix if "name" in row)
    # Loaded covers belong to the model project even when execution starts in a
    # nested module. Standalone models take their explicitly supplied native root.
    root = Path(binding.model.root or binding.native_spec()["root"])
    covers = [(Path(root, file.replace("\\", "/")).resolve(), symbol)
              for cover in binding.model.covers for file, _, symbol in [cover.partition(":")]]
    missing, unknown = [], []
    sources = actual.get("inventory_sources", {})
    declarations = actual.get("inventory_bindings", {})
    for receiver, entries in actual["inventory"].items():
        for entry in entries:
            if entry["kind"] == "property" or (receiver, entry["name"]) in declared:
                continue
            selected = _operation_in_scope(covers, sources.get(receiver), entry, declarations.get(receiver))
            operation = f"{receiver}.{entry['name']}"
            if selected is None:
                unknown.append("native operation scope is unavailable: " + operation)
            elif selected:
                missing.append(operation)
    return missing, unknown


def check_trace(graph, trace: Trace, *, binding=None, timeout=30) -> AdapterRun:
    binding = binding or graph.model.adapter_binding
    if binding is None:
        raise ModelError("the model has no native adapter binding")
    inputs = tuple(ReplayInput.from_trace_step(step) for step in trace.steps)
    try:
        actual = binding.execute(inputs, timeout=timeout)
    except session.UnsupportedWorld as error:
        evidence = {"status": error.evidence_status, "message": str(error)}
        for name in ("outcome", "exception"):
            value = getattr(error, name, None)
            if value is not None:
                evidence[name] = value
        return AdapterRun("unknown", inputs, trace, {"evidence_error": evidence}, reason=str(error))
    # A native engine fault propagates to the caller; it is not an SUT crash/drift.
    evidence = actual.get("rule_captures", {}).get("native_evidence", {})
    if evidence.get("status") != "current" or "inventory" not in actual:
        return AdapterRun("unknown", inputs, trace, actual, reason="native capture or operation inventory is incomplete")
    missing, scope_limits = _missing_operations(binding, actual)
    construction = TraceStep(None, _CONSTRUCT, None, None, trace.initial_state, trace.initial_state, "construct")
    compared = Trace((construction, *trace.steps), trace.initial_state, metadata=trace.metadata)
    inventory_rule = ConformanceRule("operation_inventory", "Native public operations are modeled.",
                                    lambda expected, observed: "unmodeled code operation: " + ", ".join(missing)
                                    if expected.function_name == _CONSTRUCT and missing else None)
    try:
        report = replay_trace(compared, _RecordedAdapter(graph, binding, actual, inputs),
                              rules=(inventory_rule, *default_conformance_rules()))
    except session.NativeEngineError:
        raise
    except Exception as error:
        raise session.NativeEngineError(
            f"native conformance judgment raised {type(error).__name__}: {error}", phase="judgment") from error
    limits = scope_limits + [reason for reasons in actual.get("inventory_limits", {}).values() for reason in reasons]
    status = "drift" if not report.ok else "unknown" if limits else "conformant"
    return AdapterRun(status, inputs, trace, actual, report, "; ".join(limits))


def walk(graph, *, steps: int, seed: int, binding=None, timeout=30) -> AdapterRun:
    """A declared finite model-call walk, driven through the same binding/capture."""
    if not isinstance(steps, int) or steps < 0:
        raise ValueError("walk steps must be a nonnegative integer")
    if steps and not graph.calls:
        raise ValueError("a nonempty walk needs a modeled operation")
    if not graph.complete:
        return AdapterRun("unknown", (), Trace((), dict(zip(graph.keys, graph.init))), {},
                          reason="model search is incomplete; no complete native walk oracle",
                          seed=seed, step_budget=steps)
    rng = random.Random(seed)
    calls = [rng.randrange(len(graph.calls)) for _ in range(steps)] if graph.calls else []
    result = check_trace(graph, trace_calls(graph, calls), binding=binding, timeout=timeout)
    result.seed, result.step_budget = seed, steps
    return result
