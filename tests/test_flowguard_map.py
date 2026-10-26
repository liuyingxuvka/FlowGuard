"""Tests for flowguard.map: scan, check, lint, impact, find, show, digest, confirm, cache."""

from __future__ import annotations

import io
import json
import shutil
import subprocess
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from flowguard.map import cli
from flowguard.map.common import DEFAULT_IGNORE
from flowguard.map.inventory import build_inventory


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture(scope="module")
def _project_template(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("project-template") / "shop"
    write(root, "shop/__init__.py", "")
    write(root, "shop/api.py", "from shop.orders import place_order\n\ndef handle(req):\n    return place_order(req)\n")
    write(root, "shop/orders.py", "from typing import TYPE_CHECKING\nfrom shop import storage\nif TYPE_CHECKING:\n    from shop.api import handle\n\n"
          "class OrderService:\n    def place(self, x):\n        return storage.save(x)\n\ndef place_order(x):\n    return OrderService().place(x)\n")
    write(root, "shop/storage.py", "DB = {}\n\ndef save(x):\n    DB[x] = True\n    return x\n")
    write(root, "web/app.js", "import { api } from './client';\nexport const x = 1;\n")
    write(root, "web/client.js", "export const api = 2;\n")
    write(root, "tests/test_orders.py", "def test_x():\n    assert True\n")
    write(root, "tests/test_storage.py", "def test_y():\n    assert True\n")
    git(root, "init", "-q")
    git(root, "add", "-A")
    git(root, "-c", "user.email=a@b", "-c", "user.name=t", "commit", "-qm", "init")
    return root


@pytest.fixture()
def project(tmp_path: Path, _project_template: Path) -> Path:
    return Path(shutil.copytree(_project_template, tmp_path / "shop"))


def run(root: Path, *argv: str, capsys=None) -> tuple[int, str]:
    code = cli.main(["--root", str(root), *argv])
    out = capsys.readouterr().out if capsys else ""
    return code, out


def load(root: Path) -> dict:
    return json.loads((root / ".flowguard/map.json").read_text(encoding="utf-8"))


def save(root: Path, data: dict) -> None:
    (root / ".flowguard/map.json").write_text(json.dumps(data, indent=2), encoding="utf-8")


def fill(root: Path) -> dict:
    """What the AI does after scan: describe components, merge, set layers."""
    data = load(root)
    data["layers"] = ["entry", "domain", "infra"]
    data["components"] = [
        {"id": "api", "layer": "entry", "summary": "HTTP entry", "responsibilities": ["accept order requests"],
         "files": ["shop/api.py", "shop/__init__.py"], "entrypoints": ["shop/api.py:handle"], "state": [],
         "side_effects": [], "depends_on": ["orders"], "tests": [], "models": [], "status": "draft", "fingerprint": ""},
        {"id": "orders", "layer": "domain", "summary": "Order rules", "responsibilities": ["place an order once"],
         "files": ["shop/orders.py"], "entrypoints": ["shop/orders.py:OrderService.place"], "state": [],
         "side_effects": [], "depends_on": ["storage"], "tests": ["tests/test_orders.py"], "models": [],
         "status": "draft", "fingerprint": ""},
        {"id": "storage", "layer": "infra", "summary": "Persistence", "responsibilities": ["save orders to the database"],
         "files": ["shop/storage.py"], "entrypoints": ["shop/storage.py:save"], "state": ["DB dict"],
         "side_effects": ["writes DB"], "depends_on": [], "tests": ["tests/test_storage.py"], "models": [],
         "status": "draft", "fingerprint": ""},
        {"id": "web", "layer": "entry", "summary": "Browser client", "responsibilities": ["render the shop page"],
         "files": ["web/*.js"], "entrypoints": ["web/app.js:x"], "state": [], "side_effects": [], "depends_on": [],
         "tests": [], "models": [], "status": "draft", "fingerprint": ""},
    ]
    data["flows"] = [{"id": "place_order", "summary": "request to saved order",
                      "steps": ["api:handle", "orders:place", "storage:save"]}]
    save(root, data)
    return data


def codes(root: Path, command: str, capsys) -> list[str]:
    cli.main(["--root", str(root), command, "--json"])
    return [f["code"] for f in json.loads(capsys.readouterr().out)["findings"]]


def test_scan_creates_draft_map_with_real_deps(project, capsys):
    code, out = run(project, "scan", capsys=capsys)
    assert code == 0 and "draft components" in out
    data = load(project)
    ids = {c["id"] for c in data["components"]}
    assert {"shop", "web"} <= ids
    assert all(c["status"] == "draft" for c in data["components"])
    assert (project / ".flowguard/cache/inventory.json").is_file()


def test_type_checking_imports_are_not_dependencies(project):
    inv = build_inventory(project, DEFAULT_IGNORE)
    assert "shop/api.py" not in inv.file_deps.get("shop/orders.py", set())
    assert "shop/storage.py" in inv.file_deps["shop/orders.py"]
    assert "web/client.js" in inv.file_deps["web/app.js"]


def test_filled_map_checks_clean_after_confirm(project, capsys):
    run(project, "scan", capsys=capsys)
    fill(project)
    assert run(project, "confirm", "api", "orders", "storage", "web", capsys=capsys)[0] == 0
    assert codes(project, "check", capsys) == []


def test_check_reports_unmapped_overlap_anchor_and_undeclared_dep(project, capsys):
    run(project, "scan", capsys=capsys)
    data = fill(project)
    data["components"][0]["entrypoints"] = ["shop/api.py:missing_fn"]
    data["components"][1]["depends_on"] = []                       # orders really imports storage
    data["components"][2]["files"].append("shop/orders.py")        # overlap
    save(project, data)
    write(project, "shop/payments.py", "def pay():\n    return 1\n")  # new unowned file
    found = codes(project, "check", capsys)
    for expected in ("anchor_broken", "dep_undeclared", "file_multi_owner", "file_unmapped"):
        assert expected in found, found


def test_stale_after_owned_file_changes_and_confirm_clears_it(project, capsys):
    run(project, "scan", capsys=capsys)
    fill(project)
    run(project, "confirm", "api", "orders", "storage", "web", capsys=capsys)
    write(project, "shop/storage.py", "DB = {}\n\ndef save(x):\n    DB[x] = 1\n    return x\n")
    assert codes(project, "check", capsys) == ["stale"]
    run(project, "confirm", "storage", capsys=capsys)
    assert codes(project, "check", capsys) == []


def test_flow_steps_are_verified(project, capsys):
    run(project, "scan", capsys=capsys)
    data = fill(project)
    data["flows"][0]["steps"].append("storage:delete_everything")
    data["flows"][0]["steps"].append("billing:charge")
    save(project, data)
    found = codes(project, "check", capsys)
    assert "flow_step_broken" in found and "flow_step_unknown" in found


def test_lint_finds_layer_violation_cycle_and_duplicate_owner(project, capsys):
    run(project, "scan", capsys=capsys)
    data = fill(project)
    write(project, "shop/storage.py", "from shop.orders import place_order\nDB = {}\n\ndef save(x):\n    return x\n")
    data["components"][2]["responsibilities"].append("place an order once")
    save(project, data)
    found = codes(project, "lint", capsys)
    assert "layer_violation" in found          # infra -> domain
    assert "dependency_cycle" in found         # orders <-> storage
    assert "duplicate_owner" in found          # same responsibility in two components


def test_impact_selects_only_affected_tests(project, capsys):
    run(project, "scan", capsys=capsys)
    fill(project)
    run(project, "confirm", "api", "orders", "storage", "web", capsys=capsys)
    git(project, "add", "-A")
    git(project, "-c", "user.email=a@b", "-c", "user.name=t", "commit", "-qm", "map")
    write(project, "shop/storage.py", "DB = {}\n\ndef save(x):\n    return x\n")
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


def test_show_is_bounded_and_digest_has_no_bodies(project, capsys):
    run(project, "scan", capsys=capsys)
    fill(project)
    code, out = run(project, "show", "--budget", "200", capsys=capsys)
    assert code == 0 and len(out) < 320 and "truncated" in out
    code, out = run(project, "digest", "orders", capsys=capsys)
    assert "class OrderService" in out and "storage.save" not in out


def test_cache_is_invalidated_when_a_file_changes(project, capsys):
    run(project, "scan", capsys=capsys)
    inv1 = build_inventory(project, DEFAULT_IGNORE)
    assert "save" in inv1.py["shop/storage.py"].symbols
    write(project, "shop/storage.py", "def persist(x):\n    return x\n\n\n")
    inv2 = build_inventory(project, DEFAULT_IGNORE)
    assert "persist" in inv2.py["shop/storage.py"].symbols and "save" not in inv2.py["shop/storage.py"].symbols


def test_invalid_map_is_rejected(project, capsys):
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


@pytest.fixture(scope="module")
def _impact_project_template(tmp_path_factory, _project_template):
    project = Path(shutil.copytree(_project_template, tmp_path_factory.mktemp("impact-template") / "shop"))
    with redirect_stdout(io.StringIO()):
        assert run(project, "scan")[0] == 0
    data = fill(project)
    data["components"][0]["tests"] = ["tests/test_api.py"]
    data["components"][1]["models"] = [".flowguard/models/orders_check.py"]
    data["components"][2]["models"] = [".flowguard/models/persistence.py"]
    write(project, "tests/test_api.py", "def test_api():\n    assert True\n")
    write(project, "tests/test_web.py", "def test_web():\n    assert True\n")
    data["components"][3]["tests"] = ["tests/test_web.py"]
    write(project, ".flowguard/models/orders_check.py", '''from flowguard import FunctionResult, Invariant, Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport, Fact
MODEL_ID = "orders_check"
COMPONENTS = ["orders"]
IMPLEMENTED_BY = {"Place": "shop/orders.py:OrderService.place"}
TESTED_BY = {}
class Place:
    name = "Place"
    def __init__(self, persists=True): self.persists = persists
    def apply(self, value, state):
        saved = state[1] | {value} if self.persists else state[1]
        return [FunctionResult(value, (value, saved))]
def explorer(persists=True):
    return Explorer(Workflow((Place(persists),)), initial_states=((None, frozenset()),), external_inputs=(0, 1),
                    max_sequence_length=1, progress_steps=0,
                    invariants=(Invariant("placed_is_saved", "placing an order writes its database entry",
                                          lambda s, t: s[0] is None or s[0] in s[1]),))
def build_explorer(): return explorer()
def broken_variants(): return {"does_not_save": explorer(False)}
def conformance():
    from shop.orders import OrderService
    from shop import storage
    storage.DB.clear()
    facts = []
    for value in (0, 1):
        observed = OrderService().place(value)
        facts.extend((Fact("return matches input", observed == value, str(value)),
                      Fact("order stored", storage.DB.get(value) is True, str(value))))
    return CodeFactsReport(tuple(facts))
''')
    write(project, ".flowguard/models/persistence.py", "MODEL_ID = 'storage-proof'\nCOMPONENTS = ['storage']\ndef build_explorer():\n    pass\n")
    save(project, data)
    git(project, "add", "-A")
    git(project, "-c", "user.email=a@b", "-c", "user.name=t", "commit", "-qm", "map with checks")
    return project


@pytest.fixture()
def impact_project(tmp_path: Path, _impact_project_template: Path):
    root = Path(shutil.copytree(_impact_project_template, tmp_path / "shop"))
    return root, load(root)




def impact_of(root, data, changed, **kwargs):
    from flowguard.map.impact import compute_impact
    return compute_impact(root, data, build_inventory(root, DEFAULT_IGNORE), changed, **kwargs)


@pytest.fixture()
def retired_model_project(impact_project):
    root, data = impact_project
    for mid in ("survivor", "retired"):
        write(root, f"tests/test_{mid}.py", "def test_safe():\n    assert True\n")
        write(root, f".flowguard/models/{mid}.py",
              f"MODEL_ID = {mid!r}\nCOMPONENTS = ['storage']\n"
              "IMPLEMENTED_BY = {'Save': 'shop/storage.py:save'}\n"
              f"TESTED_BY = {{'safe': ['tests/test_{mid}.py:test_safe']}}\n"
              + ("PARENT = 'survivor'\n" if mid == "retired" else "")
              + "def build_explorer(): pass\n")
    git(root, "add", "-A")
    git(root, "-c", "user.email=a@b", "-c", "user.name=t", "commit", "-qm", "retirement baseline")
    return root, data


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
    source = ("MODEL_ID = 'importer'\nCOMPONENTS = ['storage']\n"
              "TESTED_BY = {'safe': ['tests/test_importer.py:test_safe']}\n"
              "def build_explorer(): pass\n")
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
        write(root, ".flowguard/models/orphan.py",
              "MODEL_ID = 'orphan'\nCOMPONENTS = ['storage']\nPARENT = 'retired'\n"
              "TESTED_BY = {'safe': ['tests/test_storage.py:test_y']}\n"
              "def build_explorer(): pass\n")
    save(root, data)
    imp = impact_of(root, data, changed_files(root, "HEAD"), base="HEAD")
    assert imp.blocked
    if residue == "parent":
        assert "orphan" in imp.model_ids and "tests/test_storage.py" in imp.tests


@pytest.mark.parametrize("invalid", ["never-existed", "malformed", "duplicate", "no-base"])
def test_missing_model_without_unambiguous_base_contract_stays_blocked(retired_model_project, invalid):
    root, data = retired_model_project
    path = ".flowguard/models/retired.py"
    if invalid == "malformed":
        write(root, path, "MODEL_ID = 'retired'\n")
    elif invalid == "duplicate":
        write(root, ".flowguard/models/duplicate.py", (root / path).read_text())
    if invalid in {"malformed", "duplicate"}:
        git(root, "add", "-A")
        git(root, "-c", "user.email=a@b", "-c", "user.name=t", "commit", "-qm", "invalid old contract")
    (root / path).unlink()
    if invalid == "never-existed":
        path = ".flowguard/models/never_existed.py"
    imp = impact_of(root, data, [path], base=None if invalid == "no-base" else "HEAD")
    assert imp.blocked


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


@pytest.mark.parametrize("surface", ["lazy", "alias"])
def test_impact_declared_edges_bridge_unsupported_imports(impact_project, surface):
    root, data = impact_project
    if surface == "lazy":
        write(root, "shop/api.py", "import importlib\ndef handle(req):\n    return importlib.import_module('shop.orders').place_order(req)\n")
    else:
        write(root, "web/app.js", "import { api } from '@shop/orders';\n")
        data["components"][3]["depends_on"] = ["orders"]
    imp = impact_of(root, data, ["shop/orders.py"])
    expected = "api" if surface == "lazy" else "web"
    assert expected in imp.dependents
    if surface == "lazy":
        assert not any("declared but unverified" in message and message.startswith("api") for message in imp.uncertainty)
    else:
        assert any(f"{expected} -> orders: declared but unverified" in message for message in imp.uncertainty)


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
        write(root, ".flowguard/models/new_storage.py", "MODEL_ID = 'new-storage-proof'\nCOMPONENTS = ['storage']\ndef build_explorer():\n    pass\n")
        data["components"][2]["models"] = [".flowguard/models/new_storage.py"]
        save(root, data)
        changed = [".flowguard/map.json"]
    else:
        changed = [{"contract": ".flowguard/models/persistence.py", "test": "tests/test_orders.py"}[change]]
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


def test_impact_shared_test_binding_and_unknown_helper(impact_project):
    root, data = impact_project
    data["components"][2]["tests"].append("tests/test_orders.py")
    imp = impact_of(root, data, ["tests/test_orders.py"])
    assert imp.direct == [] and imp.dependents == []
    assert imp.tests == ["tests/test_orders.py"]
    assert imp.model_ids == []
    unknown = impact_of(root, data, [".flowguard/models/owners/unbound/helper.py"])
    assert unknown.blocked and not unknown.models and not unknown.model_ids


def test_impact_summary_only_map_change_does_not_select_checks(impact_project):
    root, data = impact_project
    data["components"][1]["summary"] = "Clarified order rules"
    save(root, data)
    imp = impact_of(root, data, [".flowguard/map.json"], base="HEAD")
    assert imp.map_review == ["orders"]
    assert not imp.tests and not imp.models and not imp.blocked


def test_impact_cli_uses_full_closure_and_discloses_depth(impact_project, capsys):
    root, data = impact_project
    code, out = run(root, "impact", "shop/storage.py", capsys=capsys)
    assert code == 0 and "dependents: api, orders" in out
    code, out = run(root, "impact", "shop/storage.py", "--depth", "1", capsys=capsys)
    assert code == 0 and "TRUNCATED" in out and "dependents: orders" in out


def test_deps_write_keeps_unverified_declared_dependencies(impact_project, capsys):
    root, data = impact_project
    write(root, "shop/api.py", "import importlib\ndef handle(req):\n    return importlib.import_module('shop.orders').place_order(req)\n")
    run(root, "deps", "--write", capsys=capsys)
    assert load(root)["components"][0]["depends_on"] == ["orders"]


def test_impact_static_parenthesized_import_is_not_dynamic(impact_project):
    root, data = impact_project
    write(root, "shop/api.py", "from shop.orders import (\n    place_order,\n)\n")
    imp = impact_of(root, data, ["shop/orders.py"])
    assert "api" in imp.dependents
    assert not any("shop/api.py: dynamic" in message for message in imp.uncertainty)


def test_impact_duplicate_model_id_is_blocked_without_run_hint(impact_project):
    from flowguard.map.impact import render_impact
    root, data = impact_project
    write(root, ".flowguard/models/duplicate.py", "MODEL_ID = 'storage-proof'\ndef build_explorer():\n    pass\n")
    imp = impact_of(root, data, ["shop/storage.py"])
    assert any("duplicated" in message for message in imp.blocked)
    assert "storage-proof" not in imp.model_ids
    assert "storage-proof" not in render_impact(imp).split("run: python -m flowguard map models")[-1]


def test_non_ascii_file_names_are_inventoried_and_fingerprinted(project):
    write(project, "shop/工具.py", "def 帮助():\n    return 1\n")
    git(project, "add", "-A")
    inv = build_inventory(project, DEFAULT_IGNORE)
    assert "shop/工具.py" in inv.source            # git C-quotes this name without -z


def test_cli_output_never_crashes_on_text_the_console_cannot_encode(project, capsys, monkeypatch):
    import io
    import sys
    run(project, "scan", capsys=capsys)
    data = fill(project)
    data["components"][0]["summary"] = "运行检查 ✓"
    save(project, data)
    console = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")   # Windows pipe code page
    monkeypatch.setattr(sys, "stdout", console)
    assert cli.main(["--root", str(project), "show"]) == 0
    console.flush()
    assert b"\\u8fd0\\u884c" in console.buffer.getvalue()


def test_impact_decodes_previous_map_and_changed_names_as_utf8(project, capsys, monkeypatch):
    real_run = subprocess.run

    def ansi_run(*args, **kwargs):            # Windows: text=True decodes git output with the ANSI code page
        if kwargs.pop("text", False):
            kwargs["encoding"] = "cp1252"
        return real_run(*args, **kwargs)

    run(project, "scan", capsys=capsys)
    data = fill(project)
    data["components"][0]["summary"] = "运行检查"          # UTF-8 has byte 0x90, undefined in cp1252
    data["components"][0]["files"].append("shop/工具.py")
    (project / ".flowguard/map.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    write(project, "shop/工具.py", "VALUE = 1\n")
    git(project, "add", "-A")
    git(project, "-c", "user.email=a@b", "-c", "user.name=t", "commit", "-qm", "chinese map")
    write(project, "shop/工具.py", "VALUE = 2\n")
    monkeypatch.setattr(subprocess, "run", ansi_run)
    code, out = run(project, "impact", "--base", "HEAD", capsys=capsys)
    assert code == 0, out
    assert "directly affected: api" in out


def test_bom_and_coding_cookie_sources_parse_like_python(project, capsys):
    run(project, "scan", capsys=capsys)
    data = fill(project)
    data["components"][2]["files"].append("shop/legacy.py")
    save(project, data)
    storage = project / "shop/storage.py"
    storage.write_bytes(b"\xef\xbb\xbf" + storage.read_bytes())            # PowerShell 5.1 / Visual Studio BOM
    (project / "shop/legacy.py").write_bytes('# -*- coding: gbk -*-\nNAME = "订单"\n'.encode("gbk"))
    mapping = project / ".flowguard/map.json"
    mapping.write_bytes(b"\xef\xbb\xbf" + mapping.read_bytes())            # map edited by a Windows tool
    code, out = run(project, "check", capsys=capsys)
    assert code == 0 and "source_parse_error" not in out and "anchor_broken" not in out, out
    code, out = run(project, "impact", "shop/legacy.py", "shop/storage.py", capsys=capsys)
    assert code == 0 and "directly affected: storage" in out, out


def test_inventory_cache_never_trusts_a_parse_of_a_just_written_file(project):
    import os
    path = project / "shop/storage.py"
    path.write_text("def save(x):\n    return x\n", encoding="utf-8")
    first = build_inventory(project, DEFAULT_IGNORE)
    assert "save" in first.py["shop/storage.py"].symbols
    st = path.stat()
    path.write_text("def keep(x):\n    return x\n", encoding="utf-8")           # same size
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns))                         # same coarse mtime tick
    second = build_inventory(project, DEFAULT_IGNORE)
    assert "keep" in second.py["shop/storage.py"].symbols


