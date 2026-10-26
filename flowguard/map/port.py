"""Static model ports and executable checks of writes, receipts and strict model edges."""
from __future__ import annotations
import ast
import copy
from collections.abc import Mapping
from dataclasses import dataclass, field, fields, is_dataclass
from itertools import combinations
from .common import Finding


@dataclass(frozen=True)
class Port:
    state: tuple[str, ...] | None = None
    blocks: dict = field(default_factory=dict)
    reads: tuple[str, ...] | None = None
    writes: tuple[str, ...] | None = None
    outputs: dict | None = None
    handoff: dict | None = None
    reads_parent: tuple[str, ...] = ()
    keeps: tuple[str, ...] = ()
    dispatch: dict | None = None
    approximate: bool = False
    feature_table: bool = False
    code_reads: dict = field(default_factory=dict)
    declared_parent: tuple[str, ...] = ()


class _Syntax:
    def __init__(self, text):
        self.tree = text if isinstance(text, ast.Module) else ast.parse(text)
        self.functions = {n.name: n for n in self.tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        self.classes = {n.name: n for n in self.tree.body if isinstance(n, ast.ClassDef)}
        self.values = self.assignments(self.tree.body)

    @staticmethod
    def assignments(nodes):
        out = {}
        for node in nodes:
            if isinstance(node, ast.Assign):
                out.update((n.id, node.value) for n in node.targets if isinstance(n, ast.Name))
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                out[node.target.id] = node.value
        return out

    @staticmethod
    def name(node):
        return node.id if isinstance(node, ast.Name) else node.attr if isinstance(node, ast.Attribute) else ""

    def literal(self, name, default=None):
        try:
            return ast.literal_eval(self.values[name])
        except (KeyError, ValueError, TypeError):
            return default

    def resolve(self, node, env=None, depth=0):
        if node is None or depth > 12:
            return node
        env = {**self.values, **(env or {})}
        if isinstance(node, ast.Name) and node.id in env and env[node.id] is not node:
            return self.resolve(env[node.id], env, depth+1)
        if isinstance(node, ast.BoolOp):
            return self.resolve(node.values[-1], env, depth+1)
        if isinstance(node, ast.Call) and self.name(node.func) in self.functions:
            fn = self.functions[self.name(node.func)]
            bindings = {**env, **self.assignments(fn.body)}
            params = fn.args.posonlyargs + fn.args.args
            defaults = dict(zip([p.arg for p in params[-len(fn.args.defaults):]], fn.args.defaults)) if fn.args.defaults else {}
            bindings.update(defaults)
            bindings.update((p.arg, value) for p, value in zip(params, node.args))
            bindings.update((kw.arg, kw.value) for kw in node.keywords if kw.arg)
            for statement in fn.body:
                if isinstance(statement, ast.Return):
                    return self.resolve(statement.value, bindings, depth+1)
        if isinstance(node, ast.Call):
            class Substitute(ast.NodeTransformer):
                def __init__(self): self.active = set()
                def visit_Name(self, value):
                    if isinstance(value.ctx, ast.Load) and value.id in env and value.id not in self.active:
                        self.active.add(value.id)
                        changed = self.visit(copy.deepcopy(env[value.id]))
                        self.active.remove(value.id)
                        return changed
                    return value
            result = copy.deepcopy(node)
            if self.name(node.func) == "Explorer":
                # Only these two arguments define a port; do not expand rule tables.
                result.args[:2] = [Substitute().visit(value) for value in result.args[:2]]
                for keyword in result.keywords:
                    if keyword.arg in ("workflow", "initial_states"):
                        keyword.value = Substitute().visit(keyword.value)
                return result
            if self.name(node.func) != "feature_explorer":
                return Substitute().visit(result)
        return node

    def explorer(self):
        fn = self.functions.get("build_explorer")
        if fn is None:
            return None
        return self.resolve(ast.Call(func=ast.Name(id="build_explorer", ctx=ast.Load()), args=[], keywords=[]))

    @staticmethod
    def argument(call, name, index):
        if not isinstance(call, ast.Call):
            return None
        return next((kw.value for kw in call.keywords if kw.arg == name), call.args[index] if len(call.args) > index else None)

    def state_type(self, node, depth=0):
        if node is None or depth > 8:
            return None
        if isinstance(node, ast.Call) and self.name(node.func) == "reachable_states":
            projection = self.argument(node, "project_parent_state", 1)
            fn = self.functions.get(self.name(projection))
            if fn:
                for value in ast.walk(fn):
                    if isinstance(value, ast.Return) and value.value is not None:
                        found = self.state_type(value.value, depth+1)
                        if found:
                            return found
            return None
        resolved = self.resolve(node)
        if ast.dump(resolved) != ast.dump(node):
            return self.state_type(resolved, depth+1)
        if isinstance(node, ast.Call) and self.name(node.func) in self.classes:
            cls = self.classes[self.name(node.func)]
            if any(self.name(d.func if isinstance(d, ast.Call) else d) == "dataclass" for d in cls.decorator_list):
                return tuple(n.target.id for n in cls.body if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name))
            return None
        if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            for value in node.elts:
                result = self.state_type(value, depth+1)
                if result is not None:
                    return result
        elif isinstance(node, (ast.GeneratorExp, ast.ListComp, ast.SetComp)):
            return self.state_type(node.elt, depth+1)
        elif isinstance(node, ast.Call) and self.name(node.func) in ("tuple", "list", "set", "frozenset") and node.args:
            return self.state_type(node.args[0], depth+1)
        return None


