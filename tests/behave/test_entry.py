"""Exercise the standalone bootstrap without advertising future behavior."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from flowguard.behave import __main__ as entry

ROOT = Path(__file__).resolve().parents[2]


def test_static_where_forms_do_not_import_program_or_write_cache(tmp_path, monkeypatch, capsys):
    (tmp_path / "program.py").write_text(
        'raise RuntimeError("the static view imported the application")\n'
        'def helper(value): return value + 1\n'
        'def main(value): return helper(value)\n')
    (tmp_path / "README.md").write_text("The `main` function in `program.py` uses `helper`.\n")
    monkeypatch.setattr(entry.sys, "version_info", (3, 11, 17))
    for args in (("helper",), (), ("--flow",), ("--arch",), ("--text",), ("--keyflows",)):
        assert entry.main(["where", *args, "--root", str(tmp_path), "--json"]) == 0
        assert isinstance(json.loads(capsys.readouterr().out), dict)
    assert not (tmp_path / ".flowguard").exists()
    assert sorted(path.name for path in tmp_path.iterdir()) == ["README.md", "program.py"]


def test_help_lists_only_implemented_commands():
    result = subprocess.run(
        [sys.executable, "-m", "flowguard.behave", "--help"],
        cwd=ROOT, text=True, capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("usage: python -m flowguard.behave")
    assert not result.stderr
    assert "{init,audit,why,where}" in result.stdout


def test_empty_invocation_prints_help(capsys):
    assert entry.main([]) == 0
    assert capsys.readouterr().out.startswith("usage: python -m flowguard.behave")


def test_unimplemented_verb_never_reports_success():
    result = subprocess.run(
        [sys.executable, "-m", "flowguard.behave", "release"],
        cwd=ROOT, text=True, capture_output=True,
    )
    assert result.returncode == 2
    assert not result.stdout
    expected = ("needs Python 3.12 or newer" if sys.version_info < (3, 12)
                else "invalid choice: 'release'")
    assert expected in result.stderr


def test_python311_refuses_behavior_before_dispatch(monkeypatch, capsys):
    monkeypatch.setattr(entry.sys, "version_info", (3, 11, 17))
    with pytest.raises(SystemExit) as error:
        entry.main(["init"])
    assert error.value.code == 2
    assert "the FlowGuard pilot needs Python 3.12 or newer" in capsys.readouterr().err
    assert entry.main([]) == 0
    with pytest.raises(SystemExit) as help_exit:
        entry.main(["--help"])
    assert help_exit.value.code == 0


def test_package_import_does_not_load_engine_modules():
    code = (
        "import sys, flowguard.behave; "
        "assert sorted(name for name in sys.modules if name.startswith('flowguard.behave')) "
        "== ['flowguard.behave']"
    )
    subprocess.run([sys.executable, "-c", code], cwd=ROOT, check=True)