def test_impact_accepts_absolute_and_backslash_paths(project, capsys):
    run(project, "scan", capsys=capsys)
    fill(project)
    code, out = run(project, "impact", str(project / "shop" / "api.py"), "shop\\orders.py", capsys=capsys)
    assert code == 0 and "UNMAPPED" not in out and "directly affected: api, orders" in out, out


def test_parse_cache_written_by_other_parser_code_is_ignored(project):
    import os
    import time
    path = project / "shop/storage.py"
    old = time.time_ns() - 10_000_000_000
    os.utime(path, ns=(old, old))                                    # old enough to be cached
    build_inventory(project, DEFAULT_IGNORE)
    cache = project / ".flowguard/cache/inventory.json"
    data = json.loads(cache.read_text(encoding="utf-8"))
    data["files"]["shop/storage.py"]["symbols"] = ["stale_symbol"]
    data["parser"] = "written-by-an-older-flowguard"
    cache.write_text(json.dumps(data), encoding="utf-8")
    assert "save" in build_inventory(project, DEFAULT_IGNORE).py["shop/storage.py"].symbols


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


def test_explicit_test_named_product_file_is_owned_and_not_run_as_test(impact_project):
    root, data = impact_project
    write(root, "shop/test_inventory.py", "VALUE = 1\n")
    data["components"][2]["files"].append("shop/test_inventory.py")
    imp = impact_of(root, data, ["shop/test_inventory.py"])
    assert imp.direct == ["storage"]
    assert "shop/test_inventory.py" not in imp.tests
    assert "storage-proof" in imp.model_ids


