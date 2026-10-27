"""Tests grouped by their model or native component."""
from __future__ import annotations
import pytest,os,json
from pathlib import Path


from _fg_helpers import (
    map__release_project as _release_project,
    map_codes as codes,
    map_fill as fill,
    map_function_fixture as function_fixture,
    map_git as git,
    map_impact_of as impact_of,
    map_load as load,
    map_run as run,
    map_save as save,
    map_write as write,
)

def test_invalid_map_is_rejected(project, capsys):
    from flowguard.map import cli

    run(project, "scan", capsys=capsys)
    data = load(project)
    data["components"][0]["status"] = "done"
    save(project, data)
    assert cli.main(["--root", str(project), "check"]) == 2
    assert "status must be" in capsys.readouterr().err


def test_fingerprint_ignores_crlf_line_endings(project, capsys):
    from flowguard.map.mapfile import fingerprint
    path = project / "shop/storage.py"
    lf_bytes = path.read_bytes().replace(b"\r\n", b"\n")  # write_text already gives CRLF on Windows
    path.write_bytes(lf_bytes)
    lf = fingerprint(project, ["shop/storage.py"])
    path.write_bytes(lf_bytes.replace(b"\n", b"\r\n"))
    assert b"\r\r\n" not in path.read_bytes()
    assert fingerprint(project, ["shop/storage.py"]) == lf


@pytest.mark.parametrize("operation", ["delete", "rename-same-id", "delete-own-test"])
def test_removed_contract_keeps_surviving_parent_and_tests(retired_model_project, operation):
    from flowguard.map.impact import changed_files

    root, data = retired_model_project
    path = ".flowguard/models/retired.py"
    move = operation == "rename-same-id"
    if move:
        (root / path).rename(root / ".flowguard/models/replacement.py")
    else:
        (root / path).unlink()
    if operation == "delete-own-test":
        (root / "tests/test_retired.py").unlink()
    imp = impact_of(root, data, changed_files(root, "HEAD"), base="HEAD")
    assert not imp.blocked
    assert path not in imp.models
    assert "survivor" in imp.model_ids
    assert "tests/test_survivor.py" in imp.tests
    assert ("tests/test_retired.py" in imp.tests) is (operation != "delete-own-test")
    assert ("retired" in imp.model_ids) is move
    assert (".flowguard/models/replacement.py" in imp.models) is move


@pytest.mark.parametrize("via", ["direct", "helper", "removed-helper"])
def test_removed_contract_keeps_importers_and_their_tests_blocked(retired_model_project, via):
    from flowguard.map.impact import changed_files

    root, data = retired_model_project
    write(root, "tests/test_importer.py", "def test_safe():\n    assert True\n")
    source = (
        "MODEL_ID = 'importer'\nCOMPONENTS = ['storage']\n"
        "TESTED_BY = {'safe': ['tests/test_importer.py:test_safe']}\n"
        "def build_explorer(): pass\n"
    )
    if via == "direct":
        source += "import retired\n"
    else:
        source += "import _bridge\n"
        write(root, ".flowguard/models/_bridge.py", "import retired\n")
    write(root, ".flowguard/models/importer.py", source)
    git(root, "add", "-A")
    git(root, "-c", "user.email=a@b", "-c", "user.name=t", "commit", "-qm", "importer baseline")
    (root / ".flowguard/models/retired.py").unlink()
    if via == "removed-helper":
        (root / ".flowguard/models/_bridge.py").unlink()
    imp = impact_of(root, data, changed_files(root, "HEAD"), base="HEAD")
    assert imp.blocked
    assert "importer" in imp.model_ids
    assert "tests/test_importer.py" in imp.tests


