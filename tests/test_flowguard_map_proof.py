"""Tests for the proof layer (flowguard.map.proof) and its links to the map.

The fixture is a tiny shop whose OrderService charges the card again when a
client retries the same order id.  Its unit test is green; the model's
conformance replay must catch the bug.
"""

from __future__ import annotations

import json
import os
import signal
import shutil
import subprocess
from pathlib import Path

import pytest

from flowguard.map import cli

MODEL_SOURCE = Path(__file__).resolve().parents[1] / ".agents/skills/flowguard/assets/model_template.py"

BUGGY = '''class OrderService:
    def __init__(self):
        self.orders = {}
        self.charges = []

    def place(self, order_id, amount):
        self.charges.append(order_id)          # BUG: a retry charges again
        self.orders[order_id] = amount
        return "placed"
'''

FIXED = '''class OrderService:
    def __init__(self):
        self.orders = {}
        self.charges = []

    def place(self, order_id, amount):
        if order_id in self.orders:
            return "already_placed"
        self.charges.append(order_id)
        self.orders[order_id] = amount
        return "placed"
'''


def write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture()
def shop(tmp_path: Path) -> Path:
    root = tmp_path / "shop"
    write(root, "shop/__init__.py", "")
    write(root, "shop/orders.py", BUGGY)
    write(root, "tests/test_orders.py", "from shop.orders import OrderService\n\n"
          "def test_place_once():\n    svc = OrderService()\n    assert svc.place('o1', 5) == 'placed'\n")
    (root / ".flowguard/models").mkdir(parents=True)
    shutil.copy(MODEL_SOURCE, root / ".flowguard/models/order_placement.py")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    cli.main(["--root", str(root), "scan"])
    data = json.loads((root / ".flowguard/map.json").read_text(encoding="utf-8"))
    data["components"] = [{
        "id": "orders", "layer": "", "summary": "Order placement and payment",
        "responsibilities": ["place an order and charge the customer once per order id"],
        "files": ["shop/*.py"], "entrypoints": ["shop/orders.py:OrderService.place"],
        "state": ["orders by id"], "side_effects": ["charges the customer"], "depends_on": [],
        "tests": ["tests/test_orders.py"], "models": [".flowguard/models/order_placement.py"],
        "status": "draft", "fingerprint": ""}]
    (root / ".flowguard/map.json").write_text(json.dumps(data), encoding="utf-8")
    return root


def models(root: Path, capsys, *extra: str) -> tuple[int, str]:
    code = cli.main(["--root", str(root), "models", *extra])
    return code, capsys.readouterr().out


def _native_model(root, path):
    """Exercise the native API without lending another temporary shop its imports."""
    import sys
    from flowguard.map.proof import run_model_in_process

    saved_path = sys.path[:]
    model_name = "_flowguard_model_" + path.stem
    saved = {name: module for name, module in sys.modules.items()
             if name == "shop" or name.startswith("shop.") or name == model_name}
    for name in saved:
        sys.modules.pop(name)
    try:
        return run_model_in_process(root, path)
    finally:
        sys.path[:] = saved_path
        for name in list(sys.modules):
            if name == "shop" or name.startswith("shop.") or name == model_name:
                sys.modules.pop(name)
        sys.modules.update(saved)


def test_unit_test_is_green_but_model_conformance_catches_double_charge(shop, capsys):
    code, out = models(shop, capsys)
    assert code == 1
    assert "FAIL" in out and "does not conform" in out and "one_charge_per_order" in out


def test_fixed_code_passes_and_every_run_executes(shop, capsys):
    write(shop, "shop/orders.py", FIXED)
    for _ in range(2):
        code, out = models(shop, capsys)
        assert code == 0 and "PASS" in out and "cached" not in out
        assert "violated by no known-bad variant" not in out
    assert not (shop / ".flowguard/cache/models.json").exists()


def test_invariant_no_known_bad_variant_violates_is_a_warning(shop, capsys):
    write(shop, "shop/orders.py", FIXED)
    _edit_model(shop, "INVARIANTS = (at_most_once_by(",
                "def orders_are_unique(state, trace):\n    return len(set(state.orders)) == len(state.orders)\n\n\n"
                "INVARIANTS = (orders_are_unique, at_most_once_by(")
    code, out = models(shop, capsys)
    assert code == 0, out
    assert "invariant 'orders_are_unique' is violated by no known-bad variant" in out
    assert "'one_charge_per_order' is violated by no" not in out


def test_invariants_without_teeth_are_rejected(shop, capsys):
    write(shop, "shop/orders.py", FIXED)
    path = shop / ".flowguard/models/order_placement.py"
    text = path.read_text(encoding="utf-8")
    start = text.index("INVARIANTS = (")
    end = text.index("\n", start)
    path.write_text(text[:start] + "INVARIANTS = ()" + text[end:], encoding="utf-8")
    code, out = models(shop, capsys)
    assert code == 1 and "known-bad variant 'charge_every_time' passed" in out


def test_check_verifies_model_code_anchors(shop, capsys):
    cli.main(["--root", str(shop), "confirm", "orders"])
    capsys.readouterr()
    assert cli.main(["--root", str(shop), "check"]) == 0
    path = shop / ".flowguard/models/order_placement.py"
    path.write_text(path.read_text(encoding="utf-8").replace("OrderService.place\"", "OrderService.place_order\""),
                    encoding="utf-8")
    assert cli.main(["--root", str(shop), "check"]) == 1
    assert "model_anchor_broken" in capsys.readouterr().out


def test_impact_lists_models_of_affected_components(shop, capsys):
    cli.main(["--root", str(shop), "confirm", "orders"])
    capsys.readouterr()
    assert cli.main(["--root", str(shop), "impact", "shop/orders.py"]) == 0
    out = capsys.readouterr().out
    assert ".flowguard/models/order_placement.py" in out and "tests/test_orders.py" in out


def test_strict_check_and_verify_gate(shop, capsys):
    assert cli.main(["--root", str(shop), "check", "--strict"]) == 1          # still draft
    cli.main(["--root", str(shop), "confirm", "all"])
    write(shop, "shop/orders.py", FIXED)                                         # now stale
    assert cli.main(["--root", str(shop), "check", "--strict"]) == 1
    cli.main(["--root", str(shop), "confirm", "orders"])
    capsys.readouterr()
    assert cli.main(["--root", str(shop), "verify"]) == 0
    assert "verify: PASS" in capsys.readouterr().out


def test_accepted_debt_downgrades_a_lint_error(shop, capsys):
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


