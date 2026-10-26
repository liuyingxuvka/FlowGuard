"""Each model sits under PARENT, its one importer, COMPONENTS, its anchor's owner or system; nesting mistakes are errors.

Each event adds one shape to a small tree. ``resolve`` below is the design: the
placement order and the component-parent checks. Conformance writes the same shape
as a real project and reads the placement, the finding codes and the parent
component's models from flowguard/map/tree.py.
"""
from dataclasses import dataclass, replace
import json
from pathlib import Path
import shutil
import tempfile

from flowguard import FunctionResult, Invariant, InvariantResult, ReplayObservation, Workflow, replay_trace, select_covering_traces
from flowguard.conformance import projected_output_matches, projected_state_matches
from flowguard.explorer import Explorer
from flowguard.map.inventory import build_inventory
from flowguard.map.tree import build_tree, component_parent_findings

MODEL_ID = "tree_resolution"
PARENT = "map-file"
IMPLEMENTED_BY = {
    "BuildTree": "flowguard/map/tree.py:build_tree",
    "ComponentParents": "flowguard/map/tree.py:component_parent_findings",
}
TESTED_BY = {
    "explicit_parent_wins": [
        "tests/test_flowguard_map_contracts.py:test_child_import_of_its_explicit_parent_preserves_tree_and_impact",
    ],
    "single_importer_is_parent": [
        "tests/test_flowguard_map_contracts.py:test_model_tree_parent_defaults_and_nesting_warnings",
    ],
    "local_import_is_not_a_parent": [
        "tests/test_flowguard_map.py:test_change_selects_a_child_that_imports_its_parent_in_a_function",
    ],
    "components_then_anchor_then_system": [
        "tests/test_flowguard_map_contracts.py:test_model_tree_anchor_components_and_root_defaults",
    ],
    "nesting_mistakes_are_errors": [
        "tests/test_flowguard_map_contracts.py:test_model_tree_parent_defaults_and_nesting_warnings",
        "tests/test_flowguard_map_contracts.py:test_old_mesh_mistakes_are_tree_errors",
    ],
    "component_parent_same_layer": [
        "tests/test_flowguard_map_contracts.py:test_component_parent_mistakes_are_errors",
    ],
    "component_parents_known_and_acyclic": [
        "tests/test_flowguard_map_contracts.py:test_component_parent_mistakes_are_errors",
    ],
    "child_component_models_count_for_parent": [
        "tests/test_map_views.py:test_component_parent_nests_and_rolls_up",
    ],
}

# Base tree: components app and lib (layer core) and ui (layer top); model m is the one placed.
# A model is (id, PARENT or None, COMPONENTS, first anchor's component, imported at top level by, imported in a function by).
SHAPES = {
    "cousin_owner": {"models": [("m", "left", ["app"], "app", (), ()), ("m2", "right", ["app"], "app", (), ())],
                     "sub": [("left", "core", "app"), ("right", "core", "app")]},
    "explicit_parent": {"models": [("p", None, ["app"], "app", (), ()), ("m", "p", [], "app", (), ())]},
    "single_importer": {"models": [("p", None, ["app"], "app", ("m",), ()), ("m", None, ["lib"], "app", (), ())]},
    "local_importer": {"models": [("p", None, ["app"], "app", (), ("m",)), ("m", None, ["app"], "app", (), ())]},
    "components_first": {"models": [("m", None, ["lib"], "app", (), ())]},
    "anchor_owner": {"models": [("m", None, [], "lib", (), ())]},
    "no_hint": {"models": [("m", None, [], None, (), ())]},
    "unknown_parent": {"models": [("m", "absent", ["app"], "app", (), ())]},
    "parent_cycle": {"models": [("m", "m2", ["app"], "app", (), ()), ("m2", "m", ["app"], "app", (), ())]},
    "import_mismatch": {"models": [("p", None, ["app"], "app", ("m",), ()), ("m", "app", [], "app", (), ())]},
    "outside_anchor": {"models": [("p", None, ["app"], "app", (), ()), ("m", "p", [], "lib", (), ())]},
    "duplicate_child_anchor": {"models": [("p", None, ["app"], "app", (), ()), ("m", "p", [], "app", (), ()),
                                          ("m2", "p", [], "app", (), ())]},
    "component_child": {"models": [("m", None, ["sub"], "sub", (), ())], "sub": [("sub", "core", "app")]},
    "component_child_other_layer": {"models": [("m", None, ["sub"], "sub", (), ())], "sub": [("sub", "top", "app")]},
    "component_parent_unknown": {"models": [("m", None, ["sub"], "sub", (), ())], "sub": [("sub", "core", "absent")]},
    "component_parent_cycle": {"models": [("m", None, ["sub"], "sub", (), ())],
                               "sub": [("sub", "core", "sub2"), ("sub2", "core", "sub")]},
}
LAYERS = {"app": "core", "lib": "core", "ui": "top"}


