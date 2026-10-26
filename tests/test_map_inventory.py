"""Tests grouped by their model or native component."""
from __future__ import annotations
import pytest,os,json
from pathlib import Path


def test_type_checking_imports_are_not_dependencies(project):
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    inv = build_inventory(project, DEFAULT_IGNORE)
    assert "shop/api.py" not in inv.file_deps.get("shop/orders.py", set())
    assert "shop/storage.py" in inv.file_deps["shop/orders.py"]
    assert "web/client.js" in inv.file_deps["web/app.js"]


@pytest.mark.parametrize("invalid", ["never-existed", "malformed", "duplicate", "no-base"])
def test_missing_model_without_unambiguous_base_contract_stays_blocked(retired_model_project, invalid):
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
    from _fg_helpers import map_save as save, map_impact_of as impact_of
    root, data = impact_project
    data["components"][1]["summary"] = "Clarified order rules"
    save(root, data)
    imp = impact_of(root, data, [".flowguard/map.json"], base="HEAD")
    assert imp.map_review == ["orders"]
    assert not imp.tests and not imp.models and not imp.blocked


def test_impact_static_parenthesized_import_is_not_dynamic(impact_project):
    from _fg_helpers import map_write as write, map_impact_of as impact_of
    root, data = impact_project
    write(root, "shop/api.py", "from shop.orders import (\n    place_order,\n)\n")
    imp = impact_of(root, data, ["shop/orders.py"])
    assert "api" in imp.dependents
    assert not any("shop/api.py: dynamic" in message for message in imp.uncertainty)


def test_non_ascii_file_names_are_inventoried_and_fingerprinted(project):
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    from _fg_helpers import map_write as write, map_git as git
    write(project, "shop/工具.py", "def 帮助():\n    return 1\n")
    git(project, "add", "-A")
    inv = build_inventory(project, DEFAULT_IGNORE)
    assert "shop/工具.py" in inv.source            # git C-quotes this name without -z


def test_inventory_cache_never_trusts_a_parse_of_a_just_written_file(project):
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
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


def test_parse_cache_written_by_other_parser_code_is_ignored(project):
    import json
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
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


def test_explicit_test_named_product_file_is_owned_and_not_run_as_test(impact_project):
    from _fg_helpers import map_write as write, map_impact_of as impact_of
    root, data = impact_project
    write(root, "shop/test_inventory.py", "VALUE = 1\n")
    data["components"][2]["files"].append("shop/test_inventory.py")
    imp = impact_of(root, data, ["shop/test_inventory.py"])
    assert imp.direct == ["storage"]
    assert "shop/test_inventory.py" not in imp.tests
    assert "storage-proof" in imp.model_ids


def test_import_changed_code_selects_test_outside_component_binding(impact_project):
    from _fg_helpers import map_write as write, map_impact_of as impact_of
    root, data = impact_project
    write(root, "tests/test_cross.py", "from shop.storage import save\n\ndef test_cross():\n    assert save(1) == 1\n")
    data["components"][3]["tests"].append("tests/test_cross.py")
    assert "tests/test_cross.py" in impact_of(root, data, ["shop/storage.py"]).tests


def test_test_helper_selects_importing_tests_without_running_helper(impact_project):
    from _fg_helpers import map_write as write, map_impact_of as impact_of
    root, data = impact_project
    write(root, "tests/_helper.py", "VALUE = 1\n")
    write(root, "tests/test_helper_user.py", "from tests._helper import VALUE\n\ndef test_helper():\n    assert VALUE == 1\n")
    write(root, "tests/__init__.py", "")
    imp = impact_of(root, data, ["tests/_helper.py"])
    assert imp.tests == ["tests/test_helper_user.py"]
    assert imp.direct == [] and imp.dependents == []


def test_conftest_change_selects_all_tests_below_its_directory(impact_project):
    from _fg_helpers import map_write as write, map_impact_of as impact_of
    root, data = impact_project
    write(root, "tests/conftest.py", "VALUE = 1\n")
    imp = impact_of(root, data, ["tests/conftest.py"])
    assert set(imp.tests) == {"tests/test_orders.py", "tests/test_storage.py", "tests/test_api.py", "tests/test_web.py"}
    assert "tests/conftest.py" not in imp.tests


def test_model_binding_implemented_by_and_tested_by_select_bidirectionally(impact_project):
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


@pytest.mark.parametrize("expression", ["pkg.B", "getattr(pkg, 'B')", "hasattr(pkg, name)", "pkg.__all__"])
def test_lazy_facade_module_attribute_and_reflection_reach_exports(tmp_path, expression):
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    from _fg_helpers import map_write as write
    write(tmp_path, "pkg/__init__.py", "_TABLE = {'pkg.a': ('A',), 'pkg.b': ('B',)}\ndef __getattr__(name):\n    pass\n")
    write(tmp_path, "pkg/a.py", "A = 1\n")
    write(tmp_path, "pkg/b.py", "B = 2\n")
    write(tmp_path, "tests/test_reflect.py", f"import pkg\nname = 'B'\nvalue = {expression}\n")
    inv = build_inventory(tmp_path, DEFAULT_IGNORE)
    assert "pkg/b.py" in inv.file_deps["tests/test_reflect.py"]


