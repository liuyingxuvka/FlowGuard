"""Tests grouped by their model or native component."""
from __future__ import annotations
import pytest,os,json
from pathlib import Path


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
    from _fg_helpers import proof_write as write, proof_FIXED as FIXED, proof_models as models, proof_MODEL_SOURCE as MODEL_SOURCE
    write(shop, "shop/orders.py", FIXED)
    write(shop, "shop/other.py", "def marker():\n    return 1\n")
    model_path = shop / ".flowguard/models/order_placement.py"
    source = MODEL_SOURCE.replace(
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


def test_rule_without_a_test_is_named(shop, capsys):
    from _fg_helpers import proof_MODEL as MODEL, proof_write as write, proof_FIXED as FIXED, proof__native_model as _native_model, proof_models as models
    write(shop, "shop/orders.py", FIXED)
    path = shop / MODEL
    source = path.read_text(encoding="utf-8")
    source += ('\nINVARIANTS = INVARIANTS + (at_most_once_by("retry_has_one_charge", '
               '"a retry has one charge", lambda state: state.charges, lambda charge: charge, "charge"),)\n')
    binding = "tests/test_orders.py:test_place_once"
    first = {"one_charge_per_order": [binding]}
    write(shop, MODEL, source + "\nTESTED_BY = " + repr(first) + "\n")
    code, output = models(shop, capsys, "order_placement")
    expected = ("invariant_untested: retry_has_one_charge have no TESTED_BY test; "
                "bind a test that fails when the rule is broken")
    assert code == 0 and "PASS  order_placement" in output, output
    assert expected in output
    assert "invariant_untested: one_charge_per_order" not in output
    native = _native_model(shop, path)
    from flowguard.map.proof import run_bound_tests
    run_bound_tests(shop, path, native)
    assert native.status == "pass", native.problems
    assert native.test_seconds is not None
    assert [warning for warning in native.warnings if warning.startswith("invariant_untested:")] == [expected]
    complete = {**first, "retry_has_one_charge": [binding]}
    write(shop, MODEL, source + "\nTESTED_BY = " + repr(complete) + "\n")
    code, output = models(shop, capsys, "order_placement")
    assert code == 0 and "PASS  order_placement" in output, output
    assert "invariant_untested:" not in output
    native = _native_model(shop, path)
    assert native.status == "pass", native.problems
    assert not any(warning.startswith("invariant_untested:") for warning in native.warnings)
