"""The project around the models: root, model files, request lines, conflicts.json,
manifests, git (changed models, files at a revision), overlapping views; and the parts."""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from flowguard.flow import parts
from flowguard.flow.checks import WARNING
from flowguard.flow.model import load_model
from flowguard.flow.parts import ENGINE_DIGEST, PartContext, PartResult, PartSpec, part_digest, run_part
from flowguard.flow.project import (ProjectError, cache_dir, changed_models, conflict_entry, export_at,
                                     find_root, model_files, new_and_open, overlaps, read_conflicts,
                                     read_manifest, request_line, request_lines, resolve_models,
                                     write_conflicts, write_manifest)

from conftest import DATA, REPO

KIT = DATA / "kit"


def test_find_root_and_model_files(project):
    project.kit().flow_from(KIT / "workshop.py")
    project.flow("_helpers", "X = 1\n")
    (project.root / "deep" / "er").mkdir(parents=True)
    assert find_root(project.root / "deep" / "er") == project.root.resolve()
    assert [p.name for p in model_files(project.root)] == ["workshop.py"]
    with pytest.raises(ProjectError, match="not a FlowGuard project"):
        find_root(project.root.parent)


def test_models_are_named_by_id_or_by_a_path_in_the_flow_directory(project, monkeypatch):
    project.kit().flow_from(KIT / "workshop.py")
    monkeypatch.chdir(project.root)
    assert resolve_models(project.root, ["workshop"]) == model_files(project.root)
    assert resolve_models(project.root, [".flowguard/flow/workshop.py"]) == model_files(project.root)
    project.file("elsewhere/m.py", "MODEL = None\n")
    with pytest.raises(ProjectError, match="models live in .flowguard/flow/"):
        resolve_models(project.root, ["elsewhere/m.py"])


def test_request_lines(project):
    project.kit()
    assert request_line(project.root, "R10") == "Repairs are done only at the main branch."
    assert request_line(project.root, "R4") == "Members rent tools from the shelf of a branch."
    assert request_line(project.root, "R99") is None
    project.request("R5", "\n\n" + "x" * 150 + "\n")
    assert len(request_line(project.root, "R5")) == 100
    assert request_lines(project.root, ("R10", "R4", "R99")) == [
        ("R4", "Members rent tools from the shelf of a branch."), ("R10", "Repairs are done only at the main branch."),
        ("R99", "(not a stored request)")]
    assert request_lines(project.root, ()) == [("", "the AI's own")]


@pytest.mark.parametrize("words,quote", [
    ("# Request\n\nKeep existing loans usable.\n", "Keep existing loans usable."),
    ("# Request\n\n## Rules\n\n- Members can return a loan.\n", "- Members can return a loan."),
    ("# Keep existing loans usable\n", "# Keep existing loans usable"),
    ("\n\n", ""),
])
def test_request_quote_prefers_words_over_headings_without_editing_the_request(project, words, quote):
    stored = project.request("RQuote", words)
    before = stored.read_bytes()
    assert request_line(project.root, "RQuote") == quote
    assert stored.read_bytes() == before


def test_conflicts_json_is_deterministic_and_tells_new_from_open(project):
    from flowguard.flow.checks import check_model
    project.kit().flow_from(KIT / "workshop_naive.py")
    report = check_model(load_model(project.root / ".flowguard/flow/workshop_naive.py", project.root))
    entries = [conflict_entry(f) for f in report.findings if f.cls == "conflict"]
    data = {"engine": ENGINE_DIGEST, "tree": "t", "complete": True, "conflicts": list(reversed(entries)),
            "unknown": [], "warnings": 0}
    assert read_conflicts(project.root) is None
    new, open_ = new_and_open(None, [e["id"] for e in entries])
    assert (len(new), open_) == (len(entries), [])
    write_conflicts(project.root, data)
    first = (project.root / ".flowguard/conflicts.json").read_bytes()
    write_conflicts(project.root, dict(data, conflicts=entries))      # another order, same file
    assert (project.root / ".flowguard/conflicts.json").read_bytes() == first
    previous = read_conflicts(project.root)
    new, open_ = new_and_open(previous, [e["id"] for e in entries] + ["C-000000000000"])
    assert new == ["C-000000000000"] and len(open_) == len(entries)
    assert b"time" not in first


