"""Static diagnostics for undeclared calls made by model replay protocols."""

from __future__ import annotations
import ast
from .common import read_source


def replay_call_findings(root, data, inv, tree, raw):
    """Find undeclared product replays by following only the model's static protocol."""
    import re
    from pathlib import Path
    from .common import Finding
    from .inventory import resolve_import, syntax_tree
    from .selection import anchor_matches, reachable_functions, select_model_functions
    from .mapfile import model_registry

    api_source = syntax_tree(
        read_source(Path(__file__).resolve().parents[1] / "__init__.py")
    )
    api = next(
        ast.literal_eval(node.value)
        for node in api_source.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "_PUBLIC_API"
    )
    public = {name for names in api.values() for name in names}
    modules = {}
    lazy = {
        info.module: info.lazy_exports for info in inv.py.values() if info.lazy_exports
    }
    protocol = (
        "__init__",
        "reset",
        "apply_step",
        "observe_state",
        "observe_output",
        "close",
    )

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
                if isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                ):
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
            info = inv.py.get(path)
            if info is not None:
                package = (
                    info.module
                    if path.endswith("/__init__.py")
                    else info.module.rpartition(".")[0]
                )
                parts = package.split(".") if package else []
                tail = imported.split(".") if imported else []
                imported = ".".join([*parts[: len(parts) - node.level + 1], *tail])
            elif node.level != 1:
                parts = Path(path).parent.parts
                imported = ".".join(
                    (*parts[: len(parts) - node.level + 1], *imported.split("."))
                )
        helper = (Path(path).parent / (imported + ".py")).as_posix()
        local = (
            module(helper)
            if imported.startswith("_")
            and "/" not in imported
            and (root / helper).is_file()
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
                        if isinstance(
                            n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                        )
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
                    isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and n.name == "__init__"
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
                        follow(
                            ("local", local_path, member, definition),
                            site,
                            context,
                            local_path,
                        )
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
                for argument in (
                    *node.args,
                    *(keyword.value for keyword in node.keywords),
                ):
                    expression(
                        argument,
                        names,
                        path,
                        bare=not outside
                        or not isinstance(argument, (ast.Name, ast.Attribute)),
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

        def assignment(target, value, names, path):
            if (
                isinstance(target, (ast.Tuple, ast.List))
                and isinstance(value, (ast.Tuple, ast.List))
                and len(target.elts) == len(value.elts)
                and not any(isinstance(item, ast.Starred) for item in target.elts)
            ):
                for destination, item in zip(target.elts, value.elts):
                    assignment(destination, item, names, path)
                return
            ref = resolve(
                value.func if isinstance(value, ast.Call) else value, names, path
            )
            stored = False
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
                elif isinstance(
                    statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                ):
                    names[statement.name] = ("local", path, statement, None)
                elif isinstance(statement, (ast.Assign, ast.AnnAssign)):
                    targets = (
                        statement.targets
                        if isinstance(statement, ast.Assign)
                        else [statement.target]
                    )
                    for target in targets:
                        assignment(target, statement.value, names, path)
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
            if (
                any(anchor_matches(anchor, function) for anchor in anchors)
                or function in coverage
            ):
                continue
            selected = select_model_functions(data, inv, tree, raw, {function})[0]
            selection = ", ".join(sorted(selected)) or "no model"
            if entry.id in selected:
                selection += " (not through an anchor of " + entry.id + ")"
            key = "".join(
                word[:1].upper() + word[1:]
                for word in re.split(
                    r"[_\W]+", symbol.removesuffix(".__init__").lstrip("_")
                )
                if word
            )
            if key in keys and keys[key] != path + ":" + symbol:
                key = "".join(word.title() for word in Path(path).stem.split("_")) + key
            keys[key] = path + ":" + symbol
            ordered = sorted(
                sites,
                key=lambda site: (
                    site.rpartition(":")[0],
                    int(site.rpartition(":")[2]),
                ),
            )
            site = ordered[0] + (f"+{len(ordered)-1} more" if len(ordered) > 1 else "")
            message = f'replays {path}:{qualname} at {site}, but no IMPLEMENTED_BY or USES anchor of {entry.id} reaches it, so an edit of it selects {selection}; declare it: USES "{key}": "{path}:{symbol}" (python -m flowguard target add {entry.id})'
            findings.append(
                Finding("warn", "replay_call_undeclared", entry.id, message)
            )
    return findings
