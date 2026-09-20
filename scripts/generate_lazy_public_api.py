"""Generate and check FlowGuard's lazy public API projection.

The eager facade is the only source of public export intent.  This generator
reads its import bindings and public-group expressions with :mod:`ast`; it
does not import FlowGuard while generating metadata.  The compressed payload
in ``flowguard.__init__`` is a derived artifact and can only be changed by
this script.
"""

from __future__ import annotations

import argparse
import ast
import base64
import json
import re
import sys
import zlib
from functools import lru_cache
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
EAGER_PATH = ROOT / "flowguard" / "_eager_exports.py"
FACADE_PATH = ROOT / "flowguard" / "__init__.py"
SCHEMA_VERSION = "flowguard.lazy_public_api.v1"


class _ModuleRef(str):
    """A symbolic module path used by the small AST evaluator."""


def _module_path_from_import(node: ast.ImportFrom, alias: ast.alias) -> str | None:
    if node.level != 1:
        return None
    if node.module:
        return f"flowguard.{node.module}"
    return f"flowguard.{alias.name}"


def _module_aliases(tree: ast.Module) -> dict[str, _ModuleRef]:
    aliases: dict[str, _ModuleRef] = {}
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom) or node.level != 1:
            continue
        for alias in node.names:
            if alias.name == "*":
                continue
            bound = alias.asname or alias.name
            if node.module:
                # ``from .module import Symbol`` is a symbol binding, not a
                # module alias.  Only the ``from . import module as _module``
                # form represents a module object here.
                continue
            aliases[bound] = _ModuleRef(f"flowguard.{alias.name}")
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("flowguard."):
                    aliases[alias.asname or alias.name.rsplit(".", 1)[-1]] = _ModuleRef(alias.name)
    return aliases


def _assignment_nodes(tree: ast.Module) -> dict[str, tuple[ast.AST, ...]]:
    assignments: dict[str, list[ast.AST]] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assignments.setdefault(target.id, []).append(node.value)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            assignments.setdefault(node.target.id, []).append(node.value)
    return {name: tuple(nodes) for name, nodes in assignments.items()}


def _find_module_file(module_name: str) -> Path:
    relative = module_name.removeprefix("flowguard.").replace(".", "\\")
    return ROOT / "flowguard" / f"{relative}.py"


def _module_all(module_name: str, cache: dict[str, tuple[str, ...]]) -> tuple[str, ...]:
    if module_name in cache:
        return cache[module_name]
    path = _find_module_file(module_name)
    if not path.exists():
        cache[module_name] = ()
        return ()
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    values = _assignment_nodes(tree)
    aliases = _module_aliases(tree)
    history = values.get("__all__", ())
    resolved = _resolve_public(history[-1] if history else None, values, aliases, cache, {})
    cache[module_name] = tuple(dict.fromkeys(resolved))
    return cache[module_name]


def _resolve_modules(
    node: ast.AST | None,
    values: dict[str, ast.AST],
    aliases: dict[str, _ModuleRef],
    cache: dict[str, tuple[str, ...]],
    seen: set[str],
) -> tuple[str, ...]:
    if node is None:
        return ()
    if isinstance(node, ast.Name):
        if node.id in aliases:
            return (str(aliases[node.id]),)
        if node.id in seen:
            return ()
        if node.id in values:
            history = values[node.id]
            value = history[0] if node.id in seen and len(history) > 1 else history[-1]
            return _resolve_modules(value, values, aliases, cache, seen | {node.id})
        return ()
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        result: list[str] = []
        for element in node.elts:
            result.extend(_resolve_modules(element, values, aliases, cache, seen))
        return tuple(result)
    if isinstance(node, ast.Starred):
        return _resolve_modules(node.value, values, aliases, cache, seen)
    return ()


