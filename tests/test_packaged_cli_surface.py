"""Regression checks for console commands that delegate to executable examples."""

from __future__ import annotations

import ast
import json
import errno
import io
import subprocess
import sys

import pytest
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


@pytest.mark.parametrize("command", [("read",), ("change",), ("release",), ("map", "show")])
@pytest.mark.parametrize("read_first", [False, True])
def test_cli_closed_output_pipe_is_quiet(tmp_path, command, read_first):
    directory = tmp_path / ".flowguard"
    directory.mkdir()
    (directory / "map.json").write_text(json.dumps({
        "schema": "flowguard.map.v1", "project": "empty", "components": []}))
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                    "commit", "-qm", "fixture"], check=True)
    args = [command[0], "--root", str(tmp_path), *command[1:]]
    proc = subprocess.Popen([sys.executable, "-m", "flowguard", *args], cwd=ROOT,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if read_first:
        proc.stdout.readline()
    proc.stdout.close()
    stderr = proc.stderr.read().decode()
    assert proc.wait(timeout=30) == 0, stderr
    assert "BrokenPipeError" not in stderr


@pytest.mark.parametrize("operation", ["write", "flush"])
def test_windows_stdout_einval_is_a_closed_pipe(monkeypatch, operation):
    from flowguard.map.common import quiet_broken_pipe

    class ClosedOutput(io.StringIO):
        def write(self, text):
            if operation == "write":
                raise OSError(errno.EINVAL, "closed Windows pipe")
            return super().write(text)

        def flush(self):
            if operation == "flush":
                raise OSError(errno.EINVAL, "closed Windows pipe")
            return super().flush()

    with monkeypatch.context() as patch:
        patch.setattr(sys, "platform", "win32")
        patch.setattr(sys, "stdout", ClosedOutput())
        assert quiet_broken_pipe(lambda: print("output"))() == 0


def test_quiet_pipe_does_not_swallow_command_einval(monkeypatch):
    from flowguard.map.common import quiet_broken_pipe

    def command():
        raise OSError(errno.EINVAL, "invalid filesystem operation")

    with monkeypatch.context() as patch:
        patch.setattr(sys, "platform", "win32")
        patch.setattr(sys, "stdout", io.StringIO())
        with pytest.raises(OSError, match="invalid filesystem"):
            quiet_broken_pipe(command)()


def test_read_budget_option_matches_map_show(tmp_path):
    """`read --budget N` is the same budget as `map show --budget N`; tiny budgets are refused."""
    directory = tmp_path / ".flowguard"
    directory.mkdir()
    components = [{"id": f"part{index}", "summary": "Serve part " * 20, "responsibilities": ["serve"],
                   "files": [f"part{index}.py"], "status": "draft", "fingerprint": "", "layer": ""}
                  for index in range(12)]
    for index in range(12):
        (tmp_path / f"part{index}.py").write_text("def run():\n    return True\n", encoding="utf-8")
    (directory / "map.json").write_text(json.dumps({
        "schema": "flowguard.map.v1", "project": "budget", "components": components}), encoding="utf-8")

    def run(*args):
        return subprocess.run([sys.executable, "-m", "flowguard", *args, "--root", str(tmp_path)],
                              cwd=ROOT, capture_output=True, text=True, encoding="utf-8")

    read = run("read", "--budget", "3000")
    shown = run("map", "show", "--budget", "3000")
    assert read.returncode == 0 and shown.returncode == 0, read.stderr + shown.stderr
    assert len(read.stdout.rstrip("\n")) <= 3000
    assert read.stdout == shown.stdout
    assert run("read", "--budget", "100").returncode == 2