@pytest.mark.parametrize("residue", ["map", "flow", "parent"])
def test_removed_contract_with_current_reference_stays_blocked(retired_model_project, residue):
    from flowguard.map.impact import changed_files

    root, data = retired_model_project
    path = ".flowguard/models/retired.py"
    (root / path).unlink()
    if residue == "map":
        data["components"][2]["models"].append(path)
    elif residue == "flow":
        data["flows"][0]["model"] = path
    else:
        write(
            root,
            ".flowguard/models/orphan.py",
            "MODEL_ID = 'orphan'\nCOMPONENTS = ['storage']\nPARENT = 'retired'\n"
            "TESTED_BY = {'safe': ['tests/test_storage.py:test_y']}\n"
            "def build_explorer(): pass\n",
        )
    save(root, data)
    imp = impact_of(root, data, changed_files(root, "HEAD"), base="HEAD")
    assert imp.blocked
    if residue == "parent":
        assert "orphan" in imp.model_ids and "tests/test_storage.py" in imp.tests


def test_impact_default_full_closure_and_explicit_depth(impact_project):
    from flowguard.map.impact import render_impact

    root, data = impact_project
    full = impact_of(root, data, ["shop/storage.py"])
    assert full.direct == ["storage"] and full.dependents == ["api", "orders"]
    assert full.tests == ["tests/test_api.py", "tests/test_orders.py", "tests/test_storage.py"]
    limited = impact_of(root, data, ["shop/storage.py"], depth=1)
    assert limited.dependents == ["orders"]
    assert "TRUNCATED" in render_impact(limited)
    data["components"][1]["depends_on"].append("api")
    cyclic = impact_of(root, data, ["shop/storage.py"])
    assert cyclic.tests == full.tests


@pytest.mark.parametrize("change", ["delete", "rename", "contract", "test", "mapping"])
def test_impact_verification_backreferences_and_old_paths(impact_project, change):
    from flowguard.map.impact import changed_files, render_impact

    root, data = impact_project
    changed = []
    if change == "delete":
        (root / "shop/storage.py").unlink()
        changed = changed_files(root, "HEAD")
        assert "shop/storage.py" in changed
    elif change == "rename":
        (root / "shop/storage.py").rename(root / "shop/persist.py")
        git(root, "add", "-A")
        changed = changed_files(root, "HEAD")
        assert {"shop/storage.py", "shop/persist.py"} <= set(changed)
    elif change == "mapping":
        write(
            root,
            ".flowguard/models/new_storage.py",
            "MODEL_ID = 'new-storage-proof'\nCOMPONENTS = ['storage']\ndef build_explorer():\n    pass\n",
        )
        data["components"][2]["models"] = [".flowguard/models/new_storage.py"]
        save(root, data)
        changed = [".flowguard/map.json"]
    else:
        changed = [
            {"contract": ".flowguard/models/persistence.py", "test": "tests/test_orders.py"}[change]
        ]
    imp = impact_of(root, data, changed, base="HEAD")
    if change in {"delete", "rename", "mapping"}:
        assert {"tests/test_orders.py", "tests/test_api.py"} <= set(imp.tests)
        assert "orders_check" in imp.model_ids
    else:
        assert imp.direct == [] and imp.dependents == []
        assert imp.tests == (["tests/test_orders.py"] if change == "test" else [])
        expected_models = {"contract": ["storage-proof"], "test": []}
        assert imp.model_ids == expected_models[change]
    assert "tests/test_web.py" not in imp.tests
    assert " models model" not in render_impact(imp)
    if change == "mapping":
        assert {"new-storage-proof", "storage-proof"} <= set(imp.model_ids)
    elif change != "test":
        assert "storage-proof" in imp.model_ids
    assert not imp.blocked


def test_impact_duplicate_model_id_is_blocked_without_run_hint(impact_project):
    from flowguard.map.impact import render_impact

    root, data = impact_project
    write(
        root,
        ".flowguard/models/duplicate.py",
        "MODEL_ID = 'storage-proof'\ndef build_explorer():\n    pass\n",
    )
    imp = impact_of(root, data, ["shop/storage.py"])
    assert any("duplicated" in message for message in imp.blocked)
    assert "storage-proof" not in imp.model_ids
    assert (
        "storage-proof" not in render_impact(imp).split("run: python -m flowguard map models")[-1]
    )


def test_cli_output_never_crashes_on_text_the_console_cannot_encode(project, capsys, monkeypatch):
    import io
    from flowguard.map import cli
    import io
    import sys

    run(project, "scan", capsys=capsys)
    data = fill(project)
    data["components"][0]["summary"] = "运行检查 ✓"
    save(project, data)
    console = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")  # Windows pipe code page
    monkeypatch.setattr(sys, "stdout", console)
    assert cli.main(["--root", str(project), "show"]) == 0
    console.flush()
    assert b"\\u8fd0\\u884c" in console.buffer.getvalue()