def test_manifests_live_in_the_cache(project):
    write_manifest(project.root, "m", ["b.py", "a.py"])
    assert read_manifest(project.root, "m") == ["a.py", "b.py"]
    assert (cache_dir(project.root) / "manifests" / "m.json").is_file()
    assert read_manifest(project.root, "other") is None


def test_changed_models_and_files_at_a_revision(project, tmp_path):
    project.kit().flow_from(KIT / "workshop_naive.py", "workshop")
    project.flow_from(DATA / "planted" / "tool_life.py")
    write_manifest(project.root, "workshop", ["counter/config.py", ".flowguard/flow/workshop.py"])
    (project.root / ".gitignore").write_text(".flowguard/cache/\n")
    project.commit()
    assert changed_models(project.root) == []
    (project.root / "counter/config.py").write_text((project.root / "counter/config.py").read_text() + "\n")
    assert [p.stem for p in changed_models(project.root)] == ["workshop"]       # through its manifest
    project.flow_from(KIT / "workshop.py", "workshop")
    project.flow_from(DATA / "planted" / "rental_naive.py", "new_model")
    assert [p.stem for p in changed_models(project.root)] == ["new_model", "workshop"]
    dest = tmp_path / "old"
    export_at(project.root, "HEAD", [".flowguard/flow/workshop.py", ".flowguard/flow/new_model.py",
                                     "counter/config.py"], dest)
    assert (dest / ".flowguard/flow/workshop.py").read_text() == (KIT / "workshop_naive.py").read_text()
    assert not (dest / ".flowguard/flow/new_model.py").exists()                # did not exist at HEAD
    with pytest.raises(ProjectError, match="unknown revision"):
        export_at(project.root, "nope", ["counter/config.py"], dest)


def test_without_git_nothing_counts_as_changed(project):
    project.kit().flow_from(KIT / "workshop.py")
    with pytest.raises(ProjectError, match="not a git repository"):
        changed_models(project.root)


def test_overlapping_views_warn_on_each_model(project):
    project.kit().flow_from(KIT / "workshop.py")
    text = (KIT / "workshop.py").read_text().replace('Model("workshop"', 'Model("maintenance"')
    project.flow("maintenance", text)
    project.flow_from(DATA / "planted" / "tool_life.py")         # covers nothing: no overlap
    flow = project.root / ".flowguard/flow"
    loaded = [load_model(flow / f"{n}.py", project.root) for n in ("workshop", "maintenance", "tool_life")]
    found = overlaps(loaded)
    assert {(f.model, f.subject) for f in found} == {
        (a, f"field '{fam}' is also declared by {b}") for a, b in (("workshop", "maintenance"), ("maintenance", "workshop"))
        for fam in ("branch", "cond", "rentals")}
    assert all(f.cls == WARNING and f.kind == "OVERLAP" for f in found)


# ---------------------------------------------------------------- parts
def core(project, name, **options):
    path = project.root / ".flowguard/flow" / f"{name}.py"
    spec = PartSpec("core", name, tuple(sorted(options.items())))
    seen = []
    result = run_part(PartContext(project.root, spec, path, cache_dir(project.root), seen.append))
    return result, spec, seen


def test_the_core_part_runs_the_checks(project):
    project.kit().flow_from(KIT / "workshop_naive.py")
    result, spec, _ = core(project, "workshop_naive")
    assert result.complete and result.kind == "core"
    assert [f["kind"] for f in result.findings][:1] == ["STUCK"]
    assert result.info["reach_line"].startswith("workshop_naive: complete, 171 states")
    assert "counter/config.py" in result.reads
    conflicts = [f["id"][2:] for f in result.findings if f["cls"] == "conflict"]
    assert {w.rsplit("/", 1)[1].split(".")[0] for w in result.writes} == {f"workshop_naive-{c}" for c in conflicts}
    assert all((project.root / w).is_file() for w in result.writes)            # its pictures (design 6.4)
    assert result.digest == part_digest(project.root, spec, result.reads)
    assert PartResult.from_json(json.loads(json.dumps(result.to_json()))) == result