def code_reads(text, block=None):
    """Named fields read through non-self parameters, inherited methods and one helper level."""
    syntax = _Syntax(text)
    def direct(fn):
        params = {p.arg for p in fn.args.posonlyargs + fn.args.args + fn.args.kwonlyargs} - {"self", "cls"}
        return {n.attr for n in ast.walk(fn) if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id in params}
    def class_reads(name, seen=()):
        if name in seen or name not in syntax.classes:
            return set()
        cls = syntax.classes[name]
        result = set().union(*(class_reads(syntax.name(base), (*seen, name)) for base in cls.bases))
        for fn in cls.body:
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            result.update(direct(fn))
            for call in ast.walk(fn):
                if isinstance(call, ast.Call) and syntax.name(call.func) in syntax.functions:
                    result.update(direct(syntax.functions[syntax.name(call.func)]))
        return result
    result = {name: tuple(sorted(class_reads(name))) for name in syntax.classes}
    return result.get(block, ()) if block is not None else result


def model_port(text) -> Port:
    """Read a model's actual explorer construction and top-level port literals without imports."""
    syntax = _Syntax(text)
    explorer = syntax.explorer()
    kit = isinstance(explorer, ast.Call) and syntax.name(explorer.func) == "feature_explorer"
    state = ("features", "outcome", "codes", "plain_outcome", "plain_codes") if kit else syntax.state_type(syntax.argument(explorer, "initial_states", 1))
    blocks, approximate = {}, False
    if kit:
        blocks = {"AddFeature": {"reads": ("features",), "writes": state}}
    else:
        workflow = syntax.resolve(syntax.argument(explorer, "workflow", 0))
        sequence = syntax.argument(workflow, "blocks", 0) if isinstance(workflow, ast.Call) else None
        selected = []
        if isinstance(sequence, (ast.Tuple, ast.List)):
            selected = [syntax.name(syntax.resolve(n).func) for n in sequence.elts if isinstance(syntax.resolve(n), ast.Call)]
        if not selected:
            selected = [name for name, cls in syntax.classes.items() if any(isinstance(n, ast.FunctionDef) and n.name == "apply" for n in cls.body)]
            approximate = bool(selected)
        for name in selected:
            cls = syntax.classes.get(name)
            if cls is None:
                blocks[name] = {"reads": None, "writes": None}
                continue
            values = syntax.assignments(cls.body)
            def declared(key):
                try:
                    value = ast.literal_eval(values[key])
                    return tuple(value) if isinstance(value, (tuple, list)) and all(isinstance(x, str) for x in value) else None
                except (KeyError, TypeError, ValueError):
                    return None
            blocks[name] = {"reads": declared("reads"), "writes": declared("writes")}
    def union(key):
        values = [b[key] for b in blocks.values()]
        return tuple(sorted(set().union(*(set(v) for v in values)))) if values and all(v is not None for v in values) else None
    reads_parent = set(syntax.literal("READS_PARENT", ()))
    projection = syntax.functions.get("project_parent_state")
    if projection and projection.args.args:
        param = projection.args.args[0].arg
        parents = {id(n.value) for n in ast.walk(projection) if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == param}
        reads_parent.update(n.attr for n in ast.walk(projection) if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == param)
        if any(isinstance(n, ast.Name) and n.id == param and isinstance(n.ctx, ast.Load) and id(n) not in parents for n in ast.walk(projection)):
            reads_parent.add("?")
    return Port(state, blocks, union("reads"), union("writes"), syntax.literal("OUTPUTS"), syntax.literal("HANDOFF"),
                tuple(sorted(reads_parent)), tuple(syntax.literal("KEEPS", ())), syntax.literal("DISPATCH"), approximate, kit, code_reads(syntax.tree), tuple(syntax.literal("READS_PARENT", ())))


