"""Tests grouped by their model or native component."""
from __future__ import annotations
import pytest,os,json
from pathlib import Path


def test_check_verifies_model_code_anchors(shop, capsys):
    from flowguard.map import cli
    cli.main(["--root", str(shop), "confirm", "orders"])
    capsys.readouterr()
    assert cli.main(["--root", str(shop), "check"]) == 0
    path = shop / ".flowguard/models/order_placement.py"
    path.write_text(path.read_text(encoding="utf-8").replace("OrderService.place\"", "OrderService.place_order\""),
                    encoding="utf-8")
    assert cli.main(["--root", str(shop), "check"]) == 1
    assert "model_anchor_broken" in capsys.readouterr().out


def test_impact_lists_models_of_affected_components(shop, capsys):
    from flowguard.map import cli
    cli.main(["--root", str(shop), "confirm", "orders"])
    capsys.readouterr()
    assert cli.main(["--root", str(shop), "impact", "shop/orders.py"]) == 0
    out = capsys.readouterr().out
    assert ".flowguard/models/order_placement.py" in out and "tests/test_orders.py" in out


def test_strict_check_and_verify_gate(shop, capsys):
    from flowguard.map import cli
    from _fg_helpers import proof_write as write, proof_FIXED as FIXED
    assert cli.main(["--root", str(shop), "check", "--strict"]) == 1          # still draft
    cli.main(["--root", str(shop), "confirm", "all"])
    write(shop, "shop/orders.py", FIXED)                                         # now stale
    assert cli.main(["--root", str(shop), "check", "--strict"]) == 1
    cli.main(["--root", str(shop), "confirm", "orders"])
    capsys.readouterr()
    assert cli.main(["--root", str(shop), "verify"]) == 0
    assert "verify: PASS" in capsys.readouterr().out


def test_accepted_debt_downgrades_a_lint_error(shop, capsys):
    import json
    from flowguard.map import cli
    from _fg_helpers import proof_write as write
    data = json.loads((shop / ".flowguard/map.json").read_text(encoding="utf-8"))
    extra = dict(data["components"][0], id="billing", files=["billing/*.py"], entrypoints=[], tests=[], models=[],
                 state=[], side_effects=[])
    data["components"].append(extra)                                             # same responsibility twice
    write(shop, "billing/pay.py", "def pay():\n    return 1\n")
    (shop / ".flowguard/map.json").write_text(json.dumps(data), encoding="utf-8")
    assert cli.main(["--root", str(shop), "lint"]) == 1
    data["accepted_debts"] = [{"code": "duplicate_owner", "reason": "billing split planned for Q3"}]
    (shop / ".flowguard/map.json").write_text(json.dumps(data), encoding="utf-8")
    capsys.readouterr()
    assert cli.main(["--root", str(shop), "lint"]) == 0
    assert "accepted debt: billing split planned for Q3" in capsys.readouterr().out


@pytest.mark.parametrize("invalid", ["unsupported", "duplicate", "missing"])
def test_registry_errors_block_check_and_model_execution(shop, capsys, invalid):
    import json
    from flowguard.map import cli
    from _fg_helpers import proof_write as write, proof_models as models, proof_MODEL_SOURCE as MODEL_SOURCE
    data = json.loads((shop / ".flowguard/map.json").read_text())
    if invalid == "unsupported":
        rel = ".flowguard/models/nested/model.py"
        write(shop, rel, MODEL_SOURCE)
        data["components"][0]["models"].append(rel)
        expected = "model_path_unsupported"
    elif invalid == "duplicate":
        write(shop, ".flowguard/models/duplicate.py", MODEL_SOURCE)
        expected = "model_id_duplicate"
    else:
        data["components"][0]["models"].append(".flowguard/models/missing.py")
        expected = "model_missing"
    (shop / ".flowguard/map.json").write_text(json.dumps(data))
    assert cli.main(["--root", str(shop), "check"]) == 1
    assert expected in capsys.readouterr().out
    code, output = models(shop, capsys)
    assert code == 1 and expected in output


