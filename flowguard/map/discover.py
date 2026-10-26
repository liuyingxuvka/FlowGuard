"""Reverse-wrap discovery: behavior surfaces of an existing codebase.

Finds what a file/symbol/import scan cannot: entrypoints (HTTP routes with
method+path, CLI commands with names, console scripts, __main__ guards),
side effects by kind (fs write/delete, subprocess, network, db, env, exit,
event emit), instance/module state and its writer functions, raised errors,
dynamic dispatch, and an intra-repo call graph used to say which effect kinds
each entrypoint can reach.

Raw per-file facts go to .flowguard/cache/discover.json keyed by content
digest (incremental, never authority, safe to delete).  Only a bounded
per-component summary is returned for map.json.
"""

from __future__ import annotations

import ast
import json
import sys
from collections import defaultdict
from pathlib import Path

from .inventory import resolve_module
from .common import atomic_write_text, cache_dir, CACHE_RELDIR, content_digest, read_source, sha256_bytes

CACHE_SCHEMA = "flowguard.map.discover_cache.v5"
# Facts are reused only by the exact analysis code that wrote them (upgrades never keep stale facts).
PARSER_ID = sha256_bytes(Path(__file__).read_bytes() + (Path(__file__).parent / "common.py").read_bytes()
                         + sys.version.encode())[:16]   # ast results differ between Python versions
SUMMARY_LIMIT = 12

ROUTE_LEAVES = {"route", "get", "post", "put", "delete", "patch", "head", "options", "websocket", "api_route"}
CLI_LEAVES = {"command", "group"}
HANDLER_LEAVES = {"callback", "handler", "listener", "on", "subscribe", "task", "job", "receiver"}
FS_WRITE = {"write_text", "write_bytes", "mkdir", "makedirs", "touch", "chmod", "symlink_to", "copy", "copy2",
            "copyfile", "copytree", "move", "rename"}
FS_DELETE = {"unlink", "remove", "rmdir", "rmtree", "removedirs"}
FS_RECEIVERS = ("os", "shutil", "path", "Path", "dir", "file", "target", "dest", "tmp", "root", "parent")
SUBPROCESS = {"subprocess.run", "subprocess.call", "subprocess.check_call", "subprocess.check_output",
              "subprocess.Popen", "os.system", "os.popen", "os.execv", "os.execvp", "asyncio.create_subprocess_exec",
              "os.fork", "os.forkpty", "os.spawnv", "os.spawnl", "os.posix_spawn"}
NETWORK_LEAVES = {"get", "post", "put", "patch", "delete", "head", "options", "request", "send", "urlopen",
                  "connect", "create_connection", "sendall", "sendmail", "send_message", "stream"}
NETWORK_PREFIXES = ("requests.", "httpx.", "urllib.request.", "aiohttp.", "socket.", "http.client.", "smtplib.",
                    "boto3.", "urlopen")
DB_LEAVES = {"execute", "executemany", "executescript", "commit", "rollback", "bulk_save_objects", "add_all"}
EMIT_LEAVES = {"send", "emit", "publish", "dispatch", "notify", "enqueue", "put_nowait"}
EXIT_CALLS = {"sys.exit", "os._exit", "exit", "quit", "abort"}
DYNAMIC = {"eval", "exec", "getattr", "setattr", "__import__", "importlib.import_module", "import_module",
           "entry_points", "load_entry_point"}


def _name(node: ast.AST | None) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Call):
        return _name(node.func)
    if isinstance(node, ast.Subscript):
        return _name(node.value)
    return ""


def _str_arg(call: ast.Call, index: int = 0, keyword: str = "") -> str:
    if len(call.args) > index and isinstance(call.args[index], ast.Constant) and isinstance(call.args[index].value, str):
        return call.args[index].value
    for kw in call.keywords:
        if kw.arg == keyword and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
            return kw.value.value
    return ""


