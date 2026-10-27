"""Tests grouped by their model or native component."""
from __future__ import annotations

import pytest, os, json
from pathlib import Path
from _fg_helpers import map_inventory421_pytest as pytest, map_inventory421_os as os, map_inventory421_json as json, map_inventory421_Path as Path

@pytest.mark.parametrize("invalid", ["never-existed", "malformed", "duplicate", "no-base"])
def test_missing_model_without_unambiguous_base_contract_stays_blocked(retired_model_project, invalid):
    import pytest, os, json
    from pathlib import Path
    from _fg_helpers import map_inventory421_pytest as pytest, map_inventory421_os as os, map_inventory421_json as json, map_inventory421_Path as Path
    from _fg_helpers import map_write as write, map_impact_of as impact_of, map_git as git
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


@pytest.mark.parametrize("surface", ["lazy", "alias"])
def test_impact_declared_edges_bridge_unsupported_imports(impact_project, surface):
    import pytest, os, json
    from pathlib import Path
    from _fg_helpers import map_inventory421_pytest as pytest, map_inventory421_os as os, map_inventory421_json as json, map_inventory421_Path as Path
    from _fg_helpers import map_write as write, map_impact_of as impact_of
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


def test_impact_summary_only_map_change_does_not_select_checks(impact_project):
    import pytest, os, json
    from pathlib import Path
    from _fg_helpers import map_inventory421_pytest as pytest, map_inventory421_os as os, map_inventory421_json as json, map_inventory421_Path as Path
    from _fg_helpers import map_save as save, map_impact_of as impact_of
    root, data = impact_project
    data["components"][1]["summary"] = "Clarified order rules"
    save(root, data)
    imp = impact_of(root, data, [".flowguard/map.json"], base="HEAD")
    assert imp.map_review == ["orders"]
    assert not imp.tests and not imp.models and not imp.blocked


def test_impact_static_parenthesized_import_is_not_dynamic(impact_project):
    import pytest, os, json
    from pathlib import Path
    from _fg_helpers import map_inventory421_pytest as pytest, map_inventory421_os as os, map_inventory421_json as json, map_inventory421_Path as Path
    from _fg_helpers import map_write as write, map_impact_of as impact_of
    root, data = impact_project
    write(root, "shop/api.py", "from shop.orders import (\n    place_order,\n)\n")
    imp = impact_of(root, data, ["shop/orders.py"])
    assert "api" in imp.dependents
    assert not any("shop/api.py: dynamic" in message for message in imp.uncertainty)


def test_non_ascii_file_names_are_inventoried_and_fingerprinted(project):
    import pytest, os, json
    from pathlib import Path
    from _fg_helpers import map_inventory421_pytest as pytest, map_inventory421_os as os, map_inventory421_json as json, map_inventory421_Path as Path
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    from _fg_helpers import map_write as write, map_git as git
    write(project, "shop/工具.py", "def 帮助():\n    return 1\n")
    git(project, "add", "-A")
    inv = build_inventory(project, DEFAULT_IGNORE)
    assert "shop/工具.py" in inv.source            # git C-quotes this name without -z


def test_explicit_test_named_product_file_is_owned_and_not_run_as_test(impact_project):
    import pytest, os, json
    from pathlib import Path
    from _fg_helpers import map_inventory421_pytest as pytest, map_inventory421_os as os, map_inventory421_json as json, map_inventory421_Path as Path
    from _fg_helpers import map_write as write, map_impact_of as impact_of
    root, data = impact_project
    write(root, "shop/test_inventory.py", "VALUE = 1\n")
    data["components"][2]["files"].append("shop/test_inventory.py")
    imp = impact_of(root, data, ["shop/test_inventory.py"])
    assert imp.direct == ["storage"]
    assert "shop/test_inventory.py" not in imp.tests
    assert "storage-proof" in imp.model_ids


def test_import_changed_code_selects_test_outside_component_binding(impact_project):
    import pytest, os, json
    from pathlib import Path
    from _fg_helpers import map_inventory421_pytest as pytest, map_inventory421_os as os, map_inventory421_json as json, map_inventory421_Path as Path
    from _fg_helpers import map_write as write, map_impact_of as impact_of
    root, data = impact_project
    write(root, "tests/test_cross.py", "from shop.storage import save\n\ndef test_cross():\n    assert save(1) == 1\n")
    data["components"][3]["tests"].append("tests/test_cross.py")
    assert "tests/test_cross.py" in impact_of(root, data, ["shop/storage.py"]).tests