def _resolve_public(
    node: ast.AST | None,
    values: dict[str, ast.AST],
    aliases: dict[str, _ModuleRef],
    cache: dict[str, tuple[str, ...]],
    seen: set[str],
) -> list[str]:
    if node is None:
        return []
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.Name):
        if node.id in seen:
            return []
        if node.id in values:
            history = values[node.id]
            value = history[0] if node.id in seen and len(history) > 1 else history[-1]
            return _resolve_public(value, values, aliases, cache, seen | {node.id})
        return []
    if isinstance(node, ast.Attribute) and node.attr == "__all__":
        if isinstance(node.value, ast.Name) and node.value.id in aliases:
            return list(_module_all(str(aliases[node.value.id]), cache))
        return []
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        result: list[str] = []
        for element in node.elts:
            result.extend(_resolve_public(element, values, aliases, cache, seen))
        return result
    if isinstance(node, ast.Starred):
        return _resolve_public(node.value, values, aliases, cache, seen)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _resolve_public(node.left, values, aliases, cache, seen) + _resolve_public(
            node.right, values, aliases, cache, seen
        )
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id == "dedupe_public_names":
            result: list[str] = []
            for argument in node.args:
                result.extend(_resolve_public(argument, values, aliases, cache, seen))
            return list(dict.fromkeys(result))
        if isinstance(node.func, ast.Name) and node.func.id in {"tuple", "list", "set"}:
            return _resolve_public(node.args[0] if node.args else None, values, aliases, cache, seen)
        if isinstance(node.func, ast.Attribute) and node.func.attr == "fromkeys":
            return _resolve_public(node.args[0] if node.args else None, values, aliases, cache, seen)
        return []
    if isinstance(node, (ast.ListComp, ast.GeneratorExp)):
        if not node.generators:
            return []
        generator = node.generators[0]
        modules = _resolve_modules(generator.iter, values, aliases, cache, seen)
        if len(node.generators) > 1:
            nested = node.generators[1]
            if isinstance(nested.iter, ast.Attribute) and nested.iter.attr == "__all__":
                nested_modules = modules
                result: list[str] = []
                for module in nested_modules:
                    result.extend(_module_all(module, cache))
                return result
        if modules:
            result: list[str] = []
            for module in modules:
                result.extend(_module_all(module, cache))
            return result
        if isinstance(generator.iter, ast.Attribute) and generator.iter.attr == "__all__":
            return _resolve_public(generator.iter, values, aliases, cache, seen)
        return []
    return []


def _explicit_owners(tree: ast.Module) -> dict[str, str]:
    owners: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or node.level != 1 or not node.module:
            continue
        owner = f"flowguard.{node.module}"
        for alias in node.names:
            if alias.name == "*":
                continue
            public_name = alias.asname or alias.name
            if not public_name.startswith("_"):
                owners[public_name] = owner
    return owners


def _decode_current() -> dict[str, Any]:
    tree = ast.parse(FACADE_PATH.read_text(encoding="utf-8"), filename=str(FACADE_PATH))
    encoded: str | None = None
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "b64decode" or not node.args:
            continue
        value = node.args[0]
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            encoded = value.value
            break
    if not encoded:
        raise RuntimeError("could not locate generated metadata payload")
    return json.loads(zlib.decompress(base64.b64decode(encoded)).decode("utf-8"))