def _literal_strings(node: ast.AST | None) -> list[str]:
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return [e.value for e in node.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
    return []


NETWORK_ROOTS = {"requests", "httpx", "urllib", "aiohttp", "socket", "http", "smtplib", "boto3"}


def _imported_root(name: str, imports: dict[str, str]) -> str:
    """Top-level module behind the first name segment, or '' when the name is not an import."""
    bound = imports.get(name.split(".", 1)[0], "")
    return bound.split(":", 1)[0].split(".", 1)[0] if bound else ""


def _effect_kind(call: ast.Call, name: str, imports: dict[str, str] | None = None, receiver_ctor: str = "") -> str:
    leaf = name.rsplit(".", 1)[-1]
    receiver = name.rsplit(".", 1)[0] if "." in name else ""
    if receiver.startswith(("os.environ", "sys.path")) and name not in {"os.environ.setdefault", "os.environ.update", "os.environ.pop"}:
        return ""
    bound = (imports or {}).get(name.split(".", 1)[0], "")
    canonical = bound.replace(":", ".") + name[len(name.split(".", 1)[0]):] if bound else name
    if canonical in SUBPROCESS:
        return "subprocess"
    if receiver_ctor and leaf in NETWORK_LEAVES:
        return "network"
    if name == "open" or leaf == "open" and receiver.endswith(("path", "Path", "io")):
        mode = _str_arg(call, 1, "mode")
        return "fs_write" if any(c in mode for c in "wax+") else ""
    if canonical.startswith(NETWORK_PREFIXES) and leaf in NETWORK_LEAVES and (imports is None or _imported_root(name, imports) in NETWORK_ROOTS):
        return "network"
    if name in EXIT_CALLS:
        return "exit"
    if leaf in FS_DELETE and (receiver.split(".")[0] in {"os", "shutil"} or receiver.endswith(FS_RECEIVERS)):
        return "fs_delete"
    if leaf in FS_WRITE and (receiver.split(".")[0] in {"os", "shutil"} or receiver.endswith(FS_RECEIVERS)
                             or leaf in {"write_text", "write_bytes", "makedirs"}):
        return "fs_write"
    if leaf == "replace" and receiver in {"os", "Path"}:
        return "fs_write"
    if leaf in DB_LEAVES and receiver.split(".")[-1] in {"cursor", "cur", "conn", "connection", "db", "session", "engine"}:
        return "db"
    if name in {"os.putenv", "os.environ.setdefault", "os.environ.update", "os.environ.pop"}:
        return "env_write"
    if leaf in EMIT_LEAVES and receiver and not receiver.startswith("self.") and receiver.split(".")[-1] not in {"self"}:
        return "emit"
    return ""


class _FileVisitor(ast.NodeVisitor):
    def __init__(self, module: str, package: str) -> None:
        self.module, self.package = module, package
        self.scope: list[str] = []
        self.classes: list[str] = []
        self.functions: dict[str, dict] = {}
        self.imports: dict[str, str] = {}          # bound name -> "module" or "module:symbol"
        self.entrypoints: list[dict] = []
        self.state: dict[str, set[str]] = defaultdict(set)
        self.main_calls: list[str] = []
        self.instances: dict[str, str] = {}       # "scope|var" -> constructor call name ("Cls" / "mod.Cls")
        self.injected: dict[str, str] = {}        # "Cls|self.attr" -> the __init__ parameter assigned to it
        self.annotations: dict[str, str] = {}     # "Cls|self.attr" -> class-body annotation name

    # ---- scope bookkeeping -------------------------------------------------
    def _symbol(self) -> str:
        return ".".join(self.scope) or "<module>"

    def _fn(self) -> dict | None:
        return self.functions.get(self._symbol()) if self.scope else None

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.scope.append(node.name)
        self.classes.append(".".join(self.scope))
        self.generic_visit(node)
        self.scope.pop()

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self.scope.append(node.name)
        symbol = self._symbol()
        owner_class = ".".join(self.scope[:-1]) if ".".join(self.scope[:-1]) in self.classes else ""
        self.functions[symbol] = {"line": node.lineno, "class": owner_class, "calls": set(), "effects": [],
                                  "raises": set(), "dynamic": set(), "writes": set(), "locals": set(), "local_imports": {},
                                  "deep_writes": set(), "direct_writes": set(), "attr_writes": [], "ctor_calls": []}
        if owner_class and node.name == "__init__":
            arguments = [*node.args.posonlyargs, *node.args.args][1:] + list(node.args.kwonlyargs)
            self.functions[symbol]["params"] = [argument.arg for argument in arguments]
            self.functions[symbol]["annotations"] = {
                argument.arg: name for argument in arguments if (name := _annotation_class(argument.annotation))}
        for deco in node.decorator_list:
            self._decorator_entrypoint(deco, symbol, node)
        for stmt in node.body:
            self.visit(stmt)
        self.scope.pop()

    visit_FunctionDef = visit_AsyncFunctionDef = _visit_function

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        cls = ".".join(self.scope)
        if cls in self.classes and isinstance(node.target, ast.Name):      # class-body attribute annotation
            if (name := _annotation_class(node.annotation)):
                self.annotations[f"{cls}|self.{node.target.id}"] = name
        fn = self._fn()
        if (fn is not None and fn["class"] and isinstance(node.target, ast.Attribute)
                and isinstance(node.target.value, ast.Name) and node.target.value.id == "self"
                and (name := _annotation_class(node.annotation))):
            self.annotations[f"{fn['class']}|self.{node.target.attr}"] = name
        if (node.value is not None and fn is not None and fn["class"] and self._symbol() == f"{fn['class']}.__init__"
                and isinstance(node.target, ast.Attribute)):
            self.visit_Assign(ast.Assign(targets=[node.target], value=node.value, lineno=node.lineno,
                                         col_offset=node.col_offset))
        else:
            self.generic_visit(node)

    # ---- entrypoints -------------------------------------------------------
    def _decorator_entrypoint(self, deco: ast.AST, symbol: str, fn: ast.AST) -> None:
        name = _name(deco)
        leaf = name.rsplit(".", 1)[-1]
        call = deco if isinstance(deco, ast.Call) else None
        if leaf in ROUTE_LEAVES and call is not None and _str_arg(call).startswith("/"):
            methods = _literal_strings(next((k.value for k in call.keywords if k.arg == "methods"), None))
            if not methods:
                methods = ["GET"] if leaf == "route" else [leaf.upper()]
            self.entrypoints.append({"kind": "http_route", "name": f"{','.join(methods)} {_str_arg(call)}",
                                     "symbol": symbol, "line": fn.lineno, "via": name})
        elif leaf in CLI_LEAVES and "." in name:
            cli_name = (_str_arg(call, 0, "name") if call is not None else "") or symbol.rsplit(".", 1)[-1].replace("_", "-")
            self.entrypoints.append({"kind": "cli_command", "name": cli_name, "symbol": symbol, "line": fn.lineno, "via": name})
        elif leaf in HANDLER_LEAVES and "." in name:
            self.entrypoints.append({"kind": "handler", "name": name, "symbol": symbol, "line": fn.lineno, "via": name})

    def visit_If(self, node: ast.If) -> None:
        test = node.test
        if (isinstance(test, ast.Compare) and isinstance(test.left, ast.Name) and test.left.id == "__name__"
                and any(isinstance(c, ast.Constant) and c.value == "__main__" for c in test.comparators)):
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call):
                    self.main_calls.append(_name(sub.func))
            self.entrypoints.append({"kind": "main_guard", "name": "__main__", "symbol": "<module>", "line": node.lineno, "via": ""})
        self.generic_visit(node)

    # ---- imports -----------------------------------------------------------
    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            bindings = self._fn()["local_imports"] if self._fn() is not None else self.imports
            bindings[alias.asname or alias.name.split(".")[0]] = alias.name if alias.asname else alias.name.split(".")[0]

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.level:
            parts = self.package.split(".") if self.package else []
            parts = parts[: len(parts) - (node.level - 1)] if node.level > 1 else parts
            base = ".".join(p for p in [*parts, node.module or ""] if p)
        else:
            base = node.module or ""
        for alias in node.names:
            if alias.name != "*":
                bindings = self._fn()["local_imports"] if self._fn() is not None else self.imports
                bindings[alias.asname or alias.name] = f"{base}:{alias.name}"

    # ---- facts -------------------------------------------------------------
    def visit_Call(self, node: ast.Call) -> None:
        name = _name(node.func)
        fn = self._fn()
        leaf = name.rsplit(".", 1)[-1]
        if leaf == "add_parser" and _str_arg(node):
            self.entrypoints.append({"kind": "cli_command", "name": _str_arg(node), "symbol": self._symbol(),
                                     "line": node.lineno, "via": "argparse"})
        if leaf == "add_url_rule" and _str_arg(node).startswith("/"):
            self.entrypoints.append({"kind": "http_route", "name": _str_arg(node), "symbol": self._symbol(),
                                     "line": node.lineno, "via": name})
        if (leaf in {"path", "re_path"} and len(node.args) >= 2 and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str) and not self.scope):
            self.entrypoints.append({"kind": "http_route", "name": "/" + _str_arg(node).lstrip("/"),
                                     "symbol": _name(node.args[1]) or "<view>", "line": node.lineno, "via": name})
        if fn is not None and name and leaf[:1].isupper():
            arguments = [[index, self._argument_class(arg)] for index, arg in enumerate(node.args)]
            arguments += [[keyword.arg, self._argument_class(keyword.value)] for keyword in node.keywords if keyword.arg]
            if arguments:
                fn["ctor_calls"].append([name, arguments])
        if fn is not None and name:
            parts = name.split(".")
            if len(parts) == 4 and parts[0] == "self" and parts[3] in MUTATORS and fn["class"]:
                fn["attr_writes"].append([parts[1], parts[2], node.lineno])
            fn["calls"].add(name)
            # Named function arguments are conservative may-call edges; unresolved values stay outside the graph.
            fn["calls"].update(_name(arg) for arg in [*node.args, *(kw.value for kw in node.keywords)]
                               if isinstance(arg, (ast.Name, ast.Attribute)))
            root_name = name.split(".", 1)[0]
            imports = {**self.imports, **fn["local_imports"]} if root_name not in fn["locals"] else {}
            ctor = self.instances.get(f"{self._symbol()}|{root_name}", "") or self.instances.get(f"|{root_name}", "")
            ctor = ctor if _imported_root(ctor, {**self.imports, **fn["local_imports"]}) in NETWORK_ROOTS else ""
            kind = _effect_kind(node, name, imports, ctor)
            if kind:
                fn["effects"].append([kind, name, node.lineno])
            if name in DYNAMIC or leaf in {"import_module", "entry_points"}:
                fn["dynamic"].add(name)
        self.generic_visit(node)

    def _argument_class(self, value: ast.AST) -> str:
        """The class a constructor argument visibly carries: Other(...) or a local x = Other(...)."""
        if isinstance(value, ast.Call):
            ctor = _name(value.func)
            return ctor if ctor.rsplit(".", 1)[-1][:1].isupper() else ""
        if isinstance(value, ast.Name):
            return self.instances.get(f"{self._symbol()}|{value.id}", "")
        return ""

    def _write_target(self, target: ast.AST) -> None:
        fn = self._fn()
        if fn is None:
            return
        if isinstance(target, (ast.Tuple, ast.List)):
            for elt in target.elts:
                self._write_target(elt)
            return
        base = target
        while isinstance(base, ast.Subscript):
            base = base.value
        name = _name(base)
        if name.startswith("self.") and fn["class"]:
            attr = f"{fn['class']}.{name[5:].split('.')[0]}"
            self.state[attr].add(self._symbol())
            fn["writes"].add(attr)
            parts = name.split(".")
            if len(parts) >= 3:          # self.attr.field = ...: a write into the object held by attr
                fn["deep_writes"].add(attr)
                fn["attr_writes"].append([parts[1], parts[2], getattr(target, "lineno", 0)])
            else:
                fn["direct_writes"].add(attr)
        elif name == "os.environ":
            fn["effects"].append(["env_write", "os.environ[...]", getattr(target, "lineno", 0)])
        elif isinstance(target, ast.Subscript) and name and name.split(".")[0] not in fn["locals"]:
            bound = {**self.imports, **fn["local_imports"]}.get(name.split(".")[0], "")
            if ":" in bound and "." not in name:
                fn["writes"].add(f"<import>.{bound}")

    def visit_Assign(self, node: ast.Assign) -> None:
        fn = self._fn()
        if fn is not None:
            fn["locals"].update(t.id for t in node.targets if isinstance(t, ast.Name))
        for target in node.targets:
            self._write_target(target)
            ctor = _name(node.value.func) if isinstance(node.value, ast.Call) else ""
            if isinstance(target, ast.Name) and ctor and ctor.rsplit(".", 1)[-1][:1].isupper():
                self.instances[f"{self._symbol() if self.scope else ''}|{target.id}"] = ctor
            if (fn is not None and fn["class"] and self._symbol() == f"{fn['class']}.__init__"
                    and isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name)
                    and target.value.id == "self"):
                value = node.value
                if (isinstance(value, ast.BoolOp) and isinstance(value.op, ast.Or) and len(value.values) == 2
                        and isinstance(value.values[0], ast.Name)):
                    value = value.values[1]
                assigned = _name(value.func) if isinstance(value, ast.Call) else ""
                key = f"{fn['class']}|self.{target.attr}"
                if isinstance(node.value, ast.Name) and node.value.id in fn.get("params", ()):
                    # Constructor injection: the class comes from an annotation or from the call sites.
                    self.injected[key] = node.value.id
                    assigned = fn["annotations"].get(node.value.id, "")
                previous = self.instances.get(key, assigned)
                self.instances[key] = assigned if assigned and previous == assigned else "<unresolved>"
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self._write_target(node.target)
        self.generic_visit(node)

    def visit_Delete(self, node: ast.Delete) -> None:
        for target in node.targets:
            self._write_target(target)
        self.generic_visit(node)

    def visit_Global(self, node: ast.Global) -> None:
        fn = self._fn()
        if fn is not None:
            for name in node.names:
                self.state[f"<module>.{name}"].add(self._symbol())
                fn["writes"].add(f"<module>.{name}")

    def visit_Raise(self, node: ast.Raise) -> None:
        fn = self._fn()
        if fn is not None and node.exc is not None:
            fn["raises"].add(_name(node.exc))
        self.generic_visit(node)