def test_test_helper_selects_importing_tests_without_running_helper(impact_project):
    import pytest, os, json
    from pathlib import Path
    from _fg_helpers import map_inventory421_pytest as pytest, map_inventory421_os as os, map_inventory421_json as json, map_inventory421_Path as Path
    from _fg_helpers import map_write as write, map_impact_of as impact_of
    root, data = impact_project
    write(root, "tests/_helper.py", "VALUE = 1\n")
    write(root, "tests/test_helper_user.py", "from tests._helper import VALUE\n\ndef test_helper():\n    assert VALUE == 1\n")
    write(root, "tests/__init__.py", "")
    imp = impact_of(root, data, ["tests/_helper.py"])
    assert imp.tests == ["tests/test_helper_user.py"]
    assert imp.direct == [] and imp.dependents == []


def test_conftest_change_selects_all_tests_below_its_directory(impact_project):
    import pytest, os, json
    from pathlib import Path
    from _fg_helpers import map_inventory421_pytest as pytest, map_inventory421_os as os, map_inventory421_json as json, map_inventory421_Path as Path
    from _fg_helpers import map_write as write, map_impact_of as impact_of
    root, data = impact_project
    write(root, "tests/conftest.py", "VALUE = 1\n")
    imp = impact_of(root, data, ["tests/conftest.py"])
    assert set(imp.tests) == {"tests/test_orders.py", "tests/test_storage.py", "tests/test_api.py", "tests/test_web.py"}
    assert "tests/conftest.py" not in imp.tests


def test_model_binding_implemented_by_and_tested_by_select_bidirectionally(impact_project):
    import pytest, os, json
    from pathlib import Path
    from _fg_helpers import map_inventory421_pytest as pytest, map_inventory421_os as os, map_inventory421_json as json, map_inventory421_Path as Path
    from _fg_helpers import map_write as write, map_impact_of as impact_of
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
    import pytest, os, json
    from pathlib import Path
    from _fg_helpers import map_inventory421_pytest as pytest, map_inventory421_os as os, map_inventory421_json as json, map_inventory421_Path as Path
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    from _fg_helpers import map_write as write, map_impact_of as impact_of
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


def test_confirm_alone_is_not_reported_as_a_description_change(impact_project):
    import pytest, os, json
    from pathlib import Path
    from _fg_helpers import map_inventory421_pytest as pytest, map_inventory421_os as os, map_inventory421_json as json, map_inventory421_Path as Path
    from _fg_helpers import map_impact_of as impact_of
    root, data = impact_project
    data["components"][1].update(status="confirmed", fingerprint="sha256:updated")
    imp = impact_of(root, data, [".flowguard/map.json"], base="HEAD")
    assert not imp.map_review and not imp.tests and not imp.models


@pytest.mark.parametrize("retire", [False, True])
def test_deleted_owner_keeps_surviving_test_and_contract_only(impact_project, retire):
    import pytest, os, json
    from pathlib import Path
    from _fg_helpers import map_inventory421_pytest as pytest, map_inventory421_os as os, map_inventory421_json as json, map_inventory421_Path as Path
    import subprocess
    from _fg_helpers import map_write as write, map_save as save, map_impact_of as impact_of, map_git as git
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
    import pytest, os, json
    from pathlib import Path
    from _fg_helpers import map_inventory421_pytest as pytest, map_inventory421_os as os, map_inventory421_json as json, map_inventory421_Path as Path
    from _fg_helpers import map_save as save, map_impact_of as impact_of, map_git as git
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


def test_npm_static_import_is_not_a_dynamic_surface(impact_project):
    import pytest, os, json
    from pathlib import Path
    from _fg_helpers import map_inventory421_pytest as pytest, map_inventory421_os as os, map_inventory421_json as json, map_inventory421_Path as Path
    from _fg_helpers import map_write as write, map_impact_of as impact_of
    root, data = impact_project
    write(root, "web/app.js", "import React from 'react';\n")
    assert not any("dynamic" in message for message in impact_of(root, data, ["web/app.js"]).uncertainty)


def test_depends_on_order_is_not_a_verification_change(impact_project):
    import pytest, os, json
    from pathlib import Path
    from _fg_helpers import map_inventory421_pytest as pytest, map_inventory421_os as os, map_inventory421_json as json, map_inventory421_Path as Path
    from _fg_helpers import map_save as save, map_impact_of as impact_of, map_git as git
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


