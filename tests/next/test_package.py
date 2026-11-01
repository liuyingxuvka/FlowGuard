"""The package rules: standard library only, relative imports inside the package, nothing
from the rest of flowguard, and nothing named `machine` (the golden test supplies it)."""
from __future__ import annotations

import ast
import sys
from pathlib import Path

PKG = Path(__file__).parents[2] / "flowguard" / "_next"


def modules():
    return sorted(PKG.rglob("*.py"))


def test_imports_are_relative_or_standard_library():
    for path in modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    assert a.name.split(".")[0] in sys.stdlib_module_names, (path.name, a.name)
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0:
                    assert node.module.split(".")[0] in sys.stdlib_module_names, (path.name, node.module)


def test_nothing_is_named_machine():
    for path in modules():
        assert "machine" not in path.stem
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.alias):
                assert "machine" not in (node.asname or node.name).lower(), path.name
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert node.value not in ("machine", "MACHINE", "MACHINES") or path.name == "model.py", path.name
    assert "machine" not in sys.modules or not getattr(sys.modules["machine"], "__file__", "").startswith(str(PKG))


def test_the_public_names():
    import flowguard._next as nxt
    assert nxt.__all__ == ["Model", "need"]


# ---------------------------------------------------------------------- package data (G9)
# The [tool.setuptools.package-data] entry the move-in adds to pyproject.toml when
# flowguard/_next becomes flowguard/flow (s1aplan/MOVE_IN.md has the same lines).
MOVED_NAME = "flowguard.flow"
PACKAGE_DATA = ["HOWTO.md", "render.js", "vendor/mermaid.min.js", "vendor/MERMAID-LICENSE"]
PYPROJECT_LINES = """[tool.setuptools.package-data]
"flowguard.flow" = ["HOWTO.md", "render.js", "vendor/mermaid.min.js", "vendor/MERMAID-LICENSE"]
"""


def _data_files():
    return sorted(p.relative_to(PKG).as_posix() for p in PKG.rglob("*")
                  if p.is_file() and p.suffix not in (".py", ".pyc") and "__pycache__" not in p.parts)


def test_every_file_the_engine_needs_besides_code_is_listed_for_the_wheel():
    """G9: the picture renderer, the vendored Mermaid (with its licence) and the HOWTO are
    not Python files, so a wheel leaves them out unless package-data lists them. Every such
    file of the package is matched by the planned entry, and the ones the engine opens at
    run time exist where it opens them."""
    from fnmatch import fnmatch
    from flowguard._next import diagram
    for rel in _data_files():
        assert any(fnmatch(rel, pattern) for pattern in PACKAGE_DATA), f"{rel} is not in the planned package-data"
    for pattern in PACKAGE_DATA:
        assert list(PKG.glob(pattern)), f"{pattern} matches no file of the package"
    for used in (diagram.RENDER_JS, diagram.MERMAID_JS, PKG / "HOWTO.md"):
        assert used.is_file() and used.relative_to(PKG).as_posix() in PACKAGE_DATA


def test_the_moved_package_has_its_data_in_pyproject():
    """Before the move-in the package is flowguard._next (kept out of the wheel); once it is
    flowguard.flow, pyproject.toml must carry exactly the planned package-data entry."""
    import tomllib
    import flowguard._next as pkg
    config = tomllib.loads((PKG.parents[1] / "pyproject.toml").read_text(encoding="utf-8"))
    listed = config.get("tool", {}).get("setuptools", {}).get("package-data", {}).get(MOVED_NAME)
    if pkg.__name__ == MOVED_NAME:
        assert sorted(listed or []) == sorted(PACKAGE_DATA)
    else:
        assert pkg.__name__ == "flowguard._next" and listed is None


def test_a_wheel_of_the_moved_package_carries_its_data(tmp_path):
    """The planned lines work: a wheel built from the package moved to flowguard/flow with
    them holds every data file (without them it holds none: the review's finding)."""
    import shutil
    import subprocess
    import zipfile
    import pytest
    pytest.importorskip("setuptools")
    src = tmp_path / "src"
    (src / "flowguard").mkdir(parents=True)
    (src / "flowguard" / "__init__.py").write_text("")
    shutil.copytree(PKG, src / "flowguard" / "flow", ignore=shutil.ignore_patterns("__pycache__"))
    head = ('[build-system]\nrequires = ["setuptools>=61"]\nbuild-backend = "setuptools.build_meta"\n\n'
            '[project]\nname = "flowguard"\nversion = "0.0.0"\n\n'
            '[tool.setuptools.packages.find]\ninclude = ["flowguard*"]\n\n')
    built = {}
    for name, extra in (("without", ""), ("with", PYPROJECT_LINES)):
        (src / "pyproject.toml").write_text(head + extra)
        for old in [src / "build", *src.glob("*.egg-info")]:
            shutil.rmtree(old, ignore_errors=True)
        dist = tmp_path / name
        res = subprocess.run([sys.executable, "-c", f"from setuptools import build_meta as b; b.build_wheel({str(dist)!r})"],
                             cwd=src, capture_output=True, text=True)
        assert res.returncode == 0, res.stderr[-2000:]
        built[name] = set(zipfile.ZipFile(next(dist.glob("*.whl"))).namelist())
    wanted = {f"flowguard/flow/{rel}" for rel in PACKAGE_DATA}
    assert wanted <= built["with"]
    assert not wanted & built["without"]