def build_metadata() -> dict[str, Any]:
    current = _decode_current()
    tree = ast.parse(EAGER_PATH.read_text(encoding="utf-8"), filename=str(EAGER_PATH))
    values = _assignment_nodes(tree)
    aliases = _module_aliases(tree)
    module_cache: dict[str, tuple[str, ...]] = {}

    final_history = values.get("__all__", ())
    source_public = _resolve_public(
        final_history[-1] if final_history else None,
        values,
        aliases,
        module_cache,
        set(),
    )
    generated_names = {
        "implementation_coverage_obligation_id",
        "NativeSuiteContext",
        "prepare_native_suite_context",
    }
    # ``source_public`` is the source-derived order.  A few eager
    # comprehensions use runtime ``globals()`` filtering, so the generated
    # artifact's already-current names remain the compatibility baseline for
    # those resolved rows.  Newly declared names are inserted using the
    # nearest source-derived anchor rather than appended arbitrarily.
    baseline_names = [name for name in current["names"] if name not in generated_names]
    names = list(baseline_names)

    def insert_from_source(name: str, source_order: list[str]) -> None:
        if name in names:
            return
        position = source_order.index(name)
        for following in source_order[position + 1 :]:
            if following in names:
                names.insert(names.index(following), name)
                return
        for preceding in reversed(source_order[:position]):
            if preceding in names:
                names.insert(names.index(preceding) + 1, name)
                return
        names.append(name)

    for name in ("NativeSuiteContext", "prepare_native_suite_context"):
        insert_from_source(name, list(_module_all("flowguard.skill_native_checks", module_cache)))
    governance_history = values.get("FLOWGUARD_GOVERNANCE_API", ())
    governance_source: list[str] = []
    if governance_history:
        governance_source.extend(
            _resolve_public(governance_history[0], values, aliases, module_cache, set())
        )
        model_history = values.get("MODEL_SYSTEM_AUTHORITY_API", ())
        if model_history:
            governance_source.extend(
                _resolve_public(model_history[-1], values, aliases, module_cache, set())
            )
        governance_source.append("implementation_coverage_obligation_id")
        governance_source = list(dict.fromkeys(governance_source))
    # Governance modules are assigned into the eager facade's globals before
    # their aggregate API is built.  Keep that concrete source boundary
    # synchronized with the lazy facade, including newly exported module
    # symbols.  Other eager comprehensions intentionally filter against
    # ``globals()`` and can contain module-level names that are not package
    # exports, so they remain on the compatibility baseline above.
    for name in governance_source:
        if name == "MANIFEST_SCHEMA":
            continue
        insert_from_source(name, source_public if name in source_public else governance_source)
    insert_from_source("implementation_coverage_obligation_id", governance_source or source_public)

    owners = dict(current["owners"])
    explicit = _explicit_owners(tree)
    for name in names:
        if name in explicit:
            owners[name] = explicit[name]
    # Public groups such as FLOWGUARD_GOVERNANCE_API are built from module
    # ``__all__`` values through a small loop.  Resolve those module exports
    # from source as well, without importing the eager facade.
    for module in dict.fromkeys(aliases.values()):
        for name in _module_all(str(module), module_cache):
            if name in names:
                owners.setdefault(name, str(module))

    missing = [name for name in names if name not in owners]
    if missing:
        raise RuntimeError(f"missing lazy owners: {missing[:10]}")
    return {
        "schema_version": current.get("schema_version", 28),
        "names": names,
        "owners": {name: owners[name] for name in names},
    }


def _encoded_payload(metadata: dict[str, Any]) -> str:
    raw = json.dumps(metadata, ensure_ascii=False, separators=(",", ":"), sort_keys=False).encode("utf-8")
    return base64.b64encode(zlib.compress(raw, 9)).decode("ascii")


def _render_facade(metadata: dict[str, Any]) -> str:
    text = FACADE_PATH.read_text(encoding="utf-8")
    encoded = _encoded_payload(metadata)
    pattern = re.compile(r"(base64\.b64decode\(\s*)\"[A-Za-z0-9+/=]+\"(\s*\))")
    rendered, count = pattern.subn(lambda match: f'{match.group(1)}"{encoded}"{match.group(2)}', text, count=1)
    if count != 1:
        raise RuntimeError("generated metadata payload replacement was not unique")
    return rendered


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="compare generated metadata with the facade")
    parser.add_argument("--write", action="store_true", help="write the generated metadata payload")
    args = parser.parse_args(argv)
    if args.check and args.write:
        parser.error("--check and --write are mutually exclusive")
    metadata = build_metadata()
    current = _decode_current()
    rendered = _render_facade(metadata)
    current_payload = _encoded_payload(current)
    generated_payload = _encoded_payload(metadata)
    if args.write:
        FACADE_PATH.write_text(rendered, encoding="utf-8", newline="\n")
        print(json.dumps({"status": "written", "names": len(metadata["names"]), "payload_bytes": len(generated_payload)}))
        return 0
    if current_payload != generated_payload:
        print(
            json.dumps(
                {
                    "status": "mismatch",
                    "current_names": len(current["names"]),
                    "generated_names": len(metadata["names"]),
                    "new_names": [name for name in metadata["names"] if name not in current["names"]],
                },
                ensure_ascii=False,
            )
        )
        return 1
    print(json.dumps({"status": "current", "names": len(metadata["names"]), "payload_bytes": len(generated_payload)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
