"""Tests grouped by their model or native component."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
import pytest
from flowguard.__main__ import main
from flowguard.map.cli import _context
from flowguard.map.check import run_check
from flowguard.map.lint import run_lint
import shutil
import sys
import tempfile
import unittest
from flowguard.map.discover import component_summary, console_scripts, discover, discover_inventory, file_facts
from flowguard.map.common import DEFAULT_IGNORE
from flowguard.map.inventory import build_inventory
from flowguard.map.lint import entrypoint_coverage_findings, run_lint, scoped_architecture_findings
from flowguard.map.scan import guess_tests, new_map, propose_components
from dataclasses import fields, is_dataclass, replace
import runpy
from flowguard.map.mapfile import load_map
from flowguard.map.port import model_port, port_findings, upward
from flowguard.map.tree import build_tree
import pytest, os, json

from _fg_helpers import (
    flowguard_map_discover421__INJECTED_SERVICE as _INJECTED_SERVICE,
    view__component as _component,
    view__field_project as _field_project,
    flowguard_map_discover421__injected_project as _injected_project,
    view__inventory as _inventory,
    view__quiet_fixture as _quiet_fixture,
    map__release_project as _release_project,
    view__review_project as _review_project,
    flowguard_port421_dispatch_project as dispatch_project,
    flowguard_port421_errors as errors,
    flowguard_map_contracts421_write,
    flowguard_port421_project,
    view_locate_fixture as locate_fixture,
    map_write,
    flowguard_port421_probe as probe,
    flowguard_port421_rewrite as rewrite,
)

def test_import_literals_survive_inventory_cache(tmp_path):
    import json
    import subprocess
    from pathlib import Path
    import pytest
    from flowguard.__main__ import main
    from flowguard.map.cli import _context
    from flowguard.map.check import run_check
    from flowguard.map.lint import run_lint
    import os
    from flowguard.map.inventory import CACHE_SCHEMA, build_inventory
    from flowguard.map.common import DEFAULT_IGNORE

    flowguard_map_contracts421_write(tmp_path, "a.py", 'TARGET = __import__("pkg")\n')
    os.utime(tmp_path / "a.py", (1, 1))
    first = build_inventory(tmp_path, DEFAULT_IGNORE)
    cached = json.loads((tmp_path / ".flowguard/cache/inventory.json").read_text())
    assert cached["schema"] == CACHE_SCHEMA == "flowguard.map.inventory_cache.v5"
    assert cached["files"]["a.py"]["import_literals"] == ["pkg"]
    second = build_inventory(tmp_path, DEFAULT_IGNORE)
    assert first.py["a.py"].import_literals == second.py["a.py"].import_literals == {"pkg"}


def test_write_into_an_injected_object_is_a_foreign_state_write(tmp_path):
    """Writing an attribute of another component's injected object is foreign_state_write."""
    import json
    import shutil
    import subprocess
    import sys
    import tempfile
    import unittest
    from pathlib import Path
    import pytest
    from flowguard.map.discover import (
        component_summary,
        console_scripts,
        discover,
        discover_inventory,
        file_facts,
    )
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    from flowguard.map.lint import (
        entrypoint_coverage_findings,
        run_lint,
        scoped_architecture_findings,
    )
    from flowguard.map.scan import guess_tests, new_map, propose_components

    service = _INJECTED_SERVICE + "\n    def clear(self):\n        self.store.notes = {}\n"
    data = _injected_project(tmp_path, service=service)
    inv = build_inventory(tmp_path, DEFAULT_IGNORE)
    found = [f for f in run_lint(tmp_path, data, inv) if f.code == "foreign_state_write"]
    assert any("NoteStore.notes" in f.message and f.component == "service" for f in found), found


