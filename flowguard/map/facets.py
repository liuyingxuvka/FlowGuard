"""Static node facets: literals and source facts, never imported model hooks."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from ..kit import Feature, feature_model_names
from .common import matches_any, read_source, parse_test_anchor
from .inventory import Inventory
from .lint import _variants, explained_by
from .mapfile import component_files, component_scope, component_subtree, is_stale, resolve_model_path


@dataclass(frozen=True)
class Facets:
    purpose: str
    rules: tuple[str, ...]
    rules_source: str
    known_bad: tuple[str, ...]
    known_bad_source: str
    code: tuple[str, ...]
    tests: tuple[str, ...]
    rule_count: int | None
    test_count: int
    rule_notes: tuple[str, ...] = ()    # description of each rule, aligned with ``rules``
    model_id: str = ""
    cases: tuple | None = None          # feature-kit models: (defect names, benign names)

    @property
    def known_bad_count(self) -> int | None:
        return None if self.known_bad_source == "runtime" else len(self.known_bad)

    @property
    def rule_count_text(self) -> str:
        """Exact count, ``~N`` for names merely found in the file, ``?`` when unreadable."""
        if self.rule_count is None:
            return "?"
        return f"~{self.rule_count}" if self.rules_source == "file" else str(self.rule_count)


def _returned_dicts(function):
    """Only this hook's actual return values, not nested helpers or metadata dicts."""
    pending = list(function.body)
    returned = []
    while pending:
        node = pending.pop()
        if isinstance(node, ast.Return):
            returned.append(node.value)
        elif not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            pending.extend(ast.iter_child_nodes(node))
    return returned


_UNKNOWN = object()
BUILTIN_RULE_HELPERS = {"at_most_once_by", "no_duplicate_by", "all_items_have_source", "cache_matches_source"}


def _call_name(call) -> str:
    return call.func.id if isinstance(call.func, ast.Name) else call.func.attr if isinstance(call.func, ast.Attribute) else ""


class _Scope:
    """Module-level names of one model or helper file (static, never imported)."""

    def __init__(self, syntax):
        self.assigns, self.functions, self.imports, self.stars = {}, {}, {}, []
        pending = list(syntax.body)
        while pending:
            node = pending.pop(0)
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                self.assigns[node.targets[0].id] = node.value
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
                self.assigns[node.target.id] = node.value
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.functions[node.name] = node
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                for alias in node.names:
                    if alias.name == "*":
                        self.stars.append(node.module)
                    else:
                        self.imports[alias.asname or alias.name] = (node.module, alias.name)
            elif isinstance(node, ast.If):
                pending[:0] = node.body + node.orelse


def _locals(function) -> dict:
    found = {}
    for node in function.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            found[node.targets[0].id] = node.value
    return found


def _returns(function) -> list:
    return [value for value in _returned_dicts(function) if value is not None]


