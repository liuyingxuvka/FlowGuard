"""Request commit links follow actual symbol changes, without importing models."""
import json
import subprocess
import pytest

from flowguard.map.common import normalize_newlines
from flowguard.map.derived import render, where
from flowguard.map.requests import retire_request, store_request


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], stderr=subprocess.PIPE).decode().strip()


def write(root, path, text):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def commit(root, message):
    git(root, "add", ".")
    git(root, "commit", "-qm", message)
    return git(root, "rev-parse", "HEAD")


def project(root):
    git(root, "init", "-q")
    git(root, "config", "user.name", "Fixture")
    git(root, "config", "user.email", "fixture@example.invalid")
    write(root, "app.py", "def first():\n    return 1\n\ndef other():\n    return 2\n")
    commit(root, "initial")
    store_request(root, b"first returns three", identifier="R1")
    store_request(root, b"other returns four", identifier="R2")
    commit(root, "store owner words")


def test_commit_request_links_only_the_changed_symbol_and_prints_original_words(tmp_path):
    project(tmp_path)
    write(tmp_path, "app.py", "def first():\n    return 3\n\ndef other():\n    return 2\n")
    first = commit(tmp_path, "repair first\n\nRequest: R1")
    write(tmp_path, "app.py", "def first():\n    return 3\n\ndef other():\n    return 4\n")
    commit(tmp_path, "repair other\n\nRequest: R2")
    result = where(tmp_path, "first")
    assert [r["id"] for r in result["requests"]] == ["R1"]
    assert result["functions"][0]["request_commits"] == [{"commit": first, "requests": ["R1"]}]
    assert "first returns three" in render(result)
    assert "other returns four" not in render(result)
    assert [r["id"] for r in where(tmp_path, "other")["requests"]] == ["R2"]


def test_retired_and_malformed_commit_requests_are_visible_limits_not_live_links(tmp_path):
    project(tmp_path)
    write(tmp_path, "app.py", "def first():\n    return 3\n\ndef other():\n    return 2\n")
    commit(tmp_path, "repair\n\nRequest: R1")
    retire_request(tmp_path, "R1")
    result = where(tmp_path, "first")
    assert result["requests"] == []
    assert any("R1" in item and "retired" in item for item in result["unknown"])
    write(tmp_path, "app.py", "def first():\n    return 5\n\ndef other():\n    return 2\n")
    commit(tmp_path, "unparseable citation\n\nRequest: R2 ???")
    result = where(tmp_path, "first")
    assert result["requests"] == []
    assert any("malformed Request:" in item for item in result["unknown"])


def test_flow_models_rules_and_open_conflicts_are_discovered_without_execution(tmp_path):
    project(tmp_path)
    write(tmp_path, ".flowguard/flow/repair.py", '''from flowguard.flow import Model
raise AssertionError("where must not import this file")
m = Model("repair", covers=["app.py:first"])
m.always("first output", lambda s: True, source="R1")
MODEL = m
''')
    write(tmp_path, ".flowguard/flow/other.py", '''from flowguard.flow import Model
m = Model("other", covers=["app.py:other"])
m.always("other output", lambda s: True, source="R2")
MODEL = m
''')
    write(tmp_path, ".flowguard/conflicts.json", json.dumps({"conflicts": [
        {"id": "C-first", "kind": "BROKEN", "model": "repair", "subject": "first output", "text": "wrong", "sources": ["R1"]},
        {"id": "C-other", "kind": "BROKEN", "model": "other", "subject": "other output", "text": "wrong", "sources": ["R2"]}]}))
    result = where(tmp_path, "first")
    assert [row["model"] for row in result["flow_models"]] == ["repair"]
    assert [row["name"] for row in result["flow_rules"]] == ["first output"]
    assert [row["id"] for row in result["open_conflicts"]] == ["C-first"]
    assert [row["id"] for row in result["requests"]] == ["R1"]
    assert "C-first" in render(result) and "first output" in render(result)
    assert result["functions"][0]["model_bindings"][0]["model"] == "repair"


def test_computed_model_covers_and_unreadable_conflict_record_are_explicit(tmp_path):
    project(tmp_path)
    write(tmp_path, ".flowguard/flow/dynamic.py", 'from flowguard.flow import Model\nm = Model("dynamic", covers=build_covers())\nMODEL=m\n')
    write(tmp_path, ".flowguard/conflicts.json", "{bad")
    result = where(tmp_path, "first")
    assert any("dynamic.py" in item and "covers" in item for item in result["unknown"])
    assert any("conflicts.json" in item for item in result["unknown"])