def test_module_resolver_keeps_package_then_script_then_root_precedence():
    import json
    import shutil
    import subprocess
    import sys
    import tempfile
    import unittest
    from pathlib import Path
    import pytest
    from flowguard.map.discover import (
        component_summary,
        console_scripts,
        discover,
        discover_inventory,
        file_facts,
    )
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    from flowguard.map.lint import (
        entrypoint_coverage_findings,
        run_lint,
        scoped_architecture_findings,
    )
    from flowguard.map.scan import guess_tests, new_map, propose_components
    from flowguard.map.inventory import resolve_module, resolve_import

    files = {
        "scripts/runner.py",
        "scripts/helper.py",
        "library/helper.py",
        "other/helper.py",
        "library/pkg/__init__.py",
    }
    assert (
        resolve_module(
            "helper", "scripts/runner.py", {"helper": "package/helper.py"}, files, ("library",)
        )
        == "package/helper.py"
    )
    assert (
        resolve_module("helper", "scripts/runner.py", {}, files, ("library",))
        == "scripts/helper.py"
    )
    assert (
        resolve_module(
            "helper", "scripts/runner.py", {}, files | {"scripts/__init__.py"}, ("library", "other")
        )
        == "library/helper.py"
    )
    assert resolve_module("pkg", "runner.py", {}, files, ("library",)) == "library/pkg/__init__.py"
    assert (
        resolve_import("helper:_private", {}, importer="scripts/runner.py", py_paths=files)
        == "scripts/helper.py"
    )


def test_clearing_an_into_field_is_not_a_receipt(tmp_path):
    from dataclasses import fields, is_dataclass, replace
    from pathlib import Path
    import json
    import runpy
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    from flowguard.map.mapfile import load_map
    from flowguard.map.port import model_port, port_findings, upward
    from flowguard.map.tree import build_tree

    root = tmp_path
    flowguard_port421_project(root, "domain_keeps")
    rewrite(root, "desk", 'writes=("extra",)', 'writes=("extra","answer")')
    rewrite(root, "desk", "extra=not state.extra", 'extra=not state.extra,answer=""')
    result = probe(root)
    assert result.status == "fail" and any(
        "keeps_not_orchestration" in p for p in result.problems
    ), result


def test_dispatch_parent_checks(tmp_path):
    from dataclasses import fields, is_dataclass, replace
    from pathlib import Path
    import json
    import runpy
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    from flowguard.map.mapfile import load_map
    from flowguard.map.port import model_port, port_findings, upward
    from flowguard.map.tree import build_tree

    for kind in ("valid", "no_dispatch"):
        root = tmp_path / kind
        data, inv = dispatch_project(root, kind)
        result = probe(root, "cmd")
        assert not errors(root, data, inv), errors(root, data, inv)
        assert result.status == "pass", result
    for kind, code in (
        ("unknown", "dispatch_without_child"),
        ("wrong_branch", "dispatch_branch_not_received"),
        ("two_branches", "dispatch_two_branches"),
    ):
        root = tmp_path / kind
        dispatch_project(root, kind)
        result = probe(root, "cmd")
        assert result.status == "fail" and any(code in p for p in result.problems), result
    for kind, code in (
        ("nonchild", "dispatch_without_child"),
        ("unknown_selector", "dispatch_field_unknown"),
    ):
        root = tmp_path / kind
        data, inv = dispatch_project(root, kind)
        assert errors(root, data, inv) == {code}


def test_type_checking_imports_are_not_dependencies(project):
    import pytest, os, json
    from pathlib import Path
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory

    inv = build_inventory(project, DEFAULT_IGNORE)
    assert "shop/api.py" not in inv.file_deps.get("shop/orders.py", set())
    assert "shop/storage.py" in inv.file_deps["shop/orders.py"]
    assert "web/client.js" in inv.file_deps["web/app.js"]


def test_inventory_cache_never_trusts_a_parse_of_a_just_written_file(project):
    import pytest, os, json
    from pathlib import Path
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    import os

    path = project / "shop/storage.py"
    path.write_text("def save(x):\n    return x\n", encoding="utf-8")
    first = build_inventory(project, DEFAULT_IGNORE)
    assert "save" in first.py["shop/storage.py"].symbols
    st = path.stat()
    path.write_text("def keep(x):\n    return x\n", encoding="utf-8")  # same size
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns))  # same coarse mtime tick
    second = build_inventory(project, DEFAULT_IGNORE)
    assert "keep" in second.py["shop/storage.py"].symbols