class _StaticModel:
    """Read rule and known-bad names the way the model builds them, without importing it.

    Rules come from the ``invariants=`` of the ``Explorer(...)`` that ``build_explorer()``
    returns (one same-file call deep); names may live in ``_helper`` files of the same model
    directory or be made by a small wrapper returning ``Invariant(...)``.  Known-bad names
    come from what ``broken_variants()`` returns: literal dicts, comprehensions and loops over
    literal tuples or dicts.  Anything else is unreadable (``None``), never guessed.
    """

    def __init__(self, root, logical, syntax, *, view=None):
        self.root, self.view, self.base = root, view, PurePosixPath(logical).parent
        self.main = _Scope(syntax)
        self.modules = {}
        self.cases = None

    # -- names across the model file and its helper files -------------------------------------
    def _module(self, name):
        if name not in self.modules:
            self.modules[name] = None
            try:
                path = resolve_model_path(self.root, str(self.base / f"{name}.py"), view=self.view)
                if path is not None and path.is_file():
                    self.modules[name] = _Scope(ast.parse(read_source(path)))
            except (OSError, SyntaxError, ValueError):
                pass
        return self.modules[name]

    def _lookup(self, name, scope, kind="assigns", seen=None):
        seen = set() if seen is None else seen
        if (id(scope), name, kind) in seen:
            return None
        seen.add((id(scope), name, kind))
        table = scope.assigns if kind == "assigns" else scope.functions
        if name in table:
            return table[name], scope
        if name in scope.imports:
            module = self._module(scope.imports[name][0])
            return self._lookup(scope.imports[name][1], module, kind, seen) if module else None
        for star in scope.stars:
            module = self._module(star)
            found = self._lookup(name, module, kind, seen) if module else None
            if found:
                return found
        return None

    def value(self, expr, scope, local=None, env=None, depth=0):
        """A literal value, or _UNKNOWN; names resolve through env, locals, module and helpers."""
        local, env = local or {}, env or {}
        if depth > 20:
            return _UNKNOWN
        if isinstance(expr, ast.Constant):
            return expr.value
        if isinstance(expr, (ast.Tuple, ast.List)):
            return tuple(self.value(item, scope, local, env, depth + 1) for item in expr.elts)
        if isinstance(expr, ast.Dict):
            out = {}
            for key, value in zip(expr.keys, expr.values):
                key = self.value(key, scope, local, env, depth + 1) if key is not None else _UNKNOWN
                if key is _UNKNOWN or not isinstance(key, (str, int, tuple)):
                    return _UNKNOWN
                out[key] = self.value(value, scope, local, env, depth + 1)
            return out
        if isinstance(expr, ast.Name):
            if expr.id in env:
                return env[expr.id]
            if expr.id in local:
                return self.value(local[expr.id], scope, {}, {}, depth + 1)
            found = self._lookup(expr.id, scope)
            return self.value(found[0], found[1], None, None, depth + 1) if found else _UNKNOWN
        if isinstance(expr, ast.JoinedStr):
            parts = []
            for part in expr.values:
                if isinstance(part, ast.Constant):
                    parts.append(str(part.value))
                elif isinstance(part, ast.FormattedValue) and part.conversion == -1 and part.format_spec is None:
                    inner = self.value(part.value, scope, local, env, depth + 1)
                    if not isinstance(inner, (str, int)):
                        return _UNKNOWN
                    parts.append(str(inner))
                else:
                    return _UNKNOWN
            return "".join(parts)
        if (isinstance(expr, ast.Call) and isinstance(expr.func, ast.Attribute) and not expr.args and not expr.keywords
                and expr.func.attr in {"keys", "values", "items"}):
            base = self.value(expr.func.value, scope, local, env, depth + 1)
            if isinstance(base, dict):
                return tuple(getattr(base, expr.func.attr)())
            return _UNKNOWN
        if isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Add):
            left = self.value(expr.left, scope, local, env, depth + 1)
            right = self.value(expr.right, scope, local, env, depth + 1)
            if type(left) is type(right) and isinstance(left, (str, tuple)):
                return left + right
        return _UNKNOWN

    # -- rules --------------------------------------------------------------------------------
    def _rule_call(self, call, scope, local):
        name = _call_name(call)
        if name == "Invariant":
            given = dict(zip(("name", "description"), call.args))
            given.update({k.arg: k.value for k in call.keywords if k.arg in {"name", "description"}})
            title = self.value(given["name"], scope, local) if "name" in given else _UNKNOWN
            note = self.value(given["description"], scope, local) if "description" in given else ""
            return [(title, note if isinstance(note, str) else "")] if isinstance(title, str) else None
        if name in BUILTIN_RULE_HELPERS:
            title = self.value(call.args[0], scope, local) if call.args else _UNKNOWN
            return [(title, "")] if isinstance(title, str) else None
        found = self._lookup(name, scope, "functions") if isinstance(call.func, ast.Name) else None
        if not found:
            return None
        function, home = found
        returns = _returns(function)
        if len(returns) == 1 and isinstance(returns[0], (ast.Tuple, ast.List, ast.Name, ast.BinOp)) and not call.args:
            return self.rules(returns[0], home, _locals(function))   # a function that returns the rule list
        if len(returns) != 1 or not isinstance(returns[0], ast.Call) or _call_name(returns[0]) != "Invariant":
            return None
        params = [arg.arg for arg in function.args.posonlyargs + function.args.args + function.args.kwonlyargs]
        bound = dict(zip(params, call.args))
        bound.update({k.arg: k.value for k in call.keywords if k.arg})
        inner = returns[0]
        given = dict(zip(("name", "description"), inner.args))
        given.update({k.arg: k.value for k in inner.keywords if k.arg in {"name", "description"}})

        def resolve(expr):
            if isinstance(expr, ast.Name) and expr.id in bound:
                return self.value(bound[expr.id], scope, local)
            return self.value(expr, home, _locals(function))
        title = resolve(given["name"]) if "name" in given else _UNKNOWN
        note = resolve(given["description"]) if "description" in given else ""
        return [(title, note if isinstance(note, str) else "")] if isinstance(title, str) else None

    def rules(self, expr, scope, local=None, depth=0):
        if depth > 20:
            return None
        if isinstance(expr, (ast.Tuple, ast.List)):
            out = []
            for item in expr.elts:
                found = self.rules(item.value if isinstance(item, ast.Starred) else item, scope, local, depth + 1)
                if found is None:
                    return None
                out += found
            return out
        if isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Add):
            left, right = self.rules(expr.left, scope, local, depth + 1), self.rules(expr.right, scope, local, depth + 1)
            return None if left is None or right is None else left + right
        if isinstance(expr, ast.Call):
            return self._rule_call(expr, scope, local or {})
        if isinstance(expr, ast.Name):
            if local and expr.id in local:
                return self.rules(local[expr.id], scope, None, depth + 1)
            found = self._lookup(expr.id, scope)
            return self.rules(found[0], found[1], None, depth + 1) if found else None
        return None

    # -- feature kit --------------------------------------------------------------------------
    def _features(self, expr, scope, local=None, depth=0):
        """Literal Feature(...) declarations (``apply`` ignored; non-literal codes become placeholders)."""
        if depth > 20:
            return None
        if isinstance(expr, ast.Name):
            if local and expr.id in local:
                return self._features(local[expr.id], scope, None, depth + 1)
            found = self._lookup(expr.id, scope)
            return self._features(found[0], found[1], None, depth + 1) if found else None
        if isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Add):
            left = self._features(expr.left, scope, local, depth + 1)
            right = self._features(expr.right, scope, local, depth + 1)
            return None if left is None or right is None else left + right
        if not isinstance(expr, (ast.Tuple, ast.List)):
            return None
        features = []
        for item in expr.elts:
            if isinstance(item, ast.Starred):
                nested = self._features(item.value, scope, local, depth + 1)
                if nested is None:
                    return None
                features += nested
                continue
            if isinstance(item, ast.Name):
                found = self._lookup(item.id, scope)
                item, scope_item = found if found else (None, scope)
            else:
                scope_item = scope
            if not isinstance(item, ast.Call) or _call_name(item) != "Feature":
                return None
            given = dict(zip(("name", "rejects", "codes", "apply", "exclusive", "requires", "conflicts"), item.args))
            given.update({k.arg: k.value for k in item.keywords if k.arg})
            name = self.value(given["name"], scope_item, local) if "name" in given else _UNKNOWN
            rejects = self.value(given["rejects"], scope_item, local) if "rejects" in given else _UNKNOWN
            codes = given.get("codes")
            if codes is not None and not isinstance(codes, (ast.Tuple, ast.List)):
                return None
            options = {}
            for key, default in (("exclusive", False), ("requires", ()), ("conflicts", ())):
                options[key] = self.value(given[key], scope_item, local) if key in given else default
            if (not isinstance(name, str) or not isinstance(rejects, bool) or not isinstance(options["exclusive"], bool)
                    or not all(isinstance(options[key], tuple) and all(isinstance(v, str) for v in options[key])
                               for key in ("requires", "conflicts"))):
                return None
            placeholders = tuple(f"\0{name}:{index}" for index in range(len(codes.elts))) if codes is not None else ()
            try:
                features.append(Feature(name, rejects, placeholders, None, **options))
            except ValueError:
                return None
        return features

    def kit_names(self, call, scope, local=None):
        """(rules, known-bad, cases) of feature_explorer/feature_variants(F, ...), or None."""
        if not call.args:
            return None
        features = self._features(call.args[0], scope, local)
        if not features:
            return None
        options = {}
        for keyword in call.keywords:
            if keyword.arg not in {"max_features", "codes"}:
                return None
            options[keyword.arg] = self.value(keyword.value, scope, local)
        if len(call.args) > 1 or any(value is _UNKNOWN for value in options.values()):
            return None
        try:
            rules, bad = feature_model_names(features, **options)
        except (ValueError, TypeError):
            return None
        cases = (tuple(f.name for f in features if f.rejects), tuple(f.name for f in features if not f.rejects))
        return rules, bad, cases

    def _explorer_calls(self, function, scope, depth=0):
        """Explorer(...) calls returned by this function, following one same-file call."""
        calls = []
        local = _locals(function)
        for value in _returns(function):
            if isinstance(value, ast.Name) and value.id in local:
                value = local[value.id]
            if not isinstance(value, ast.Call):
                return None
            name = _call_name(value)
            if name in {"Explorer", "feature_explorer"}:
                calls.append((value, scope, local))
            elif depth == 0 and isinstance(value.func, ast.Name) and value.func.id in scope.functions:
                inner = self._explorer_calls(scope.functions[value.func.id], scope, 1)
                if inner is None:
                    return None
                calls += inner
            else:
                return None
        return calls or None

    def explorer_rules(self):
        build = self.main.functions.get("build_explorer")
        calls = self._explorer_calls(build, self.main) if build else None
        if not calls:
            return None
        found = []
        for call, scope, local in calls:
            if _call_name(call) == "feature_explorer":
                kit = self.kit_names(call, scope, local)
                if kit is None:
                    return None
                self.cases = kit[2]
                found.append(tuple(kit[0]))
                continue
            given = next((k.value for k in call.keywords if k.arg == "invariants"), None)
            if given is None and len(call.args) > 3:
                given = call.args[3]
            rules = [] if given is None else self.rules(given, scope, local)
            if rules is None:
                return None
            found.append(tuple(dict.fromkeys(rules)))
        return found[0] if all(item == found[0] for item in found) else None

    # -- known-bad ----------------------------------------------------------------------------
    def _bind(self, target, item, env):
        if isinstance(target, ast.Name):
            env[target.id] = item
            return True
        if isinstance(target, (ast.Tuple, ast.List)) and isinstance(item, tuple) and len(item) == len(target.elts):
            return all(self._bind(sub, value, env) for sub, value in zip(target.elts, item))
        return False

    def _iterate(self, expr, scope, local, env=None):
        items = self.value(expr, scope, local, env)
        if isinstance(items, dict):
            items = tuple(items)
        return items if isinstance(items, tuple) else None

    def _key(self, expr, scope, local, env):
        key = self.value(expr, scope, local, env)
        return key if isinstance(key, str) else None

    def _loop_keys(self, target, iterable, body, name, scope, local):
        """Keys written as ``name[key] = ...`` by one non-nested for loop."""
        items = self._iterate(iterable, scope, local)
        if items is None:
            return None
        keys = []
        for item in items:
            env = {}
            if not self._bind(target, item, env):
                return None
            for statement in body:
                if (isinstance(statement, ast.Assign) and len(statement.targets) == 1
                        and isinstance(statement.targets[0], ast.Subscript)
                        and isinstance(statement.targets[0].value, ast.Name) and statement.targets[0].value.id == name):
                    key = self._key(statement.targets[0].slice, scope, local, env)
                    if key is None:
                        return None
                    keys.append(key)
                elif _writes_to(statement, name):
                    return None
        return keys

    def bad_keys(self, expr, scope, function=None, depth=0):
        local = _locals(function) if function is not None else {}
        if depth > 20:
            return None
        if isinstance(expr, ast.Dict):
            keys = []
            for key, value in zip(expr.keys, expr.values):
                if key is None:
                    nested = self.bad_keys(value, scope, function, depth + 1)
                    if nested is None:
                        return None
                    keys += nested
                else:
                    key = self._key(key, scope, local, {})
                    if key is None:
                        return None
                    keys.append(key)
            return keys
        if isinstance(expr, ast.DictComp):
            if len(expr.generators) != 1 or expr.generators[0].ifs or expr.generators[0].is_async:
                return None
            generator = expr.generators[0]
            items = self._iterate(generator.iter, scope, local)
            if items is None:
                return None
            keys = []
            for item in items:
                env = {}
                key = self._key(expr.key, scope, local, env) if self._bind(generator.target, item, env) else None
                if key is None:
                    return None
                keys.append(key)
            return keys
        if isinstance(expr, ast.Name):
            if expr.id in local and function is not None:
                keys = self.bad_keys(local[expr.id], scope, function, depth + 1)
                if keys is None:
                    return None
                for statement in function.body:
                    if isinstance(statement, ast.For):
                        if any(_writes_to(item, expr.id) for item in statement.body):
                            more = self._loop_keys(statement.target, statement.iter, statement.body, expr.id, scope, local)
                            if more is None:
                                return None
                            keys += more
                    elif (isinstance(statement, ast.Assign) and len(statement.targets) == 1
                          and isinstance(statement.targets[0], ast.Subscript)
                          and isinstance(statement.targets[0].value, ast.Name) and statement.targets[0].value.id == expr.id):
                        key = self._key(statement.targets[0].slice, scope, local, {})
                        if key is None:
                            return None
                        keys.append(key)
                    elif not isinstance(statement, (ast.Assign, ast.Return)) and _writes_to(statement, expr.id):
                        return None
                return keys
            found = self._lookup(expr.id, scope)
            return self.bad_keys(found[0], found[1], None, depth + 1) if found else None
        if isinstance(expr, ast.Call) and _call_name(expr) == "feature_variants":
            kit = self.kit_names(expr, scope, local)
            return list(kit[1]) if kit else None
        return None

    def known_bad(self):
        hook = self.main.functions.get("broken_variants")
        returns = _returns(hook) if hook else []
        if not returns:
            return None
        keys = []
        for value in returns:
            found = self.bad_keys(value, self.main, hook)
            if found is None:
                return None
            keys += found
        return tuple(sorted(set(keys)))


