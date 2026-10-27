"""Python syntax facts used by reverse discovery."""
from __future__ import annotations
import ast
from collections import defaultdict

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
NETWORK_ROOTS = {"requests", "httpx", "urllib", "aiohttp", "socket", "http", "smtplib", "boto3"}
MUTATORS = {"append", "extend", "insert", "pop", "remove", "clear", "update", "add", "discard", "setdefault"}

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