def test_parse_cache_written_by_other_parser_code_is_ignored(project):
    import pytest, os, json
    from pathlib import Path
    import json
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    import os
    import time

    path = project / "shop/storage.py"
    old = time.time_ns() - 10_000_000_000
    os.utime(path, ns=(old, old))  # old enough to be cached
    build_inventory(project, DEFAULT_IGNORE)
    cache = project / ".flowguard/cache/inventory.json"
    data = json.loads(cache.read_text(encoding="utf-8"))
    data["files"]["shop/storage.py"]["symbols"] = ["stale_symbol"]
    data["parser"] = "written-by-an-older-flowguard"
    cache.write_text(json.dumps(data), encoding="utf-8")
    assert "save" in build_inventory(project, DEFAULT_IGNORE).py["shop/storage.py"].symbols


@pytest.mark.parametrize(
    "expression", ["pkg.B", "getattr(pkg, 'B')", "hasattr(pkg, name)", "pkg.__all__"]
)
def test_lazy_facade_module_attribute_and_reflection_reach_exports(tmp_path, expression):
    import pytest, os, json
    from pathlib import Path
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory

    map_write(
        tmp_path,
        "pkg/__init__.py",
        "_TABLE = {'pkg.a': ('A',), 'pkg.b': ('B',)}\ndef __getattr__(name):\n    pass\n",
    )
    map_write(tmp_path, "pkg/a.py", "A = 1\n")
    map_write(tmp_path, "pkg/b.py", "B = 2\n")
    map_write(tmp_path, "tests/test_reflect.py", f"import pkg\nname = 'B'\nvalue = {expression}\n")
    inv = build_inventory(tmp_path, DEFAULT_IGNORE)
    assert "pkg/b.py" in inv.file_deps["tests/test_reflect.py"]


def test_script_directory_imports_resolve_to_sibling_files(tmp_path):
    import pytest, os, json
    from pathlib import Path
    from flowguard.map.inventory import build_inventory
    from flowguard.map.inventory import build_inventory

    map_write(tmp_path, "scripts/run.py", "from helper import value\nimport json\n")
    map_write(tmp_path, "scripts/helper.py", "value = 1\n")
    map_write(tmp_path, "pkg/__init__.py", "")
    map_write(tmp_path, "pkg/a.py", "import helper\n")
    map_write(tmp_path, "pkg/helper.py", "value = 2\n")
    inv = build_inventory(tmp_path, [])
    assert inv.file_deps.get("scripts/run.py") == {"scripts/helper.py"}
    assert "pkg/helper.py" not in inv.file_deps.get("pkg/a.py", set())


def test_inventory_without_bodies_still_gives_lint_its_bodies_later(tmp_path):
    import pytest, os, json
    from pathlib import Path
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    import os
    import time

    map_write(tmp_path, "pkg/a.py", "def f(a):\n" + "    a = a + 1\n" * 10 + "    return a\n")
    past = time.time() - 60
    os.utime(tmp_path / "pkg/a.py", (past, past))  # old enough to be cached
    assert build_inventory(tmp_path, DEFAULT_IGNORE, with_bodies=False).py["pkg/a.py"].bodies == []
    assert build_inventory(tmp_path, DEFAULT_IGNORE).py["pkg/a.py"].bodies


@pytest.mark.parametrize("guard", ["TYPE_CHECKING", "t.TYPE_CHECKING"])
def test_import_sites_skip_type_checking_and_sort_by_line(tmp_path, guard):
    import pytest, os, json
    from pathlib import Path
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    from flowguard.map.lint import dependency_import_sites

    map_write(
        tmp_path,
        "a.py",
        "from typing import TYPE_CHECKING\nif " + guard + ":\n"
        "    from b import X\nelse:\n    from b import Y\n\n"
        "def late():\n    pass\n    from b import Z\n    pass\n    from b import W\n",
    )
    map_write(tmp_path, "b.py", "X = Y = Z = W = 1\n")
    data = {"components": [{"id": "a", "files": ["a.py"]}, {"id": "b", "files": ["b.py"]}]}
    inv = build_inventory(tmp_path, DEFAULT_IGNORE)
    sites = dependency_import_sites(tmp_path, data, inv, "a", "b")
    assert sites == ["a.py:5 from b import Y", "a.py:9 from b import Z", "a.py:11 from b import W"]
    assert inv.py["a.py"].imports >= {"b:Y", "b:Z", "b:W"}
    assert "b:X" not in inv.py["a.py"].imports


