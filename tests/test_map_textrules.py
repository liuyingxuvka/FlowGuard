"""Text rules expose literal and workflow evidence without inventing semantics."""

import json
import subprocess

import pytest

from flowguard.map.derived import source_names, where
from flowguard.map.discover import discover_inventory
from flowguard.map.inventory import build_inventory
from flowguard.map.mapfile import SCHEMA
from flowguard.map.textrules import _literal_groups, render, report, select


FACT_KEYS = {
    "texts", "references", "literal_groups", "workflow_groups", "unknown",
    "summary", "source", "revision",
}


def write(root, path, text):
    destination = root / path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")


def git(root, *arguments):
    return subprocess.check_output(
        ["git", "-C", str(root), *arguments], stderr=subprocess.PIPE,
    ).decode().strip()


def repository(root):
    git(root, "init", "-q")
    git(root, "config", "user.name", "Fixture")
    git(root, "config", "user.email", "fixture@example.invalid")


def facts(root):
    inventory = build_inventory(root, [], with_bodies=False, write_cache=False)
    return inventory, discover_inventory(root, inventory, write_cache=False)


def snapshot(root):
    return {
        path.relative_to(root).as_posix(): None if path.is_dir() else path.read_bytes()
        for path in root.rglob("*")
    }


def text_for(result, path):
    return [row for row in result["texts"] if row["path"] == path]


def test_ordinary_identifier_reference_stays_unknown_without_source(tmp_path):
    write(tmp_path, "core.py", "def current_name(): return 1\n")
    sentence = "Before editing, you MUST check foo_old against the current implementation."
    write(tmp_path, "AGENTS.md", sentence + "\n")

    result = report(tmp_path)

    assert FACT_KEYS <= result.keys()
    assert any(sentence in row["text"] for row in text_for(result, "AGENTS.md"))
    reference, = [row for row in result["references"] if row["name"] == "foo_old"]
    assert reference["path"] == "AGENTS.md" and reference["line"] == 1
    assert "unknown" in reference["state"].lower()
    assert not reference["locations"]
    assert not reference["placement"]["owners"]


def test_global_spelling_matches_do_not_establish_same_owner(tmp_path):
    write(tmp_path, "left.py", "def shared_name(): return 'left'\n")
    write(tmp_path, "right.py", "def shared_name(): return 'right'\n")
    write(tmp_path, "AGENTS.md", "Before editing, you MUST preserve `shared_name`.\n")

    result = report(tmp_path)

    reference, = [row for row in result["references"] if row["name"] == "shared_name"]
    assert {row["path"] for row in reference["locations"]} == {"left.py", "right.py"}
    # Candidate locations are useful evidence; neither spelling proves ownership
    # of an unplaced instruction, or licenses an arbitrary first candidate.
    assert "unknown" in reference["placement"]["state"].lower()
    assert not reference["placement"]["owners"]
    assert not reference["placement"]["functions"]
    for row in text_for(result, "AGENTS.md"):
        assert not row["placement"]["owners"]


def test_code_ignore_does_not_hide_normative_docs_or_declared_model_sources(tmp_path):
    write(tmp_path, ".flowguard/map.json", json.dumps({
        "schema": SCHEMA, "components": [], "flows": [], "ignore": ["docs/**"],
    }))
    write(tmp_path, "docs/architecture.md", "The `former_model` checks the selected request.\n")
    write(tmp_path, ".flowguard/models/current_model.py", '''MODEL_ID = "current_model"
raise RuntimeError("static text reporting must not import a model")
def build_explorer(): return None
''')
    write(tmp_path, "core.py", "def current_name(): return 1\n")
    before = snapshot(tmp_path)

    result = report(tmp_path)

    assert text_for(result, "docs/architecture.md")
    reference, = [row for row in result["references"] if row["name"] == "former_model"]
    assert "not found" in reference["state"] and "unknown" in reference["placement"]["state"]
    assert not reference["locations"] and not reference["placement"]["functions"]
    assert any(row["path"] == ".flowguard/models/current_model.py" and row["name"] == "current_model"
               for row in result["code_literals"])
    assert snapshot(tmp_path) == before