def test_parse_cache_key_includes_the_python_version(monkeypatch):
    import importlib.util
    import sys
    from flowguard.map import discover, inventory
    monkeypatch.setattr(sys, "version", "0.0.0 (another interpreter)")   # ast results differ between versions
    for module in (inventory, discover):
        spec = importlib.util.spec_from_file_location(f"{module.__name__}_probe", module.__file__)
        probe = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, spec.name, probe)
        spec.loader.exec_module(probe)
        assert probe.PARSER_ID != module.PARSER_ID, module.__name__


def test_non_source_reference_selects_test_and_unreferenced_doc_reports_no_checks(impact_project):
    from flowguard.map.impact import render_impact

    root, data = impact_project
    write(
        root,
        "tests/test_config.py",
        "CONFIG = 'pyproject.toml'\n\ndef test_config():\n    assert CONFIG\n",
    )
    write(root, "pyproject.toml", "version = '1.0'\n")
    assert impact_of(root, data, ["pyproject.toml"]).tests == ["tests/test_config.py"]
    write(root, "docs/notes.md", "notes\n")
    imp = impact_of(root, data, ["docs/notes.md"])
    assert "NO CHECKS for: docs/notes.md" in render_impact(imp)


def test_confirmed_changed_source_needs_no_repeated_review(impact_project):
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    from flowguard.map.mapfile import component_files, fingerprint

    root, data = impact_project
    write(root, "shop/storage.py", "def save(x):\n    return x + 1\n")
    inv = build_inventory(root, DEFAULT_IGNORE)
    data["components"][2].update(
        status="confirmed",
        fingerprint=fingerprint(root, component_files(data["components"][2], inv)),
    )
    assert not impact_of(root, data, ["shop/storage.py"]).needs_review


def test_test_commands_route_javascript_without_pytest(impact_project):
    from flowguard.map.impact import render_impact

    root, data = impact_project
    write(root, "web/cart.test.js", "test('x', () => {});\n")
    imp = impact_of(root, data, ["web/cart.test.js"])
    text = render_impact(imp)
    assert "NO TEST COMMAND for: web/cart.test.js" in text
    assert imp.blocked
    assert not any(line.startswith("run:") and ".js" in line for line in text.splitlines())
    data["test_commands"] = {"**/*.test.js": "npx jest"}
    assert "run: npx jest web/cart.test.js" in render_impact(
        impact_of(root, data, ["web/cart.test.js"])
    )


@pytest.mark.parametrize("mode", ["historical", "override", "ambiguous", "missing", "retired"])
def test_surviving_javascript_command_is_resolved_or_blocked(impact_project, capsys, mode):
    from flowguard.__main__ import main
    from flowguard.map.impact import render_impact

    root, data = impact_project
    path = "web/cart.test.cjs"
    write(root, path, "require('./client.js');\n")
    data["components"][3]["tests"] = [path]
    data["test_commands"] = {} if mode == "missing" else {"**/*.test.cjs": "node --test"}
    save(root, data)
    git(root, "add", "-A")
    git(root, "-c", "user.email=a@b", "-c", "user.name=t", "commit", "-qm", "JS check")
    data["components"].pop()
    data["test_commands"] = {}
    if mode == "override":
        data["test_commands"] = {path: "node --test --test-reporter=tap"}
    elif mode == "ambiguous":
        data["test_commands"] = {path: "node --test", "**/*.test.cjs": "npx jest"}
    elif mode == "retired":
        (root / path).unlink()
    save(root, data)
    changed = [".flowguard/map.json"]
    imp = impact_of(root, data, changed, base="HEAD")
    blocked = mode in {"missing", "ambiguous"}
    assert bool(imp.blocked) is blocked
    if mode == "retired":
        assert path not in imp.tests
    elif not blocked:
        command = "node --test --test-reporter=tap" if mode == "override" else "node --test"
        assert imp.test_commands[path] == command
        assert f"run: {command} {path}" in render_impact(imp)
    else:
        assert "NO TEST COMMAND for: " + path in render_impact(imp)
        assert run(root, "impact", *changed, capsys=capsys)[0] == 1
        assert main(["change", "--root", str(root), *changed]) == 1
        capsys.readouterr()