def test_docstring_version_text_is_not_a_declaration(tmp_path):
    import pytest, os, json
    from pathlib import Path
    from flowguard.map.inventory import build_inventory
    from flowguard.map.mapfile import component_state

    data, comp = _release_project(tmp_path)
    p = tmp_path / "pkg/__init__.py"
    p.write_text(p.read_text().replace('str = "1.0.0"', 'str = "1.0.1"'))
    inv = build_inventory(tmp_path, [])
    assert component_state(tmp_path, comp, inv, data) == "current"
    p.write_text(p.read_text().replace('"example"', '"changed documentation"'))
    assert component_state(tmp_path, comp, inv, data) == "stale"


def test_function_digests_separate_nested_and_module_changes():
    import pytest, os, json
    from pathlib import Path
    from flowguard.map.inventory import function_digests

    source = "VALUE=1\nclass C:\n    field=1\n    def method(self):\n        def inner(): return 1\n        return inner()\n"
    before = function_digests(source)
    nested = function_digests(source.replace("inner(): return 1", "inner(): return 2"))
    assert before["functions"]["C.method"] == nested["functions"]["C.method"]
    assert before["functions"]["C.method.inner"] != nested["functions"]["C.method.inner"]
    assert before["classes"] == nested["classes"]
    assert function_digests(source.replace("field=1", "field=2"))["classes"] != before["classes"]
    assert function_digests(source.replace("VALUE=1", "VALUE=2"))["bindings"] != before["bindings"]


def test_find_matches_plural_and_camel_case_words(tmp_path):
    import pytest, os, json
    from pathlib import Path
    from flowguard.map.inventory import Inventory, PyInfo
    from flowguard.map.views import find_owners

    data = dict(
        components=[
            _component(
                "api", summary="cancel endpoint", responsibilities=["route cancel requests"]
            ),
            _component("orders", responsibilities=["place orders and cancel them"]),
        ]
    )
    assert find_owners(data, _inventory(tmp_path), ["cancel", "order"])[0][1] == "orders"
    inv = Inventory(
        tmp_path,
        ["shop/svc.py"],
        ["shop/svc.py"],
        [],
        {"shop/svc.py": PyInfo("shop.svc", {"OrderService"})},
        {},
        {},
    )
    data = dict(components=[dict(_component("svc"), files=["shop/svc.py"])])
    assert [hit[1] for hit in find_owners(data, inv, ["order"])] == ["svc"]


def test_show_renders_the_model_tree_and_cheap_debt_rules(tmp_path, monkeypatch):
    import pytest, os, json
    from pathlib import Path
    from flowguard.map.views import render_show
    from flowguard.map.inventory import build_inventory
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map import lint, proof

    def write(path, text):
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)

    write("app.py", "import store\ndef run(): return True\n")
    write("store.py", "import app\ndef save(): return True\n")
    write("spare.py", "def idle(): pass\n")
    write("tests/test_app.py", "def test_run(): pass\n")
    contract = 'MODEL_ID = {mid!r}\nCOMPONENTS = {components!r}\nIMPLEMENTED_BY = {{"Run": "app.py:run"}}\ndef build_explorer(): pass\n'
    write(
        ".flowguard/models/parent.py",
        contract.format(mid="parent", components=["app", "store"])
        + 'import child\nTESTED_BY = {"works": ["tests/test_app.py:test_run"]}\n',
    )
    write(".flowguard/models/child.py", contract.format(mid="child", components=["app"]))
    write(
        ".flowguard/models/rooted.py",
        'MODEL_ID="rooted"\nPARENT="system"\nIMPLEMENTED_BY={"Run":"app.py:run"}\ndef conformance(): pass\ndef build_explorer(): pass\n',
    )
    data = dict(
        project="demo",
        layers=["entry", "domain"],
        components=[
            dict(_component("app"), files=["app.py"], layer="entry"),
            dict(_component("store"), files=["store.py"], layer="domain"),
            dict(_component("spare"), files=["spare.py"], layer="domain"),
        ],
        flows=[dict(id="request", steps=["app:run"], model=".flowguard/models/parent.py")],
        accepted_debts=[
            dict(
                expires='9999-12-31',
                code="dependency_cycle",
                component="app",
                contains="store spare",
                reason="Legacy larger scope",
            )
        ],
    )
    inv = build_inventory(tmp_path, DEFAULT_IGNORE)

    def forbidden(*args, **kwargs):
        raise AssertionError("read must not run full lint or models")

    monkeypatch.setattr(lint, "run_lint", forbidden)
    monkeypatch.setattr(proof, "run_models", forbidden)
    text = render_show(tmp_path, data, inv, component=None, detail=False)
    assert text.startswith(
        "# demo: system, 3 components, layers (top > bottom) entry > domain; architecture: 1 error(s), 3 warning(s), 1 accepted debt(s); python -m flowguard read --review ranks them"
    )
    lines = text.splitlines()
    parent = next(line for line in lines if "model parent:" in line)
    child = next(line for line in lines if "+1 stage children: child" in line)
    assert len(child) - len(child.lstrip()) == len(parent) - len(parent.lstrip()) + 2
    assert text.index("model rooted:") < text.index("## app")
    assert "cycle (debt)" in text and "cycle shrank" in text and "layer_violation" in text
    assert "> flow request:" in text and "model: parent" in text
    detail = render_show(tmp_path, data, inv, component="store", detail=False)
    assert "model parent:" in detail and "(home app)" in detail
    assert "works -> tests/test_app.py:test_run" in render_show(
        tmp_path, data, inv, component="app", detail=False
    )
    data["accepted_debts"].append(
        dict(expires='9999-12-31', code="dependency_cycle", members=["app", "store"], reason="Exact scope")
    )
    assert "1 error(s), 3 warning(s), 2 accepted debt(s)" in render_show(
        tmp_path, data, inv, component=None, detail=False
    )


