"""Tests of the model and its real native implementation."""
import pytest
from pathlib import Path





from _fg_helpers import (
    map_git as git,
    view__fg232_count_discovery as _fg232_count_discovery,
    view__fg232_view_project as _fg232_view_project,
    flowguard_map_contracts421__scope_helpers as _scope_helpers,
    flowguard_map_discover421_map_cli as map_cli,
    flowguard_map_contracts421_project as project,
    flowguard_map_contracts421_save as save,
    flowguard_map_contracts421_write as write,
)


def test_shape_findings_are_advice(tmp_path, capsys, monkeypatch):
    from copy import deepcopy
    from flowguard.map import cli, lint

    data = project(tmp_path)
    write(tmp_path, "app.py", "from lib import answer\n\ndef run():\n    return answer()\n")
    write(tmp_path, "lib.py", "def answer():\n    return True\n")
    data["components"][0]["responsibilities"] = ["serve the provider answer", "present availability"]
    data["components"][0]["depends_on"] = ["lib"]
    data["components"].append({
        "id": "lib", "summary": "Provide an immutable answer",
        "responsibilities": ["supply the shared result"], "files": ["lib.py"],
        "tests": ["tests/test_app.py"], "models": [], "depends_on": [], "status": "draft",
    })
    save(tmp_path, data)
    limits = lint.Limits(max_component_loc=1, max_file_loc=1,
                         max_responsibilities=1, max_fan_out=0)
    monkeypatch.setattr(lint, "Limits", lambda: limits)
    monkeypatch.setattr(cli, "Limits", lambda: limits)
    loaded, inv = cli._context(tmp_path)
    shape_codes = {"large_component", "large_file", "too_many_responsibilities", "high_fan_out"}
    findings = lint.run_lint(tmp_path, loaded, inv)
    advice = [finding for finding in findings if finding.code in shape_codes]
    assert {finding.code for finding in advice} == shape_codes
    assert all(finding.level == "info" and "(advice, not a gate)" in finding.message
               for finding in advice), advice
    assert cli.main(["--root", str(tmp_path), "lint"]) == 0
    output = capsys.readouterr().out
    assert "0 warning(s)" in output and "INFO" in output
    assert cli.main(["--root", str(tmp_path), "confirm", "all"]) == 0
    assert main(["release", "--root", str(tmp_path)]) == 0
    output = capsys.readouterr().out
    assert "lint: 0 error(s) gating; 0 warning(s)," in output, output

    data["accepted_debts"] = [{"code": "large_file", "component": "app",
                               "reason": "one actual unit of work", "expires": "9999-12-31"}]
    save(tmp_path, data)
    loaded, inv = cli._context(tmp_path)
    findings = lint.run_lint(tmp_path, loaded, inv)
    assert any(finding.code == "debt_stale" and finding.level == "warn" for finding in findings)
    assert all("accepted debt:" not in finding.message
               for finding in findings if finding.code in shape_codes)
    assert cli.main(["--root", str(tmp_path), "lint"]) == 0
    assert "debt_stale" in capsys.readouterr().out

    missing_tests = deepcopy(loaded)
    missing_tests["components"][0]["tests"] = []
    assert any(finding.code == "untested_component" and finding.level == "warn"
               for finding in lint.shape_findings(missing_tests, inv, {"app": {"lib"}, "lib": set()}))


def test_debt_without_expiry_refused(tmp_path, capsys):
    data = project(tmp_path)
    assert main(["map", "--root", str(tmp_path), "confirm", "all"]) == 0
    data = json.loads((tmp_path / ".flowguard/map.json").read_text())
    invalid = [
        {"reason": "covered elsewhere"},
        {"expires": "9999-12-31"},
        {"expires": "v1.0.0"},
        {"reason": "  ", "expires": "9999-12-31"},
        {"reason": ["not text"], "expires": "9999-12-31"},
        {"reason": "covered elsewhere", "expires": "tomorrow"},
        {"reason": "covered elsewhere", "expires": "2026-02-30"},
        {"reason": "covered elsewhere", "expires": "20261030"},
        {"reason": "covered elsewhere", "expires": "v1.0.0"},
    ]
    for fields in invalid:
        data["accepted_debts"] = [{"code": "entrypoint_unmodeled", "component": "app", **fields}]
        save(tmp_path, data)
        for arguments in (("check",), ("check", "--strict"), ("lint",)):
            assert main(["map", "--root", str(tmp_path), *arguments]) == 1, fields
            output = capsys.readouterr().out
            assert "debt_without_expiry: accepted debt entrypoint_unmodeled app needs reason and expires" in output
            if fields.get("expires") == "v1.0.0":
                assert "this project has no version in pyproject.toml: use a date" in output
    data["accepted_debts"] = [{"code": "entrypoint_unmodeled", "component": "app",
                               "reason": "covered elsewhere", "expires": "9999-12-31"}]
    save(tmp_path, data)
    assert main(["map", "--root", str(tmp_path), "check", "--strict"]) == 0
    assert "debt_without_expiry" not in capsys.readouterr().out


