"""FG-814 show: the prototype pictures drawn again from the same models, the default show of
every E7b model, before/after colours, symmetry, the refusal with its list of views, the
picture files (Mermaid in headless Chromium) and the `show` command body."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from flowguard.flow import diagram
from flowguard.flow.checks import CONFLICT, check_model
from flowguard.flow.explore import Bounds
from flowguard.flow.model import Loaded, load_model
from flowguard.flow.parts import PartContext, PartSpec, run_part
from flowguard.flow.project import cache_dir

from conftest import DATA, REPO
from golden_machine import load_machines

PICTURES = DATA / "pictures"
E7B = sorted((DATA / "golden" / "models").glob("e7b_*/*.py"))
RENDERER = shutil.which("node") is not None


# ---------------------------------------------------------------------- reading Mermaid
_NODE = re.compile(r'^\s+(\w+)(?:\["(.*)"\]|\(\["(.*)"\]\))$')
_LINK = re.compile(r'^\s+(\w+)(?:\(\( \)\))? (?:(--|-\.) "(.*)" (?:-->|\.->)|(-->)) (\w+)$')


def parse(text):
    """{boxes: id -> text, arrows: [(from text, label, to text, style, dotted)], classes}."""
    boxes, links, classes, styles = {}, [], {}, {}
    for line in text.splitlines():
        m = _NODE.match(line)
        if m:
            boxes[m.group(1)] = m.group(2) if m.group(2) is not None else m.group(3)
            continue
        m = _LINK.match(line)
        if m:
            links.append((m.group(1), m.group(3) or "", m.group(5), m.group(2) == "-."))
            continue
        m = re.match(r"^\s+class ([\w,]+) (\w+)$", line)
        if m:
            for b in m.group(1).split(","):
                classes[b] = m.group(2)
            continue
        m = re.match(r"^\s+linkStyle (\d+) stroke:(#\w+)", line)
        if m:
            styles[int(m.group(1))] = m.group(2)
    arrows = []
    for n, (a, label, b, dotted) in enumerate(links):
        if a == "start":
            continue
        arrows.append((boxes[a], label, boxes[b], styles.get(n), dotted))
    return {"boxes": boxes, "arrows": arrows, "classes": classes,
            "start": next((boxes[b] for a, _, b, _ in links if a == "start"), None)}


def plain(text):
    """A box text without its mark."""
    return re.sub(r" \((STUCK|can be STUCK|removed|never reached|only with [^)]*)\)$", "", text)


def show(root, *argv):
    """The show verb as `python -m flowguard show` parses it, run in process."""
    from flowguard.flow import cli
    try:
        args = cli.parser().parse_args(["show", *argv])
    except cli.UsageError as e:
        return 2, f"usage error: {e}\n"
    return diagram.show_main(Path(root), args, diagram.inprocess_runner(Path(root)))


def body(out):
    """The Mermaid text of the first picture printed by show."""
    lines = out.splitlines()
    end = next((n for n, x in enumerate(lines[1:], 1) if x and not x.startswith((" ", "---", "title:", "flowchart"))),
               len(lines))
    return "\n".join(lines[1:end]).rstrip("\n")


# ---------------------------------------------------------------------- the prototype pictures
def test_naive_picture_is_the_prototype_picture(project):
    project.flow_from(DATA / "planted" / "rental_naive.py", "rental")
    code, out = show(project.root)
    assert code == 0, out
    first = out.splitlines()[0]
    assert first.startswith("rental: STUCK T1 stuck in cond='repair', branch='library'")
    assert "with its 3-step path" in first
    assert "the fields the counterexample changes (cond[T1], branch[T1]), whole space: 6 boxes, 9 arrows" in first
    assert "folded: nothing" in first
    got, want = parse(body(out)), parse((PICTURES / "naive.mmd").read_text())
    assert sorted(got["boxes"].values()) == sorted(want["boxes"].values())          # the same 6 boxes
    assert sorted(a[:3] for a in got["arrows"]) == sorted(a[:3] for a in want["arrows"])   # the same 9 arrows
    stuck = [t for b, t in got["boxes"].items() if got["classes"].get(b) == "stuck"]
    assert stuck == ["cond=repair<br/>branch=library (STUCK)"]
    red = sorted(a[1] for a in got["arrows"] if a[3] == "#c00")
    assert red == ["rent", "return_damaged", "transfer"] == sorted(a[1] for a in want["arrows"] if a[3] == "#c00")
    assert got["start"] == "cond=shop<br/>branch=main"


def test_stuck_json_subject_names_the_same_object_and_fields_as_check(project):
    path = project.flow_from(DATA / "planted" / "rental_naive.py", "rental")
    [finding] = [f for f in check_model(load_model(path, project.root)).findings if f.kind == "STUCK"]
    code, out = show(project.root, "--json")
    assert code == 0
    [picture] = json.loads(out)["pictures"]
    assert picture["subject"] == finding.text.partition(": ")[0]
    assert picture["subject_id"] == finding.id
    assert f"STUCK {picture['subject']} with its" in picture["first_line"]
    assert finding.subject == "branch[*] = 'library'"  # the fingerprint's subject does not change


def test_fixed_against_head_is_the_prototype_diff_picture(project):
    project.flow_from(DATA / "planted" / "rental_naive.py", "rental")
    project.file(".gitignore", ".flowguard/cache/\n")
    project.commit("naive")
    project.flow_from(DATA / "planted" / "rental_fixed.py", "rental")
    code, out = show(project.root)
    assert code == 0, out
    first = out.splitlines()[0]
    assert first.startswith("rental: the change against HEAD: 2 arrows added (green), 1 removed (grey) in this view; "
                            "in the whole model 2 steps added, 1 removed (a step is one action from one full state, "
                            "so a new or wider field multiplies them)")
    got, want = parse(body(out)), parse((PICTURES / "fixed_diff.mmd").read_text())
    kept = {b: t for b, t in got["boxes"].items() if got["classes"].get(b) != "removed"}
    assert sorted(kept.values()) == sorted(want["boxes"].values())                   # the 6 non-grey boxes
    added = [t for b, t in got["boxes"].items() if got["classes"].get(b) == "added"]
    assert added == ["cond=transit<br/>branch=library"]
    green = sorted(a[:3] for a in got["arrows"] if a[3] == "#080")
    assert green == sorted(a[:3] for a in want["arrows"] if a[3] == "#080")          # return_damaged, receive
    assert [a[1] for a in got["arrows"] if a[3] == "#080"] == ["return_damaged", "receive"]
    removed = [t for b, t in got["boxes"].items() if got["classes"].get(b) == "removed"]
    assert removed == ["cond=repair<br/>branch=library (removed)"]
    grey = [a for a in got["arrows"] if a[3] == "#999"]
    assert grey == [("cond=loan<br/>branch=library", "return_damaged", "cond=repair<br/>branch=library (removed)",
                     "#999", True)]
    assert sorted(a[:3] for a in got["arrows"] if a[3] != "#999") == sorted(a[:3] for a in want["arrows"])


def test_picture_files_carry_the_same_texts_and_colours(project):
    project.flow_from(DATA / "planted" / "rental_naive.py", "rental")
    code, out = show(project.root)
    assert code == 0
    first = out.splitlines()[0]
    m = re.search(r"picture: (\S+\.png) \(also (\S+\.svg), (\S+\.mmd)\)", first)
    assert m, first
    png, svg, mmd = (project.root / x for x in m.groups())
    assert png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n" and png.stat().st_size > 5000
    assert mmd.read_text() == body(out) + "\n"
    root = ET.parse(svg).getroot()                                   # well-formed XML
    text = " ".join(t.strip() for t in root.itertext() if t.strip())
    for word in ("cond=repair", "branch=library (STUCK)", "transfer", "return_damaged", "repaired"):
        assert word in text
    raw = svg.read_text()
    assert "#fdd" in raw and "#c00" in raw


def test_without_a_renderer_the_first_line_says_so(project, monkeypatch, tmp_path):
    project.flow_from(DATA / "planted" / "rental_naive.py", "rental")
    bin_ = tmp_path / "bin"                                  # git, but no node
    bin_.mkdir()
    (bin_ / "git").symlink_to(shutil.which("git"))
    monkeypatch.setenv("PATH", str(bin_))
    code, out = show(project.root)
    first = out.splitlines()[0]
    assert code == 0
    assert "picture file not written: node is not on PATH" in first
    mmd = re.search(r"the Mermaid text is (\S+\.mmd)", first).group(1)
    assert (project.root / mmd).read_text() == body(out) + "\n"
    assert not list((cache_dir(project.root) / "pictures").glob("*.png"))


# ---------------------------------------------------------------------- the E7b models
def _e7b():
    for path in E7B:
        for model in load_machines(path):
            yield f"{path.parent.name}/{path.stem}", model


@pytest.mark.parametrize("name,model", list(_e7b()), ids=[n for n, _ in _e7b()])
def test_default_show_of_every_e7b_model_covers_its_conflict(name, model):
    report = check_model(Loaded(model, ()), Bounds())
    conflicts = diagram.order_conflicts(f for f in report.findings if f.cls == CONFLICT)
    subject = conflicts[0] if conflicts else None
    choice = diagram.choose_view(report, subject)
    d = choice.drawing
    assert d is not None, choice.refusal_lines(model.id)
    assert d.fits(diagram.MAX_BOXES, diagram.MAX_ARROWS)
    line = diagram.first_line(d)
    assert "; folded: " in line and f": {d.n_boxes} boxes" in line or f": {d.n_boxes} box" in line
    pic = parse(diagram.mermaid(d))
    scene = choice.scene
    if subject is None:
        fam, obj = scene.status()
        assert fam in d.view.name and set(d.view.keys) >= set(scene.keys_of(fam, obj))   # one object's status
    elif subject.kind == "NEVER REACHED":
        explained = subject.detail["explained"]
        assert explained and f"only with {explained[0]}" in " ".join(d.caption)
        dashed = [a for a in pic["arrows"] if a[3] == "#c00" and a[4]]
        assert dashed and any(subject.subject.split()[-1] in a[1] for a in dashed)   # the missing action, dashed red
    else:
        marked = [t for b, t in pic["boxes"].items() if pic["classes"].get(b) == "stuck"]
        assert marked and all("STUCK" in t for t in marked)
        proj = scene.space.projector(d.view.keys)
        shown = scene.shown(d.view)
        pairs = {(proj(a), proj(b)) for a, b in zip(scene.story, scene.story[1:])
                 if (shown is None or (a in shown and b in shown)) and proj(a) != proj(b)}
        red = [a for a in d.arrows if a.style == "red"]
        assert len(red) == len(pairs) > 0                                              # its whole path red
        if shown is not None and 0 not in shown:
            assert d.start[2]                                                           # the way in is the path's
    print(f"{name}: {len(scene.space)} states, full {diagram.full_size(scene.space)}, drawn {d.n_boxes}/{d.n_arrows}: "
          f"{line}")


# ---------------------------------------------------------------------- symmetry
def test_symmetric_view_of_one_tool_equals_the_unreduced_view(project):
    path = project.flow_from(DATA / "sym" / "workshop_r10.py", "workshop")
    loaded = load_model(path, project.root)
    reduced = check_model(loaded)
    plain_ = check_model(loaded, reduce=False)
    assert reduced.graph.sym is not None and len(reduced.graph.states) < len(plain_.graph.states)
    for a, b in ((reduced, plain_),):
        sa, sb = diagram.Space(a.graph), diagram.Space(b.graph)
        assert len(sa) == len(sb) == len(b.graph.states)
        assert set(sa.states) == set(sb.states)
        for keys in ((("cond", "T1"),), (("cond", "T1"), ("branch", "T1")), tuple(sa.keys)):
            pa, pb = sa.projector(keys), sb.projector(keys)
            ea = {(pa(u), pa(v)) for u, nxt in enumerate(sa.succ()) for v in nxt if pa(u) != pa(v)}
            eb = {(pb(u), pb(v)) for u, nxt in enumerate(sb.succ()) for v in nxt if pb(u) != pb(v)}
            assert ea == eb
    fa = next(f for f in reduced.findings if f.kind == "STUCK")
    fb = next(f for f in plain_.findings if f.kind == "STUCK")
    assert fa.id == fb.id
    da = diagram.choose_view(reduced, fa).drawing
    db = diagram.choose_view(plain_, fb).drawing
    assert da.view == db.view
    pa_, pb_ = parse(diagram.mermaid(da)), parse(diagram.mermaid(db))
    assert sorted(pa_["boxes"].values()) == sorted(pb_["boxes"].values())
    assert sorted(pa_["arrows"]) == sorted(pb_["arrows"])
    assert "T1 stands for any tool (interchangeable)" in da.caption


def test_replayed_paths_are_real_runs_under_renaming(project):
    path = project.flow_from(DATA / "sym" / "workshop_r10.py", "workshop")
    report = check_model(load_model(path, project.root))
    space = diagram.Space(report.graph)
    for f in report.findings:
        if not f.path:
            continue
        seq, names = space.replay(f.path)
        assert len(seq) == len(f.path) + 1 and names == [s.split("(")[0] for s in f.path]
        end = dict(zip(space.keys, space.states[seq[-1]]))
        state = ", ".join(f"{k[0]}[{k[1]}]={v!r}" for k, v in end.items() if v != space.inits[k])
        assert state == f.state


# ---------------------------------------------------------------------- refusal, options, NEVER REACHED
COUNTERS = '''
from flowguard.flow import Model, need
m = Model("dials")
for name in ("a", "b", "c"):
    m.field(name, range(10), 0)

@m.action(d=["a", "b", "c"])
def turn(s, d):
    s[d] = (s[d] + 1) % 10

MODEL = m
'''


def test_nothing_fits_lists_every_view_with_its_size_and_options(project):
    path = project.flow("dials", COUNTERS)
    report = check_model(load_model(path, project.root))
    assert len(report.graph.states) == 1000
    choice = diagram.choose_view(report)
    assert choice.drawing is None
    lines = choice.refusal_lines("dials")
    assert re.match(r"dials: no picture drawn: (the only view of what is under discussion is|all \d+ views of what is "
                    r"under discussion are) above the readable size of 12 boxes and 20 arrows", lines[0]), lines[0]
    assert "  python -m flowguard show dials --fields *: the whole state space, 1000 boxes, 3000 arrows" in lines
    # acceptance A6: a view that fits is never listed as above the readable size, and nothing drawn is exit 2
    fit = lines.index("Views that fit but leave out what is under discussion:")
    assert lines.index("  python -m flowguard show dials --fields a: a alone, 10 boxes, 10 arrows") > fit
    assert all(int(re.search(r"(\d+) boxes", x).group(1)) > 12 or int(re.search(r"(\d+) arrows", x).group(1)) > 20
               for x in lines[1:fit]), lines
    code, out = show(project.root, "dials")
    assert code == 2 and out.splitlines()[0] == lines[0]
    code, out = show(project.root, "dials", "--fields", "a")
    assert code == 0 and ": fields a: 10 boxes, 10 arrows; folded: 1,000 states merged into 10 boxes" in out
    code, out = show(project.root, "dials", "--fields", "a,b")
    assert code == 2 and "this view has 100 boxes and 200 arrows" in out.splitlines()[0]    # nothing drawn
    assert "  python -m flowguard show dials --fields a: a alone, 10 boxes, 10 arrows" in out.splitlines()
    code, out = show(project.root, "dials", "--fields", "a,b", "--max-boxes", "100", "--max-arrows", "200")
    assert code == 0 and ": fields a, b: 100 boxes, 200 arrows" in out.splitlines()[0]


def test_never_reached_value_without_explanation_is_a_dashed_box(project):
    project.kit()
    path = project.flow_from(DATA / "kit" / "workshop_naive.py", "workshop")
    report = check_model(load_model(path, project.root))
    f = next(f for f in report.findings if f.kind == "NEVER REACHED" and f.subject == "value cond[*] = 'transit'")
    assert f.cls == CONFLICT and f.detail["explained"] == []
    d = diagram.choose_view(report, f).drawing
    pic = parse(diagram.mermaid(d))
    assert pic["boxes"]["missing"] == "cond=transit (never reached)" and pic["classes"]["missing"] == "dashed"
    assert "no one-setting change reaches it" in diagram.first_line(d)


def test_contradiction_offering_state_is_red_with_the_refusal(project):
    project.kit()
    path = project.flow_from(DATA / "kit" / "workshop_naive.py", "workshop")
    report = check_model(load_model(path, project.root))
    f = next(f for f in report.findings if f.kind == "CONTRADICTION")
    d = diagram.choose_view(report, f).drawing
    pic = parse(diagram.mermaid(d))
    assert pic["boxes"]["refused"] == "repaired(t=#quot;T1#quot;) refused".replace("#quot;", "'")
    refusal = [a for a in pic["arrows"] if a[2] == pic["boxes"]["refused"]]
    assert refusal == [(refusal[0][0], "offered, refused: repairs only at main", pic["boxes"]["refused"], "#c00", True)]
    assert "(offered, refused)" in refusal[0][0]


def test_explicit_views_and_usage_errors(project):
    project.flow_from(DATA / "planted" / "rental_naive.py", "rental")
    code, out = show(project.root, "rental", "--story")
    assert code == 0 and "; the counterexample alone, the whole state space: 4 boxes, 3 arrows" in out.splitlines()[0]
    code, out = show(project.root, "rental", "--focus", "1", "--fields", "cond")
    assert code == 0 and "1 step around the dead end, fields cond[T1]" in out.splitlines()[0]
    assert "the way in is one dashed arrow" in out.splitlines()[0]
    code, out = show(project.root, "rental:T1")
    assert code == 0 and out.startswith("rental: STUCK")
    code, out = show(project.root, "nosuch")
    assert code == 2 and out == "nosuch: no such model (models: rental)\n"
    code, out = show(project.root, "rental", "--fields", "colour")
    assert code == 2 and "--fields: the model has no field 'colour' (fields: cond, branch)" in out
    code, out = show(project.root, "C-000000000000")
    assert code == 2 and out.startswith("no conflict C-000000000000 now (conflicts: C-")
    code, out = show(project.root, "--bogus")
    assert code == 2 and out.startswith("usage error: unrecognized arguments: --bogus")


def test_a_capped_show_never_presents_a_proven_conflict_as_absent(project):
    """G1 round 2 (show): a conflict a complete check stored is open; a show whose search is
    capped below it once printed "no conflict C-... now" (exit 2). It says the conflict is
    open, why it is not drawn, and exits 3 (UNKNOWN); the default show lists it too."""
    from checkrun import run_check
    project.flow_from(DATA / "planted" / "rental_naive.py", "rental")
    assert run_check(project.root).code == 1
    [entry] = json.loads((project.root / ".flowguard/conflicts.json").read_text())["conflicts"]
    cid = entry["id"]
    code, out = show(project.root, cid, "--max-states", "3")
    assert code == 3 and "no conflict" not in out, out
    assert out == (f"open, not drawn: {cid} STUCK rental: {entry['text']} (proven by an earlier complete check; "
                   f"this show's search is capped at 3 states and does not reach it)\n"), out
    code, out = show(project.root, "--max-states", "3")
    assert code == 3 and "nothing under discussion" not in out, out
    assert out.startswith(f"open, not drawn: {cid} STUCK rental: "), out
    code, out = show(project.root, cid)
    assert code == 0 and f"[{cid}]" in out.splitlines()[0]


def test_conflict_id_json_and_more_than_three(project):
    project.kit()
    project.flow_from(DATA / "kit" / "workshop_naive.py", "workshop")
    code, out = show(project.root, "--json")
    assert code == 0 and out.count("\n") == 1
    data = json.loads(out)
    assert [p["subject"] for p in data["pictures"]][:1] and len(data["pictures"]) == 3
    kinds = [p["first_line"].split(":")[1].split()[0] for p in data["pictures"]]
    assert kinds == ["STUCK", "BROKEN", "CONTRADICTION"]                      # dead ends first
    assert len(data["more"]) == 3 and all(m.startswith("python -m flowguard show C-") for m in data["more"])
    fid = data["more"][0].split()[-1]
    code, out = show(project.root, fid)
    assert code == 0 and f"[{fid}]" in out.splitlines()[0]


def test_nothing_under_discussion(project):
    project.flow_from(DATA / "planted" / "rental_fixed.py", "rental")
    code, out = show(project.root)
    assert code == 2 and out.startswith("nothing under discussion: no conflict, and the change cannot be computed "
                                        "without git; name a model (models: rental)")
    project.file(".gitignore", ".flowguard/cache/\n")
    project.commit()
    code, out = show(project.root)
    assert code == 2 and out.startswith("nothing under discussion: no conflict and no changed model")
    code, out = show(project.root, "rental")
    assert code == 0 and out.startswith("rental: cond of T1")
    (project.root / ".flowguard" / "flow" / "rental.py").unlink()
    code, out = show(project.root)
    assert code == 2 and "no flow models" in out


def test_before_a_revision_without_the_model_is_drawn_uncoloured(project):
    project.file(".gitignore", ".flowguard/cache/\n")
    project.file("README", "x\n")
    project.commit("empty")
    project.flow_from(DATA / "planted" / "rental_fixed.py", "rental")
    code, out = show(project.root, "rental", "--before", "HEAD")
    assert code == 0 and "new model: no before picture (.flowguard/flow/rental.py is not in HEAD)" in out
    assert "#080" not in out and "#999" not in out
    code, out = show(project.root, "rental", "--before", "nosuchrev")
    assert code == 2 and "unknown revision 'nosuchrev'" in out


# ---------------------------------------------------------------------- parts and pictures of check
def test_conflict_pictures_and_the_picture_part(project):
    project.kit()
    path = project.flow_from(DATA / "kit" / "workshop_naive.py", "workshop")
    report = check_model(load_model(path, project.root))
    pics = diagram.conflict_pictures(report, project.root)
    conflicts = [f for f in report.findings if f.cls == CONFLICT]
    assert [p[0] for p in pics] == [f.id for f in conflicts]
    for fid, line, files in pics:
        assert files[0] == f".flowguard/cache/flow/pictures/workshop-{fid[2:]}.mmd"
        assert all((project.root / x).is_file() for x in files)
        assert ("picture: " in line) == RENDERER
    spec = PartSpec("picture", "workshop", (("what", conflicts[0].id),))
    res = run_part(PartContext(project.root, spec, path, cache_dir(project.root)))
    assert res.kind == "picture" and res.findings == [] and res.info["subject_id"] == conflicts[0].id
    assert res.info["subject"] == conflicts[0].text.partition(": ")[0]
    assert res.info["files"][0] == pics[0][2][0] and set(res.writes) <= set(res.info["files"])
    assert all((project.root / x).is_file() for x in res.writes)
    again = run_part(PartContext(project.root, spec, path, cache_dir(project.root)))
    assert again.digest == res.digest and again.info["mermaid"] == res.info["mermaid"]


_SEED = """
import sys
from pathlib import Path
from flowguard.flow import diagram
from flowguard.flow.checks import check_model
from flowguard.flow.model import load_model
root, path = Path(sys.argv[1]), Path(sys.argv[2])
report = check_model(load_model(path, root))
for f in diagram.order_conflicts(f for f in report.findings if f.cls == "conflict"):
    print(diagram.mermaid(diagram.choose_view(report, f).drawing))