def test_review_of_a_clean_project_lists_its_strengths(tmp_path):
    import pytest, os, json
    from pathlib import Path
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    from flowguard.map.review import render_review

    data = _review_project(tmp_path, clean=True)
    inv = build_inventory(tmp_path, DEFAULT_IGNORE, with_bodies=False, write_cache=False)
    text = render_review(tmp_path, data, inv)
    assert "strengths: no dependency cycles; no layer violations" in text
    assert "no accepted debts" in text and "debts:" not in text
    steps = text.split("optimise next:", 1)[1]
    assert steps.startswith(" nothing to rank") or not any(
        word in steps for word in (" fix ", " split ")
    )


def test_read_line_four_counts_models(tmp_path):
    import pytest, os, json
    from pathlib import Path
    from flowguard.map.views import render_show
    from flowguard.map.inventory import build_inventory
    from flowguard.map.common import DEFAULT_IGNORE

    data = _quiet_fixture("read_show")["make_fixture"](tmp_path)
    inv = build_inventory(tmp_path, DEFAULT_IGNORE, write_cache=False)
    assert (
        render_show(tmp_path, data, inv, component=None, detail=False)
        .splitlines()[3]
        .startswith("relations: 1 models;")
    )


def test_unbound_models_debt_closes_only_models_no_test_calls(tmp_path):
    import pytest, os, json
    from pathlib import Path
    from flowguard.map.review import render_review
    from flowguard.map.inventory import build_inventory
    from flowguard.map.common import DEFAULT_IGNORE

    data = _quiet_fixture("read_show")["make_fixture"](tmp_path)
    path = tmp_path / ".flowguard/models/probe.py"
    source = path.read_text()
    source = source[: source.index("TESTED_BY=")] + "TESTED_BY={}\ndef build_explorer(): pass\n"
    path.write_text(source)
    data["accepted_debts"] = [
        dict(
            expires='9999-12-31',
            code="unbound_models",
            component="probe",
            reason="abstract parent; its children have tests",
        )
    ]
    inv = build_inventory(tmp_path, DEFAULT_IGNORE, write_cache=False)
    text = render_review(tmp_path, data, inv)
    assert "bind tests probe: 3 test functions call its code" in text, text
    from flowguard.map.lint import run_lint

    assert any(
        f.code == "unbound_models" and f.level == "warn" for f in run_lint(tmp_path, data, inv)
    )
    test = tmp_path / "tests/test_app.py"
    test.write_text("def test_unrelated(): assert True\n")
    inv = build_inventory(tmp_path, DEFAULT_IGNORE, write_cache=False)
    text = render_review(tmp_path, data, inv)
    assert (
        "bind tests probe:" not in text
        and "declined: 1 (accepted debts; 0 no longer arise)" in text
    )
    assert not any(
        f.code == "unbound_models" and f.level == "warn" for f in run_lint(tmp_path, data, inv)
    )