def test_seven_repair_variants_keep_their_words_and_only_share_a_literal(tmp_path):
    common = "stop and return the artifact with the audit note"
    variants = {
        "references/routes/academic.md": "If a revision round fixes none of the reported defects, " + common + ".",
        "references/routes/fiction.md": "If a revision round fixes none of the reported defects, " + common + ".",
        "references/routes/investigation.md": "If a revision round fixes none of the reported defects, " + common + ".",
        "references/routes/travel.md": "If a revision round fixes none of the reported defects, " + common + ".",
        "references/shared/reader-chain.md": "When a repair round resolves none of the actual defects, " + common + ".",
        "references/shared/closure.md": "After an ineffective repair round, " + common + ".",
        "routes/fiction/references/closure-report.md": "When no further repair is warranted, " + common + ".",
    }
    for path, sentence in variants.items():
        write(tmp_path, path, sentence + "\n")

    result = report(tmp_path)

    for path, sentence in variants.items():
        assert any(sentence in row["text"] for row in text_for(result, path))
    group = next(
        row for row in result["literal_groups"]
        if set(variants) <= {hit["path"] for hit in row["occurrences"]}
        and common in row["fragment"]
    )
    assert group["token_count"] >= len(common.split())
    assert group["relation"] == "literal occurrence only"
    assert all(row["relation"] == "literal occurrence only" for row in result["literal_groups"])
    text_ids = {row["id"] for row in result["texts"]}
    assert all(hit["source"] in text_ids for hit in group["occurrences"])
    assert all(hit["line"] >= 1 and hit["end_line"] >= hit["line"] for hit in group["occurrences"])


TARGET_PROGRAM = '''import argparse
def check_target():
    return 0
def build_parser():
    parser = argparse.ArgumentParser(prog="python -m flowguard target")
    commands = parser.add_subparsers(dest="command")
    check = commands.add_parser("check")
    check.set_defaults(run=check_target)
    return parser
def main(argv=None):
    options = build_parser().parse_args(argv)
    return options.run()
'''


def test_full_command_groups_real_handler_but_preserves_different_instructions(tmp_path):
    write(tmp_path, "flowguard/__init__.py", "")
    write(tmp_path, "flowguard/map/__init__.py", "")
    write(tmp_path, "flowguard/map/target.py", TARGET_PROGRAM)
    write(tmp_path, "flowguard/__main__.py", '''import sys
from flowguard.map.target import main as target_main
def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if args[0] == "target":
        return target_main(args[1:])
''')
    template_rule = "Run python -m flowguard target check. Require EXPECTED GAP and no ERROR."
    skill_rule = "Run `python -m flowguard target check`. Require `EXPECTED GAP`, except moved rules only may return NO GAP."
    write(tmp_path, "flowguard/templates.py", "GUIDANCE = " + repr(template_rule) + "\n")
    write(tmp_path, ".agents/skills/flowguard/SKILL.md", skill_rule + "\n")

    result = report(tmp_path)

    template_text = next(row for row in text_for(result, "flowguard/templates.py") if template_rule in row["text"])
    skill_text = next(row for row in text_for(result, ".agents/skills/flowguard/SKILL.md") if skill_rule in row["text"])
    group = next(row for row in result["workflow_groups"] if row["command"] == "python -m flowguard target check")
    assert "flowguard/map/target.py#check_target" in group["functions"]
    assert {template_text["id"], skill_text["id"]} <= set(group["sources"])
    assert group["evidence"]
    assert "unknown" not in group["state"].lower()
    selected = select(result, "group:" + group["id"])
    assert {template_text["id"], skill_text["id"]} <= {row["id"] for row in selected["texts"]}
    assert selected["workflow_groups"] == [group]
    file_selected = select(result, ".agents/skills/flowguard/SKILL.md")
    assert {"id": group["id"], "selector": "group:" + group["id"], "command": group["command"], "count": len(group["sources"])} in file_selected["related_groups"]
    assert "group:" + group["id"] in render(select(result, "text:" + group["command"]))
    # Output labels are prose, with or without Markdown markup, not missing APIs.
    assert not any(
        row["name"] in {"EXPECTED", "GAP", "EXPECTED GAP", "NO GAP", "ERROR"}
        and ("missing" in row["state"].lower() or "not found" in row["state"].lower())
        for row in result["references"]
    )
    assert "equivalent" not in group and "contradiction" not in group