def test_expired_debt_fails_release(tmp_path, capsys):
    from datetime import date, timedelta

    data = project(tmp_path)
    (tmp_path / "tests/test_app.py").unlink()
    data["components"][0]["tests"] = []
    save(tmp_path, data)
    assert main(["map", "--root", str(tmp_path), "confirm", "all"]) == 0
    data = json.loads((tmp_path / ".flowguard/map.json").read_text())
    for deadline in (date.today() - timedelta(days=1), date.today()):
        data["accepted_debts"] = [{"code": "untested_component", "component": "app",
                                   "reason": "verified through callers", "expires": deadline.isoformat()}]
        save(tmp_path, data)
        loaded, inv = _context(tmp_path)
        findings = run_check(tmp_path, loaded, inv)
        assert any(f.code == "debt_expired" and f.level == "warn" for f in findings)
        assert any(f.code == "debt_expired" and f.level == "error"
                   for f in run_check(tmp_path, loaded, inv, strict=True))
        lint = run_lint(tmp_path, loaded, inv)
        assert any(f.code == "untested_component" and f.level == "warn" for f in lint)
        assert not any(f.code == "debt_stale" for f in lint)
        assert main(["map", "--root", str(tmp_path), "check", "--strict"]) == 1
        assert "debt_expired: untested_component app expired at " + deadline.isoformat() in capsys.readouterr().out
        assert main(["release", "--root", str(tmp_path)]) == 1
        assert "verify: FAIL" in capsys.readouterr().out
    data["accepted_debts"][0]["expires"] = (date.today() + timedelta(days=1)).isoformat()
    save(tmp_path, data)
    assert main(["map", "--root", str(tmp_path), "check", "--strict"]) == 0
    assert main(["release", "--root", str(tmp_path)]) == 0
    assert "debt_expired" not in capsys.readouterr().out

    write(tmp_path, "pyproject.toml", '[project]\nname = "expiry-probe"\nversion = "1.2.3"\n')
    for deadline, expired in (("v1.2.2", True), ("v1.2.3", True), ("v1.2.4", False)):
        data["accepted_debts"][0]["expires"] = deadline
        save(tmp_path, data)
        loaded, inv = _context(tmp_path)
        findings = run_check(tmp_path, loaded, inv, strict=True)
        assert any(f.code == "debt_expired" for f in findings) is expired