def test_mapped_helper_mutation_invalidates_pass_without_direct_anchor_edit(shop, capsys):
    implementation = "from shop.helper import healthy\n" + FIXED.replace(
        "    def place(self, order_id, amount):\n", "    def place(self, order_id, amount):\n        if not healthy():\n            return 'broken'\n")
    write(shop, "shop/orders.py", implementation)
    write(shop, "shop/helper.py", "def healthy():\n    return True\n")
    assert models(shop, capsys)[0] == 0
    write(shop, "shop/helper.py", "def healthy():\n    return False\n")
    code, output = models(shop, capsys)
    assert code == 1 and "FAIL" in output
    assert (shop / "shop/orders.py").read_text() == implementation
    write(shop, "shop/helper.py", "def healthy():\n    return True\n")
    assert models(shop, capsys)[0] == 0


@pytest.mark.parametrize("selection", [("missing",), ("order_placement", "missing")])
def test_any_unknown_model_selector_fails_instead_of_partial_success(shop, capsys, selection):
    write(shop, "shop/orders.py", FIXED)
    code, output = models(shop, capsys, *selection)
    assert code == 1 and "unknown model id 'missing'" in output


def test_model_selector_uses_declared_id_not_filename_alias(shop, capsys):
    path = shop / ".flowguard/models/order_placement.py"
    path.write_text(path.read_text().replace('MODEL_ID = "order_placement"', 'MODEL_ID = "checkout"'))
    code, output = models(shop, capsys, "order_placement")
    assert code == 1 and "unknown model id" in output
    write(shop, "shop/orders.py", FIXED)
    assert models(shop, capsys, "checkout")[0] == 0


@pytest.mark.parametrize("invalid", ["unsupported", "duplicate", "missing"])
def test_registry_errors_block_check_and_model_execution(shop, capsys, invalid):
    data = json.loads((shop / ".flowguard/map.json").read_text())
    if invalid == "unsupported":
        rel = ".flowguard/models/nested/model.py"
        write(shop, rel, MODEL_SOURCE.read_text())
        data["components"][0]["models"].append(rel)
        expected = "model_path_unsupported"
    elif invalid == "duplicate":
        write(shop, ".flowguard/models/duplicate.py", MODEL_SOURCE.read_text())
        expected = "model_id_duplicate"
    else:
        data["components"][0]["models"].append(".flowguard/models/missing.py")
        expected = "model_missing"
    (shop / ".flowguard/map.json").write_text(json.dumps(data))
    assert cli.main(["--root", str(shop), "check"]) == 1
    assert expected in capsys.readouterr().out
    code, output = models(shop, capsys)
    assert code == 1 and expected in output


def test_registry_issue_does_not_block_the_requested_model(shop, capsys):
    write(shop, "shop/orders.py", FIXED)
    write(shop, ".flowguard/verification/owners/stray/run_checks.py", "raise SystemExit(0)\n")
    code, output = models(shop, capsys, "order_placement")
    assert code == 1
    assert "PASS  order_placement" in output and "model_unbound" in output


_MINIMAL_MODEL = MODEL_SOURCE.read_text(encoding="utf-8").replace(
    'MODEL_ID = "order_placement"', 'MODEL_ID = "minimal"').replace(
    'IMPLEMENTED_BY = {"PlaceOrder": "shop/orders.py:OrderService.place"}', 'IMPLEMENTED_BY = {}').replace(
    "def conformance():", "def _unused_conformance():")


@pytest.mark.parametrize("hook", ["def conformance():\n    return None\n",
                                  "def conformance():\n    return True\n",
                                  "def broken_variants():\n    return {}\n"])
def test_defined_proof_hooks_cannot_silently_do_nothing(tmp_path, hook):
    from flowguard.map.proof import run_model
    write(tmp_path, ".flowguard/models/minimal.py", _MINIMAL_MODEL + hook)
    result = run_model(tmp_path, tmp_path / ".flowguard/models/minimal.py")
    assert result.status == "error" and "no " in " ".join(result.problems)


def test_abstract_model_fails_and_design_only_is_the_one_exemption(tmp_path):
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
    write(tmp_path, ".flowguard/models/minimal.py", _MINIMAL_MODEL + '\nDESIGN_ONLY = "the order service is not written yet"\n')
    result = run_model(tmp_path, tmp_path / ".flowguard/models/minimal.py")
    assert result.status == "pass" and any("design only" in warning for warning in result.warnings)
    native = _native_model(tmp_path, tmp_path / ".flowguard/models/minimal.py")
    assert native.status == "pass" and any("design only" in warning for warning in native.warnings)


def test_no_models_output_is_explicitly_not_model_proof(tmp_path):
    from flowguard.map.proof import render_results, run_models
    assert render_results(run_models(tmp_path, [])) == "models: 0 declared, 0 executed; no model proof"


def test_unanchored_python_syntax_error_is_a_check_error(shop, capsys):
    write(shop, "shop/unanchored.py", "def broken(:\n")
    assert cli.main(["--root", str(shop), "check"]) == 1
    output = capsys.readouterr().out
    assert "shop/unanchored.py" in output and "SyntaxError" in output


def test_component_selector_reports_its_registered_model_ids(shop, capsys):
    code, output = models(shop, capsys, "orders")
    assert code == 1 and "is a component id" in output and "registered model ids: order_placement" in output


def test_runner_output_in_any_language_never_breaks_the_verdict(tmp_path, monkeypatch):
    from flowguard.map.proof import run_runner
    monkeypatch.setenv("PYTHONIOENCODING", "cp1252")          # the code page a Windows pipe gives a child
    runner = tmp_path / ".flowguard/verification/owners/shop/run_checks.py"
    runner.parent.mkdir(parents=True)
    write(tmp_path, "app.py", "def run():\n    return 1\n")
    runner.write_text("from flowguard.map.runner import run_owner\nimport app\nIMPLEMENTED_BY = {'App': 'app.py:run'}\n"
                      "from flowguard.explorer import Explorer\nfrom flowguard.workflow import Workflow\n"
                      "def main():\n    print('运行检查 ✓', app.run())\n"
                      "    return Explorer(Workflow(()), (0,), (1,), progress_steps=0).explore()\n"
                      "raise SystemExit(run_owner(main))\n", encoding="utf-8")
    assert run_runner(tmp_path, runner).status == "pass"
    runner.write_text("print('失败 ✗')\nraise SystemExit(1)\n", encoding="utf-8")
    result = run_runner(tmp_path, runner)
    assert result.status == "fail" and "失败 ✗" in result.problems[0], result.problems


def test_out_of_boundary_inputs_never_report_a_stale_pass(shop, capsys, monkeypatch):
    write(shop, ".gitignore", "shop/local_settings.py\n")
    write(shop, "shop/local_settings.py", "ENABLED = True\n")
    write(shop, "shop/orders.py", "from os import environ\nfrom shop import local_settings\n" + FIXED.replace(
        "        if order_id in self.orders:\n",
        "        if order_id in self.orders or not local_settings.ENABLED or environ.get('SHOP_MODE') == 'off':\n"))
    assert models(shop, capsys)[0] == 0
    write(shop, "shop/local_settings.py", "ENABLED = False\n")
    assert models(shop, capsys)[0] == 1
    write(shop, "shop/local_settings.py", "ENABLED = True\n")
    assert models(shop, capsys)[0] == 0
    monkeypatch.setenv("SHOP_MODE", "off")
    assert models(shop, capsys)[0] == 1