def upward(port):
    """Only finite output values form the upward interface; declaration order is immaterial."""
    return None if port.outputs is None else {key: frozenset(values) for key, values in port.outputs.items()}


def port_delta(old, new):
    """Fresh comparison only; callers decide whether any children consume the state side."""
    before, after = upward(old), upward(new)
    return dict(out=(before or {}) != (after or {}), state=old.state is None or new.state is None or set(old.state) != set(new.state),
                reads=set(old.reads_parent) != set(new.reads_parent), handoff=old.handoff != new.handoff,
                keeps=set(old.keeps) != set(new.keeps), dispatch=old.dispatch != new.dispatch)


def _receipts(port, ports):
    result = {}
    for producer, keys in (port.handoff or {}).items():
        output = ports[producer].outputs or {} if producer in ports else {}
        result[producer] = {key: (item, {v: v for v in output.get(key, ())}) if isinstance(item, str) else item
                            for key, item in keys.items()}
    return result


def port_findings(tree, ports):
    """Strict static edges and exclusive code ownership throughout the complete model tree."""
    out = []
    def add(code, mid, message, level="error"):
        out.append(Finding(level, code, mid, message))
    children = {mid: [n.id for n in tree.children(mid, "model")] for mid in tree.nodes}
    for mid, node in tree.nodes.items():
        port = ports[mid]
        direct = children[mid]
        if direct and port.feature_table:
            add("kit_model_parent", mid, f"{', '.join(direct)} name {mid} as PARENT, but {mid} is a feature-table model; its State cannot receive a child's value; set PARENT to the component ({node.home})")
        if direct or node.parent_kind == "model":
            if port.state is None:
                parent = mid if direct else node.parent
                add("port_unreadable", mid, f"{mid} is in a model edge ({parent} > {mid}) but its State is unreadable; build_explorer() must return Explorer(...) built in this file or feature_explorer(...)")
        if direct:
            for block, declarations in port.blocks.items():
                if declarations["writes"] is None:
                    add("parent_writes_undeclared", mid, f"{mid} has model children; declare writes on its block {block}")
        if port.state is not None:
            for key in port.outputs or {}:
                if key not in port.state:
                    add("outputs_not_state", mid, f"OUTPUTS key {key} of {mid} is not a field of its State")
        received = _receipts(port, ports)
        for child in direct:
            if child not in received:
                for key, values in (ports[child].outputs or {}).items():
                    add("handoff_output_unhandled", mid, f"{child} emits {key}={'|'.join(map(str,values))}; {mid} never handles it (add HANDOFF['{child}']['{key}'] in {node.path})")
        destinations = {}
        for producer, keys in received.items():
            if producer not in ports:
                add("handoff_output_unhandled", mid, f"HANDOFF['{producer}'] in {mid} names no model")
                continue
            produced = ports[producer].outputs
            if produced is None:
                add("handoff_output_unhandled", mid, f"{mid} maps outputs of {producer}, which declares no OUTPUTS")
                continue
            is_parent = producer in direct
            for key, values in produced.items():
                mapping = keys.get(key)
                if mapping is None:
                    add("handoff_output_unhandled", mid, f"{producer} emits {key}={'|'.join(map(str,values))}; {mid} never handles it (add HANDOFF['{producer}']['{key}'] in {node.path})")
                    continue
                into, value_map = mapping
                for value in values:
                    if value not in value_map:
                        add("handoff_output_unhandled", mid, f"{producer} emits {key}='{value}'; {mid} never handles it (add '{value}' to HANDOFF['{producer}']['{key}'] in {node.path})")
                    elif is_parent and value_map[value] is None:
                        add("handoff_drops_child_value", mid, f"{mid} maps {producer}.{key}='{value}' to None; a parent receives every child value")
                if is_parent and into is None:
                    add("handoff_drops_child_value", mid, f"{mid} maps {producer}.{key} into no field; a parent receives each child value into one of its State fields")
            for key, (into, value_map) in keys.items():
                if into is not None:
                    if port.state is not None and into not in port.state:
                        add("handoff_into_unknown", mid, f"HANDOFF['{producer}']['{key}'] in {mid} goes into '{into}', which {mid}.State does not have")
                    if into in destinations:
                        add("sibling_outputs_overlap", mid, f"{mid}.State.{into} is fed by {destinations[into]}, {producer}.{key}; give each received value its own field")
                    destinations[into] = f"{producer}.{key}"
                for value in value_map:
                    if key not in produced or value not in produced[key]:
                        add("handoff_output_unhandled", mid, f"HANDOFF['{producer}']['{key}'] in {mid} maps '{value}', which {producer} no longer outputs; remove it", "warn")
        covered = set(port.keeps) | set(destinations)
        for child in direct:
            child_port = ports[child]
            for name in child_port.reads_parent:
                if port.state is not None and name not in port.state:
                    add("child_input_unprovided", child, f"{child} reads {mid}.State.{name}, which {mid}.State does not have")
                if name in child_port.declared_parent and child_port.state is not None and name not in child_port.state:
                    add("child_input_unprovided", child, f"{child} declares READS_PARENT '{name}' but its own State has no field {name}; a child holds the input it takes")
            covered.update(child_port.reads_parent)
            keys = received.get(child, {})
            if not any(key in (child_port.outputs or {}) and into is not None for key, (into, _) in keys.items()):
                add("child_unconnected", child, f"{child} hands {mid} nothing; a child hands its result up: declare OUTPUTS and map it in {mid}'s HANDOFF, or, if {mid} does not take its result, make it a component model (PARENT = \"{tree.nodes[child].home}\")")
        if direct and port.state is not None:
            for name in set(port.state) - covered:
                add("parent_field_uncovered", mid, f"{mid}.State.{name}: no child reads it, no child output goes into it, and KEEPS does not list it; give it to the child that handles it (READS_PARENT or HANDOFF into), or list it in KEEPS if {mid} takes it as input, uses it as a step marker or aggregates it from received values")
        if port.dispatch is not None:
            if len(port.dispatch) != 1:
                add("dispatch_field_unknown", mid, f"DISPATCH in {mid} must name exactly one selector field, not {len(port.dispatch)}")
            for selector, alternatives in port.dispatch.items():
                if port.state is not None and selector not in port.state:
                    add("dispatch_field_unknown", mid, f"DISPATCH in {mid} selects on '{selector}', which {mid}.State does not have")
                for alternative, child in alternatives.items():
                    if child not in tree.nodes:
                        add("dispatch_without_child", mid, f"dispatch_without_child: {mid} dispatches {selector}='{alternative}' to '{child}', which names no model")
                    elif child not in direct:
                        add("dispatch_without_child", mid, f"dispatch_without_child: {mid} dispatches {selector}='{alternative}' to {child}, which is not a child of {mid}; set PARENT = \"{mid}\" in {child}, or remove '{alternative}'")
    for a, b in combinations(tree.nodes.values(), 2):
        if a.id in tree.ancestors(b.id) or b.id in tree.ancestors(a.id):
            continue
        for aa in a.contract.get("IMPLEMENTED_BY", {}).values():
            ap, _, sa = aa.partition(":")
            for ab in b.contract.get("IMPLEMENTED_BY", {}).values():
                bp, _, sb = ab.partition(":")
                if ap == bp and (sa == sb or sa.startswith(sb+".") or sb.startswith(sa+".")):
                    shared = (a.parent, a.parent_kind) == (b.parent, b.parent_kind)
                    message = (f"{a.parent}: siblings {a.id}, {b.id} both own {ap}:{sa if len(sa)<len(sb) else sb} ({a.id} {aa}, {b.id} {ab}); " if shared else
                               f"{a.id}, {b.id} both own {ap}:{sa if len(sa)<len(sb) else sb} ({aa} under {a.parent}, {ab} under {b.parent}) and neither is the other's model ancestor; ")
                    add("duplicate_child_owner", a.id, message+"keep it in the model whose rules judge it and bind it read-only with USES in the other")
    return out


