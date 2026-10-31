"""Execution facts invalidate on actual file, directory and engine content."""

import json
import sys

import pytest

from flowguard.behave import engine
from flowguard.behave.engine import audit, content_identity
from flowguard.behave.project import replay
from flowguard.behave.skeleton import derive
from .test_explore import program

pytestmark = pytest.mark.skipif(sys.version_info < (3, 12), reason="pilot behavior needs Python 3.12")


def test_facts_reuse_then_actual_read_file_change_invalidates(program):
    from pathlib import Path
    import subprocess
    path = program / "program.py"
    path.write_text(path.read_text().replace('        self._value = 0', '        self._value = 0\n        self._payload = Path(__file__).with_name("data.txt").read_text()'))
    data = program / "data.txt"
    data.write_text("first")
    first = audit(program, worlds=["small"], seeds=[0], steps=1)
    second = audit(program, worlds=["small"], seeds=[0], steps=1)
    assert first["facts_reused"] == 0 and second["facts_reused"] == 1
    data.write_text("changed without a code edit")
    changed = audit(program, worlds=["small"], seeds=[0], steps=1)
    assert changed["facts_reused"] == 0
    caches = list(engine.cache_root(program).glob("*.json"))
    assert caches
    for cache in caches:
        value = json.loads(cache.read_text())
        assert "verdict" not in value and "verdict" not in value["facts"]
    command = [sys.executable, "-m", "flowguard.behave", "audit", "--root", str(program),
               "--world", "small", "--seeds", "0", "--steps", "1", "--json"]
    first_cli = subprocess.run(command, cwd=Path(__file__).resolve().parents[2], check=True, capture_output=True, text=True)
    second_cli = subprocess.run(command, cwd=Path(__file__).resolve().parents[2], check=True, capture_output=True, text=True)
    assert json.loads(first_cli.stdout)["facts_reused"] in {0, 1}
    assert json.loads(second_cli.stdout)["facts_reused"] == 1


def test_actually_listed_directory_change_invalidates(program):
    assets = program / "assets"
    assets.mkdir()
    path = program / "program.py"
    path.write_text(path.read_text().replace('        self._value = 0', '        self._value = 0\n        self._listed = os.listdir(Path(__file__).with_name("assets"))'))
    first = audit(program, worlds=["small"], seeds=[0], steps=1)
    assert audit(program, worlds=["small"], seeds=[0], steps=1)["facts_reused"] == 1
    (assets / "new.txt").write_text("new")
    changed = audit(program, worlds=["small"], seeds=[0], steps=1)
    assert first["facts_reused"] == 0 and changed["facts_reused"] == 0


def test_engine_source_identity_changes_without_version_bump(program, tmp_path, monkeypatch):
    package = tmp_path / "engine-copy/flowguard/behave"
    package.mkdir(parents=True)
    path = package / "engine.py"
    path.write_text('__version__ = "0.71.0"\nVALUE = 1\n')
    monkeypatch.setattr(engine, "__file__", str(path))
    spec = derive(program)
    before = content_identity(spec)
    path.write_text('__version__ = "0.71.0"\nVALUE = 2\n')
    assert content_identity(spec) != before


def test_native_import_reads_current_source_despite_timestamp_bytecode(program):
    import os
    import py_compile

    path = program / "program.py"
    source = path.read_text().replace("        self._value = 0", "        self._value = VALUE") + "\nVALUE = 1\n"
    path.write_text(source)
    py_compile.compile(str(path), doraise=True)
    metadata = path.stat()
    path.write_text(source.replace("VALUE = 1", "VALUE = 2"))
    os.utime(path, ns=(metadata.st_atime_ns, metadata.st_mtime_ns))
    result = replay(derive(program), [{"name": "value", "args": ["U1"]}], {"world": "small"})
    assert result["steps"][0]["value"]["root"] == 2


def test_executed_external_path_exists_is_a_content_input(program):
    path = program / "program.py"
    flag = program.parent / (program.name + ".flag")
    helper = program.parent / (program.name + "_helper.py")
    helper.write_text("from pathlib import Path\ndef check(path): return Path(path).exists()\n")
    loading = "from importlib.util import spec_from_file_location, module_from_spec\n_spec = spec_from_file_location('external_helper', " + repr(str(helper)) + ")\nhelper = module_from_spec(_spec)\n_spec.loader.exec_module(helper)\n"
    path.write_text(loading + path.read_text().replace("        self._value = 0", "        self._value = 0\n        self._flag = helper.check(" + repr(str(flag)) + ")"))
    spec = derive(program)
    first = replay(spec, [])
    assert engine.footprint_identity(first["footprint"])
    flag.write_text("created after the first replay")
    assert engine.footprint_identity(first["footprint"]) is None
    second = replay(spec, [])
    assert first["initial"] != second["initial"]
    helper.write_text("from pathlib import Path\ndef check(path): return Path(path).stat().st_size\n")
    direct = replay(derive(program), [])
    assert not direct["footprint"]["reusable"]
    assert "application-consumed full filesystem metadata" in direct["footprint"]["untracked"]


def test_application_arena_listing_cannot_license_a_complete_proof(program):
    path = program / "program.py"
    source = path.read_text().replace("        self._value = 0", '        self._value = 0\n        Path("b").write_text("b")\n        Path("a").write_text("a")')
    path.write_text(source + '\n    def first(self): return next(name for name in os.listdir(".") if name in ("a", "b"))\n')
    first = replay(derive(program), [{"name": "first"}])
    assert not first["footprint"]["reusable"]
    result = engine.prove(program, {"semantic": {"kind": "query", "query": "first", "value": first["steps"][0]["value"]["root"]}, "prefix": []}, persist=False)
    assert not result["matched"] and result["state"] == "unchecked"
