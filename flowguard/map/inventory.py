"""Repository inventory: files, Python symbols/imports/duplicate fingerprints, JS imports.

Parse results are cached in .flowguard/cache/inventory.json keyed by
(size, mtime_ns, module) plus the parser code and Python version; files
written in the last 3 s are never cached.  The cache is a speed-up only,
never authority: deleting .flowguard/cache/ is always safe.
"""

from __future__ import annotations

import ast
import copy
import json
import os
import re
import subprocess
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .common import cache_dir, CACHE_RELDIR, JS_EXTS, SOURCE_EXTS, git_paths, is_test_file, matches_any, norm, read_source, sha256_bytes

CACHE_SCHEMA = "flowguard.map.inventory_cache.v4"
# A parse cache is reused only by the exact parser code that wrote it (upgrades never keep stale parses).
PARSER_ID = sha256_bytes(Path(__file__).read_bytes() + (Path(__file__).parent / "common.py").read_bytes()
                         + sys.version.encode())[:16]   # ast results differ between Python versions
RACY_NS = 3_000_000_000  # never cache the parse of a file written in the last 3 s (FAT/SMB/NTFS clock ticks)
MIN_DUP_NODES = 40   # functions smaller than this many AST nodes are ignored by duplicate detection
JS_IMPORT = re.compile(r"""(?:import\s[^'"]*?from\s*|import\s*\(\s*|require\s*\(\s*|import\s+)['"](\.{1,2}/[^'"]+)['"]""")


@dataclass
class PyInfo:
    module: str
    symbols: set[str] = field(default_factory=set)   # "name" and "Class.method"
    imports: set[str] = field(default_factory=set)   # "a.b" for import, "a:b" for from-import
    loc: int = 0                                     # non-blank, non-comment lines
    parse_error: str = ""
    bodies: list = field(default_factory=list)       # [symbol, body_hash, node_count]
    lazy_exports: dict[str, str] = field(default_factory=dict)
    string_literals: set[str] = field(default_factory=set)
    dynamic_imports: bool = False
    import_lines: dict[str, int] = field(default_factory=dict)


@dataclass
class Inventory:
    root: Path
    files: list[str]                  # every non-ignored file
    source: list[str]                 # code plus explicitly registered exact files (includes tests)
    tests: list[str]                  # source files that look like tests
    py: dict[str, PyInfo]             # path -> parse result
    file_deps: dict[str, set[str]]    # path -> repo paths it imports at runtime
    loc: dict[str, int]
    explicit_sources: set[str] = field(default_factory=set)
    dynamic_files: set[str] = field(default_factory=set)

    def set_explicit_sources(self, patterns: list[str]) -> None:
        self.explicit_sources = {norm(p) for p in patterns if not any(char in p for char in "*?[")}
        # Exact schema/config/resource paths share the normal owner and freshness
        # boundary. Globs never broaden the default code inventory. Ignored files
        # are absent from files, so an explicit path cannot bypass ignore rules.
        self.source = [f for f in self.files if Path(f).suffix in SOURCE_EXTS or f in self.explicit_sources]
        self.tests = [f for f in self.source if self.is_test(f)]

    def is_test(self, path: str) -> bool:
        return path not in self.explicit_sources and is_test_file(path)


def list_files(root: Path) -> list[str]:
    """Tracked plus untracked-but-not-ignored files (git); os.walk when git is unavailable."""
    try:
        return sorted(f for f in (norm(x) for x in git_paths(root, "ls-files", "-z", "-co", "--exclude-standard"))
                      if (root / f).is_file())
    except (OSError, subprocess.CalledProcessError):
        found = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in {".git", "node_modules", "__pycache__", ".venv"}]
            found += [norm(str(Path(dirpath, n).relative_to(root))) for n in filenames]
        return sorted(found)


def python_roots(files: list[str]) -> list[str]:
    """Import roots: '' (repo root) plus every parent directory of a top-level package (e.g. 'src')."""
    roots = {""}
    present = set(files)
    for f in files:
        if f.endswith("/__init__.py"):
            pkg_dir = f.rsplit("/", 1)[0]
            parent = pkg_dir.rsplit("/", 1)[0] if "/" in pkg_dir else ""
            if (f"{parent}/__init__.py" if parent else "__init__.py") not in present:
                roots.add(parent)
    return sorted(roots, key=len, reverse=True)


def module_name(path: str, roots: list[str]) -> str:
    for root in roots:
        prefix = f"{root}/" if root else ""
        if path.startswith(prefix):
            mod = path[len(prefix):-3].replace("/", ".")
            return mod[: -len(".__init__")] if mod.endswith(".__init__") else mod
    return path[:-3].replace("/", ".")


