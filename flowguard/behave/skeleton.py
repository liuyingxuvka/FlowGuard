"""Derive a skeleton from the existing source inventory and shared syntax."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from flowguard.map.common import read_source
from flowguard.map.discover import discover_inventory
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
    errors = [f"{path}: {info.parse_error}" for path, info in inv.py.items() if not inv.is_test(path) and info.parse_error]
    if errors:
        raise SkeletonError("source_not_parseable: " + "; ".join(errors))
    raw = discover_inventory(root, inv, write_cache=False)
    # These are references into shared syntax, not another persisted source index.
    trees = {path: syntax_tree(read_source(root / path)) for path in raw["files"]}
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
    ui_facts = {"options": [], "screens": [], "inputs": []}
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
        ui_facts = {"options": sorted(options), "screens": sorted(screens), "inputs": sorted(inputs)}
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
    return {"root": str(root), "classes": sorted(classes), "system": system, "settings": settings, "settings_parameter": parameter,
            "shipped": settings_values, "refusal": sorted(locator for locator in classes if is_refusal(locator)),
            "entities": entities, "actions": actions, "queries": queries, "parameters": parameters,
            "predictor_pairs": sorted(predictors), "status_values": statuses, "ui": ui, "ui_methods": ui_names, "ui_facts": ui_facts,
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