print(diagram.first_line(diagram.choose_view(report).drawing))
"""


def test_pictures_do_not_depend_on_hash_order(project):
    project.kit()
    path = project.flow_from(DATA / "kit" / "workshop_naive.py", "workshop")
    outs = []
    for seed in (0, 1, 2):
        env = {**os.environ, "PYTHONHASHSEED": str(seed), "PYTHONPATH": str(REPO)}
        res = subprocess.run([sys.executable, "-c", _SEED, str(project.root), str(path)], capture_output=True,
                             text=True, env=env, timeout=300, check=False)
        assert res.returncode == 0, res.stderr
        outs.append(res.stdout)
    assert outs[0] == outs[1] == outs[2] and outs[0].count("flowchart LR") == 6


def test_never_reached_action_without_explanation_is_named_in_the_picture():
    model, = load_machines(DATA / "golden" / "models" / "e7_mach_sonnet1_R9" / "model.py")
    report = check_model(Loaded(model, ()), Bounds())
    f = next(f for f in report.findings if f.subject == "action inspected_pass")
    assert f.cls == CONFLICT and f.detail["explained"] == []
    pic = parse(diagram.mermaid(diagram.choose_view(report, f).drawing))
    assert pic["boxes"]["missing"] == "action inspected_pass: never happens"
    assert pic["classes"]["missing"] == "refusal"


def test_before_with_a_conflict_keeps_the_red_path_and_greys_what_went(project):
    project.flow_from(DATA / "planted" / "rental_fixed.py", "rental")
    project.file(".gitignore", ".flowguard/cache/\n")
    project.commit("fixed")
    project.flow_from(DATA / "planted" / "rental_naive.py", "rental")
    code, out = show(project.root, "rental", "--before", "HEAD")
    assert code == 0 and out.startswith("rental: STUCK T1 stuck in cond='repair', branch='library'")
    pic = parse(body(out))
    assert sorted(a[1] for a in pic["arrows"] if a[3] == "#c00") == ["rent", "return_damaged", "transfer"]
    removed = [t for b, t in pic["boxes"].items() if pic["classes"].get(b) == "removed"]
    assert removed == ["cond=transit<br/>branch=library (removed)"]
    assert sorted(a[1] for a in pic["arrows"] if a[3] == "#999") == ["receive", "return_damaged"]
    code, out = show(project.root)                       # the default: the conflict picture, as check draws it
    assert code == 0 and "#999" not in out and ": 6 boxes, 9 arrows" in out.splitlines()[0]


def test_a_fallback_route_is_focused_where_the_second_route_is_used(project):
    """A route conflict with a path (FALLBACK ROUTE) focuses on where the second route is
    used; one without a path (DUPLICATE ROUTE) is offered no focus view at all, so no
    picture is ever an empty focus."""
    from flowguard.flow.routes import route_checks
    path = project.flow_from(DATA / "toy_flow" / "rental_planted.py", "rental")
    _, _, routes = route_checks(path, project.root, Bounds())
    report = check_model(load_model(path, project.root))
    fallback = next(f for f in routes.findings if f.kind == "FALLBACK ROUTE")
    choice = diagram.choose_view(report, fallback, request=diagram.Request(max_boxes=4, max_arrows=5))
    focus = [(v.name, nb) for v, nb, _ in choice.tried if v.kind == "focus"]
    assert [name for name, _ in focus] == [f"{k} step{'s' if k > 1 else ''} around where the second route is used, "
                                           "fields cond[T1], main_busy" for k in (3, 2, 1)]
    assert all(nb > 0 for _, nb in focus)
    duplicate = next(f for f in routes.findings if f.kind == "DUPLICATE ROUTE")
    choice = diagram.choose_view(report, duplicate)
    assert not [v for v, _, _ in choice.tried if v.kind == "focus"] and choice.drawing.n_boxes > 0
    assert "red: the arrows of the routes" in diagram.mermaid(choice.drawing)


# ---------------------------------------------------------------------- G7
def _kit_change(project, commit_fixed=False):
    project.kit()
    project.file(".gitignore", ".flowguard/cache/\n__pycache__/\n")
    project.flow_from(DATA / "kit" / "workshop_naive.py", "workshop")
    project.commit("naive R10")
    project.flow_from(DATA / "kit" / "workshop.py", "workshop")
    if commit_fixed:
        project.commit("R10: a tool due away from main travels to main first")


def test_a_change_with_two_tools_is_drawn_for_one_tool_in_green_and_grey(project):
    """G7: with two or more objects the change view narrows to one object, as conflict
    views do, and colours what the change adds and removes."""
    _kit_change(project)
    code, out = show(project.root)
    assert code == 0, out
    first = out.splitlines()[0]
    assert first.startswith("workshop: the change against HEAD: ") and "drawn for T1" in first
    assert "branch" in first.split(": ", 2)[2] and "cond" in first
    assert "[T2]" not in first.split("; folded")[0]
    got = parse(body(out))
    assert any(got["classes"].get(b) == "added" for b in got["boxes"]) or any(a[3] == "#080" for a in got["arrows"])
    assert any(a[3] == "#999" for a in got["arrows"]) or any(c == "removed" for c in got["classes"].values())


def _counts(first):
    m = re.search(r"(\d+) (?:steps?|arrows?) added \(green\), (\d+) (?:steps? |arrows? )?removed \(grey\)", first)
    return (int(m.group(1)), int(m.group(2))) if m else None


@pytest.mark.parametrize("argv", [(), ("--fields", "cond,branch", "--object", "T1")])
def test_the_change_head_counts_what_the_view_draws(project, argv):
    """#10 (round 2): the first line's green and grey counts are the green and grey arrows of
    the drawn view (a view that leaves the counters out once said 36 steps added and drew 2);
    the whole model's counts follow, said as such when they differ."""
    _kit_change(project)
    code, out = show(project.root, *argv)
    assert code == 0, out
    first = out.splitlines()[0]
    got = parse(body(out))
    green = sum(1 for a in got["arrows"] if a[3] == "#080")
    grey = sum(1 for a in got["arrows"] if a[3] == "#999")
    assert _counts(first) == (green, grey), first
    if "in this view" in first:
        assert re.search(r"in the whole model \d+ steps? added, \d+ removed", first), first


