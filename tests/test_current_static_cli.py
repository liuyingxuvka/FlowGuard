"""Retained public source and native-test inventory contracts."""
import json, os
from pathlib import Path


def test_help_lists_every_option_of_every_verb(capsys):
    from flowguard.__main__ import main, _verb_parser

    assert main(["--help"]) == 0
    text = capsys.readouterr().out
    for verb in ("where", "release", "template", "req", "status", "check", "show", "decide"):
        for action in _verb_parser(verb)._actions:
            for option in action.option_strings:
                assert option in text, (verb, option)

def test_public_where_forms_are_static_and_next_commands_are_executable(tmp_path):
    import shlex
    import subprocess
    import sys

    root = tmp_path / "static project"
    root.mkdir()
    (root / "app.py").write_text('''raise RuntimeError("the application must never be imported")
STATE = 0
def helper(): return STATE
def advance():
    global STATE
    STATE += 1
    return helper()
if __name__ == "__main__": advance()
''')
    (root / "guide.md").write_text("You MUST preserve `app.helper` before publishing.\n")
    (root / ".flowguard/models").mkdir(parents=True)
    (root / ".flowguard/models/static_model.py").write_text('''MODEL_ID = "static_model"
COMPONENTS = ["app"]
IMPLEMENTED_BY = {"Helper": "app.py:helper"}
raise RuntimeError("the model must never be imported")
''')
    (root / ".flowguard/map.json").write_text(json.dumps({"schema": "flowguard.map.v1", "components": [
        {"id": "app", "files": ["app.py"], "models": [".flowguard/models/static_model.py"], "status": "draft"}]}))
    before = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    environment = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}
    guarded_module = '''import runpy, sys
sys.argv = ["flowguard", *sys.argv[1:]]
try:
    runpy.run_module("flowguard", run_name="__main__")
finally:
    assert not any(name == "flowguard.behave" or name.startswith("flowguard.behave.") for name in sys.modules)
'''
    def invoke(arguments):
        return subprocess.run([sys.executable, "-c", guarded_module, *arguments], cwd=root,
                              env=environment, capture_output=True, text=True, timeout=20)
    for arguments in ([], ["helper"], ["--flow"], ["--arch"], ["--text"], ["--keyflows"]):
        answer = invoke(["where", *arguments, "--root", str(root), "--json"])
        assert answer.returncode == 0 and not answer.stderr, answer
        assert len(answer.stdout.splitlines()) == 1
        facts = json.loads(answer.stdout)
        # Every view reports its next steps one way, as the other commands do: {id, command} objects in next.
        assert "next_queries" not in facts and isinstance(facts["next"], list), facts.get("next")
        assert all(set(item) == {"id", "command"} and item["id"] == "where" for item in facts["next"]), facts["next"]
        if not arguments:
            command = shlex.split(facts["next"][0]["command"])
            assert command[:4] == ["python", "-m", "flowguard", "where"]
            assert command[command.index("--root") + 1] == str(root.resolve())
            assert invoke(command[3:]).returncode == 0
        if arguments == ["--text"]:
            assert facts["projection"] == "compact"
            assert facts["next"]
        if arguments == ["helper"]:
            assert facts["functions"][0]["execution"] == {"state": "not_recorded", "tests": "not recorded in this clone"}
    for arguments in (["--at", "HEAD"], ["--flow", "--arch"]):
        answer = invoke(["where", *arguments, "--root", str(root)])
        assert answer.returncode == 2 and "error:" in answer.stderr
    # An adopted project keeps only disposable, self-ignoring parse caches; nothing else changes.
    assert {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*")
            if p.is_file() and not p.relative_to(root).as_posix().startswith(".flowguard/cache/")} == before
    assert (root / ".flowguard/cache/.gitignore").read_text() == "*\n"

def test_public_text_reuses_one_report_and_preserves_ref_in_group_queries(tmp_path, monkeypatch, capsys):
    import shlex
    import subprocess
    from flowguard.__main__ import main
    from flowguard.map import derived, textrules

    def git(*arguments):
        return subprocess.check_output(["git", "-C", str(tmp_path), *arguments], stderr=subprocess.PIPE).decode().strip()
    git("init", "-q")
    original = "You MUST preserve `old_name` before publishing the selected original artifact."
    (tmp_path / "core.py").write_text("def old_name(): return 1\n")
    for path in ("left.md", "right.md"):
        (tmp_path / path).write_text(original + "\n")
    git("add", ".")
    git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "old originals")
    revision = git("rev-parse", "HEAD")
    git("tag", "old")
    (tmp_path / "core.py").write_text("def new_name(): return 2\n")
    for path in ("left.md", "right.md"):
        (tmp_path / path).write_text("You MUST preserve `new_name` in the current working tree.\n")
    calls, real_report = [], textrules.report
    def once(*args, **kwargs):
        calls.append(kwargs)
        return real_report(*args, **kwargs)
    def no_second_scan(*args, **kwargs):
        raise AssertionError("the text controller must not also scan derived.where")
    monkeypatch.setattr(textrules, "report", once)
    monkeypatch.setattr(derived, "where", no_second_scan)
    assert main(["where", "--text", "--at", "old", "--root", str(tmp_path), "--json"]) == 0
    answer = capsys.readouterr()
    assert not answer.err and len(answer.out.splitlines()) == 1
    compact = json.loads(answer.out)
    assert calls == [{"at": "old"}]
    command = shlex.split(compact["next"][0]["command"])
    assert command[:4] == ["python", "-m", "flowguard", "where"]
    assert command[4].startswith("group:") and "--text" in command and "--json" in command
    assert command[command.index("--root") + 1] == str(tmp_path.resolve())
    assert command[command.index("--at") + 1] == "old"
    assert main(command[3:]) == 0
    selected = json.loads(capsys.readouterr().out)
    assert calls == [{"at": "old"}, {"at": "old"}]
    assert selected["revision"] == revision and selected["source"] == "old"
    assert len(selected["texts"]) == 2 and all(row["text"] == original for row in selected["texts"])
    assert any(row["name"] == "old_name" and row["state"] == "found in static source" for row in selected["references"])
    assert not any(row["name"] == "new_name" for row in selected["references"])
    literal_command = next(shlex.split(item["command"]) for item in selected["next"]
                           if shlex.split(item["command"])[4].startswith("text:"))
    assert literal_command[literal_command.index("--at") + 1] == "old"
    assert main(literal_command[3:]) == 0
    literal = json.loads(capsys.readouterr().out)
    assert calls == [{"at": "old"}] * 3
    # A group selection prints originals with their Git origin; a literal selection lists the same passages.
    assert all(row["provenance"]["state"] == "git" for row in selected["texts"])
    assert literal["selection"]["kind"] == "literal"
    assert literal["texts"] == [{key: value for key, value in row.items() if key != "provenance"} for row in selected["texts"]]
    assert literal["omitted"] == {}
    assert not (tmp_path / ".flowguard").exists()