MUTATORS = {"append", "extend", "insert", "pop", "remove", "clear", "update", "add", "discard", "setdefault"}


def _annotation_class(annotation) -> str:
    """``Cls``, ``"Cls"``, ``mod.Cls``, ``Optional[Cls]`` or ``Cls | None`` -> the class name."""
    if annotation is None:
        return ""
    if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
        try:
            annotation = ast.parse(annotation.value, mode="eval").body
        except SyntaxError:
            return ""
    if isinstance(annotation, ast.Subscript) and _name(annotation.value).rsplit(".", 1)[-1] == "Optional":
        return _annotation_class(annotation.slice)
    if isinstance(annotation, ast.BinOp) and isinstance(annotation.op, ast.BitOr):
        sides = [side for side in (annotation.left, annotation.right)
                 if not (isinstance(side, ast.Constant) and side.value is None)]
        return _annotation_class(sides[0]) if len(sides) == 1 else ""
    name = _name(annotation) if isinstance(annotation, (ast.Name, ast.Attribute)) else ""
    return name if name.rsplit(".", 1)[-1][:1].isupper() else ""


def _mutating_method_writes(visitor: _FileVisitor) -> None:
    """self.items.append(x) mutates state just like self.items = ..."""
    for symbol, fn in visitor.functions.items():
        if not fn["class"]:
            continue
        for call in fn["calls"]:
            parts = call.split(".")
            if len(parts) == 3 and parts[0] == "self" and parts[2] in MUTATORS:
                attr = f"{fn['class']}.{parts[1]}"
                visitor.state[attr].add(symbol)
                fn["writes"].add(attr)
                fn["deep_writes"].add(attr)


