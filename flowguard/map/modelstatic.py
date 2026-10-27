"""The single static reader for rule contracts, shared by checks and views."""
from __future__ import annotations
import ast
from pathlib import PurePosixPath
from ..kit import Feature,feature_model_names
from .common import read_source
from .mapfile import resolve_model_path, read_model_syntax

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


def call_name(call) -> str:
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


class StaticModel:
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
        self.rule_defs, self.bad_defs = {}, {}    # name -> ast.dump of the expression that defines it

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
        name = call_name(call)
        if name == "Invariant":
            given = dict(zip(("name", "description"), call.args))
            given.update({k.arg: k.value for k in call.keywords if k.arg in {"name", "description"}})
            title = self.value(given["name"], scope, local) if "name" in given else _UNKNOWN
            note = self.value(given["description"], scope, local) if "description" in given else ""
            return self._defined([(title, note if isinstance(note, str) else "")], call, scope) if isinstance(title, str) else None
        if name in BUILTIN_RULE_HELPERS:
            title = self.value(call.args[0], scope, local) if call.args else _UNKNOWN
            return self._defined([(title, "")], call, scope) if isinstance(title, str) else None
        found = self._lookup(name, scope, "functions") if isinstance(call.func, ast.Name) else None
        if not found:
            return None
        function, home = found
        returns = _returns(function)
        if len(returns) == 1 and isinstance(returns[0], (ast.Tuple, ast.List, ast.Name, ast.BinOp)) and not call.args:
            return self.rules(returns[0], home, _locals(function))   # a function that returns the rule list
        if len(returns) != 1 or not isinstance(returns[0], ast.Call) or call_name(returns[0]) != "Invariant":
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
        return self._defined([(title, note if isinstance(note, str) else "")], call, scope) if isinstance(title, str) else None

    def _definition(self, node, scope):
        """Semantic rule inputs: local helpers and constants, never imported product code."""
        dependencies, visited = [], set()
        def lookup(name, home, kind, seen):
            key = (id(home), name, kind)
            if key in seen:
                return None
            seen.add(key)
            table = home.assigns if kind == "assigns" else home.functions
            if name in table:
                return table[name], home
            if name in home.imports:
                module, alias = home.imports[name]
                if module.startswith("_"):
                    inner = self._module(module)
                    return lookup(alias, inner, kind, seen) if inner else None
            for module in home.stars:
                if module.startswith("_"):
                    inner = self._module(module)
                    found = lookup(name, inner, kind, seen) if inner else None
                    if found:
                        return found
            return None
        def names(value, bound=frozenset()):
            if isinstance(value, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                args = value.args
                local = {a.arg for a in args.posonlyargs + args.args + args.kwonlyargs}
                local.update(a.arg for a in (args.vararg, args.kwarg) if a)
                local.update(n.id for n in ast.walk(value) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store))
                bound = bound | local
            if isinstance(value, ast.Name) and isinstance(value.ctx, ast.Load) and value.id not in bound:
                yield value.id
            for child in ast.iter_child_nodes(value):
                yield from names(child, bound)
        def visit(value, home):
            for name in names(value):
                for kind in ("assigns", "functions"):
                    found = lookup(name, home, kind, set())
                    if found is None:
                        continue
                    definition, owner = found
                    key = (id(owner), name, kind)
                    if key not in visited:
                        visited.add(key)
                        dependencies.append((name, kind, ast.dump(definition)))
                        visit(definition, owner)
        visit(node, scope)
        return repr((ast.dump(node), sorted(dependencies)))

    def _defined(self, found, call, scope):
        """Remember the call that defines each rule (goal rules compare these between versions)."""
        for title, _ in found:
            self.rule_defs.setdefault(title, self._definition(call, scope))
        return found

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
            if not isinstance(item, ast.Call) or call_name(item) != "Feature":
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
            # Equal literal codes must stay equal: the kit chooses its reporting
            # witness from code sets, so two defects can share one code. Keep
            # symbolic placeholders only where static evaluation is unavailable.
            values = tuple(self.value(code, scope_item, local) for code in codes.elts) if codes is not None else ()
            placeholders = tuple(value if isinstance(value, str) else f"\0{name}:{index}"
                                 for index, value in enumerate(values))
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
            name = call_name(value)
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
            if call_name(call) == "feature_explorer":
                kit = self.kit_names(call, scope, local)
                if kit is None:
                    return None
                self.cases = kit[2]
                definition = self._definition(call, scope)
                for name, _ in kit[0]:
                    self.rule_defs.setdefault(name, definition)
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
                    self.bad_defs.setdefault(key, ast.dump(value))
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
        if isinstance(expr, ast.Call) and call_name(expr) == "feature_variants":
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