@pytest.mark.parametrize("hook", ["def conformance():\n    return None\n",
                                  "def conformance():\n    return True\n",
                                  "def broken_variants():\n    return {}\n"])
def test_defined_proof_hooks_cannot_silently_do_nothing(tmp_path, hook):
    from _fg_helpers import proof__MINIMAL_MODEL as _MINIMAL_MODEL, proof_write as write
    from flowguard.map.proof import run_model
    write(tmp_path, ".flowguard/models/minimal.py", _MINIMAL_MODEL + hook)
    result = run_model(tmp_path, tmp_path / ".flowguard/models/minimal.py")
    assert result.status == "error" and "no " in " ".join(result.problems)


def test_abstract_model_fails(tmp_path):
    from _fg_helpers import proof__MINIMAL_MODEL as _MINIMAL_MODEL, proof_write as write, proof__native_model as _native_model
    from flowguard.map.proof import run_model
    write(tmp_path, ".flowguard/models/minimal.py", _MINIMAL_MODEL)
    result = run_model(tmp_path, tmp_path / ".flowguard/models/minimal.py")
    assert result.status == "fail"
    assert any("abstract boundary only" in problem for problem in result.problems)
    assert any("declares no IMPLEMENTED_BY anchors" in problem for problem in result.problems)
    native = _native_model(tmp_path, tmp_path / ".flowguard/models/minimal.py")
    assert native.status == "fail"
    assert any("abstract boundary only" in problem for problem in native.problems)
    assert any("declares no IMPLEMENTED_BY anchors" in problem for problem in native.problems)


def test_no_models_output_is_explicitly_not_model_proof(tmp_path):
    from flowguard.map.proof import render_results, run_models
    assert render_results(run_models(tmp_path, [])) == "models: 0 declared, 0 executed; no model proof"


def test_unanchored_python_syntax_error_is_a_check_error(shop, capsys):
    from flowguard.map import cli
    from _fg_helpers import proof_write as write
    write(shop, "shop/unanchored.py", "def broken(:\n")
    assert cli.main(["--root", str(shop), "check"]) == 1
    output = capsys.readouterr().out
    assert "shop/unanchored.py" in output and "SyntaxError" in output


def test_non_explorer_proves_nothing(tmp_path):
    from _fg_helpers import proof_write as write
    from flowguard.map.proof import run_model
    write(tmp_path, ".flowguard/models/fake.py", "from types import SimpleNamespace\nMODEL_ID='fake'\ndef build_explorer():\n    return SimpleNamespace(explore=lambda: SimpleNamespace(ok=True))\n")
    result = run_model(tmp_path, tmp_path / ".flowguard/models/fake.py")
    assert result.status == "error" and "Explorer" in " ".join(result.problems)


def test_no_broken_variants_is_an_error(tmp_path):
    from _fg_helpers import proof__MINIMAL_MODEL as _MINIMAL_MODEL, proof_write as write
    from flowguard.map.proof import run_model
    source = _MINIMAL_MODEL.replace("def broken_variants()", "def unused_variants()")
    write(tmp_path, ".flowguard/models/minimal.py", source)
    result = run_model(tmp_path, tmp_path / ".flowguard/models/minimal.py")
    assert result.status == "error" and "no broken_variants" in " ".join(result.problems)