def file_facts(text: str, module: str, package: str, path: str) -> dict:
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return {"parse_error": f"{exc.msg} line {exc.lineno}"}
    visitor = _FileVisitor(module, package)
    visitor.visit(tree)
    _mutating_method_writes(visitor)
    for key, param in visitor.injected.items():            # class-body annotations seen after __init__
        if visitor.instances.get(key) == "<unresolved>" and key in visitor.annotations:
            visitor.instances[key] = visitor.annotations[key]
    # Constructor-only initialization is not a changing state lifecycle.
    initialized_only = {attr for attr, writers in visitor.state.items() if all(w.endswith(".__init__") for w in writers)}
    for attr in initialized_only:
        del visitor.state[attr]
    for fn in visitor.functions.values():
        fn["writes"].difference_update(initialized_only)
    for call in visitor.main_calls:
        if call in visitor.functions:
            visitor.entrypoints.append({"kind": "main_call", "name": call, "symbol": call, "line": 0, "via": "__main__"})
    return {
        "module": module,
        "imports": visitor.imports,
        "instances": visitor.instances,
        "injected": visitor.injected,
        "classes": visitor.classes,
        "entrypoints": visitor.entrypoints,
        "state": {k: sorted(v) for k, v in sorted(visitor.state.items())},
        "functions": {s: {"line": f["line"], "class": f["class"], "calls": sorted(f["calls"]),
                          "effects": f["effects"], "raises": sorted(x for x in f["raises"] if x),
                          "dynamic": sorted(f["dynamic"]), "writes": sorted(f["writes"]),
                          "local_imports": dict(sorted(f["local_imports"].items())),
                          "deep_writes": sorted(f["deep_writes"] - f["direct_writes"]),
                          "attr_writes": f["attr_writes"], "ctor_calls": f["ctor_calls"],
                          **({"params": f["params"]} if "params" in f else {})}
                      for s, f in visitor.functions.items()},
    }


def _scope_imports(file, caller):
    """File imports followed by lexical function imports, outermost to innermost."""
    imports = dict(file.get("imports", {}))
    parts = caller.split(".")
    for depth in range(1, len(parts) + 1):
        function = file.get("functions", {}).get(".".join(parts[:depth]))
        if function is not None:
            imports.update(function.get("local_imports", {}))
    return imports