@dataclass(frozen=True)
class State:
    event: str = ""
    placement: tuple = ()            # (parent, kind, source) of model m
    codes: tuple = ()                # sorted "level:code" findings of the tree and the component parents
    parent_models: tuple = ()        # models that count for component app (component_child only)


def resolve(event, defect=""):
    """The placement order and the nesting checks, applied to one shape."""
    shape = SHAPES[event]
    models = {mid: (parent, components, anchor, imported_by, local_by)
              for mid, parent, components, anchor, imported_by, local_by in shape["models"]}
    components = dict(LAYERS, **{cid: layer for cid, layer, _ in shape.get("sub", ())})
    parents = {cid: parent for cid, _, parent in shape.get("sub", ())}
    codes = set()

    def default(mid, allow_model=True):
        _, declared, anchor, _, _ = models[mid]
        importers = [other for other, row in models.items() if mid in row[3]]
        if defect == "local_import_makes_parent":
            importers += [other for other, row in models.items() if mid in row[4]]
        if defect == "prefers_components_over_importer" and declared:
            return declared[0], "component", "COMPONENTS"
        if allow_model and len(importers) == 1:
            return importers[0], "model", "import"
        if declared:
            return declared[0], "component", "COMPONENTS"
        if anchor and defect != "skips_anchor_owner":
            return anchor, "component", "anchor"
        return "system", "system", "default"

    placed = {}
    for mid, (parent, declared, anchor, _, _) in models.items():
        placed[mid] = default(mid)
        if parent is not None and defect != "ignores_explicit_parent":
            if parent in models or parent in components or parent == "system":
                kind = "model" if parent in models else "component" if parent in components else "system"
                placed[mid] = (parent, kind, "PARENT")
            else:
                codes.add("parent_unknown")
            importers = [other for other, row in models.items() if mid in row[3]]
            if len(importers) == 1 and importers[0] != parent:
                codes.add("parent_import_mismatch")
    for mid in models:
        seen, current = [], mid
        while current in placed and placed[current][1] == "model":
            if current in seen:
                codes.add("parent_cycle")
                placed[mid] = default(mid, allow_model=False)
                break
            seen.append(current)
            current = placed[current][0]
    by_parent = {}
    for mid, (parent, kind, source) in placed.items():
        if kind == "model" and source in {"PARENT", "import"}:
            by_parent.setdefault((parent, models[mid][2]), []).append(mid)
    for mid in models:
        current, seen, declared = mid, set(), set(models[mid][1])
        while current in models and current not in seen:
            seen.add(current)
            declared.update(models[current][1])
            parent, kind, _ = placed[current]
            if kind != "model":
                break
            current = parent
        if kind == "component":
            declared.add(parent)
            allowed = set(declared)
            for cid in components:
                current, visited = cid, set()
                while current in parents and current not in visited:
                    visited.add(current)
                    current = parents[current]
                    if current in declared:
                        allowed.add(cid)
                        break
            if models[mid][2] is not None and models[mid][2] not in allowed:
                codes.add("anchor_outside_home")
    if event == "cousin_owner" and defect != "compares_siblings_only":
        codes.add("duplicate_child_owner")
    if any(len(children) > 1 for children in by_parent.values()):
        codes.add("duplicate_child_owner")
    for cid, layer, parent in shape.get("sub", ()):
        if parent not in components:
            codes.add("component_parent_unknown")
        elif layer != components[parent] and defect != "cross_layer_component_parent":
            codes.add("component_parent_layer")
        seen, current = [], cid
        while current in parents:
            if current in seen:
                if defect != "accepts_component_parent_cycle":
                    codes.add("component_parent_cycle")
                break
            seen.append(current)
            current = parents[current]
    level = "warn" if defect == "nesting_mistake_as_warning" else "error"
    listed = ()
    if event == "component_child" and defect != "drops_parent_component_models":
        listed = ("m",)
    return State(event, placed["m"], tuple(sorted(f"{level}:{code}" for code in codes)), listed)