MODEL = ".flowguard/models/order_placement.py"


def _edit_model(root, old, new):
    path = root / MODEL
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


@pytest.mark.parametrize("case", ["fake_conformance", "removed_conformance"])
def test_model_that_never_runs_its_implemented_by_code_fails(shop, capsys, case):
    write(shop, "shop/orders.py", FIXED)
    if case == "fake_conformance":
        _edit_model(shop, "def conformance():\n", "def conformance():\n    from types import SimpleNamespace\n"
              "    return SimpleNamespace(ok=True, format_text=lambda **k: '')\n\n\ndef _old():\n")
    else:
        _edit_model(shop, "def conformance():\n", "def _old_conformance():\n")
    code, out = models(shop, capsys)
    assert code == 1 and "never ran" in out
    native = _native_model(shop, shop / MODEL)
    assert native.status == "fail" and "never ran" in " ".join(native.problems)


def test_abstract_model_with_empty_implemented_by_fails(shop, capsys):
    write(shop, "shop/orders.py", FIXED)
    _edit_model(shop, 'IMPLEMENTED_BY = {"PlaceOrder": "shop/orders.py:OrderService.place"}', "IMPLEMENTED_BY = {}")
    _edit_model(shop, "def conformance():\n", "def _old_conformance():\n")
    code, out = models(shop, capsys)
    assert code == 1 and "abstract boundary only" in out and "declares no IMPLEMENTED_BY anchors" in out


def test_non_python_anchor_is_a_warning_not_a_failure(shop, capsys):
    write(shop, "shop/orders.py", FIXED)
    write(shop, "web/cart.ts", "export function addItem(c, i) { return [...c, i]; }\n")
    map_path = shop / ".flowguard/map.json"
    data = json.loads(map_path.read_text())
    data["components"].append(dict(data["components"][0], id="ui", summary="Cart interface",
        responsibilities=["render shopping cart"], files=["web/cart.ts"], entrypoints=[], tests=[], models=[],
        state=[], side_effects=[]))
    map_path.write_text(json.dumps(data))
    _edit_model(shop, 'IMPLEMENTED_BY = {"PlaceOrder": "shop/orders.py:OrderService.place"}',
          'IMPLEMENTED_BY = {"PlaceOrder": "shop/orders.py:OrderService.place", "Ui": "web/cart.ts:addItem"}')
    code, out = models(shop, capsys)
    assert code == 0 and "is not Python" in out


_CRASH = ("return {\"charge_every_time\": _explorer(ChargeEveryTime())}",
          "return {\"charge_every_time\": _explorer(Crashes())}")


@pytest.mark.parametrize("case", ["crash", "invariant_crash", "other_invariant", "same_name_wrong_predicate", "budget", "budget_after_violation", "design_without_invariants"])
def test_broken_variant_must_violate_a_design_property(shop, capsys, case):
    write(shop, "shop/orders.py", FIXED)
    if case == "crash":
        _edit_model(shop, *_CRASH)
        _edit_model(shop, "INVARIANTS = (", "class Crashes(PlaceOrder):\n    def apply(self, inp, state):\n"
              "        raise RuntimeError('boom')\n\n\nINVARIANTS = (")
        expected = "fails without violating"
    elif case == "invariant_crash":
        _edit_model(shop, 'return {"charge_every_time": _explorer(ChargeEveryTime())}',
                    "def raising(state, trace):\n        raise RuntimeError('oracle crashed')\n"
                    "    raising.__name__ = 'one_charge_per_order'\n"
                    "    return {'charge_every_time': Explorer(workflow=Workflow((PlaceOrder(),)), "
                    "initial_states=(State(),), external_inputs=INPUTS, invariants=(raising,), progress_steps=0)}")
        expected = "fails without violating"
    elif case in {"other_invariant", "same_name_wrong_predicate"}:
        _edit_model(shop, "return {\"charge_every_time\": _explorer(ChargeEveryTime())}",
              "from flowguard import Invariant, InvariantResult\n"
              "    never = Invariant('never', 'always fails', lambda s, t: InvariantResult.fail('x'))\n"
              "    return {'charge_every_time': Explorer(workflow=Workflow((PlaceOrder(),)), initial_states=(State(),), "
              "external_inputs=INPUTS, invariants=(never,), max_sequence_length=3, progress_steps=0)}")
        if case == "same_name_wrong_predicate":
            _edit_model(shop, "Invariant('never',", "Invariant('one_charge_per_order',")
        expected = "fails without violating"
    elif case in {"budget", "budget_after_violation"}:
        block = "ChargeEveryTime()" if case == "budget_after_violation" else "PlaceOrder()"
        limit = 4 if case == "budget_after_violation" else 1
        _edit_model(shop, 'return {"charge_every_time": _explorer(ChargeEveryTime())}',
                    f"bad = Explorer(workflow=Workflow(({block},)), initial_states=(State(),), "
                    f"external_inputs=INPUTS, invariants=INVARIANTS, max_sequence_length=3, progress_steps=0, max_transitions={limit})\n"
                    + ("    report = bad.explore()\n"
                       "    assert report.exploration_status == 'budget_exhausted'\n"
                       "    assert any(v.invariant_name == 'one_charge_per_order' for v in report.violations)\n"
                       if case == "budget_after_violation" else "")
                    + "    return {'charge_every_time': bad}")
        expected = "fails without violating"
    else:
        _edit_model(shop, "def build_explorer() -> Explorer:\n    return _explorer(PlaceOrder())",
              "def build_explorer() -> Explorer:\n    return Explorer(workflow=Workflow((PlaceOrder(),)), "
              "initial_states=(State(),), external_inputs=INPUTS, invariants=(), max_sequence_length=3, progress_steps=0)")
        expected = "declares no invariants"
    code, out = models(shop, capsys)
    assert code == 1 and expected in out
    if case != "design_without_invariants":
        assert "invariant 'one_charge_per_order' is violated by no known-bad variant" in out
    native = _native_model(shop, shop / MODEL)
    assert native.status == "fail" and expected in " ".join(native.problems)
    if case != "design_without_invariants":
        assert any("invariant 'one_charge_per_order' is violated by no known-bad variant" in warning
                   for warning in native.warnings)


def test_plain_function_invariant_is_accepted(shop, capsys):
    write(shop, "shop/orders.py", FIXED)
    _edit_model(shop, "INVARIANTS = (at_most_once_by(",
          "def one_charge_per_order(state, trace):\n    return len(set(state.charges)) == len(state.charges)\n\n\n"
          "INVARIANTS = (one_charge_per_order,)\n_UNUSED = (at_most_once_by(")
    code, out = models(shop, capsys)
    assert code == 0, out


