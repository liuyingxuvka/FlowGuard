"""Tests grouped by their model or native component."""
from __future__ import annotations
import pytest,os,json
from pathlib import Path



from _fg_helpers import (
    proof_FIXED as FIXED,
    proof_MODEL as MODEL,
    proof__edit_model as _edit_model,
    proof__native_model as _native_model,
    proof_models as models,
    proof_FIXED,
    proof_MODEL,
    proof__native_model,
    proof_write,
    proof_write as write,
)

def test_fixed_code_passes_and_every_run_executes(shop, capsys):
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

    write(shop, "shop/orders.py", FIXED)
    _edit_model(
        shop,
        "INVARIANTS = (at_most_once_by(",
        "def orders_are_unique(state, trace):\n    return len(set(state.orders)) == len(state.orders)\n\n\n"
        "INVARIANTS = (orders_are_unique, at_most_once_by(",
    )
    code, out = models(shop, capsys)
    assert code == 1 and "FAIL" in out, out
    assert (
        "uncovered_invariant: invariant 'orders_are_unique' is violated by no known-bad variant"
        in out
    )
    assert (
        "remove it from this model's invariants" in out and "say why it cannot be broken" not in out
    )
    assert "'one_charge_per_order' is violated by no" not in out
    native = _native_model(shop, shop / MODEL)
    assert native.status == "fail" and native.uncovered_invariants == ["orders_are_unique"]
    assert not any("violated by no known-bad" in warning for warning in native.warnings)
    code = cli.main(["--root", str(shop), "verify"])
    out = capsys.readouterr().out
    assert (
        code == 1
        and "uncovered_invariant:" in out
        and "invariant(s) violated by no known-bad variant" not in out
    ), out
    assert "say why it cannot be broken" not in out


def test_plain_function_invariant_is_accepted(shop, capsys):
    write(shop, "shop/orders.py", FIXED)
    _edit_model(
        shop,
        "INVARIANTS = (at_most_once_by(",
        "def one_charge_per_order(state, trace):\n    return len(set(state.charges)) == len(state.charges)\n\n\n"
        "INVARIANTS = (one_charge_per_order,)\n_UNUSED = (at_most_once_by(",
    )
    code, out = models(shop, capsys)
    assert code == 0, out

    native = _native_model(shop, shop / MODEL)
    assert native.status == "pass", native.problems
    path = shop / MODEL
    path.write_text(
        path.read_text(encoding="utf-8") + "\ndef unused_helper():\n    return 17\n",
        encoding="utf-8",
    )
    neutral = _native_model(shop, path)
    assert (neutral.status, neutral.problems, neutral.warnings) == (
        native.status,
        native.problems,
        native.warnings,
    )


def test_tested_by_must_name_a_design_invariant(shop, capsys):
    write(shop, "shop/orders.py", FIXED)
    path = shop / MODEL
    source = path.read_text(encoding="utf-8")
    caught = 'return {"charge_every_time": _explorer(ChargeEveryTime())}'
    assert caught in source
    source = source.replace(caught, 'return {"charge_every_time": _explorer(PlaceOrder())}', 1)
    write(
        shop,
        MODEL,
        source + '\nTESTED_BY = {"no_such_invariant": ["tests/test_orders.py:test_place_once"]}\n',
    )
    code, out = models(shop, capsys)
    assert code == 1 and "no_such_invariant" in out
    native = _native_model(shop, shop / MODEL)
    assert native.status == "fail" and "no_such_invariant" in " ".join(native.problems)

    assert native.problems[0].startswith("TESTED_BY names 'no_such_invariant'")
    assert any(
        "known-bad variant 'charge_every_time' passed" in problem for problem in native.problems
    )


def test_model_subprocess_uses_ports_from_the_request(shop, monkeypatch):
    from flowguard.map import inventory, proof
    from flowguard.map.mapfile import load_map
    from flowguard.map.tree import build_tree

    proof_write(shop, "shop/orders.py", proof_FIXED)
    data = load_map(shop)
    inv = inventory.build_inventory(shop, [], write_cache=False)
    tree = build_tree(shop, data, inv)
    request = proof._port_request(tree, Path(proof_MODEL).stem)

    def forbidden(*args, **kwargs):
        raise AssertionError("the subprocess rebuilt the inventory or model tree")

    monkeypatch.setattr(inventory, "build_inventory", forbidden)
    monkeypatch.setattr(proof, "build_tree", forbidden)
    native = proof.run_model_in_process
    monkeypatch.setattr(
        proof, "run_model_in_process", lambda root, path: native(root, path, port_request=request)
    )
    result = proof__native_model(shop, shop / proof_MODEL)
    assert result.status == "pass", result.problems


def test_port_payload_keeps_static_literal_types():
    from flowguard.map.port import Port, port_to_payload, port_from_payload

    port = Port(
        state=("state",),
        outputs={"value": ("a", b"bytes", 2 + 3j, None)},
        handoff={"producer": {"answer": ("seen", {("a", 1): frozenset({2, 3})})}},
        blocks={"Block": {"writes": {"one", "two"}, "values": [Ellipsis, True, 1.5]}},
    )
    restored = port_from_payload(json.loads(json.dumps(port_to_payload(port))))
    assert restored == port
    assert type(restored.state) is tuple
    assert type(restored.outputs["value"][1]) is bytes
    assert type(restored.handoff["producer"]["answer"][1][("a", 1)]) is frozenset


@pytest.mark.parametrize("regular_package", [True, False])
def test_project_scripts_package_wins_over_flowguard_parent(
    shop, tmp_path, monkeypatch, regular_package
):
    from flowguard.map.cli import _context
    from flowguard.map.proof import run_models

    package = tmp_path / "project_pythonpath"
    (package / "scripts").mkdir(parents=True)
    if regular_package:
        (package / "scripts/__init__.py").write_text("")
    (package / "scripts/x.py").write_text('VALUE = "project"\n')
    monkeypatch.setenv("PYTHONPATH", str(package))
    proof_write(shop, "shop/orders.py", proof_FIXED)
    model = shop / proof_MODEL
    model_source = model.read_text()
    future = "from __future__ import annotations\n"
    assert future in model_source
    model_source = model_source.replace(future, future + "from scripts.x import VALUE\n", 1)
    model_source = model_source.replace(
        "def conformance():", 'def conformance():\n    assert VALUE == "project"'
    )
    model_source += (
        '\nTESTED_BY = {"one_charge_per_order": ["tests/test_orders.py:test_place_once"]}\n'
    )
    model.write_text(model_source)
    test = shop / "tests/test_orders.py"
    test.write_text('from scripts.x import VALUE\nassert VALUE == "project"\n' + test.read_text())
    data, inv = _context(shop)
    results = run_models(shop, [model.stem], inv=inv, tests=True, jobs=1)
    assert results and all(
        result.status == "pass" and result.test_seconds is not None for result in results
    ), [(result.model, result.problems) for result in results]