class Resolve:
    name = "Resolve"

    def __init__(self, defect=""):
        self.defect = defect

    def apply(self, event, state):
        return (FunctionResult(event, resolve(event, self.defect), label=event),)


def _rule(name, relevant, predicate, message):
    return Invariant(name, message, lambda state, trace:
                     InvariantResult.pass_() if state.event not in relevant or predicate(state)
                     else InvariantResult.fail(message))


NESTING = {"cousin_owner": "duplicate_child_owner","unknown_parent": "parent_unknown", "parent_cycle": "parent_cycle", "import_mismatch": "parent_import_mismatch",
           "outside_anchor": "anchor_outside_home", "duplicate_child_anchor": "duplicate_child_owner"}
INVARIANTS = (
    _rule("explicit_parent_wins", {"explicit_parent", "import_mismatch"},
          lambda state: state.placement[0] in {"p", "app"} and state.placement[2] == "PARENT",
          "a declared PARENT did not place the model"),
    _rule("single_importer_is_parent", {"single_importer"}, lambda state: state.placement == ("p", "model", "import"),
          "the one model importing it at top level is not its parent"),
    _rule("local_import_is_not_a_parent", {"local_importer"}, lambda state: state.placement[0] != "p",
          "an import inside a function made a parent"),
    _rule("components_then_anchor_then_system", {"components_first", "anchor_owner", "no_hint"},
          lambda state: state.placement == {"components_first": ("lib", "component", "COMPONENTS"),
                                            "anchor_owner": ("lib", "component", "anchor"),
                                            "no_hint": ("system", "system", "default")}[state.event],
          "the default placement skipped COMPONENTS, the anchor owner or system"),
    _rule("nesting_mistakes_are_errors", set(NESTING), lambda state: f"error:{NESTING[state.event]}" in state.codes,
          "a model nesting mistake is not an error"),
    _rule("component_parent_same_layer", {"component_child", "component_child_other_layer"},
          lambda state: ("error:component_parent_layer" in state.codes) == (state.event == "component_child_other_layer"),
          "a cross-layer component parent was accepted, or a same-layer one refused"),
    _rule("component_parents_known_and_acyclic", {"component_parent_unknown", "component_parent_cycle"},
          lambda state: f"error:{state.event}" in state.codes, "an unknown or looping component parent was accepted"),
    _rule("child_component_models_count_for_parent", {"component_child"}, lambda state: "m" in state.parent_models,
          "a model under a child component does not count for its parent component"),
)


def _explorer(defect=""):
    return Explorer(Workflow((Resolve(defect),)), (State(),), tuple(SHAPES), invariants=INVARIANTS,
                    max_sequence_length=1, progress_steps=0)


def build_explorer():
    return _explorer()