def _resolve(call: str, caller: str, path: str, facts: dict, index: dict[str, dict[str, str]],
             mod_to_path: dict[str, str], *,
             dependency_files: dict[str, set[str]] | None = None, py_paths=(), import_roots=()) -> str | None:
    """Resolve a call to 'path#symbol' inside the repo, or None (external / dynamic)."""
    file = facts[path]
    funcs = file["functions"]
    cls = funcs.get(caller, {}).get("class", "")
    parts = call.split(".")
    imports = _scope_imports(file, caller)
    if parts[0] == "self" and cls and len(parts) == 2:
        return f"{path}#{cls}.{parts[1]}" if f"{cls}.{parts[1]}" in funcs else None
    if len(parts) == 1:
        scopes = [".".join(caller.split(".")[:depth]) for depth in range(len(caller.split(".")), 0, -1)]
        for scope in [*(scope for scope in scopes if scope in funcs), ""]:
            name = f"{scope}.{call}" if scope else call
            if name in funcs:
                return f"{path}#{name}"
        if f"{call}.__init__" in funcs:
            return f"{path}#{call}.__init__"
        if call in file.get("classes", ()):
            return f"{path}#{call}"
        bound = imports.get(call, "")
        if ":" in bound:
            mod, sym = bound.split(":", 1)
            target = resolve_module(mod, path, mod_to_path, py_paths, import_roots)
            if target and sym in index.get(target, {}):
                return f"{target}#{sym}"
            if target and f"{sym}.__init__" in index.get(target, {}):
                return f"{target}#{sym}.__init__"
            if target and sym in facts[target].get("classes", ()):
                return f"{target}#{sym}"
        return None
    if call in funcs:
        return f"{path}#{call}"
    instances = file.get("instances", {})
    ctor = instances.get(f"{caller}|{parts[0]}") or instances.get(f"|{parts[0]}")
    if ctor and len(parts) == 2:
        init = _resolve(ctor, caller, path, facts, index, mod_to_path, py_paths=py_paths, import_roots=import_roots)       # -> path#Cls.__init__ or path#Cls
        cls_path, _, cls_symbol = (init or "").partition("#")
        cls_symbol = cls_symbol.removesuffix(".__init__")
        if cls_path and f"{cls_symbol}.{parts[1]}" in index.get(cls_path, {}):
            return f"{cls_path}#{cls_symbol}.{parts[1]}"
    bound = imports.get(parts[0], "")
    if ":" in bound and len(parts) == 2:
        module, class_name = bound.split(":", 1)
        target = resolve_module(module, path, mod_to_path, py_paths, import_roots)
        method = f"{class_name}.{parts[1]}"
        if target and class_name in facts[target].get("classes", ()) and method in index.get(target, {}):
            return f"{target}#{method}"
    module = bound.replace(":", ".") if bound else ""
    if module:
        for cut in range(len(parts) - 1, 0, -1):
            target = resolve_module(".".join([module, *parts[1:cut]]), path, mod_to_path, py_paths, import_roots)
            if target and ".".join(parts[cut:]) in index.get(target, {}):
                return f"{target}#{'.'.join(parts[cut:])}"
    if parts[0] == "self" and cls and len(parts) == 3:
        ctor = instances.get(f"{cls}|self.{parts[1]}", "")
        if ctor and ctor != "<unresolved>":
            init = _resolve(ctor, f"{cls}.__init__", path, facts, index, mod_to_path, py_paths=py_paths, import_roots=import_roots)
            cls_path, _, cls_symbol = (init or "").partition("#")
            cls_symbol = cls_symbol.removesuffix(".__init__")
            if not cls_path:
                ctor_parts = ctor.split(".")
                ctor_imports = _scope_imports(file, f"{cls}.__init__")
                module = ctor_imports.get(ctor_parts[0], "").replace(":", ".")
                for cut in range(len(ctor_parts) - 1, 0, -1) if module else ():
                    target = resolve_module(".".join([module, *ctor_parts[1:cut]]), path, mod_to_path, py_paths, import_roots)
                    symbol = ".".join(ctor_parts[cut:])
                    if symbol in facts.get(target, {}).get("classes", ()):
                        cls_path, cls_symbol = target, symbol
                        break
            method = f"{cls_symbol}.{parts[2]}"
            if cls_symbol in facts.get(cls_path, {}).get("classes", ()) and method in index.get(cls_path, {}):
                return f"{cls_path}#{method}"
        candidates = {f"{target}#{symbol}"
                      for target in (dependency_files or {}).get(path, ())
                      for symbol, function in index.get(target, {}).items()
                      if function.get("class") and symbol.rsplit(".", 1)[-1] == parts[2]}
        if len(candidates) == 1:
            return next(iter(candidates))
    return None


def discover(root: Path, py_files: dict[str, str], *, write_cache: bool = True,
             dependency_files: dict[str, set[str]] | None = None, import_roots=()) -> dict:
    """py_files: path -> module.  Returns {"files": facts, "edges": ..., "reach": ...} (raw)."""
    cache_path = (cache_dir(root) if write_cache else root / CACHE_RELDIR) / "discover.json"
    try:
        old = json.loads(cache_path.read_text(encoding="utf-8"))
        old = old.get("files", {}) if old.get("schema") == CACHE_SCHEMA and old.get("parser") == PARSER_ID else {}
    except (OSError, ValueError):
        old = {}
    facts: dict[str, dict] = {}
    for path, module in sorted(py_files.items()):
        digest = content_digest(root / path)
        hit = old.get(path)
        if hit and hit.get("digest") == digest:
            facts[path] = hit
            continue
        text = read_source(root / path)
        package = module if path.endswith("__init__.py") else module.rpartition(".")[0]
        facts[path] = {"digest": digest, **file_facts(text, module, package, path)}
    # Per-file facts are cached as parsed; cross-file injection results are recomputed every run.
    cached = json.dumps({"schema": CACHE_SCHEMA, "parser": PARSER_ID, "files": facts}, sort_keys=True) if write_cache else ""
    mod_to_path = {f.get("module", ""): p for p, f in facts.items()}
    py_paths = tuple(facts)
    index = {p: f.get("functions", {}) for p, f in facts.items()}
    injected = _injected_classes(facts, index, mod_to_path, py_paths=py_paths, import_roots=import_roots)
    foreign_writes = _apply_injected_writes(facts, injected)
    edges: dict[str, set[str]] = defaultdict(set)
    injected_edges: dict[str, set[str]] = defaultdict(set)
    incoming: dict[str, int] = defaultdict(int)
    for path, file in facts.items():
        for symbol, fn in file.get("functions", {}).items():
            for call in fn["calls"]:
                target = _resolve_injected(call, symbol, path, file, index, injected)
                if target:
                    injected_edges[f"{path}#{symbol}"].add(target)
                else:
                    target = _resolve(call, symbol, path, facts, index, mod_to_path, dependency_files=dependency_files, py_paths=py_paths, import_roots=import_roots)
                if target and target != f"{path}#{symbol}":
                    edges[f"{path}#{symbol}"].add(target)
                    incoming[target] += 1
    raw = {"schema": CACHE_SCHEMA, "parser": PARSER_ID, "files": facts,
           "edges": {k: sorted(v) for k, v in sorted(edges.items())}}
    if write_cache:
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_text(cache_path, cached)
        except OSError:
            pass
    raw["incoming"] = dict(incoming)
    raw["injected_edges"] = {k: sorted(v) for k, v in sorted(injected_edges.items())}
    raw["foreign_writes"] = foreign_writes
    return raw