def test_the_change_head_writes_every_count_the_same_way():
    """A large change said "41,064 steps added, 41064 removed": every count of the first line
    is written with thousands separators, in the view and in the whole model."""
    from types import SimpleNamespace
    scene = SimpleNamespace(change=SimpleNamespace(added=41_064, removed=41_064, unknown=(), rev="HEAD"),
                            change_drawn=" (drawn for T1 of T1, T2)")
    head = diagram.Scene.change_head(scene, 3, 12_345)
    assert "3 arrows added (green), 12,345 removed (grey) in this view" in head, head
    assert ("in the whole model 41,064 steps added, 41,064 removed (a step is one action from one full state, so a "
            "new or wider field multiplies them) (drawn for T1 of T1, T2)") in head, head
    whole = diagram.Scene.change_head(scene, None, None)       # no view drawn: the whole model alone, said so
    assert whole == ("the change against HEAD: in the whole model 41,064 steps added, 41,064 removed (a step is one "
                     "action from one full state, so a new or wider field multiplies them) (drawn for T1 of T1, T2)"), whole
    assert diagram.Scene.change_head(scene, 41_064, 41_064).startswith(
        "the change against HEAD: 41,064 arrows added (green), 41,064 removed (grey) in this view; in the whole model")


def test_a_capped_change_claims_no_removed_step(project):
    """#10 (round 2): when the search of the new model is capped, a step of the old model it
    did not reach is no removed step; the change says removed steps are UNKNOWN and draws no
    grey arrow for them."""
    _kit_change(project)
    code, out = show(project.root, "--max-states", "40")
    first = out.splitlines()[0]
    assert first.startswith("workshop: CAPPED at 40 states"), first
    got = parse(body(out))
    assert not any(a[3] == "#999" for a in got["arrows"]) and not any(c == "removed" for c in got["classes"].values())
    assert "removed steps UNKNOWN" in first, first


