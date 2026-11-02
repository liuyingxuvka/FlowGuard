"""The package rules: standard library only, relative imports inside the package, nothing
from the rest of flowguard, and nothing named `machine` (the golden test supplies it)."""
from __future__ import annotations

import ast
import sys
from pathlib import Path

PKG = Path(__file__).parents[2] / "flowguard" / "flow"


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
    import flowguard.flow as nxt
    assert nxt.__all__ == ["Model", "need"]


# ---------------------------------------------------------------------- package data (G9)
# pyproject.toml lists the files of flowguard.flow that are not Python; a wheel leaves out
# any other. tests/test_packaged_cli_surface.py builds the wheel and looks for them.
PACKAGE_DATA = ["HOWTO.md", "render.js", "vendor/mermaid.min.js", "vendor/MERMAID-LICENSE"]


def _data_files():
    return sorted(p.relative_to(PKG).as_posix() for p in PKG.rglob("*")
                  if p.is_file() and p.suffix not in (".py", ".pyc") and "__pycache__" not in p.parts)


def test_every_file_the_engine_needs_besides_code_is_listed_for_the_wheel():
    """G9: the picture renderer, the vendored Mermaid (with its licence) and the HOWTO are
    not Python files, so a wheel leaves them out unless package-data lists them. Every such
    file of the package is matched by the planned entry, and the ones the engine opens at
    run time exist where it opens them."""
    from fnmatch import fnmatch
    from flowguard.flow import diagram
    for rel in _data_files():
        assert any(fnmatch(rel, pattern) for pattern in PACKAGE_DATA), f"{rel} is not in the planned package-data"
    for pattern in PACKAGE_DATA:
        assert list(PKG.glob(pattern)), f"{pattern} matches no file of the package"
    for used in (diagram.RENDER_JS, diagram.MERMAID_JS, PKG / "HOWTO.md"):
        assert used.is_file() and used.relative_to(PKG).as_posix() in PACKAGE_DATA


def test_pyproject_lists_exactly_the_data_files_of_the_package():
    import tomllib
    config = tomllib.loads((PKG.parents[1] / "pyproject.toml").read_text(encoding="utf-8"))
    listed = config["tool"]["setuptools"]["package-data"]["flowguard.flow"]
    assert sorted(listed) == sorted(PACKAGE_DATA)