@pytest.mark.skipif(os.name == "nt", reason="POSIX process-group cleanup")
@pytest.mark.parametrize("kind", ["contract"])
def test_model_timeout_cleans_its_spawned_child(tmp_path, kind):
    import os
    import signal
    from pathlib import Path
    import pytest
    from flowguard.map.proof import run_model
    body = (
        "import subprocess,sys,time\nfrom pathlib import Path\n"
        "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'])\n"
        "Path('child.pid').write_text(str(child.pid))\ntime.sleep(30)\n"
    )
    path = tmp_path / ".flowguard" / "models" / "probe.py"
    body = "MODEL_ID='probe'\ndef build_explorer(): pass\n" + body
    function = run_model
    path.parent.mkdir(parents=True)
    path.write_text(body)
    result = function(tmp_path, path, timeout=.5)
    pid = int((tmp_path / "child.pid").read_text())
    try:
        assert result.status == "error"
        assert "cleanup_confirmed=True" in " ".join(result.problems)
        if Path(f"/proc/{pid}/stat").exists():
            assert Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] == "Z"
        else:
            with pytest.raises(ProcessLookupError):
                os.kill(pid, 0)
    finally:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def test_verify_without_user_models_runs_the_builtin_system(tmp_path, capsys):
    import json
    from flowguard.map import cli
    from _fg_helpers import proof_write as write
    write(tmp_path, ".flowguard/map.json", json.dumps({
        "schema": "flowguard.map.v1", "project": "empty", "components": []}))
    assert cli.main(["--root", str(tmp_path), "verify"]) == 0
    output = capsys.readouterr().out
    assert output.count("models: 1 declared, 1 executed") == 1
    assert "PASS  system" in output and "no model proof" not in output
    assert "no known-bad variants could be generated" in output


def test_release_fails_when_an_invariant_has_no_breaking_variant(shop, capsys, monkeypatch):
    from flowguard.map import cli
    from _fg_helpers import proof_write as write, proof__edit_model as _edit_model, proof_FIXED as FIXED, proof_models as models
    from flowguard.map.proof import ModelResult

    write(shop, 'shop/orders.py', FIXED)
    _edit_model(shop, 'INVARIANTS = (at_most_once_by(',
                'def orders_are_unique(state, trace):\n    return len(set(state.orders)) == len(state.orders)\n\n\n'
                'INVARIANTS = (orders_are_unique, at_most_once_by(')
    assert cli.main(['--root', str(shop), 'confirm', 'orders']) == 0
    capsys.readouterr()
    captured = []
    actual_run_models = cli.run_models

    def capture(*args, **kwargs):
        results = actual_run_models(*args, **kwargs)  # real subprocess transport, no fabricated results
        captured.extend(results)
        return results

    monkeypatch.setattr(cli, 'run_models', capture)
    code, output = models(shop, capsys)
    assert code == 1 and "invariant 'orders_are_unique' is violated by no known-bad variant" in output
    assert cli.main(['--root', str(shop), 'verify']) == 1
    output = capsys.readouterr().out
    assert 'uncovered_invariant: invariant \'orders_are_unique\'' in output
    assert 'invariant(s) violated by no known-bad variant' not in output     # counted once, by the failed model
    assert 'verify: FAIL' in output
    assert captured[0].status == 'fail' and captured[0].uncovered_invariants == ['orders_are_unique']
    assert ModelResult(**{'model': 'legacy', 'file': 'legacy.py'}).uncovered_invariants == []


@pytest.mark.parametrize("mode,expected", [("clean", None), ("layer", "layer_violation"),
    ("cycle", "shortest cycle:"), ("no_layers", "no layers in the map"),
    ("duplicate", "duplicate_owner"), ("reserved", "reserved for the root node"),
    ("broken_anchor", "the map does not match the code:"),
    ("uncaught_variant", "passed: the architecture rules do not catch it")])