def test_a_model_without_conflict_is_drawn_with_its_latest_change(project):
    """G7: `show MODEL` of a model with no conflict draws the fields its latest change
    touched (the model's last commit against its parent), not the status field alone."""
    _kit_change(project, commit_fixed=True)
    code, out = show(project.root, "workshop")
    assert code == 0, out
    first = out.splitlines()[0]
    assert "the change against" in first and "R10: a tool due away from main travels to main first" in first
    assert "branch" in first.split("; folded")[0]


def test_a_capped_picture_says_so_in_its_first_line(project):
    """G7: CAPPED is in the first line the AI reads, not only in the picture's caption."""
    project.flow_from(DATA / "planted" / "rental_naive.py", "rental")
    code, out = show(project.root, "rental", "--max-states", "4")
    first = out.splitlines()[0]
    assert first.startswith("rental: CAPPED at 4 states: only the explored part; "), first


def test_an_explanation_never_says_reached_and_unknown_for_one_setting(project):
    """G7: a variant that reaches an item is not also listed as capped (UNKNOWN) for it; it
    stays UNKNOWN only for the items it did not reach before its cap."""
    project.flow("lim", '''
from flowguard.flow import Model, need
m = Model("lim")
S = m.settings
m.setting("limit", 2, vary=[40])
m.field("n", range(0, 50), 0)
m.field("flag", [False, True], False, source="R1")

@m.action()
def inc(s):
    need(s["n"] < S["limit"], "at the limit")
    s["n"] += 1

@m.action(source="R1")
def big(s):
    need(s["n"] >= 3, "too small")
    s["flag"] = True

@m.action(source="R2")
def never(s):
    need(False, "never")
MODEL = m
''')
    report = check_model(load_model(project.root / ".flowguard/flow/lim.py", project.root), Bounds(10))
    by = {f.subject: f.detail for f in report.findings if f.kind == "NEVER REACHED"}
    assert by["action big"]["explained"] == ["limit=40"] and by["action big"]["capped"] == []
    assert by["action never"]["explained"] == [] and by["action never"]["capped"] == ["limit=40"]


