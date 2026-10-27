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
                         + (Path(__file__).parent / "discovery_syntax.py").read_bytes()
                         + sys.version.encode())[:16]   # ast results differ between Python versions
SUMMARY_LIMIT = 12


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
    from .selection import reachable_functions as shared

    return shared(edges, start)


def anchor_matches(anchor, function):
    """A primary function/class anchor includes its nested symbols."""
    from .selection import anchor_matches as shared

    return shared(anchor, function)


def select_model_functions(data, inv, tree, raw, functions):
    """The shared body-edit selection used by change and relation views."""
    from .selection import select_model_functions as shared

    return shared(data, inv, tree, raw, functions)


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

from .discovery_syntax import (CLI_LEAVES, DB_LEAVES, DYNAMIC, EMIT_LEAVES, EXIT_CALLS, FS_DELETE, FS_RECEIVERS, FS_WRITE, HANDLER_LEAVES, MUTATORS, NETWORK_LEAVES, NETWORK_PREFIXES, NETWORK_ROOTS, ROUTE_LEAVES, SUBPROCESS, _FileVisitor, _annotation_class, _effect_kind, _imported_root, _literal_strings, _mutating_method_writes, _name, _str_arg)