def test_builtin_system_model(shop, capsys, monkeypatch, mode, expected):
    import json
    from flowguard.map import cli
    from _fg_helpers import proof_write as write, proof_FIXED as FIXED, proof_models as models, proof_MODEL_SOURCE as MODEL_SOURCE
    write(shop, "shop/orders.py", FIXED)
    write(shop, "shop/api.py", "from shop.orders import OrderService\ndef handle():\n    return OrderService()\n")
    data_path = shop / ".flowguard/map.json"
    data = json.loads(data_path.read_text())
    data["layers"] = ["interface", "engine"]
    orders = data["components"][0]
    orders.update(files=["shop/orders.py", "shop/__init__.py"], layer="engine")
    data["components"].append(dict(orders, id="api", layer="interface", summary="HTTP entry",
        responsibilities=["receive checkout requests"], files=["shop/api.py"], depends_on=["orders"],
        entrypoints=["shop/api.py:handle"], tests=[], models=[], state=[], side_effects=[]))
    # The root checks static consistency; it must never execute a registered user model.
    model_path = shop / ".flowguard/models/order_placement.py"
    model_path.write_text("raise AssertionError('system imported user model')\n" + MODEL_SOURCE)
    if mode in {"layer", "cycle"}:
        write(shop, "shop/orders.py", "from shop.api import handle\n" + FIXED)
        orders["depends_on"] = ["api"]
    if mode in {"cycle", "no_layers"}:
        data["layers"] = []
    if mode == "duplicate":
        data["components"][1]["responsibilities"] = list(orders["responsibilities"])
    if mode == "reserved":
        model_path.write_text(model_path.read_text().replace('MODEL_ID = "order_placement"', 'MODEL_ID = "system"'))
    if mode == "broken_anchor":
        orders["entrypoints"] = ["shop/orders.py:absent"]
    data_path.write_text(json.dumps(data))
    cli.main(["--root", str(shop), "confirm", "all"])
    capsys.readouterr()
    if mode == "uncaught_variant":
        from flowguard.map import lint
        monkeypatch.setattr(lint, "structural_findings", lambda *args, **kwargs: [])
    code, output = models(shop, capsys, "system")
    assert code == (0 if mode in {"clean", "no_layers"} else 1)
    if code == 0:
        assert "PASS  system" in output and "generated known-bad variant" not in output
    if expected:
        assert expected in output
    if mode == "layer":
        assert "shop/orders.py:1" in output


def test_system_variants_only_skip_positive_accepted_debt_findings(monkeypatch):
    from flowguard.map import lint, system_model
    data = {"layers": ["top", "low"], "components": [
        {"id": "a", "layer": "top", "responsibilities": ["receive requests"]},
        {"id": "b", "layer": "low", "responsibilities": ["persist records"]}]}
    graph = {"a": {"b"}, "b": set()}
    variants = list(system_model.architecture_variants(data, graph))
    assert {name for name, _, _ in variants} == {
        "a_closes_cycle_with_b", "a_duplicates_b", "b_imports_a", "b_duplicates_a"}
    assert all(any(f.level == "error" for f in system_model.architecture_findings(changed, edges))
               for _, changed, edges in variants)
    accepted = {**data, "accepted_debts": [
        {"code": "dependency_cycle", "members": ["a", "b"], "reason": "existing cycle policy"},
        {"code": "layer_violation", "reason": "existing boundary policy"},
        {"code": "duplicate_owner", "reason": "existing shared responsibility"}]}
    assert list(system_model.architecture_variants(accepted, graph)) == []
    # A missing architecture rule is not evidence that a mutation was debt-accepted.
    monkeypatch.setattr(lint, "structural_findings", lambda *args, **kwargs: [])
    remaining = list(system_model.architecture_variants(data, graph))
    assert {name for name, _, _ in remaining} >= {"a_closes_cycle_with_b", "b_imports_a"}
    assert any(not system_model.architecture_findings(changed, edges) for _, changed, edges in remaining)


def test_bound_tests_without_pytest_are_an_environment_error(shop, monkeypatch):
    from _fg_helpers import proof_write as write, proof_FIXED as FIXED, proof_MODEL_SOURCE as MODEL_SOURCE
    from flowguard.map import proof

    write(shop, "shop/orders.py", FIXED)
    path = shop / ".flowguard/models/order_placement.py"
    path.write_text(MODEL_SOURCE +
                    "\nTESTED_BY = {'one_charge_per_order': ['tests/test_orders.py:test_bound']}\n")
    write(shop, "tests/test_orders.py", "def test_bound():\n    assert True\n")
    original = proof.run_isolated_process

    def without_site(argv, **kwargs):
        # The real child cannot import site-packages; do not fabricate its result.
        if "flowguard.map.testreach" in argv:
            argv = [argv[0], "-S", *argv[1:]]
        return original(argv, **kwargs)

    monkeypatch.setattr(proof, "run_isolated_process", without_site)
    result = proof.run_model(shop, path, tests=True)
    assert result.status == "error", result.problems
    assert any("pytest is required to check TESTED_BY" in p for p in result.problems)