def test_locate_unbound_calling_test_suggests_binding(tmp_path):
    import pytest, os, json
    from pathlib import Path

    helper = locate_fixture()
    helper["fixture"](tmp_path)
    code, text = helper["observe"](tmp_path, "unbound")
    assert code == 0 and "bound to: none (unbound; position app)" in text
    assert "next: bind it in owner's TESTED_BY if it checks one of its rules" in text
    from flowguard.map.inventory import build_inventory
    from flowguard.map.views import render_locate

    data = __import__("json").loads((tmp_path / ".flowguard/map.json").read_text())
    text = render_locate(
        tmp_path,
        data,
        build_inventory(tmp_path, [], write_cache=False),
        "tests/test_api.py::test_plain",
    )
    assert "to a model of app in a target" in text and "otherwise it stays unbound" in text


def test_locate_qualified_and_unique_test_method(tmp_path):
    import pytest, os, json
    from pathlib import Path
    from flowguard.map.inventory import build_inventory
    from flowguard.map.views import render_locate

    helper = locate_fixture()
    data = helper["fixture"](tmp_path)
    path = tmp_path / "tests/test_api.py"
    with path.open("a") as stream:
        stream.write(
            "import unittest\nclass Suite(unittest.TestCase):\n    def test_method(self): assert owned()==1\n"
        )
    model = tmp_path / ".flowguard/models/owner.py"
    model.write_text(
        model.read_text().replace(
            '"tests/test_api.py:test_bound"]',
            '"tests/test_api.py:test_bound","tests/test_api.py:Suite.test_method"]',
        )
    )
    inv = build_inventory(tmp_path, [], write_cache=False)
    for location in ("tests/test_api.py::Suite::test_method", "tests/test_api.py:test_method"):
        text = render_locate(tmp_path, data, inv, location)
        assert "bound to: owner (rule safe)" in text and "calls: api.py:owned" in text


def test_locate_test_shows_its_position(tmp_path):
    import pytest, os, json
    from pathlib import Path
    from flowguard.map.views import render_locate

    data, inv = _field_project(tmp_path)
    text = render_locate(tmp_path, data, inv, "tests/test_state.py::test_status")
    assert "(test; position status_model)" in text
    path = tmp_path / "tests/test_state.py"
    path.write_text(
        path.read_text() + "".join(f"def test_extra_{i}(): assert True\n" for i in range(41))
    )
    from flowguard.map.inventory import build_inventory
    from flowguard.map.common import DEFAULT_IGNORE

    inv = build_inventory(tmp_path, DEFAULT_IGNORE, write_cache=False)
    text = render_locate(tmp_path, data, inv, "tests/test_state.py")
    assert "lint: tests/test_state.py: 42 test functions" in text