def test_strict_check_refuses_committed_promoted_target(tmp_path, capsys):
    import shutil

    project(tmp_path)
    assert main(["map", "confirm", "all", "--root", str(tmp_path)]) == 0
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", ".")
    git(tmp_path, "-c", "user.name=probe", "-c", "user.email=probe@example.invalid", "commit", "-qm", "seed")
    assert main(["target", "start", "unchanged app", "--root", str(tmp_path)]) == 0
    assert main(["target", "add", "component:app", "--root", str(tmp_path)]) == 0
    git(tmp_path, "add", ".flowguard/target")
    capsys.readouterr()
    # Merely staged is not committed, even though its target happens to be a no-op.
    assert main(["map", "check", "--strict", "--root", str(tmp_path)]) == 0
    git(tmp_path, "-c", "user.name=probe", "-c", "user.email=probe@example.invalid", "commit", "-qm", "target")
    assert main(["map", "check", "--strict", "--root", str(tmp_path)]) == 1
    assert "target_already_promoted: .flowguard/target/ is committed but changes nothing (already promoted)" in capsys.readouterr().out
    assert main(["map", "check", "--root", str(tmp_path)]) == 0
    assert "WARN" in capsys.readouterr().out
    assert main(["read", "--root", str(tmp_path)]) == 0
    assert 'target: "unchanged app": stale (already promoted); delete .flowguard/target/ and commit the deletion' in capsys.readouterr().out
    shutil.rmtree(tmp_path / ".flowguard/target")
    assert main(["map", "check", "--strict", "--root", str(tmp_path)]) == 1
    assert "target_deleted_not_staged" in capsys.readouterr().out
    git(tmp_path, "add", "-A", ".flowguard")
    assert main(["map", "check", "--strict", "--root", str(tmp_path)]) == 0
    git(tmp_path, "-c", "user.name=probe", "-c", "user.email=probe@example.invalid", "commit", "-qm", "remove stale target")
    current = json.loads((tmp_path / ".flowguard/map.json").read_text())
    current["flows"] = [{"id": "retired_flow", "steps": ["app:run"]}]
    save(tmp_path, current)
    git(tmp_path, "add", ".flowguard/map.json")
    git(tmp_path, "-c", "user.name=probe", "-c", "user.email=probe@example.invalid", "commit", "-qm", "flow")
    assert main(["target", "start", "retire completed flow", "--root", str(tmp_path)]) == 0
    path = tmp_path / ".flowguard/target/map.json"
    target = json.loads(path.read_text())
    target["remove"] = ["flow:retired_flow"]
    path.write_text(json.dumps(target))
    retained = {p.relative_to(tmp_path): p.read_bytes() for p in (tmp_path / ".flowguard/target").rglob("*") if p.is_file()}
    git(tmp_path, "add", ".flowguard/target")
    git(tmp_path, "-c", "user.name=probe", "-c", "user.email=probe@example.invalid", "commit", "-qm", "retire target")
    assert main(["target", "promote", "--root", str(tmp_path)]) == 0
    for relative, content in retained.items():
        (tmp_path / relative).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / relative).write_bytes(content)
    git(tmp_path, "add", ".flowguard/map.json")
    git(tmp_path, "-c", "user.name=probe", "-c", "user.email=probe@example.invalid", "commit", "-qm", "bad retirement publication")
    capsys.readouterr()
    assert main(["release", "--root", str(tmp_path)]) == 1
    assert "target_already_promoted" in capsys.readouterr().out
    assert main(["map", "check", "--strict", "--root", str(tmp_path)]) == 1
    assert main(["read", "--root", str(tmp_path)]) == 0
    assert 'target: "retire completed flow": stale (already promoted)' in capsys.readouterr().out
    from flowguard.map.targetfile import load_target, target_is_noop, validate_target
    current = json.loads((tmp_path / ".flowguard/map.json").read_text())
    restored = load_target(tmp_path)
    assert not target_is_noop(tmp_path, current, restored)
    assert any("remove names no current node" in issue.message for issue in validate_target(tmp_path, current, restored))
    from copy import deepcopy
    from flowguard.map.targetfile import target_seam
    original = json.loads(path.read_text())
    for entries in (["flow:retired_flow", "flow:retired_flow"],
                    ["flow:retired_flow", "unknown:item"], ["flow:retired_flow", "broken"]):
        malformed = {**original, "remove": entries}
        path.write_text(json.dumps(malformed))
        assert not target_seam(tmp_path, current).already_promoted
    pending = deepcopy(original)
    pending["components"] = [dict(current["components"][0], summary="New work still pending")]
    for field in ("status", "fingerprint", "_hint"):
        pending["components"][0].pop(field, None)
    path.write_text(json.dumps(pending))
    assert not target_seam(tmp_path, current).already_promoted
    path.write_text(json.dumps(original))
    shutil.rmtree(tmp_path / ".flowguard/target")
    git(tmp_path, "add", "-A", ".flowguard")
    # Keep the no-Git input independent; Git's object files can be read-only on Windows.
    gitless = tmp_path.parent / (tmp_path.name + "-gitless")
    project(gitless)
    assert main(["map", "confirm", "all", "--root", str(gitless)]) == 0
    assert main(["target", "start", "gitless unchanged app", "--root", str(gitless)]) == 0
    assert main(["target", "add", "component:app", "--root", str(gitless)]) == 0
    capsys.readouterr()
    assert main(["map", "check", "--strict", "--root", str(gitless)]) == 0
    output = capsys.readouterr().out
    assert "WARN" in output and "target_noop: target changes nothing: drop it or add work" in output