@pytest.mark.parametrize("body,status", [("raise SystemExit(0)", "pass"), ("raise SystemExit(run_owner(lambda: 0))", "pass"),
                                         ("raise SystemExit(run_owner(lambda: None))", "error"),
                                         ("raise SystemExit(run_owner(lambda: []))", "fail")])
def test_runner_verdict_is_its_exit_code(tmp_path, body, status):
    from flowguard.map.proof import run_runner
    path = tmp_path / ".flowguard/verification/owners/shop/run_checks.py"
    write(tmp_path, "app.py", "def run():\n    return 0\n")
    write(tmp_path, path.relative_to(tmp_path).as_posix(), "from flowguard.map.runner import run_owner\nimport app\n"
          "IMPLEMENTED_BY = {'App': 'app.py:run'}\napp.run()\n" + body + "\n")
    result = run_runner(tmp_path, path)
    assert result.status == status, result.problems
    assert any("run_owner(main)" in w for w in result.warnings) == ("run_owner(" not in body)


def test_non_explorer_proves_nothing(tmp_path):
    from flowguard.map.proof import run_model
    write(tmp_path, ".flowguard/models/fake.py", "from types import SimpleNamespace\nMODEL_ID='fake'\ndef build_explorer():\n    return SimpleNamespace(explore=lambda: SimpleNamespace(ok=True))\n")
    result = run_model(tmp_path, tmp_path / ".flowguard/models/fake.py")
    assert result.status == "error" and "Explorer" in " ".join(result.problems)


def test_no_broken_variants_is_an_error(tmp_path):
    from flowguard.map.proof import run_model
    source = _MINIMAL_MODEL.replace("def broken_variants()", "def unused_variants()")
    write(tmp_path, ".flowguard/models/minimal.py", source)
    result = run_model(tmp_path, tmp_path / ".flowguard/models/minimal.py")
    assert result.status == "error" and "no broken_variants" in " ".join(result.problems)


def test_tested_by_must_name_a_design_invariant(shop, capsys):
    write(shop, "shop/orders.py", FIXED)
    path = shop / MODEL
    source = path.read_text(encoding="utf-8")
    write(shop, MODEL, source + '\nTESTED_BY = {"no_such_invariant": ["tests/test_orders.py:test_place_once"]}\n')
    code, out = models(shop, capsys)
    assert code == 1 and "no_such_invariant" in out
    native = _native_model(shop, shop / MODEL)
    assert native.status == "fail" and "no_such_invariant" in " ".join(native.problems)


@pytest.mark.parametrize("location", ["hook", "adapter_reset", "adapter_step"])
def test_conformance_import_error_reports_interpreter_environment(shop, capsys, location):
    write(shop, "shop/orders.py", FIXED)
    if location == "hook":
        _edit_model(shop, "def conformance():\n", "def conformance():\n    import nonexistent_third_party_dependency\n")
    elif location == "adapter_reset":
        write(shop, "shop/orders.py", "import nonexistent_third_party_dependency\n" + FIXED)
    else:
        write(shop, "shop/orders.py", FIXED.replace("        if order_id in self.orders:",
                                                  "        import nonexistent_third_party_dependency\n        if order_id in self.orders:"))
    code, out = models(shop, capsys)
    assert code == 1 and "ERROR" in out and "interpreter" in out and "environment" in out
    assert "does not conform" not in out


def test_runner_must_call_or_read_its_anchored_code(tmp_path):
    from flowguard.map.proof import run_runner
    write(tmp_path, "app.py", "def run():\n    return 1\n")
    source = ("from flowguard.map.runner import run_owner\nIMPLEMENTED_BY = {'App': 'app.py:run'}\n"
              "def main():\n    return 0\n"
              "raise SystemExit(run_owner(main))\n")
    path = tmp_path / ".flowguard/verification/owners/shop/run_checks.py"
    rel = path.relative_to(tmp_path).as_posix()
    write(tmp_path, rel, source)
    result = run_runner(tmp_path, path, own_files={"app.py"})
    problems = " ".join(result.problems)
    assert result.status == "fail" and "abstract boundary only" in problems and "never ran" in problems
    write(tmp_path, rel, "import app\n" + source)
    result = run_runner(tmp_path, path, own_files={"app.py"})
    assert result.status == "fail" and "never ran" in " ".join(result.problems)       # importing is not consulting
    write(tmp_path, rel, "import app\napp.run()\n" + source)
    result = run_runner(tmp_path, path, own_files={"app.py"})
    assert result.status == "pass" and not result.warnings, result.problems
    write(tmp_path, rel, "from flowguard.map.facts import CodeFacts\nCodeFacts().present('run', ['app.py'])\n" + source)
    result = run_runner(tmp_path, path, own_files={"app.py"})
    assert result.status == "pass", result.problems                                   # read as code facts


def test_explorer_with_no_initial_states_proves_nothing(shop, capsys):
    write(shop, "shop/orders.py", FIXED)
    _edit_model(shop, "def build_explorer() -> Explorer:\n    return _explorer(PlaceOrder())",
                "def build_explorer() -> Explorer:\n    return Explorer(workflow=Workflow((PlaceOrder(),)), "
                "initial_states=(), external_inputs=INPUTS, invariants=INVARIANTS, progress_steps=0)")
    code, out = models(shop, capsys)
    assert code == 1 and "explored no input transitions" in out


@pytest.mark.skipif(os.name == "nt", reason="POSIX process-group cleanup")
@pytest.mark.parametrize("kind", ["runner", "contract"])
def test_model_timeout_cleans_its_spawned_child(tmp_path, kind):
    from flowguard.map.proof import run_model, run_runner
    body = (
        "import subprocess,sys,time\nfrom pathlib import Path\n"
        "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'])\n"
        "Path('child.pid').write_text(str(child.pid))\ntime.sleep(30)\n"
    )
    if kind == "runner":
        path = tmp_path / ".flowguard" / "probe" / "run_checks.py"
        function = run_runner
    else:
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


RUNNER = ".flowguard/verification/owners/orders_check/run_checks.py"
RUNNER_SOURCE = ('"""Runner model: places an order through the real OrderService."""\n'
                 'from flowguard.map.runner import run_owner\n\n'
                 'IMPLEMENTED_BY = {"Place": "ANCHOR"}\n'
                 'TESTED_BY = {"places_once": ["tests/test_orders.py:test_place_once"]}\n\n\n'
                 'def main():\n    from shop.orders import OrderService\n'
                 '    return 0 if OrderService().place("o1", 5) == "placed" else 1\n\n\n'
                 'if __name__ == "__main__":\n    raise SystemExit(run_owner(main))\n')


