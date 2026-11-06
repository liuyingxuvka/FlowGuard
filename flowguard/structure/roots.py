"""Import roots and module names (C-1).

Roots come from, in this order of trust: [tool.flowguard] roots, each package's own
pyproject.toml (with its src/ layout), pytest `pythonpath`, literal sys.path.insert/append
calls, and the 1.x `python_roots` (repository root plus the parent of every top-level
package). A file's primary name comes from the deepest root that holds it; a file under a
second detected root gets a second name, and the store links the two with an `alias` edge.
"""
from __future__ import annotations

import ast
import configparser
import posixpath
import tomllib
from pathlib import Path

from flowguard.map.inventory import python_roots

CONFIGS = ("pyproject.toml", "pytest.ini", "setup.cfg", "tox.ini")
PATH_FUNCS = {"abspath", "realpath", "normpath", "str", "fspath", "Path", "PurePath", "resolve", "absolute",
              "expanduser"}


def _toml(root: Path, rel: str) -> dict:
    try:
        return tomllib.loads((root / rel).read_text(encoding="utf-8-sig"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def _norm(base: str, value: str) -> str | None:
    """A repository-relative directory, or None when it leaves the repository or is absolute."""
    if value.startswith("/"):
        return None
    path = posixpath.normpath(posixpath.join(base, value)) if base else posixpath.normpath(value)
    path = "" if path == "." else path
    return None if path == ".." or path.startswith("../") else path


def config_roots(root: Path, files: list[str]) -> list[tuple[str, str]]:
    """Roots that configuration files declare: [(directory, how)]."""
    out = []
    top = _toml(root, "pyproject.toml") if "pyproject.toml" in files else {}
    for value in top.get("tool", {}).get("flowguard", {}).get("roots", []):
        if (path := _norm("", str(value))) is not None:
            out.append((path, "[tool.flowguard] roots"))
    for rel in files:
        name = posixpath.basename(rel)
        if name not in CONFIGS:
            continue
        base = posixpath.dirname(rel)
        if name == "pyproject.toml":
            data = top if rel == "pyproject.toml" else _toml(root, rel)
            tool = data.get("tool", {})
            where = tool.get("setuptools", {}).get("packages", {})
            where = where.get("find", {}).get("where", []) if isinstance(where, dict) else []
            dirs = list(where) + list(tool.get("setuptools", {}).get("package-dir", {}).values())
            dirs += [p["from"] for p in tool.get("poetry", {}).get("packages", []) if isinstance(p, dict) and "from" in p]
            if not dirs and any(f.startswith(posixpath.join(base, "src") + "/") and f.endswith("/__init__.py") for f in files):
                dirs = ["src"]
            if base and not dirs:
                out.append((base, f"{rel} (package root)"))
            for d in dirs:
                if (path := _norm(base, str(d))) is not None:
                    out.append((path, f"{rel} (package directory {d})"))
            pythonpath = tool.get("pytest", {}).get("ini_options", {}).get("pythonpath", [])
            for value in pythonpath.split() if isinstance(pythonpath, str) else pythonpath:
                if (path := _norm(base, str(value))) is not None:
                    out.append((path, f"pytest pythonpath in {rel}"))
            continue
        parser = configparser.ConfigParser(interpolation=None)
        try:
            parser.read_string((root / rel).read_text(encoding="utf-8-sig"))
        except (OSError, configparser.Error):
            continue
        section = "tool:pytest" if name == "setup.cfg" else "pytest"
        for value in parser.get(section, "pythonpath", fallback="").split():
            if (path := _norm(base, value)) is not None:
                out.append((path, f"pytest pythonpath in {rel}"))
    return out


def _path_value(node, here: str, env: dict, depth: int = 0) -> str | None:
    """Evaluate a path expression built from __file__ and literals: os.path.join(dirname(__file__), '..'),
    Path(__file__).resolve().parents[1] / 'src', str(ROOT / 'lib'). Returns a repo-relative path."""
    if depth > 12:
        return None
    rec = lambda n: _path_value(n, here, env, depth + 1)
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        if node.id == "__file__":
            return here
        return rec(env[node.id]) if node.id in env else None
    if isinstance(node, ast.Attribute) and node.attr == "parent":
        inner = rec(node.value)
        return posixpath.dirname(inner) if inner is not None else None
    if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Attribute) and node.value.attr == "parents" \
            and isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, int):
        inner = rec(node.value.value)
        for _ in range(node.slice.value + 1 if inner is not None else 0):
            inner = posixpath.dirname(inner)
        return inner
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        left, right = rec(node.left), rec(node.right)
        return posixpath.join(left, right) if left is not None and right is not None else None
    if isinstance(node, ast.Call):
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else ""
        if name == "dirname" and node.args:
            inner = rec(node.args[0])
            return posixpath.dirname(inner) if inner is not None else None
        if name == "join" and node.args:
            parts = [rec(a) for a in node.args]
            return posixpath.join(*parts) if all(p is not None for p in parts) else None
        if name in PATH_FUNCS:
            target = node.args[0] if node.args else func.value if isinstance(func, ast.Attribute) else None
            return rec(target) if target is not None else None
    return None


def syspath_entries(tree: ast.AST, rel: str) -> list[tuple[int, str]]:
    """Literal sys.path.insert/append/extend and site.addsitedir calls of one file: [(line, directory)]."""
    env, out = {}, []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            env.setdefault(node.targets[0].id, node.value)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        owner = ast.unparse(node.func.value)
        args = []
        if owner == "sys.path" and node.func.attr in ("insert", "append") and node.args:
            args = [node.args[-1]]
        elif owner == "sys.path" and node.func.attr == "extend" and node.args and isinstance(node.args[0], (ast.List, ast.Tuple)):
            args = list(node.args[0].elts)
        elif owner == "site" and node.func.attr == "addsitedir" and node.args:
            args = [node.args[0]]
        for arg in args:
            value = _path_value(arg, rel, env)
            if value is not None and (path := _norm("", value)) is not None:
                out.append((node.lineno, path))
    return out