def test_report_and_compact_render_are_read_only_and_full_is_explicit(tmp_path):
    sentence = "You MUST preserve the singular ultramarine instruction when adapting this deliberately long local policy."
    write(tmp_path, "AGENTS.md", sentence + "\n")
    write(tmp_path, "core.py", "def current_name(): return 1\n")
    before = snapshot(tmp_path)

    result = report(tmp_path)
    human = render(result)
    compact = render(result, as_json=True)
    full = json.loads(render(result, as_json=True, full=True))

    assert FACT_KEYS <= result.keys()
    assert sentence not in human and sentence not in compact
    for key in FACT_KEYS:
        assert full[key] == result[key]
    for row in result["texts"]:
        assert {"id", "path", "line", "end_line", "text", "fingerprint", "placement", "provenance"} <= row.keys()
        assert {"state", "owners", "functions"} <= row["placement"].keys()
        assert {"state", "origins"} <= row["provenance"].keys()
    assert snapshot(tmp_path) == before


def test_history_reads_blobs_despite_export_ignore_and_discards_current_indices(tmp_path):
    repository(tmp_path)
    write(tmp_path, "core.py", "def old_name(): return 1\n")
    write(tmp_path, "AGENTS.md", "Before editing, you MUST preserve `old_name`.\n")
    write(tmp_path, ".gitattributes", "core.py export-ignore\nAGENTS.md export-ignore\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-qm", "old public tree")
    old_revision = git(tmp_path, "rev-parse", "HEAD")
    git(tmp_path, "tag", "old")
    write(tmp_path, "core.py", "def new_name(): return 2\n")
    write(tmp_path, "AGENTS.md", "Before editing, you MUST preserve `new_name`.\n")
    inv, raw = facts(tmp_path)
    before = snapshot(tmp_path)

    result = report(tmp_path, inv=inv, raw=raw, at="old")

    assert result["revision"] == old_revision
    assert any("old_name" in row["text"] for row in text_for(result, "AGENTS.md"))
    assert not any("new_name" in row["text"] for row in result["texts"])
    reference, = [row for row in result["references"] if row["name"] == "old_name"]
    assert any(row["path"] == "core.py" for row in reference["locations"])
    assert not any(row["name"] == "new_name" for row in result["references"])
    assert snapshot(tmp_path) == before


def test_fingerprints_normalize_newlines_and_origins_need_real_blame(tmp_path):
    lf, crlf = tmp_path / "lf", tmp_path / "crlf"
    lf.mkdir()
    crlf.mkdir()
    policy = "You MUST preserve the public call.\nYou MUST keep the recorded result.\n"
    (lf / "AGENTS.md").write_bytes(policy.encode())
    (crlf / "AGENTS.md").write_bytes(policy.replace("\n", "\r\n").encode())

    left = report(lf)
    right = report(crlf)

    assert left["texts"] and right["texts"]
    assert [row["fingerprint"] for row in left["texts"]] == [row["fingerprint"] for row in right["texts"]]
    for row in right["texts"]:
        assert "unknown" in row["provenance"]["state"].lower()
        assert not row["provenance"]["origins"]

    repository(lf)
    git(lf, "add", ".")
    git(lf, "commit", "-qm", "recorded policy")
    revision = git(lf, "rev-parse", "HEAD")
    recorded = report(lf)
    assert [row["fingerprint"] for row in recorded["texts"]] == [row["fingerprint"] for row in left["texts"]]
    for row in recorded["texts"]:
        assert revision in json.dumps(row["provenance"]["origins"])


