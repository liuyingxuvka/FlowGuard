"""Regression checks for console commands that delegate to executable examples."""

from __future__ import annotations

import ast
from pathlib import Path
import tomllib

from setuptools import find_packages


ROOT = Path(__file__).resolve().parents[1]


def _console_example_packages() -> set[str]:
    tree = ast.parse(
        (ROOT / "flowguard" / "__main__.py").read_text(encoding="utf-8")
    )
    packages: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        if not node.module.startswith("examples."):
            continue
        packages.add(node.module.rsplit(".", 1)[0])
    return packages


def test_wheel_configuration_includes_every_console_example_package() -> None:
    """A clean wheel must not advertise a CLI that imports source-only modules."""

    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    include = tuple(
        metadata["tool"]["setuptools"]["packages"]["find"]["include"]
    )
    assert "examples*" not in include
    assert not _console_example_packages()

    discovered = set(find_packages(where=str(ROOT), include=include))
    assert _console_example_packages() <= discovered
