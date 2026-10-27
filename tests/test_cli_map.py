"""Tests grouped by their model or native component."""
from __future__ import annotations
import pytest,os,json
from pathlib import Path



from _fg_helpers import (
    flowguard_map_contracts421_CONTRACT as CONTRACT,
    proof_FIXED as FIXED,
    proof_MODEL as MODEL,
    proof_MODEL_SOURCE as MODEL_SOURCE,
    proof__CRASH as _CRASH,
    proof__check_codes as _check_codes,
    proof__edit_model as _edit_model,
    proof__native_model as _native_model,
    map_codes as codes,
    map_fill as fill,
    flowguard_map_contracts421_save,
    flowguard_map_contracts421_write,
    map_git as git,
    map_load as load,
    map_save,
    map_write,
    proof_models as models,
    flowguard_map_contracts421_project as project,
    proof_write,
    map_run as run,
    target_shelf_project as shelf_project,
)

def test_scan_creates_draft_map_with_real_deps(project, capsys):
    code, out = run(project, "scan", capsys=capsys)
    assert code == 0 and "draft components" in out
    data = load(project)
    ids = {c["id"] for c in data["components"]}
    assert {"shop", "web"} <= ids
    assert all(c["status"] == "draft" for c in data["components"])
    assert (project / ".flowguard/cache/inventory.json").is_file()


def test_lint_finds_layer_violation_cycle_and_duplicate_owner(project, capsys):
    run(project, "scan", capsys=capsys)
    data = fill(project)
    map_write(
        project,
        "shop/storage.py",
        "from shop.orders import place_order\nDB = {}\n\ndef save(x):\n    return x\n",
    )
    data["components"][2]["responsibilities"].append("place an order once")
    map_save(project, data)
    found = codes(project, "lint", capsys)
    assert "layer_violation" in found  # infra -> domain
    assert "dependency_cycle" in found  # orders <-> storage
    assert "duplicate_owner" in found  # same responsibility in two components


def test_impact_selects_only_affected_tests(project, capsys):
    run(project, "scan", capsys=capsys)
    fill(project)
    run(project, "confirm", "api", "orders", "storage", "web", capsys=capsys)
    git(project, "add", "-A")
    git(project, "-c", "user.email=a@b", "-c", "user.name=t", "commit", "-qm", "map")
    map_write(project, "shop/storage.py", "DB = {}\n\ndef save(x):\n    return x\n")
    code, out = run(project, "impact", capsys=capsys)
    assert code == 0
    assert "directly affected: storage" in out
    assert "dependents: api, orders" in out
    assert "tests/test_storage.py" in out and "tests/test_orders.py" in out
    assert "REVIEW storage" in out


def test_find_returns_existing_owner(project, capsys):
    run(project, "scan", capsys=capsys)
    fill(project)
    code, out = run(project, "find", "save", "database", capsys=capsys)
    assert code == 0 and out.splitlines()[0].split()[1] == "storage"
    code, out = run(project, "find", "refund", "invoice", capsys=capsys)
    assert code == 1


def test_show_is_complete_and_digest_has_no_bodies(project, capsys):
    run(project, "scan", capsys=capsys)
    fill(project)
    code, out = run(project, "show", capsys=capsys)
    assert code == 0 and "truncated" not in out
    assert all("## " + cid + " [" in out for cid in ("api", "orders", "storage"))
    code, out = run(project, "digest", "orders", capsys=capsys)
    assert "class OrderService" in out and "storage.save" not in out


def test_cache_is_invalidated_when_a_file_changes(project, capsys):
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory

    run(project, "scan", capsys=capsys)
    inv1 = build_inventory(project, DEFAULT_IGNORE)
    assert "save" in inv1.py["shop/storage.py"].symbols
    map_write(project, "shop/storage.py", "def persist(x):\n    return x\n\n\n")
    inv2 = build_inventory(project, DEFAULT_IGNORE)
    assert (
        "persist" in inv2.py["shop/storage.py"].symbols
        and "save" not in inv2.py["shop/storage.py"].symbols
    )


def test_impact_cli_uses_full_closure(impact_project, capsys):
    root, data = impact_project
    code, out = run(root, "impact", "shop/storage.py", capsys=capsys)
    assert code == 0 and "dependents: api, orders" in out


def test_deps_write_keeps_unverified_declared_dependencies(impact_project, capsys):
    root, data = impact_project
    map_write(
        root,
        "shop/api.py",
        "import importlib\ndef handle(req):\n    return importlib.import_module('shop.orders').place_order(req)\n",
    )
    run(root, "deps", "--write", capsys=capsys)
    assert load(root)["components"][0]["depends_on"] == ["orders"]