def test_import_changed_code_selects_test_outside_component_binding(impact_project):
    root, data = impact_project
    write(root, "tests/test_cross.py", "from shop.storage import save\n\ndef test_cross():\n    assert save(1) == 1\n")
    data["components"][3]["tests"].append("tests/test_cross.py")
    assert "tests/test_cross.py" in impact_of(root, data, ["shop/storage.py"]).tests


def test_test_helper_selects_importing_tests_without_running_helper(impact_project):
    root, data = impact_project
    write(root, "tests/_helper.py", "VALUE = 1\n")
    write(root, "tests/test_helper_user.py", "from tests._helper import VALUE\n\ndef test_helper():\n    assert VALUE == 1\n")
    write(root, "tests/__init__.py", "")
    imp = impact_of(root, data, ["tests/_helper.py"])
    assert imp.tests == ["tests/test_helper_user.py"]
    assert imp.direct == [] and imp.dependents == []


def test_conftest_change_selects_all_tests_below_its_directory(impact_project):
    root, data = impact_project
    write(root, "tests/conftest.py", "VALUE = 1\n")
    imp = impact_of(root, data, ["tests/conftest.py"])
    assert set(imp.tests) == {"tests/test_orders.py", "tests/test_storage.py", "tests/test_api.py", "tests/test_web.py"}
    assert "tests/conftest.py" not in imp.tests


def test_model_binding_implemented_by_and_tested_by_select_bidirectionally(impact_project):
    root, data = impact_project
    path = ".flowguard/models/persistence.py"
    write(root, path, "MODEL_ID = 'storage-proof'\nCOMPONENTS = ['storage']\n"
          "IMPLEMENTED_BY = {'save': 'shop/api.py:handle'}\n"
          "TESTED_BY = {'saved_once': ['tests/test_storage.py:test_y']}\n"
          "def build_explorer():\n    pass\n")
    assert "storage-proof" in impact_of(root, data, ["shop/api.py"]).model_ids
    test_imp = impact_of(root, data, ["tests/test_storage.py"])
    assert test_imp.model_ids == ["storage-proof"] and test_imp.tests == ["tests/test_storage.py"]
    model_imp = impact_of(root, data, [path])
    assert model_imp.model_ids == ["storage-proof"] and model_imp.tests == ["tests/test_storage.py"]
    assert not model_imp.direct and not model_imp.dependents


def test_lazy_facade_selection_preserves_ancestor_initialization_without_hub(tmp_path):
    root = tmp_path
    write(root, "pkg/__init__.py", "import importlib\n_TABLE = {'pkg.a': ('A',), 'pkg.b': ('B',)}\n"
          "def __getattr__(name):\n    return importlib.import_module('pkg.a')\n")
    write(root, "pkg/a.py", "A = 1\n")
    write(root, "pkg/b.py", "B = 2\n")
    write(root, "consumer.py", "from pkg import A\n")
    write(root, "tests/test_consumer.py", "import consumer\n\ndef test_value():\n    assert consumer.A == 1\n")
    data = {"components": [
        {"id": "facade", "files": ["pkg/__init__.py"], "depends_on": ["a", "b"], "tests": []},
        {"id": "a", "files": ["pkg/a.py"], "tests": []},
        {"id": "b", "files": ["pkg/b.py"], "tests": []},
        {"id": "consumer", "files": ["consumer.py"], "depends_on": ["a"], "tests": ["tests/test_consumer.py"]},
    ]}
    assert impact_of(root, data, ["pkg/b.py"]).tests == []
    assert impact_of(root, data, ["pkg/a.py"]).tests == ["tests/test_consumer.py"]
    assert impact_of(root, data, ["pkg/__init__.py"], broad=True).tests == ["tests/test_consumer.py"]
    inv = build_inventory(root, DEFAULT_IGNORE)
    assert "pkg/a.py" in inv.file_deps["consumer.py"] and "pkg/__init__.py" not in inv.file_deps["consumer.py"]


@pytest.mark.parametrize("expression", ["pkg.B", "getattr(pkg, 'B')", "hasattr(pkg, name)", "pkg.__all__"])
def test_lazy_facade_module_attribute_and_reflection_reach_exports(tmp_path, expression):
    write(tmp_path, "pkg/__init__.py", "_TABLE = {'pkg.a': ('A',), 'pkg.b': ('B',)}\ndef __getattr__(name):\n    pass\n")
    write(tmp_path, "pkg/a.py", "A = 1\n")
    write(tmp_path, "pkg/b.py", "B = 2\n")
    write(tmp_path, "tests/test_reflect.py", f"import pkg\nname = 'B'\nvalue = {expression}\n")
    inv = build_inventory(tmp_path, DEFAULT_IGNORE)
    assert "pkg/b.py" in inv.file_deps["tests/test_reflect.py"]


def test_non_source_reference_selects_test_and_unreferenced_doc_reports_no_checks(impact_project):
    from flowguard.map.impact import render_impact
    root, data = impact_project
    write(root, "tests/test_config.py", "CONFIG = 'pyproject.toml'\n\ndef test_config():\n    assert CONFIG\n")
    write(root, "pyproject.toml", "version = '1.0'\n")
    assert impact_of(root, data, ["pyproject.toml"]).tests == ["tests/test_config.py"]
    write(root, "docs/notes.md", "notes\n")
    imp = impact_of(root, data, ["docs/notes.md"])
    assert "NO CHECKS for: docs/notes.md" in render_impact(imp)


def test_confirm_alone_is_not_reported_as_a_description_change(impact_project):
    root, data = impact_project
    data["components"][1].update(status="confirmed", fingerprint="sha256:updated")
    imp = impact_of(root, data, [".flowguard/map.json"], base="HEAD")
    assert not imp.map_review and not imp.tests and not imp.models