def _runner_project(shop, anchor):
    write(shop, "shop/orders.py", FIXED)
    write(shop, RUNNER, RUNNER_SOURCE.replace("ANCHOR", anchor))
    data = json.loads((shop / ".flowguard/map.json").read_text(encoding="utf-8"))
    data["components"][0]["models"].append(RUNNER)
    (shop / ".flowguard/map.json").write_text(json.dumps(data), encoding="utf-8")


def _check_codes(shop, capsys):
    cli.main(["--root", str(shop), "check"])
    return capsys.readouterr().out


def test_runner_models_follow_the_same_binding_rule(shop, capsys):
    _runner_project(shop, "REPLACE_ME/orders.py:place")
    out = _check_codes(shop, capsys)
    assert "model_anchor_broken" in out and "placeholder anchor 'REPLACE_ME/orders.py:place'" in out
    code, output = models(shop, capsys, "orders_check")
    assert code == 1 and "placeholder anchor" in output
    _runner_project(shop, "shop/orders.py:OrderService.place")
    assert "orders_check" not in _check_codes(shop, capsys)
    assert models(shop, capsys, "orders_check")[0] == 0
    write(shop, "shop/orders.py", FIXED.replace("def place(", "def place_order(").replace("return \"placed\"", "return 'placed'"))
    out = _check_codes(shop, capsys)
    assert "model_anchor_broken" in out and "symbol 'OrderService.place' not found in shop/orders.py" in out


def test_runner_is_selected_by_its_anchored_file_and_its_tests(shop, capsys):
    _runner_project(shop, "shop/orders.py:OrderService.place")
    cli.main(["--root", str(shop), "confirm", "orders"])
    capsys.readouterr()
    assert cli.main(["--root", str(shop), "impact", "shop/orders.py"]) == 0
    assert "orders_check" in capsys.readouterr().out
    assert cli.main(["--root", str(shop), "impact", "tests/test_orders.py"]) == 0
    assert "orders_check" in capsys.readouterr().out


def test_unbound_models_are_errors_in_check(shop, capsys):
    write(shop, "shop/orders.py", FIXED)
    _edit_model(shop, 'IMPLEMENTED_BY = {"PlaceOrder": "shop/orders.py:OrderService.place"}', "IMPLEMENTED_BY = {}")
    _edit_model(shop, "def conformance():\n", "def _old_conformance():\n")
    out = _check_codes(shop, capsys)
    assert "model_anchor_missing" in out and "model_conformance_missing" in out
    _edit_model(shop, "IMPLEMENTED_BY = {}", 'IMPLEMENTED_BY = {}\nDESIGN_ONLY = "the order service is not written yet"')
    out = _check_codes(shop, capsys)
    assert "model_anchor_missing" not in out and "model_conformance_missing" not in out
    cli.main(["--root", str(shop), "lint"])
    assert "model_design_only" in capsys.readouterr().out


def test_verify_without_user_models_runs_the_builtin_system(tmp_path, capsys):
    write(tmp_path, ".flowguard/map.json", json.dumps({
        "schema": "flowguard.map.v1", "project": "empty", "components": []}))
    assert cli.main(["--root", str(tmp_path), "verify"]) == 0
    output = capsys.readouterr().out
    assert output.count("models: 1 declared, 1 executed") == 1
    assert "PASS  system" in output and "no model proof" not in output
    assert "no known-bad variants could be generated" in output


def test_release_fails_when_an_invariant_has_no_breaking_variant(shop, capsys, monkeypatch):
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
    assert code == 0 and "invariant 'orders_are_unique' is violated by no known-bad variant" in output
    assert cli.main(['--root', str(shop), 'verify']) == 1
    output = capsys.readouterr().out
    assert 'models: 1 invariant(s) violated by no known-bad variant: order_placement:orders_are_unique' in output
    assert 'verify: FAIL' in output
    assert captured[0].status == 'pass' and captured[0].uncovered_invariants == ['orders_are_unique']
    assert ModelResult(**{'model': 'legacy', 'file': 'legacy.py'}).uncovered_invariants == []


@pytest.mark.parametrize("mode,expected", [("clean", None), ("layer", "layer_violation"),
    ("cycle", "shortest cycle:"), ("no_layers", "no layers in the map"),
    ("duplicate", "duplicate_owner"), ("reserved", "reserved for the root node"),
    ("broken_anchor", "the map does not match the code:"),
    ("uncaught_variant", "passed: the architecture rules do not catch it")])
def test_builtin_system_model(shop, capsys, monkeypatch, mode, expected):
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
    model_path.write_text("raise AssertionError('system imported user model')\n" + MODEL_SOURCE.read_text())
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
    variants = list(system_model._variants(data, graph))
    assert {name for name, _, _ in variants} == {
        "a_closes_cycle_with_b", "a_duplicates_b", "b_imports_a", "b_duplicates_a"}
    assert all(any(f.level == "error" for f in system_model._rules(changed, edges))
               for _, changed, edges in variants)
    accepted = {**data, "accepted_debts": [
        {"code": "dependency_cycle", "members": ["a", "b"], "reason": "existing cycle policy"},
        {"code": "layer_violation", "reason": "existing boundary policy"},
        {"code": "duplicate_owner", "reason": "existing shared responsibility"}]}
    assert list(system_model._variants(accepted, graph)) == []
    # A missing architecture rule is not evidence that a mutation was debt-accepted.
    monkeypatch.setattr(lint, "structural_findings", lambda *args, **kwargs: [])
    remaining = list(system_model._variants(data, graph))
    assert {name for name, _, _ in remaining} >= {"a_closes_cycle_with_b", "b_imports_a"}
    assert any(not system_model._rules(changed, edges) for _, changed, edges in remaining)


@pytest.mark.parametrize("mode,problem", [
    ("call", None), ("empty", "tested_by_misses_anchor"), ("fail", "tested_by_failed"),
    ("default", None), ("import_only", "tested_by_misses_anchor"), ("read_after_import", None),
    ("os_read_without_accmode", None),
    ("subprocess", "tested_by_misses_anchor"), ("mixed", "tested_by_misses_anchor"),
    ("parameter_miss", "tested_by_misses_anchor"), ("parameter_fail", "tested_by_failed"),
    ("nested_conformance", None), ("initializer_body", None), ("initializer_read", None),
    ("write_only", "tested_by_misses_anchor"),
    ("class_method", None), ("subtest_fail", "tested_by_failed")])