@pytest.mark.parametrize("rule_count,bad_count,expected_line", [
    (0, 0, None),
    (8, 8, "      rules: r0, r1, r2, r3, r4, r5, r6, r7; known-bad: b0, b1, b2, b3, b4, b5, b6, b7"),
    (9, 9, "      rules: r0, r1, r2, r3, r4, r5, r6, r7 +1 more; known-bad: b0, b1, b2, b3, b4, b5, b6, b7 +1 more"),
    (9, 0, "      rules: r0, r1, r2, r3, r4, r5, r6, r7 +1 more; known-bad: "),
    (0, 9, "      rules: ; known-bad: b0, b1, b2, b3, b4, b5, b6, b7 +1 more")])
def test_model_result_name_defaults_and_bounded_display(rule_count, bad_count, expected_line):
    import json
    from flowguard.map.proof import ModelResult, render_results

    legacy = ModelResult(**{"model": "legacy", "file": "legacy.py"})
    other = ModelResult("other", "other.py")
    assert legacy.rules == legacy.known_bad == other.rules == other.known_bad == []
    legacy.rules.append("only_this_result")
    legacy.known_bad.append("only_this_variant_list")
    assert other.rules == other.known_bad == []
    rules = [f"r{i}" for i in range(rule_count)]
    bad = [f"b{i}" for i in range(bad_count)]
    result = ModelResult("bounded", "bounded.py", status="fail", rules=rules, known_bad=bad,
                         problems=["original problem"], warnings=["original warning"])
    output = render_results([result])
    assert "original problem" in output and "warning: original warning" in output
    assert "models: 0 passed, 1 failed" in output
    detail = [line for line in output.splitlines() if line.startswith("      rules:")]
    assert detail == ([] if expected_line is None else [expected_line])
    payload = json.loads(json.dumps(result.__dict__))
    assert payload["rules"] == rules and payload["known_bad"] == bad
    assert ModelResult(**payload) == result


@pytest.mark.parametrize("suffix,problem", [
    ("[hit]", None),
    ("[miss]", "tested_by_misses_anchor"),
    ("[unknown]", "tested_by_failed"),
    ("", "tested_by_misses_anchor"),
    ("[", "malformed"),
])
def test_bound_parameter_selection_preserves_each_item_guard(shop, capsys, suffix, problem):
    from _fg_helpers import proof_MODEL as MODEL, proof_write as write, proof__check_codes as _check_codes, proof_FIXED as FIXED, proof_models as models
    write(shop, "shop/orders.py", FIXED)
    write(shop, "tests/test_orders.py", "import pytest\n"
          "@pytest.mark.parametrize('hit', [True, False], ids=['hit', 'miss'])\n"
          "def test_bound(hit):\n"
          "    if hit:\n"
          "        from shop.orders import OrderService\n"
          "        assert OrderService().place('x', 1) == 'placed'\n"
          "    else:\n"
          "        assert 1 == 1\n")
    anchor = "tests/test_orders.py:test_bound" + suffix
    source = (shop / MODEL).read_text(encoding="utf-8")
    write(shop, MODEL, source + "\nTESTED_BY = " + repr({"one_charge_per_order": [anchor]}) + "\n")
    checked = _check_codes(shop, capsys)
    if problem == "malformed":
        assert "model_test_broken" in checked and "malformed parameter selector" in checked, checked
    else:
        assert "model_test_broken" not in checked, checked
    from flowguard.__main__ import main as public_main
    assert public_main(["read", "--root", str(shop), "--component", "orders"]) == 0
    readback = capsys.readouterr().out
    expected_bound = 0 if problem == "malformed" else 1
    assert f"1 functions here and below (bound {expected_bound}, unbound {1-expected_bound})" in readback, readback
    code, output = models(shop, capsys, "order_placement", "--tests")
    if problem is None:
        assert code == 0 and "PASS  order_placement" in output, output
    elif problem == "malformed":
        assert code != 0 and "TESTED_BY" in output, output
        assert "PASS  order_placement" not in output
    else:
        assert code == 1 and problem in output, output
        if suffix in {"[miss]", ""}:
            assert "test_bound[miss]" in output


