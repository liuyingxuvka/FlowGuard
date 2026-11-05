"""The installed package has one model engine and every advertised CLI is usable."""

from __future__ import annotations

import ast
import json
import errno
import io
import os
import shutil
import subprocess
import sys
import zipfile

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


def test_wheel_contains_one_engine_and_executes_native_capture(tmp_path):
    """Removed pilot sources cannot leak in through a stale build manifest.
    The flow/native engine ships together with the files it opens besides its code.

    An earlier editable install leaves flowguard.egg-info/SOURCES.txt behind and
    setuptools reads it back on every build, so the stand-in below lists every
    package source file the way such a stale list does.
    """
    source = tmp_path / "source"
    shutil.copytree(ROOT / "flowguard", source / "flowguard", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy2(ROOT / "pyproject.toml", source / "pyproject.toml")
    (source / "flowguard/_next/draft").mkdir(parents=True)
    for name in ("__init__.py", "draft/__init__.py"):
        (source / "flowguard/_next" / name).write_text("", encoding="utf-8")
    (source / "flowguard.egg-info").mkdir()
    (source / "flowguard.egg-info/SOURCES.txt").write_text(
        "".join(path.relative_to(source).as_posix() + "\n" for path in sorted((source / "flowguard").rglob("*.py"))),
        encoding="utf-8")
    built = subprocess.run(
        [sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation", "--no-index",
         "--disable-pip-version-check", "-q", "-w", str(tmp_path / "dist"), str(source)],
        capture_output=True, text=True)
    assert built.returncode == 0, built.stdout + built.stderr
    (wheel,) = (tmp_path / "dist").glob("flowguard-*.whl")
    with zipfile.ZipFile(wheel) as package:
        names = package.namelist()
        package.extractall(tmp_path / "site")
        assert package.read("flowguard/flow/HOWTO.md")== (ROOT/"flowguard/flow/HOWTO.md").read_bytes()
    assert "flowguard/map/runner.py" in names
    flow_data = ["HOWTO.md", "render.js", "vendor/mermaid.min.js", "vendor/MERMAID-LICENSE"]
    assert [name for name in flow_data if "flowguard/flow/" + name not in names] == []
    assert "flowguard/flow/cli.py" in names
    shipped = [name for name in names if name.startswith(("flowguard/behave/", "flowguard/_next/"))
               or name in {"flowguard/map/jobs.py", "flowguard/map/inputs.py"}]
    assert shipped == []
    probe = subprocess.run(
        [sys.executable, "-I", "-S", "-c", "import sys; sys.path.insert(0, sys.argv[1]); import flowguard.behave",
         str(tmp_path / "site")], capture_output=True, text=True)
    assert probe.returncode == 1 and "No module named 'flowguard.behave'" in probe.stderr, probe.stderr
    (tmp_path/'sut').mkdir()
    (tmp_path/'sut/program.py').write_text('class Program:\n    def __init__(self): self.value=0\n    def add(self,amount):\n        self.value+=amount\n        return self.value\n')
    code = """import importlib.util,json,sys
sys.path.insert(0,sys.argv[1])
from flowguard.flow import Model
from flowguard.native.session import replay
for name in ('behave','_next','core','workflow','explorer','validator','ui_flow'):
    assert importlib.util.find_spec('flowguard.'+name) is None,name
result=replay(dict(root=sys.argv[2],system='program:Program',classes=['program:Program'],capture_shape={'wire':2,'queries':{}}),[dict(name='add',args=[3])])
assert result['steps'][0]['outcome']=='success'
assert result['steps'][0]['value']['root']==3
assert result['rule_captures']['native_evidence']['status']=='current'
from flowguard.__main__ import main
assert main(['--help'])==0
print('installed native capture passed')
"""
    captured=subprocess.run([sys.executable,'-I','-S','-c',code,str(tmp_path/'site'),str(tmp_path/'sut')],
                            capture_output=True,text=True,timeout=30)
    assert captured.returncode==0,captured.stdout+captured.stderr
    assert captured.stdout.strip().endswith('installed native capture passed')
    assert 'python -m flowguard check' in captured.stdout
    assert 'python -m flowguard map' not in captured.stdout
    assert 'python -m flowguard target' not in captured.stdout



@pytest.mark.parametrize("command", [("where",), ("status",), ("release",), ("check",)])
@pytest.mark.parametrize("read_first", [False, True])
def test_cli_closed_output_pipe_is_quiet(tmp_path, command, read_first):
    directory = tmp_path / ".flowguard"
    directory.mkdir()
    (tmp_path/'app.py').write_text('def run(): return 1\n')
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



def test_top_help_advertises_only_current_commands(capsys):
    from flowguard.__main__ import main,VERB_PURPOSE
    assert main(['--help'])==0
    output=capsys.readouterr()
    assert not output.err
    for verb in VERB_PURPOSE:
        assert f'python -m flowguard {verb}' in output.out
    assert 'python -m flowguard map' not in output.out
    assert 'python -m flowguard target' not in output.out


@pytest.mark.parametrize('command',['map','target','read','change'])
def test_retired_console_commands_are_refused(command,capsys):
    from flowguard.__main__ import main
    assert main([command])==2
    output=capsys.readouterr()
    assert f"unknown command {command!r}" in output.err


def test_source_views_are_mutually_exclusive():
    from flowguard.__main__ import _verb_parser
    with pytest.raises(SystemExit) as error:
        _verb_parser('where').parse_args(['--flow','--text'])
    assert error.value.code==2