def test_identical_info_grouped_into_one_line(capsys, tmp_path, monkeypatch):
    import json
    from pathlib import Path
    from flowguard.map import cli
    from flowguard.map.common import Finding, print_findings
    notes = [Finding("info", "same", f"c{i}", "note") for i in range(24)]
    warnings = [Finding("warn", "same", f"w{i}", "warning") for i in range(3)]
    counts = print_findings(notes + warnings, "lint", as_json=False, limit=80)
    text = capsys.readouterr().out
    assert counts == {"error": 0, "warn": 3, "info": 24}
    assert sum(line.startswith("INFO") for line in text.splitlines()) == 1
    assert "INFO same x24: c0, c1, c10, c11, c12, c13, c14, c15 (+16 more; python -m flowguard map lint --json)" in text
    assert sum(line.startswith("WARN") for line in text.splitlines()) == 3
    print_findings(notes, "lint", as_json=True, limit=1)
    assert len(json.loads(capsys.readouterr().out)["findings"]) == 24
    # Exercise release's real output boundary: findings precede real model execution.
    import runpy
    from types import SimpleNamespace
    helpers = runpy.run_path(str(Path(__file__).parents[1] / ".flowguard/models/model_runs.py"))
    helpers["make_fixture"](tmp_path)
    monkeypatch.setattr(cli, "run_check", lambda *a, **kw: [Finding("info", "same", str(i), "note") for i in range(24)])
    assert cli.cmd_verify(tmp_path, SimpleNamespace(limit=80, jobs=1, shards=None)) == 0
    output = capsys.readouterr().out
    assert sum(line.startswith("INFO same x24:") for line in output.splitlines()) == 1
    assert "PASS  first" in output and "PASS  second" in output

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
import pytest, os, json

def test_accepted_debts_mean_the_same_in_check_and_lint(tmp_path):
    import json
    import subprocess
    from pathlib import Path
    import pytest
    from flowguard.__main__ import main
    from flowguard.map.cli import _context
    from flowguard.map.check import run_check
    from flowguard.map.lint import run_lint

    data = project(tmp_path)
    write(tmp_path, "app.py", "def run():\n    open('out.txt', 'w').write('x')\n    return True\n")
    write(tmp_path, "lib.py", "VALUE = 1\n")
    data["components"].append(
        {
            "id": "lib",
            "summary": "Lib",
            "responsibilities": ["hold a value"],
            "files": ["lib.py"],
            "entrypoints": [],
            "tests": [],
            "models": [],
            "depends_on": [],
            "status": "draft",
        }
    )
    data["components"][0]["depends_on"] = ["lib"]
    data["accepted_debts"] = [
        {
            "code": "dep_unused",
            "component": "app",
            "contains": "lib",
            "reason": "loaded by path at runtime",
            "expires": "9999-12-31",
        },
        {
            "code": "entrypoint_unmodeled",
            "component": "app",
            "reason": "file output is covered by an integration test",
            "expires": "9999-12-31",
        },
    ]
    save(tmp_path, data)
    d, inv = _context(tmp_path)
    levels = {f.code: f.level for f in run_check(tmp_path, d, inv)}
    assert "dep_unused" not in levels and levels.get("entrypoint_unmodeled") == "info"
    assert "debt_stale" not in {f.code for f in run_lint(tmp_path, d, inv)}
    write(
        tmp_path,
        "app.py",
        "import lib\n\ndef run():\n    open('out.txt', 'w').write('x')\n    return lib.VALUE\n",
    )
    d, inv = _context(tmp_path)
    assert any(
        f.code == "debt_stale" and "loaded by path" in f.message for f in run_lint(tmp_path, d, inv)
    )


def test_broken_uses_is_named(tmp_path):
    import json
    import subprocess
    from pathlib import Path
    import pytest
    from flowguard.__main__ import main
    from flowguard.map.cli import _context
    from flowguard.map.check import run_check
    from flowguard.map.lint import run_lint

    data, inv, _ = _scope_helpers()["scope_fixture"](tmp_path, "uses")
    path = tmp_path / ".flowguard/models/m.py"
    path.write_text(path.read_text().replace('"Read": "lib.py:value"', '"Read": "lib.py:missing"'))
    broken = [
        f
        for f in run_check(tmp_path, data, inv)
        if f.code == "model_anchor_broken" and "USES Read" in f.message
    ]
    assert len(broken) == 1 and "missing" in broken[0].message


