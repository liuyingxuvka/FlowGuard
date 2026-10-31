"""Ordinary test calls become bounded shipped prefixes, never assertion verdicts."""

import sys

import pytest

from flowguard.behave.project import replay
from flowguard.behave.skeleton import derive

pytestmark = pytest.mark.skipif(sys.version_info < (3, 12), reason="pilot behavior needs Python 3.12")

PROGRAM = '''from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    ceiling: int = 2

class Refusal(Exception): pass

class Program:
    def __init__(self, settings=None):
        self._settings = settings if settings is not None else Settings()
        self._ids = []
        self._value = 0
    def add_unit(self, unit_id, name): self._ids.append(unit_id)
    def units(self): return list(self._ids)
    def advance(self, unit_id):
        if self._value >= self._settings.ceiling: raise Refusal("ceiling")
        self._value += 1
    def value(self, unit_id): return self._value
    def status(self, unit_id):
        if self._value == 0: return "new"
        if self._value == 1: return "ready"
        return "done"

class View:
    def __init__(self, program, label="", staff=False):
        self.program = program
        self.label = label
        self.staff = staff
        self.screen = "home"
    def options(self): return ["next", "home"]
    def choose(self, option):
        if option == "next":
            self.program.advance("U1")
            self.screen = "details"
        else:
            self.screen = "home"
'''


def source(tmp_path, tests):
    (tmp_path / "program.py").write_text(PROGRAM)
    directory = tmp_path / "tests"
    directory.mkdir()
    (directory / "test_sample.py").write_text('from program import Program, Settings, View\n' + tests)
    return derive(tmp_path)


def replayed(spec, facts):
    return replay(spec, [], {"world": "small"}, operation="witnesses",
                  options={"recordings": facts["recordings"]})


def test_recording_tracks_two_ui_constructors_and_only_outer_calls(tmp_path):
    spec = source(tmp_path, '''
def test_views():
    program = Program()
    program.add_unit("U1", "one")
    first = View(program, "first", staff=True)
    second = View(program, label="second", staff=False)
    first.choose("next")
    second.choose("next")
    assert program.value("U1") == 2
''')
    facts = replay(spec, [], operation="record")
    assert facts["pytest_exitcode"] == 0
    recording, = facts["recordings"]
    assert recording["stop"] is None
    events = recording["events"]
    created = [row for row in events if row.get("construct")]
    assert [row["receiver"] for row in created] == ["ui:0", "ui:1"]
    assert created[0]["args"] == ["first"] and created[0]["kwargs"] == {"staff": True}
    assert created[1]["kwargs"] == {"label": "second", "staff": False}
    assert [row["receiver"] for row in events if row.get("name") == "choose"] == ["ui:0", "ui:1"]
    assert not any(row.get("name") == "advance" for row in events)
    shipped = replayed(spec, facts)
    assert not shipped["divergences"]
    assert any(row["semantic"].get("kind") == "screen" and row["semantic"]["value"] == "details" for row in shipped["witnesses"])
    assert all(row["start"] == {} and "observations" in row for row in shipped["prefixes"])


def test_nonshipped_settings_stop_at_first_outcome_divergence(tmp_path):
    spec = source(tmp_path, '''
def test_more():
    program = Program(Settings(ceiling=4))
    program.add_unit("U1", "one")
    for number in range(3): program.advance("U1")
    assert program.value("U1") == 3
''')
    facts = replay(spec, [], operation="record")
    assert facts["pytest_exitcode"] == 0
    assert facts["recordings"][0]["settings"] == {"ceiling": 4}
    shipped = replayed(spec, facts)
    assert shipped["ignored_settings"][0]["settings"] == {"ceiling": 4}
    assert shipped["divergences"][0]["index"] == 3
    assert shipped["divergences"][0]["actual"] == "refusal"
    assert len(shipped["replays"][0]["prefix"]) == 3
    assert all(row["start"] == {} for row in shipped["witnesses"])


def test_private_edit_cuts_before_the_next_public_observation(tmp_path):
    spec = source(tmp_path, '''
def test_private():
    program = Program()
    program.add_unit("U1", "one")
    program.advance("U1")
    program._value = 99
    assert program.value("U1") == 99
''')
    facts = replay(spec, [], operation="record")
    assert facts["pytest_exitcode"] == 0
    recording, = facts["recordings"]
    assert recording["stop"]["kind"] == "edit"
    assert recording["stop"]["index"] == 2
    assert [event["name"] for event in recording["events"]] == ["add_unit", "advance"]
    shipped = replayed(spec, facts)
    assert len(shipped["replays"][0]["prefix"]) == 2
    assert not any(row["semantic"].get("value") == 99 for row in shipped["witnesses"])
    assert shipped["prefixes"][-1]["observations"]["values"]


def test_nonchoose_navigation_stops_recording_without_changing_the_test(tmp_path):
    source(tmp_path, '''
def test_navigation():
    program = Program()
    program.add_unit("U1", "one")
    view = View(program)
    assert view.jump() == 42
    assert view.screen == "details"
''')
    path = tmp_path / "program.py"
    path.write_text(path.read_text() + '\n    def jump(self):\n        self.screen = "details"\n        return 42\n')
    spec = derive(tmp_path)
    facts = replay(spec, [], operation="record")
    assert facts["pytest_exitcode"] == 0
    recording, = facts["recordings"]
    assert recording["stop"]["kind"] == "edit"
    assert recording["stop"]["index"] == 2
    assert not any(row.get("name") == "jump" for row in recording["events"])
    shipped = replayed(spec, facts)
    assert not any(row["semantic"].get("kind") == "screen" and row["semantic"]["value"] == "details" for row in shipped["witnesses"])