def parse_python(root: Path, path: str, module: str, *, collect_bodies: bool = True) -> PyInfo:
    info = PyInfo(module=module)
    try:
        text = read_source(root / path)
    except OSError as exc:
        info.parse_error = str(exc)
        return info
    info.loc = sum(1 for line in text.splitlines() if line.strip() and not line.strip().startswith("#"))
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        info.parse_error = f"SyntaxError: {exc.msg} line {exc.lineno}"
        return info
    package = module if path.endswith("__init__.py") else module.rpartition(".")[0]

    def remember_body(symbol: str, fn: ast.AST) -> None:
        if not collect_bodies:
            return
        body = list(fn.body)
        if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
                and isinstance(body[0].value.value, str):
            body = body[1:]                                   # a docstring is not behavior
        size = sum(1 for stmt in body for _ in ast.walk(stmt))
        if size >= MIN_DUP_NODES:
            # Rename only lexical locals. Attributes, constants and global callees
            # retain their names so different external operations never collapse.
            local_names = [arg.arg for arg in (*fn.args.posonlyargs, *fn.args.args, *fn.args.kwonlyargs)]
            local_names += [a.arg for a in (fn.args.vararg, fn.args.kwarg) if a]
            local_names += [n.id for stmt in body for n in ast.walk(stmt)
                            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)]
            globals_ = {name for stmt in body for n in ast.walk(stmt)
                        if isinstance(n, (ast.Global, ast.Nonlocal)) for name in n.names}
            replacements = {name: f"_local{i}" for i, name in enumerate(dict.fromkeys(local_names))
                            if name not in globals_}
            class LocalNames(ast.NodeTransformer):
                def visit_Name(self, node):
                    return ast.copy_location(ast.Name(replacements.get(node.id, node.id), node.ctx), node)
            normalized = [LocalNames().visit(copy.deepcopy(stmt)) for stmt in body]
            dump = "\n".join(ast.dump(stmt, annotate_fields=False) for stmt in normalized)
            info.bodies.append([symbol, sha256_bytes(dump.encode())[:16], size])

    module_nodes = list(tree.body)
    cursor = 0
    while cursor < len(module_nodes):
        node = module_nodes[cursor]
        cursor += 1
        if isinstance(node, (ast.If, ast.Try, ast.With)):
            module_nodes.extend(node.body)
            module_nodes.extend(getattr(node, "orelse", []))
            module_nodes.extend(getattr(node, "finalbody", []))
            for handler in getattr(node, "handlers", []):
                module_nodes.extend(handler.body)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            info.symbols.add(node.name)
            remember_body(node.name, node)
        elif isinstance(node, ast.ClassDef):
            info.symbols.add(node.name)
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    info.symbols.add(f"{node.name}.{sub.name}")
                    remember_body(f"{node.name}.{sub.name}", sub)
        elif isinstance(node, ast.Assign):
            info.symbols.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            info.symbols.add(node.target.id)

    if any(isinstance(n, ast.FunctionDef) and n.name == "__getattr__" for n in tree.body):
        for node in tree.body:
            value = node.value if isinstance(node, (ast.Assign, ast.AnnAssign)) else None
            if not isinstance(value, ast.Dict):
                continue
            for key, val in zip(value.keys, value.values):
                if not isinstance(key, ast.Constant) or not isinstance(key.value, str):
                    continue
                if isinstance(val, (ast.Tuple, ast.List)):
                    for name in val.elts:
                        if isinstance(name, ast.Constant) and isinstance(name.value, str):
                            info.lazy_exports[name.value] = key.value
                elif isinstance(val, ast.Constant) and isinstance(val.value, str):
                    info.lazy_exports[key.value] = val.value
    module_aliases: dict[str, str] = {}
    stack: list[ast.AST] = [tree]          # one traversal; "if TYPE_CHECKING:" imports are not runtime deps
    while stack:
        node = stack.pop()
        if isinstance(node, ast.If):
            test = node.test
            if (test.attr if isinstance(test, ast.Attribute) else getattr(test, "id", "")) == "TYPE_CHECKING":
                stack.extend(node.orelse)
                continue
        if isinstance(node, ast.Import):
            info.imports.update(alias.name for alias in node.names)
            for alias in node.names:
                module_aliases[alias.asname or alias.name.split(".")[0]] = alias.name if alias.asname else alias.name.split(".")[0]
                info.import_lines[alias.name] = node.lineno
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                parts = package.split(".") if package else []
                parts = parts[: len(parts) - (node.level - 1)] if node.level > 1 else parts
                base = ".".join(parts)
                target = f"{base}.{node.module}" if node.module and base else (node.module or base)
            else:
                target = node.module or ""
            if target:
                info.imports.update(f"{target}:{alias.name}" for alias in node.names)
                for alias in node.names:
                    info.import_lines[f"{target}:{alias.name}"] = node.lineno
        else:
            stack.extend(ast.iter_child_nodes(node))
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            info.string_literals.add(node.value)
        if isinstance(node, ast.Call) and (getattr(node.func, "id", "") or getattr(node.func, "attr", "")) in {"__import__", "import_module"}:
            info.dynamic_imports = True
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in module_aliases:
            info.imports.add(f"{module_aliases[node.value.id]}:{node.attr}")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"getattr", "hasattr"} \
                and node.args and isinstance(node.args[0], ast.Name) and node.args[0].id in module_aliases:
            info.imports.add(f"{module_aliases[node.args[0].id]}:*")
    return info