def test_tested_by_must_reach_the_anchored_code(shop, capsys, mode, problem):
    write(shop, "shop/orders.py", FIXED)
    write(shop, "shop/other.py", "def marker():\n    return 1\n")
    model_path = shop / ".flowguard/models/order_placement.py"
    source = MODEL_SOURCE.read_text().replace(
        'IMPLEMENTED_BY = {"PlaceOrder": "shop/orders.py:OrderService.place"}',
        'IMPLEMENTED_BY = {"PlaceOrder": "shop/orders.py:OrderService.place", "Other": "shop/other.py:marker"}')
    source += "\n_base_conformance = conformance\ndef conformance():\n    from shop.other import marker\n    assert marker() == 1\n    return _base_conformance()\n"
    anchors = ["tests/test_orders.py:test_bound"]
    call = "    from shop.orders import OrderService\n    assert OrderService().place('x', 1) == 'placed'\n"
    header = "from pathlib import Path\nimport pytest\n"
    body = "def test_bound():\n" + call
    if mode in {"empty", "default"}:
        body = "def test_bound():\n    assert True\n"
    elif mode == "fail":
        body += "    assert False, 'real pytest failure after actual anchor call'\n"
    elif mode == "import_only":
        body = "def test_bound():\n    import shop.orders\n    assert shop.orders.__name__ == 'shop.orders'\n"
    elif mode == "read_after_import":
        body = "def test_bound():\n    import shop.orders\n    assert 'def place' in (Path(__file__).parents[1] / 'shop/orders.py').read_text()\n"
    elif mode == "os_read_without_accmode":
        body = ("def test_bound(monkeypatch):\n    import os\n"
                "    monkeypatch.delattr(os, 'O_ACCMODE', raising=False)\n"
                "    fd = os.open(Path(__file__).parents[1] / 'shop/orders.py', os.O_RDONLY)\n"
                "    try:\n        assert b'def place' in os.read(fd, 4096)\n"
                "    finally:\n        os.close(fd)\n")
    elif mode == "subprocess":
        body = "def test_bound():\n    import subprocess, sys\n    p = subprocess.run([sys.executable, '-c', \"from shop.orders import OrderService; print(OrderService().place('x',1))\"], capture_output=True, text=True, check=True)\n    assert p.stdout.strip() == 'placed'\n"
    elif mode == "mixed":
        body += "def test_empty():\n    assert True\n"
        anchors.append("tests/test_orders.py:test_empty")
    elif mode in {"parameter_miss", "parameter_fail"}:
        body = "@pytest.mark.parametrize('hit', [True, False])\ndef test_bound(hit):\n"
        body += ("    if hit:\n" + "\n".join("    " + line for line in call.rstrip().splitlines()) + "\n" if mode == "parameter_miss" else call + "    assert hit\n")
    elif mode == "nested_conformance":
        body = "def test_bound():\n    from flowguard.map.proof import run_model_in_process\n    root = Path(__file__).parents[1]\n    assert run_model_in_process(root, root / '.flowguard/models/order_placement.py').status == 'pass'\n"
    elif mode == "initializer_body":
        write(shop, "shop/__init__.py", "from .orders import OrderService\nassert OrderService().place('init',1) == 'placed'\n")
        body = "def test_bound():\n    import shop\n    assert shop.__name__ == 'shop'\n"
    elif mode == "initializer_read":
        write(shop, "shop/__init__.py", "from pathlib import Path\nassert 'def place' in (Path(__file__).parent / 'orders.py').read_text()\n")
        body = "def test_bound():\n    import shop\n    assert shop.__name__ == 'shop'\n"
    elif mode == "write_only":
        body = "def test_bound():\n    with (Path(__file__).parents[1] / 'shop/orders.py').open('a') as stream:\n        stream.write('\\n')\n    assert True\n"
    elif mode == "class_method":
        body = "class TestOrders:\n    def test_bound(self):\n" + "\n".join("    " + line for line in call.rstrip().splitlines()) + "\n"
    elif mode == "subtest_fail":
        body = "def test_bound(subtests):\n" + call + "    with subtests.test('real failure'):\n        assert False\n"
    write(shop, "tests/test_orders.py", header + body)
    model_path.write_text(source + "\nTESTED_BY = " + repr({"one_charge_per_order": anchors}) + "\n")
    options = [] if mode == "default" else ["--tests"]
    code, output = models(shop, capsys, "order_placement", *options)
    assert code == (1 if problem else 0), output
    if problem:
        assert problem in output and "one_charge_per_order -> tests/test_orders.py:" in output
    if mode == "parameter_miss":
        assert "[False]" in output


@pytest.mark.parametrize("hit", [True, False])
def test_runner_bound_tests_observe_their_own_call(tmp_path, hit):
    from flowguard.map.proof import run_runner

    write(tmp_path, "app.py", "def run():\n    return 1\n")
    write(tmp_path, "tests/test_app.py", "def test_app():\n" + (
        "    import app\n    assert app.run() == 1\n" if hit else "    assert True\n"))
    runner = tmp_path / ".flowguard/verification/owners/app/run_checks.py"
    write(tmp_path, runner.relative_to(tmp_path).as_posix(),
          "from flowguard.map.runner import run_owner\nimport app\n"
          "from flowguard.explorer import Explorer\nfrom flowguard.workflow import Workflow\n"
          "IMPLEMENTED_BY = {'App': 'app.py:run'}\n"
          "TESTED_BY = {'app_result': ['tests/test_app.py:test_app']}\n"
          "def main():\n    assert app.run() == 1\n"
          "    return Explorer(Workflow(()), (0,), (1,), progress_steps=0).explore()\n"
          "raise SystemExit(run_owner(main))\n")
    result = run_runner(tmp_path, runner, tests=True)
    assert result.status == ("pass" if hit else "fail"), result.problems
    if not hit:
        assert any("tested_by_misses_anchor app_result" in p for p in result.problems)