def test_new_writer_of_modeled_state_is_reported(tmp_path, monkeypatch):
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
    from flowguard.map import discover as discovery
    from flowguard.map.check import run_check
    from flowguard.map.cli import _context

    def write(path, text):
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    write("pkg/__init__.py", "")
    write(
        "pkg/proxy.py",
        """class Proxy:
    def __init__(self):
        self._parts = []
        self._map = {}
        self.label = 'only init'
    def __setitem__(self, key, value):
        self._parts[0] = value
        self._map[key] = 0
    def move_to_end(self, key):
        self._parts.append(key)
        self._map[key] = 1
    def __delitem__(self, key):
        del self._map[key]

class Other:
    def __init__(self):
        self._map = {}
    def clear(self, key):
        del self._map[key]
""",
    )
    write("other.py", "class Proxy:\n    def __delitem__(self, key):\n        del self._map[key]\n")
    model = (
        'MODEL_ID="proxy_model"\nCOMPONENTS=["proxy"]\n'
        'IMPLEMENTED_BY={"Set":"pkg/proxy.py:Proxy.__setitem__"}\n'
        "def build_explorer(): pass\n"
        "def conformance():\n    from pkg.proxy import Proxy\n    return Proxy()\n"
    )
    write(".flowguard/models/proxy.py", model)
    data = dict(
        schema="flowguard.map.v1",
        components=[
            dict(
                id="proxy",
                files=["pkg/*.py"],
                summary="Proxy ordering",
                responsibilities=["order parts"],
                tests=[],
                models=[],
                depends_on=[],
                status="draft",
            ),
            dict(
                id="other",
                files=["other.py"],
                summary="Other",
                responsibilities=["unrelated state"],
                tests=[],
                models=[],
                depends_on=[],
                status="draft",
            ),
        ],
    )
    write(".flowguard/map.json", json.dumps(data))
    current, inv = _context(tmp_path)
    raw = discover_inventory(tmp_path, inv)
    assert "Proxy.__delitem__" in raw["files"]["pkg/proxy.py"]["state"]["Proxy._map"]
    original = discovery.discover_inventory
    calls = []

    def counted(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(discovery, "discover_inventory", counted)
        warnings = [
            f for f in run_check(tmp_path, current, inv) if f.code == "model_writer_unbound"
        ]
    assert len(calls) == 1
    assert len(warnings) == 2
    assert all(f.level == "warn" and f.component == "proxy" for f in warnings)
    assert all(
        "model proxy_model" in f.message and "pkg/proxy.py:Proxy.__setitem__" in f.message
        for f in warnings
    )
    assert any("pkg/proxy.py:Proxy.move_to_end" in f.message for f in warnings)
    assert any("pkg/proxy.py:Proxy.__delitem__" in f.message for f in warnings)
    assert map_cli(tmp_path, "check").returncode == 0
    assert (
        len([f for f in run_lint(tmp_path, current, inv) if f.code == "model_writer_unbound"]) == 2
    )

    data["accepted_debts"] = [
        dict(
            code="model_writer_unbound",
            component="proxy",
            contains=symbol,
            reason="An existing ordering path awaits model extension",
            expires="9999-12-31",
        )
        for symbol in ["Proxy.move_to_end", "Proxy.__delitem__"]
    ]
    write(".flowguard/map.json", json.dumps(data))
    current, inv = _context(tmp_path)
    assert [
        f.level for f in run_check(tmp_path, current, inv) if f.code == "model_writer_unbound"
    ] == ["info", "info"]
    lint = run_lint(tmp_path, current, inv)
    assert len([f for f in lint if f.code == "model_writer_unbound" and f.level == "info"]) == 2
    assert not any(f.code == "debt_stale" for f in lint)

    # Exclusions come from every registered model, including a separate contract.
    data.pop("accepted_debts")
    separate = ".flowguard/models/proxy_writer.py"
    data["components"][0]["models"] = [separate]
    write(
        separate,
        'MODEL_ID="proxy_writer"\n'
        'IMPLEMENTED_BY={"Delete":"pkg/proxy.py:Proxy.__delitem__"}\n'
        'NOT_MODELED={"pkg/proxy.py:Proxy.move_to_end":"Ordering is covered by its direct test"}\n'
        "def build_explorer(): pass\ndef conformance(): pass\n",
    )
    write(".flowguard/map.json", json.dumps(data))
    current, inv = _context(tmp_path)
    assert not any(f.code == "model_writer_unbound" for f in run_check(tmp_path, current, inv))


def test_coverage_line_counts_explained_entrypoints(tmp_path, monkeypatch):
    import pytest, os, json
    from pathlib import Path
    from flowguard.map.views import render_show
    import sys
    import pytest
    from flowguard.map import proof
    from flowguard.map.lint import run_lint

    data, inv, marker = _fg232_view_project(tmp_path)
    before = [
        (finding.level, finding.code, finding.component, finding.message)
        for finding in run_lint(tmp_path, data, inv)
    ]
    calls = _fg232_count_discovery(monkeypatch)

    def _fg232_forbid_execution(*args, **kwargs):
        raise AssertionError("read must not execute a user model or pytest")

    with monkeypatch.context() as guard:
        for name in ("run_models", "run_model", "run_model_in_process", "_load"):
            guard.setattr(proof, name, _fg232_forbid_execution)
        guard.setattr(pytest, "main", _fg232_forbid_execution)
        focused = render_show(tmp_path, data, inv, component="subject", detail=False)
        assert len(calls) == 1
        line = next(
            line
            for line in focused.splitlines()
            if "coverage: entrypoints 2 of 4 bound (model 1, test 1), 1 by reason, 0 unlisted; state writers 1 of 2 bound (model 1, test 0), 0 by reason;"
            in line
        )
        unexplained = line.partition("; unexplained: ")[2]
        assert (
            "view232_subject.py:unexplained" in unexplained
            and "view232_subject.py:Ledger.purge" in unexplained
        )
        assert (
            "view232_subject.py:by_model" not in unexplained
            and "view232_subject.py:by_scope" not in unexplained
        )
        assert (
            "view232_subject.py:by_test" not in unexplained and "Ledger.__init__" not in unexplained
        )
        calls.clear()
        overview = render_show(tmp_path, data, inv, component=None, detail=False)
        assert len(calls) == 1
    assert (
        "coverage: entrypoints 3 of 5 bound (model 2, test 1), 1 by reason, 0 unlisted; state writers 1 of 2 bound (model 1, test 0), 0 by reason"
    ) in overview
    assert "truncated" not in overview
    after = [
        (finding.level, finding.code, finding.component, finding.message)
        for finding in run_lint(tmp_path, data, inv)
    ]
    assert after == before
    assert not marker.exists()
    assert not any(name.startswith("view232_") for name in sys.modules)


def test_replay_call_undeclared_reports_fixture_replays(tmp_path):
    from flowguard.map.replay_lint import replay_call_findings
    from flowguard.map.inventory import build_inventory
    from flowguard.map.tree import build_tree
    from flowguard.map.discover import discover_inventory

    def write(name, text):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    write(
        "native.py",
        "def entry(): return True\ndef used(): return True\ndef other(): return False\n",
    )
    write("src/surface/__init__.py", "from .bridge import used\n")
    write("src/surface/bridge.py", "from native import used\n")
    write(
        ".flowguard/models/_cases.py",
        """from surface import used
from native import other
class Replay:
    def __init__(self):
        self.callback, self.unused_callback = used, other
    def apply_step(self, event): return self.callback()
    def convenience(self): return other()
def choose(kind):
    if kind == "yes": return used()
    elif kind == "unmentioned": return other()
    else: return other()
""",
    )
    source = """import inspect
from native import other
from _cases import choose, Replay
MODEL_ID = "probe"
PARENT = "native"
IMPLEMENTED_BY = {"Entry": "native.py:entry"}
USES = {"Used": "native.py:entry"}
def build_explorer(): pass
def conformance():
    choose("yes")
    Replay()
    inspect.signature(other)
    return True

_previous_conformance = conformance
def conformance():
    return str(_previous_conformance()).strip() == "True"
"""
    write(".flowguard/models/probe.py", source)
    data = dict(
        schema="flowguard.map.v1",
        components=[
            dict(
                id="native",
                files=["native.py", "src/surface/*.py"],
                models=[],
                tests=[],
                responsibilities=["own native operations"],
                summary="Native operations",
                status="draft",
            )
        ],
    )

    def findings():
        inv = build_inventory(tmp_path, [], write_cache=False)
        tree = build_tree(tmp_path, data, inv)
        raw = discover_inventory(tmp_path, inv, data=data, write_cache=False)
        return replay_call_findings(tmp_path, data, inv, tree, raw)

    rows = findings()
    assert len(rows) == 1, rows
    assert (
        rows[0].level == "warn"
        and rows[0].code == "replay_call_undeclared"
        and rows[0].component == "probe"
    )
    assert "replays native.py:used at .flowguard/models/_cases.py:" in rows[0].message
    assert 'USES "NativeUsed": "native.py:used"' in rows[0].message
    write(
        ".flowguard/models/probe.py",
        source.replace(
            'USES = {"Used": "native.py:entry"}',
            'USES = {"Used": "native.py:entry", "NativeUsed": "native.py:used"}',
        ),
    )
    assert findings() == []