def test_ignore_and_generated_cache_files_never_become_unmapped_changes(impact_project):
    from flowguard.map.impact import changed_files

    root, data = impact_project
    data["ignore"] = ["docs/**"]
    write(root, "docs/snippet.py", "VALUE = 1\n")
    write(root, "tests/__pycache__/helper.pyc", "binary\n")
    assert "tests/__pycache__/helper.pyc" not in changed_files(root, "HEAD")
    imp = impact_of(root, data, ["docs/snippet.py", "tests/__pycache__/helper.pyc"])
    assert not imp.unmapped and not imp.tests


def test_impact_lists_test_paths_only_once_in_small_command(impact_project):
    from flowguard.map.impact import render_impact

    root, data = impact_project
    text = render_impact(impact_of(root, data, ["shop/storage.py"]))
    assert text.count("tests/test_storage.py") == 1


@pytest.mark.parametrize("selected_count", (30, 31))
def test_large_selected_scope_does_not_expand_to_the_full_suite(selected_count):
    from flowguard.map.impact import Impact, render_impact

    paths = [f"tests/test_{index:03}.py" for index in range(selected_count)]
    impact = Impact(
        changed=["shop/orders.py"],
        direct=["orders"],
        dependents=[],
        unmapped=[],
        tests=paths,
        models=[],
        needs_review=[],
        total_tests=136,
    )
    text = render_impact(impact)
    from flowguard.map.impact import run_commands

    assert run_commands(impact) == ["python -m pytest -q " + " ".join(paths)]
    assert "test_135.py" not in " ".join(run_commands(impact))
    assert (
        f"run: python -m flowguard change --run (pytest: {selected_count} tests in {selected_count} files:"
        in text
    )
    assert "run: python -m pytest -q " + " ".join(paths) in render_impact(impact, verbose=True)
    assert f"{selected_count} of 136" in text


def test_exact_schema_binding_tracks_content_and_deletion_without_broad_json_scan(impact_project):
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    from flowguard.map.check import run_check
    from flowguard.map.mapfile import component_files, fingerprint, is_stale

    root, data = impact_project
    path = "schemas/request.json"
    write(root, path, '{"required": ["order_id"]}\n')
    write(root, "schemas/unregistered.json", "{}\n")
    write(root, ".flowguard/ignored.json", "{}\n")
    owner = data["components"][2]
    owner["files"] += [path, ".flowguard/ignored.json"]
    inv = build_inventory(root, DEFAULT_IGNORE)
    assert path not in inv.source  # Default inventory still scans code only.
    assert path in component_files(owner, inv)
    assert not any(
        f.code == "pattern_dead" and path in f.message for f in run_check(root, data, inv)
    )
    assert path in inv.source
    assert component_files({"files": ["schemas/*.json"]}, inv) == []
    assert "schemas/unregistered.json" not in inv.source
    assert ".flowguard/ignored.json" not in inv.source
    owner.update(status="confirmed", fingerprint=fingerprint(root, component_files(owner, inv)))
    assert not is_stale(root, owner, inv)
    write(root, path, '{"required": ["order_id", "mode"]}\n')
    assert is_stale(root, owner, inv)
    changed = impact_of(root, data, [path])
    assert changed.direct == ["storage"] and "storage" in changed.needs_review
    assert "tests/test_storage.py" in changed.tests and "storage-proof" in changed.model_ids
    assert path not in changed.no_checks
    (root / path).unlink()
    inv = build_inventory(root, DEFAULT_IGNORE)
    inv.set_explicit_sources([p for c in data["components"] for p in c["files"]])
    assert is_stale(root, owner, inv)
    assert any(f.code == "pattern_dead" and path in f.message for f in run_check(root, data, inv))
    deleted = impact_of(root, data, [path])
    assert deleted.direct == ["storage"] and path not in deleted.no_checks