def file_rules(syntax) -> list[str]:
    """Every literal rule name anywhere in the file: an approximation used only as a fallback."""
    names = set()
    for call in ast.walk(syntax):
        if not isinstance(call, ast.Call):
            continue
        name = call_name(call)
        value = call.args[0] if call.args else None
        if name == "Invariant" and value is None:
            value = next((k.value for k in call.keywords if k.arg == "name"), None)
        if name in BUILTIN_RULE_HELPERS | {"Invariant"} and isinstance(value, ast.Constant) and isinstance(value.value, str):
            names.add(value.value)
    return sorted(names)



def rule_count(root, logical, *, view=None):
    path=resolve_model_path(root,logical,view=view)
    if path is None:return None
    try:syntax=read_model_syntax(path,copy_tree=False)
    except (OSError,SyntaxError):return None
    found=StaticModel(root,logical,syntax,view=view).explorer_rules()
    if found is not None:return len({name for name,note in found})
    names=file_rules(syntax)
    return len(names) if names else None


def replay_call_findings(root, data, inv, tree, raw):
    """Find undeclared product replays by following only the model's static protocol."""
    import re
    from pathlib import Path
    from .common import Finding
    from .inventory import resolve_import, syntax_tree
    from .selection import anchor_matches, reachable_functions, select_model_functions
    from .mapfile import model_registry

    api_source = syntax_tree(read_source(Path(__file__).resolve().parents[1] / "__init__.py"))
    api = next(
        ast.literal_eval(node.value)
        for node in api_source.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "_PUBLIC_API"
    )
    public = {name for names in api.values() for name in names}
    modules = {}
    lazy = {info.module: info.lazy_exports for info in inv.py.values() if info.lazy_exports}
    protocol = ("__init__", "reset", "apply_step", "observe_state", "observe_output", "close")

    def module(path):
        if path not in modules:
            try:
                syntax = syntax_tree(read_source(root / path))
            except (OSError, SyntaxError):
                modules[path] = None
                return None
            scope = {"path": path, "syntax": syntax, "names": {}}
            modules[path] = scope
            for node in syntax.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    scope["names"][node.name] = ("local", path, node, None)
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    bind_import(node, scope["names"], path)
                elif isinstance(node, ast.Assign):
                    value = resolve(node.value, scope["names"], path)
                    for target in node.targets:
                        if isinstance(target, ast.Name) and value:
                            scope["names"][target.id] = value
            return scope
        return modules[path]

    def bind_import(node, names, path):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names[alias.asname or alias.name.split(".")[0]] = (
                    "module",
                    alias.name if alias.asname else alias.name.split(".")[0],
                )
            return
        imported = node.module or ""
        if node.level:
            parts = Path(path).parent.parts
            imported = ".".join((*parts[: len(parts) - node.level + 1], *imported.split(".")))
        helper = (Path(path).parent / (imported + ".py")).as_posix()
        local = (
            module(helper)
            if imported.startswith("_") and "/" not in imported and (root / helper).is_file()
            else None
        )
        for alias in node.names:
            if local:
                if alias.name == "*":
                    names.update(local["names"])
                elif alias.name in local["names"]:
                    names[alias.asname or alias.name] = local["names"][alias.name]
            else:
                names[alias.asname or alias.name] = ("import", imported, alias.name)

    def resolve(expr, names, path):
        if isinstance(expr, ast.Name):
            return names.get(expr.id)
        if not isinstance(expr, ast.Attribute):
            return None
        base = resolve(expr.value, names, path)
        if base and base[0] == "module":
            return ("import", base[1], expr.attr)
        if base and base[0] == "import":
            return ("import", base[1] + "." + base[2], expr.attr)
        if base and base[0] == "instance":
            cls = base[2]
            method = next(
                (
                    n
                    for n in cls.body
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and n.name == expr.attr
                ),
                None,
            )
            return (
                ("local", base[1], method, cls)
                if method
                else ("stored", base[3][expr.attr]) if expr.attr in base[3] else None
            )
        return None

    def imported(ref, path):
        if not ref or ref[0] != "import":
            return ref
        home, name = ref[1:]
        helper = (Path(path).parent / (home + ".py")).as_posix()
        if home.startswith("_") and (root / helper).is_file():
            found = module(helper)
            return found["names"].get(name) if found else None
        target = resolve_import(
            home + ":" + name,
            inv.mod_to_path,
            lazy,
            importer=path,
            py_paths=inv.py,
            import_roots=inv.import_roots,
        )
        if target is None or target.startswith(".flowguard/") or inv.is_test(target):
            return None
        if inv.py[target].module == home + "." + name:
            return ("module", home + "." + name)
        syntax = module(target)
        if not syntax:
            return None
        prefix = (
            home[len(inv.py[target].module) + 1 :]
            if home.startswith(inv.py[target].module + ".")
            else ""
        )
        qualname = prefix + "." + name if prefix else name
        parts = qualname.split(".")
        node = syntax["names"].get(parts[0])
        for part in parts[1:]:
            definition = node[2] if node and node[0] == "local" else None
            child = (
                next(
                    (
                        n
                        for n in definition.body
                        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                        and n.name == part
                    ),
                    None,
                )
                if isinstance(definition, ast.ClassDef)
                else None
            )
            node = ("local", target, child, definition) if child else None
        if node and node[0] == "import" and node != ref:
            return imported(node, target)
        if node and node[0] == "local":
            definition = node[2]
            if isinstance(definition, ast.ClassDef):
                if not any(
                    isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "__init__"
                    for n in definition.body
                ):
                    return None
                return ("product", target, qualname + ".__init__", qualname)
            return ("product", target, qualname, qualname)
        return None

    findings = []
    for entry in model_registry(root, data).entries:
        if entry.kind != "contract":
            continue
        scope = module(entry.path)
        hook = scope["names"].get("conformance") if scope else None
        if not hook or hook[0] != "local":
            continue
        literals = {
            n.value
            for n in ast.walk(scope["syntax"])
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
        }
        used, visited = {}, set()
        object_attrs = {}

        def follow(ref, site, names, path, *, called=False):
            while ref and ref[0] == "stored":
                if not called:
                    return
                ref = ref[1]
            ref = imported(ref, path)
            if not ref:
                return
            if ref[0] == "product":
                if ref[2].split(".")[0] not in public:
                    used.setdefault((ref[1], ref[2], ref[3]), set()).add(site)
                return
            if ref[0] != "local" or ref[2] is None:
                return
            _, local_path, definition, cls = ref
            key = (local_path, id(definition))
            if key in visited:
                return
            visited.add(key)
            context = dict(module(local_path)["names"])
            if isinstance(definition, ast.ClassDef):
                attrs = object_attrs.setdefault(id(definition), {})
                instance = ("instance", local_path, definition, attrs)
                for member in definition.body:
                    if (
                        isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and member.name in protocol
                    ):
                        follow(("local", local_path, member, definition), site, context, local_path)
                return
            if cls:
                context["self"] = (
                    "instance",
                    local_path,
                    cls,
                    object_attrs.setdefault(id(cls), {}),
                )
                context["cls"] = context["self"]
            walk(definition.body, context, local_path)

        def expression(node, names, path, *, bare=True):
            if node is None:
                return
            site = path + ":" + str(getattr(node, "lineno", 1))
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute) and isinstance(
                    node.func.value, (ast.Call, ast.Subscript)
                ):
                    expression(node.func.value, names, path)
                elif isinstance(node.func, ast.Subscript):
                    expression(node.func, names, path)
                ref = resolve(node.func, names, path)
                resolved = imported(ref, path)
                follow(ref, site, names, path, called=True)
                outside = bool(ref and ref[0] in ("import", "module") and not resolved)
                for argument in (*node.args, *(keyword.value for keyword in node.keywords)):
                    expression(
                        argument,
                        names,
                        path,
                        bare=not outside or not isinstance(argument, (ast.Name, ast.Attribute)),
                    )
                return
            if isinstance(node, (ast.Name, ast.Attribute)):
                if bare:
                    follow(resolve(node, names, path), site, names, path)
                if isinstance(node, ast.Attribute) and isinstance(
                    node.value, (ast.Call, ast.Subscript)
                ):
                    expression(node.value, names, path, bare=bare)
                return
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                return
            for child in ast.iter_child_nodes(node):
                expression(child, names, path, bare=bare)

        def relevant(test):
            if (
                isinstance(test, ast.Compare)
                and len(test.ops) == 1
                and isinstance(test.ops[0], ast.Eq)
            ):
                values = [
                    node.value
                    for node in (test.left, *test.comparators)
                    if isinstance(node, ast.Constant) and isinstance(node.value, str)
                ]
                return any(value in literals for value in values) if values else None
            return None

        def walk(statements, names, path):
            for statement in statements:
                if isinstance(statement, (ast.Import, ast.ImportFrom)):
                    bind_import(statement, names, path)
                elif isinstance(statement, ast.If):
                    expression(statement.test, names, path)
                    matched = relevant(statement.test)
                    if path == entry.path or matched is not False:
                        walk(statement.body, dict(names), path)
                    if (
                        path == entry.path
                        or matched is None
                        or statement.orelse
                        and isinstance(statement.orelse[0], ast.If)
                    ):
                        walk(statement.orelse, dict(names), path)
                elif isinstance(statement, ast.Match):
                    expression(statement.subject, names, path)
                    for case in statement.cases:
                        constants = {
                            n.value
                            for n in ast.walk(case.pattern)
                            if isinstance(n, ast.Constant) and isinstance(n.value, str)
                        }
                        if path == entry.path or constants & literals:
                            walk(case.body, dict(names), path)
                elif isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    names[statement.name] = ("local", path, statement, None)
                elif isinstance(statement, (ast.Assign, ast.AnnAssign)):
                    value = statement.value
                    ref = resolve(value.func if isinstance(value, ast.Call) else value, names, path)
                    targets = (
                        statement.targets
                        if isinstance(statement, ast.Assign)
                        else [statement.target]
                    )
                    stored = False
                    for target in targets:
                        if (
                            isinstance(target, ast.Attribute)
                            and isinstance(target.value, ast.Name)
                            and target.value.id in ("self", "cls")
                        ):
                            instance = names.get(target.value.id)
                            if instance and ref:
                                instance[3][target.attr] = ref
                                stored = not isinstance(value, ast.Call)
                        elif isinstance(target, ast.Name) and ref:
                            known = imported(ref, path)
                            if (
                                known
                                and known[0] == "local"
                                and isinstance(known[2], ast.ClassDef)
                                and isinstance(value, ast.Call)
                            ):
                                ref = (
                                    "instance",
                                    known[1],
                                    known[2],
                                    object_attrs.setdefault(id(known[2]), {}),
                                )
                            names[target.id] = ref
                    if not stored:
                        expression(value, names, path)
                else:
                    for child in ast.iter_child_nodes(statement):
                        if isinstance(child, ast.stmt):
                            walk([child], names, path)
                        else:
                            expression(child, names, path)

        follow(hook, entry.path + ":" + str(hook[2].lineno), scope["names"], entry.path)
        anchors = [
            *tree.nodes[entry.id].contract.get("IMPLEMENTED_BY", {}).values(),
            *tree.nodes[entry.id].contract.get("USES", {}).values(),
        ]
        coverage = set()
        for anchor in anchors:
            file, _, name = anchor.partition(":")
            starts = [
                file + "#" + function
                for function in raw.get("files", {}).get(file, {}).get("functions", {})
                if anchor_matches(anchor, file + "#" + function)
            ]
            coverage.update(
                start
                for function in starts
                for start in reachable_functions(raw.get("edges", {}), function)
            )
        keys = dict(tree.nodes[entry.id].contract.get("USES", {}))
        for (path, qualname, symbol), sites in sorted(used.items()):
            function = path + "#" + qualname
            if any(anchor_matches(anchor, function) for anchor in anchors) or function in coverage:
                continue
            selected = select_model_functions(data, inv, tree, raw, {function})[0]
            selection = ", ".join(sorted(selected)) or "no model"
            if entry.id in selected:
                selection += " (not through an anchor of " + entry.id + ")"
            key = "".join(
                word[:1].upper() + word[1:]
                for word in re.split(r"[_\W]+", symbol.removesuffix(".__init__").lstrip("_"))
                if word
            )
            if key in keys and keys[key] != path + ":" + symbol:
                key = "".join(word.title() for word in Path(path).stem.split("_")) + key
            keys[key] = path + ":" + symbol
            ordered = sorted(
                sites, key=lambda site: (site.rpartition(":")[0], int(site.rpartition(":")[2]))
            )
            site = ordered[0] + (f"+{len(ordered)-1} more" if len(ordered) > 1 else "")
            message = f'replays {path}:{qualname} at {site}, but no IMPLEMENTED_BY or USES anchor of {entry.id} reaches it, so an edit of it selects {selection}; declare it: USES "{key}": "{path}:{symbol}" (python -m flowguard target add {entry.id})'
            findings.append(Finding("warn", "replay_call_undeclared", entry.id, message))
    return findings
