"""Exercise the standalone bootstrap without advertising future behavior."""

import subprocess
import sys
from pathlib import Path

import pytest

from flowguard.behave import __main__ as entry

ROOT = Path(__file__).resolve().parents[2]


def test_help_lists_only_implemented_commands():
    result = subprocess.run(
        [sys.executable, "-m", "flowguard.behave", "--help"],
        cwd=ROOT, text=True, capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("usage: python -m flowguard.behave")
    assert not result.stderr
    assert "{init,audit,why}" in result.stdout


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


@pytest.mark.skipif(sys.version_info < (3, 12), reason="pilot behavior needs Python 3.12")
def test_init_constructs_the_program_and_writes_only_source_pins(tmp_path):
    from .test_skeleton import SOURCE

    (tmp_path / "example.py").write_text(SOURCE, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "flowguard.behave", "init", "--root", str(tmp_path)],
        cwd=ROOT, text=True, capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    assert "system: example:Engine" in result.stdout
    assert "unrecognized front doors:" in result.stdout
    assert "glossary draft:" in result.stdout
    assert sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*") if path.is_file()) == [
        ".flowguard/skeleton.py", "example.py",
    ]