def changed_fields(before, after):
    """Compare only dataclass-to-dataclass or Mapping-to-Mapping field values."""
    if is_dataclass(before) and not isinstance(before, type) and is_dataclass(after) and not isinstance(after, type):
        names = {f.name for f in fields(before)} | {f.name for f in fields(after)}
        return tuple(sorted(name for name in names if getattr(before, name, _ABSENT) != getattr(after, name, _ABSENT)))
    if isinstance(before, Mapping) and isinstance(after, Mapping):
        return tuple(sorted((key for key in before.keys() | after.keys() if before.get(key, _ABSENT) != after.get(key, _ABSENT)), key=str))
    return ()


_ABSENT = object()
_LAST_KEEPS = {}


def _value(state, name):
    return state.get(name, _ABSENT) if isinstance(state, Mapping) else getattr(state, name, _ABSENT)


def _atoms(value, depth=2):
    if isinstance(value, (str, int, bool)):
        return {value}
    if depth <= 0:
        return set()
    if is_dataclass(value) and not isinstance(value, type):
        return set().union(*(_atoms(getattr(value, f.name), depth-1) for f in fields(value)))
    if isinstance(value, (tuple, list, set, frozenset)):
        return set().union(*(_atoms(item, depth-1) for item in value))
    return set()


def step_atoms(step):
    """Receipt evidence comes from input/label/output, never from the new state."""
    return _atoms(step.external_input) | _atoms(step.label) | _atoms(step.function_output)