class DiscoveryBoundaryTests(unittest.TestCase):
    def test_scoped_architecture_reports_cycle_error_with_import_lines_and_preserves_debt(self) -> None:
        import json
        import shutil
        import subprocess
        import sys
        import tempfile
        import unittest
        from pathlib import Path
        import pytest
        from flowguard.map.discover import (
            component_summary,
            console_scripts,
            discover,
            discover_inventory,
            file_facts,
        )
        from flowguard.map.common import DEFAULT_IGNORE
        from flowguard.map.inventory import build_inventory
        from flowguard.map.lint import (
            entrypoint_coverage_findings,
            run_lint,
            scoped_architecture_findings,
        )
        from flowguard.map.scan import guess_tests, new_map, propose_components

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a.py").write_text("import b\ndef act(): return b.run()\n", encoding="utf-8")
            (root / "b.py").write_text("import a\ndef run(): return 1\n", encoding="utf-8")
            inv = build_inventory(root, DEFAULT_IGNORE)
            data = {
                "components": [
                    {"id": "a", "files": ["a.py"], "layer": "low", "tests": [], "models": []},
                    {"id": "b", "files": ["b.py"], "layer": "high", "tests": [], "models": []},
                ],
                "layers": ["high", "low"],
                "flows": [],
                "accepted_debts": [],
            }
            findings = scoped_architecture_findings(root, data, inv, {"a"})
            cycle = next(finding for finding in findings if finding.code == "dependency_cycle")
            self.assertEqual("error", cycle.level)
            self.assertIn("a.py:1 import b", cycle.message)
            layer = next(finding for finding in findings if finding.code == "layer_violation")
            self.assertIn("a.py:1 import b", layer.message)
            data["accepted_debts"] = [
                {
                    "expires": "9999-12-31",
                    "code": "dependency_cycle",
                    "component": "a",
                    "contains": "a <-> b",
                    "reason": "legacy constraint",
                }
            ]
            accepted = scoped_architecture_findings(root, data, inv, {"a"})
            self.assertEqual(
                "info",
                next(finding.level for finding in accepted if finding.code == "dependency_cycle"),
            )
            self.assertEqual([], scoped_architecture_findings(root, data, inv, set()))

    def test_renamed_local_variables_match_duplicate_bodies_but_global_calls_do_not(self) -> None:
        import json
        import shutil
        import subprocess
        import sys
        import tempfile
        import unittest
        from pathlib import Path
        import pytest
        from flowguard.map.discover import (
            component_summary,
            console_scripts,
            discover,
            discover_inventory,
            file_facts,
        )
        from flowguard.map.common import DEFAULT_IGNORE
        from flowguard.map.inventory import build_inventory
        from flowguard.map.lint import (
            entrypoint_coverage_findings,
            run_lint,
            scoped_architecture_findings,
        )
        from flowguard.map.scan import guess_tests, new_map, propose_components

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = (
                "def total(items):\n    result = 0\n    for item in items:\n"
                "        if item > 0:\n            result += item * 2\n"
                "        else:\n            result -= item\n    result *= 2\n    return transform(result)\n"
            )
            renamed = (
                original.replace("total", "sum_values")
                .replace("items", "values")
                .replace("item", "value")
                .replace("result", "answer")
            )
            (root / "a.py").write_text(original, encoding="utf-8")
            (root / "b.py").write_text(renamed, encoding="utf-8")
            (root / "c.py").write_text(
                renamed.replace("transform", "different_operation"), encoding="utf-8"
            )
            inv = build_inventory(root, DEFAULT_IGNORE)
            data = {
                "components": [
                    {"id": name, "files": [f"{name}.py"], "tests": [], "models": []}
                    for name in ("a", "b", "c")
                ],
                "flows": [],
                "layers": [],
                "accepted_debts": [],
            }
            duplicates = [
                finding for finding in run_lint(root, data, inv) if finding.code == "duplicate_code"
            ]
            self.assertEqual(1, len(duplicates))
            self.assertIn("['a', 'b']", duplicates[0].message)
            self.assertNotIn("c.py", duplicates[0].message)

    def test_registered_contracts_and_pytest_hooks_are_real_external_importers(self) -> None:
        import json
        import shutil
        import subprocess
        import sys
        import tempfile
        import unittest
        from pathlib import Path
        import pytest
        from flowguard.map.discover import (
            component_summary,
            console_scripts,
            discover,
            discover_inventory,
            file_facts,
        )
        from flowguard.map.common import DEFAULT_IGNORE
        from flowguard.map.inventory import build_inventory
        from flowguard.map.lint import (
            entrypoint_coverage_findings,
            run_lint,
            scoped_architecture_findings,
        )
        from flowguard.map.scan import guess_tests, new_map, propose_components

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "library.py").write_text("def work(): return 1\n", encoding="utf-8")
            (root / "plugin.py").write_text(
                "def pytest_sessionstart(session): pass\n", encoding="utf-8"
            )
            model = root / ".flowguard/models/sample.py"
            model.parent.mkdir(parents=True)
            model.write_text(
                'MODEL_ID="sample"\nIMPLEMENTED_BY={"Work":"library.py:work"}\n'
                "from library import work\ndef build_explorer(): pass\ndef conformance(): pass\n",
                encoding="utf-8",
            )
            inv = build_inventory(root, DEFAULT_IGNORE)
            data = {
                "components": [
                    {
                        "id": "library",
                        "files": ["library.py", "plugin.py"],
                        "tests": [],
                        "models": [model.relative_to(root).as_posix()],
                    }
                ],
                "flows": [],
                "layers": [],
                "accepted_debts": [],
            }
            findings = run_lint(root, data, inv)
            self.assertFalse(any(finding.code == "never_imported" for finding in findings))
