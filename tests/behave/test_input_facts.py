"""Native importer precision never masks actual application or test inputs."""
import sys

import pytest

from flowguard.behave import engine
from flowguard.behave.project import replay
from flowguard.behave.skeleton import derive
from flowguard.map import jobs
from flowguard.map.inputs import footprint_identity
from flowguard.map.requests import store_request

pytestmark = pytest.mark.skipif(sys.version_info < (3, 12), reason="native input controls need Python 3.12")

PROGRAM = '''class Program:
    def __init__(self): self._units = {}
    def add_unit(self, unit_id, name): self._units[unit_id] = 3
    def units(self): return list(self._units)
    def tick(self, unit_id): self._units[unit_id] += 0
    def count(self, unit_id): return self._units[unit_id]
'''


def test_first_norm_directory_rejudges_cached_facts_without_native_replay(tmp_path, monkeypatch):
    (tmp_path / "program.py").write_text(PROGRAM)
    store_request(tmp_path, b"The count must be at most 3.\n", identifier="R1")
    result = engine.audit(tmp_path, worlds=["small"], seeds=[1], steps=1, node_cap=4, alphabet_cap=8)
    assert not result["errors"] and result["rules"]["capture_scope"]["complete"]
    before = engine.content_identity(engine._execution_spec(tmp_path))
    footprint = result["runs"][0]["facts"]["footprint"]
    assert footprint_identity(footprint)
    request = {"operation": "native facts", "slices": [], "bases": [], "parameters": {}}
    original_job = jobs.prepare(tmp_path, files=["program.py"], directories=["."], request=request,
                                directory_uses=footprint["directory_uses"])
    norm = tmp_path / "tests/rules/limits/test_count.py"
    norm.parent.mkdir(parents=True)
    norm.write_text('from flowguard.behave.rules import rule, owner\n'
                    '@rule(owner("R1", "The count must be at most 3."))\n'
                    'def test_limit(state):\n'
                    '    for unit in state.units():\n'
                    '        assert state.count(unit) <= 3\n')
    assert engine.content_identity(engine._execution_spec(tmp_path)) == before
    assert footprint_identity(footprint)
    legacy = {key: value for key, value in footprint.items() if key != "directory_uses"}
    assert footprint_identity(legacy) is None  # Old receipts have no narrower provenance.
    current_job = jobs.prepare(tmp_path, files=["program.py"], directories=["."], request=request,
                               directory_uses=footprint["directory_uses"])
    assert current_job.key == original_job.key and original_job.matches(tmp_path)
    monkeypatch.setattr(engine, "replay", lambda *args, **kwargs: pytest.fail("cached norm adoption ran native execution"))
    judged = engine.judge_cached_rules(tmp_path)
    assert judged is not None and judged["rules"][0]["status"] == "clean"


def test_real_program_directory_read_stays_an_execution_dependency(tmp_path):
    (tmp_path / "tests").mkdir()
    note = tmp_path / "tests/note.txt"
    note.write_text("first")
    source = PROGRAM.replace('    def __init__(self): self._units = {}',
        '    def __init__(self):\n'
        '        self._units = {}\n'
        '        from pathlib import Path\n'
        '        folder = Path(__file__).parent / "tests"\n'
        '        self._data = [path.read_text() for path in sorted(folder.iterdir())]')
    (tmp_path / "program.py").write_text(source)
    facts = replay(derive(tmp_path), [], {"world": "small"})
    footprint = facts["footprint"]
    assert footprint_identity(footprint)
    assert footprint["directory_uses"][str(note.parent)]["kind"] == "listing"
    assert str(note) in footprint["files"]
    note.write_text("changed actual data")
    assert footprint_identity(footprint) is None
    note.write_text("first")
    assert footprint_identity(footprint)
    (note.parent / "new.txt").write_text("new listed input")
    assert footprint_identity(footprint) is None


def test_ordinary_test_helper_import_and_read_still_invalidate(tmp_path):
    (tmp_path / "program.py").write_text(PROGRAM)
    (tmp_path / "tests").mkdir()
    helper = tmp_path / "tests/helper.py"
    helper.write_text("value = 1\n")
    (helper.parent / "test_sample.py").write_text('from helper import value\nfrom program import Program\n'
        'def test_actual():\n'
        '    subject = Program()\n    subject.add_unit("U7", "seven")\n'
        '    subject.tick("U7")\n    assert subject.count("U7") == 3 and value == 1\n')
    facts = replay(derive(tmp_path), [], operation="record", timeout=30)
    assert facts["pytest_exitcode"] == 0 and facts["recordings"]
    assert footprint_identity(facts["footprint"])
    assert str(helper) in facts["footprint"]["files"]
    helper.write_text("value = 2\n")
    assert footprint_identity(facts["footprint"]) is None