def _writes_to(statement, name) -> bool:
    """Whether a statement stores into ``name[...]`` or calls a mutating method on it."""
    for node in ast.walk(statement):
        if (isinstance(node, ast.Subscript) and isinstance(node.ctx, (ast.Store, ast.Del))
                and isinstance(node.value, ast.Name) and node.value.id == name):
            return True
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name)
                and node.func.value.id == name and node.func.attr in {"update", "setdefault", "pop", "popitem", "clear"}):
            return True
    return False


def _file_rules(syntax) -> list[str]:
    """Every literal rule name anywhere in the file: an approximation used only as a fallback."""
    names = set()
    for call in ast.walk(syntax):
        if not isinstance(call, ast.Call):
            continue
        name = _call_name(call)
        value = call.args[0] if call.args else None
        if name == "Invariant" and value is None:
            value = next((k.value for k in call.keywords if k.arg == "name"), None)
        if name in BUILTIN_RULE_HELPERS | {"Invariant"} and isinstance(value, ast.Constant) and isinstance(value.value, str):
            names.add(value.value)
    return sorted(names)


def model_facets(root: Path, node, *, view=None) -> Facets:
    contract = node.contract
    try:
        path = resolve_model_path(root, node.path, view=view)
        if path is None:
            raise FileNotFoundError(node.path)
        syntax = ast.parse(read_source(path))
    except (OSError, SyntaxError):
        syntax = ast.Module(body=[], type_ignores=[])
    doc = ast.get_docstring(syntax)
    purpose = doc.strip().splitlines()[0] if doc and doc.strip() else "(no purpose line: add a module docstring)"
    static = _StaticModel(root, node.path, syntax, view=view)
    found = static.explorer_rules()
    if found is not None:
        source, notes = "explorer", dict(sorted(found))
    else:
        notes = dict.fromkeys(_file_rules(syntax), "")
        source = "file" if notes else "runtime"
    rules = set(notes)
    known = static.known_bad()
    literal_bad = known is not None
    bad = known if literal_bad else ()
    code = [f"{block} -> {anchor}" for block, anchor in sorted(contract.get("IMPLEMENTED_BY", {}).items())]
    if contract.get("NOT_MODELED"):
        code.append(f"not modeled: {len(contract['NOT_MODELED'])}")
    tests = [f"{rule} -> {anchor}" + (" (not nested)" if anchor.split(":", 1)[0] in node.nonnested_tests else "")
             for rule, anchors in sorted(contract.get("TESTED_BY", {}).items()) for anchor in anchors]
    untested = sorted(rule for rule in rules if not contract.get("TESTED_BY", {}).get(rule))
    if untested:
        tests.append("untested: " + ", ".join(untested))
    names = tuple(sorted(rules))
    return Facets(purpose, names, source, bad, "literal" if literal_bad else "runtime",
                  tuple(code), tuple(tests), len(rules) if source != "runtime" else None,
                  sum(len(anchors) for anchors in contract.get("TESTED_BY", {}).values()),
                  tuple(notes[name] for name in names), node.id, static.cases if source == "explorer" else None)