def _class_ref(name: str, caller: str, path: str, facts: dict, index: dict, mod_to_path: dict, *, py_paths=(), import_roots=()) -> str:
    """'path#Cls' for a class name as seen from one function, or ''."""
    if not name or name == "<unresolved>":
        return ""
    target = _resolve(name, caller, path, facts, index, mod_to_path, py_paths=py_paths, import_roots=import_roots)
    cls_path, _, symbol = (target or "").partition("#")
    symbol = symbol.removesuffix(".__init__")
    if cls_path and symbol in facts.get(cls_path, {}).get("classes", ()):
        return f"{cls_path}#{symbol}"
    parts = name.split(".")
    imports = _scope_imports(facts[path], caller)
    module = imports.get(parts[0], "").replace(":", ".")
    for cut in range(len(parts) - 1, 0, -1) if module else ():
        target = resolve_module(".".join([module, *parts[1:cut]]), path, mod_to_path, py_paths, import_roots)
        symbol = ".".join(parts[cut:])
        if symbol in facts.get(target, {}).get("classes", ()):
            return f"{target}#{symbol}"
    return ""


def _injected_classes(facts: dict, index: dict, mod_to_path: dict, *, py_paths=(), import_roots=()) -> dict[str, dict[str, str]]:
    """path -> {"Cls|self.attr": "class_path#Other"} for constructor-injected attributes.

    An annotated parameter (or class-body annotation) names the class; without one, every static
    constructor call must pass the same class (or a local instance of it), otherwise it stays unresolved.
    """
    evidence: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for path, file in facts.items():
        for symbol, fn in file.get("functions", {}).items():
            for callee, arguments in fn.get("ctor_calls", ()):
                cls = _class_ref(callee, symbol, path, facts, index, mod_to_path, py_paths=py_paths, import_roots=import_roots)
                if not cls:
                    continue
                cls_path, cls_name = cls.split("#", 1)
                params = index.get(cls_path, {}).get(f"{cls_name}.__init__", {}).get("params", [])
                for slot, argument in arguments:
                    param = params[slot] if isinstance(slot, int) and slot < len(params) else slot
                    if isinstance(param, str):
                        evidence[(cls_path, cls_name, param)].add(
                            _class_ref(argument, symbol, path, facts, index, mod_to_path, py_paths=py_paths, import_roots=import_roots) or "?")
    found: dict[str, dict[str, str]] = {}
    for path, file in facts.items():
        for key, param in file.get("injected", {}).items():
            cls_name = key.split("|", 1)[0]
            ref = _class_ref(file.get("instances", {}).get(key, ""), f"{cls_name}.__init__", path, facts, index, mod_to_path, py_paths=py_paths, import_roots=import_roots)
            seen = evidence.get((path, cls_name, param), set())
            if not ref and len(seen) == 1 and "?" not in seen:
                ref = next(iter(seen))
            if ref:
                found.setdefault(path, {})[key] = ref
    return found


def _resolve_injected(call: str, caller: str, path: str, file: dict, index: dict, injected: dict) -> str | None:
    parts = call.split(".")
    cls = file.get("functions", {}).get(caller, {}).get("class", "")
    if len(parts) != 3 or parts[0] != "self" or not cls:
        return None
    ref = injected.get(path, {}).get(f"{cls}|self.{parts[1]}")
    if not ref:
        return None
    cls_path, cls_name = ref.split("#", 1)
    method = f"{cls_name}.{parts[2]}"
    return f"{cls_path}#{method}" if method in index.get(cls_path, {}) else None


def _apply_injected_writes(facts: dict, injected: dict) -> list[dict]:
    """Calls on or writes into an injected object are not writes of the holder's attribute.

    Writes into such an object's own attributes are returned for foreign_state_write.
    """
    foreign = []
    for path, keys in injected.items():
        file = facts[path]
        resolved = {key.replace("|self.", "."): ref for key, ref in keys.items()}
        for symbol, fn in file.get("functions", {}).items():
            for attr, field, line in fn.get("attr_writes", ()):
                ref = resolved.get(f"{fn['class']}.{attr}")
                if ref:
                    cls_path, cls_name = ref.split("#", 1)
                    foreign.append({"source": f"{path}#{symbol}", "line": line, "class_path": cls_path,
                                    "class": cls_name, "attr": field})
            for attr in set(fn.get("deep_writes", ())) & set(resolved):
                fn["writes"] = [write for write in fn["writes"] if write != attr]
                writers = [writer for writer in file.get("state", {}).get(attr, []) if writer != symbol]
                file["state"][attr] = writers
        for attr in resolved:
            writers = file.get("state", {}).get(attr)
            if writers is not None and all(writer.endswith(".__init__") for writer in writers):
                del file["state"][attr]
                for writer in writers:
                    function = file["functions"].get(writer, {})
                    function["writes"] = [write for write in function.get("writes", []) if write != attr]
    return foreign


def anchor_state_writes(raw: dict, anchor: str) -> set[str]:
    """The exact function anchor's known state writes, without cross-file or alias inference."""
    path, _, symbol = anchor.partition(":")
    return set(raw["files"].get(path, {}).get("functions", {}).get(symbol, {}).get("writes", []))


def reachable_effects(raw: dict, start: str, limit: int = 2000) -> dict[str, set[str]]:
    """Effect kind -> example call sites reachable from one function through repo-internal calls."""
    seen, stack, found = set(), [start], defaultdict(set)
    while stack and len(seen) < limit:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        path, symbol = node.split("#", 1)
        fn = raw["files"].get(path, {}).get("functions", {}).get(symbol)
        if fn is None:
            continue
        for kind, call, _line in fn["effects"]:
            found[kind].add(f"{symbol}->{call}")
        stack.extend(raw["edges"].get(node, ()))
    return found


def _cap(items, limit: int = SUMMARY_LIMIT) -> list:
    items = list(items)
    return items[:limit] + ([f"... +{len(items) - limit} more"] if len(items) > limit else [])