def test_the_digest_follows_every_read_file_and_the_options(project):
    project.kit().flow_from(KIT / "workshop.py")
    first, spec, _ = core(project, "workshop")
    again, _, _ = core(project, "workshop")
    assert again.digest == first.digest
    capped, _, _ = core(project, "workshop", max_states=50)
    assert capped.digest != first.digest and not capped.complete
    (project.root / "counter/config.py").write_text((project.root / "counter/config.py").read_text() + "# x\n")
    assert core(project, "workshop")[0].digest != first.digest


def test_a_model_that_fails_to_load_is_one_model_error(project):
    project.kit()
    project.flow("bad", (KIT / "workshop.py").read_text().replace('m.setting("maintain_every"', 'm.setting("nope"'))
    result, _, _ = core(project, "bad")
    assert [f["kind"] for f in result.findings] == ["MODEL ERROR"]
    assert "has no attribute 'nope'" in result.findings[0]["text"]
    assert "counter/config.py" in result.reads                 # fixing the config re-runs it
    assert result.info == {"loaded": False}


def test_progress_is_reported_while_exploring(project):
    project.flow("dials", """
from flowguard.flow import Model
m = Model("dials")
m.field("pos", range(0, 10), 0, over=["a", "b", "c", "d"])

@m.action(d=["a", "b", "c", "d"])
def turn(s, d):
    s["pos", d] = (s["pos", d] + 1) % 10
MODEL = m
""")
    result, _, seen = core(project, "dials")
    assert result.complete and seen
    assert seen[0] == {"model": "dials", "kind": "core", "states": seen[0]["states"]}
    assert [d["states"] for d in seen] == sorted(d["states"] for d in seen)


def test_registry_and_engine_digest():
    # every part module is registered, whatever was imported first; show's pictures are never planned by a check
    assert parts.kinds() == ["core", "routes"]
    assert parts.kinds(full=True) == ["core", "routes", "mutate"]
    assert "picture" in parts._registry()
    with pytest.raises(ValueError):
        parts.register("core", parts.core_part)
    code = "from flowguard.flow.parts import ENGINE_DIGEST; print(ENGINE_DIGEST)"
    env = {**os.environ, "PYTHONPATH": str(REPO), "PYTHONHASHSEED": "1"}
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, check=True)
    assert out.stdout.strip() == ENGINE_DIGEST


@pytest.mark.parametrize("body", [{}, {"models": {}, "unknown": []}])
def test_conflicts_record_cannot_omit_its_conflicts(project, body):
    from flowguard.flow.project import ConflictsUnreadable
    project.file(".flowguard/conflicts.json", json.dumps(body))
    with pytest.raises(ConflictsUnreadable, match="conflicts"):
        read_conflicts(project.root)


def test_conflicts_directory_is_unreadable_not_an_absent_record(project):
    from flowguard.flow.project import ConflictsUnreadable
    (project.root / ".flowguard/conflicts.json").mkdir()
    with pytest.raises(ConflictsUnreadable, match="not a regular file"):
        read_conflicts(project.root)


def test_atomic_record_replacement_and_concurrent_readers(tmp_path):
    """A record stays readable while another thread publishes complete replacements."""
    import threading
    from flowguard.flow._process import read_text
    from flowguard.flow.project import _atomic_write
    path = tmp_path / "record.json"
    _atomic_write(path, '{"generation": 0}\n')
    ready, stop = threading.Event(), threading.Event()
    errors, observed = [], []

    def read_records():
        try:
            observed.append(json.loads(read_text(path))["generation"])
            ready.set()
            while not stop.is_set():
                observed.append(json.loads(read_text(path))["generation"])
        except BaseException as error:
            errors.append(error)
            ready.set()

    reader = threading.Thread(target=read_records, daemon=True)
    reader.start()
    try:
        assert ready.wait(10), "the reader never started"
        for generation in range(1, 501):
            _atomic_write(path, json.dumps({"generation": generation}) + "\n")
    finally:
        stop.set()
        reader.join(10)
    assert not reader.is_alive(), "the record reader did not finish"
    if errors:
        raise errors[0]
    assert observed and all(0 <= value <= 500 for value in observed)
    assert json.loads(read_text(path))["generation"] == 500
