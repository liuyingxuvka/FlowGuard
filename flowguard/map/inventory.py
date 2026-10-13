"""Repository inventory: files, Python symbols/imports/duplicate fingerprints, JS imports.

Parse results are cached in .flowguard/cache/inventory.json keyed by
(size, mtime_ns, module).  The cache is a speed-up only, never authority:
deleting .flowguard/cache/ is always safe.
"""

from __future__ import annotations

import ast
import json
import os
import re
import subprocess
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .common import CACHE_RELDIR, JS_EXTS, SOURCE_EXTS, is_test_file, matches_any, norm, sha256_bytes

CACHE_SCHEMA = "flowguard.map.inventory_cache.v1"
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


@dataclass
class Inventory:
    root: Path
    files: list[str]                  # every non-ignored file
    source: list[str]                 # files with a source extension (includes tests)
    tests: list[str]                  # source files that look like tests
    py: dict[str, PyInfo]             # path -> parse result
    file_deps: dict[str, set[str]]    # path -> repo paths it imports at runtime
    loc: dict[str, int]


def list_files(root: Path) -> list[str]:
    """Tracked plus untracked-but-not-ignored files (git); os.walk when git is unavailable."""
    try:
        out = subprocess.run(["git", "-C", str(root), "ls-files", "-co", "--exclude-standard"],
                             capture_output=True, text=True, check=True).stdout
        return sorted(f for f in (norm(x) for x in out.splitlines() if x.strip()) if (root / f).is_file())
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


def parse_python(root: Path, path: str, module: str) -> PyInfo:
    info = PyInfo(module=module)
    try:
        text = (root / path).read_text(encoding="utf-8", errors="replace")
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
        body = list(fn.body)
        if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
                and isinstance(body[0].value.value, str):
            body = body[1:]                                   # a docstring is not behavior
        size = sum(1 for stmt in body for _ in ast.walk(stmt))
        if size >= MIN_DUP_NODES:
            dump = "\n".join(ast.dump(stmt, annotate_fields=False) for stmt in body)
            info.bodies.append([symbol, sha256_bytes(dump.encode())[:16], size])

    for node in tree.body:
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
        else:
            stack.extend(ast.iter_child_nodes(node))
    return info


def resolve_import(imp: str, mod_to_path: dict[str, str]) -> str | None:
    """'a.b' -> module a.b or its nearest package; 'a:b' -> submodule a.b if it exists, else a."""
    if ":" in imp:
        base, name = imp.split(":", 1)
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
        text = (root / path).read_text(encoding="utf-8", errors="replace")
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
        return data.get("files", {}) if data.get("schema") == CACHE_SCHEMA else {}
    except (OSError, ValueError):
        return {}


def build_inventory(root: Path, ignore: list[str]) -> Inventory:
    files = [f for f in list_files(root) if not matches_any(f, ignore)]
    files_set = set(files)
    source = [f for f in files if Path(f).suffix in SOURCE_EXTS]
    tests = [f for f in source if is_test_file(f)]
    py_files = [f for f in source if f.endswith(".py")]
    roots = python_roots(py_files)
    cache_path = root / CACHE_RELDIR / "inventory.json"
    old, new = _read_cache(cache_path), {}
    py: dict[str, PyInfo] = {}
    mod_to_path: dict[str, str] = {}
    for f in py_files:
        module = module_name(f, roots)
        try:
            st = (root / f).stat()
            key = [st.st_size, st.st_mtime_ns, module]
        except OSError:
            key = None
        hit = old.get(f)
        if key is not None and hit and hit.get("key") == key:
            info = PyInfo(module, set(hit["symbols"]), set(hit["imports"]), hit["loc"], hit["parse_error"], hit["bodies"])
        else:
            info = parse_python(root, f, module)
        if key is not None:
            new[f] = {"key": key, "symbols": sorted(info.symbols), "imports": sorted(info.imports),
                      "loc": info.loc, "parse_error": info.parse_error, "bodies": info.bodies}
        py[f] = info
        mod_to_path[module] = f
    if new != old:
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps({"schema": CACHE_SCHEMA, "files": new}), encoding="utf-8")
        except OSError:
            pass                                  # read-only checkout: run without cache
    deps: dict[str, set[str]] = defaultdict(set)
    loc: dict[str, int] = {}
    for f, info in py.items():
        loc[f] = info.loc
        for imp in info.imports:
            target = resolve_import(imp, mod_to_path)
            if target and target != f:
                deps[f].add(target)
    for f in source:
        if f in py:
            continue
        try:
            loc[f] = sum(1 for line in (root / f).read_text(encoding="utf-8", errors="replace").splitlines() if line.strip())
        except OSError:
            loc[f] = 0
        if Path(f).suffix in JS_EXTS:
            deps[f] |= js_imports(root, f, files_set)
    return Inventory(root, files, source, tests, py, dict(deps), loc)
