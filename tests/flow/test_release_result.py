"""Release reports its actual scope and does not rewrite a clean check record."""
import json
from flowguard.__main__ import main

MODEL = '''from flowguard.flow import Model, need
m = Model("dial")
m.field("pos", range(3), 0)
@m.action()
def up(s):
    need(s["pos"] < 2, "top")
    s["pos"] += 1
@m.action()
def down(s):
    need(s["pos"] > 0, "bottom")
    s["pos"] -= 1
MODEL = m
'''


def test_release_without_tests_names_the_scope(project, capsys):
    project.flow("dial", MODEL)
    assert main(["release", "--root", str(project.root)]) == 0
    last = capsys.readouterr().out.splitlines()[-1]
    assert last.startswith("verify: MODELS PASS; tests not run")
    assert "verify: PASS" not in last


def test_release_keeps_normal_checks_committed_record_clean(project, capsys):
    project.flow("dial", MODEL)
    project.file(".gitignore", ".flowguard/cache/\n")
    assert main(["check", "--wait", "60", "--root", str(project.root)]) == 0
    before = (project.root / ".flowguard/conflicts.json").read_bytes()
    project.commit()
    assert main(["release", "--root", str(project.root)]) == 0
    assert (project.root / ".flowguard/conflicts.json").read_bytes() == before
    project.git("diff", "--exit-code")


def test_release_final_line_names_surviving_breakages(project, capsys):
    from conftest import DATA
    project.flow_from(DATA / "planted/rental_naive.py", "rental")
    assert main(["release", "--root", str(project.root)]) == 1
    lines = capsys.readouterr().out.splitlines()
    assert "; 3 deliberate breakages not caught" in lines[-1]
    assert main(["check", "--full", "--json", "--wait", "60", "--root", str(project.root)]) == 1
    data = json.loads(capsys.readouterr().out)
    assert data["surviving_breakages"] == 3


def test_covered_code_syntax_error_names_file_and_line(project, capsys):
    project.file("app.py", "class App(:\n    pass\n")
    project.flow("dial", MODEL.replace('Model("dial")', 'Model("dial", covers=["app.py:App"])'))
    assert main(["check", "--wait", "60", "--root", str(project.root)]) == 2
    output = capsys.readouterr().out
    assert "app.py:1" in output and "syntax error" in output
    assert "worker failed" not in output