def component_summary(raw: dict, files: list[str]) -> dict:
    """Bounded, review-oriented summary for one map component (goes into map.json as a hint)."""
    entry, effects, state, raises, dynamic = [], defaultdict(int), {}, set(), set()
    reach: dict[str, set[str]] = defaultdict(set)
    unreferenced = 0
    for path in files:
        file = raw["files"].get(path)
        if not file or "functions" not in file:
            continue
        for ep in file["entrypoints"]:
            entry.append(f"{ep['kind']} {ep['name']} -> {path}:{ep['symbol']}")
            if ep["symbol"] in file["functions"]:
                for kind, sites in reachable_effects(raw, f"{path}#{ep['symbol']}").items():
                    reach[f"{ep['kind']} {ep['name']}"].add(kind)
        for symbol, fn in file["functions"].items():
            for kind, _call, _line in fn["effects"]:
                effects[kind] += 1
            raises.update(fn["raises"])
            dynamic.update(fn["dynamic"])
            if (not symbol.rsplit(".", 1)[-1].startswith("_") and not raw["incoming"].get(f"{path}#{symbol}")):
                unreferenced += 1
        for attr, writers in file["state"].items():
            state[attr] = writers
    return {
        "entrypoints": _cap(sorted(entry)),
        "effects": dict(sorted(effects.items())),
        "entrypoint_effect_reach": {k: sorted(v) for k, v in sorted(reach.items()) if v},
        "state_writers": {k: _cap(v, 4) for k, v in sorted(state.items())[:SUMMARY_LIMIT]},
        "state_attrs_total": len(state),
        "raises": _cap(sorted(raises)),
        "dynamic": _cap(sorted(dynamic)),
        "public_functions_without_repo_callers": unreferenced,
    }


def discover_inventory(root: Path, inv, *, write_cache: bool = True, data: dict | None = None, extra_sources=()) -> dict:
    """Discover non-test Python, plus supplied source paths already in this inventory.

    Extra sources let one target view retain both real source classifications;
    they never bypass ignore rules or change ordinary lint/check scope.
    """

    from .inventory import module_name, python_roots

    roots = python_roots(list(inv.py))
    dependency_files: dict[str, set[str]] = {}
    if data is not None:
        from .mapfile import component_files, owner_index

        owners, _ = owner_index(data, inv)
        components = {component["id"]: component for component in data.get("components", [])}
        files = {cid: set(component_files(component, inv)) for cid, component in components.items()}
        for path, cid in owners.items():
            dependency_files[path] = {target for dep in components[cid].get("depends_on", ())
                                      for target in files.get(dep, ())}
    extra = set(extra_sources)
    modules = {f: module_name(f, roots) for f in inv.py if not inv.is_test(f) or f in extra}
    raw = discover(root, modules, write_cache=write_cache, dependency_files=dependency_files,
                   import_roots=tuple(data.get("import_roots", ())) if data is not None else inv.import_roots)
    mod_to_path = {module: path for path, module in modules.items()}
    for name, target, via in console_scripts(root):
        module, sep, symbol = target.partition(":")
        path = mod_to_path.get(module.strip())
        symbol = symbol.strip().split("[", 1)[0].strip()
        file = raw["files"].get(path or "", {})
        if sep and symbol in file.get("functions", {}):
            file["entrypoints"].append({"kind": "console_script", "name": name, "symbol": symbol,
                                        "line": file["functions"][symbol]["line"], "via": via})
    return raw


def console_scripts(root: Path) -> list[tuple[str, str, str]]:
    """Read literal packaging entrypoints without importing or executing packaging code."""
    import configparser
    import tomllib

    found: set[tuple[str, str, str]] = set()
    cfg = root / "setup.cfg"
    if cfg.is_file():
        parser = configparser.ConfigParser(interpolation=None)
        try:
            parser.read(cfg, encoding="utf-8")
            text = parser.get("options.entry_points", "console_scripts", fallback="")
        except (OSError, configparser.Error):
            text = ""
        for line in text.splitlines():
            name, eq, target = line.partition("=")
            if eq and name.strip():
                found.add((name.strip(), target.strip(), "setup.cfg"))
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        try:
            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        for table in (data.get("project", {}).get("scripts", {}),
                      data.get("tool", {}).get("poetry", {}).get("scripts", {})):
            if isinstance(table, dict):
                for name, target in table.items():
                    if isinstance(target, str):
                        found.add((name, target, "pyproject.toml"))
    setup = root / "setup.py"
    if setup.is_file():
        try:
            tree = ast.parse(read_source(setup))
        except (OSError, SyntaxError, ValueError):
            tree = None
        for node in ast.walk(tree) if tree else ():
            if isinstance(node, ast.Dict):
                for key, value in zip(node.keys, node.values):
                    if isinstance(key, ast.Constant) and key.value == "console_scripts":
                        for item in _literal_strings(value):
                            name, eq, target = item.partition("=")
                            if eq and name.strip():
                                found.add((name.strip(), target.strip(), "setup.py"))
    return sorted(found)


def relied_models(raw: dict, data: dict, inv, anchors: dict[str, list[str]], *, component: str | None = None,
                  files=None) -> dict[str, set[tuple[str, str]]]:
    """Models whose ``IMPLEMENTED_BY`` anchors the given code calls directly: {model id: {(owner, symbol)}}.

    The callers are the files of ``component``'s subtree, or the given changed ``files``. Anchors in the
    caller's own component, its subtree or its ancestors do not count. Only direct calls (one step in the
    discovered call graph) are followed, never a transitive closure. A class anchor matches its
    constructor and every method.
    """
    from .mapfile import component_ancestors, component_files, component_subtree, owner_index

    owner, _ = owner_index(data, inv)
    by_id = {c["id"]: c for c in data.get("components", [])}

    def related_files(cid):
        members = [c["id"] for c in component_subtree(data, cid)] + list(component_ancestors(data, cid))
        return {path for member in members if member in by_id for path in component_files(by_id[member], inv)}

    if component is not None:
        sources = {path: related_files(component) for path in
                   {p for c in component_subtree(data, component) for p in component_files(c, inv)}}
    else:
        sources = {path: related_files(owner[path]) for path in files or () if path in owner}
    found: dict[str, set[tuple[str, str]]] = defaultdict(set)
    targets = [(mid, anchor.partition(":")[0], anchor.partition(":")[2]) for mid, values in anchors.items()
               for anchor in values if ":" in anchor]
    for source, excluded in sources.items():
        prefix = source + "#"
        for caller, callees in raw.get("edges", {}).items():
            if not caller.startswith(prefix):
                continue
            for callee in callees:
                path, _, symbol = callee.partition("#")
                if path in excluded or path not in owner:
                    continue
                for mid, anchor_path, anchor_symbol in targets:
                    if path == anchor_path and (symbol == anchor_symbol or symbol.startswith(anchor_symbol + ".")):
                        found[mid].add((owner[path], anchor_symbol))
    return dict(found)