def test_confirmed_changed_source_needs_no_repeated_review(impact_project):
    from flowguard.map.mapfile import component_files, fingerprint
    root, data = impact_project
    write(root, "shop/storage.py", "def save(x):\n    return x + 1\n")
    inv = build_inventory(root, DEFAULT_IGNORE)
    data["components"][2].update(status="confirmed", fingerprint=fingerprint(root, component_files(data["components"][2], inv)))
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
    assert "run: npx jest web/cart.test.js" in render_impact(impact_of(root, data, ["web/cart.test.js"]))


@pytest.mark.parametrize("retire", [False, True])
def test_deleted_owner_keeps_surviving_test_and_contract_only(impact_project, retire):
    import sys

    root, data = impact_project
    write(root, "tests/test_storage.py", "from shop.storage import save\nassert save(1) == 1\n")
    git(root, "add", "-A")
    git(root, "-c", "user.email=a@b", "-c", "user.name=t", "commit", "-qm", "native test")
    (root / "shop/storage.py").unlink()
    data["components"] = [c for c in data["components"] if c["id"] != "storage"]
    if retire:
        (root / "tests/test_storage.py").unlink()
        (root / ".flowguard/models/persistence.py").unlink()
    save(root, data)
    imp = impact_of(root, data, ["shop/storage.py", ".flowguard/map.json"], base="HEAD")
    assert "storage" in imp.direct
    assert ("tests/test_storage.py" in imp.tests) is not retire
    assert ("storage-proof" in imp.model_ids) is not retire
    assert not imp.blocked
    if not retire:
        assert "shop/storage.py" not in imp.no_checks
        result = subprocess.run([sys.executable, "-c", "exec(open('tests/test_storage.py').read())"],
                                cwd=root, capture_output=True, text=True)
        assert result.returncode != 0 and "ModuleNotFoundError" in result.stderr


def test_deleted_owner_without_surviving_checks_is_visible(impact_project):
    root, data = impact_project
    owner = data["components"][2]
    owner["tests"] = owner["models"] = []
    save(root, data)
    git(root, "add", "-A")
    git(root, "-c", "user.email=a@b", "-c", "user.name=t", "commit", "-qm", "unverified owner")
    (root / "shop/storage.py").unlink()
    data["components"].remove(owner)
    save(root, data)
    imp = impact_of(root, data, ["shop/storage.py", ".flowguard/map.json"], base="HEAD")
    assert "shop/storage.py" in imp.no_checks




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


def test_npm_static_import_is_not_a_dynamic_surface(impact_project):
    root, data = impact_project
    write(root, "web/app.js", "import React from 'react';\n")
    assert not any("dynamic" in message for message in impact_of(root, data, ["web/app.js"]).uncertainty)


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


def test_impact_cli_exits_nonzero_for_unmapped_source(impact_project, capsys):
    root, data = impact_project
    write(root, "shop/unowned.py", "VALUE = 1\n")
    code, text = run(root, "impact", "shop/unowned.py", capsys=capsys)
    assert code == 1 and "UNMAPPED" in text


@pytest.mark.parametrize("selected_count", (30, 31))
def test_large_selected_scope_does_not_expand_to_the_full_suite(selected_count):
    from flowguard.map.impact import Impact, render_impact
    paths = [f"tests/test_{index:03}.py" for index in range(selected_count)]
    impact = Impact(changed=["shop/orders.py"], direct=["orders"], dependents=[],
                    unmapped=[], tests=paths, models=[], needs_review=[], total_tests=136)
    text = render_impact(impact)
    from flowguard.map.impact import run_commands
    assert run_commands(impact) == ["python -m pytest -q " + " ".join(paths)]
    assert "test_135.py" not in " ".join(run_commands(impact))
    assert "run: python -m pytest -q " + " ".join(paths) in text
    assert f"{selected_count} of 136" in text


def test_exact_schema_binding_tracks_content_and_deletion_without_broad_json_scan(impact_project):
    from flowguard.map.check import run_check
    from flowguard.map.mapfile import component_files, fingerprint, is_stale
    root, data = impact_project
    path = "schemas/request.json"
    write(root, path, '{"required": ["order_id"]}\n')
    write(root, "schemas/unregistered.json", '{}\n')
    write(root, ".flowguard/ignored.json", '{}\n')
    owner = data["components"][2]
    owner["files"] += [path, ".flowguard/ignored.json"]
    inv = build_inventory(root, DEFAULT_IGNORE)
    assert path not in inv.source  # Default inventory still scans code only.
    assert path in component_files(owner, inv)
    assert not any(f.code == "pattern_dead" and path in f.message
                   for f in run_check(root, data, inv))
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

def test_script_directory_imports_resolve_to_sibling_files(tmp_path):
    from flowguard.map.inventory import build_inventory
    write(tmp_path, "scripts/run.py", "from helper import value\nimport json\n")
    write(tmp_path, "scripts/helper.py", "value = 1\n")
    write(tmp_path, "pkg/__init__.py", "")
    write(tmp_path, "pkg/a.py", "import helper\n")
    write(tmp_path, "pkg/helper.py", "value = 2\n")
    inv = build_inventory(tmp_path, [])
    assert inv.file_deps.get("scripts/run.py") == {"scripts/helper.py"}
    assert "pkg/helper.py" not in inv.file_deps.get("pkg/a.py", set())

def test_inventory_without_bodies_still_gives_lint_its_bodies_later(tmp_path):
    import os
    import time
    write(tmp_path, "pkg/a.py", "def f(a):\n" + "    a = a + 1\n" * 10 + "    return a\n")
    past = time.time() - 60
    os.utime(tmp_path / "pkg/a.py", (past, past))          # old enough to be cached
    assert build_inventory(tmp_path, DEFAULT_IGNORE, with_bodies=False).py["pkg/a.py"].bodies == []
    assert build_inventory(tmp_path, DEFAULT_IGNORE).py["pkg/a.py"].bodies


@pytest.mark.parametrize("edit", ["comment", "docstring", "code", "untouched"])
@pytest.mark.parametrize("line_endings", ["\n", "\r\n"], ids=["lf", "crlf"])
def test_comment_only_edit_keeps_review_but_selects_no_checks(impact_project, edit, line_endings):
    from flowguard.map.impact import render_impact
    root, data = impact_project
    path = root / "shop/storage.py"
    text = path.read_text(encoding="utf-8")
    edited = {"comment": text.replace("DB = {}\n", "DB = {}  # in-memory store\n\n"),
              "docstring": '"""Order storage."""\n' + text,
              "code": text.replace("return x", "return x or None"),
              "untouched": text}[edit]
    path.write_bytes(edited.replace("\n", line_endings).encode("utf-8"))
    imp = impact_of(root, data, ["shop/storage.py"], base="HEAD", broad=True)
    assert imp.direct == ["storage"]
    if edit == "comment":
        assert imp.comment_only == ["shop/storage.py"] and "comment-only edits" in render_impact(imp)
        assert imp.dependents == [] and imp.tests == [] and imp.models == []
    else:
        assert imp.comment_only == [] and imp.dependents == ["api", "orders"]
        assert "tests/test_storage.py" in imp.tests and "orders_check" in imp.model_ids


@pytest.mark.parametrize("guard", ["TYPE_CHECKING", "t.TYPE_CHECKING"])
def test_import_sites_skip_type_checking_and_sort_by_line(tmp_path, guard):
    from flowguard.map.lint import dependency_import_sites
    write(tmp_path, "a.py", "from typing import TYPE_CHECKING\nif " + guard + ":\n"
          "    from b import X\nelse:\n    from b import Y\n\n"
          "def late():\n    pass\n    from b import Z\n    pass\n    from b import W\n")
    write(tmp_path, "b.py", "X = Y = Z = W = 1\n")
    data = {"components": [{"id": "a", "files": ["a.py"]}, {"id": "b", "files": ["b.py"]}]}
    inv = build_inventory(tmp_path, DEFAULT_IGNORE)
    sites = dependency_import_sites(tmp_path, data, inv, "a", "b")
    assert sites == ["a.py:5 from b import Y", "a.py:9 from b import Z", "a.py:11 from b import W"]
    assert inv.py["a.py"].imports >= {"b:Y", "b:Z", "b:W"}
    assert "b:X" not in inv.py["a.py"].imports


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


def test_depends_on_order_is_not_a_verification_change(impact_project):
    root, data = impact_project
    data["components"][0]["depends_on"] = ["orders", "storage"]
    save(root, data)
    git(root, "add", ".flowguard/map.json")
    git(root, "-c", "user.email=a@b", "-c", "user.name=t", "commit", "-qm", "baseline dependencies")
    data["components"][0]["depends_on"] = ["storage", "orders", "orders"]
    save(root, data)
    impact = impact_of(root, data, [".flowguard/map.json"], base="HEAD")
    assert "api" not in impact.direct
    assert "api" not in impact.map_review
    data["components"][0]["depends_on"].append("web")
    save(root, data)
    assert "api" in impact_of(root, data, [".flowguard/map.json"], base="HEAD").direct


def test_normalize_newlines_handles_crlf_and_lone_cr(tmp_path):
    from flowguard.map.common import content_digest
    mixed = tmp_path / "mixed.py"
    lf = tmp_path / "lf.py"
    mixed.write_bytes(b"a\r\nb\rc\n")
    lf.write_bytes(b"a\nb\nc\n")
    assert content_digest(mixed) == content_digest(lf)
    from flowguard.map.common import normalize_newlines
    assert normalize_newlines(mixed.read_bytes()) == lf.read_bytes()
    assert normalize_newlines(lf.read_bytes()) == lf.read_bytes()
    lf.write_bytes(b"a\nb\nchanged\n")
    assert content_digest(mixed) != content_digest(lf)