CANCEL = '''

@m.action(b=BOOKS, source="R2")
def cancel(s, b):
    need(s["where", b] == "held", "not held")
    s["where", b], s["nights", b] = "shelf", 0
'''


def test_an_arrow_that_only_lost_steps_is_no_added_arrow(project):
    """G7 round 4: a change that only removes `cancel` printed "1 arrow added (green), 1
    removed (grey) in this view" and drew 'night (no longer: cancel)' green: an arrow whose
    labels changed was taken as added even when it only lost some. Such an arrow is drawn
    as changed (its own colour, never green) and counted as changed in the first line."""
    desk = DATA / "desk"
    shutil.copytree(desk / "app", project.root / "app")
    for p in (desk / "requests").glob("*.md"):
        from flowguard.map.requests import store_request
        store_request(project.root, p.read_bytes(), identifier=p.stem)
    project.file(".gitignore", ".flowguard/cache/\n__pycache__/\n")
    text = (desk / "desk.py").read_text()
    anchor = '''    s["where", b], s["nights", b] = "held", 0
'''
    assert text.count(anchor) == 1
    path = project.flow("desk", text.replace(anchor, anchor + CANCEL))
    project.commit("cancel a hold")
    path.write_text(text)                                        # the change removes cancel again
    code, out = show(project.root)
    assert code == 0, out
    first = out.splitlines()[0]
    got = parse(body(out))
    green = [a for a in got["arrows"] if a[3] == "#080"]
    assert not green, green
    changed = [a for a in got["arrows"] if "(no longer: cancel)" in a[1]]
    assert changed and all(a[3] == diagram.CHANGED for a in changed), got["arrows"]
    grey = [a for a in got["arrows"] if a[3] == "#999"]
    assert "0 arrows added (green), " in first, first
    assert f"{len(grey)} removed (grey), {len(changed)} with fewer steps (orange) in this view" in first, first