def _contains(value, wanted):
    return wanted in value if isinstance(value, (tuple, list, set, frozenset)) else value == wanted


def _forward(old, new, seen):
    if isinstance(old, bool) and isinstance(new, bool):
        return not old and new
    if isinstance(old, int) and isinstance(new, int):
        return new > old
    if isinstance(old, str) and isinstance(new, str):
        return new not in seen
    if isinstance(old, tuple) and isinstance(new, tuple):
        return len(new) > len(old) and new[:len(old)] == old
    if isinstance(old, frozenset) and isinstance(new, frozenset):
        return old < new
    return False


def keeps_classes(model_id, port=None, records=(), received=(), *, aggregate_only=False):
    """Classify observed parent fields; retain only this process's last classification for display."""
    if port is None:
        return _LAST_KEEPS.get(model_id, {})
    receiving = set(received)
    changed_by = {name: set() for name in port.keeps}
    is_input = dict.fromkeys(port.keeps, True)
    is_marker = dict.fromkeys(port.keeps, True)
    receiver_blocks = set()
    for trace in records:
        seen = {name: [] for name in port.keeps}
        for step, changed, atoms in trace:
            for name in receiving:
                value = _value(step.new_state, name)
                mappings = received.get(name, ()) if isinstance(received, dict) else ()
                clearing = value is None or value == "" or isinstance(value, (tuple, list, set, frozenset)) and not value
                if name in changed and not clearing and any(source in atoms and _contains(value, target) for source, target in mappings):
                    receiver_blocks.add(step.function_name)
            for name in port.keeps:
                before, after = _value(step.old_state, name), _value(step.new_state, name)
                if not seen[name]:
                    seen[name].append(before)
                if name in changed:
                    changed_by[name].add(step.function_name)
                    inputs = [step.external_input]
                    if is_dataclass(step.external_input) and not isinstance(step.external_input, type):
                        inputs.extend(getattr(step.external_input, f.name) for f in fields(step.external_input))
                    is_input[name] &= any(after == value for value in inputs)
                    is_marker[name] &= _forward(before, after, seen[name])
                seen[name].append(after)
    result = {} if aggregate_only else {name: "input" if is_input[name] else "marker" for name in port.keeps if is_input[name] or is_marker[name]}
    pending = set(port.keeps) - set(result)
    while pending:
        added = {name for name in pending if changed_by[name] and all(block in receiver_blocks or
                 bool(set(port.code_reads.get(block, ())) & (receiving | {f for f, kind in result.items() if kind == "aggregate"}))
                 for block in changed_by[name])}
        if not added:
            break
        result.update((name, "aggregate") for name in added)
        pending -= added
    result.update((name, "domain") for name in pending)
    _LAST_KEEPS[model_id] = result
    return result


