"""Derive a skeleton from the existing source inventory and shared syntax."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from flowguard.map.common import read_source
from flowguard.map.discover import discover_inventory, function_spans
from flowguard.map.inventory import build_inventory, syntax_tree


class SkeletonError(ValueError):
    pass


def _name(node):
    if isinstance(node, ast.Call):
        return _name(node.func)
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return _name(node.value) + "." + node.attr
    return ""


def read_corrections(root):
    path = Path(root) / ".flowguard/skeleton.py"
    if not path.is_file():
        return []
    try:
        tree = syntax_tree(read_source(path))
    except (SyntaxError, OSError) as exc:
        raise SkeletonError(f"correction_syntax {path}: {exc}") from exc
    rows = []
    for node in tree.body:
        if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
            raise SkeletonError(f"config_in_skeleton {path}:{node.lineno}: corrections cannot set configuration")
        expr = node.value
        kind = _name(expr.func)
        if kind not in {"pin", "ui", "exclude", "call", "world", "budget", "alias", "adapter"}:
            raise SkeletonError(f"config_in_skeleton {path}:{node.lineno}: unsupported correction {kind}")
        try:
            args = [ast.literal_eval(value) for value in expr.args]
            kwargs = {item.arg: ast.literal_eval(item.value) for item in expr.keywords}
        except (ValueError, TypeError) as exc:
            raise SkeletonError(f"config_in_skeleton {path}:{node.lineno}: only literal correction arguments are supported") from exc
        if not isinstance(kwargs.get("why"), str) or not kwargs["why"].strip():
            raise SkeletonError(f"correction_reason_missing {path}:{node.lineno}")
        if any(key in {None, "settings", "config", "shipped"} for key in kwargs):
            raise SkeletonError(f"config_in_skeleton {path}:{node.lineno}: judge the shipped settings")
        rows.append({"kind": kind, "args": args, "kwargs": kwargs, "line": node.lineno})
    return rows


def _plural(name):
    if name.endswith(("s", "x", "z", "ch", "sh")):
        return name + "es"
    if name.endswith("y") and len(name) > 1 and name[-2] not in "aeiou":
        return name[:-1] + "ies"
    return name + "s"


def _signature(fn):
    positional = [*fn.args.posonlyargs, *fn.args.args]
    defaults = [None] * (len(positional) - len(fn.args.defaults)) + list(fn.args.defaults)
    pairs = [*zip(positional, defaults), *zip(fn.args.kwonlyargs, fn.args.kw_defaults)]
    result = []
    for arg, default in pairs:
        if arg.arg in {"self", "cls"}:
            continue
        row = {"name": arg.arg, "required": default is None}
        if arg.annotation is not None:
            row["annotation"] = ast.unparse(arg.annotation)
        if default is not None:
            try:
                row["default"] = ast.literal_eval(default)
            except (ValueError, TypeError):
                row["default_unknown"] = ast.unparse(default)
        result.append(row)
    return result


def derive(root):
    """No application import occurs here; all live construction belongs to project."""
    root = Path(root).resolve()
    corrections = read_corrections(root)
    inv = build_inventory(root, [".flowguard/**"], with_bodies=False, write_cache=False)
    current_syntax, errors = {}, []
    for source in inv.py:
        if inv.is_test(source):
            continue
        try:
            current_syntax[source] = syntax_tree(read_source(root / source))
        except (OSError, UnicodeError, SyntaxError) as exc:
            errors.append(f"{source}: {exc}")
    if errors:
        raise SkeletonError("source_not_parseable: " + "; ".join(errors))
    raw = discover_inventory(root, inv, write_cache=False)
    # These are references into shared syntax, not another persisted source index.
    trees = {path: current_syntax[path] for path in raw["files"]}
    classes = {}
    functions = {}
    for path, tree in trees.items():
        module = inv.py[path].module
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                locator = module + ":" + node.name
                classes[locator] = (path, node)
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        functions[path + "#" + node.name + "." + item.name] = item
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions[path + "#" + node.name] = node

    def resolve(spelling, path):
        own = inv.py[path].module + ":" + spelling
        if own in classes:
            return own
        first, _, suffix = spelling.partition(".")
        imported = raw["files"][path]["imports"].get(first, "")
        if ":" in imported:
            candidate = imported + ("." + suffix if suffix else "")
            return candidate if candidate in classes else None
        candidate = imported + ("." + suffix if suffix else "")
        for locator in classes:
            if locator.replace(":", ".") == candidate:
                return locator
        return None

    def is_settings(locator):
        source, node = classes[locator]
        return any(_name(value).split(".")[-1] == "dataclass" or raw["files"][source]["imports"].get(_name(value), "").endswith(":dataclass") for value in node.decorator_list)

    def is_refusal(locator, seen=()):
        if locator in seen:
            return False
        path, node = classes[locator]
        for base in node.bases:
            spelling = _name(base)
            if spelling in {"Exception", "ValueError", "RuntimeError", "TypeError"}:
                return True
            parent = resolve(spelling, path)
            if parent and is_refusal(parent, (*seen, locator)):
                return True
        return False

    pins = {}
    for row in corrections:
        if row["kind"] == "pin":
            if len(row["args"]) != 2 or row["args"][0] not in {"system", "settings", "ui", "persistence"}:
                raise SkeletonError("pin_syntax: expected pin(role, source, why=...)")
            role, locator = row["args"]
            if role in pins or locator not in classes:
                raise SkeletonError("pin_not_buildable: " + str(locator))
            pins[role] = locator
    candidates = []
    for locator, (_path, node) in classes.items():
        if not is_settings(locator) and not is_refusal(locator):
            count = sum(isinstance(item, ast.FunctionDef) and not item.name.startswith("_") for item in node.body)
            if count:
                candidates.append((count, locator))
    if not candidates:
        raise SkeletonError("world kind needed: no constructible system class; use a Calls or CLI project world when available")
    highest = max(count for count, _ in candidates)
    choices = sorted(locator for count, locator in candidates if count == highest)
    if "system" not in pins and len(choices) != 1:
        raise SkeletonError("system_ambiguous: " + ", ".join(choices) + "; add a source pin")
    system = pins.get("system", choices[0])
    path, cls = classes[system]
    if any(_name(base) != "object" for base in cls.bases):
        raise SkeletonError("world kind needed: inherited public surfaces need an explicit world")
    methods = {item.name: item for item in cls.body if isinstance(item, ast.FunctionDef)}
    settings, parameter = pins.get("settings"), None
    init = methods.get("__init__")
    if init:
        params = {item["name"] for item in _signature(init)}
        bindings = []
        for item in ast.walk(init):
            if isinstance(item, (ast.Assign, ast.AnnAssign)):
                value = item.value
                found = {resolve(_name(expr.func), path) for expr in ast.walk(value) if isinstance(expr, ast.Call)} if value else set()
                found = {locator for locator in found if locator and is_settings(locator)}
                names = {expr.id for expr in ast.walk(value) if isinstance(expr, ast.Name)} & params if value else set()
                if len(found) == len(names) == 1:
                    bindings.append((next(iter(found)), next(iter(names))))
        for arg in [*init.args.posonlyargs, *init.args.args, *init.args.kwonlyargs]:
            locator = resolve(_name(arg.annotation), path)
            if locator and is_settings(locator):
                bindings.append((locator, arg.arg))
        bindings = sorted(set(bindings))
        if len(bindings) == 1:
            derived_settings, parameter = bindings[0]
            if settings and settings != derived_settings:
                raise SkeletonError("settings_pin_conflicts_with_constructor")
            settings = derived_settings
        elif bindings:
            raise SkeletonError("settings_ambiguous: constructor has several settings bindings")
        elif settings:
            raise SkeletonError("settings_parameter_unknown")
    ui_candidates = []
    for locator, (_source, node) in classes.items():
        names = {item.name for item in node.body if isinstance(item, ast.FunctionDef)}
        if {"options", "choose"} <= names:
            ui_candidates.append(locator)
    ui = pins.get("ui")
    ui_names = {"options": "options", "choose": "choose"}
    for row in corrections:
        if row["kind"] == "ui":
            if len(row["args"]) != 1 or row["args"][0] not in classes:
                raise SkeletonError("ui_root_unknown")
            ui = row["args"][0]
            ui_names = {key: row["kwargs"].get(key, key) for key in ui_names}
    if not ui and len(ui_candidates) == 1:
        ui = ui_candidates[0]
    unknown = []
    if not ui and ui_candidates:
        unknown.append("ambiguous UI roots: " + ", ".join(sorted(ui_candidates)))
    method_symbols = {name: path + "#" + cls.name + "." + name for name in methods}
    closure_memo = {}

    def closure(symbol):
        if symbol not in closure_memo:
            seen, queue = set(), [symbol]
            while queue:
                current = queue.pop()
                if current not in seen:
                    seen.add(current)
                    queue.extend(raw["edges"].get(current, ()))
            closure_memo[symbol] = seen
        return closure_memo[symbol]

    def writes(symbol):
        for current in closure(symbol):
            source, _, name = current.partition("#")
            facts = raw["files"].get(source, {}).get("functions", {}).get(name, {})
            if facts.get("writes"):
                return True
            fn = functions.get(current)
            if fn and not fn.name.startswith("__"):
                for stmt in ast.walk(fn):
                    targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target] if isinstance(stmt, (ast.AnnAssign, ast.AugAssign)) else []
                    if any(isinstance(target, ast.Attribute) for target in targets):
                        return True
        return False

    def reads_file(symbol):
        for current in closure(symbol):
            fn = functions.get(current)
            if fn and any(isinstance(item, ast.Call) and _name(item.func).split(".")[-1] in {"open", "read_text", "read_bytes"} for item in ast.walk(fn)):
                return True
        return False

    public = {name: node for name, node in methods.items() if not name.startswith("_") and not any(_name(deco) == "property" for deco in node.decorator_list)}
    entities = {}
    for name, node in public.items():
        if name.startswith("add_") and _plural(name[4:]) in public:
            entities[name[4:]] = {"add": name, "list": _plural(name[4:]), "parameters": _signature(node)}
    known_arguments = {item["parameters"][0]["name"]: kind for kind, item in entities.items() if item["parameters"]}
    bindings = {(name, row["name"]): known_arguments[row["name"]] for name, node in methods.items() for row in _signature(node) if row["name"] in known_arguments}
    changed = True
    while changed:
        changed = False
        for name, node in methods.items():
            for expr in ast.walk(node):
                if isinstance(expr, ast.Call) and isinstance(expr.func, ast.Attribute) and _name(expr.func.value) == "self" and expr.func.attr in methods:
                    rows = _signature(methods[expr.func.attr])
                    arguments = {row["name"]: value for row, value in zip(rows, expr.args)}
                    arguments.update({item.arg: item.value for item in expr.keywords})
                    for parameter_name, value in arguments.items():
                        kind = bindings.get((expr.func.attr, parameter_name))
                        key = (name, value.id) if isinstance(value, ast.Name) else None
                        if kind and key and key not in bindings:
                            bindings[key] = kind
                            changed = True
    persistence = {"save": "save", "load": "load"} if {"save", "load"} <= public.keys() else None
    if pins.get("persistence", system) != system:
        raise SkeletonError("persistence_root_unknown: persistence on a separate root needs an explicit world")
    file_inputs = [name for name in public if name not in {"save", "load"} and reads_file(method_symbols[name])]
    seeds = {value["add"] for value in entities.values()}
    actions = sorted(name for name in public if name not in seeds | set(file_inputs) | {"save", "load"} and writes(method_symbols[name]))
    queries = sorted(set(public) - set(actions) - seeds - set(file_inputs) - {"save", "load"})
    predictors = [[name, name[len(prefix):]] for prefix in ("why_not_", "can_") for name in queries if name.startswith(prefix) and name[len(prefix):] in actions]
    statuses = {}
    for name in queries:
        values = {item.value.value for item in ast.walk(methods[name]) if isinstance(item, ast.Return) and isinstance(item.value, ast.Constant) and isinstance(item.value.value, str)}
        if len(values) >= 3 and len(_signature(methods[name])) == 1:
            statuses[name] = sorted(values)
    parameters = {}
    for name in [*actions, *queries, *file_inputs]:
        rows = _signature(public[name])
        for row in rows:
            key = row["name"]
            row["entity"] = bindings.get((name, key))
            literals = []
            for tree in trees.values():
                for item in ast.walk(tree):
                    if isinstance(item, ast.Compare) and any(isinstance(value, ast.Name) and value.id == key for value in [item.left, *item.comparators]):
                        for value in [item.left, *item.comparators]:
                            try:
                                literal = ast.literal_eval(value)
                                literals.extend(literal if isinstance(literal, (tuple, list, set)) else [literal])
                            except (ValueError, TypeError):
                                pass
            row["literals"] = sorted(set(value for value in literals if type(value) in (str, int)), key=lambda value: (type(value).__name__, str(value)))
        parameters[name] = rows
    settings_values = {}
    if settings:
        for item in classes[settings][1].body:
            if isinstance(item, ast.AnnAssign) and item.value is not None:
                try:
                    settings_values[item.target.id] = ast.literal_eval(item.value)
                except (ValueError, TypeError):
                    unknown.append("setting default requires construction: " + item.target.id)
    for row in corrections:
        if set(row["kwargs"]) & (settings_values.keys() - {"why"}):
            raise SkeletonError(f"config_in_skeleton .flowguard/skeleton.py:{row['line']}: judge shipped settings")
    entity_queries = {
        name: {"parameter": rows[0]["name"], "entity": rows[0]["entity"]}
        for name in queries if len(rows := parameters[name]) == 1 and rows[0].get("entity")
    }
    ui_facts = {"options": [], "screens": [], "inputs": [], "option_inputs": {}}
    ui_constructor = None
    ui_refusal = []
    if ui:
        ui_path, ui_class = classes[ui]
        globals_ = {item.targets[0].id: item.value for item in trees[ui_path].body if isinstance(item, ast.Assign) and isinstance(item.targets[0], ast.Name)}
        ui_methods = {item.name: item for item in ui_class.body if isinstance(item, ast.FunctionDef)}
        options, screens, inputs = set(), set(), set()
        if any(name not in ui_methods for name in ui_names.values()):
            raise SkeletonError("ui_methods_unknown: correction names missing public methods")
        options_fn = ui_methods[ui_names["options"]]
        referenced = {item.id for item in ast.walk(options_fn) if isinstance(item, ast.Name)}
        for name in referenced & globals_.keys():
            try:
                value = ast.literal_eval(globals_[name])
            except (ValueError, TypeError):
                continue
            if isinstance(value, (list, tuple)):
                options.update(item for item in value if isinstance(item, str))
            elif isinstance(value, dict) and all(isinstance(item, (list, tuple)) for item in value.values()):
                screens.update(value)
                options.update(item for values in value.values() for item in values if isinstance(item, str))
        for item in ast.walk(options_fn):
            if isinstance(item, (ast.List, ast.Tuple)):
                options.update(value.value for value in item.elts if isinstance(value, ast.Constant) and isinstance(value.value, str))
            if isinstance(item, ast.Call) and isinstance(item.func, ast.Attribute) and item.func.attr == "append" and item.args and isinstance(item.args[0], ast.Constant) and isinstance(item.args[0].value, str):
                options.add(item.args[0].value)
        for item in ast.walk(ui_class):
            if isinstance(item, ast.Tuple) and len(item.elts) == 2 and isinstance(item.elts[0], ast.Constant) and isinstance(item.elts[0].value, str) and isinstance(item.elts[1], ast.Dict):
                screens.add(item.elts[0].value)
        choose = ui_methods[ui_names["choose"]]
        kw = choose.args.kwarg.arg if choose.args.kwarg else None
        for item in ast.walk(choose):
            value = item.slice if isinstance(item, ast.Subscript) and _name(item.value) == kw else item.args[0] if isinstance(item, ast.Call) and _name(item.func) == str(kw) + ".get" and item.args else None
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                inputs.add(value.value)
        option_inputs = {}
        option_arg = choose.args.args[1].arg if len(choose.args.args) > 1 else None
        for item in ast.walk(choose):
            if not isinstance(item, ast.If) or not isinstance(item.test, ast.Compare):
                continue
            test = item.test
            if len(test.ops) != 1 or not isinstance(test.left, ast.Name) or test.left.id != option_arg:
                continue
            value = test.comparators[0]
            value = globals_.get(value.id, value) if isinstance(value, ast.Name) else value
            try:
                values = ast.literal_eval(value)
            except (ValueError, TypeError):
                continue
            selected = [values] if isinstance(test.ops[0], ast.Eq) else list(values) if isinstance(test.ops[0], ast.In) and isinstance(values, (dict, list, tuple, set)) else []
            fields = set()
            for statement in item.body:
                for expression in ast.walk(statement):
                    key = expression.slice if isinstance(expression, ast.Subscript) and _name(expression.value) == kw else expression.args[0] if isinstance(expression, ast.Call) and _name(expression.func) == str(kw) + ".get" and expression.args else None
                    if isinstance(key, ast.Constant) and isinstance(key.value, str):
                        fields.add(key.value)
            for value in selected:
                if isinstance(value, str) and value in options:
                    option_inputs[value] = sorted(fields)
        # Values assembled by the offer method but not chosen through a static
        # condition retain the unknown input boundary, rather than an empty one.
        if missing := options - option_inputs.keys():
            unknown.append("UI input fields not bound to a static choice: " + ", ".join(sorted(missing)))
        ui_refusal = sorted({
            spelling for item in ast.walk(choose) if isinstance(item, ast.Raise) and item.exc is not None
            if (spelling := _name(item.exc)) in {"ValueError", "TypeError", "KeyError", "IndexError", "RuntimeError"}
        })
        ctor = ui_methods.get("__init__")
        rows = _signature(ctor) if ctor else []
        known_ui = {}
        for (_method, arg), kind in bindings.items():
            known_ui.setdefault(arg, set()).add(kind)
        for row in rows:
            kinds = known_ui.get(row["name"], set())
            row["entity"] = next(iter(kinds)) if len(kinds) == 1 else None
        references = []
        for item in ast.walk(ctor) if ctor else ():
            if not isinstance(item, ast.Assign) or not isinstance(item.value, ast.Name):
                continue
            if item.value.id not in {row["name"] for row in rows}:
                continue
            for target in item.targets:
                if not isinstance(target, ast.Attribute) or _name(target.value) != "self":
                    continue
                for fn in ui_methods.values():
                    aliases_ = {"self." + target.attr}
                    for expr in ast.walk(fn):
                        if isinstance(expr, ast.Assign) and _name(expr.value) in aliases_:
                            aliases_.update(value.id for value in expr.targets if isinstance(value, ast.Name))
                    if any(isinstance(expr, ast.Call) and isinstance(expr.func, ast.Attribute) and _name(expr.func.value) in aliases_ and expr.func.attr in methods for expr in ast.walk(fn)):
                        references.append((item.value.id, target.attr))
        references = sorted(set(references))
        ui_constructor = {"parameters": rows, "system_parameter": references[0][0] if len(references) == 1 else None,
                          "system_attribute": references[0][1] if len(references) == 1 else None,
                          "source": {"path": ui_path, "function": ui_class.name + ".__init__", "line": ctor.lineno if ctor else ui_class.lineno}}
        if len(references) != 1:
            unknown.append("UI constructor system reference is not uniquely bound")
        ui_facts = {"options": sorted(options), "screens": sorted(screens), "inputs": sorted(inputs), "option_inputs": option_inputs}

    # These are source-bound search hints, not an evaluator for arbitrary Python.
    settings_attributes = set()
    for item in ast.walk(init) if init else ():
        if isinstance(item, (ast.Assign, ast.AnnAssign)) and item.value is not None:
            targets = item.targets if isinstance(item, ast.Assign) else [item.target]
            has_settings = any(isinstance(expr, ast.Call) and resolve(_name(expr.func), path) == settings for expr in ast.walk(item.value))
            has_parameter = isinstance(item.value, ast.Name) and item.value.id == parameter
            if has_settings or has_parameter:
                settings_attributes.update(target.attr for target in targets if isinstance(target, ast.Attribute) and _name(target.value) == "self")
    setting_query_reads = {name: [] for name in settings_values}
    for query in queries:
        for symbol in closure(method_symbols[query]):
            fn = functions.get(symbol)
            if fn is None or not symbol.startswith(path + "#" + cls.name + "."):
                continue
            for item in ast.walk(fn):
                if isinstance(item, ast.Attribute) and isinstance(item.ctx, ast.Load) and item.attr in settings_values and isinstance(item.value, ast.Attribute) and item.value.attr in settings_attributes and _name(item.value.value) == "self":
                    setting_query_reads[item.attr].append(query)
    setting_query_reads = {name: sorted(set(values)) for name, values in setting_query_reads.items()}
    getters = {}
    for name, binding in entity_queries.items():
        returned = [item.value for item in ast.walk(methods[name]) if isinstance(item, ast.Return)]
        if len(returned) == 1 and isinstance(returned[0], ast.Attribute):
            getters.setdefault(returned[0].attr, []).append((name, binding))

    def guard_facts(symbols):
        source_rows, comparisons = [], []
        operators = {ast.Gt: ">", ast.GtE: ">=", ast.Lt: "<", ast.LtE: "<=", ast.Eq: "==", ast.NotEq: "!="}
        inverse = {">": "<", ">=": "<=", "<": ">", "<=": ">=", "==": "==", "!=": "!="}
        for symbol in sorted(symbols):
            fn = functions.get(symbol)
            if fn is None:
                continue
            source, _, qualified = symbol.partition("#")
            assigned = {target.id: item.value for item in ast.walk(fn) if isinstance(item, ast.Assign)
                        for target in item.targets if isinstance(target, ast.Name)}
            def expand(value):
                seen = set()
                while isinstance(value, ast.Name) and value.id in assigned and value.id not in seen:
                    seen.add(value.id)
                    value = assigned[value.id]
                return value
            def threshold(value):
                value = expand(value)
                if isinstance(value, ast.Attribute) and isinstance(value.value, ast.Attribute) and value.value.attr in settings_attributes and _name(value.value.value) == "self" and value.attr in settings_values:
                    return {"setting": value.attr}
                if isinstance(value, ast.Constant) and type(value.value) in (int, float):
                    return {"value": value.value}
                return None
            for item in ast.walk(fn):
                test = item.test if isinstance(item, (ast.If, ast.IfExp)) else item.value if isinstance(item, ast.Return) and isinstance(item.value, (ast.Compare, ast.BoolOp)) else None
                if test is not None:
                    source_rows.append({"path": source, "function": qualified, "line": item.lineno, "expression": ast.unparse(test)})
                if not isinstance(item, ast.Compare) or len(item.ops) != 1 or type(item.ops[0]) not in operators:
                    continue
                left, right = expand(item.left), expand(item.comparators[0])
                op = operators[type(item.ops[0])]
                for value, bound, operation in ((left, right, op), (right, left, inverse[op])):
                    limit = threshold(bound)
                    if not isinstance(value, ast.Attribute) or limit is None:
                        continue
                    for query, binding in getters.get(value.attr, ()):
                        if not any(bindings.get((fn.name, row["name"])) == binding["entity"] for row in _signature(fn)):
                            continue
                        comparisons.append({"query": query, **binding, "operator": operation, "threshold": limit,
                                            "source": {"path": source, "function": qualified, "line": item.lineno, "expression": ast.unparse(item)}})
        unique = lambda rows: [json.loads(key) for key in sorted({json.dumps(row, sort_keys=True) for row in rows})]
        return unique(source_rows), unique(comparisons)

    def preferred_guards(symbols, tokens):
        selected, sources_ = set(), []
        def positive_helpers(test):
            if isinstance(test, ast.BoolOp) and isinstance(test.op, ast.And):
                return set().union(*(positive_helpers(item) for item in test.values))
            if isinstance(test, ast.Call) and isinstance(test.func, ast.Attribute) and _name(test.func.value) == "self" and test.func.attr in method_symbols:
                return {symbol for symbol in closure(method_symbols[test.func.attr]) if symbol.startswith(path + "#" + cls.name + ".")}
            return set()
        for symbol in sorted(symbols):
            fn = functions.get(symbol)
            if fn is None:
                continue
            source, _, qualified = symbol.partition("#")
            def visit(node, conditions=()):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    return
                if isinstance(node, ast.If):
                    for item in node.body:
                        visit(item, (*conditions, node))
                    for item in node.orelse:
                        visit(item, conditions)
                    return
                targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
                assigned = targets and any(isinstance(item, (ast.Attribute, ast.Subscript)) for item in targets) and isinstance(node.value, ast.Constant) and node.value.value in tokens
                called = isinstance(node, ast.Call) and any(isinstance(item, ast.Constant) and item.value in tokens for item in node.args)
                if assigned or called:
                    for condition in conditions:
                        sources_.append({"path": source, "function": qualified, "line": condition.lineno, "expression": ast.unparse(condition.test)})
                        selected.update(positive_helpers(condition.test))
                for item in ast.iter_child_nodes(node):
                    visit(item, conditions)
            for statement in fn.body:
                visit(statement)
        expanded, comparisons = guard_facts(selected)
        sources_.extend(expanded)
        return [json.loads(key) for key in sorted({json.dumps(row, sort_keys=True) for row in sources_})], comparisons

    goal_guards = []
    for name in actions:
        sources_, comparisons = guard_facts(closure(method_symbols[name]))
        goal_guards.append({"goal": {"kind": "action", "receiver": "system", "name": name, "outcome": "success"},
                            "actions": [name], "sources": sources_, "comparisons": comparisons,
                            "preferred_sources": [], "preferred_comparisons": []})
    for query, values in statuses.items():
        for value in values:
            tokens = {value}
            for item in ast.walk(methods[query]):
                if isinstance(item, ast.If) and any(isinstance(expr, ast.Return) and isinstance(expr.value, ast.Constant) and expr.value.value == value for statement in item.body for expr in ast.walk(statement)):
                    tokens.update(expr.value for expr in ast.walk(item.test) if isinstance(expr, ast.Constant) and isinstance(expr.value, str))
            relevant = []
            for name in actions:
                for symbol in closure(method_symbols[name]):
                    fn = functions.get(symbol)
                    if fn and any((isinstance(expr, (ast.Assign, ast.AnnAssign)) and isinstance(expr.value, ast.Constant) and expr.value.value in tokens)
                                  or (isinstance(expr, ast.Call) and any(isinstance(arg, ast.Constant) and arg.value in tokens for arg in expr.args)) for expr in ast.walk(fn)):
                        relevant.append(name)
                        break
            symbols = closure(method_symbols[query]) | set().union(*(closure(method_symbols[name]) for name in relevant))
            sources_, comparisons = guard_facts(symbols)
            preferred_sources, preferred_comparisons = preferred_guards(symbols, tokens)
            goal_guards.append({"goal": {"kind": "query", "receiver": "system", "query": query, "value": value},
                                "actions": sorted(relevant), "sources": sources_, "comparisons": comparisons,
                                "preferred_sources": preferred_sources, "preferred_comparisons": preferred_comparisons})
    if ui:
        for kind, values in (("option", ui_facts["options"]), ("screen", ui_facts["screens"])):
            for value in values:
                selected = [fn for fn in ui_methods.values() if any(isinstance(expr, ast.Constant) and expr.value == value for expr in ast.walk(fn))]
                if kind == "option" and options_fn not in selected:
                    selected.append(options_fn)
                referenced = {expr.func.attr for fn in selected for expr in ast.walk(fn) if isinstance(expr, ast.Call) and isinstance(expr.func, ast.Attribute) and expr.func.attr in methods}
                ui_symbols = {ui_path + "#" + ui_class.name + "." + fn.name for fn in selected}
                sources_, comparisons = guard_facts(ui_symbols | set().union(*(closure(method_symbols[name]) for name in referenced)))
                preferred_sources, preferred_comparisons = preferred_guards({ui_path + "#" + ui_class.name + "." + options_fn.name}, {value}) if kind == "option" else ([], [])
                goal = {"kind": kind, "value": value, "ui_class": ui}
                goal_guards.append({"goal": goal, "actions": sorted(referenced & set(actions)),
                                    "sources": sources_, "comparisons": comparisons,
                                    "preferred_sources": preferred_sources, "preferred_comparisons": preferred_comparisons})

    def location(source, fn, item=None):
        return {"path": source, "function": fn, "line": (item or functions[source + "#" + fn]).lineno}

    predictor_bindings = []
    for predictor, action in predictors:
        expected = {row["name"] for row in parameters[predictor]}
        available = {row["name"] for row in parameters[action]}
        mappings = []
        direct = False
        unresolved = False
        for item in ast.walk(methods[action]):
            if not isinstance(item, ast.Call) or _name(item.func) != "self." + predictor:
                continue
            direct = True
            values = {row["name"]: value for row, value in zip(parameters[predictor], item.args)}
            values.update({row.arg: row.value for row in item.keywords})
            if set(values) == expected and all(isinstance(value, ast.Name) and value.id in available for value in values.values()):
                mappings.append({name: value.id for name, value in values.items()})
            else:
                unresolved = True
        if not direct and expected <= available:
            mappings.append({name: name for name in expected})
        unique = {json.dumps(row, sort_keys=True) for row in mappings}
        if unresolved or len(unique) != 1 or methods[predictor].args.vararg or methods[predictor].args.kwarg:
            unknown.append("predictor arguments are not uniquely source-bound: " + predictor)
            continue
        mapping = json.loads(next(iter(unique)))
        predictor_bindings.append({"predictor": predictor, "action": action,
                                   "allow": "none" if predictor.startswith("why_not_") else "true",
                                   "parameters": [{"predictor": row["name"], "action": mapping[row["name"]]} for row in parameters[predictor]],
                                   "sources": [location(path, cls.name + "." + predictor)]})

    ui_bindings = []
    if ui and ui_constructor["system_attribute"]:
        system_reference = {"ui_path": [ui_constructor["system_attribute"]]}
        unbound_choices = set()
        def ui_value(item, environment):
            if isinstance(item, ast.Name):
                if item.id in environment:
                    return environment[item.id]
                item = globals_.get(item.id, item)
            if isinstance(item, ast.Constant):
                return {"value": item.value} if type(item.value) in (str, int, float, bool, type(None)) else None
            if isinstance(item, ast.Attribute):
                parent = ui_value(item.value, environment)
                return {"ui_path": [*parent["ui_path"], item.attr]} if parent and "ui_path" in parent else None
            if isinstance(item, ast.Subscript):
                parent = ui_value(item.value, environment)
                try:
                    key = ast.literal_eval(item.slice)
                except (ValueError, TypeError):
                    return None
                if parent and "ui_path" in parent and type(key) in (str, int):
                    return {"ui_path": [*parent["ui_path"], key]}
                if parent == {"inputs": True} and isinstance(key, str):
                    return {"input": key}
            if isinstance(item, ast.Call) and isinstance(item.func, ast.Attribute) and item.func.attr == "get" and ui_value(item.func.value, environment) == {"inputs": True} and item.args:
                key = ui_value(item.args[0], environment)
                if key and isinstance(key.get("value"), str):
                    return {"input": key["value"]}
            return None
        def ui_arguments(fn, item, environment):
            rows = _signature(fn)
            positional = [row for row in rows if row["name"] not in {arg.arg for arg in fn.args.kwonlyargs}]
            if fn.args.vararg or fn.args.kwarg or len(item.args) > len(positional) or any(isinstance(arg, ast.Starred) for arg in item.args) or any(row.arg is None for row in item.keywords):
                return None
            values = {row["name"]: ui_value(value, environment) for row, value in zip(positional, item.args)}
            values.update({row.arg: ui_value(row.value, environment) for row in item.keywords})
            if set(values) - {row["name"] for row in rows}:
                return None
            for row in rows:
                if row["name"] not in values and "default" in row:
                    values[row["name"]] = {"value": row["default"]}
            return values if all(values.get(row["name"]) is not None for row in rows) else None
        def ui_recipe(action, values):
            rows = parameters[action]
            values = dict(values)
            for row in rows:
                if row["name"] not in values and "default" in row:
                    values[row["name"]] = {"value": row["default"]}
            if any(values.get(row["name"]) is None for row in rows):
                return None
            keyword_names = {row.arg for row in methods[action].args.kwonlyargs}
            return {"args": [values[row["name"]] for row in rows if row["name"] not in keyword_names],
                    "kwargs": {row["name"]: values[row["name"]] for row in rows if row["name"] in keyword_names}}
        def ui_target(item, environment):
            if isinstance(item.func, ast.Attribute):
                return ui_value(item.func.value, environment), item.func.attr
            if isinstance(item.func, ast.Call) and _name(item.func.func) == "getattr" and len(item.func.args) == 2:
                name = ui_value(item.func.args[1], environment)
                return ui_value(item.func.args[0], environment), name.get("value") if name else None
            return None, None
        def choice_truth(test, environment):
            if isinstance(test, ast.Constant) and type(test.value) is bool:
                return test.value
            if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
                value = choice_truth(test.operand, environment)
                return None if value is None else not value
            if isinstance(test, ast.BoolOp):
                values = [choice_truth(value, environment) for value in test.values]
                if isinstance(test.op, ast.And):
                    return False if False in values else True if all(value is True for value in values) else None
                if isinstance(test.op, ast.Or):
                    return True if True in values else False if all(value is False for value in values) else None
            if isinstance(test, ast.Compare) and len(test.ops) == 1:
                left = ui_value(test.left, environment)
                right = ui_value(test.comparators[0], environment)
                if isinstance(test.comparators[0], ast.Name) and test.comparators[0].id in globals_:
                    try:
                        right = {"value": ast.literal_eval(globals_[test.comparators[0].id])}
                    except (ValueError, TypeError):
                        pass
                if left and right and "value" in left and "value" in right:
                    if isinstance(test.ops[0], ast.Eq):
                        return left["value"] == right["value"]
                    if isinstance(test.ops[0], ast.NotEq):
                        return left["value"] != right["value"]
                    if isinstance(test.ops[0], (ast.In, ast.NotIn)) and isinstance(right["value"], (tuple, list, dict, set)):
                        found = left["value"] in right["value"]
                        return not found if isinstance(test.ops[0], ast.NotIn) else found
            return None
        def phase_conditions(test, environment, positive):
            if choice_truth(test, environment) is not None:
                return [], False
            if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
                return phase_conditions(test.operand, environment, not positive)
            if isinstance(test, ast.BoolOp) and isinstance(test.op, ast.And) and positive:
                parts = [phase_conditions(value, environment, True) for value in test.values]
                return [row for rows, _ in parts for row in rows], any(unknown_ for _, unknown_ in parts)
            if isinstance(test, ast.Compare) and len(test.ops) == 1 and isinstance(test.ops[0], (ast.Eq, ast.NotEq)):
                left = ui_value(test.left, environment)
                right = ui_value(test.comparators[0], environment)
                if left and right and "value" in left and "ui_path" in right:
                    left, right = right, left
                if left and right and "ui_path" in left and "value" in right:
                    equal = isinstance(test.ops[0], ast.Eq)
                    return [{"ui_path": left["ui_path"], "value": right["value"], "equal": equal == positive}], False
            return [], True
        def ui_walk(fn, environment, option, trail=(), conditions=(), path_guards=(), context_unknown=False):
            if fn.name in trail:
                unbound_choices.add(option)
                return
            def assign(target, value, env):
                if isinstance(target, ast.Name):
                    env[target.id] = ui_value(value, env)
                elif isinstance(target, (ast.Tuple, ast.List)):
                    if isinstance(value, (ast.Tuple, ast.List)) and len(target.elts) == len(value.elts):
                        for destination, source_ in zip(target.elts, value.elts):
                            assign(destination, source_, env)
                    elif (reference := ui_value(value, env)) and "ui_path" in reference:
                        for index, destination in enumerate(target.elts):
                            if isinstance(destination, ast.Name):
                                env[destination.id] = {"ui_path": [*reference["ui_path"], index]}
            def record(action, predictor, values, item, phases, uncertain):
                recipe = ui_recipe(action, values)
                if recipe is None:
                    unbound_choices.add(option)
                    return
                ui_bindings.append({"option": option, "action": action, "predictor": predictor["predictor"], "allow": predictor["allow"], **recipe,
                                    "guards": list(phases), "context_unknown": uncertain,
                                    "sources": [location(ui_path, ui_class.name + "." + fn.name, item), *predictor["sources"]]})
            def visit(statements, env, guards, phases, uncertain):
                for statement in statements:
                    if isinstance(statement, ast.Assign):
                        for target in statement.targets:
                            assign(target, statement.value, env)
                    if isinstance(statement, ast.If):
                        truth = choice_truth(statement.test, env)
                        if truth is not False:
                            added, unresolved_ = phase_conditions(statement.test, env, True)
                            visit(statement.body, dict(env), (*guards, statement.test), (*phases, *added), uncertain or unresolved_)
                        if truth is not True:
                            added, unresolved_ = phase_conditions(statement.test, env, False)
                            visit(statement.orelse, dict(env), guards, (*phases, *added), uncertain or unresolved_)
                        continue
                    if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        continue
                    for item in ast.walk(statement):
                        if not isinstance(item, ast.Call):
                            continue
                        receiver, name = ui_target(item, env)
                        if receiver == system_reference and name in actions:
                            values = ui_arguments(methods[name], item, env)
                            matches = [row for row in predictor_bindings if row["action"] == name]
                            if values is None or not matches:
                                unbound_choices.add(option)
                            else:
                                for predictor in matches:
                                    record(name, predictor, values, item, phases, uncertain)
                        elif receiver == {"ui_path": []} and name in ui_methods:
                            values = ui_arguments(ui_methods[name], item, env)
                            if values is None:
                                unbound_choices.add(option)
                            else:
                                ui_walk(ui_methods[name], {"self": {"ui_path": []}, **values}, option, (*trail, fn.name), guards, phases, uncertain)
                        if fn is options_fn and isinstance(item.func, ast.Attribute) and item.func.attr == "append" and item.args and ui_value(item.args[0], env) == {"value": option}:
                            for guard in guards:
                                for call_ in ast.walk(guard):
                                    if not isinstance(call_, ast.Call):
                                        continue
                                    target, predicted = ui_target(call_, env)
                                    matches = [row for row in predictor_bindings if row["predictor"] == predicted] if target == system_reference else []
                                    for predictor in matches:
                                        values = ui_arguments(methods[predicted], call_, env)
                                        if values is None:
                                            unbound_choices.add(option)
                                        else:
                                            record(predictor["action"], predictor, {row["action"]: values[row["predictor"]] for row in predictor["parameters"]}, item, phases, uncertain)
            visit(fn.body, dict(environment), conditions, path_guards, context_unknown)
        for option in ui_facts["options"]:
            choose_environment = {"self": {"ui_path": []}, choose.args.args[1].arg: {"value": option}}
            if choose.args.kwarg:
                choose_environment[choose.args.kwarg.arg] = {"inputs": True}
            ui_walk(choose, choose_environment, option)
            ui_walk(options_fn, {"self": {"ui_path": []}}, option)
        grouped = {}
        for row in ui_bindings:
            grouped.setdefault(row["option"], []).append(row)
        ui_bindings = []
        for option, rows in sorted(grouped.items()):
            recipes = {json.dumps({key: row[key] for key in ("action", "args", "kwargs")}, sort_keys=True) for row in rows}
            if len(recipes) != 1 or option in unbound_choices:
                unknown.append("UI choice arguments are not uniquely source-bound: " + option)
                continue
            merged = {}
            for row in rows:
                key = json.dumps({key: value for key, value in row.items() if key != "sources"}, sort_keys=True)
                merged.setdefault(key, {**row, "sources": []})["sources"].extend(row["sources"])
            for row in merged.values():
                row["sources"] = [json.loads(key) for key in sorted({json.dumps(value, sort_keys=True) for value in row["sources"]})]
                ui_bindings.append(row)
        unknown.extend("UI choice arguments are not source-bound: " + option for option in sorted(unbound_choices - grouped.keys()))

    def library(item, source, name):
        spelling = _name(item)
        first, _, tail = spelling.partition(".")
        imported = raw["files"][source]["imports"].get(first, "").replace(":", ".")
        return imported + ("." + tail if tail else "") == name
    def function_target(item, source):
        spelling = _name(item)
        if source + "#" + spelling in functions:
            return source + "#" + spelling
        first, _, tail = spelling.partition(".")
        imported = raw["files"][source]["imports"].get(first, "").replace(":", ".")
        complete = imported + ("." + tail if tail else "")
        candidates_ = [symbol for symbol in functions if inv.py[symbol.partition("#")[0]].module + "." + symbol.partition("#")[2] == complete]
        return candidates_[0] if len(candidates_) == 1 else None
    def reference(item, source, env):
        if isinstance(item, ast.Name):
            value = env.get(item.id)
            return reference(value[1], value[2], value[3]) if value and value[0] == "expression" else value
        if isinstance(item, ast.Attribute) and reference(item.value, source, env) == ("system",) and item.attr in settings_attributes:
            return ("settings", item.attr)
        return None
    def local_environment(fn, source, values):
        env = dict(values)
        for item in fn.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        env[target.id] = ("expression", item.value, source, dict(env))
        return env
    def bound_function(symbol, item, source, env):
        fn = functions[symbol]
        rows = [*fn.args.posonlyargs, *fn.args.args]
        if len(item.args) > len(rows) or any(isinstance(value, ast.Starred) for value in item.args) or any(value.arg is None for value in item.keywords):
            return None
        values = {arg.arg: ("expression", value, source, dict(env)) for arg, value in zip(rows, item.args)}
        values.update({value.arg: ("expression", value.value, source, dict(env)) for value in item.keywords})
        return local_environment(fn, symbol.partition("#")[0], values)
    def mirrors(item, source, env, trail=()):
        if isinstance(item, ast.Name):
            value = env.get(item.id)
            return mirrors(value[1], value[2], value[3], trail) if value and value[0] == "expression" else []
        if isinstance(item, ast.Dict):
            if any(key is None or not isinstance(key, ast.Constant) or not isinstance(key.value, str) for key in item.keys):
                return []
            return [{**row, "path": [key.value, *row["path"]]} for key, value in zip(item.keys, item.values) for row in mirrors(value, source, env, trail)]
        if not isinstance(item, ast.Call):
            return []
        if library(item.func, source, "dataclasses.asdict") and len(item.args) == 1:
            value = reference(item.args[0], source, env)
            if value and value[0] == "settings":
                return [{"attribute": value[1], "path": [], "sources": [{"path": source, "function": trail[-1].partition("#")[2], "line": item.lineno}]}]
        if isinstance(item.func, ast.Attribute) and (value := reference(item.func.value, source, env)) and value[0] == "settings" and not item.args and not item.keywords:
            cfg_path, cfg_class = classes[settings]
            symbol = cfg_path + "#" + cfg_class.name + "." + item.func.attr
            if symbol in functions and symbol not in trail:
                fn = functions[symbol]
                returns = [statement for statement in fn.body if isinstance(statement, ast.Return)]
                if len(returns) == 1:
                    return mirrors(returns[0].value, cfg_path, local_environment(fn, cfg_path, {"self": value}), (*trail, symbol))
        if isinstance(item.func, ast.Attribute) and reference(item.func.value, source, env) == ("system",) and item.func.attr in method_symbols and not item.args and not item.keywords:
            symbol = method_symbols[item.func.attr]
            fn = functions[symbol]
            returns = [statement for statement in fn.body if isinstance(statement, ast.Return)]
            if symbol not in trail and len(returns) == 1:
                rows = mirrors(returns[0].value, path, local_environment(fn, path, {"self": ("system",)}), (*trail, symbol))
                for row in rows:
                    row["sources"].append(location(path, cls.name + "." + fn.name, returns[0]))
                return rows
        symbol = function_target(item.func, source)
        if symbol and symbol not in trail:
            fn = functions[symbol]
            returns = [statement for statement in fn.body if isinstance(statement, ast.Return)]
            values = bound_function(symbol, item, source, env)
            if len(returns) == 1 and values is not None:
                rows = mirrors(returns[0].value, symbol.partition("#")[0], values, (*trail, symbol))
                for row in rows:
                    row["sources"].append(location(symbol.partition("#")[0], symbol.partition("#")[2], returns[0]))
                return rows
        return []
    writers = {}
    def json_writers(symbol, env, trail=()):
        if symbol in trail:
            return
        fn = functions[symbol]
        source, _, qualified = symbol.partition("#")
        env = local_environment(fn, source, env)
        for item in ast.walk(fn):
            if not isinstance(item, ast.Call):
                continue
            payload = item.args[0] if library(item.func, source, "json.dump") and item.args else None
            if isinstance(item.func, ast.Attribute) and item.func.attr in {"write_text", "write_bytes", "write"} and item.args:
                encoded = item.args[0]
                while isinstance(encoded, ast.Name) and (value := env.get(encoded.id)) and value[0] == "expression":
                    encoded = value[1]
                payload = encoded.args[0] if isinstance(encoded, ast.Call) and library(encoded.func, source, "json.dumps") and encoded.args else None
                if payload is None:
                    writers[(source, item.lineno)] = []
            if payload is not None:
                rows = mirrors(payload, source, env, (*trail, symbol))
                for row in rows:
                    row["sources"].extend([location(source, qualified, item), *[location(value.partition("#")[0], value.partition("#")[2]) for value in (*trail, symbol)]])
                writers[(source, item.lineno)] = rows
            target = function_target(item.func, source)
            if target and (values := bound_function(target, item, source, env)) is not None:
                json_writers(target, values, (*trail, symbol))
    serializer_settings_mirror = None
    if persistence and settings:
        json_writers(method_symbols[persistence["save"]], {"self": ("system",)})
        rows = next(iter(writers.values())) if len(writers) == 1 else []
        shapes = {(row["attribute"], tuple(row["path"])) for row in rows}
        if len(shapes) == 1:
            attribute, keys = next(iter(shapes))
            serializer_settings_mirror = {"attribute": attribute, "path": list(keys), "format": "json",
                                          "sources": [json.loads(key) for key in sorted({json.dumps(value, sort_keys=True) for row in rows for value in row["sources"]})]}
        else:
            unknown.append("settings mirror is not uniquely source-bound to the public JSON save")
    optional_calls = {}
    for caller, fn in functions.items():
        source, _, qualified = caller.partition("#")
        for item in ast.walk(fn):
            if not isinstance(item, ast.Call):
                continue
            target = function_target(item.func, source)
            bound = False
            if isinstance(item.func, ast.Attribute):
                receiver = _name(item.func.value)
                if source == path and qualified.startswith(cls.name + ".") and receiver == "self" and item.func.attr in method_symbols:
                    target, bound = method_symbols[item.func.attr], True
                elif ui and ui_constructor["system_attribute"] and source == ui_path and qualified.startswith(ui_class.name + "."):
                    aliases_ = {"self." + ui_constructor["system_attribute"]}
                    assignments = sorted((node for node in ast.walk(fn) if isinstance(node, ast.Assign) and node.lineno < item.lineno), key=lambda node: (node.lineno, node.col_offset))
                    for assignment in assignments:
                        pairs = [(destination, assignment.value) for destination in assignment.targets]
                        if len(assignment.targets) == 1 and isinstance(assignment.targets[0], (ast.Tuple, ast.List)) and isinstance(assignment.value, (ast.Tuple, ast.List)) and len(assignment.targets[0].elts) == len(assignment.value.elts):
                            pairs = list(zip(assignment.targets[0].elts, assignment.value.elts))
                        previous = set(aliases_)
                        for destination, value in pairs:
                            if isinstance(destination, ast.Name):
                                if _name(value) in previous:
                                    aliases_.add(destination.id)
                                else:
                                    aliases_.discard(destination.id)
                    if receiver in aliases_ and item.func.attr in method_symbols:
                        target, bound = method_symbols[item.func.attr], True
            if target is None:
                continue
            callee = functions[target]
            decorators = {_name(value) for value in callee.decorator_list}
            if "staticmethod" in decorators:
                bound = False
            elif "classmethod" in decorators:
                bound = True
            positional = [*callee.args.posonlyargs, *callee.args.args]
            defaults = [None] * (len(positional) - len(callee.args.defaults)) + list(callee.args.defaults)
            optional = [(argument.arg, index - int(bound)) for index, (argument, default) in enumerate(zip(positional, defaults)) if default is not None]
            optional.extend((argument.arg, None) for argument, default in zip(callee.args.kwonlyargs, callee.args.kw_defaults) if default is not None)
            if not optional:
                continue
            if any(isinstance(argument, ast.Starred) for argument in item.args) or any(keyword.arg is None for keyword in item.keywords):
                unknown.append("optional argument usage is not statically bound: " + source + ":" + str(item.lineno))
                continue
            provided = {keyword.arg for keyword in item.keywords}
            for parameter_name, index in optional:
                state = "provided" if parameter_name in provided or index is not None and 0 <= index < len(item.args) else "omitted"
                row = optional_calls.setdefault((target, parameter_name), {"provided": [], "omitted": []})
                row[state].append(location(source, qualified, item))
    optional_argument_advice = []
    for (target, parameter_name), usage in sorted(optional_calls.items()):
        if usage["provided"] and usage["omitted"] and any(left["path"] != right["path"] for left in usage["provided"] for right in usage["omitted"]):
            optional_argument_advice.append({"function": target, "parameter": parameter_name,
                                             **{state: [json.loads(key) for key in sorted({json.dumps(row, sort_keys=True) for row in rows})] for state, rows in usage.items()}})
    aliases, budgets = {}, {}
    for row in corrections:
        if row["kind"] == "exclude":
            raise SkeletonError(f"skeleton_removes_goal .flowguard/skeleton.py:{row['line']}: generated goals cannot be removed")
        if row["kind"] == "alias":
            if len(row["args"]) != 2 or not all(isinstance(value, str) for value in row["args"]):
                raise SkeletonError("alias_syntax: expected two strings")
            aliases[row["args"][0]] = row["args"][1]
        elif row["kind"] == "budget":
            budgets[row["kwargs"].get("world", "default")] = {key: value for key, value in row["kwargs"].items() if key not in {"world", "why"}}
        elif row["kind"] not in {"pin", "ui", "adapter", "world"}:
            raise SkeletonError(f"correction_not_supported .flowguard/skeleton.py:{row['line']}: {row['kind']} needs a later execution capability")
    for source, facts in raw["files"].items():
        unknown.extend(source + ":" + item["symbol"] + " (" + item["kind"] + ")" for item in facts["entrypoints"])
    counts = {kind: sum(row.get("entity") == kind for rows in parameters.values() for row in rows) for kind in entities}
    item_kind = max(counts, key=counts.get) if counts else None
    worlds = {"small": {kind: 1 for kind in entities}, "default": {kind: 4 if kind == item_kind else 2 for kind in entities}, "crowded": {kind: 6 if kind == item_kind else 1 for kind in entities}}
    for row in corrections:
        if row["kind"] == "world":
            if len(row["args"]) != 2 or not isinstance(row["args"][0], str) or not isinstance(row["args"][1], dict):
                raise SkeletonError("world_syntax: expected a name and entity counts")
            name, sizes = row["args"]
            if set(sizes) != set(entities) or any(type(value) is not int or value < 1 for value in sizes.values()):
                raise SkeletonError("skeleton_removes_goal: every entity needs a positive finite size")
            if name in worlds and any(sizes[kind] < value for kind, value in worlds[name].items()):
                raise SkeletonError("skeleton_removes_goal: a correction cannot shrink a generated world")
            worlds[name] = sizes
    unsupported = []
    for source, tree in trees.items():
        if any(isinstance(node, (ast.Global, ast.Nonlocal)) for node in ast.walk(tree)):
            unsupported.append(source + ": dynamic global or closure state needs an explicit world")
    return {"root": str(root), "classes": sorted(classes), "input_files": sorted(inv.py),
            "source_files": sorted(trees),
            "source_functions": sorted(source + "#" + name for source, tree in trees.items() for _, _, name in function_spans(tree)),
            "system": system, "settings": settings, "settings_parameter": parameter,
            "shipped": settings_values, "refusal": sorted(locator for locator in classes if is_refusal(locator)),
            "entities": entities, "actions": actions, "queries": queries, "parameters": parameters,
            "predictor_pairs": sorted(predictors), "status_values": statuses, "ui": ui, "ui_methods": ui_names, "ui_facts": ui_facts,
            "predictor_bindings": predictor_bindings, "ui_bindings": ui_bindings,
            "settings_attributes": sorted(settings_attributes), "serializer_settings_mirror": serializer_settings_mirror,
            "setting_query_reads": setting_query_reads,
            "optional_argument_advice": optional_argument_advice,
            "entity_queries": entity_queries, "ui_constructor": ui_constructor, "ui_refusal": ui_refusal, "goal_guards": goal_guards,
            "persistence": persistence, "file_inputs": sorted(file_inputs), "worlds": worlds,
            "aliases": aliases, "budgets": budgets, "unsupported": unsupported,
            "corrections": corrections, "unknown": sorted(set(unknown)),
            "glossary": sorted({term for value in [*actions, *queries, *entities] for term in value.split("_")}),
            "sources": {role: {"locator": locator, "path": classes[locator][0], "line": classes[locator][1].lineno} for role, locator in {"system": system, "settings": settings, "ui": ui}.items() if locator}}


def write_pins(root, spec):
    root = Path(root)
    corrections = read_corrections(root)
    existing = {row["args"][0]: row["args"][1] for row in corrections if row["kind"] == "pin"}
    path = root / ".flowguard/skeleton.py"
    additions = []
    for role, source in spec["sources"].items():
        locator = source["locator"]
        if role in existing and existing[role] != locator:
            raise SkeletonError("pin_conflict: " + role)
        if role not in existing:
            additions.append(f'pin({json.dumps(role)}, {json.dumps(locator)}, why="Selected from the current source")\n')
    if additions:
        path.parent.mkdir(parents=True, exist_ok=True)
        original = path.read_bytes() if path.exists() else b""
        suffix = (b"\n" if original and not original.endswith(b"\n") else b"") + "".join(additions).encode("utf-8")
        path.write_bytes(original + suffix)
    return path


def render(spec):
    rows = ["system: " + spec["system"], "settings: " + str(spec["settings"]) + "; shipped=" + json.dumps(spec["shipped"], sort_keys=True),
            "refusal: " + ", ".join(spec["refusal"]), "entities: " + ", ".join(sorted(spec["entities"])),
            f"actions ({len(spec['actions'])}): " + ", ".join(spec["actions"]),
            f"queries ({len(spec['queries'])}): " + ", ".join(spec["queries"]),
            "predictor pairs: " + ", ".join(left + " -> " + right for left, right in spec["predictor_pairs"]),
            "status values: " + json.dumps(spec["status_values"], sort_keys=True),
            "ui: " + str(spec["ui"]) + "; " + json.dumps(spec["ui_facts"], sort_keys=True),
            "persistence: " + str(spec["persistence"]), "file inputs: " + ", ".join(spec["file_inputs"]),
            "worlds: " + json.dumps(spec["worlds"], sort_keys=True), "corrections: " + (str(spec["corrections"]) if spec["corrections"] else "none"),
            "unrecognized front doors: " + ("; ".join(spec["unknown"]) or "none"),
            "query purity: not judged until a real call is observed",
            "glossary draft: " + ", ".join(spec["glossary"])]
    return "\n".join(rows)