def test_shallow_history_is_explicit_and_does_not_claim_complete_links(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    project(source)
    shallow = tmp_path / "shallow"
    subprocess.check_call(["git", "clone", "-q", "--depth=1", source.as_uri(), str(shallow)])
    result = where(shallow, "first")
    assert any("shallow" in item for item in result["unknown"])


def test_source_query_without_git_marks_request_history_unavailable(tmp_path):
    write(tmp_path, "app.py", "def first(): return 1\n")
    assert any("request commit history" in item for item in where(tmp_path, "first")["unknown"])


def test_decorator_and_deleted_lines_belong_to_the_changed_function(tmp_path):
    project(tmp_path)
    write(tmp_path, "app.py", "def deco(fn): return fn\n@deco\ndef first():\n    extra = 1\n    return extra\n\ndef other(): return 2\n")
    commit(tmp_path, "baseline decorator")
    write(tmp_path, "app.py", "def deco(fn): return fn\n@deco\ndef first():\n    return 1\n\ndef other(): return 2\n")
    removed = commit(tmp_path, "remove assignment\n\nRequest: R1")
    write(tmp_path, "app.py", "def deco(fn): return fn\ndef first():\n    return 1\n\ndef other(): return 2\n")
    decorator = commit(tmp_path, "remove decorator\n\nRequest: R1")
    links = where(tmp_path, "first")["functions"][0]["request_commits"]
    assert [row["commit"] for row in links] == [decorator, removed]


def test_only_exported_model_declaration_supplies_coverage(tmp_path):
    project(tmp_path)
    write(tmp_path, ".flowguard/flow/chosen.py", '''from flowguard.flow import Model as F
unused = F("other", covers=["app.py:other"])
m = F("chosen", covers=["app.py:first"])
unused.always("unexported", lambda s: True, source="R2")
m.always("first output", lambda s: True, source="R1")
MODEL = m
''')
    result = where(tmp_path, "first output")
    assert [row["name"] for row in result["flow_rules"]] == ["first output"]
    assert result["flow_models"][0]["covers"] == ["app.py:first"]
    assert where(tmp_path, "other")["flow_models"] == []
    assert not any("name not resolved" in item for item in result["unknown"])


def test_missing_commit_objects_are_not_a_successful_empty_history(tmp_path, monkeypatch):
    from flowguard.map import requests
    from flowguard.map.common import MapError
    project(tmp_path)
    real = requests.git_run
    def broken(root, *args, **kwargs):
        if args[0] == "log":
            raise MapError("git log failed: missing commit object")
        return real(root, *args, **kwargs)
    monkeypatch.setattr(requests, "git_run", broken)
    import pytest
    with pytest.raises(MapError, match="missing commit object"):
        where(tmp_path, "first")


@pytest.mark.parametrize("original_newline", [b"\n", b"\r\n"])
def test_physical_newline_change_does_not_create_a_semantic_request_link(tmp_path, original_newline):
    project(tmp_path)
    git(tmp_path, "config", "core.autocrlf", "false")
    path = tmp_path / "app.py"
    canonical = normalize_newlines(path.read_bytes())
    path.write_bytes(canonical.replace(b"\n", original_newline))
    git(tmp_path, "add", "app.py")
    git(tmp_path, "commit", "--allow-empty", "-qm", "baseline physical newlines")
    changed_newline = b"\r\n" if original_newline == b"\n" else b"\n"
    path.write_bytes(canonical.replace(b"\n", changed_newline))
    commit(tmp_path, "checkout newline normalization\n\nRequest: R1")
    result = where(tmp_path, "first")
    assert result["requests"] == []
    assert result["functions"][0]["request_commits"] == []


def test_export_keeps_instance_when_local_name_is_rebound(tmp_path):
    project(tmp_path)
    write(tmp_path, ".flowguard/flow/chosen.py", '''from flowguard.flow import Model
m = Model("chosen", covers=["app.py:first"])
m.always("first output", lambda s: True, source="R1")
MODEL = m
m = Model("later unexported model", covers=["app.py:other"])
m.always("other output", lambda s: True, source="R2")
''')
    first = where(tmp_path, "first")
    assert first["flow_models"][0]["covers"] == ["app.py:first"]
    assert [row["name"] for row in first["flow_rules"]] == ["first output"]
    assert [row["id"] for row in first["requests"]] == ["R1"]
    assert where(tmp_path, "other")["flow_models"] == []


def test_constructor_and_rule_arguments_keep_their_values_at_the_call(tmp_path):
    project(tmp_path)
    write(tmp_path, ".flowguard/flow/chosen.py", '''from flowguard.flow import Model
COVERS = ["app.py:first"]
SOURCE = "R1"
TITLE = "first output"
m = Model("chosen", covers=COVERS)
m.always(TITLE, lambda s: True, source=SOURCE)
MODEL = m
COVERS = ["app.py:other"]
SOURCE = "R2"
TITLE = "other output"
''')
    first = where(tmp_path, "first")
    assert first["flow_models"][0]["covers"] == ["app.py:first"]
    assert [(r["name"], r["source"]) for r in first["flow_rules"]] == [("first output", "R1")]
    assert where(tmp_path, "other")["flow_models"] == []


def test_alias_rules_and_literal_later_covers_mutation_follow_the_instance(tmp_path):
    project(tmp_path)
    write(tmp_path, ".flowguard/flow/chosen.py", '''from flowguard.flow import Model
m = Model("chosen", covers=["app.py:other"])
MODEL = m
alias = m
m = Model("unexported", covers=["app.py:other"])
alias.covers = ["app.py:first"]
alias.always("first output", lambda s: True, source="R1")
m.always("other output", lambda s: True, source="R2")
''')
    first = where(tmp_path, "first")
    assert first["flow_models"][0]["covers"] == ["app.py:first"]
    assert [r["name"] for r in first["flow_rules"]] == ["first output"]
    assert where(tmp_path, "other")["flow_models"] == []


def test_dynamic_mutation_does_not_leave_a_clean_false_static_binding(tmp_path):
    project(tmp_path)
    write(tmp_path, ".flowguard/flow/chosen.py", '''from flowguard.flow import Model
m = Model("chosen", covers=["app.py:first"])
MODEL = m
m.covers = calculate_covers()
''')
    result = where(tmp_path, "first")
    assert result["flow_models"] == []
    assert any("covers" in item and "unknown" in item for item in result["unknown"])


def test_model_rule_container_mutation_is_unknown_instead_of_old_live_rules(tmp_path):
    project(tmp_path)
    write(tmp_path, ".flowguard/flow/chosen.py", '''from flowguard.flow import Model
m = Model("chosen", covers=["app.py:first"])
m.always("first output", lambda s: True, source="R1")
MODEL = m
m.rules.clear()
''')
    result = where(tmp_path, "first")
    assert result["flow_rules"] == []
    assert any("model-container" in item and "unknown" in item for item in result["unknown"])


def test_literal_container_mutation_before_constructor_is_not_a_known_old_cover(tmp_path):
    project(tmp_path)
    write(tmp_path, ".flowguard/flow/chosen.py", '''from flowguard.flow import Model
COVERS = ["app.py:first"]
COVERS[0] = "app.py:other"
MODEL = Model("chosen", covers=COVERS)
''')
    result = where(tmp_path, "first")
    assert result["flow_models"] == []
    assert any("covers" in item and "unknown" in item for item in result["unknown"])


def test_literal_container_changes_after_constructor_do_not_change_the_model_copy(tmp_path):
    project(tmp_path)
    write(tmp_path, ".flowguard/flow/chosen.py", '''from flowguard.flow import Model
COVERS = ["app.py:first"]
MODEL = Model("chosen", covers=COVERS)
COVERS[0] = "app.py:other"
''')
    result = where(tmp_path, "first")
    assert result["flow_models"][0]["covers"] == ["app.py:first"]
    assert not any("chosen.py" in item for item in result["unknown"])


def test_dynamic_call_receives_the_old_instance_before_assignment_rebinds_name(tmp_path):
    project(tmp_path)
    write(tmp_path, ".flowguard/flow/chosen.py", '''from flowguard.flow import Model
m = Model("chosen", covers=["app.py:first"])
MODEL = m
m = configure(m)
''')
    result = where(tmp_path, "first")
    assert result["flow_models"] == []
    assert any("dynamic call" in item and "unknown" in item for item in result["unknown"])


def test_dynamic_top_level_call_can_change_exported_model_through_a_global(tmp_path):
    project(tmp_path)
    write(tmp_path, ".flowguard/flow/chosen.py", '''from flowguard.flow import Model
m = Model("chosen", covers=["app.py:first"])
MODEL = m
def configure():
    m.covers = ["app.py:other"]
configure()
''')
    result = where(tmp_path, "first")
    assert result["flow_models"] == []
    assert any("dynamic top-level call" in item and "unknown" in item for item in result["unknown"])


def test_public_objects_declaration_preserves_literal_coverage_and_rules(tmp_path):
    project(tmp_path)
    write(tmp_path, "app.py", "class First:\n    def run(self): return 1\n")
    write(tmp_path, ".flowguard/flow/chosen.py", '''from flowguard.flow import Model
m = Model("chosen", covers=["app.py:First"])
TOOLS = m.objects("tool", "T1")
m.field("on", [False, True], False, over=TOOLS)
m.always("first available", lambda s: True, source="R1")
MODEL = m
''')
    result = where(tmp_path, "First.run")
    assert result["flow_models"][0]["covers"] == ["app.py:First"]
    assert [r["name"] for r in result["flow_rules"]] == ["first available"]
    assert not any("chosen.py" in item for item in result["unknown"])


def test_public_adapter_binding_preserves_static_coverage_without_loading_native_code(tmp_path):
    project(tmp_path)
    write(tmp_path, "app.py", "class First:\n    def run(self): return 1\n")
    write(tmp_path, ".flowguard/flow/chosen.py", '''from flowguard.flow import Model
m = Model("chosen", covers=["app.py:First"])
m.always("first available", lambda s: True, source="R1")
m.bind_adapter(spec, state=lambda snapshot: snapshot, operations={"run": "First.run"})
MODEL = m
''')
    result = where(tmp_path, "First.run")
    assert result["flow_models"][0]["covers"] == ["app.py:First"]
    assert [r["name"] for r in result["flow_rules"]] == ["first available"]
    assert not any("chosen.py" in item for item in result["unknown"])


def test_adapter_binding_helper_arguments_still_mark_dynamic_mutation_unknown(tmp_path):
    project(tmp_path)
    write(tmp_path, "app.py", "class First:\n    def run(self): return 1\n")
    write(tmp_path, ".flowguard/flow/chosen.py", '''from flowguard.flow import Model
m = Model("chosen", covers=["app.py:First"])
def configure():
    m.covers = ["app.py:Other"]
    return spec
m.bind_adapter(configure(), state=lambda snapshot: snapshot, operations={"run": "First.run"})
MODEL = m
''')
    result = where(tmp_path, "First.run")
    assert result["flow_models"] == []
    assert any("dynamic" in item and "unknown" in item for item in result["unknown"])


def test_nested_helper_argument_mutation_is_unknown_without_executing_helper(tmp_path):
    from flowguard.flow.model import load_model
    project(tmp_path)
    write(tmp_path, "app.py", "class First:\n    def run(self): return 1\nclass Other:\n    def run(self): return 2\n")
    marker = tmp_path / "helper-executed"
    write(tmp_path, ".flowguard/flow/chosen.py", '''from pathlib import Path
from flowguard.flow import Model
m = Model("chosen", covers=["app.py:First"])
m.field("on", [False, True], False)
def make_predicate():
    m.covers = ["app.py:Other"]
    Path(MARKER).write_text("executed")
    return lambda s: True
m.always("helper rule", make_predicate(), source="R1")
MODEL = m
'''.replace("MARKER", repr(str(marker))))
    result = where(tmp_path, "First.run")
    assert not marker.exists()
    assert result["flow_models"] == []
    assert any("dynamic" in item and "unknown" in item for item in result["unknown"])
    # Only now execute this known-safe fixture to demonstrate the actual different model.
    assert list(load_model(tmp_path / ".flowguard/flow/chosen.py", tmp_path).model.covers) == ["app.py:Other"]
    assert marker.exists()


def test_lambda_body_calls_are_deferred_but_lambda_default_calls_are_not(tmp_path):
    project(tmp_path)
    marker = tmp_path / "not-run"
    template = '''from pathlib import Path
from flowguard.flow import Model
m = Model("chosen", covers=["app.py:first"])
def helper():
    Path(MARKER).write_text("executed")
    return lambda s: True
m.always("rule", PREDICATE, source="R1")
MODEL = m
'''.replace("MARKER", repr(str(marker)))
    write(tmp_path, ".flowguard/flow/chosen.py", template.replace("PREDICATE", "lambda s: helper()(s)"))
    deferred = where(tmp_path, "first")
    assert deferred["flow_models"][0]["covers"] == ["app.py:first"]
    assert not any("chosen.py" in item for item in deferred["unknown"])
    assert not marker.exists()
    write(tmp_path, ".flowguard/flow/chosen.py", template.replace("PREDICATE", "lambda s, pred=helper(): pred(s)"))
    immediate = where(tmp_path, "first")
    assert immediate["flow_models"] == []
    assert any("dynamic" in item for item in immediate["unknown"])
    assert not marker.exists()


def test_constructor_argument_helper_is_unknown_before_copying_literal_covers(tmp_path):
    project(tmp_path)
    write(tmp_path, ".flowguard/flow/chosen.py", '''from flowguard.flow import Model
COVERS = ["app.py:first"]
def helper():
    COVERS[0] = "app.py:other"
    return "note"
MODEL = Model("chosen", covers=COVERS, note=helper())
''')
    result = where(tmp_path, "first")
    assert result["flow_models"] == []
    assert any("dynamic constructor argument" in item for item in result["unknown"])