def test_selected_originals_keep_complete_text_and_provenance_without_rescanning(tmp_path):
    repository(tmp_path)
    original = "You MUST preserve " + " ".join("word%d" % index for index in range(45)) + "."
    extra = "\n\n".join(("You MUST preserve amber bronze copper.", "You MUST keep violet indigo azure.", "You MUST return north south west."))
    write(tmp_path, "left.md", original + "\n\nYou MUST retain the independent second passage.\n\n" + extra + "\n")
    write(tmp_path, "right.md", original + "\n\n" + extra + "\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-qm", "record original text")
    revision = git(tmp_path, "rev-parse", "HEAD")
    result = report(tmp_path)
    group = next(row for row in result["literal_groups"] if row["token_count"] > 40)
    compact = json.loads(render(result, as_json=True))
    assert compact["literal_groups"][0]["selector"] == "group:" + group["id"]
    assert original not in render(result)
    assert compact["unexpanded"]["texts"] == 9
    # Selecting saved facts must not depend on a later working-tree edit.
    write(tmp_path, "left.md", "Unrelated replacement.\n")
    selected = select(result, "group:" + group["id"])
    assert len(selected["texts"]) == 2
    assert all(row["text"] == original for row in selected["texts"])
    assert all(revision in json.dumps(row["provenance"]["origins"]) for row in selected["texts"])
    assert original in render(selected)
    assert json.loads(render(selected, as_json=True))["texts"] == selected["texts"]
    identifier = selected["texts"][0]["id"]
    assert select(result, "source:" + identifier)["texts"] == [selected["texts"][0]]
    assert len(select(result, "left.md")["texts"]) == 5
    visible = {row["id"] for row in compact["literal_groups"]}
    hidden = next(row for row in result["literal_groups"] if row["id"] not in visible)
    hit = hidden["occurrences"][0]
    file_selected = select(result, hit["path"])
    summary = next(row for row in file_selected["related_groups"] if row["id"] == hidden["id"])
    assert summary["count"] == len(hidden["occurrences"])
    assert set(summary) == {"id", "selector", "count", "fragment"}
    assert all(row["path"] == hit["path"] for row in file_selected["texts"])
    assert summary in select(result, "source:" + hit["source"])["related_groups"]
    expanded = select(result, summary["selector"])
    expected = {row["source"] for row in hidden["occurrences"]}
    assert {row["id"] for row in expanded["texts"]} == expected
    assert expanded["literal_groups"] == [hidden]
    assert expanded["related_groups"] == []
    displayed = json.loads(render(file_selected, as_json=True))
    assert len(displayed["related_groups"]) <= 3
    assert displayed["unexpanded"]["related_groups"] == len(file_selected["related_groups"]) - len(displayed["related_groups"])
    assert displayed["unexpanded"]["references"] == max(0, len(file_selected["references"]) - 3)
    assert displayed["texts"] == file_selected["texts"]
    assert json.loads(render(file_selected, as_json=True, full=True)) == file_selected
    shown = {row["id"] for row in displayed["related_groups"]}
    narrowed = next(row for row in result["literal_groups"] if row["id"] not in shown and row["token_count"] >= 6)
    literal = select(result, "text:" + narrowed["fragment"])
    assert all(narrowed["fragment"] in row["text"].casefold() for row in literal["texts"])
    assert any(row["id"] == narrowed["id"] for row in literal["related_groups"])
    assert "group:" + narrowed["id"] in render(literal)
    assert any(row["id"] == narrowed["id"] for row in json.loads(render(literal, as_json=True))["related_groups"])
    with pytest.raises(ValueError, match="nonempty"):
        select(result, "text:")
    for bad in ("group:absent", "source:absent", "absent.md", "../left.md"):
        with pytest.raises(ValueError):
            select(result, bad)
    with pytest.raises(ValueError, match="full facts"):
        select(compact, "left.md")


