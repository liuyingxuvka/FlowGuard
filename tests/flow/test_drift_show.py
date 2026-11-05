"""The real drift id draws cached native facts, including differences outside model domains."""
import json
import os
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

from checkrun import command, env, run_check


MODEL = '''from flowguard.flow import Model, need
from flowguard.flow.adapter import fields
m=Model("counter", covers=["app.py:Program"])
m.field("n", (0,1), 0)
@m.action()
def step(s):
    need(s["n"] == 0)
    s["n"] = 1
    return "expected output"
m.bind_adapter({"system":"app:Program","classes":["app:Program"],"refusal":["app:Refusal"]},
    state=lambda snapshot: fields(snapshot,names=("n",)),operations={"step":"step"})
MODEL=m
'''
APP = '''class Refusal(Exception): pass
class Program:
    def __init__(self): self.n=0
    def step(self):
        if self.n != 0: raise Refusal("at limit")
        self.n=1
        return "observed output"
'''


def show(root, identifier):
    result = subprocess.run(command("show", identifier, "--json"), cwd=root, env=env(),
                            capture_output=True, text=True, timeout=120)
    return result.returncode, json.loads(result.stdout), result.stderr


def checked(project, app=APP):
    project.file("app.py", app)
    project.flow("counter", MODEL)
    first = run_check(project.root, "--json")
    mismatches = [row for row in first.data["conflicts"] if row["kind"] == "MODEL DRIFT"]
    assert len(mismatches) == 1, first.out + first.err
    drift, = mismatches
    return drift["id"]


def test_real_drift_id_draws_actual_svg_and_stale_or_missing_core_never_executes_code(project, monkeypatch):
    identifier = checked(project)
    first_code, first_picture, first_errors = show(project.root, identifier)
    assert first_code == 0, (first_picture, first_errors)
    first_record = json.loads((project.root / ".flowguard/conflicts.json").read_text())
    first_digest = first_record["models"]["counter"]["core"]["digest"]
    # An unchanged model reuses the actually checked recipe, including its witness.
    again = run_check(project.root, "--json")
    assert any(row["id"] == identifier for row in again.data["conflicts"])
    record = json.loads((project.root / ".flowguard/conflicts.json").read_text())
    receipt = record["models"]["counter"]["core"]
    assert receipt == first_record["models"]["counter"]["core"]
    assert receipt["digest"] == first_digest
    code, data, errors = show(project.root, identifier)
    assert code == 0, (data, errors)
    picture, = data["pictures"]
    assert picture["subject_id"] == identifier and picture["rendered"], picture
    assert "expected output" in picture["mermaid"] and "observed output" in picture["mermaid"]
    assert "success" in picture["mermaid"] and "state" in picture["mermaid"]
    cached_pictures = [json.loads(path.read_text()) for path in
                       (project.root / ".flowguard/cache/flow/parts").glob("*.json")]
    assert any(row["kind"] == "picture" and row["info"].get("native_core") == receipt["digest"]
               and row["info"]["mermaid"] == picture["mermaid"] for row in cached_pictures)
    svg, = [project.root / name for name in picture["files"] if name.endswith(".svg")]
    text = " ".join(ET.parse(svg).getroot().itertext())
    assert "expected output" in text and "observed output" in text

    from flowguard.flow import cli, diagram
    from flowguard.native import session
    def refuse_native(*args, **kwargs):
        raise AssertionError("show entered native execution")
    monkeypatch.setattr(session, "replay", refuse_native)
    args = cli.parser().parse_args(["show", identifier, "--json"])
    direct_code, direct_json = diagram.show_main(project.root, args, diagram.inprocess_runner(project.root))
    assert direct_code == 0, direct_json

    source = project.root / "app.py"
    saved, stamp = source.read_bytes(), source.stat()
    source.write_bytes(saved.replace(b"observed output", b"modified output"))
    os.utime(source, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    code, stale, errors = show(project.root, identifier)
    assert code == 2 and not stale["pictures"], (stale, errors)
    assert "check counter" in stale["message"] and "stale" in stale["message"]
    assert diagram.show_main(project.root, args, diagram.inprocess_runner(project.root))[0] == 2
    source.write_bytes(saved)
    (project.root / f'.flowguard/cache/flow/parts/{receipt["digest"]}.json').unlink()
    code, missing, errors = show(project.root, identifier)
    assert code == 2 and not missing["pictures"], (missing, errors)
    assert "check counter" in missing["message"] and "missing" in missing["message"]
    assert diagram.show_main(project.root, args, diagram.inprocess_runner(project.root))[0] == 2


def test_unknown_real_state_is_an_observation_error_not_a_model_domain_node(project):
    identifier = checked(project, APP.replace("self.n=1", "self.n=2"))
    code, data, errors = show(project.root, identifier)
    assert code == 0, (data, errors)
    text = data["pictures"][0]["mermaid"]
    assert "outside the model domain" in text and "projection unavailable" in text
    assert "code observed" in text and "model expected" in text
    assert "native outcome: success" in text


def test_full_walk_drift_uses_the_same_finding_and_actual_witness(project):
    # The cheap operation witness passes. Only a later state reached by the walk
    # returns the wrong value, so this still exercises the actual walk picture.
    project.file("app.py", APP.replace("self.n != 0", "self.n >= 2")
                 .replace("def step(self):", "def step(self, amount):")
                 .replace("self.n=1", "self.n+=amount")
                 .replace('return "observed output"',
                          'return "expected output" if self.n == 1 else "observed output"'))
    project.flow("counter", MODEL.replace('(0,1)', '(0,1,2)')
                 .replace('@m.action()', '@m.action(amount=(1,2))').replace('def step(s):', 'def step(s, amount):')
                 .replace('s["n"] == 0', 's["n"] + amount <= 2').replace('s["n"] = 1', 's["n"] += amount')
                 .replace("MODEL=m", 'm.terminal("n", [2])\nMODEL=m'))
    checked = run_check(project.root, "--full", "--json")
    drift, = [row for row in checked.data["conflicts"] if row["kind"] == "MODEL DRIFT"]
    assert drift["detail"]["native"]["check"] == "walk"
    code, data, errors = show(project.root, drift["id"])
    assert code == 0, (data, errors)
    assert "expected output" in data["pictures"][0]["mermaid"]
    assert "observed output" in data["pictures"][0]["mermaid"]