def test_scan_preserves_project_gitignore(project, capsys):
    ignore = project / ".gitignore"
    original = b"build/\r\n# project-owned rules\r\n"
    ignore.write_bytes(original)
    assert run(project, "scan", capsys=capsys)[0] == 0
    assert ignore.read_bytes() == original
    assert (project / ".flowguard/cache/.gitignore").read_text() == "*\n"


@pytest.mark.parametrize('changed,expected,tests', [
    ('child.py', {'child', 'parent'}, ['tests/test_child.py']),
    ('_shared.py', {'child', 'parent'}, []),
    ('_leaf.py', {'child', 'parent'}, []),
    ('grand.py', {'grand', 'parent'}, ['tests/test_grand.py']),
    ('parent.py', {'parent'}, ['tests/test_parent.py']),
    ('_unused.py', set(), []),
])
def test_change_selects_importers_and_ancestors_of_a_changed_model(impact_project, changed, expected, tests):
    root, data = impact_project
    for mid in ('parent', 'child', 'grand'):
        content = (f'MODEL_ID = {mid!r}\nIMPLEMENTED_BY = {{"Probe": "tests/test_{mid}.py:test_safe"}}\ndef conformance(): pass\n'
                   f'TESTED_BY = {{"safe": ["tests/test_{mid}.py:test_safe"]}}\ndef build_explorer(): pass\n')
        content += {'parent': 'import child\nimport _shared\n', 'child': 'from _shared import VALUE\n',
                    'grand': 'PARENT = "parent"\n'}[mid]
        write(root, f'.flowguard/models/{mid}.py', content)
        write(root, f'tests/test_{mid}.py', 'def test_safe(): assert True\n')
    write(root, '.flowguard/models/_shared.py', 'PARENT = None\nfrom _leaf import VALUE\n')
    write(root, '.flowguard/models/_leaf.py', 'VALUE = 1\n')
    write(root, '.flowguard/models/_unused.py', 'VALUE = 2\n')
    path = '.flowguard/models/' + changed
    impact = impact_of(root, data, [path], broad=True)
    assert set(impact.model_ids) == expected
    assert impact.tests == tests  # added importers/ancestors do not add their TESTED_BY tests
    assert not impact.direct and not impact.dependents and not impact.blocked
    assert impact.no_checks == ([path] if changed == '_unused.py' else [])


    # Reverse model imports remain selected even without the broad ancestry loop.
    direct = impact_of(root, data, [path])
    if changed in {"child.py", "_shared.py", "_leaf.py"}:
        assert {"child", "parent"} <= set(direct.model_ids)

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
        {"id": cid, "layer": "", "summary": responsibility, "responsibilities": [responsibility],
         "files": [cid + ".py"], "entrypoints": [], "state": [], "side_effects": [],
         "depends_on": dependencies, "tests": [], "models": [], "status": "draft", "fingerprint": ""}
        for cid, dependencies, responsibility in [("a", ["b", "c"], "alpha operation"),
                                                   ("b", ["c"], "bravo persistence"),
                                                   ("c", ["a"], "charlie rendering")]]
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
    debt.update({"members": ["a", "b", "c"]} if debt_style == "members" else
                {"component": "a", "contains": "a <-> b <-> c"})
    data = load(root)
    data["accepted_debts"] = [debt]
    save(root, data)
    code, out = run(root, "check", capsys=capsys)
    assert code == 0 and "INFO  dependency_cycle" in out and "accepted debt" in out


def test_change_selects_the_review_children_of_a_selected_model(impact_project):
    root, data = impact_project
    for mid, parent, imports in (("target", "system", ""), ("review", "target", "import target\n"),
                                 ("second_review", "review", "import review\n"),
                                 ("child", "target", "")):
        text = f'MODEL_ID = {mid!r}\nCOMPONENTS = []\n'
        if parent:
            text += f'PARENT = {parent!r}\n'
        text += imports + 'def build_explorer(): pass\ndef conformance(): pass\n'
        if mid == "target":
            text += 'IMPLEMENTED_BY = {"save": "shop/storage.py:save"}\n'
        write(root, f'.flowguard/models/{mid}.py', text)
    impact = impact_of(root, data, ["shop/storage.py"], broad=True)
    assert {"target", "review", "second_review"} <= set(impact.model_ids)
    assert "child" not in impact.model_ids
    assert not impact.blocked


def test_first_map_covers_finite_sources_once_within_budget(tmp_path):
    """Native new_map handles nested, ignored, test and malformed source files together."""
    from collections import Counter
    from flowguard.map.mapfile import component_files
    from flowguard.map.scan import new_map

    files = {
        "api.py": "def run(): return True\n",
        "service/core.py": "def save(): return True\n",
        "pkg/__init__.py": "",
        "pkg/nested/__init__.py": "",
        "pkg/nested/tool.py": "def tool(): return True\n",
        "broken/bad.py": "def broken(:\n",
        "skip/hidden.py": "raise RuntimeError('ignored')\n",
        "tests/test_api.py": "def test_run(): pass\n",
    }
    for relative, source in files.items():
        write(tmp_path, relative, source)
    expected = {"api.py", "service/core.py", "pkg/__init__.py", "pkg/nested/__init__.py",
                "pkg/nested/tool.py", "broken/bad.py"}
    inv = build_inventory(tmp_path, [*DEFAULT_IGNORE, "skip/**"], with_bodies=False, write_cache=False)
    assert set(inv.source) - set(inv.tests) == expected
    assert inv.tests == ["tests/test_api.py"]
    assert inv.py["broken/bad.py"].parse_error
    for limit in (1, 2):
        actual = new_map(tmp_path, inv, max_components=limit)
        components = actual["components"]
        assert 1 <= len(components) <= limit
        owned = [path for component in components for path in component_files(component, inv)]
        assert Counter(owned) == Counter(expected)
        assert "skip/hidden.py" not in owned and "tests/test_api.py" not in owned
        assert all(component["status"] == "draft" for component in components)


def test_change_selects_a_child_that_imports_its_parent_in_a_function(impact_project):
    """The documented split style imports the parent inside a function; editing the parent selects it."""
    from flowguard.map.tree import build_tree
    root, data = impact_project
    write(root, ".flowguard/models/parent.py", 'MODEL_ID = "parent"\nCOMPONENTS = ["storage"]\nLIMIT = 1\n'
          'IMPLEMENTED_BY = {"save": "shop/storage.py:save"}\ndef build_explorer(): pass\ndef conformance(): pass\n')
    write(root, ".flowguard/models/child.py", 'MODEL_ID = "child"\nPARENT = "parent"\n'
          'def _starts():\n    import parent\n    return parent.LIMIT\n'
          'def build_explorer(): pass\ndef conformance(): pass\n')
    git(root, "add", "-A")
    git(root, "-c", "user.email=a@b", "-c", "user.name=t", "commit", "-qm", "parent and child")
    path = root / ".flowguard/models/parent.py"
    original = path.read_text(encoding="utf-8")
    path.write_text(original.replace("LIMIT = 1", "LIMIT = 2"), encoding="utf-8")
    impact = impact_of(root, data, [".flowguard/models/parent.py"], base="HEAD")
    assert {"parent", "child"} <= set(impact.model_ids) and not impact.blocked
    path.write_text(original + "# only a comment\n", encoding="utf-8")
    assert impact_of(root, data, [".flowguard/models/parent.py"], base="HEAD").model_ids == []
    tree = build_tree(root, data, build_inventory(root, DEFAULT_IGNORE))
    assert (tree.nodes["child"].parent, tree.nodes["child"].parent_kind) == ("parent", "model")
    assert tree.nodes["child"].local_import_files == {".flowguard/models/parent.py"}
    assert not [f for f in tree.findings if f.code == "parent_import_mismatch"]


def test_change_selects_models_whose_anchors_the_edit_calls(tmp_path, capsys):
    """Editing a file that calls another component's anchored code selects that model and its tests."""
    import flowguard.__main__ as flowguard_cli
    from test_flowguard_target import shelf_project

    root = shelf_project(tmp_path)
    capsys.readouterr()
    path = root / "shelf/cli.py"
    original = path.read_text(encoding="utf-8")
    path.write_text(original + "X = 1\n", encoding="utf-8")
    flowguard_cli.main(["change", "--root", str(root)])
    output = capsys.readouterr().out
    assert "relies on: lending via loans:LoanService.borrow" in output, output
    assert "models to run: -" in output, output
    path.write_text(original + "# a comment only\n", encoding="utf-8")
    flowguard_cli.main(["change", "--root", str(root)])
    assert "models to run: -" in capsys.readouterr().out


def test_change_selects_the_model_of_a_flow_whose_step_changed(impact_project):
    """A flow's model protects every step: editing a step's file selects it, a comment does not."""
    root, data = impact_project
    write(root, "shop/jobs.py", "def run():\n    return 'done'\n")
    write(root, ".flowguard/models/journey.py", 'MODEL_ID = "journey"\nCOMPONENTS = ["storage"]\n'
          'IMPLEMENTED_BY = {"save": "shop/storage.py:save"}\ndef build_explorer(): pass\ndef conformance(): pass\n')
    data["components"].append({"id": "jobs", "summary": "jobs", "responsibilities": ["run jobs"], "files": ["shop/jobs.py"],
                               "entrypoints": ["shop/jobs.py:run"], "depends_on": [], "tests": [], "models": [],
                               "status": "draft", "layer": data["components"][0].get("layer", "")})
    data.setdefault("flows", []).append({"id": "chain", "summary": "store then run the job",
                                         "steps": ["storage:save", "jobs:run reads out.json"],
                                         "model": ".flowguard/models/journey.py"})
    save(root, data)
    git(root, "add", "-A")
    git(root, "-c", "user.email=a@b", "-c", "user.name=t", "commit", "-qm", "flow chain")
    from flowguard.map.impact import render_impact
    path = root / "shop/jobs.py"
    path.write_text("def run():\n    return 'finished'\n", encoding="utf-8")
    impact = impact_of(root, data, ["shop/jobs.py"], base="HEAD")
    assert "journey" in impact.model_ids, impact
    assert "flow chain: step 2 changed; model journey" in render_impact(impact)
    path.write_text("def run():\n    return 'done'\n# a comment\n", encoding="utf-8")
    assert "journey" not in impact_of(root, data, ["shop/jobs.py"], base="HEAD").model_ids