def test_left_maximal_groups_use_all_occurrences_and_preserve_independent_runs():
    rows = [
        {"id": "a", "path": "a.md", "line": 10,
         "text": "keep alpha\nbeta gamma now bright blue sky x red green field end alpha beta gamma tail"},
        {"id": "b", "path": "b.md", "line": 20,
         "text": "run alpha\nbeta gamma next bright blue sky y red green field stop other beta gamma tail"},
    ]
    groups = _literal_groups(rows)
    by_fragment = {row["fragment"]: row for row in groups}
    assert {"alpha beta gamma", "bright blue sky", "red green field", "beta gamma tail"} <= by_fragment.keys()
    assert "gamma tail" not in by_fragment and "blue sky" not in by_fragment
    assert [(hit["line"], hit["end_line"]) for hit in by_fragment["alpha beta gamma"]["occurrences"]] == [(10, 11), (20, 21)]
    # alpha precedes the first beta/gamma in both documents, but not every
    # occurrence: compression to one hit per passage would lose a real group.
    assert "beta gamma" in by_fragment
    assert {row["id"] for row in groups} == {row["id"] for row in _literal_groups(list(reversed(rows)))}


def test_weak_prose_does_not_displace_real_code_hints(tmp_path):
    write(tmp_path, "core.py", 'LABEL = "registered-name"\ndef current_name(): return 1\n')
    write(tmp_path, "README.md", "This tool-rental application covers R1-R11.\n"
          "You MUST check `tool-rental`, `R1-R11`, registered-name and `route_and_guard_model` before skip_with_reason.\n")
    result = report(tmp_path)
    refs = {row["name"]: row for row in result["references"]}
    assert refs["tool-rental"]["kind"] == refs["R1-R11"]["kind"] == "prose candidate"
    assert refs["registered-name"]["state"] == "found in static source"
    unresolved = {row["name"] for row in json.loads(render(result, as_json=True))["references"]}
    assert unresolved == {"route_and_guard_model", "skip_with_reason"}
    assert result["summary"]["unresolved_references"] == 2


def test_filename_candidates_stay_typed_and_never_grant_owner_or_symbol_binding(tmp_path):
    write(tmp_path, "counter/config.py", "def configure(): return 1\n")
    write(tmp_path, "left/shared.py", "def left(): return 1\n")
    write(tmp_path, "right/shared.py", "def right(): return 1\n")
    write(tmp_path, "local.py", "def root_local(): return 1\n")
    write(tmp_path, "docs/local.py", "def document_local(): return 1\n")
    write(tmp_path, "docs/guide.md", "You MUST inspect `config.py`, `shared.py`, `local.py` and `counter.config.configure`.\n")
    inv, raw = facts(tmp_path)
    names = source_names(inv, raw)
    assert "config.py" not in names and "shared.py" not in names
    result = report(tmp_path, inv=inv, raw=raw)
    refs = {row["name"]: row for row in result["references"]}
    for name, paths in {"config.py": ["counter/config.py"], "shared.py": ["left/shared.py", "right/shared.py"], "local.py": ["docs/local.py"]}.items():
        assert refs[name]["kind"] == "file candidate"
        assert refs[name]["files"] == paths
        assert {row["path"] for row in refs[name]["locations"]} == set(paths)
        assert not refs[name]["placement"]["owners"] and not refs[name]["placement"]["functions"]
    assert "ambiguous" in refs["shared.py"]["state"]
    assert refs["counter.config.configure"]["placement"]["functions"] == ["counter/config.py#configure"]
    text_refs = {row["name"]: row for row in where(tmp_path, "docs/guide.md", view="text", inv=inv, raw=raw)["references"]}
    assert text_refs["config.py"]["files"] == ["counter/config.py"]
    assert source_names(inv, raw) == names


def test_text_file_keeps_backticked_heading_as_original_passage(tmp_path):
    write(tmp_path, "core.py", "def current_name(): return 1\n")
    heading = "# API: `former_name`"
    write(tmp_path, "guide.md", heading + "\n\n```\n# Example: `ignored_example`\n```\n")
    result = report(tmp_path)
    selected = select(result, "guide.md")
    passage, = selected["texts"]
    assert passage["text"] == heading and passage["line"] == passage["end_line"] == 1
    reference, = [row for row in result["references"] if row["name"] == "former_name"]
    assert reference["path"] == "guide.md" and reference["line"] == 1
    assert "not found" in reference["state"]
    assert not any(row["name"] == "ignored_example" for row in result["references"])
