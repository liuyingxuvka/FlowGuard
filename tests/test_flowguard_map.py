"""Tests for flowguard.map: scan, check, lint, impact, find, show, digest, confirm, cache."""

from __future__ import annotations

import json
import subprocess
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


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    root = tmp_path / "shop"
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


@pytest.fixture()
def impact_project(project, capsys):
    run(project, "scan", capsys=capsys)
    data = fill(project)
    data["components"][0]["tests"] = ["tests/test_api.py"]
    data["components"][1]["models"] = [".flowguard/verification/owners/orders/run_checks.py"]
    data["components"][2]["models"] = [".flowguard/models/persistence.py"]
    write(project, "tests/test_api.py", "def test_api():\n    assert True\n")
    write(project, "tests/test_web.py", "def test_web():\n    assert True\n")
    data["components"][3]["tests"] = ["tests/test_web.py"]
    write(project, ".flowguard/verification/owners/orders/run_checks.py", "raise SystemExit(0)\n")
    write(project, ".flowguard/models/owners/orders/model.py", "VALUE = True\n")
    write(project, ".flowguard/models/owners/orders/helper.py", "VALUE = True\n")
    write(project, ".flowguard/models/persistence.py", "MODEL_ID = 'storage-proof'\nCOMPONENTS = ['storage']\ndef build_explorer():\n    pass\n")
    save(project, data)
    git(project, "add", "-A")
    git(project, "-c", "user.email=a@b", "-c", "user.name=t", "commit", "-qm", "map with checks")
    return project, data


def impact_of(root, data, changed, **kwargs):
    from flowguard.map.impact import compute_impact
    return compute_impact(root, data, build_inventory(root, DEFAULT_IGNORE), changed, **kwargs)


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
    assert any(f"{expected} -> orders: declared but unverified" in message for message in imp.uncertainty)
    assert any("unresolved" in message for message in imp.uncertainty)


@pytest.mark.parametrize("change", ["delete", "rename", "contract", "nested", "helper", "runner", "test", "mapping"])
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
        write(root, ".flowguard/models/new_storage.py", "MODEL_ID = 'new-storage-proof'\ndef build_explorer():\n    pass\n")
        data["components"][2]["models"] = [".flowguard/models/new_storage.py"]
        save(root, data)
        changed = [".flowguard/map.json"]
    else:
        changed = [{"contract": ".flowguard/models/persistence.py", "nested": ".flowguard/models/owners/orders/model.py",
                    "helper": ".flowguard/models/owners/orders/helper.py", "runner": ".flowguard/verification/owners/orders/run_checks.py",
                    "test": "tests/test_orders.py"}[change]]
    imp = impact_of(root, data, changed, base="HEAD")
    assert "tests/test_orders.py" in imp.tests and "tests/test_api.py" in imp.tests
    assert "tests/test_web.py" not in imp.tests
    assert ".flowguard/verification/owners/orders/run_checks.py" in imp.models
    assert "orders" in imp.model_ids and " models model" not in render_impact(imp)
    if change == "mapping":
        assert "new-storage-proof" in imp.model_ids and "storage-proof" not in imp.model_ids
    elif change not in {"nested", "helper", "runner", "test"}:
        assert "storage-proof" in imp.model_ids
    assert not imp.blocked


def test_impact_shared_test_binding_and_unknown_helper(impact_project):
    root, data = impact_project
    data["components"][2]["tests"].append("tests/test_orders.py")
    imp = impact_of(root, data, ["tests/test_orders.py"])
    assert imp.direct == ["orders", "storage"]
    assert set(imp.model_ids) == {"orders", "storage-proof"}
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
    assert "storage-proof" not in render_impact(imp).split("run: python -m flowguard.map models")[-1]
