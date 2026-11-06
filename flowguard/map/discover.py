"""Resolve calls from source facts; no second inventory or discovery cache."""
from __future__ import annotations

from collections import defaultdict

from .inventory import resolve_module

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