def _test_source(root, path, source_cache=None):
    if source_cache is None:
        return read_source(root / path)
    if path not in source_cache:
        source_cache[path] = read_source(root / path)
    return source_cache[path]


def coverage_facts(root, data, inv, tree, raw, *, source_cache=None):
    """Static explanation counts, scoped to each real component and its subtree."""
    excluded = {anchor for node in tree.nodes.values() for anchor in node.contract.get("NOT_MODELED", {})}
    cache = source_cache if source_cache is not None else {}
    out = {}
    for component in data["components"]:
        cid = component["id"]
        scoped = component_scope(data, component)
        covered = {anchor for node in tree.models_for_component(cid)
                   for anchor in node.contract.get("IMPLEMENTED_BY", {}).values()}
        sources = []
        for path in inv.tests:
            if matches_any(path, scoped.get("tests", [])):
                try:
                    sources.append(_test_source(root, path, cache))
                except OSError:
                    continue
        tests = "\n".join(sources)
        entries = set(scoped.get("entrypoints", []))
        writers = {f"{path}:{symbol}" for path in component_files(scoped, inv)
                   for symbol, facts in raw["files"].get(path, {}).get("functions", {}).items()
                   if facts.get("writes") and symbol.rsplit(".", 1)[-1] != "__init__"}
        explained_entries = {anchor for anchor in entries if explained_by(anchor, covered, excluded, tests=tests)}
        explained_writers = {anchor for anchor in writers if explained_by(anchor, covered, excluded, tests=tests)}
        out[cid] = {"entrypoints": (len(explained_entries), len(entries)),
                    "state_writers": (len(explained_writers), len(writers)),
                    "unexplained": tuple(sorted((entries - explained_entries) | (writers - explained_writers)))}
        if len(component_subtree(data, cid)) > 1:
            own_entries = set(component.get("entrypoints", []))
            own_files = set(component_files(component, inv))
            own_writers = {anchor for anchor in writers if anchor.partition(":")[0] in own_files}
            out[cid]["_direct"] = {"entrypoints": (len(own_entries & explained_entries), len(own_entries)),
                                   "state_writers": (len(own_writers & explained_writers), len(own_writers))}
    return out