def test_change_selects_the_review_children_of_a_selected_model(impact_project):
    import pytest, os, json
    from pathlib import Path
    from _fg_helpers import map_inventory421_pytest as pytest, map_inventory421_os as os, map_inventory421_json as json, map_inventory421_Path as Path
    from _fg_helpers import map_write as write, map_impact_of as impact_of
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


def test_signature_change_selects_callers_models(tmp_path):
    import pytest, os, json
    from pathlib import Path
    from _fg_helpers import map_inventory421_pytest as pytest, map_inventory421_os as os, map_inventory421_json as json, map_inventory421_Path as Path
    from _fg_helpers import map_function_fixture as function_fixture, map_impact_of as impact_of, map_git as git
    h=function_fixture();data=h['fixture'](tmp_path)
    h['write'](tmp_path,'api.py','from core import own\ndef call(): return own()\n')
    git(tmp_path,'add','.')
    git(tmp_path,'-c','user.name=FlowGuard','-c','user.email=model@example.invalid','commit','-qm','caller baseline')
    path=tmp_path/'core.py';path.write_text(path.read_text().replace('def own():','def own(value=0):'))
    impact=impact_of(tmp_path,data,['core.py'],base='HEAD')
    assert {'child','importer'}<=set(impact.model_ids)
    assert 'api.py:call' in impact.changed_functions


def test_dataclass_field_added_selects_constructors_models(tmp_path):
    import pytest, os, json
    from pathlib import Path
    from _fg_helpers import map_inventory421_pytest as pytest, map_inventory421_os as os, map_inventory421_json as json, map_inventory421_Path as Path
    from _fg_helpers import map_function_fixture as function_fixture, map_impact_of as impact_of, map_git as git
    h=function_fixture();data=h['fixture'](tmp_path)
    h['write'](tmp_path,'core.py','from dataclasses import dataclass\n@dataclass\nclass Value:\n    x:int=0\n')
    h['write'](tmp_path,'api.py','from core import Value\ndef call(): return Value()\n')
    git(tmp_path,'add','.')
    git(tmp_path,'-c','user.name=FlowGuard','-c','user.email=model@example.invalid','commit','-qm','dataclass baseline')
    path=tmp_path/'core.py';path.write_text(path.read_text()+'    y:int=0\n')
    impact=impact_of(tmp_path,data,['core.py'],base='HEAD')
    assert 'importer' in impact.model_ids and 'api.py:call' in impact.changed_functions


def test_class_anchor_covers_methods(tmp_path):
    import pytest, os, json
    from pathlib import Path
    from _fg_helpers import map_inventory421_pytest as pytest, map_inventory421_os as os, map_inventory421_json as json, map_inventory421_Path as Path
    from _fg_helpers import map_function_fixture as function_fixture, map_impact_of as impact_of, map_git as git
    h=function_fixture();data=h['fixture'](tmp_path)
    h['write'](tmp_path,'core.py','class Service:\n    def work(self): return 1\n')
    h['write'](tmp_path,'.flowguard/models/child.py','MODEL_ID="child"\nPARENT="logic"\nIMPLEMENTED_BY={"Run":"core.py:Service"}\ndef build_explorer(): pass\n')
    git(tmp_path,'add','.')
    git(tmp_path,'-c','user.name=FlowGuard','-c','user.email=model@example.invalid','commit','-qm','class baseline')
    path=tmp_path/'core.py';path.write_text(path.read_text().replace('return 1','return 2'))
    impact=impact_of(tmp_path,data,['core.py'],base='HEAD')
    assert impact.model_ids==['child'] and 'core.py:Service.work' in impact.changed_functions


def test_model_edit_keeps_bound_test_function_selection(tmp_path):
    import pytest, os, json
    from pathlib import Path
    from _fg_helpers import map_inventory421_pytest as pytest, map_inventory421_os as os, map_inventory421_json as json, map_inventory421_Path as Path
    from _fg_helpers import map_function_fixture as function_fixture, map_impact_of as impact_of
    helper=function_fixture();data=helper['fixture'](tmp_path)
    path=tmp_path/'.flowguard/models/child.py'
    path.write_text(path.read_text()+'\nREVISION=2\n')
    result=impact_of(tmp_path,data,['.flowguard/models/child.py'],base='HEAD')
    assert result.tests==['tests/test_core.py']
    assert result.test_functions=={'tests/test_core.py':['test_bound']}
    assert result.selected_test_functions==1
    assert not result.whole_test_files
