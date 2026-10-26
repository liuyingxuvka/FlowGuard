"""Tests grouped by their model or native component."""
from __future__ import annotations
import pytest,os,json
from pathlib import Path


def test_fixed_code_passes_and_every_run_executes(shop, capsys):
    from _fg_helpers import proof_MODEL as MODEL, proof_write as write, proof_FIXED as FIXED, proof__native_model as _native_model, proof_models as models
    write(shop, "shop/orders.py", FIXED)
    for _ in range(2):
        code, out = models(shop, capsys)
        assert code == 0 and "PASS" in out and "cached" not in out
        assert "violated by no known-bad variant" not in out
    assert not (shop / ".flowguard/cache/models.json").exists()
    native = _native_model(shop, shop / MODEL)
    assert native.status == "pass", native.problems


def test_uncovered_invariant_fails_the_model_everywhere(shop, capsys):
    """map models, release (verify) and target check judge an unbroken invariant the same way: the model fails."""
    from flowguard.map import cli
    from _fg_helpers import proof_MODEL as MODEL, proof_write as write, proof__edit_model as _edit_model, proof_FIXED as FIXED, proof__native_model as _native_model, proof_models as models
    write(shop, "shop/orders.py", FIXED)
    _edit_model(shop, "INVARIANTS = (at_most_once_by(",
                "def orders_are_unique(state, trace):\n    return len(set(state.orders)) == len(state.orders)\n\n\n"
                "INVARIANTS = (orders_are_unique, at_most_once_by(")
    code, out = models(shop, capsys)
    assert code == 1 and "FAIL" in out, out
    assert "uncovered_invariant: invariant 'orders_are_unique' is violated by no known-bad variant" in out
    assert "remove it from this model's invariants" in out and "say why it cannot be broken" not in out
    assert "'one_charge_per_order' is violated by no" not in out
    native = _native_model(shop, shop / MODEL)
    assert native.status == "fail" and native.uncovered_invariants == ["orders_are_unique"]
    assert not any("violated by no known-bad" in warning for warning in native.warnings)
    code = cli.main(["--root", str(shop), "verify"])
    out = capsys.readouterr().out
    assert code == 1 and "uncovered_invariant:" in out and "invariant(s) violated by no known-bad variant" not in out, out
    assert "say why it cannot be broken" not in out


def test_plain_function_invariant_is_accepted(shop, capsys):
    from _fg_helpers import proof_MODEL as MODEL, proof_write as write, proof__edit_model as _edit_model, proof_FIXED as FIXED, proof__native_model as _native_model, proof_models as models
    write(shop, "shop/orders.py", FIXED)
    _edit_model(shop, "INVARIANTS = (at_most_once_by(",
          "def one_charge_per_order(state, trace):\n    return len(set(state.charges)) == len(state.charges)\n\n\n"
          "INVARIANTS = (one_charge_per_order,)\n_UNUSED = (at_most_once_by(")
    code, out = models(shop, capsys)
    assert code == 0, out

    native = _native_model(shop, shop / MODEL)
    assert native.status == "pass", native.problems
    path = shop / MODEL
    path.write_text(path.read_text(encoding="utf-8") + "\ndef unused_helper():\n    return 17\n", encoding="utf-8")
    neutral = _native_model(shop, path)
    assert (neutral.status, neutral.problems, neutral.warnings) == (native.status, native.problems, native.warnings)


def test_tested_by_must_name_a_design_invariant(shop, capsys):
    from _fg_helpers import proof_MODEL as MODEL, proof_write as write, proof_FIXED as FIXED, proof__native_model as _native_model, proof_models as models
    write(shop, "shop/orders.py", FIXED)
    path = shop / MODEL
    source = path.read_text(encoding="utf-8")
    caught = 'return {"charge_every_time": _explorer(ChargeEveryTime())}'
    assert caught in source
    source = source.replace(caught, 'return {"charge_every_time": _explorer(PlaceOrder())}', 1)
    write(shop, MODEL, source + '\nTESTED_BY = {"no_such_invariant": ["tests/test_orders.py:test_place_once"]}\n')
    code, out = models(shop, capsys)
    assert code == 1 and "no_such_invariant" in out
    native = _native_model(shop, shop / MODEL)
    assert native.status == "fail" and "no_such_invariant" in " ".join(native.problems)

    assert native.problems[0].startswith("TESTED_BY names 'no_such_invariant'")
    assert any("known-bad variant 'charge_every_time' passed" in problem for problem in native.problems)