def coverage_line(coverage, *, summary=False):
    records = [record.get("_direct", record) for record in coverage.values()] if summary else [coverage]
    entries = tuple(sum(record["entrypoints"][i] for record in records) for i in (0, 1))
    writers = tuple(sum(record["state_writers"][i] for record in records) for i in (0, 1))
    line = (f"coverage: entrypoints {entries[0]}/{entries[1]}, "
            f"state writers {writers[0]}/{writers[1]} explained")
    if summary:
        return line + " by a model, a test or NOT_MODELED"
    missing = coverage["unexplained"]
    if missing:
        line += "; unexplained: " + ", ".join(missing[:5])
        if len(missing) > 5:
            line += f" (+{len(missing) - 5} more)"
    return line


def _test_function_index(root: Path, inv: Inventory, *, source_cache=None) -> dict[str, set[str]]:
    """One view-local index: inventory symbols alone also include variables and classes."""
    found = {}
    for path in inv.tests:
        if not path.endswith(".py"):
            continue
        try:
            syntax = ast.parse(_test_source(root, path, source_cache))
        except (OSError, SyntaxError):
            continue
        names, pending = set(), list(syntax.body)
        while pending:
            node = pending.pop()
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("test"):
                    names.add(node.name)
            elif isinstance(node, ast.ClassDef):
                names.update(f"{node.name}.{method.name}" for method in node.body
                             if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)) and method.name.startswith("test"))
            elif isinstance(node, (ast.If, ast.Try, ast.With)):
                pending.extend(node.body + getattr(node, "orelse", []) + getattr(node, "finalbody", []))
                for handler in getattr(node, "handlers", []):
                    pending.extend(handler.body)
        found[path] = names
    return found


