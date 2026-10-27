"""Regression checks for console commands that delegate to executable examples."""

from __future__ import annotations

import ast
import json
import errno
import io
import os
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
        # Shortened lines end with "…"; read the child's output as UTF-8 on every platform.
        environment = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        return subprocess.run([sys.executable, "-m", "flowguard", *args, "--root", str(tmp_path)],
                              cwd=ROOT, capture_output=True, text=True, encoding="utf-8", env=environment)

    read = run("read", "--budget", "3000")
    shown = run("map", "show", "--budget", "3000")
    assert read.returncode == 0 and shown.returncode == 0, read.stderr + shown.stderr
    assert len(read.stdout.rstrip("\n")) <= 3000
    assert read.stdout == shown.stdout
    assert run("read", "--budget", "100").returncode == 2


def test_read_review_matches_map_show_review(tmp_path):
    """`read --review` is `map show --review`; it cannot be combined with the other views."""
    directory = tmp_path / ".flowguard"
    directory.mkdir()
    (tmp_path / "app.py").write_text("import store\ndef run():\n    return store.save()\n", encoding="utf-8")
    (tmp_path / "store.py").write_text("def save():\n    return True\n", encoding="utf-8")
    components = [{"id": cid, "summary": "Serve " + cid, "responsibilities": ["serve " + cid], "files": [cid + ".py"],
                   "status": "draft", "fingerprint": "", "layer": "", "depends_on": deps}
                  for cid, deps in (("app", ["store"]), ("store", []))]
    (directory / "map.json").write_text(json.dumps({
        "schema": "flowguard.map.v1", "project": "review", "components": components}), encoding="utf-8")

    def run(*args):
        environment = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        return subprocess.run([sys.executable, "-m", "flowguard", *args, "--root", str(tmp_path)],
                              cwd=ROOT, capture_output=True, text=True, encoding="utf-8", env=environment)

    read = run("read", "--review")
    shown = run("map", "show", "--review")
    assert read.returncode == 0 and shown.returncode == 0, read.stderr + shown.stderr
    assert read.stdout == shown.stdout
    assert read.stdout.startswith("# review review: 2 components") and "optimise next:" in read.stdout
    assert run("read", "--review", "--component", "app").returncode == 2
    assert run("map", "show", "--review", "--component", "app").returncode == 2


def _change_run_project(tmp_path):
    root = tmp_path / "proj"
    (root / ".flowguard").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "app.py").write_text("def run():\n    return True\n", encoding="utf-8")
    (root / "tests/test_app.py").write_text("from app import run\n\ndef test_run():\n    assert run()\n", encoding="utf-8")
    component = {"id": "app", "summary": "Runs the app", "responsibilities": ["run the app"], "files": ["app.py"],
                 "tests": ["tests/test_app.py"], "status": "draft", "fingerprint": "", "layer": "", "depends_on": []}
    (root / ".flowguard/map.json").write_text(json.dumps({
        "schema": "flowguard.map.v1", "project": "run", "test_command": "python -m pytest -q -p no:cacheprovider",
        "components": [component]}), encoding="utf-8")
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
    for arguments in (("init", "-q"), ("add", "."), ("commit", "-qm", "base")):
        subprocess.run([*git, *arguments], cwd=root, check=True, capture_output=True)
    return root


def _flowguard(root, *args):
    environment = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run([sys.executable, "-m", "flowguard", *args, "--root", str(root)], cwd=ROOT,
                          capture_output=True, text=True, encoding="utf-8", env=environment)


