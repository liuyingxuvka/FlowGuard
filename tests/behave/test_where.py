"""Static CLI reads stay separate from behavior execution and recorded test reach."""

import hashlib
import json
from pathlib import Path
import sys

import pytest

from flowguard.behave import __main__ as entry


@pytest.mark.skipif(sys.version_info < (3, 12), reason="recorded native test reach requires Python 3.12")
def test_where_uses_real_recorded_test_calls_without_running_them_again(tmp_path, monkeypatch, capsys):
    from flowguard.behave import engine, project
    (tmp_path / "program.py").write_text('''class Program:
    def __init__(self): self._units, self._value = [], 0
    def add_unit(self, unit_id, name): self._units.append(unit_id)
    def units(self): return list(self._units)
    def advance(self, unit_id):
        self._value += 1
        return helper(self._value)
    def value(self, unit_id): return self._value
def helper(value): return value * 2
''')
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test_live.py").write_text('''from program import Program
def test_live():
    subject = Program()
    subject.add_unit("U7", "seven")
    assert subject.advance("U7") == 2
''')
    engine.audit(tmp_path, worlds=["small"], seeds=[0], steps=1, node_cap=4, alphabet_cap=8)
    def no_execution(*args, **kwargs):
        raise AssertionError("where started behavior or created a cache")
    monkeypatch.setattr(project, "run_isolated_process", no_execution)
    monkeypatch.setattr(engine, "cache_root", no_execution)
    facts = entry._where_facts(tmp_path)
    assert facts["test_reach"]["program.py#helper"] == ["tests/test_live.py::test_live"]
    cache = tmp_path / ".flowguard/cache"
    def stamps():
        return {p.relative_to(cache).as_posix(): (p.stat().st_mtime_ns, hashlib.sha256(p.read_bytes()).hexdigest())
                for p in cache.rglob("*") if p.is_file()}
    before = stamps()
    assert entry.main(["where", "helper", "--root", str(tmp_path), "--json"]) == 0
    assert "tests/test_live.py::test_live" in capsys.readouterr().out
    assert stamps() == before
    source = tmp_path / "program.py"
    source.write_text(source.read_text().replace("return value * 2", "return value * 3"))
    stale = entry._where_facts(tmp_path)
    assert stale["state"] == "stale" and stale["test_reach"] == {}