def test_flow_without_model_across_modeled_code_is_reported(tmp_path):
    """flow_unmodeled: a flow crossing a modeled component has no model of its own."""
    from flowguard.map.cli import _context
    from flowguard.map.lint import run_lint
    from test_flowguard_target import shelf_project

    root = shelf_project(tmp_path)
    data, inv = _context(root)
    found = [f for f in run_lint(root, data, inv) if f.code == "flow_unmodeled"]
    assert found and "borrow" in found[0].message and "lending" in found[0].message and found[0].level == "info"
    data["flows"][0]["model"] = ".flowguard/models/lending.py"
    assert not [f for f in run_lint(root, data, inv) if f.code == "flow_unmodeled"]


def test_lint_reports_private_names_used_across_components(tmp_path):
    """A `_private` name owned by another component is a WARN; own files, dunders and tests are not."""
    from flowguard.map.lint import run_lint
    from flowguard.map.views import render_show

    write(tmp_path, "a/__init__.py", "")
    write(tmp_path, "a/x.py", "from b.y import _helper, __version__\nimport b.z as zed\n\n"
          "def run():\n    return _helper() + zed._other()\n")
    write(tmp_path, "b/__init__.py", "")
    write(tmp_path, "b/y.py", "__version__ = '1'\n\ndef _helper():\n    return 1\n")
    write(tmp_path, "b/z.py", "from b.y import _helper\n\ndef _other():\n    return _helper()\n")
    write(tmp_path, "tests/test_x.py", "from b.y import _helper\n\ndef test_helper():\n    assert _helper() == 1\n")

    def component(cid, depends_on=()):
        return {"id": cid, "summary": cid, "responsibilities": [f"{cid} work"], "files": [f"{cid}/*.py"],
                "entrypoints": [], "tests": ["tests/test_x.py"] if cid == "a" else [], "models": [],
                "depends_on": list(depends_on), "status": "draft"}
    data = {"schema": "flowguard.map.v1", "components": [component("a", ["b"]), component("b")], "flows": []}
    write(tmp_path, ".flowguard/map.json", json.dumps(data))
    inv = build_inventory(tmp_path, DEFAULT_IGNORE)
    found = [f for f in run_lint(tmp_path, data, inv) if f.code == "private_cross_component_use"]
    assert {(f.level, f.component) for f in found} == {("warn", "a")}, found
    messages = " ".join(f.message for f in found)
    assert "_helper" in messages and "_other" in messages and "a/x.py:1" in messages, messages
    assert "__version__" not in messages and "b/z.py" not in messages and "tests/" not in messages
    debt = {"code": "private_cross_component_use", "component": "a", "contains": "_helper", "reason": "migration"}
    found = [f for f in run_lint(tmp_path, {**data, "accepted_debts": [debt]}, inv)
             if f.code == "private_cross_component_use"]
    assert any(f.level == "info" and "_helper" in f.message for f in found), found
    shown = render_show(tmp_path, data, inv, component="a", detail=False, budget=8000)
    assert "_helper (private)" in next(line for line in shown.splitlines() if "uses b:" in line), shown


def test_check_and_change_report_duplicate_owner(tmp_path, capsys):
    """Two components claiming one state is an error in map check, change, read and system, once each."""
    import flowguard.__main__ as flowguard_cli
    from test_flowguard_target import shelf_project

    root = shelf_project(tmp_path)
    data = load(root)
    next(c for c in data["components"] if c["id"] == "catalog")["state"].append("current loans")
    save(root, data)
    capsys.readouterr()

    def run(*args):
        code = flowguard_cli.main([*args, "--root", str(root)])
        return code, capsys.readouterr().out

    code, out = run("map", "check")
    assert code == 1 and out.count("duplicate_owner") == 1 and "ERROR duplicate_owner" in out, out
    assert "duplicate_owner" in run("change")[1]
    assert "architecture: 1 error(s)" in run("read")[1].splitlines()[0]
    assert run("map", "models", "system")[1].count("duplicate_owner catalog") == 1
    data["accepted_debts"] = [{"code": "duplicate_owner", "component": "catalog", "contains": "current loans",
                               "reason": "the catalog mirrors loans until the split"}]
    save(root, data)
    code, out = run("map", "check")
    assert code == 0 and "INFO  duplicate_owner" in out, out


def test_change_lists_unexplained_functions_of_changed_files(tmp_path, capsys):
    """A real edit lists the edited file's unexplained entrypoints; the exit code does not change."""
    import flowguard.__main__ as flowguard_cli
    from test_flowguard_target import shelf_project

    root = shelf_project(tmp_path)
    capsys.readouterr()
    path = root / "shelf/members.py"
    original = path.read_text(encoding="utf-8")
    path.write_text(original + "\nLIMIT_NOTE = 'members may borrow up to the limit'\n", encoding="utf-8")
    code = flowguard_cli.main(["change", "--root", str(root)])
    output = capsys.readouterr().out
    assert "UNEXPLAINED members: shelf/members.py:Members.may_borrow (entrypoint)" in output, output
    path.write_text(original + "# a comment only\n", encoding="utf-8")
    comment_code = flowguard_cli.main(["change", "--root", str(root)])
    assert "UNEXPLAINED" not in capsys.readouterr().out
    assert code == comment_code


def test_load_map_reads_a_bom_map_and_rejects_missing_or_invalid_ones(tmp_path):
    from flowguard.map.mapfile import MapError, load_map

    with pytest.raises(MapError, match="no map"):
        load_map(tmp_path)
    write(tmp_path, ".flowguard/map.json", "{not json")
    with pytest.raises(MapError, match="not valid JSON"):
        load_map(tmp_path)
    (tmp_path / ".flowguard/map.json").write_text('﻿{"schema": "flowguard.map.v1", "components": []}', encoding="utf-8")
    assert load_map(tmp_path)["components"] == []


def test_missing_map_points_at_scan_and_the_first_map_guide(tmp_path, capsys):
    from flowguard.__main__ import main

    write(tmp_path, "app.py", "def run():\n    return True\n")
    assert main(["read", "--root", str(tmp_path)]) == 2
    error = capsys.readouterr().err
    assert "run python -m flowguard map scan first" in error and "references/first_map.md" in error, error


def test_scan_hints_a_split_and_discover_says_when_nothing_is_found(tmp_path, capsys):
    root = tmp_path / "lib"
    for index in range(6):
        write(root, f"pkg/part{index}.py", f"def value{index}():\n    return {index}\n")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    code, out = run(root, "scan", capsys=capsys)
    assert code == 0 and "hint: draft pkg holds 6 files of one directory; split it by responsibility " \
        "(python -m flowguard map digest pkg lists each file's API)" in out, out
    code, out = run(root, "discover", capsys=capsys)
    assert code == 0 and "no entrypoints, effects or state writers found (a library without commands is normal; " \
        "list its public API in entrypoints by hand)" in out, out


def test_lint_notes_compound_responsibilities(project, capsys):
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
    assert all("write one present-tense duty per entry (references/first_map.md)" in f["message"] for f in notes)
    data["components"][0]["responsibilities"] = ["accept order requests"]
    data["components"][1]["responsibilities"] = ["place an order once"]
    save(project, data)
    assert "responsibility_compound" not in codes(project, "lint", capsys)
    data["components"][0]["responsibilities"] = [long_duty]
    save(project, data)
    assert cli.main(["--root", str(project), "lint"]) == before


def test_retired_table_is_the_only_owner():
    import re

    from flowguard.map.retired import RETIRED

    root = Path(__file__).resolve().parents[1]
    literal = re.compile(r"DESIGN_ONLY|ledger\.json|(?<![A-Za-z])project\.toml|owner-current")
    owners = sorted({path.relative_to(root).as_posix() for path in (root / "flowguard").rglob("*.py")
                     if literal.search(path.read_text(encoding="utf-8"))})
    assert owners == ["flowguard/map/retired.py"]
    kinds = {entry.kind for entry in RETIRED}
    assert {"path", "literal", "flag", "project_marker", "public_name"} <= kinds
    tests_text = "\n".join(path.read_text(encoding="utf-8") for path in (root / "tests").glob("test_*.py"))
    for entry in RETIRED:
        assert entry.code in tests_text, entry


def test_map_check_binding_codes(tmp_path):
    """A declared dependency with no evidence is dep_unused; one used only through an injected object is not."""
    from flowguard.map.check import run_check

    write(tmp_path, "core.py", "class Store:\n    def save(self):\n        return 1\n")
    write(tmp_path, "api.py", "class Service:\n    def __init__(self, store):\n        self.store = store\n\n"
          "    def run(self):\n        return self.store.save()\n")
    write(tmp_path, "app.py", "from api import Service\nfrom core import Store\n\n\ndef main():\n    return Service(Store()).run()\n")

    def component(cid, layer, depends_on):
        return {"id": cid, "layer": layer, "summary": cid, "responsibilities": [cid + " duty"], "files": [cid + ".py"],
                "entrypoints": [], "state": [], "side_effects": [], "depends_on": depends_on, "tests": [], "models": [],
                "status": "draft", "fingerprint": ""}
    data = {"schema": "flowguard.map.v1", "project": "binding", "layers": ["interface", "core"], "ignore": [],
            "components": [component("app", "interface", ["api", "core"]), component("api", "interface", ["core"]),
                           component("core", "core", [])], "flows": [], "accepted_debts": []}

    def unused():
        inv = build_inventory(tmp_path, DEFAULT_IGNORE, write_cache=False)
        return [f.component for f in run_check(tmp_path, data, inv) if f.code == "dep_unused"]
    assert unused() == []                       # api reaches core only through the injected store
    write(tmp_path, "app.py", "from api import Service\nfrom core import Store\n\n\ndef main():\n    return 1\n")
    assert unused() == ["api"]                  # nothing passes a Store any more: the declared edge has no evidence