@pytest.mark.parametrize("debt_style", ["members", "legacy"])
def test_check_and_lint_report_cycles_with_the_shortest_import_path(tmp_path, capsys, debt_style):
    root = tmp_path / "cycle"
    write(root, "a.py", "from b import value\nfrom c import value\nvalue = 1\n")
    write(root, "b.py", "from c import value\nvalue = 2\n")
    write(root, "c.py", "from a import value\nvalue = 3\n")
    git(root, "init", "-q")
    run(root, "scan", capsys=capsys)
    data = load(root)
    data["layers"] = []
    data["components"] = [
        {
            "id": cid,
            "layer": "",
            "summary": responsibility,
            "responsibilities": [responsibility],
            "files": [cid + ".py"],
            "entrypoints": [],
            "state": [],
            "side_effects": [],
            "depends_on": dependencies,
            "tests": [],
            "models": [],
            "status": "draft",
            "fingerprint": "",
        }
        for cid, dependencies, responsibility in [
            ("a", ["b", "c"], "alpha operation"),
            ("b", ["c"], "bravo persistence"),
            ("c", ["a"], "charlie rendering"),
        ]
    ]
    save(root, data)
    run(root, "confirm", "all", capsys=capsys)
    for command in ("check", "lint"):
        code, out = run(root, command, capsys=capsys)
        assert code == 1 and "ERROR dependency_cycle" in out
        assert "a <-> b <-> c; shortest cycle: a -> c -> a" in out
        assert "a -> c: a.py:2 from c import value" in out
        assert "c -> a: c.py:1 from a import value" in out
    from flowguard.__main__ import main

    code = main(["change", "--root", str(root), "a.py"])
    out = capsys.readouterr().out
    assert code == 1 and out.count("dependency_cycle") == 1
    assert "ARCH ERROR dependency_cycle" in out
    debt = {"code": "dependency_cycle", "reason": "preserve this existing cycle"}
    debt.update(
        {"members": ["a", "b", "c"]}
        if debt_style == "members"
        else {"component": "a", "contains": "a <-> b <-> c"}
    )
    data = load(root)
    data["accepted_debts"] = [debt]
    save(root, data)
    code, out = run(root, "check", capsys=capsys)
    assert code == 0 and "INFO  dependency_cycle" not in out
    assert (
        "(1 finding(s) covered by accepted debts not shown: python -m flowguard map lint --debts)"
        in out
    )


def test_load_map_reads_a_bom_map_and_rejects_missing_or_invalid_ones(tmp_path):
    import pytest
    from flowguard.map.mapfile import MapError, load_map

    with pytest.raises(MapError, match="no map"):
        load_map(tmp_path)
    write(tmp_path, ".flowguard/map.json", "{not json")
    with pytest.raises(MapError, match="not valid JSON"):
        load_map(tmp_path)
    (tmp_path / ".flowguard/map.json").write_text(
        '﻿{"schema": "flowguard.map.v1", "components": []}', encoding="utf-8"
    )
    assert load_map(tmp_path)["components"] == []


def test_missing_map_points_at_scan_and_the_first_map_guide(tmp_path, capsys):
    from flowguard.__main__ import main

    write(tmp_path, "app.py", "def run():\n    return True\n")
    assert main(["read", "--root", str(tmp_path)]) == 2
    error = capsys.readouterr().err
    assert (
        "run python -m flowguard map scan first" in error and "references/first_map.md" in error
    ), error


def test_lint_notes_compound_responsibilities(project, capsys):
    import json
    from flowguard.map import cli

    run(project, "scan", capsys=capsys)
    data = fill(project)
    long_duty = "accept order requests from every client and route them " + "carefully " * 8
    long_duty = long_duty.strip()[:130].ljust(130, "x")
    data["components"][0]["responsibilities"] = [long_duty]
    data["components"][1]["responsibilities"] = ["place an order once; refund it later"]
    save(project, data)
    before = cli.main(["--root", str(project), "lint"])
    capsys.readouterr()
    cli.main(["--root", str(project), "lint", "--json"])
    findings = json.loads(capsys.readouterr().out)["findings"]
    notes = [f for f in findings if f["code"] == "responsibility_compound"]
    assert sorted(f["component"] for f in notes) == ["api", "orders"]
    assert all(f["level"] == "info" for f in notes)
    assert any("(130 chars or ';')" in f["message"] for f in notes)
    assert all(
        "write one present-tense duty per entry (references/first_map.md)" in f["message"]
        for f in notes
    )
    data["components"][0]["responsibilities"] = ["accept order requests"]
    data["components"][1]["responsibilities"] = ["place an order once"]
    save(project, data)
    assert "responsibility_compound" not in codes(project, "lint", capsys)
    data["components"][0]["responsibilities"] = [long_duty]
    save(project, data)
    assert cli.main(["--root", str(project), "lint"]) == before