def test_change_run_runs_the_selected_checks(tmp_path):
    root = _change_run_project(tmp_path)
    (root / "app.py").write_text("def run():\n    return 1 == 1\n", encoding="utf-8")
    plain = _flowguard(root, "change")
    assert "run: python -m pytest" in plain.stdout and "RAN" not in plain.stdout, plain.stdout + plain.stderr
    ran = _flowguard(root, "change", "--run")
    assert ran.returncode == plain.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout.startswith(plain.stdout.rstrip("\n")) and any(line.startswith("RAN PASS ") and "s python -m pytest" in line for line in ran.stdout.splitlines()), ran.stdout
    (root / "tests/test_app.py").write_text("from app import run\n\ndef test_run():\n    assert not run()\n", encoding="utf-8")
    failed = _flowguard(root, "change", "--run")
    assert failed.returncode == 1 and any(line.startswith("RAN FAIL (exit 1) ") and "s python -m pytest" in line for line in failed.stdout.splitlines()), failed.stdout + failed.stderr
    assert "  " in failed.stdout.split("RAN FAIL", 1)[1]           # the failing output's tail is indented

    from contextlib import redirect_stdout,redirect_stderr
    from io import StringIO
    from flowguard.__main__ import main
    direct=StringIO()
    with redirect_stdout(direct),redirect_stderr(direct):
        code=main(['change','--root',str(root),'--run'])
    assert code==1 and 'RAN FAIL (exit 1)' in direct.getvalue(),direct.getvalue()


def test_change_run_skips_when_check_has_errors(tmp_path):
    root = _change_run_project(tmp_path)
    (root / "stray.py").write_text("def stray():\n    return 1\n", encoding="utf-8")
    (root / "app.py").write_text("def run():\n    return 1 == 1\n", encoding="utf-8")
    marker = root / "tests/test_app.py"
    marker.write_text("from pathlib import Path\nPath(__file__).with_name('ran.marker').write_text('ran')\n"
                      "def test_run():\n    pass\n", encoding="utf-8")
    ran = _flowguard(root, "change", "--run", "app.py", "stray.py")
    assert ran.returncode == 1 and "RAN: skipped (fix the errors above first)" in ran.stdout, ran.stdout + ran.stderr
    assert not (root / "tests/ran.marker").exists()

    from contextlib import redirect_stdout,redirect_stderr
    from io import StringIO
    from flowguard.__main__ import main
    direct=StringIO()
    with redirect_stdout(direct),redirect_stderr(direct):
        code=main(['change','--root',str(root),'--run','app.py','stray.py'])
    assert code==1 and 'RAN: skipped (fix the errors above first)' in direct.getvalue(),direct.getvalue()
    assert not (root / "tests/ran.marker").exists()


def test_template_writes_into_the_open_target(tmp_path, capsys):
    from flowguard.__main__ import main
    from flowguard.map.target import start_target
    start_target(tmp_path, "add a behaviour")
    assert main(["template", "behaviour", "--write", str(tmp_path)]) == 0
    assert not (tmp_path / ".flowguard/models").exists()
    assert list((tmp_path / ".flowguard/target/models").glob("*.py"))
    assert "(into the open target)" in capsys.readouterr().out


def test_change_run_ends_with_map_confirm_for_stale_components(tmp_path, capsys):
    from flowguard.__main__ import main
    directory = tmp_path / ".flowguard"
    directory.mkdir()
    path = tmp_path / "app.py"
    path.write_text("def answer(): return 1\n")
    (directory / "map.json").write_text(json.dumps({"schema": "flowguard.map.v1", "components": [{
        "id": "app", "summary": "Compute an answer", "responsibilities": ["compute answers"],
        "files": ["app.py"], "tests": [], "models": [], "status": "draft"}]}))
    assert main(["map", "confirm", "app", "--root", str(tmp_path)]) == 0
    path.write_text("def answer(): return 2\n")
    assert main(["change", "--root", str(tmp_path), "app.py", "--run"]) == 0
    assert capsys.readouterr().out.rstrip().endswith("next: python -m flowguard map confirm app")


def test_find_unknown_symbol_exits_one(tmp_path,capsys):
    import runpy
    from flowguard.__main__ import main
    directory=ROOT/'.flowguard'
    pending=directory/'target/models/_locate_fixture.py'
    fixture=runpy.run_path(str(pending if pending.exists() else directory/'models/_locate_fixture.py'))
    fixture['fixture'](tmp_path)
    assert main(['read','--root',str(tmp_path),'--find','api.py:missing'])==1
    output=capsys.readouterr().out
    assert output.startswith("no symbol 'missing' in api.py; symbols:")


@pytest.mark.parametrize('flags',[['--component','map-read'],['--find','status'],['--mermaid'],['--review'],['--target']])
def test_read_field_conflicts_with_other_views(flags):
    from flowguard.__main__ import main
    with pytest.raises(SystemExit) as error:
        main(['read','--field','status',*flags])
    assert error.value.code==2