def _release_project(root, *, legacy=False):
    from hashlib import sha256
    from flowguard.map.common import SCHEMA, content_digest
    from flowguard.map.mapfile import fingerprint
    files = {"pkg/__init__.py": '\"\"\"__version__ = "example" note.\"\"\"\n__version__: str = "1.0.0"\nX = 1\n',
             "pyproject.toml": '[project]\nname = "app"\nversion = "1.0.0"\n[tool.x]\nversion = "stable"\n', "VERSION": "1.0.0\n"}
    for path, text in files.items():
        write(root, path, text)
    comp = {"id": "app", "layer": "app", "summary": "A versioned package", "responsibilities": ["Declare package values"],
            "files": list(files), "status": "confirmed", "depends_on": [], "tests": [], "models": []}
    comp["fingerprint"] = fingerprint(root, list(files))
    if legacy:
        old = sha256()
        for path in sorted(files):
            old.update(f"{path}\0{content_digest(root / path)}\n".encode())
        comp["fingerprint"] = "sha256:" + old.hexdigest()
    data = {"schema": SCHEMA, "layers": ["app"], "components": [comp], "fingerprint_format": 1 if legacy else 2}
    write(root, ".flowguard/map.json", json.dumps(data))
    return data, comp


@pytest.mark.parametrize("filename", ["pkg/__init__.py", "pyproject.toml", "VERSION"])
@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_version_only_bump_keeps_components_current(tmp_path, filename, newline):
    from flowguard.map.mapfile import component_state
    from flowguard.map.check import run_check
    data, comp = _release_project(tmp_path)
    path = tmp_path / filename
    path.write_bytes(path.read_text().replace("1.0.0", "1.0.1").replace("\n", newline).encode())
    inv = build_inventory(tmp_path, [])
    assert component_state(tmp_path, comp, inv, data) == "current"
    assert not [f for f in run_check(tmp_path, data, inv, strict=True) if f.level == "error"]


@pytest.mark.parametrize("filename,old,new", [("pkg/__init__.py", "X = 1", "X = 2"),
    ("pyproject.toml", '"app"', '"other"'), ("pyproject.toml", '"stable"', '"changed"')])
def test_non_version_edit_in_version_file_is_stale(tmp_path, filename, old, new):
    from flowguard.map.mapfile import component_state
    data, comp = _release_project(tmp_path)
    path = tmp_path / filename
    path.write_text(path.read_text().replace(old, new))
    assert component_state(tmp_path, comp, build_inventory(tmp_path, []), data) == "stale"


def test_format1_map_migrates_once(tmp_path):
    from flowguard.map.check import run_check
    from flowguard.map.mapfile import component_state, load_map
    data, comp = _release_project(tmp_path, legacy=True)
    inv = build_inventory(tmp_path, [])
    assert component_state(tmp_path, comp, inv, data) == "migrate"
    findings = [f for f in run_check(tmp_path, data, inv, strict=True) if f.code == "fingerprint_migrate"]
    assert len(findings) == 1 and findings[0].level == "error"
    assert cli.main(["confirm", "app", "--root", str(tmp_path)]) == 0
    current = load_map(tmp_path)
    assert current["fingerprint_format"] == 2
    assert component_state(tmp_path, current["components"][0], inv, current) == "current"


def test_format2_map_with_format1_value_is_stale(tmp_path):
    from flowguard.map.mapfile import component_state
    data, comp = _release_project(tmp_path, legacy=True)
    data["fingerprint_format"] = 2
    assert component_state(tmp_path, comp, build_inventory(tmp_path, []), data) == "stale"


def test_fingerprint_format_3_is_rejected(tmp_path):
    from flowguard.map.mapfile import validate_map
    data, _ = _release_project(tmp_path)
    data["fingerprint_format"] = 3
    assert "fingerprint_format 3 is newer than this FlowGuard (2); install a newer FlowGuard" in validate_map(data)
    for invalid in (0, "2", True):
        data["fingerprint_format"] = invalid
        assert "fingerprint_format must be 1 or 2" in validate_map(data)


def test_docstring_version_text_is_not_a_declaration(tmp_path):
    from flowguard.map.mapfile import component_state
    data, comp = _release_project(tmp_path)
    p = tmp_path / "pkg/__init__.py"
    p.write_text(p.read_text().replace('str = "1.0.0"', 'str = "1.0.1"'))
    inv = build_inventory(tmp_path, [])
    assert component_state(tmp_path, comp, inv, data) == "current"
    p.write_text(p.read_text().replace('"example"', '"changed documentation"'))
    assert component_state(tmp_path, comp, inv, data) == "stale"


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_model_contract_parsed_once_per_check(tmp_path, monkeypatch, newline):
    import ast
    from flowguard.map import mapfile
    from flowguard.map.check import run_check
    data, comp = _release_project(tmp_path)
    model = tmp_path / ".flowguard/models/one.py"
    write(tmp_path, str(model.relative_to(tmp_path)), "MODEL_ID='one'\nPARENT='app'\ndef build_explorer(): pass\n")
    model.write_bytes(model.read_text().replace("\n", newline).encode())
    comp["models"] = [".flowguard/models/one.py"]
    from flowguard.map.common import normalize_newlines
    raw, calls, original = model.read_bytes(), [], ast.parse
    def counted(source, *args, **kwargs):
        if normalize_newlines(source.encode("utf-8") if isinstance(source, str) else source) == normalize_newlines(raw):
            calls.append(True)
        return original(source, *args, **kwargs)
    monkeypatch.setattr(ast, "parse", counted)
    run_check(tmp_path, data, build_inventory(tmp_path, mapfile.ignore_patterns(data)))
    assert len(calls) == 1
    first = mapfile.read_model_contract(model)
    first["functions"].clear()
    assert mapfile.read_model_contract(model)["functions"] == ["build_explorer"]
    assert len(calls) == 1


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


def test_map_check_names_model_edited_outside_target(tmp_path):
    from flowguard.map.check import run_check
    from flowguard.map.common import content_digest
    from flowguard.map.inventory import build_inventory
    directory = tmp_path / ".flowguard/models"
    directory.mkdir(parents=True)
    path = directory / "one.py"
    path.write_text('MODEL_ID = "one"\n')
    data = {"schema": "flowguard.map.v1", "components": [], "model_digests": {".flowguard/models/one.py": content_digest(path)}}
    inv = build_inventory(tmp_path, [])
    def guards(strict=False):
        return [f for f in run_check(tmp_path, data, inv, strict=strict) if f.code == "model_edited_outside_target"]
    assert guards() == []
    from flowguard.map.mapfile import fingerprint
    (tmp_path / "app.py").write_text("def run(): return 1\n")
    pointer = fingerprint(tmp_path, ["app.py"])
    path.write_text(path.read_text() + "# modified\n")
    assert fingerprint(tmp_path, ["app.py"]) == pointer  # the model digest, not the code pointer, changes

    assert len(guards()) == 1 and guards()[0].level == "warn"
    assert len(guards(True)) == 1 and guards(True)[0].level == "error"
    del data["model_digests"]
    assert guards() == []


@pytest.mark.parametrize("roots", [[""], [".."], ["a/../b"], ["/absolute"], ["a\\b"], [42], "library"])
def test_import_roots_are_validated(tmp_path, roots):
    from flowguard.map.mapfile import validate_map
    data = {"schema": "flowguard.map.v1", "components": [], "import_roots": roots}
    assert any("import_roots" in error for error in validate_map(data))


def test_missing_import_root_is_a_warning(tmp_path):
    from flowguard.map.check import run_check
    data = {"schema": "flowguard.map.v1", "components": [], "import_roots": ["library"]}
    inv = build_inventory(tmp_path, [], write_cache=False, import_roots=("library",))
    findings = [f for f in run_check(tmp_path, data, inv, strict=True) if f.code == "import_root_missing"]
    assert len(findings) == 1 and findings[0].level == "warn"
    (tmp_path / "library").mkdir()
    assert not [f for f in run_check(tmp_path, data, inv) if f.code == "import_root_missing"]

def function_fixture():
    import runpy,sys
    base=Path(__file__).parents[1]/'.flowguard'
    directory=base/'target/models' if (base/'target/models/_function_fixture.py').exists() else base/'models'
    return runpy.run_path(str(directory/'_function_fixture.py'))


def test_owned_edit_does_not_select_composing_parent(tmp_path):
    helper=function_fixture()
    for case in ('body','helper'):
        root=tmp_path/case;root.mkdir()
        impact=helper['native_case'](root,case)
        assert impact.model_ids==['child']
        assert 'parent' not in impact.model_ids


def test_module_binding_change_selects_importer_functions(tmp_path):
    from flowguard.map.impact import render_impact
    impact=function_fixture()['native_case'](tmp_path,'binding')
    assert 'importer' in impact.model_ids
    assert 'api.py:call' in impact.changed_functions
    assert 'UNCERTAIN: core.py' not in render_impact(impact)


