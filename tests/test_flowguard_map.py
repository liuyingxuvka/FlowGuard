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
    if surface == "lazy":
        assert not any("declared but unverified" in message and message.startswith("api") for message in imp.uncertainty)
    else:
        assert any(f"{expected} -> orders: declared but unverified" in message for message in imp.uncertainty)


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
    if change in {"delete", "rename", "mapping"}:
        assert {"tests/test_orders.py", "tests/test_api.py"} <= set(imp.tests)
        assert "orders" in imp.model_ids
    else:
        assert imp.direct == [] and imp.dependents == []
        assert imp.tests == (["tests/test_orders.py"] if change == "test" else [])
        expected_models = {"contract": ["storage-proof"], "nested": ["orders"], "helper": ["orders"],
                           "runner": ["orders"], "test": []}
        assert imp.model_ids == expected_models[change]
    assert "tests/test_web.py" not in imp.tests
    assert " models model" not in render_impact(imp)
    if change == "mapping":
        assert {"new-storage-proof", "storage-proof"} <= set(imp.model_ids)
    elif change not in {"nested", "helper", "runner", "test"}:
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
    assert impact_of(root, data, ["pkg/__init__.py"]).tests == ["tests/test_consumer.py"]
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


@pytest.mark.parametrize("registered", [False, True])
def test_old_runner_requires_current_registration(impact_project, registered):
    root, data = impact_project
    owner = data["components"][1]
    path = owner["models"][0]
    data["components"].remove(owner)
    if registered:
        data["components"][0]["models"] = [path]
    save(root, data)
    imp = impact_of(root, data, [".flowguard/map.json"], base="HEAD")
    assert (path in imp.models) is registered
    assert any(path in item for item in imp.blocked) is not registered


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
    command = next(line for line in text.splitlines() if line.startswith("run:"))
    assert command == "run: python -m pytest -q " + " ".join(paths)
    assert "test_135.py" not in command
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
    imp = impact_of(root, data, ["shop/storage.py"], base="HEAD")
    assert imp.direct == ["storage"]
    if edit == "comment":
        assert imp.comment_only == ["shop/storage.py"] and "comment-only edits" in render_impact(imp)
        assert imp.dependents == [] and imp.tests == [] and imp.models == []
    else:
        assert imp.comment_only == [] and imp.dependents == ["api", "orders"]
        assert "tests/test_storage.py" in imp.tests and "orders" in imp.model_ids


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
