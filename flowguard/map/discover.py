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
from collections import defaultdict
from pathlib import Path

from .common import CACHE_RELDIR, content_digest, is_test_file

CACHE_SCHEMA = "flowguard.map.discover_cache.v2"  # bump when the analysis changes
SUMMARY_LIMIT = 12

ROUTE_LEAVES = {"route", "get", "post", "put", "delete", "patch", "head", "options", "websocket", "api_route"}
CLI_LEAVES = {"command", "group"}
HANDLER_LEAVES = {"callback", "handler", "listener", "on", "subscribe", "task", "job", "receiver"}
FS_WRITE = {"write_text", "write_bytes", "mkdir", "makedirs", "touch", "chmod", "symlink_to", "copy", "copy2",
            "copyfile", "copytree", "move", "rename"}
FS_DELETE = {"unlink", "remove", "rmdir", "rmtree", "removedirs"}
FS_RECEIVERS = ("os", "shutil", "path", "Path", "dir", "file", "target", "dest", "tmp", "root")
SUBPROCESS = {"subprocess.run", "subprocess.call", "subprocess.check_call", "subprocess.check_output",
              "subprocess.Popen", "os.system", "os.popen", "os.execv", "os.execvp", "asyncio.create_subprocess_exec"}
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


def _effect_kind(call: ast.Call, name: str, imports: dict[str, str] | None = None) -> str:
    leaf = name.rsplit(".", 1)[-1]
    receiver = name.rsplit(".", 1)[0] if "." in name else ""
    if name == "open" or leaf == "open" and receiver.endswith(("path", "Path", "io")):
        mode = _str_arg(call, 1, "mode")
        return "fs_write" if any(c in mode for c in "wax+") else ""
    if name in SUBPROCESS or receiver == "subprocess":
        return "subprocess"
    if name.startswith(NETWORK_PREFIXES) and (imports is None or _imported_root(name, imports) in NETWORK_ROOTS):
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
                                  "raises": set(), "dynamic": set(), "writes": set(), "locals": set()}
        for deco in node.decorator_list:
            self._decorator_entrypoint(deco, symbol, node)
        for stmt in node.body:
            self.visit(stmt)
        self.scope.pop()

    visit_FunctionDef = visit_AsyncFunctionDef = _visit_function

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
            self.imports[alias.asname or alias.name.split(".")[0]] = alias.name if alias.asname else alias.name.split(".")[0]

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.level:
            parts = self.package.split(".") if self.package else []
            parts = parts[: len(parts) - (node.level - 1)] if node.level > 1 else parts
            base = ".".join(p for p in [*parts, node.module or ""] if p)
        else:
            base = node.module or ""
        for alias in node.names:
            if alias.name != "*":
                self.imports[alias.asname or alias.name] = f"{base}:{alias.name}"

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
        if fn is not None and name:
            fn["calls"].add(name)
            root_name = name.split(".", 1)[0]
            imports = self.imports if root_name not in fn["locals"] else {}
            kind = _effect_kind(node, name, imports)
            if kind:
                fn["effects"].append([kind, name, node.lineno])
            if name in DYNAMIC or leaf in {"import_module", "entry_points"}:
                fn["dynamic"].add(name)
        self.generic_visit(node)

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
        elif name == "os.environ":
            fn["effects"].append(["env_write", "os.environ[...]", getattr(target, "lineno", 0)])

    def visit_Assign(self, node: ast.Assign) -> None:
        fn = self._fn()
        if fn is not None:
            fn["locals"].update(t.id for t in node.targets if isinstance(t, ast.Name))
        for target in node.targets:
            self._write_target(target)
            ctor = _name(node.value.func) if isinstance(node.value, ast.Call) else ""
            if isinstance(target, ast.Name) and ctor and ctor.rsplit(".", 1)[-1][:1].isupper():
                self.instances[f"{self._symbol() if self.scope else ''}|{target.id}"] = ctor
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self._write_target(node.target)
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


def _mutating_method_writes(visitor: _FileVisitor) -> None:
    """self.items.append(x) mutates state just like self.items = ..."""
    mutators = {"append", "extend", "insert", "pop", "remove", "clear", "update", "add", "discard", "setdefault"}
    for symbol, fn in visitor.functions.items():
        if not fn["class"]:
            continue
        for call in fn["calls"]:
            parts = call.split(".")
            if len(parts) == 3 and parts[0] == "self" and parts[2] in mutators:
                attr = f"{fn['class']}.{parts[1]}"
                visitor.state[attr].add(symbol)
                fn["writes"].add(attr)