def literal_sites(text) -> list[tuple[str, int, str]]:
    """Token-shaped strings classified by their actual syntax role, with no stored index."""
    import re
    try:
        syntax=ast.parse(text)
    except SyntaxError:
        return []
    parents={id(child):node for node in ast.walk(syntax) for child in ast.iter_child_nodes(node)}
    excluded=set()
    for node in ast.walk(syntax):
        if isinstance(node,(ast.Module,ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
            first=node.body[0] if node.body else None
            if isinstance(first,ast.Expr) and isinstance(first.value,ast.Constant) and isinstance(first.value.value,str):
                excluded.add(id(first.value))
        if isinstance(node,ast.JoinedStr):
            excluded.update(id(value) for value in node.values if isinstance(value,ast.Constant))
    found=[]
    for node in ast.walk(syntax):
        if not isinstance(node,ast.Constant) or not isinstance(node.value,str) or id(node) in excluded:
            continue
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.:-]{2,}',node.value):
            continue
        parent=parents.get(id(node)); role='value'
        if isinstance(parent,ast.Dict) and node in parent.keys:
            role='key_write'
        elif isinstance(parent,ast.Subscript) and parent.slice is node:
            role='key_write' if isinstance(parent.ctx,ast.Store) else 'key_read'
        elif isinstance(parent,ast.Call) and parent.args and parent.args[0] is node and isinstance(parent.func,ast.Attribute) and parent.func.attr in ('get','pop','setdefault'):
            role='key_read'
        else:
            cursor=parent
            while isinstance(cursor,(ast.Tuple,ast.List,ast.Set)):
                cursor=parents.get(id(cursor))
            if isinstance(cursor,ast.Compare) and any(isinstance(op,(ast.Eq,ast.NotEq,ast.In,ast.NotIn)) for op in cursor.ops) or isinstance(cursor,ast.MatchValue):
                role='compare'
        found.append((node.value,node.lineno,node.col_offset,role))
    return [(value,line,role) for value,line,column,role in sorted(found,key=lambda item:(item[1],item[2]))]


def reachable_functions(edges, start):
    """Operation-local transitive calls; no retained reachability index."""
    pending, found = [start], set()
    while pending:
        node = pending.pop()
        if node not in found:
            found.add(node)
            pending.extend(edges.get(node, ()))
    return found


def anchor_matches(anchor, function):
    """A primary function/class anchor includes its nested symbols."""
    path, _, symbol = anchor.partition(':')
    file, _, name = function.partition('#')
    return path == file and (name == symbol or name.startswith(symbol+'.'))


def select_model_functions(data, inv, tree, raw, functions):
    """The shared body-edit selection used by change and relation views."""
    from .mapfile import component_files, component_scope, flow_step_parts
    selected=set()
    flow_lines=[]
    reasons=defaultdict(list)
    own={mid:node.contract.get('IMPLEMENTED_BY',{}) for mid,node in tree.nodes.items()}
    uses={mid:node.contract.get('USES',{}) for mid,node in tree.nodes.items()}
    closures={}
    def reaches(anchor,fn):
        if anchor not in closures:
            path,_,symbol=anchor.partition(':')
            starts=[path+'#'+name for name in raw.get('files',{}).get(path,{}).get('functions',{}) if name==symbol or name.startswith(symbol+'.')]
            closures[anchor]=set().union(*(reachable_functions(raw['edges'],start) for start in starts)) if starts else set()
        return fn in closures[anchor]
    unreached=[]
    for fn in sorted(functions):
        owners={mid for mid,anchors in own.items() if any(anchor_matches(anchor,fn) for anchor in anchors.values())}
        hits=set()
        for mid in tree.nodes:
            for name,anchor in {**own[mid],**uses[mid]}.items():
                if anchor_matches(anchor,fn):
                    selected.add(mid);hits.add(mid);reasons[mid].append(name+' is '+fn.replace('#',':',1))
        reached={mid for mid,anchors in own.items() if any(reaches(anchor,fn) for anchor in anchors.values())} if not owners else set()
        reached={mid for mid in reached if not any(mid in tree.ancestors(other) for other in reached)}
        for mid in reached:
            selected.add(mid);hits.add(mid)
            name=next(name for name,anchor in own[mid].items() if reaches(anchor,fn))
            reasons[mid].append(name+' reaches '+fn.replace('#',':',1))
        for flow in data.get('flows',()):
            mid=next((mid for mid,node in tree.nodes.items() if node.path==flow.get('model')),None)
            if mid is None: continue
            for number,step in enumerate(flow.get('steps',()),1):
                cid,symbol,_=flow_step_parts(step)
                comp=next((c for c in data['components'] if c['id']==cid),None)
                if comp is None: continue
                anchors=[path+':'+(symbol or fn.split('#',1)[1]) for path in component_files(component_scope(data,comp),inv)]
                direct_flow=any(anchor_matches(anchor,fn) for anchor in anchors)
                via=not owners and not any(mid in tree.ancestors(other) for other in reached) and any(reaches(anchor,fn) for anchor in anchors)
                if direct_flow or via:
                    selected.add(mid);hits.add(mid)
                    flow_lines.append(f"flow {flow['id']}: step {number} changed; model {mid}")
        if not hits: unreached.append(fn.replace('#',':',1))
    return selected, dict(reasons), flow_lines, unreached


def function_spans(syntax):
    """Lexical function intervals, including nested classes and exception branches."""
    syntax = ast.parse(syntax) if isinstance(syntax, str) else syntax
    spans=[]
    def visit(node, prefix=''):
        for child in ast.iter_child_nodes(node):
            if isinstance(child,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
                symbol=prefix+child.name
                if not isinstance(child,ast.ClassDef): spans.append((child.lineno,child.end_lineno,symbol))
                visit(child,symbol+'.')
            else: visit(child,prefix)
    visit(syntax)
    return spans