def run_findings(model_id, design, report, port, tree, ports):
    """One traversal of a model's existing traces checks actual writes and finite receipts."""
    out, emitted = [], set()
    def add(code, message, level="error"):
        if (code, message) not in emitted:
            emitted.add((code, message))
            out.append(Finding(level, code, model_id, message))
    blocks = {str(getattr(block, "name", type(block).__name__)): block for block in design.workflow.blocks}
    declarations = {name: tuple(block.writes) for name, block in blocks.items() if hasattr(block, "writes")}
    reads = {name: port.code_reads.get(type(block).__name__, ()) for name, block in blocks.items()}
    port = Port(**{**port.__dict__, "code_reads": reads})
    receipts = _receipts(port, ports)
    handled = {(producer, key, value): False for producer, keys in receipts.items() for key, (_, values) in keys.items()
               for value, target in values.items() if target is not None}
    reached = {key: set() for key in port.outputs or {}}
    records, unique = [], {}
    parent = bool(tree.children(model_id, "model"))
    children = {child.id for child in tree.children(model_id, "model")}
    receiving = {}
    for keys in receipts.values():
        for into, values in keys.values():
            if into is not None:
                receiving.setdefault(into, []).extend((source, target) for source, target in values.items() if target is not None)
    selector, alternatives = next(iter(port.dispatch.items())) if port.dispatch and len(port.dispatch) == 1 else (None, {})
    first_block = str(getattr(design.workflow.blocks[0], "name", type(design.workflow.blocks[0]).__name__)) if design.workflow.blocks else ""
    for trace in report.traces:
        rows, calls, current = [], [], []
        pending_receipts = set()
        for step in trace.steps:
            observed = unique.get(id(step))
            if observed is None:
                changed, atoms = changed_fields(step.old_state, step.new_state), step_atoms(step)
                observed = unique[id(step)] = (changed, atoms)
                undeclared = set(changed) - set(declarations.get(step.function_name, changed))
                if undeclared:
                    add("undeclared_write", f"undeclared_write: block {step.function_name} changed State.{', '.join(map(str, sorted(undeclared, key=str)))}, which its writes ({', '.join(declarations[step.function_name])}) do not declare; add them to writes or stop writing them (trace: {step.function_name} [{step.label}])")
                for key, allowed in (port.outputs or {}).items():
                    if key not in changed:
                        continue
                    before, after = _value(step.old_state, key), _value(step.new_state, key)
                    values = (set(after) - (set(before) if isinstance(before, (tuple, list, set, frozenset)) else set())
                              if isinstance(after, (tuple, list, set, frozenset)) else {after})
                    reached[key].update(values)
                    for value in values - set(allowed):
                        add("output_undeclared", f"output_undeclared: {model_id} writes {key}='{value}', which OUTPUTS['{key}'] does not list; declare it (a port change: its parent and consumers must handle it)")
            changed, atoms = observed
            row = (step, changed, atoms)
            rows.append(row)
            if current and step.function_name == first_block:
                calls.append(current)
                current = []
            current.append(row)
            for producer, keys in receipts.items():
                for key, (into, values) in keys.items():
                    for value, target in values.items():
                        identity = (producer, key, value)
                        if target is None:
                            continue
                        if value in atoms:
                            pending_receipts.add(identity)
                        if identity in pending_receipts and ((target in atoms) if into is None else _contains(_value(step.new_state, into), target)):
                            handled[identity] = True
        records.append(rows)
        if current:
            calls.append(current)
        if selector is not None:
            for call in calls:
                chosen = _value(call[-1][0].new_state, selector)
                default = _value(call[0][0].old_state, selector)
                # Declared default values mark calls refused before a branch.
                if chosen in (None, "", 0, False):
                    continue
                branch = alternatives.get(chosen)
                if branch is None:
                    add("dispatch_without_child", f"dispatch_without_child: {model_id} takes {selector}='{chosen}', but DISPATCH['{selector}'] has no child for '{chosen}'; add a child model for '{chosen}' (PARENT = \"{model_id}\", OUTPUTS mapped in HANDOFF) and list it in DISPATCH (trace: {call[-1][0].label})")
                    continue
                touched, received_branch = set(), False
                pending = set()
                for step, changed, atoms in call:
                    for child in set(alternatives.values()):
                        for key, (into, values) in receipts.get(child, {}).items():
                            if into in changed:
                                touched.add(child)
                            for value, target in values.items():
                                if value in atoms:
                                    pending.add((child, key, value))
                                if target is not None and (child, key, value) in pending and into is not None and _contains(_value(step.new_state, into), target):
                                    touched.add(child)
                                    received_branch |= child == branch
                if not received_branch:
                    into = next((field for field, _ in receipts.get(branch, {}).values()), "?")
                    add("dispatch_branch_not_received", f"dispatch_branch_not_received: {model_id} takes {selector}='{chosen}' -> {branch}, but no step of that call receives a {branch} value into {into}; the parent receives the branch it takes (trace: {call[-1][0].label})")
                if len(touched) > 1:
                    add("dispatch_two_branches", f"dispatch_two_branches: one call of {model_id} receives or writes the fields of {', '.join(sorted(touched))}; a dispatch runs exactly one branch (trace: {call[-1][0].label})")
    for key, allowed in (port.outputs or {}).items():
        for value in set(allowed) - reached[key]:
            add("output_unreached", f"output_unreached: {model_id} declares {key}='{value}' in OUTPUTS, but no explored step writes it; remove it or model the case that produces it", "warn")
    for (producer, key, value), received in handled.items():
        if not received:
            into, values = receipts[producer][key]
            target = values[value]
            destination = f"{model_id}.{into}='{target}'" if into is not None else f"'{target}'"
            held = f"holds {into}='{target}'" if into is not None else f"reaches '{target}'"
            add("handoff_output_unhandled", f"handoff_output_unhandled: {producer} emits {key}='{value}' -> {destination}; no explored {model_id} trace receives '{value}' and then {held} (model receiving '{value}' in {tree.nodes[model_id].path})")
    if parent:
        kinds = keeps_classes(model_id, port, records, receiving)
        for name, kind in kinds.items():
            if kind == "domain":
                writers = {step.function_name for trace in records for step, changed, _ in trace if name in changed}
                reads = sorted({value for writer in writers for value in port.code_reads.get(writer, ())})
                add("keeps_not_orchestration", f"keeps_not_orchestration: {model_id}.State.{name} is changed by {', '.join(sorted(writers))} from {', '.join(reads)}, so it is neither an input, a step marker nor an aggregate of received child values; move {name} and the rules that read it into a child, so the children cover {model_id}")
        node = tree.nodes[model_id]
        consumed = any(model_id in (p.handoff or {}) for mid, p in ports.items() if mid != model_id)
        if node.parent_kind == "model" or consumed:
            output_port = Port(state=port.state, keeps=tuple((port.outputs or {}).keys()), code_reads=port.code_reads)
            output_kinds = keeps_classes(model_id + ":outputs", output_port, records, receiving, aggregate_only=True)
            for key in port.outputs or {}:
                if key not in receiving and output_kinds.get(key) != "aggregate":
                    add("parent_output_not_from_child", f"parent_output_not_from_child: {model_id} hands up {key}, which no child output goes into and no block of {model_id} computes from a received value")
    return out