def test_bound_tests_without_pytest_are_an_environment_error(shop, monkeypatch):
    from flowguard.map import proof

    write(shop, "shop/orders.py", FIXED)
    path = shop / ".flowguard/models/order_placement.py"
    path.write_text(MODEL_SOURCE.read_text() +
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


def test_bound_test_method_cannot_impersonate_a_top_level_anchor(shop, capsys):
    write(shop, "shop/orders.py", FIXED +
          "\ndef run():\n    return 'top'\n\nclass Other:\n    def run(self):\n        return 'other'\n")
    path = shop / ".flowguard/models/order_placement.py"
    source = MODEL_SOURCE.read_text().replace("shop/orders.py:OrderService.place", "shop/orders.py:run")
    source += ("\n_base_conformance = conformance\ndef conformance():\n"
               "    from shop.orders import run\n    assert run() == 'top'\n    return _base_conformance()\n"
               "TESTED_BY = {'one_charge_per_order': ['tests/test_orders.py:test_bound']}\n")
    path.write_text(source)
    write(shop, "tests/test_orders.py",
          "def test_bound():\n    from shop.orders import Other\n    assert Other().run() == 'other'\n")
    code, output = models(shop, capsys, "order_placement", "--tests")
    assert code == 1, output
    assert "tested_by_misses_anchor one_charge_per_order" in output


@pytest.mark.parametrize('with_map,parent_first', [(True, False), (False, False), (True, True)],
                         ids=['map', 'no_map', 'from_import_after_parent'])
def test_child_start_gap_warns_when_the_child_misses_parent_states(tmp_path, capsys, with_map, parent_first):
    from flowguard.map.proof import run_model

    write(tmp_path, 'counter.py', 'def increment(value):\n    return value + 1\n')
    write(tmp_path, 'tests/test_counter.py', 'def test_increment():\n    from counter import increment\n    assert increment(0) == 1\n')
    parent = '''from dataclasses import dataclass
from types import SimpleNamespace
from flowguard.core import FunctionResult, Invariant
from flowguard.explorer import Explorer
from flowguard.workflow import Workflow
MODEL_ID = "counter_parent"
COMPONENTS = ["counter"]
IMPLEMENTED_BY = {"Increment": "counter.py:increment"}
TESTED_BY = {"non_negative": ["tests/test_counter.py:test_increment"]}
@dataclass(frozen=True)
class State:
    value: int = 0
class Tick:
    name = "tick"
    def __init__(self, delta=1): self.delta = delta
    def apply(self, inp, state):
        return [FunctionResult(inp, State(state.value + self.delta))]
def make_explorer(starts=None, delta=1):
    return Explorer(Workflow((Tick(delta),)), initial_states=(State(),) if starts is None else starts,
                    external_inputs=(1,), max_sequence_length=3, progress_steps=0,
                    invariants=(Invariant("non_negative", "counter is nonnegative", lambda s, t: s.value >= 0),))
def build_explorer(): return make_explorer()
def broken_variants(): return {"decrements": make_explorer(delta=-1)}
def conformance():
    from counter import increment
    ok = all(increment(n) == n + 1 for n in range(6))
    return SimpleNamespace(ok=ok, format_text=lambda **kwargs: "counter increment replay")
'''
    child = '''import parent
MODEL_ID = "counter_child"
PARENT = "counter_parent"
COMPONENTS = ["counter"]
IMPLEMENTED_BY = {"Increment": "counter.py:increment"}
TESTED_BY = {"non_negative": ["tests/test_counter.py:test_increment"]}
STARTS = (parent.State(),)
def project_parent_state(state): return state
def build_explorer(): return parent.make_explorer(STARTS)
def broken_variants(): return parent.broken_variants()
def conformance(): return parent.conformance()
'''
    write(tmp_path, '.flowguard/models/parent.py', parent)
    path = tmp_path / '.flowguard/models/child.py'
    write(tmp_path, '.flowguard/models/child.py', child)
    if with_map:
        write(tmp_path, '.flowguard/map.json', json.dumps(dict(schema='flowguard.map.v1', components=[
            dict(id='counter', files=['counter.py'], tests=['tests/test_counter.py'], models=[], depends_on=[],
                 status='draft', summary='Counter', responsibilities=['increment a counter'])])))
    without_projection = child.replace('def project_parent_state(state): return state\n', '')
    path.write_text(without_projection)
    code, output = models(tmp_path, capsys, 'counter_child')
    assert code == 0 and 'child_start_gap' not in output, output
    path.write_text(child)
    if parent_first:
        import sys

        path.write_text(child.replace('import parent',
            'from parent import State, make_explorer, broken_variants as parent_variants, conformance as parent_conformance')
            .replace('parent.State()', 'State()').replace('parent.make_explorer(', 'make_explorer(')
            .replace('parent.broken_variants()', 'parent_variants()')
            .replace('parent.conformance()', 'parent_conformance()'))
        script = '''import json, sys
from dataclasses import asdict
from pathlib import Path
from flowguard.map.proof import run_model_in_process
root = Path(sys.argv[1])
parent = run_model_in_process(root, root / '.flowguard/models/parent.py')
print(json.dumps(asdict(parent)), flush=True)
child = run_model_in_process(root, root / '.flowguard/models/child.py')
print(json.dumps(asdict(child)), flush=True)
assert parent.status == child.status == 'pass', (parent, child)
assert any('child_start_gap: 3 of 4' in warning for warning in child.warnings), child
'''
        result = subprocess.run([sys.executable, '-c', script, str(tmp_path)], cwd=tmp_path,
                                capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        return
    code, output = models(tmp_path, capsys, 'counter_child')
    assert code == 0, output
    assert "child_start_gap: 3 of 4 states the parent 'counter_parent' reaches" in output
    if with_map:
        from flowguard.map.cli import _context
        from flowguard.map.check import run_check
        data, inv = _context(tmp_path)
        assert not {'parent_cycle', 'parent_import_mismatch'} & {f.code for f in run_check(tmp_path, data, inv)}
    seeded = child.replace('STARTS = (parent.State(),)',
                           'from flowguard.kit import reachable_states\nSTARTS = reachable_states(parent.build_explorer())')
    path.write_text(seeded)
    code, output = models(tmp_path, capsys, 'counter_child')
    assert code == 0 and 'child_start_gap' not in output, output

    local = without_projection.replace('STARTS = (parent.State(),)',
        'from dataclasses import dataclass\n@dataclass(frozen=True)\nclass LocalState:\n    value: int = 0\nSTARTS = (LocalState(),)')
    path.write_text(local)
    result = run_model(tmp_path, path)
    assert result.status == 'pass' and not any('child_start_gap' in w for w in result.warnings), result
    path.write_text(local + '\ndef project_parent_state(state): return LocalState(state.value)\n')
    result = run_model(tmp_path, path)
    assert result.status == 'pass' and any('child_start_gap: 3 of 4' in w for w in result.warnings), result

    path.write_text(child)
    write(tmp_path, '.flowguard/models/parent.py', parent.replace(
        'def build_explorer(): return make_explorer()',
        'def build_explorer(): raise RuntimeError("port unavailable\\nextra detail")'))
    result = run_model(tmp_path, path)
    assert result.status == 'pass', result
    warning = next(w for w in result.warnings if 'child_start_gap not checked:' in w)
    assert "parent 'counter_parent' could not be explored (port unavailable)" in warning
    assert '\n' not in warning
    path.write_text(without_projection)
    result = run_model(tmp_path, path)
    assert result.status == 'pass' and not any('child_start_gap' in w for w in result.warnings), result


def test_grouped_sub_check_under_a_parent_gets_no_start_gap_warning(tmp_path, capsys):
    write(tmp_path, 'counter.py', 'def valid(value):\n    return value >= 0\n')
    write(tmp_path, 'tests/test_counter.py',
          'def test_valid():\n    from counter import valid\n    assert valid(0) and not valid(-1)\n')
    source = '''from flowguard.kit import Feature, feature_explorer, feature_variants, feature_conformance
MODEL_ID = "MODEL_NAME"
COMPONENTS = ["counter"]
IMPLEMENTED_BY = {"Validate": "counter.py:valid"}
TESTED_BY = {"each_defect_rejected": ["tests/test_counter.py:test_valid"]}
FEATURES = (Feature("negative", True, apply=lambda value: -1), EXTRA_FEATURE)
def build_explorer(): return feature_explorer(FEATURES)
def broken_variants(): return feature_variants(FEATURES)
def conformance():
    from counter import valid
    return feature_conformance(FEATURES, lambda: 0, valid)
'''
    write(tmp_path, '.flowguard/models/parent.py', source.replace('MODEL_NAME', 'counter_parent')
          .replace('EXTRA_FEATURE', 'Feature("positive", False, apply=lambda value: value if value < 0 else 1),'))
    write(tmp_path, '.flowguard/models/child.py', source.replace('MODEL_NAME', 'counter_child')
          .replace('EXTRA_FEATURE', '') + '\nPARENT = "counter_parent"\n')
    code, output = models(tmp_path, capsys, 'counter_parent', 'counter_child')
    assert code == 0 and 'models: 2 passed, 0 failed' in output and 'child_start_gap' not in output, output


@pytest.mark.parametrize("location", ["conformance", "explore"])
def test_placeholder_anchor_failures_are_clean_in_hooks_and_exploration(shop, capsys, location):
    write(shop, "shop/orders.py", FIXED)
    call = "    from flowguard.map.facts import load_anchor\n    load_anchor('REPLACE_ME/module.py:Owner')\n"
    if location == "conformance":
        _edit_model(shop, "def conformance():\n", "def conformance():\n" + call)
    else:
        _edit_model(shop, "    def apply(self, inp: Place, state: State):\n",
                    "    def apply(self, inp: Place, state: State):\n" + "\n".join("    " + line for line in call.rstrip().split("\n")) + "\n")
    code, output = models(shop, capsys, "order_placement")
    assert code == 1 and "FAIL" in output and "ERROR" not in output
    assert "placeholder anchor 'REPLACE_ME/module.py:Owner': replace it with the real 'path:Symbol' this model is about" in output
    assert "Traceback" not in output
    assert "explored no input transitions" not in output


@pytest.mark.parametrize("mixed_keys", [False, True])
def test_models_output_lists_rule_and_variant_names(shop, capsys, monkeypatch, mixed_keys):
    write(shop, "shop/orders.py", FIXED)
    expected_bad = ["charge_every_time"]
    if mixed_keys:
        _edit_model(shop, 'return {"charge_every_time": _explorer(ChargeEveryTime())}',
                    'return {1: _explorer(ChargeEveryTime()), "1": _explorer(ChargeEveryTime()), '
                    '"charge_every_time": _explorer(ChargeEveryTime())}')
        expected_bad = ["1", "1", "charge_every_time"]
    captured = []
    actual = cli.run_models

    def capture(*args, **kwargs):
        results = actual(*args, **kwargs)  # includes the real model child JSON transport
        captured.extend(results)
        return results

    monkeypatch.setattr(cli, "run_models", capture)
    code, output = models(shop, capsys, "order_placement")
    assert code == 0, output
    result, = captured
    assert result.rules == ["one_charge_per_order"]
    assert result.known_bad == expected_bad
    assert "rules: one_charge_per_order; known-bad: " + ", ".join(expected_bad) in output
    assert json.loads(json.dumps(result.__dict__))["known_bad"] == expected_bad


def test_system_model_names_follow_one_generated_pass(shop, capsys, monkeypatch):
    from flowguard.map import system_model

    write(shop, "shop/orders.py", FIXED)
    write(shop, "shop/api.py", "from shop.orders import OrderService\ndef handle(): return OrderService()\n")
    map_path = shop / ".flowguard/map.json"
    data = json.loads(map_path.read_text())
    data["layers"] = ["interface", "engine"]
    orders = data["components"][0]
    orders.update(files=["shop/orders.py", "shop/__init__.py"], layer="engine")
    data["components"].append(dict(orders, id="api", layer="interface", responsibilities=["receive requests"],
        files=["shop/api.py"], entrypoints=["shop/api.py:handle"], depends_on=["orders"], tests=[], models=[],
        state=[], side_effects=[]))
    map_path.write_text(json.dumps(data))
    actual_variants, actual_models = system_model._variants, cli.run_models
    passes, names, captured = [], [], []

    def variants(*args, **kwargs):
        passes.append(1)
        for variant in actual_variants(*args, **kwargs):
            names.append(variant[0])
            yield variant

    def capture(*args, **kwargs):
        results = actual_models(*args, **kwargs)
        captured.extend(results)
        return results

    monkeypatch.setattr(system_model, "_variants", variants)
    monkeypatch.setattr(cli, "run_models", capture)
    code, output = models(shop, capsys, "system")
    assert code == 0, output
    result, = captured
    assert passes == [1] and names
    assert result.rules == ["dependency_cycle", "duplicate_owner", "layer_violation"]
    assert result.known_bad == sorted(names)
    assert "rules: dependency_cycle, duplicate_owner, layer_violation; known-bad: " in output
    assert all(name in output for name in names)


@pytest.mark.parametrize("rule_count,bad_count,expected_line", [
    (0, 0, None),
    (8, 8, "      rules: r0, r1, r2, r3, r4, r5, r6, r7; known-bad: b0, b1, b2, b3, b4, b5, b6, b7"),
    (9, 9, "      rules: r0, r1, r2, r3, r4, r5, r6, r7 +1 more; known-bad: b0, b1, b2, b3, b4, b5, b6, b7 +1 more"),
    (9, 0, "      rules: r0, r1, r2, r3, r4, r5, r6, r7 +1 more; known-bad: "),
    (0, 9, "      rules: ; known-bad: b0, b1, b2, b3, b4, b5, b6, b7 +1 more")])
def test_model_result_name_defaults_and_bounded_display(rule_count, bad_count, expected_line):
    from flowguard.map.proof import ModelResult, render_results

    legacy = ModelResult(**{"model": "legacy", "file": "legacy.py"})
    other = ModelResult("other", "other.py")
    assert legacy.rules == legacy.known_bad == other.rules == other.known_bad == []
    legacy.rules.append("only_this_result")
    legacy.known_bad.append("only_this_variant_list")
    assert other.rules == other.known_bad == []
    rules = [f"r{i}" for i in range(rule_count)]
    bad = [f"b{i}" for i in range(bad_count)]
    result = ModelResult("bounded", "bounded.py", rules=rules, known_bad=bad,
                         problems=["original problem"], warnings=["original warning"])
    output = render_results([result])
    assert "original problem" in output and "warning: original warning" in output
    assert "models: 1 passed, 0 failed" in output
    detail = [line for line in output.splitlines() if line.startswith("      rules:")]
    assert detail == ([] if expected_line is None else [expected_line])
    payload = json.loads(json.dumps(result.__dict__))
    assert payload["rules"] == rules and payload["known_bad"] == bad
    assert ModelResult(**payload) == result
