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


def test_child_path_never_exposes_repo_root(shop, tmp_path, monkeypatch):
    import subprocess
    import sys
    from flowguard.map.cli import _context
    from flowguard.map.proof import run_models

    repository = Path(__file__).resolve().parents[1]
    namespaces = sorted(
        path.name for path in repository.iterdir()
        if path.is_dir() and path.name.isidentifier() and path.name != "flowguard"
    )
    assert "examples" in namespaces and "scripts" in namespaces
    for name in namespaces:
        write(shop, name + "/fg_child_probe.py", "VALUE = 'project'\n")
    extra = shop / "project_imports"
    write(extra, "configured_probe.py", "VALUE = 'configured'\n")
    inherited = tmp_path / "inherited_imports"
    inherited.mkdir()
    monkeypatch.setenv("PYTHONPATH", os.pathsep.join((str(inherited), str(repository))))
    write(shop, "shop/orders.py", FIXED)
    model = shop / MODEL
    imports = (
        "from importlib import import_module\n"
        + "NAMESPACE_VALUES = [import_module(name + '.fg_child_probe').VALUE for name in "
        + repr(namespaces) + "]\n"
        + "from configured_probe import VALUE as CONFIGURED\n"
    )
    source = model.read_text().replace(
        "from __future__ import annotations\n",
        "from __future__ import annotations\n" + imports,
        1,
    ).replace(
        "def conformance():",
        "def conformance():\n    assert CONFIGURED == 'configured'\n"
        "    assert all(value == 'project' for value in NAMESPACE_VALUES)",
        1,
    )
    model.write_text(source + '\nTESTED_BY = {"one_charge_per_order": ["tests/test_orders.py:test_place_once"]}\n')
    test = shop / "tests/test_orders.py"
    test.write_text(imports + "assert CONFIGURED == 'configured'\n"
                    "assert all(value == 'project' for value in NAMESPACE_VALUES)\n" + test.read_text())
    map_path = shop / ".flowguard/map.json"
    data = json.loads(map_path.read_text())
    data["import_roots"] = ["project_imports"]
    map_path.write_text(json.dumps(data))
    data, inv = _context(shop)
    results = run_models(shop, [model.stem], inv=inv, tests=True, jobs=1)
    assert results and all(
        result.status == "pass" and result.test_seconds is not None for result in results
    ), [(result.model, result.problems) for result in results]
    from flowguard.map.common import child_import_path

    paths = child_import_path(shop, data)
    assert paths[:2] == [str(shop.resolve()), str(extra.resolve())]
    assert str(repository) not in paths
    assert str(inherited) in paths
    assert set(path.name for path in Path(paths[-1]).iterdir()) == {"flowguard"}
    assert child_import_path(shop, data) == paths
    # A fresh command exercises the cold concurrent path and the Windows-style
    # copy fallback, then leaves no temporary engine package behind.
    probe = '''from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
import json, sys
from flowguard.map import common
created = []
original = common.tempfile.TemporaryDirectory
def temporary(*args, **kwargs):
    value = original(*args, **kwargs)
    created.append(value.name)
    return value
source = (Path(common.__file__).resolve().parents[2] / 'pyproject.toml').is_file()
with patch.object(common.tempfile, 'TemporaryDirectory', temporary):
    with patch.object(Path, 'symlink_to', side_effect=OSError('links unavailable')):
        with ThreadPoolExecutor(max_workers=4) as pool:
            roots = list(pool.map(lambda _: common.child_import_path(Path(sys.argv[1]), {})[-1], range(8)))
assert len(set(roots)) == 1
assert len(created) == int(source), created
if source:
    assert {path.name for path in Path(roots[0]).iterdir()} == {'flowguard'}
    assert not (Path(roots[0]) / 'flowguard').is_symlink()
print(json.dumps(created))
'''
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    command = subprocess.run([sys.executable, "-c", probe, str(shop)],
                             capture_output=True, text=True, env=environment)
    assert command.returncode == 0, command.stdout + command.stderr
    assert all(not Path(folder).exists() for folder in json.loads(command.stdout))


def test_src_layout_project_imports_its_own_package(shop, capsys):
    import shutil
    from flowguard.map.cli import _context, main
    from flowguard.map.mapfile import model_digests
    from flowguard.map.proof import run_models

    write(shop, "shop/orders.py", FIXED)
    (shop / "src").mkdir()
    shutil.move(shop / "shop", shop / "src/shop")
    model = shop / MODEL
    model.write_text(model.read_text().replace("shop/orders.py:", "src/shop/orders.py:")
                     + '\nTESTED_BY = {"one_charge_per_order": ["tests/test_orders.py:test_place_once"]}\n')
    path = shop / ".flowguard/map.json"
    data = json.loads(path.read_text())
    data["components"][0]["files"] = ["src/shop/*.py"]
    data["components"][0]["entrypoints"] = ["src/shop/orders.py:OrderService.place"]
    # This is the fixture's initial src-layout map, before any change target.
    data["model_digests"] = model_digests(shop)
    path.write_text(json.dumps(data))
    data, inv = _context(shop)
    results = run_models(shop, [model.stem], inv=inv, tests=True, jobs=1)
    assert results and all(
        result.status == "pass" and result.test_seconds is not None for result in results
    ), [(result.model, result.problems) for result in results]
    assert main(["--root", str(shop), "confirm", "orders"]) == 0
    assert main(["--root", str(shop), "verify"]) == 0, capsys.readouterr().out