def resolve_import(imp: str, mod_to_path: dict[str, str], lazy: dict[str, dict[str, str]] | None = None) -> str | None:
    """'a.b' -> module a.b or its nearest package; 'a:b' -> submodule a.b if it exists, else a."""
    if ":" in imp:
        base, name = imp.split(":", 1)
        owner = (lazy or {}).get(base, {}).get(name)
        if owner in mod_to_path:
            return mod_to_path[owner]
        return mod_to_path.get(f"{base}.{name}") or mod_to_path.get(base)
    parts = imp.split(".")
    while parts:
        hit = mod_to_path.get(".".join(parts))
        if hit:
            return hit
        parts.pop()
    return None


def js_imports(root: Path, path: str, files_set: set[str]) -> set[str]:
    """Relative imports/requires of a JS/TS file, resolved to repo files."""
    try:
        text = read_source(root / path)
    except OSError:
        return set()
    found = set()
    for spec in JS_IMPORT.findall(text):
        cand = os.path.normpath(str(Path(path).parent / spec)).replace("\\", "/")
        for suffix in ("", ".ts", ".tsx", ".js", ".jsx", ".mjs", "/index.ts", "/index.tsx", "/index.js"):
            if cand + suffix in files_set:
                found.add(cand + suffix)
                break
    return found


def _read_cache(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("files", {}) if data.get("schema") == CACHE_SCHEMA and data.get("parser") == PARSER_ID else {}
    except (OSError, ValueError):
        return {}


def build_inventory(root: Path, ignore: list[str]) -> Inventory:
    files = [f for f in list_files(root) if not matches_any(f, ignore)]
    files_set = set(files)
    source = [f for f in files if Path(f).suffix in SOURCE_EXTS]
    tests = [f for f in source if is_test_file(f)]
    py_files = [f for f in source if f.endswith(".py")]
    roots = python_roots(py_files)
    cache_path = cache_dir(root) / "inventory.json"
    old, new = _read_cache(cache_path), {}
    py: dict[str, PyInfo] = {}
    mod_to_path: dict[str, str] = {}
    now_ns = time.time_ns()
    for f in py_files:
        module = module_name(f, roots)
        try:
            st = (root / f).stat()
            key = [st.st_size, st.st_mtime_ns, module] if now_ns - st.st_mtime_ns > RACY_NS else None
        except OSError:
            key = None
        hit = old.get(f)
        if key is not None and hit and hit.get("key") == key:
            info = PyInfo(module, set(hit["symbols"]), set(hit["imports"]), hit["loc"], hit["parse_error"], hit["bodies"],
                          hit["lazy_exports"], set(hit["string_literals"]), hit["dynamic_imports"], hit["import_lines"])
        else:
            info = parse_python(root, f, module)
        if key is not None:
            new[f] = {"key": key, "symbols": sorted(info.symbols), "imports": sorted(info.imports),
                      "loc": info.loc, "parse_error": info.parse_error, "bodies": info.bodies,
                      "lazy_exports": info.lazy_exports, "string_literals": sorted(info.string_literals),
                      "dynamic_imports": info.dynamic_imports, "import_lines": info.import_lines}
        py[f] = info
        mod_to_path[module] = f
    if new != old or not cache_path.is_file():
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps({"schema": CACHE_SCHEMA, "parser": PARSER_ID, "files": new}), encoding="utf-8")
        except OSError:
            pass                                  # read-only checkout: run without cache
    deps: dict[str, set[str]] = defaultdict(set)
    loc: dict[str, int] = {}
    lazy = {info.module: info.lazy_exports for info in py.values() if info.lazy_exports}
    for f, info in py.items():
        loc[f] = info.loc
        here = f.rpartition("/")[0]
        script_dir = bool(here) and f"{here}/__init__.py" not in files_set
        for imp in info.imports:
            target = resolve_import(imp, mod_to_path, lazy)
            if target is None and script_dir:          # a script imports a sibling through sys.path[0]
                head = imp.split(":", 1)[0].split(".", 1)[0]
                target = next((p for p in (f"{here}/{head}.py", f"{here}/{head}/__init__.py") if p in py), None)
            if target and target != f:
                deps[f].add(target)
            if ":" in imp:
                base, name = imp.split(":", 1)
                if name in {"*", "__all__"}:
                    deps[f].update(mod_to_path[module] for module in set(lazy.get(base, {}).values())
                                   if module in mod_to_path and mod_to_path[module] != f)
    for f in source:
        if f in py:
            continue
        try:
            loc[f] = sum(1 for line in read_source(root / f).splitlines() if line.strip())
        except OSError:
            loc[f] = 0
        if Path(f).suffix in JS_EXTS:
            deps[f] |= js_imports(root, f, files_set)
    dynamic_files = {f for f, info in py.items() if info.dynamic_imports and not info.lazy_exports}
    for f in source:
        if Path(f).suffix in JS_EXTS:
            text = read_source(root / f)
            # Static npm imports are external dependencies, not dynamic imports.
            if re.search(r"\bimport\s*\(\s*(?!['\"])", text):
                dynamic_files.add(f)
    return Inventory(root, files, source, tests, py, dict(deps), loc, dynamic_files=dynamic_files)