COME_BACK = '''
from flowguard.flow import Model, need
m = Model("ring")
m.field("x", range(0, 5), 0)

@m.action()
def step(s):
    need(s["x"] < 4, "at the end")
    s["x"] += 1

@m.action()
def back(s):
    need(s["x"] == 4, "not at the end")
    s["x"] = 1
m.always("never at the end", lambda s: s["x"] != 4)
MODEL = m
'''


def test_a_broken_rule_picture_draws_its_red_path_unbroken_into_the_last_box(project):
    """Acceptance A6 (#6): in a window around the breaking state that the counterexample enters,
    leaves and enters again (x=1 is next to x=4 by back), the dashed way in went to where the
    path first entered (x=1) and the red path ended without its way in; the way in now goes to
    the last entry (x=3) and the red path runs from there into the final box."""
    path = project.flow("ring", COME_BACK)
    report = check_model(load_model(path, project.root))
    [f] = [f for f in report.findings if f.kind == "BROKEN"]
    assert f.path == ("step()",) * 4
    d = diagram.choose_view(report, f, request=diagram.Request(focus=1)).drawing
    pic = parse(diagram.mermaid(d))
    assert pic["start"].startswith("x=3"), pic
    red = [(a, b) for a, _, b, style, _ in pic["arrows"] if style == "#c00"]
    assert [(plain(a), b) for a, b in red] == [("x=3", "x=4 (rule broken)")], pic["arrows"]
    assert "3 steps: step, step, step" in diagram.mermaid(d)


def test_show_counts_states_the_way_check_does(project):
    """Acceptance A6 (#5): check counted 25,651 states (up to renaming) and show 51,076 for the
    same model; a picture of interchangeable objects now says it draws every renaming and how
    many states that is up to renaming, the number check gives."""
    project.kit()
    path = project.flow_from(DATA / "kit" / "workshop_naive.py", "workshop")
    report = check_model(load_model(path, project.root))
    assert report.graph.sym is not None
    f = next(f for f in report.findings if f.kind == "STUCK")
    d = diagram.choose_view(report, f, request=diagram.Request(focus=1)).drawing
    n = len(report.graph.states)
    assert f"with every renaming ({n:,} up to renaming, as check counts them)" in diagram.mermaid(d)
    assert f"with every renaming ({n:,} up to renaming, as check counts them)" in diagram.first_line(d)