def test_runner_model_is_an_error(shop, capsys):
    import json
    from flowguard.map import cli
    from _fg_helpers import proof_write as write, proof_FIXED as FIXED, proof_models as models
    from flowguard.__main__ import main

    write(shop, "shop/orders.py", FIXED)
    assert cli.main(["--root", str(shop), "confirm", "orders"]) == 0
    capsys.readouterr()
    marker = shop / "runner-result.txt"
    runner = ".flowguard/verification/owners/orders_check/run_checks.py"
    write(shop, runner, f'from pathlib import Path\nPath({str(marker)!r}).write_text("executed")\n')
    assert cli.main(["--root", str(shop), "check"]) == 1
    output = capsys.readouterr().out
    lines = [line for line in output.splitlines() if len(line.split()) > 1 and line.split()[1] == "runner_model"]
    assert len(lines) == 1 and lines[0].startswith("ERROR") and runner in lines[0], output
    assert "runner models are no longer run; rewrite it as a contract model" in output
    assert not marker.exists()

    data = json.loads((shop / ".flowguard/map.json").read_text(encoding="utf-8"))
    data["components"][0]["models"].append(runner)
    (shop / ".flowguard/map.json").write_text(json.dumps(data), encoding="utf-8")
    assert cli.main(["--root", str(shop), "check"]) == 1
    output = capsys.readouterr().out
    assert len([line for line in output.splitlines() if len(line.split()) > 1 and line.split()[1] == "runner_model"]) == 1
    assert not marker.exists()
    code, output = models(shop, capsys)
    assert code == 1 and "runner_model" in output and "PASS  order_placement" in output, output
    assert not marker.exists()
    assert main(["release", "--root", str(shop)]) == 1
    output = capsys.readouterr().out
    assert "runner_model" in output and "verify: FAIL" in output, output
    assert not marker.exists()

    assert main(["target", "start", "reject a leftover runner", "--root", str(shop)]) == 0
    capsys.readouterr()
    assert main(["target", "check", "--root", str(shop)]) == 1
    output = capsys.readouterr().out
    errors = [line for line in output.splitlines() if "runner_model" in line]
    assert errors and all(line.startswith("ERROR") for line in errors), output
    assert not marker.exists()


def test_anchor_file_read_is_consulted(tmp_path):
    from flowguard.map.facts import AnchorWatch
    path = tmp_path / "source.py"
    path.write_text("def ping(): return 1\n")
    watch = AnchorWatch(tmp_path, ["source.py:ping"])
    with watch:
        assert "ping" in path.read_text()
    assert watch.consulted() == {"source.py:ping"}


def test_test_call_watch_is_per_item(tmp_path):
    from _fg_helpers import proof__watch_native_module as _watch_native_module
    from flowguard.map.facts import AnchorWatch
    module = _watch_native_module(tmp_path)
    watches = [AnchorWatch(tmp_path, ["native_calls.py:ping"], test_call=True) for _ in range(3)]
    with watches[0]:
        module.ping()
    with watches[1]:
        pass
    with watches[2]:
        module.ping()  # same code object, fresh item's disabled locations must restart
    assert [watch.consulted() for watch in watches] == [{"native_calls.py:ping"}, set(), {"native_calls.py:ping"}]