def test_fingerprint_format_3_is_rejected(tmp_path):
    from flowguard.map.mapfile import validate_map

    data, _ = _release_project(tmp_path)
    data["fingerprint_format"] = 3
    assert (
        "fingerprint_format 3 is newer than this FlowGuard (2); install a newer FlowGuard"
        in validate_map(data)
    )
    for invalid in (0, "2", True):
        data["fingerprint_format"] = invalid
        assert "fingerprint_format must be 1 or 2" in validate_map(data)


def test_same_size_rewrite_is_reparsed(tmp_path):
    import os
    from flowguard.map.mapfile import read_model_contract
    p = tmp_path / "model.py"
    p.write_text("MODEL_ID='one'\n")
    stamp = p.stat()
    assert read_model_contract(p)["MODEL_ID"] == "one"
    p.write_text("MODEL_ID='two'\n")
    os.utime(p, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    assert p.stat().st_size == stamp.st_size
    assert read_model_contract(p)["MODEL_ID"] == "two"


@pytest.mark.parametrize("roots", [[""], [".."], ["a/../b"], ["/absolute"], ["a\\b"], [42], "library"])
def test_import_roots_are_validated(tmp_path, roots):
    from flowguard.map.mapfile import validate_map
    data = {"schema": "flowguard.map.v1", "components": [], "import_roots": roots}
    assert any("import_roots" in error for error in validate_map(data))


def test_broad_equals_head_selection(tmp_path):
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    from flowguard.map.impact import compute_impact, _broad_impact

    h = function_fixture()
    data = h["fixture"](tmp_path)
    path = tmp_path / "core.py"
    path.write_text(path.read_text().replace("return helper()+VALUE", "return helper()+VALUE+1"))
    inv = build_inventory(tmp_path, DEFAULT_IGNORE, write_cache=False)
    actual = compute_impact(tmp_path, data, inv, ["core.py"], base="HEAD", broad=True)
    old = _broad_impact(tmp_path, data, inv, ["core.py"], base="HEAD", broad=True)
    assert actual.to_dict() == old.to_dict()


def test_find_owners_edit_selects_its_models_and_test_functions(tmp_path):
    """The real repository's parser and model tree agree on the actual view edit."""
    import json
    import shutil
    import subprocess
    from pathlib import Path
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    from flowguard.map.impact import compute_impact, render_impact

    origin = Path(__file__).parents[1]
    paths = (
        subprocess.check_output(
            ["git", "-C", str(origin), "ls-files", "-co", "--exclude-standard", "-z"]
        )
        .decode()
        .split("\0")
    )
    for relative in set(filter(None, paths)):
        source = origin / relative
        if source.is_file():
            destination = tmp_path / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
    # Promotion verifies the goal before replacing the current model files.
    from flowguard.map.targetfile import load_target, build_target_view

    active = load_target(origin)
    if active is not None:
        view = build_target_view(origin, load(origin), active)
        (tmp_path / ".flowguard/map.json").write_text(json.dumps(view.data))
        for current in (tmp_path / ".flowguard/models").glob("*.py"):
            if view.resolve(".flowguard/models/" + current.name) is None:
                current.unlink()
        for name in view.model_names:
            physical = view.resolve(".flowguard/models/" + name + ".py")
            if physical is not None:
                shutil.copyfile(physical, tmp_path / ".flowguard/models" / (name + ".py"))
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", ".")
    git(
        tmp_path,
        "-c",
        "user.name=FlowGuard",
        "-c",
        "user.email=model@example.invalid",
        "commit",
        "-qm",
        "candidate baseline",
    )
    path = tmp_path / "flowguard/map/views.py"
    path.write_text(
        path.read_text().replace(
            "    return scored[:limit]", "    scored = list(scored)\n    return scored[:limit]"
        )
    )
    data = load(tmp_path)
    inv = build_inventory(tmp_path, DEFAULT_IGNORE, write_cache=False)
    result = compute_impact(tmp_path, data, inv, ["flowguard/map/views.py"], base="HEAD")
    assert set(result.model_ids) == {"read_find"}
    assert result.tests == [
        "tests/test_map_inventory_inventory.py",
        "tests/test_map_read.py",
        "tests/test_read_command.py",
        "tests/test_read_find.py",
    ]
    assert result.test_functions["tests/test_map_read.py"]
    assert "Find is flowguard/map/views.py:find_" + "owners" in render_impact(result)


def test_large_model_seconds_is_validated():
    from flowguard.map.mapfile import validate_map
    data=dict(schema='flowguard.map.v1',components=[])
    for value in (0,-1,'10',True,float('inf'),float('nan')):
        assert 'large_model_seconds must be a positive number' in validate_map(dict(data,large_model_seconds=value))
    assert not validate_map(dict(data,large_model_seconds=0.01))


def test_readonly_git_index_preserves_racy_timestamp_detection(project):
    """A disposable index must keep Git's original racy-clean timestamp window."""
    import os, time
    from flowguard.map.impact import changed_files

    git(project, "config", "core.trustctime", "false")
    git(project, "config", "core.checkStat", "minimal")
    path = project / "shop/工具.py"
    write(project, "shop/工具.py", "VALUE = 1\n")
    timestamp = int(time.time()) - 10
    os.utime(path, (timestamp, timestamp))
    git(project, "add", "-A")
    git(project, "-c", "user.email=a@b", "-c", "user.name=t", "commit", "-qm", "timestamp baseline")
    index = project / ".git/index"
    os.utime(index, (timestamp, timestamp))
    path.write_text("VALUE = 2\n")
    os.utime(path, (timestamp, timestamp))
    before = (index.read_bytes(), index.stat().st_mtime_ns)
    assert "shop/工具.py" in changed_files(project, "HEAD")
    assert (index.read_bytes(), index.stat().st_mtime_ns) == before


def test_debt_findings_hidden_outside_lint_debts(tmp_path, capsys):
    import json
    from flowguard.map import cli

    directory = tmp_path / ".flowguard"
    directory.mkdir()
    components = []
    for name, dependency in (("a", "b"), ("b", "a"), ("c", "d"), ("d", "c")):
        (tmp_path / (name + ".py")).write_text(f"import {dependency}\nVALUE = 1\n")
        components.append(
            {
                "id": name,
                "summary": "Own " + name,
                "responsibilities": ["ownership" + name * 6],
                "files": [name + ".py"],
                "depends_on": [dependency],
                "tests": [],
                "models": [],
                "status": "draft",
            }
        )
    data = {
        "schema": "flowguard.map.v1",
        "components": components,
        "accepted_debts": [
            {"code": "dependency_cycle", "members": ["a", "b"], "reason": "first existing cycle"},
            {"code": "dependency_cycle", "members": ["c", "d"], "reason": "second existing cycle"},
        ],
    }
    (directory / "map.json").write_text(json.dumps(data))
    assert cli.main(["--root", str(tmp_path), "check"]) == 0
    output = capsys.readouterr().out
    assert "(accepted debt:" not in output
    assert (
        output.splitlines()[-2]
        == "(2 finding(s) covered by accepted debts not shown: python -m flowguard map lint --debts)"
    )
    assert cli.main(["--root", str(tmp_path), "check", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert (
        len([finding for finding in payload["findings"] if "(accepted debt:" in finding["message"]])
        == 2
    )
    assert cli.main(["--root", str(tmp_path), "lint", "--debts"]) == 0
    debts = capsys.readouterr().out
    assert "first existing cycle" in debts and "second existing cycle" in debts
    assert debts.count("dependency_cycle") == 2 and "(unused)" not in debts
