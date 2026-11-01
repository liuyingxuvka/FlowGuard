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