def test_shadowing_copy_names_the_imported_file(tmp_path, monkeypatch):
    from _fg_helpers import proof__anchor_watch_helpers as _anchor_watch_helpers
    from contextlib import chdir
    import importlib.util
    import sys
    from flowguard.map.proof import run_model_in_process
    root = tmp_path / "project"
    model = _anchor_watch_helpers()["make_probe"](root, "worker")
    other = tmp_path / "other"
    other.mkdir()
    source = other / "native_worker.py"
    source.write_text("def ping(): return 1\n")
    spec = importlib.util.spec_from_file_location("native_worker", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setitem(sys.modules, "native_worker", module)
    previous = sys.path[:]
    old_probe = sys.modules.get("_flowguard_model_probe")
    try:
        with chdir(root):
            result = run_model_in_process(root, model)
    finally:
        sys.path[:] = previous
        if old_probe is None: sys.modules.pop("_flowguard_model_probe", None)
        else: sys.modules["_flowguard_model_probe"] = old_probe
    assert result.status == "fail", result.problems
    assert any(f"(imported native_worker from {source})" in problem for problem in result.problems)


def test_monitoring_slots_busy_falls_back_and_preserves_other_tools(tmp_path):
    import pytest
    from _fg_helpers import proof__watch_native_module as _watch_native_module
    import sys
    from flowguard.map.facts import AnchorWatch
    if not hasattr(sys, "monitoring"):
        pytest.skip("monitoring tool slots require Python 3.12+")
    reserved = []
    try:
        for tool in (3, 4):
            if sys.monitoring.get_tool(tool) is None:
                sys.monitoring.use_tool_id(tool, "existing observer")
                reserved.append(tool)
        module = _watch_native_module(tmp_path)
        watch = AnchorWatch(tmp_path, ["native_calls.py:ping"])
        with watch:
            assert watch._tool_id is None
            module.ping()
        assert watch.consulted() == {"native_calls.py:ping"}
        assert all(sys.monitoring.get_tool(tool) == "existing observer" for tool in reserved)
    finally:
        for tool in reserved:
            sys.monitoring.free_tool_id(tool)


def test_identical_function_bodies_in_distinct_files_are_both_observed(tmp_path):
    import importlib.util
    from flowguard.map.facts import AnchorWatch
    modules = []
    for name in ("first", "second"):
        path = tmp_path / (name + ".py")
        path.write_text("def ping(): return 1\n")
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        modules.append(module)
    watch = AnchorWatch(tmp_path, ["first.py:ping", "second.py:ping"])
    with watch:
        for module in modules:
            module.ping()
    assert watch.called == {"first.py:ping", "second.py:ping"}


def test_process_model_passes_with_its_debt_and_goes_stale_once_anchored(tmp_path):
    import json
    from pathlib import Path
    from flowguard.map.inventory import build_inventory
    from flowguard.map.common import DEFAULT_IGNORE
    import runpy
    from flowguard.map.proof import run_model_in_process, render_results
    from flowguard.map.check import run_check
    from flowguard.map.lint import run_lint
    from flowguard.map.inventory import build_inventory
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.target import start_target, add_to_target, check_target
    model_dir = Path(__file__).parents[1] / ".flowguard/models"
    helpers = runpy.run_path(str(model_dir / "model_runs.py"))
    helpers["make_fixture"](tmp_path)
    path = tmp_path / ".flowguard/models/first.py"
    source = path.read_text().replace('IMPLEMENTED_BY = {"Run": "native.py:first_value"}', 'IMPLEMENTED_BY = {}')
    source = source[:source.index("def conformance():")]
    path.write_text(source)
    data = json.loads((tmp_path / ".flowguard/map.json").read_text())
    data["accepted_debts"] = [dict(code="model_anchor_missing", component="first", reason="future first-value workflow; native.py will implement it")]
    (tmp_path / ".flowguard/map.json").write_text(json.dumps(data))
    inv = build_inventory(tmp_path, DEFAULT_IGNORE, write_cache=False)
    findings = run_check(tmp_path, data, inv)
    anchor = [f for f in findings if f.code == "model_anchor_missing"]
    assert len(anchor) == 1 and anchor[0].level == "info"
    assert not any(f.code == "model_conformance_missing" for f in findings)
    result = run_model_in_process(tmp_path, path)
    assert result.status == "pass", result.problems
    assert result.known_bad == ["two"] and result.rules == ["one"]
    assert "(process model: no code yet)" in render_results([result])
    start_target(tmp_path, "process fixture")
    add_to_target(tmp_path, "first")
    report = check_target(tmp_path)
    assert any("process model: first (no code yet; no gap expected)" in line for line in report.gaps), report
    path.write_text(source.replace('IMPLEMENTED_BY = {}','IMPLEMENTED_BY = {"Run": "native.py:first_value"}'))
    inv = build_inventory(tmp_path, DEFAULT_IGNORE, write_cache=False)
    assert any(f.code == "debt_stale" and f.component == "first" for f in run_lint(tmp_path, data, inv))
    assert "abstract boundary only" in " ".join(run_model_in_process(tmp_path, path).problems)


def test_invariant_untested_only_for_models_with_tests(shop):
    from _fg_helpers import proof_MODEL as MODEL
    from flowguard.map.proof import run_model_in_process
    path = shop / MODEL
    source = path.read_text()
    path.write_text(source + "\nTESTED_BY = {}\n")
    result = run_model_in_process(shop, path)
    assert not any(w.startswith("invariant_untested:") for w in result.warnings)


def test_nine_rule_model_warns_and_a_debt_closes_it(tmp_path):
    from flowguard.map.inventory import build_inventory
    from flowguard.map.common import DEFAULT_IGNORE
    from _fg_helpers import proof__size_project as _size_project
    from flowguard.map.lint import run_lint,split_recipe
    data=_size_project(tmp_path,rules=9)
    inv=build_inventory(tmp_path,DEFAULT_IGNORE,write_cache=False)
    rows=[finding for finding in run_lint(tmp_path,data,inv) if finding.code=='large_model']
    assert len(rows)==1 and rows[0].level=='warn'
    assert rows[0].message=='9 rules (soft limit 8; split before 12): '+split_recipe('sized')
    data['accepted_debts']=[dict(code='large_model',component='sized',reason='one finite decision table')]
    rows=[finding for finding in run_lint(tmp_path,data,inv) if finding.code=='large_model']
    assert len(rows)==1 and rows[0].level=='info'
    assert 'accepted debt: one finite decision table' in rows[0].message


def test_thirteen_rule_model_fails_map_check_and_no_debt_closes_it(tmp_path):
    import json
    from flowguard.map.inventory import build_inventory
    from flowguard.map.common import DEFAULT_IGNORE
    from _fg_helpers import proof__size_project as _size_project
    from flowguard.map.check import run_check
    from flowguard.map.lint import run_lint
    data=_size_project(tmp_path,rules=13)
    data['accepted_debts']=[dict(code='large_model',component='sized',reason='cannot override a hard limit')]
    inv=build_inventory(tmp_path,DEFAULT_IGNORE,write_cache=False)
    for findings in (run_check(tmp_path,data,inv),run_lint(tmp_path,data,inv)):
        rows=[f for f in findings if f.code=='large_model']
        assert len(rows)==1 and rows[0].level=='error' and 'over the hard limit 12' in rows[0].message
    from flowguard.map.cli import main
    import json
    (tmp_path/'.flowguard/map.json').write_text(json.dumps(data))
    assert main(['--root',str(tmp_path),'check'])==1


def test_unreadable_rule_count_reports_nothing(tmp_path):
    from flowguard.map.inventory import build_inventory
    from flowguard.map.common import DEFAULT_IGNORE
    from _fg_helpers import proof__size_project as _size_project
    from flowguard.map.lint import model_size_findings
    data=_size_project(tmp_path,rules=13)
    path=tmp_path/'.flowguard/models/sized.py'
    source=path.read_text();start=source.index('RULES=');end=source.index('\ndef make',start)
    source=source[:start]+'RULES=(Invariant(str(i),"holds",lambda s,t:True) for i in range(13))'+source[end:]
    path.write_text(source)
    inv=build_inventory(tmp_path,DEFAULT_IGNORE,write_cache=False)
    assert not model_size_findings(tmp_path,data,inv)