def test_impact_decodes_previous_map_and_changed_names_as_utf8(project, capsys, monkeypatch):
    import json
    import subprocess

    real_run = subprocess.run

    def ansi_run(*args, **kwargs):  # Windows: text=True decodes git output with the ANSI code page
        if kwargs.pop("text", False):
            kwargs["encoding"] = "cp1252"
        return real_run(*args, **kwargs)

    run(project, "scan", capsys=capsys)
    data = fill(project)
    data["components"][0]["summary"] = "运行检查"  # UTF-8 has byte 0x90, undefined in cp1252
    data["components"][0]["files"].append("shop/工具.py")
    (project / ".flowguard/map.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    map_write(project, "shop/工具.py", "VALUE = 1\n")
    git(project, "add", "-A")
    git(project, "-c", "user.email=a@b", "-c", "user.name=t", "commit", "-qm", "chinese map")
    map_write(project, "shop/工具.py", "VALUE = 2\n")
    monkeypatch.setattr(subprocess, "run", ansi_run)
    code, out = run(project, "impact", "--base", "HEAD", capsys=capsys)
    assert code == 0, out
    assert "directly affected: api" in out


def test_bom_and_coding_cookie_sources_parse_like_python(project, capsys):
    run(project, "scan", capsys=capsys)
    data = fill(project)
    data["components"][2]["files"].append("shop/legacy.py")
    map_save(project, data)
    storage = project / "shop/storage.py"
    storage.write_bytes(
        b"\xef\xbb\xbf" + storage.read_bytes()
    )  # PowerShell 5.1 / Visual Studio BOM
    (project / "shop/legacy.py").write_bytes('# -*- coding: gbk -*-\nNAME = "订单"\n'.encode("gbk"))
    mapping = project / ".flowguard/map.json"
    mapping.write_bytes(b"\xef\xbb\xbf" + mapping.read_bytes())  # map edited by a Windows tool
    code, out = run(project, "check", capsys=capsys)
    assert code == 0 and "source_parse_error" not in out and "anchor_broken" not in out, out
    code, out = run(project, "impact", "shop/legacy.py", "shop/storage.py", capsys=capsys)
    assert code == 0 and "directly affected: storage" in out, out


def test_impact_accepts_absolute_and_backslash_paths(project, capsys):
    run(project, "scan", capsys=capsys)
    fill(project)
    code, out = run(
        project, "impact", str(project / "shop" / "api.py"), "shop\\orders.py", capsys=capsys
    )
    assert code == 0 and "UNMAPPED" not in out and "directly affected: api, orders" in out, out


def test_impact_cli_exits_nonzero_for_unmapped_source(impact_project, capsys):
    root, data = impact_project
    map_write(root, "shop/unowned.py", "VALUE = 1\n")
    code, text = run(root, "impact", "shop/unowned.py", capsys=capsys)
    assert code == 1 and "UNMAPPED" in text


def test_save_map_sorts_only_depends_on(project, capsys):
    from flowguard.map.mapfile import save_map

    run(project, "scan", capsys=capsys)
    data = fill(project)
    comp = data["components"][0]
    comp["depends_on"] = ["storage", "orders", "storage"]
    comp["files"] = ["shop/__init__.py", "shop/api.py"]
    comp["tests"] = ["tests/test_storage.py", "tests/test_orders.py"]
    save_map(project, data)
    saved = load(project)["components"][0]
    assert saved["depends_on"] == ["orders", "storage"]
    assert saved["files"] == ["shop/__init__.py", "shop/api.py"]
    assert saved["tests"] == ["tests/test_storage.py", "tests/test_orders.py"]


def test_scan_preserves_project_gitignore(project, capsys):
    ignore = project / ".gitignore"
    original = b"build/\r\n# project-owned rules\r\n"
    ignore.write_bytes(original)
    assert run(project, "scan", capsys=capsys)[0] == 0
    assert ignore.read_bytes() == original
    assert (project / ".flowguard/cache/.gitignore").read_text() == "*\n"


def test_flow_without_model_across_modeled_code_is_reported(tmp_path):
    """flow_unmodeled: a flow crossing a modeled component has no model of its own."""
    from flowguard.map.cli import _context
    from flowguard.map.lint import run_lint

    root = shelf_project(tmp_path)
    data, inv = _context(root)
    found = [f for f in run_lint(root, data, inv) if f.code == "flow_unmodeled"]
    assert (
        found
        and "borrow" in found[0].message
        and "desk" in found[0].message
        and found[0].level == "info"
    )
    data["flows"][0]["model"] = ".flowguard/models/desk.py"
    assert not [f for f in run_lint(root, data, inv) if f.code == "flow_unmodeled"]


def test_scan_hints_a_split_and_discover_says_when_nothing_is_found(tmp_path, capsys):
    import subprocess

    root = tmp_path / "lib"
    for index in range(6):
        map_write(root, f"pkg/part{index}.py", f"def value{index}():\n    return {index}\n")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    code, out = run(root, "scan", capsys=capsys)
    assert (
        code == 0
        and "hint: draft pkg holds 6 files of one directory; split it by responsibility "
        "(python -m flowguard map digest pkg lists each file's API)" in out
    ), out
    code, out = run(root, "discover", capsys=capsys)
    assert (
        code == 0
        and "no entrypoints, effects or state writers found (a library without commands is normal; "
        "list its public API in entrypoints by hand)" in out
    ), out


def test_unit_test_is_green_but_model_conformance_catches_double_charge(shop, capsys):
    code, out = models(shop, capsys)
    assert code == 1
    assert "FAIL" in out and "does not conform" in out and "one_charge_per_order" in out


def test_invariants_without_teeth_are_rejected(shop, capsys):
    proof_write(shop, "shop/orders.py", FIXED)
    path = shop / ".flowguard/models/order_placement.py"
    text = path.read_text(encoding="utf-8")
    start = text.index("INVARIANTS = (")
    end = text.index("\n", start)
    path.write_text(text[:start] + "INVARIANTS = ()" + text[end:], encoding="utf-8")
    code, out = models(shop, capsys)
    assert code == 1 and "known-bad variant 'charge_every_time' passed" in out


def test_mapped_helper_mutation_invalidates_pass_without_direct_anchor_edit(shop, capsys):
    implementation = "from shop.helper import healthy\n" + FIXED.replace(
        "    def place(self, order_id, amount):\n",
        "    def place(self, order_id, amount):\n        if not healthy():\n            return 'broken'\n",
    )
    proof_write(shop, "shop/orders.py", implementation)
    proof_write(shop, "shop/helper.py", "def healthy():\n    return True\n")
    assert models(shop, capsys)[0] == 0
    proof_write(shop, "shop/helper.py", "def healthy():\n    return False\n")
    code, output = models(shop, capsys)
    assert code == 1 and "FAIL" in output
    assert (shop / "shop/orders.py").read_text() == implementation
    proof_write(shop, "shop/helper.py", "def healthy():\n    return True\n")
    assert models(shop, capsys)[0] == 0


@pytest.mark.parametrize("selection", [("missing",), ("order_placement", "missing")])
def test_any_unknown_model_selector_fails_instead_of_partial_success(shop, capsys, selection):
    proof_write(shop, "shop/orders.py", FIXED)
    code, output = models(shop, capsys, *selection)
    assert code == 1 and "unknown model id 'missing'" in output


def test_model_selector_uses_declared_id_not_filename_alias(shop, capsys):
    path = shop / ".flowguard/models/order_placement.py"
    path.write_text(
        path.read_text().replace('MODEL_ID = "order_placement"', 'MODEL_ID = "checkout"')
    )
    code, output = models(shop, capsys, "order_placement")
    assert code == 1 and "unknown model id" in output
    proof_write(shop, "shop/orders.py", FIXED)
    assert models(shop, capsys, "checkout")[0] == 0




def test_component_selector_reports_its_registered_model_ids(shop, capsys):
    code, output = models(shop, capsys, "orders")
    assert (
        code == 1
        and "is a component id" in output
        and "registered model ids: order_placement" in output
    )


def test_out_of_boundary_inputs_never_report_a_stale_pass(shop, capsys, monkeypatch):
    proof_write(shop, ".gitignore", "shop/local_settings.py\n")
    proof_write(shop, "shop/local_settings.py", "ENABLED = True\n")
    proof_write(
        shop,
        "shop/orders.py",
        "from os import environ\nfrom shop import local_settings\n"
        + FIXED.replace(
            "        if order_id in self.orders:\n",
            "        if order_id in self.orders or not local_settings.ENABLED or environ.get('SHOP_MODE') == 'off':\n",
        ),
    )
    assert models(shop, capsys)[0] == 0
    proof_write(shop, "shop/local_settings.py", "ENABLED = False\n")
    assert models(shop, capsys)[0] == 1
    proof_write(shop, "shop/local_settings.py", "ENABLED = True\n")
    assert models(shop, capsys)[0] == 0
    monkeypatch.setenv("SHOP_MODE", "off")
    assert models(shop, capsys)[0] == 1


@pytest.mark.parametrize("case", ["fake_conformance", "removed_conformance"])
def test_model_that_never_runs_its_implemented_by_code_fails(shop, capsys, case):
    proof_write(shop, "shop/orders.py", FIXED)
    if case == "fake_conformance":
        _edit_model(
            shop,
            "def conformance():\n",
            "def conformance():\n    from types import SimpleNamespace\n"
            "    return SimpleNamespace(ok=True, format_text=lambda **k: '')\n\n\ndef _old():\n",
        )
    else:
        _edit_model(shop, "def conformance():\n", "def _old_conformance():\n")
    code, out = models(shop, capsys)
    assert code == 1 and "never ran" in out
    native = _native_model(shop, shop / MODEL)
    assert native.status == "fail" and "never ran" in " ".join(native.problems)


def test_abstract_model_with_empty_implemented_by_fails(shop, capsys):
    proof_write(shop, "shop/orders.py", FIXED)
    _edit_model(
        shop,
        'IMPLEMENTED_BY = {"PlaceOrder": "shop/orders.py:OrderService.place"}',
        "IMPLEMENTED_BY = {}",
    )
    _edit_model(shop, "def conformance():\n", "def _old_conformance():\n")
    code, out = models(shop, capsys)
    assert (
        code == 1
        and "abstract boundary only" in out
        and "declares no IMPLEMENTED_BY anchors" in out
    )


def test_non_python_anchor_is_a_warning_not_a_failure(shop, capsys):
    import json

    proof_write(shop, "shop/orders.py", FIXED)
    proof_write(shop, "web/cart.ts", "export function addItem(c, i) { return [...c, i]; }\n")
    map_path = shop / ".flowguard/map.json"
    data = json.loads(map_path.read_text())
    data["components"].append(
        dict(
            data["components"][0],
            id="ui",
            summary="Cart interface",
            responsibilities=["render shopping cart"],
            files=["web/cart.ts"],
            entrypoints=[],
            tests=[],
            models=[],
            state=[],
            side_effects=[],
        )
    )
    map_path.write_text(json.dumps(data))
    _edit_model(
        shop,
        'IMPLEMENTED_BY = {"PlaceOrder": "shop/orders.py:OrderService.place"}',
        'IMPLEMENTED_BY = {"PlaceOrder": "shop/orders.py:OrderService.place", "Ui": "web/cart.ts:addItem"}\nCOMPONENTS = ["orders", "ui"]',
    )
    code, out = models(shop, capsys)
    assert code == 0 and "is not Python" in out


@pytest.mark.parametrize(
    "case",
    [
        "crash",
        "invariant_crash",
        "other_invariant",
        "same_name_wrong_predicate",
        "budget",
        "budget_after_violation",
        "design_without_invariants",
    ],
)
def test_broken_variant_must_violate_a_design_property(shop, capsys, case):
    proof_write(shop, "shop/orders.py", FIXED)
    if case == "crash":
        _edit_model(shop, *_CRASH)
        _edit_model(
            shop,
            "INVARIANTS = (",
            "class Crashes(PlaceOrder):\n    def apply(self, inp, state):\n"
            "        raise RuntimeError('boom')\n\n\nINVARIANTS = (",
        )
        expected = "fails without violating"
    elif case == "invariant_crash":
        _edit_model(
            shop,
            'return {"charge_every_time": _explorer(ChargeEveryTime())}',
            "def raising(state, trace):\n        raise RuntimeError('oracle crashed')\n"
            "    raising.__name__ = 'one_charge_per_order'\n"
            "    return {'charge_every_time': Explorer(workflow=Workflow((PlaceOrder(),)), "
            "initial_states=(State(),), external_inputs=INPUTS, invariants=(raising,), progress_steps=0)}",
        )
        expected = "fails without violating"
    elif case in {"other_invariant", "same_name_wrong_predicate"}:
        _edit_model(
            shop,
            'return {"charge_every_time": _explorer(ChargeEveryTime())}',
            "from flowguard import Invariant, InvariantResult\n"
            "    never = Invariant('never', 'always fails', lambda s, t: InvariantResult.fail('x'))\n"
            "    return {'charge_every_time': Explorer(workflow=Workflow((PlaceOrder(),)), initial_states=(State(),), "
            "external_inputs=INPUTS, invariants=(never,), max_sequence_length=3, progress_steps=0)}",
        )
        if case == "same_name_wrong_predicate":
            _edit_model(shop, "Invariant('never',", "Invariant('one_charge_per_order',")
        expected = "fails without violating"
    elif case in {"budget", "budget_after_violation"}:
        block = "ChargeEveryTime()" if case == "budget_after_violation" else "PlaceOrder()"
        limit = 4 if case == "budget_after_violation" else 1
        _edit_model(
            shop,
            'return {"charge_every_time": _explorer(ChargeEveryTime())}',
            f"bad = Explorer(workflow=Workflow(({block},)), initial_states=(State(),), "
            f"external_inputs=INPUTS, invariants=INVARIANTS, max_sequence_length=3, progress_steps=0, max_transitions={limit})\n"
            + (
                "    report = bad.explore()\n"
                "    assert report.exploration_status == 'budget_exhausted'\n"
                "    assert any(v.invariant_name == 'one_charge_per_order' for v in report.violations)\n"
                if case == "budget_after_violation"
                else ""
            )
            + "    return {'charge_every_time': bad}",
        )
        expected = "fails without violating"
    else:
        _edit_model(
            shop,
            "def build_explorer() -> Explorer:\n    return _explorer(PlaceOrder())",
            "def build_explorer() -> Explorer:\n    return Explorer(workflow=Workflow((PlaceOrder(),)), "
            "initial_states=(State(),), external_inputs=INPUTS, invariants=(), max_sequence_length=3, progress_steps=0)",
        )
        expected = "declares no invariants"
    code, out = models(shop, capsys)
    assert code == 1 and expected in out
    if case != "design_without_invariants":
        assert "invariant 'one_charge_per_order' is violated by no known-bad variant" in out
    native = _native_model(shop, shop / MODEL)
    assert native.status == "fail" and expected in " ".join(native.problems)
    if case != "design_without_invariants":
        assert any(
            "invariant 'one_charge_per_order' is violated by no known-bad variant" in problem
            for problem in native.problems
        )


@pytest.mark.parametrize("location", ["hook", "adapter_reset", "adapter_step"])
def test_conformance_import_error_reports_interpreter_environment(shop, capsys, location):
    proof_write(shop, "shop/orders.py", FIXED)
    if location == "hook":
        _edit_model(
            shop,
            "def conformance():\n",
            "def conformance():\n    import nonexistent_third_party_dependency\n",
        )
    elif location == "adapter_reset":
        proof_write(shop, "shop/orders.py", "import nonexistent_third_party_dependency\n" + FIXED)
    else:
        proof_write(
            shop,
            "shop/orders.py",
            FIXED.replace(
                "        if order_id in self.orders:",
                "        import nonexistent_third_party_dependency\n        if order_id in self.orders:",
            ),
        )
    code, out = models(shop, capsys)
    assert code == 1 and "ERROR" in out and "interpreter" in out and "environment" in out
    assert "does not conform" not in out


def test_explorer_with_no_initial_states_proves_nothing(shop, capsys):
    proof_write(shop, "shop/orders.py", FIXED)
    _edit_model(
        shop,
        "def build_explorer() -> Explorer:\n    return _explorer(PlaceOrder())",
        "def build_explorer() -> Explorer:\n    return Explorer(workflow=Workflow((PlaceOrder(),)), "
        "initial_states=(), external_inputs=INPUTS, invariants=INVARIANTS, progress_steps=0)",
    )
    code, out = models(shop, capsys)
    assert code == 1 and "explored no input transitions" in out


def test_unbound_models_are_errors_in_check(shop, capsys):
    proof_write(shop, "shop/orders.py", FIXED)
    _edit_model(
        shop,
        'IMPLEMENTED_BY = {"PlaceOrder": "shop/orders.py:OrderService.place"}',
        "IMPLEMENTED_BY = {}",
    )
    _edit_model(shop, "def conformance():\n", "def _old_conformance():\n")
    out = _check_codes(shop, capsys)
    assert "model_anchor_missing" in out and "model_conformance_missing" in out


def test_bound_test_method_cannot_impersonate_a_top_level_anchor(shop, capsys):
    proof_write(
        shop,
        "shop/orders.py",
        FIXED
        + "\ndef run():\n    return 'top'\n\nclass Other:\n    def run(self):\n        return 'other'\n",
    )
    path = shop / ".flowguard/models/order_placement.py"
    source = MODEL_SOURCE.replace("shop/orders.py:OrderService.place", "shop/orders.py:run")
    source += (
        "\n_base_conformance = conformance\ndef conformance():\n"
        "    from shop.orders import run\n    assert run() == 'top'\n    return _base_conformance()\n"
        "TESTED_BY = {'one_charge_per_order': ['tests/test_orders.py:test_bound']}\n"
    )
    path.write_text(source)
    proof_write(
        shop,
        "tests/test_orders.py",
        "def test_bound():\n    from shop.orders import Other\n    assert Other().run() == 'other'\n",
    )
    code, output = models(shop, capsys, "order_placement", "--tests")
    assert code == 1, output
    assert "tested_by_misses_anchor one_charge_per_order" in output


@pytest.mark.parametrize(
    "with_map,parent_first",
    [(True, False), (False, False), (True, True)],
    ids=["map", "no_map", "from_import_after_parent"],
)
def test_child_start_gap_warns_when_the_child_misses_parent_states(
    tmp_path, capsys, with_map, parent_first
):
    import json
    import subprocess
    from flowguard.map.proof import run_model

    proof_write(tmp_path, "counter.py", "def increment(value):\n    return value + 1\n")
    proof_write(
        tmp_path,
        "tests/test_counter.py",
        "def test_increment():\n    from counter import increment\n    assert increment(0) == 1\n",
    )
    parent = """from dataclasses import dataclass
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
"""
    child = """import parent
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
"""
    proof_write(tmp_path, ".flowguard/models/parent.py", parent)
    path = tmp_path / ".flowguard/models/child.py"
    proof_write(tmp_path, ".flowguard/models/child.py", child)
    if with_map:
        proof_write(
            tmp_path,
            ".flowguard/map.json",
            json.dumps(
                dict(
                    schema="flowguard.map.v1",
                    components=[
                        dict(
                            id="counter",
                            files=["counter.py"],
                            tests=["tests/test_counter.py"],
                            models=[],
                            depends_on=[],
                            status="draft",
                            summary="Counter",
                            responsibilities=["increment a counter"],
                        )
                    ],
                )
            ),
        )
    without_projection = child.replace("def project_parent_state(state): return state\n", "")
    path.write_text(without_projection)
    code, output = models(tmp_path, capsys, "counter_child")
    assert code == 0 and "child_start_gap" not in output, output
    path.write_text(child)
    if parent_first:
        import sys

        path.write_text(
            child.replace(
                "import parent",
                "from parent import State, make_explorer, broken_variants as parent_variants, conformance as parent_conformance",
            )
            .replace("parent.State()", "State()")
            .replace("parent.make_explorer(", "make_explorer(")
            .replace("parent.broken_variants()", "parent_variants()")
            .replace("parent.conformance()", "parent_conformance()")
        )
        script = """import json, sys
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
"""
        result = subprocess.run(
            [sys.executable, "-c", script, str(tmp_path)],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        return
    code, output = models(tmp_path, capsys, "counter_child")
    assert code == 0, output
    assert "child_start_gap: 3 of 4 states the parent 'counter_parent' reaches" in output
    if with_map:
        from flowguard.map.cli import _context
        from flowguard.map.check import run_check

        data, inv = _context(tmp_path)
        assert not {"parent_cycle", "parent_import_mismatch"} & {
            f.code for f in run_check(tmp_path, data, inv)
        }
    seeded = child.replace(
        "STARTS = (parent.State(),)",
        "from flowguard.kit import reachable_states\nSTARTS = reachable_states(parent.build_explorer())",
    )
    path.write_text(seeded)
    code, output = models(tmp_path, capsys, "counter_child")
    assert code == 0 and "child_start_gap" not in output, output

    local = without_projection.replace(
        "STARTS = (parent.State(),)",
        "from dataclasses import dataclass\n@dataclass(frozen=True)\nclass LocalState:\n    value: int = 0\nSTARTS = (LocalState(),)",
    )
    path.write_text(local)
    result = run_model(tmp_path, path)
    assert result.status == "pass" and not any(
        "child_start_gap" in w for w in result.warnings
    ), result
    path.write_text(local + "\ndef project_parent_state(state): return LocalState(state.value)\n")
    result = run_model(tmp_path, path)
    assert result.status == "pass" and any(
        "child_start_gap: 3 of 4" in w for w in result.warnings
    ), result

    path.write_text(child)
    proof_write(
        tmp_path,
        ".flowguard/models/parent.py",
        parent.replace(
            "def build_explorer(): return make_explorer()",
            'def build_explorer(): raise RuntimeError("port unavailable\\nextra detail")',
        ),
    )
    result = run_model(tmp_path, path)
    assert result.status == "pass", result
    warning = next(w for w in result.warnings if "child_start_gap not checked:" in w)
    assert "parent 'counter_parent' could not be explored (port unavailable)" in warning
    assert "\n" not in warning
    path.write_text(without_projection)
    result = run_model(tmp_path, path)
    assert result.status == "pass" and not any(
        "child_start_gap" in w for w in result.warnings
    ), result


def test_grouped_sub_check_under_a_parent_gets_no_start_gap_warning(tmp_path, capsys):
    proof_write(tmp_path, "counter.py", "def valid(value):\n    return value >= 0\n")
    proof_write(
        tmp_path,
        "tests/test_counter.py",
        "def test_valid():\n    from counter import valid\n    assert valid(0) and not valid(-1)\n",
    )
    source = """from flowguard.kit import Feature, feature_explorer, feature_variants, feature_conformance
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
"""
    proof_write(
        tmp_path,
        ".flowguard/models/parent.py",
        source.replace("MODEL_NAME", "counter_parent").replace(
            "EXTRA_FEATURE",
            'Feature("positive", False, apply=lambda value: value if value < 0 else 1),',
        ),
    )
    proof_write(
        tmp_path,
        ".flowguard/models/child.py",
        source.replace("MODEL_NAME", "counter_child").replace("EXTRA_FEATURE", "")
        + '\nPARENT = "counter_parent"\n',
    )
    code, output = models(tmp_path, capsys, "counter_parent", "counter_child")
    assert (
        code == 0 and "models: 2 passed, 0 failed" in output and "child_start_gap" not in output
    ), output


@pytest.mark.parametrize("location", ["conformance", "explore"])
def test_placeholder_anchor_failures_are_clean_in_hooks_and_exploration(shop, capsys, location):
    proof_write(shop, "shop/orders.py", FIXED)
    call = "    from flowguard.map.facts import load_anchor\n    load_anchor('REPLACE_ME/module.py:Owner')\n"
    if location == "conformance":
        _edit_model(shop, "def conformance():\n", "def conformance():\n" + call)
    else:
        _edit_model(
            shop,
            "    def apply(self, inp: Place, state: State):\n",
            "    def apply(self, inp: Place, state: State):\n"
            + "\n".join("    " + line for line in call.rstrip().split("\n"))
            + "\n",
        )
    code, output = models(shop, capsys, "order_placement")
    assert code == 1 and "FAIL" in output and "ERROR" not in output
    assert (
        "placeholder anchor 'REPLACE_ME/module.py:Owner': replace it with the real 'path:Symbol' this model is about"
        in output
    )
    assert "Traceback" not in output
    assert "explored no input transitions" not in output


@pytest.mark.parametrize("mixed_keys", [False, True])
def test_models_output_lists_rule_and_variant_names(shop, capsys, monkeypatch, mixed_keys):
    import json
    from flowguard.map import cli

    proof_write(shop, "shop/orders.py", FIXED)
    expected_bad = ["charge_every_time"]
    if mixed_keys:
        _edit_model(
            shop,
            'return {"charge_every_time": _explorer(ChargeEveryTime())}',
            'return {1: _explorer(ChargeEveryTime()), "1": _explorer(ChargeEveryTime()), '
            '"charge_every_time": _explorer(ChargeEveryTime())}',
        )
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
    (result,) = captured
    assert result.rules == ["one_charge_per_order"]
    assert result.known_bad == expected_bad
    assert "rules:" not in output and len(output.splitlines()) == 2
    assert json.loads(json.dumps(result.__dict__))["known_bad"] == expected_bad


def test_system_model_names_follow_one_generated_pass(shop, capsys, monkeypatch):
    import json
    from flowguard.map import cli
    from flowguard.map import system_model

    proof_write(shop, "shop/orders.py", FIXED)
    proof_write(
        shop,
        "shop/api.py",
        "from shop.orders import OrderService\ndef handle(): return OrderService()\n",
    )
    map_path = shop / ".flowguard/map.json"
    data = json.loads(map_path.read_text())
    data["layers"] = ["interface", "engine"]
    orders = data["components"][0]
    orders.update(files=["shop/orders.py", "shop/__init__.py"], layer="engine")
    data["components"].append(
        dict(
            orders,
            id="api",
            layer="interface",
            responsibilities=["receive requests"],
            files=["shop/api.py"],
            entrypoints=["shop/api.py:handle"],
            depends_on=["orders"],
            tests=[],
            models=[],
            state=[],
            side_effects=[],
        )
    )
    map_path.write_text(json.dumps(data))
    actual_variants, actual_models = system_model.architecture_variants, cli.run_models
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

    monkeypatch.setattr(system_model, "architecture_variants", variants)
    monkeypatch.setattr(cli, "run_models", capture)
    code, output = models(shop, capsys, "system")
    assert code == 0, output
    (result,) = captured
    assert passes == [1] and names
    assert result.rules == ["dependency_cycle", "duplicate_owner", "layer_violation"]
    assert result.known_bad == sorted(names)
    assert "rules:" not in output and len(output.splitlines()) == 2
    assert result.known_bad == sorted(names)


def test_fallback_that_reports_success_is_a_known_bad_variant(tmp_path, capsys):
    import json

    proof_write(
        tmp_path,
        "app.py",
        """def primary(available):
    return "ok" if available else "failed"

def backup(result):
    return "error" if result == "failed" else result

def run(available):
    return backup(primary(available))
""",
    )
    proof_write(
        tmp_path,
        "tests/test_app.py",
        """from app import run

def test_run():
    assert run(True) == "ok"
    assert run(False) == "error"
""",
    )
    source = """from flowguard import FunctionResult, Invariant, Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport, Fact
MODEL_ID = "fallback"
COMPONENTS = ["app"]
IMPLEMENTED_BY = {"Primary": "app.py:primary", "Backup": "app.py:backup", "Run": "app.py:run"}
TESTED_BY = {"failure_visible": ["tests/test_app.py:test_run"]}
class Primary:
    name = "Primary"
    def apply(self, available, state):
        return [FunctionResult("ok" if available else "failed", (not available, "pending"))]
class Backup:
    name = "Backup"
    def __init__(self, silent=False): self.silent = silent
    def apply(self, result, state):
        output = "ok" if self.silent else ("error" if result == "failed" else result)
        return [FunctionResult(output, (state[0], output))]
INVARIANTS = (Invariant("failure_visible", "a failed primary never becomes silent success", lambda s, t: not s[0] or s[1] in ("pending", "error")),)
def explorer(silent=False):
    return Explorer(Workflow((Primary(), Backup(silent))), initial_states=((False, "pending"),),
                    external_inputs=(True, False), max_sequence_length=1, progress_steps=0,
                    invariants=INVARIANTS)
def build_explorer(): return explorer()
def broken_variants(): return {"silent_success": explorer(True)}
def conformance():
    from app import run
    return CodeFactsReport(tuple(Fact("visible outcome", run(available) == expected, str(available))
                                 for available, expected in ((True, "ok"), (False, "error"))))
"""
    path = ".flowguard/models/fallback.py"
    proof_write(tmp_path, path, source)
    proof_write(
        tmp_path,
        ".flowguard/map.json",
        json.dumps(
            {
                "schema": "flowguard.map.v1",
                "components": [
                    dict(
                        id="app",
                        summary="Application outcome",
                        responsibilities=["report the application outcome"],
                        files=["app.py"],
                        entrypoints=["app.py:run"],
                        tests=["tests/test_app.py"],
                        models=[path],
                        depends_on=[],
                        status="draft",
                    )
                ],
            }
        ),
    )
    code, output = models(tmp_path, capsys, "fallback", "--tests")
    assert code == 0 and "PASS  fallback" in output, output
    assert "rules:" not in output and "  tests " in output
    assert _native_model(tmp_path, tmp_path / path).known_bad == ["silent_success"]
    lines = source.splitlines(keepends=True)
    rule = next(line for line in lines if line.startswith("INVARIANTS = "))
    proof_write(tmp_path, path, source.replace(rule, "INVARIANTS = ()\n"))
    code, output = models(tmp_path, capsys, "fallback")
    assert code == 1 and "FAIL  fallback" in output, output
    assert "known-bad variant 'silent_success' passed" in output, output

import json
import subprocess
from pathlib import Path
import pytest
from flowguard.__main__ import main
from flowguard.map.cli import _context
from flowguard.map.check import run_check
from flowguard.map.lint import run_lint

def test_review_and_find_name_the_owning_models(tmp_path, capsys):
    import json
    import subprocess
    from pathlib import Path
    import pytest
    from flowguard.__main__ import main
    from flowguard.map.cli import _context
    from flowguard.map.check import run_check
    from flowguard.map.lint import run_lint

    data = project(tmp_path)
    # This map-view fixture's hooks are inspected, never executed as model proof.
    flowguard_map_contracts421_write(
        tmp_path, ".flowguard/models/one.py", CONTRACT + "\ndef conformance(): pass\n"
    )
    flowguard_map_contracts421_write(tmp_path, "other.py", "def idle(): return 0\n")
    data["components"].append(
        dict(
            id="other",
            files=["other.py"],
            status="draft",
            summary="Independent work",
            responsibilities=["idle"],
            depends_on=[],
        )
    )
    flowguard_map_contracts421_save(tmp_path, data)
    assert main(["map", "--root", str(tmp_path), "confirm", "app", "other"]) == 0
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "-c",
            "user.name=fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-qm",
            "initial",
        ],
        check=True,
    )
    capsys.readouterr()
    flowguard_map_contracts421_write(tmp_path, "app.py", "def run():\n    return bool(1)\n")
    flowguard_map_contracts421_write(tmp_path, "other.py", "def idle(): return int(0)\n")
    assert main(["change", "--root", str(tmp_path), "app.py", "other.py"]) == 0
    output = capsys.readouterr().out
    review = next(line for line in output.splitlines() if line.startswith("REVIEW app:"))
    assert "models to re-read: one" in review
    assert "(does the change need a new input, state or invariant?)" in review
    assert next(line for line in output.splitlines() if line.startswith("REVIEW other:")) == (
        "REVIEW other: its files changed; update its description if behavior changed, then confirm other"
    )
    assert main(["read", "--root", str(tmp_path), "--find", "run"]) == 0
    assert "     models: one" in capsys.readouterr().out
    assert main(["map", "--root", str(tmp_path), "impact", "app.py", "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["review_models"] == {"app": ["one"]}