def broken_variants():
    return {name: _explorer(name) for name in
            ("ignores_explicit_parent", "prefers_components_over_importer", "local_import_makes_parent",
             "nesting_mistake_as_warning", "cross_layer_component_parent", "accepts_component_parent_cycle",
             "drops_parent_component_models", "skips_anchor_owner", "compares_siblings_only")}


FUNCTIONS = {"app": ("a1", "a2", "a3"), "lib": ("l1", "l2", "l3"), "ui": ("u1",), "sub": ("s1",), "sub2": ("t1",)}


def _write(root, path, text):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def _component(cid, layer, parent=None):
    out = {"id": cid, "layer": layer, "summary": cid, "responsibilities": [cid + " work"], "files": [cid + ".py"],
           "entrypoints": [], "state": [], "side_effects": [], "depends_on": [], "tests": [], "models": [],
           "status": "draft", "fingerprint": ""}
    if parent:
        out["parent"] = parent
    return out


def _project(root, event):
    shape = SHAPES[event]
    data = {"schema": "flowguard.map.v1", "project": "tree", "layers": ["top", "core"], "ignore": [],
            "components": [_component(cid, layer) for cid, layer in LAYERS.items()]
            + [_component(cid, layer, parent) for cid, layer, parent in shape.get("sub", ())],
            "flows": [], "accepted_debts": []}
    _write(root, ".flowguard/map.json", json.dumps(data))
    used = {}
    for mid, parent, components, anchor, imported_by, local_by in shape["models"]:
        source = f"MODEL_ID = {mid!r}\n"
        if parent is not None:
            source += f"PARENT = {parent!r}\n"
        if components:
            source += f"COMPONENTS = {components!r}\n"
        if anchor:
            # Every model anchors its own function, except the duplicate shape's two children, which share one.
            shared = event in ("duplicate_child_anchor", "cousin_owner") and mid != "p"
            index = 1 if shared else used.get(anchor, 0)
            used[anchor] = used.get(anchor, 0) + (0 if shared else 1)
            source += f"IMPLEMENTED_BY = {{'Run': '{anchor}.py:{FUNCTIONS[anchor][index]}'}}\n"
        source += "".join(f"import {name}\n" for name in imported_by)
        source += "".join(f"def _later():\n    import {name}\n    return {name}\n" for name in local_by)
        source += "def build_explorer():\n    return None\n"
        _write(root, f".flowguard/models/{mid}.py", source)
    return data


def _observe(base, event):
    with tempfile.TemporaryDirectory(prefix="flowguard-tree-model-") as directory:
        root = Path(shutil.copytree(base, Path(directory) / "project"))
        data = _project(root, event)
        inv = build_inventory(root, [], with_bodies=False, write_cache=False)
        tree = build_tree(root, data, inv)
        node = tree.nodes["m"]
        findings = list(tree.findings) + component_parent_findings(data)
        listed = tuple(n.id for n in tree.models_for_component("app")) if event == "component_child" else ()
        return State(event, (node.parent, node.parent_kind, node.source),
                     tuple(sorted({f"{f.level}:{f.code}" for f in findings})), listed)


class RealTree:
    def __init__(self, base):
        self.base = base

    def reset(self, initial_state):
        self.state = initial_state

    def apply_step(self, step):
        self.state = _observe(self.base, step.function_input)
        return ReplayObservation(function_name=step.function_name, observed_output=step.function_input,
                                 observed_state=self.state)

    def observe_state(self):
        return self.state


def conformance():
    last = None
    with tempfile.TemporaryDirectory(prefix="flowguard-tree-base-") as directory:
        base = Path(directory)
        for cid, names in FUNCTIONS.items():
            _write(base, cid + ".py", "".join(f"def {name}():\n    return True\n" for name in names))
        for trace in select_covering_traces(build_explorer().explore().traces):
            last = replay_trace(trace=trace, adapter=RealTree(base), invariants=INVARIANTS,
                                rules=(projected_state_matches(), projected_output_matches()))
            if not last.ok:
                return last
    return last