def file_facts(text: str, module: str, package: str, path: str) -> dict:
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return {"parse_error": f"{exc.msg} line {exc.lineno}"}
    visitor = _FileVisitor(module, package)
    visitor.visit(tree)
    _mutating_method_writes(visitor)
    for call in visitor.main_calls:
        if call in visitor.functions:
            visitor.entrypoints.append({"kind": "main_call", "name": call, "symbol": call, "line": 0, "via": "__main__"})
    return {
        "module": module,
        "imports": visitor.imports,
        "instances": visitor.instances,
        "entrypoints": visitor.entrypoints,
        "state": {k: sorted(v) for k, v in sorted(visitor.state.items())},
        "functions": {s: {"line": f["line"], "class": f["class"], "calls": sorted(f["calls"]),
                          "effects": f["effects"], "raises": sorted(x for x in f["raises"] if x),
                          "dynamic": sorted(f["dynamic"]), "writes": sorted(f["writes"])}
                      for s, f in visitor.functions.items()},
    }


def _resolve(call: str, caller: str, path: str, facts: dict, index: dict[str, dict[str, str]],
             mod_to_path: dict[str, str]) -> str | None:
    """Resolve a call to 'path#symbol' inside the repo, or None (external / dynamic)."""
    file = facts[path]
    funcs = file["functions"]
    cls = funcs.get(caller, {}).get("class", "")
    parts = call.split(".")
    if parts[0] == "self" and cls and len(parts) == 2:
        return f"{path}#{cls}.{parts[1]}" if f"{cls}.{parts[1]}" in funcs else None
    if len(parts) == 1:
        if call in funcs:
            return f"{path}#{call}"
        if f"{call}.__init__" in funcs:
            return f"{path}#{call}.__init__"
        if call in file.get("classes", ()):
            return None
        bound = file["imports"].get(call, "")
        if ":" in bound:
            mod, sym = bound.split(":", 1)
            target = mod_to_path.get(mod)
            if target and sym in index.get(target, {}):
                return f"{target}#{sym}"
            if target and f"{sym}.__init__" in index.get(target, {}):
                return f"{target}#{sym}.__init__"
        return None
    instances = file.get("instances", {})
    ctor = instances.get(f"{caller}|{parts[0]}") or instances.get(f"|{parts[0]}")
    if ctor and len(parts) == 2:
        init = _resolve(ctor, caller, path, facts, index, mod_to_path)       # -> path#Cls.__init__ or path#Cls
        cls_path, _, cls_symbol = (init or "").partition("#")
        cls_symbol = cls_symbol.removesuffix(".__init__")
        if cls_path and f"{cls_symbol}.{parts[1]}" in index.get(cls_path, {}):
            return f"{cls_path}#{cls_symbol}.{parts[1]}"
    bound = file["imports"].get(parts[0], "")
    module = bound.replace(":", ".") if bound else ""
    if module:
        for cut in range(len(parts) - 1, 0, -1):
            target = mod_to_path.get(".".join([module, *parts[1:cut]]))
            if target and ".".join(parts[cut:]) in index.get(target, {}):
                return f"{target}#{'.'.join(parts[cut:])}"
    return None


def discover(root: Path, py_files: dict[str, str], *, write_cache: bool = True) -> dict:
    """py_files: path -> module.  Returns {"files": facts, "edges": ..., "reach": ...} (raw)."""
    cache_path = root / CACHE_RELDIR / "discover.json"
    try:
        old = json.loads(cache_path.read_text(encoding="utf-8"))
        old = old.get("files", {}) if old.get("schema") == CACHE_SCHEMA else {}
    except (OSError, ValueError):
        old = {}
    facts: dict[str, dict] = {}
    for path, module in sorted(py_files.items()):
        digest = content_digest(root / path)
        hit = old.get(path)
        if hit and hit.get("digest") == digest:
            facts[path] = hit
            continue
        text = (root / path).read_text(encoding="utf-8", errors="replace")
        package = module if path.endswith("__init__.py") else module.rpartition(".")[0]
        facts[path] = {"digest": digest, **file_facts(text, module, package, path)}
    mod_to_path = {f.get("module", ""): p for p, f in facts.items()}
    index = {p: f.get("functions", {}) for p, f in facts.items()}
    edges: dict[str, set[str]] = defaultdict(set)
    incoming: dict[str, int] = defaultdict(int)
    for path, file in facts.items():
        for symbol, fn in file.get("functions", {}).items():
            for call in fn["calls"]:
                target = _resolve(call, symbol, path, facts, index, mod_to_path)
                if target and target != f"{path}#{symbol}":
                    edges[f"{path}#{symbol}"].add(target)
                    incoming[target] += 1
    raw = {"schema": CACHE_SCHEMA, "files": facts,
           "edges": {k: sorted(v) for k, v in sorted(edges.items())}}
    if write_cache:
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(raw, sort_keys=True), encoding="utf-8")
        except OSError:
            pass
    raw["incoming"] = dict(incoming)
    return raw


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


def discover_inventory(root: Path, inv) -> dict:
    """Run discovery over the inventory's non-test Python files (cached by content digest)."""

    from .inventory import module_name, python_roots

    roots = python_roots(list(inv.py))
    return discover(root, {f: module_name(f, roots) for f in inv.py if not is_test_file(f)})