def detect(root: Path, files: list[str], py_files: list[str], syspath: dict[str, list]) -> list[tuple[str, str]]:
    """All roots, deepest first: [(directory, how)]; the first `how` found for a directory is kept."""
    found: dict[str, str] = {}
    for path, how in config_roots(root, files):
        found.setdefault(path, how)
    for rel, entries in sorted(syspath.items()):
        for line, path in entries:
            found.setdefault(path, f"sys.path in {rel}:{line}")
    for path in python_roots(py_files):
        found.setdefault(path, "repository root" if path == "" else f"parent of a top-level package in {path}/")
    dirs = {posixpath.dirname(f) for f in py_files}
    kept = {p: h for p, h in found.items() if p == "" or any(d == p or d.startswith(p + "/") for d in dirs)}
    return sorted(kept.items(), key=lambda kv: (-len(kv[0]), kv[0]))


def _name_under(rel: str, root: str) -> str | None:
    prefix = root + "/" if root else ""
    if not rel.startswith(prefix):
        return None
    mod = rel[len(prefix):-3].replace("/", ".")
    mod = mod[:-len(".__init__")] if mod.endswith(".__init__") else ("" if mod == "__init__" else mod)
    return mod if mod and all(part.isidentifier() for part in mod.split(".")) else None


IMPLICIT = ("repository root", "parent of a top-level")


def installed_tops(tops, root: Path) -> set[str]:
    """Top-level names that an interpreter path outside the repository provides (the standard library,
    site-packages): a package of that name under an implicit root is most likely not what `import` finds."""
    import importlib.machinery
    import sys
    base = str(root.resolve())
    outside = [p for p in sys.path if p and not str(Path(p).resolve()).startswith(base)]
    out = set()
    for top in sorted(set(tops)):
        if top in sys.builtin_module_names or top in getattr(sys, "stdlib_module_names", ()):
            out.add(top)
            continue
        try:
            spec = importlib.machinery.PathFinder.find_spec(top, outside)
        except (ImportError, ValueError):   # a broken path entry finds nothing; the name stays the repo's
            spec = None
        if spec is not None:
            out.add(top)
    return out


def implicit_packages(py_files: list[str], roots: list[tuple[str, str]]) -> dict[str, set[str]]:
    """{implicit root: the top-level packages that made it a root}."""
    present = set(py_files)
    out = {}
    for r, how in roots:
        if r and how.startswith(IMPLICIT[1]):
            out[r] = {f[len(r) + 1:].split("/")[0] for f in present
                      if f.startswith(r + "/") and f.count("/") == r.count("/") + 2 and f.endswith("/__init__.py")}
    return out


def implicit_tops(py_files: list[str], roots: list[tuple[str, str]]) -> set[str]:
    """The top-level names an implicit package parent would give: its packages and its scripts."""
    packages = implicit_packages(py_files, roots)
    scripts = {f[len(r) + 1:-3] for r in packages for f in py_files
               if f.startswith(r + "/") and f.count("/") == r.count("/") + 1}
    return {t for ts in packages.values() for t in ts} | scripts


def names(py_files: list[str], roots: list[tuple[str, str]], shadowed: set[str] = frozenset()) \
        -> tuple[dict[str, list[tuple[str, str]]], dict[str, str], dict[str, list[str]]]:
    """({file: [(name, root)] primary first}, {every candidate name: file}, {name: files} for names that
    more than one file can have).

    Secondary names are kept only under roots that were detected (not the implicit repository root or
    package parents), so `src.pkg.mod` exists only when something says `src/..` is on the path; the
    store adds an alias for an implicit name when an import uses it. An implicit package parent names
    only the packages that made it a root and the scripts directly in it, not a namespace directory
    beside them (`tools/parity/x.py` stays `tools.parity.x` when `tools/flowguard/` is the package), and
    not a package whose name the interpreter finds outside the repository (`shadowed`). Two files that
    want the same primary name: the first in path order keeps it, the other falls back to its next name;
    `multi` lets the linker choose by importer."""
    explicit = {p for p, how in roots if not how.startswith(IMPLICIT)}
    packages = implicit_packages(py_files, roots)
    out, taken, every, multi = {}, {}, {}, {}

    def allowed(rel: str, r: str, n: str) -> bool:
        if r not in packages:
            return True
        rest = rel[len(r) + 1:]
        if "/" not in rest:                               # a script in the package parent
            return rest[:-3] not in shadowed
        top = rest.split("/")[0]
        return top in packages[r] and top not in shadowed
    for rel in sorted(py_files):
        cands = [(n, r) for r, _ in roots if (n := _name_under(rel, r)) and allowed(rel, r, n)]
        for n, r in cands:
            every.setdefault(n, rel)
            multi.setdefault(n, []).append(rel)
        chosen = [c for c in cands if c[0] not in taken] or [(rel[:-3].replace("/", "."), "")]
        primary = chosen[0]
        rest = [c for c in chosen[1:] if c[1] in explicit]
        for n, _ in [primary, *rest]:
            taken[n] = rel
        out[rel] = [primary, *rest]
    return out, every, {n: fs for n, fs in multi.items() if len(set(fs)) > 1}