def _test_facts(paths, nodes, functions):
    actual = {(path, name) for path in paths for name in functions.get(path, ())}
    bound = set()
    for node in nodes:
        for anchors in node.contract.get("TESTED_BY", {}).values():
            for anchor in anchors:
                try:
                    path, name, _ = parse_test_anchor(anchor)
                except ValueError:
                    continue
                matches = {(p, s) for p, s in actual if p == path and s == name}
                if not matches:
                    matches = {(p, s) for p, s in actual if p == path and s.endswith("." + name)}
                if len(matches) == 1:
                    bound.update(matches)
    unbound = sorted(f"{path}:{name}" for path, name in actual - bound)
    facts = [f"{len(paths)} files: " + (", ".join(sorted(paths)) or "-"), f"{len(actual)} functions, {len(bound)} bound"]
    if unbound:
        facts.append("unbound: " + ", ".join(unbound[:5]) + (f" +{len(unbound) - 5} more" if len(unbound) > 5 else ""))
    return tuple(facts), len(actual)


def component_facets(root: Path, data: dict, inv: Inventory, component: dict, tree, graph, functions, *, coverage=None) -> Facets:
    cid = component["id"]
    members = component_subtree(data, cid)
    responsibilities = tuple(rule for member in members for rule in member.get("responsibilities", []))
    scoped = component_scope(data, component)
    files = component_files(scoped, inv)
    code = [f"{len(files)} files/{sum(inv.loc.get(path, 0) for path in files)} loc"]
    if scoped.get("files"):
        code.append("files: " + ", ".join(scoped["files"]))
    for key, label in (("entrypoints", "entry"), ("state", "state"), ("side_effects", "effects")):
        if scoped.get(key):
            code.append(label + ": " + "; ".join(scoped[key]))
    if coverage is not None:
        code.append(coverage_line(coverage))
    if is_stale(root, component, inv):
        code.append("STALE")
    paths = {path for path in inv.tests if matches_any(path, scoped.get("tests", []))}
    tests, count = _test_facts(paths, tree.models_for_component(cid), functions)
    rules = responsibilities + (
        f"layer {component.get('layer') or '-'} may use: " + (", ".join(scoped.get("depends_on", [])) or "-"),)
    return Facets(component.get("summary") or "(no summary yet)", rules, "map",
                  tuple(dict.fromkeys(name for member in members for name, _, _ in _variants(data, graph, only=member["id"]))), "system", tuple(code), tests,
                  len(responsibilities), count)


def system_facets(data: dict, inv: Inventory, tree, graph, functions, *, coverage=None) -> Facets:
    tests, count = _test_facts(set(inv.tests), tree.nodes.values(), functions)
    return Facets(f"{data.get('project', '')}: {len(data['components'])} components",
                  ("layers order: " + (" > ".join(data.get("layers", [])) or "none"),
                   "no unaccepted dependency cycle", "one owner per responsibility"), "map",
                  tuple(name for name, _, _ in _variants(data, graph)), "system-root",
                  (f"{len(data['components'])} components, {len(inv.source)} source files",)
                  + ((coverage_line(coverage, summary=True),) if coverage is not None else ()), tests, 3, count)
