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
    assert "dependents: orders" in out
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
    lf = fingerprint(project, ["shop/storage.py"])
    path = project / "shop/storage.py"
    path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    assert fingerprint(project, ["shop/storage.py"]) == lf