def test_confirm_alone_is_not_reported_as_a_description_change(impact_project):
    from _fg_helpers import map_impact_of as impact_of
    root, data = impact_project
    data["components"][1].update(status="confirmed", fingerprint="sha256:updated")
    imp = impact_of(root, data, [".flowguard/map.json"], base="HEAD")
    assert not imp.map_review and not imp.tests and not imp.models


@pytest.mark.parametrize("retire", [False, True])
def test_deleted_owner_keeps_surviving_test_and_contract_only(impact_project, retire):
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
    from _fg_helpers import map_write as write, map_impact_of as impact_of
    root, data = impact_project
    write(root, "web/app.js", "import React from 'react';\n")
    assert not any("dynamic" in message for message in impact_of(root, data, ["web/app.js"]).uncertainty)


def test_script_directory_imports_resolve_to_sibling_files(tmp_path):
    from flowguard.map.inventory import build_inventory
    from _fg_helpers import map_write as write
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
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    from _fg_helpers import map_write as write
    import os
    import time
    write(tmp_path, "pkg/a.py", "def f(a):\n" + "    a = a + 1\n" * 10 + "    return a\n")
    past = time.time() - 60
    os.utime(tmp_path / "pkg/a.py", (past, past))          # old enough to be cached
    assert build_inventory(tmp_path, DEFAULT_IGNORE, with_bodies=False).py["pkg/a.py"].bodies == []
    assert build_inventory(tmp_path, DEFAULT_IGNORE).py["pkg/a.py"].bodies


@pytest.mark.parametrize("guard", ["TYPE_CHECKING", "t.TYPE_CHECKING"])
def test_import_sites_skip_type_checking_and_sort_by_line(tmp_path, guard):
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    from _fg_helpers import map_write as write
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


def test_depends_on_order_is_not_a_verification_change(impact_project):
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


def test_change_selects_the_review_children_of_a_selected_model(impact_project):
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


def test_docstring_version_text_is_not_a_declaration(tmp_path):
    from flowguard.map.inventory import build_inventory
    from _fg_helpers import map__release_project as _release_project
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
    from flowguard.map.inventory import build_inventory
    from _fg_helpers import map_write as write, map__release_project as _release_project
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


def test_missing_import_root_is_a_warning(tmp_path):
    from flowguard.map.inventory import build_inventory
    from flowguard.map.check import run_check
    data = {"schema": "flowguard.map.v1", "components": [], "import_roots": ["library"]}
    inv = build_inventory(tmp_path, [], write_cache=False, import_roots=("library",))
    findings = [f for f in run_check(tmp_path, data, inv, strict=True) if f.code == "import_root_missing"]
    assert len(findings) == 1 and findings[0].level == "warn"
    (tmp_path / "library").mkdir()
    assert not [f for f in run_check(tmp_path, data, inv) if f.code == "import_root_missing"]


def test_signature_change_selects_callers_models(tmp_path):
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
    from _fg_helpers import map_function_fixture as function_fixture, map_impact_of as impact_of, map_git as git
    h=function_fixture();data=h['fixture'](tmp_path)
    h['write'](tmp_path,'core.py','class Service:\n    def work(self): return 1\n')
    h['write'](tmp_path,'.flowguard/models/child.py','MODEL_ID="child"\nPARENT="logic"\nIMPLEMENTED_BY={"Run":"core.py:Service"}\ndef build_explorer(): pass\n')
    git(tmp_path,'add','.')
    git(tmp_path,'-c','user.name=FlowGuard','-c','user.email=model@example.invalid','commit','-qm','class baseline')
    path=tmp_path/'core.py';path.write_text(path.read_text().replace('return 1','return 2'))
    impact=impact_of(tmp_path,data,['core.py'],base='HEAD')
    assert impact.model_ids==['child'] and 'core.py:Service.work' in impact.changed_functions


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


def test_model_edit_keeps_bound_test_function_selection(tmp_path):
    from _fg_helpers import map_function_fixture as function_fixture, map_impact_of as impact_of
    helper=function_fixture();data=helper['fixture'](tmp_path)
    path=tmp_path/'.flowguard/models/child.py'
    path.write_text(path.read_text()+'\nREVISION=2\n')
    result=impact_of(tmp_path,data,['.flowguard/models/child.py'],base='HEAD')
    assert result.tests==['tests/test_core.py']
    assert result.test_functions=={'tests/test_core.py':['test_bound']}
    assert result.selected_test_functions==1
    assert not result.whole_test_files