def escalation_set(model_id: str, tree, ports: dict[str, Port], *, out: bool = True, state: bool = True) -> list[tuple[str, str]]:
    """The sole ordered index of parent, explicit consumer and child-input edges."""
    node = tree.nodes.get(model_id)
    result = []
    if node is None:
        return result
    if out:
        if node.parent_kind == "model" and node.parent in ports:
            result.append((node.parent, "parent"))
        result.extend((mid, "HANDOFF") for mid in sorted(ports) if mid != model_id and mid != node.parent
                      and model_id in (ports[mid].handoff or {}))
    if state:
        result.extend((child.id, "child input") for child in tree.children(model_id, "model")
                      if child.id in ports and ports[child.id].reads_parent)
    return result


def _set_delta(before, after):
    return " ".join([*("+" + str(v) for v in sorted(set(after) - set(before), key=str)),
                     *("-" + str(v) for v in sorted(set(before) - set(after), key=str))])


def port_selection(model_id, old, new, tree, ports, *, new_model=False, unavailable=False):
    """Compare current bytes; return direct edge selections and their user-facing reason."""
    node = tree.nodes[model_id]
    parent = node.parent if node.parent_kind == "model" else None
    if unavailable:
        selected = [(mid, reason) for mid, reason in escalation_set(model_id, tree, ports, state=False) if reason == "parent"]
        return selected, (f"UNCERTAIN port: no git base for {model_id}; target check compared its port before promote; parent {parent} selected"
                          if parent else f"UNCERTAIN port: no git base for {model_id}; target check compared its port before promote; no model parent"), ""
    if parent and new.outputs is None:
        return [(mid, reason) for mid, reason in escalation_set(model_id, tree, ports, state=False) if reason == "parent"], f"UNCERTAIN port: {model_id} declares no OUTPUTS; parent {parent} selected", ""
    old = old or Port()
    delta = port_delta(old, new)
    output_change = new_model or delta['out']
    readers = escalation_set(model_id, tree, ports, out=False)
    state_change = bool(readers) and delta['state']
    selected = escalation_set(model_id, tree, ports, out=output_change, state=state_change)
    if delta['reads']:
        parent_pair = [(mid, reason) for mid, reason in escalation_set(model_id, tree, ports, state=False) if reason == 'parent']
        selected = list(dict.fromkeys(parent_pair + selected))
    parts = []
    if new_model:
        parts.append('new model')
    if delta['out']:
        if old.outputs is None and new.outputs:
            parts.append('out declared')
        else:
            before = {v for values in (old.outputs or {}).values() for v in values}
            after = {v for values in (new.outputs or {}).values() for v in values}
            changes = _set_delta(before, after)
            parts.append('out ' + (changes or '(fields changed)'))
    if delta['reads']:
        parts.append('reads ' + _set_delta(old.reads_parent, new.reads_parent))
    uncertain = state_change and (old.state is None or new.state is None)
    if state_change and not uncertain:
        parts.append('state ' + _set_delta(old.state, new.state))
    edge = []
    if delta['handoff']:
        for producer in sorted(set(old.handoff or {}) | set(new.handoff or {})):
            previous, after = (old.handoff or {}).get(producer, {}), (new.handoff or {}).get(producer, {})
            if previous != after:
                edge.append('handoff ' + producer + ' ' + (_set_delta(previous, after) or '(mapping changed)'))
    if delta['keeps']:
        edge.append('keeps ' + _set_delta(old.keeps, new.keeps))
    if delta['dispatch']:
        before = {v for values in (old.dispatch or {}).values() for v in values}
        after = {v for values in (new.dispatch or {}).values() for v in values}
        edge.append('dispatch ' + (_set_delta(before, after) or '(mapping changed)'))
    description = ' '.join(parts)
    if parts:
        consumers = ', '.join(f'{mid} ({reason})' for mid, reason in selected) or '(no model consumer)'
        line = f'port changed: {model_id} {description} -> verify {consumers}'
    else:
        line = f'port: {model_id} unchanged (this model only)'
    if edge:
        line += '; ' + '; '.join(edge) + ' (edge checked by map check)'
    if uncertain:
        note = f"UNCERTAIN port: {model_id} state unreadable; children reading it {', '.join(mid for mid, _ in readers)} selected"
        line = note if not parts else line + '\n' + note
    return selected, line, description


def code_callers(raw, node, scope):
    """At most three direct calls to owned code from outside the model's scope."""
    anchors = [anchor.partition(":") for anchor in node.contract.get("IMPLEMENTED_BY", {}).values()]
    return sorted({caller.replace("#", ":", 1) for caller, callees in raw.get("edges", {}).items()
                   if caller.partition("#")[0] not in scope
                   and any(path == callee.partition("#")[0] and (callee.partition("#")[2] == symbol or callee.partition("#")[2].startswith(symbol + "."))
                           for callee in callees for path, _, symbol in anchors)})[:3]