def test_removed_function_is_uncertain(tmp_path):
    from flowguard.map.impact import render_impact
    impact=function_fixture()['native_case'](tmp_path,'removed')
    assert impact.model_ids and impact.uncertain_files['core.py']
    assert 'UNCERTAIN: core.py:' in render_impact(impact)


def test_no_git_uses_stale_components(tmp_path):
    from flowguard.map.impact import render_impact
    impact=function_fixture()['native_case'](tmp_path,'no_git')
    assert impact.tests==['tests/test_core.py']
    assert impact.changed==['core.py']
    assert 'NO GIT: changed files = the files of 1 component(s)' in render_impact(impact)
    assert 'a test file edited alone is not seen: run it by path' in render_impact(impact)


def _signature_fixture(tmp_path, source, before, after):
    helper=function_fixture();data=helper['fixture'](tmp_path)
    helper['write'](tmp_path,'core.py',source)
    helper['write'](tmp_path,'.flowguard/models/constructor.py','MODEL_ID="constructor"\nPARENT="api"\nIMPLEMENTED_BY={"Construct":"api.py:call"}\ndef build_explorer(): pass\n')
    git(tmp_path,'add','.')
    git(tmp_path,'-c','user.name=FlowGuard','-c','user.email=model@example.invalid','commit','-qm','signature baseline')
    helper['write'](tmp_path,'core.py',source.replace(before,after))
    return impact_of(tmp_path,data,['core.py'],base='HEAD')


def test_signature_change_selects_callers_models(tmp_path):
    h=function_fixture();data=h['fixture'](tmp_path)
    h['write'](tmp_path,'api.py','from core import own\ndef call(): return own()\n')
    git(tmp_path,'add','.')
    git(tmp_path,'-c','user.name=FlowGuard','-c','user.email=model@example.invalid','commit','-qm','caller baseline')
    path=tmp_path/'core.py';path.write_text(path.read_text().replace('def own():','def own(value=0):'))
    impact=impact_of(tmp_path,data,['core.py'],base='HEAD')
    assert {'child','importer'}<=set(impact.model_ids)
    assert 'api.py:call' in impact.changed_functions


def test_dataclass_field_added_selects_constructors_models(tmp_path):
    h=function_fixture();data=h['fixture'](tmp_path)
    h['write'](tmp_path,'core.py','from dataclasses import dataclass\n@dataclass\nclass Value:\n    x:int=0\n')
    h['write'](tmp_path,'api.py','from core import Value\ndef call(): return Value()\n')
    git(tmp_path,'add','.')
    git(tmp_path,'-c','user.name=FlowGuard','-c','user.email=model@example.invalid','commit','-qm','dataclass baseline')
    path=tmp_path/'core.py';path.write_text(path.read_text()+'    y:int=0\n')
    impact=impact_of(tmp_path,data,['core.py'],base='HEAD')
    assert 'importer' in impact.model_ids and 'api.py:call' in impact.changed_functions


def test_class_anchor_covers_methods(tmp_path):
    h=function_fixture();data=h['fixture'](tmp_path)
    h['write'](tmp_path,'core.py','class Service:\n    def work(self): return 1\n')
    h['write'](tmp_path,'.flowguard/models/child.py','MODEL_ID="child"\nPARENT="logic"\nIMPLEMENTED_BY={"Run":"core.py:Service"}\ndef build_explorer(): pass\n')
    git(tmp_path,'add','.')
    git(tmp_path,'-c','user.name=FlowGuard','-c','user.email=model@example.invalid','commit','-qm','class baseline')
    path=tmp_path/'core.py';path.write_text(path.read_text().replace('return 1','return 2'))
    impact=impact_of(tmp_path,data,['core.py'],base='HEAD')
    assert impact.model_ids==['child'] and 'core.py:Service.work' in impact.changed_functions


def _select_test_fixture(tmp_path):
    from flowguard.map.tree import build_tree
    h=function_fixture();data=h['fixture'](tmp_path)
    path=tmp_path/'core.py';path.write_text(path.read_text().replace('def other(): return 2','def other(): return own()+1'))
    h['write'](tmp_path,'tests/test_half.py','from core import own\ndef test_one(): assert own()\ndef test_two(): pass\n')
    inv=build_inventory(tmp_path,DEFAULT_IGNORE,write_cache=False)
    return data,inv,build_tree(tmp_path,data,inv)


def test_parametrized_anchor_selects_its_case_only(tmp_path):
    from flowguard.map.impact import select_tests,Impact,run_commands
    data,inv,tree=_select_test_fixture(tmp_path)
    path=tmp_path/'tests/test_core.py'
    path.write_text('import pytest\n@pytest.mark.parametrize("x",[1,2],ids=["one","two"])\ndef test_bound(x): assert x\ndef test_noop(): pass\ndef test_last(): pass\n')
    tree.nodes['child'].contract['TESTED_BY']={'safe':['tests/test_core.py:test_bound[one]']}
    result=select_tests(tmp_path,data,inv,tree,{'child'},set())
    assert result['nodes']=={'tests/test_core.py':['test_bound[one]']}
    impact=Impact([],[],[],[],['tests/test_core.py'],[],[],test_functions=result['nodes'])
    assert 'tests/test_core.py::test_bound[one]' in run_commands(impact)[0]


def test_test_calling_through_same_file_helper_is_selected(tmp_path):
    from flowguard.map.impact import select_tests
    data,inv,tree=_select_test_fixture(tmp_path)
    result=select_tests(tmp_path,data,inv,tree,{'child'},{'core.py#own'})
    assert {'test_bound','test_call','test_help'}<=set(result['nodes']['tests/test_core.py'])
    assert 'test_indirect' not in result['nodes']['tests/test_core.py']


def test_half_selected_file_runs_whole(tmp_path):
    from flowguard.map.impact import select_tests
    data,inv,tree=_select_test_fixture(tmp_path)
    result=select_tests(tmp_path,data,inv,tree,set(),{'core.py#own'})
    assert 'tests/test_half.py' in result['whole_files']
    assert 'tests/test_core.py' not in result['whole_files']


def test_cli_test_reaching_through_main_is_counted_as_also_reached(tmp_path):
    from flowguard.map.impact import select_tests
    data,inv,tree=_select_test_fixture(tmp_path)
    result=select_tests(tmp_path,data,inv,tree,set(),{'core.py#own'})
    assert result['also_reached']==['2 test functions call core.py:own only through other functions (python -m flowguard change --broad)']


def test_broad_equals_head_selection(tmp_path):
    from flowguard.map.impact import compute_impact,_broad_impact
    h=function_fixture();data=h['fixture'](tmp_path)
    path=tmp_path/'core.py';path.write_text(path.read_text().replace('return helper()+VALUE','return helper()+VALUE+1'))
    inv=build_inventory(tmp_path,DEFAULT_IGNORE,write_cache=False)
    actual=compute_impact(tmp_path,data,inv,['core.py'],base='HEAD',broad=True)
    old=_broad_impact(tmp_path,data,inv,['core.py'],base='HEAD',broad=True)
    assert actual.to_dict()==old.to_dict()


def test_function_digests_separate_nested_and_module_changes():
    from flowguard.map.inventory import function_digests
    source='VALUE=1\nclass C:\n    field=1\n    def method(self):\n        def inner(): return 1\n        return inner()\n'
    before=function_digests(source)
    nested=function_digests(source.replace('inner(): return 1','inner(): return 2'))
    assert before['functions']['C.method']==nested['functions']['C.method']
    assert before['functions']['C.method.inner']!=nested['functions']['C.method.inner']
    assert before['classes']==nested['classes']
    assert function_digests(source.replace('field=1','field=2'))['classes']!=before['classes']
    assert function_digests(source.replace('VALUE=1','VALUE=2'))['bindings']!=before['bindings']


def test_find_owners_edit_selects_its_models_and_test_functions(tmp_path):
    """The real repository's parser and model tree agree on the actual view edit."""
    from flowguard.map.impact import compute_impact, render_impact
    origin=Path(__file__).parents[1]
    paths=subprocess.check_output(['git','-C',str(origin),'ls-files','-co','--exclude-standard','-z']).decode().split('\0')
    for relative in set(filter(None,paths)):
        source=origin/relative
        if source.is_file():
            destination=tmp_path/relative;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,destination)
    git(tmp_path,'init','-q');git(tmp_path,'add','.')
    git(tmp_path,'-c','user.name=FlowGuard','-c','user.email=model@example.invalid','commit','-qm','candidate baseline')
    path=tmp_path/'flowguard/map/views.py';path.write_text(path.read_text().replace('    return scored[:limit]','    scored = list(scored)\n    return scored[:limit]'))
    data=load(tmp_path);inv=build_inventory(tmp_path,DEFAULT_IGNORE,write_cache=False)
    result=compute_impact(tmp_path,data,inv,['flowguard/map/views.py'],base='HEAD')
    assert set(result.model_ids)=={'read_find','read_view'}
    assert result.tests==['tests/test_map_views.py']
    assert result.test_functions['tests/test_map_views.py']
    assert 'Find is flowguard/map/views.py:find_'+'owners' in render_impact(result)


def test_model_edit_keeps_bound_test_function_selection(tmp_path):
    helper=function_fixture();data=helper['fixture'](tmp_path)
    path=tmp_path/'.flowguard/models/child.py'
    path.write_text(path.read_text()+'\nREVISION=2\n')
    result=impact_of(tmp_path,data,['.flowguard/models/child.py'],base='HEAD')
    assert result.tests==['tests/test_core.py']
    assert result.test_functions=={'tests/test_core.py':['test_bound']}
    assert result.selected_test_functions==1
    assert not result.whole_test_files
