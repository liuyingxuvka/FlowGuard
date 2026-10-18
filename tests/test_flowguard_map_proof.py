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


def test_unit_test_is_green_but_model_conformance_catches_double_charge(shop, capsys):
    code, out = models(shop, capsys)
    assert code == 1
    assert "FAIL" in out and "does not conform" in out and "one_charge_per_order" in out


def test_fixed_code_passes_and_every_run_executes(shop, capsys):
    write(shop, "shop/orders.py", FIXED)
    for _ in range(2):
        code, out = models(shop, capsys)
        assert code == 0 and "PASS" in out and "cached" not in out
    assert not (shop / ".flowguard/cache/models.json").exists()


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
    extra = dict(data["components"][0], id="billing", files=["billing/*.py"], entrypoints=[], tests=[], models=[])
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


def test_abstract_model_exposes_unverified_implementation(tmp_path):
    from flowguard.map.proof import run_model
    write(tmp_path, ".flowguard/models/minimal.py", _MINIMAL_MODEL)
    result = run_model(tmp_path, tmp_path / ".flowguard/models/minimal.py")
    assert result.status == "pass"
    assert any("abstract boundary only" in warning for warning in result.warnings)


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
    runner.write_text("from flowguard.map.runner import run_owner\n"
                      "from flowguard.explorer import Explorer\nfrom flowguard.workflow import Workflow\n"
                      "def main():\n    print('运行检查 ✓')\n"
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


def test_abstract_model_with_empty_implemented_by_still_passes_with_warning(shop, capsys):
    write(shop, "shop/orders.py", FIXED)
    _edit_model(shop, 'IMPLEMENTED_BY = {"PlaceOrder": "shop/orders.py:OrderService.place"}', "IMPLEMENTED_BY = {}")
    _edit_model(shop, "def conformance():\n", "def _old_conformance():\n")
    code, out = models(shop, capsys)
    assert code == 0 and "abstract boundary only" in out


def test_non_python_anchor_is_a_warning_not_a_failure(shop, capsys):
    write(shop, "shop/orders.py", FIXED)
    write(shop, "web/cart.ts", "export function addItem(c, i) { return [...c, i]; }\n")
    _edit_model(shop, 'IMPLEMENTED_BY = {"PlaceOrder": "shop/orders.py:OrderService.place"}',
          'IMPLEMENTED_BY = {"PlaceOrder": "shop/orders.py:OrderService.place", "Ui": "web/cart.ts:addItem"}')
    code, out = models(shop, capsys)
    assert code == 0 and "is not Python" in out


_CRASH = ("return {\"charge_every_time\": _explorer(ChargeEveryTime())}",
          "return {\"charge_every_time\": _explorer(Crashes())}")


@pytest.mark.parametrize("case", ["crash", "invariant_crash", "other_invariant", "same_name_wrong_predicate", "budget", "design_without_invariants"])
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
    elif case == "budget":
        _edit_model(shop, "return {\"charge_every_time\": _explorer(ChargeEveryTime())}",
              "return {'charge_every_time': Explorer(workflow=Workflow((PlaceOrder(),)), initial_states=(State(),), "
              "external_inputs=INPUTS, invariants=INVARIANTS, max_sequence_length=3, progress_steps=0, max_transitions=1)}")
        expected = "fails without violating"
    else:
        _edit_model(shop, "def build_explorer() -> Explorer:\n    return _explorer(PlaceOrder())",
              "def build_explorer() -> Explorer:\n    return Explorer(workflow=Workflow((PlaceOrder(),)), "
              "initial_states=(State(),), external_inputs=INPUTS, invariants=(), max_sequence_length=3, progress_steps=0)")
        expected = "declares no invariants"
    code, out = models(shop, capsys)
    assert code == 1 and expected in out


def test_plain_function_invariant_is_accepted(shop, capsys):
    write(shop, "shop/orders.py", FIXED)
    _edit_model(shop, "INVARIANTS = (at_most_once_by(",
          "def one_charge_per_order(state, trace):\n    return len(set(state.charges)) == len(state.charges)\n\n\n"
          "INVARIANTS = (one_charge_per_order,)\n_UNUSED = (at_most_once_by(")
    code, out = models(shop, capsys)
    assert code == 0, out


@pytest.mark.parametrize("source", ["raise SystemExit(0)\n", "from flowguard.map.runner import run_owner\nraise SystemExit(run_owner(lambda: 0))\n", "from flowguard.map.runner import run_owner\nraise SystemExit(run_owner(lambda: []))\n"])
def test_runner_that_runs_nothing_cannot_pass(tmp_path, source):
    from flowguard.map.proof import run_runner
    path = tmp_path / ".flowguard/verification/owners/shop/run_checks.py"
    write(tmp_path, path.relative_to(tmp_path).as_posix(), source)
    result = run_runner(tmp_path, path)
    assert result.status == "error"
    assert "run_owner" in " ".join(result.problems)


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


def test_runner_completion_is_distinct_from_component_import_coverage(tmp_path):
    from flowguard.map.proof import run_runner
    write(tmp_path, "app.py", "VALUE=1\n")
    source = ("from flowguard.map.runner import run_owner\nfrom flowguard.explorer import Explorer\n"
              "from flowguard.workflow import Workflow\n"
              "def main():\n    return Explorer(Workflow(()), (0,), (1,), progress_steps=0).explore()\n"
              "raise SystemExit(run_owner(main))\n")
    path = tmp_path / ".flowguard/verification/owners/shop/run_checks.py"
    write(tmp_path, path.relative_to(tmp_path).as_posix(), source)
    result = run_runner(tmp_path, path, own_files={"app.py"})
    assert result.status == "pass" and any("abstract boundary only" in w for w in result.warnings)
    write(tmp_path, path.relative_to(tmp_path).as_posix(), "import app\n" + source)
    result = run_runner(tmp_path, path, own_files={"app.py"})
    assert result.status == "pass" and not result.warnings


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
