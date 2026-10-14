"""Tests for the proof layer (flowguard.map.proof) and its links to the map.

The fixture is a tiny shop whose OrderService charges the card again when a
client retries the same order id.  Its unit test is green; the model's
conformance replay must catch the bug.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from flowguard.map import cli

MODEL_SOURCE = Path(__file__).resolve().parent / "fixtures" / "flowguard_map" / "order_placement.py"

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


def test_fixed_code_passes_and_second_run_is_cached(shop, capsys):
    write(shop, "shop/orders.py", FIXED)
    code, out = models(shop, capsys)
    assert code == 0 and "PASS" in out and "(cached)" not in out
    code, out = models(shop, capsys)
    assert code == 0 and "(cached)" in out
    write(shop, "shop/orders.py", FIXED + "\n# touched\n")          # implementation bytes changed -> rerun
    code, out = models(shop, capsys)
    assert code == 0 and "(cached)" not in out


def test_invariants_without_teeth_are_rejected(shop, capsys):
    write(shop, "shop/orders.py", FIXED)
    path = shop / ".flowguard/models/order_placement.py"
    text = path.read_text(encoding="utf-8")
    start = text.index("INVARIANTS = (")
    end = text.index("\n", start)
    path.write_text(text[:start] + "INVARIANTS = ()" + text[end:], encoding="utf-8")
    code, out = models(shop, capsys, "--force")
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
    assert "(cached)" in models(shop, capsys)[1]
    write(shop, "shop/helper.py", "def healthy():\n    return False\n")
    code, output = models(shop, capsys)
    assert code == 1 and "FAIL" in output and "(cached)" not in output
    assert (shop / "shop/orders.py").read_text() == implementation
    assert models(shop, capsys, "--force")[0] == 1
    write(shop, "shop/helper.py", "def healthy():\n    return True\n")
    assert models(shop, capsys)[0] == 0


@pytest.mark.parametrize("unknown_input", ["unbound_helper", "config_reader", "no_components", "no_map"])
def test_unknown_input_boundary_executes_instead_of_reusing_pass(shop, capsys, unknown_input):
    write(shop, "shop/orders.py", FIXED)
    if unknown_input == "unbound_helper":
        write(shop, "shared/__init__.py", "")
        write(shop, "shared/helper.py", "def healthy():\n    return True\n")
        write(shop, "shop/orders.py", "from shared.helper import healthy\n" + FIXED)
    elif unknown_input == "config_reader":
        write(shop, "shop/orders.py", FIXED + "\ndef config():\n    return open('settings.json').read()\n")
    elif unknown_input == "no_components":
        path = shop / ".flowguard/models/order_placement.py"
        path.write_text(path.read_text().replace('COMPONENTS = ["orders"]', 'COMPONENTS = []'))
    else:
        (shop / ".flowguard/map.json").unlink()
    for _ in range(2):
        code, output = models(shop, capsys)
        assert code == 0 and "cache not reused:" in output and "(cached)" not in output


def test_model_cache_key_separates_engine_and_python_identity(shop):
    from flowguard.map.mapfile import read_model_contract
    from flowguard.map.proof import _input_key
    path = shop / ".flowguard/models/order_placement.py"
    contract = read_model_contract(path)
    first = _input_key(shop, path, contract, engine_digest="python-A:engine-A")
    assert first == _input_key(shop, path, contract, engine_digest="python-A:engine-A")
    assert first != _input_key(shop, path, contract, engine_digest="python-A:engine-B")
    assert first != _input_key(shop, path, contract, engine_digest="python-B:engine-A")


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


_MINIMAL_MODEL = '''from types import SimpleNamespace
MODEL_ID = "minimal"
def build_explorer():
    return SimpleNamespace(explore=lambda: SimpleNamespace(ok=True))
'''


@pytest.mark.parametrize("hook", ["def conformance():\n    return None\n",
                                  "def conformance():\n    return True\n",
                                  "def broken_variants():\n    return {}\n"])
def test_defined_proof_hooks_cannot_silently_do_nothing(tmp_path, hook):
    from flowguard.map.proof import run_model
    write(tmp_path, ".flowguard/models/minimal.py", _MINIMAL_MODEL + hook)
    result = run_model(tmp_path, tmp_path / ".flowguard/models/minimal.py")
    assert result.status == "error" and "no " in " ".join(result.problems)


def test_abstract_model_exposes_unverified_implementation(tmp_path):
    from flowguard.map.proof import run_models
    write(tmp_path, ".flowguard/models/minimal.py", _MINIMAL_MODEL)
    result, = run_models(tmp_path, [])
    assert result.status == "pass" and not result.cached
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


def test_corrupt_or_nonpass_cache_entry_is_reexecuted(shop, capsys):
    write(shop, "shop/orders.py", FIXED)
    assert models(shop, capsys)[0] == 0
    path = shop / ".flowguard/cache/models.json"
    cached = json.loads(path.read_text())
    cached["models"]["order_placement.py"]["result"]["status"] = "fail"
    path.write_text(json.dumps(cached))
    code, output = models(shop, capsys)
    assert code == 0 and "(cached)" not in output
    cached["models"] = []
    path.write_text(json.dumps(cached))
    assert models(shop, capsys)[0] == 0


def test_runner_output_in_any_language_never_breaks_the_verdict(tmp_path, monkeypatch):
    from flowguard.map.proof import run_runner
    monkeypatch.setenv("PYTHONIOENCODING", "cp1252")          # the code page a Windows pipe gives a child
    runner = tmp_path / ".flowguard/verification/owners/shop/run_checks.py"
    runner.parent.mkdir(parents=True)
    runner.write_text("print('运行检查 ✓')\n", encoding="utf-8")
    assert run_runner(tmp_path, runner).status == "pass"
    runner.write_text("print('失败 ✗')\nraise SystemExit(1)\n", encoding="utf-8")
    result = run_runner(tmp_path, runner)
    assert result.status == "fail" and "失败 ✗" in result.problems[0], result.problems
