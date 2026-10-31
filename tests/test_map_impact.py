"""Tests grouped by their model or native component."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
import pytest
from flowguard.map.discover import component_summary, console_scripts, discover, discover_inventory, file_facts
from flowguard.map.common import DEFAULT_IGNORE
from flowguard.map.inventory import build_inventory
from flowguard.map.lint import entrypoint_coverage_findings, run_lint, scoped_architecture_findings
from flowguard.map.scan import guess_tests, new_map, propose_components

from _fg_helpers import (
    flowguard_map_discover421_literal_fixture as literal_fixture,
)

def test_s4c_dropped_consumer_names_the_producer(tmp_path):
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
    from flowguard.map.impact import compute_impact, render_impact

    h = literal_fixture()
    data = h["fixture"](tmp_path)
    h["write"](tmp_path, "consumer.py", "def use(value): return True\n")
    impact = compute_impact(
        tmp_path,
        data,
        build_inventory(tmp_path, DEFAULT_IGNORE, write_cache=False),
        ["consumer.py"],
        base="HEAD",
    )
    assert (
        "consumer no longer handles 'stale' that producer produces at producer.py:1"
        in render_impact(impact)
    )


def test_yaml_key_rename_is_mentioned(tmp_path):
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
    from flowguard.map.impact import compute_impact, render_impact

    h = literal_fixture()
    data = h["fixture"](tmp_path)
    h["write"](tmp_path, "producer.py", 'def emit(): return {"code":"ready"}\n')
    h["write"](tmp_path, "consumer.py", 'def use(row): return row["code"]\n')
    h["write"](tmp_path, "cases.yaml", "row:\n  code: ready\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "-c",
            "user.name=FlowGuard",
            "-c",
            "user.email=model@example.invalid",
            "commit",
            "-qm",
            "keys",
        ],
        check=True,
        capture_output=True,
    )
    h["write"](tmp_path, "producer.py", 'def emit(): return {"status":"ready"}\n')
    result = compute_impact(
        tmp_path,
        data,
        build_inventory(tmp_path, DEFAULT_IGNORE, write_cache=False),
        ["producer.py"],
        base="HEAD",
    )
    text = render_impact(result)
    assert "producer no longer produces 'code' that consumer reads at consumer.py:1" in text
    assert "mentions 'code' in 1 text files: cases.yaml" in text


def test_typo_consumer_prints_nothing_produces(tmp_path):
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
    from flowguard.map.impact import compute_impact, render_impact

    h = literal_fixture()
    data = h["fixture"](tmp_path)
    h["write"](tmp_path, "consumer.py", 'def use(value): return value == "stale_typo"\n')
    impact = compute_impact(
        tmp_path,
        data,
        build_inventory(tmp_path, DEFAULT_IGNORE, write_cache=False),
        ["consumer.py"],
        base="HEAD",
    )
    text = render_impact(impact)
    assert "nothing produces 'stale_typo' in statically recognized literal sites (consumed at consumer.py:1); check the spelling or an indirect producer" in text


def test_split_that_drops_a_field_names_it(tmp_path):
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
    from flowguard.map.impact import compute_impact, render_impact

    h = literal_fixture()
    data = h["fixture"](tmp_path)
    path = tmp_path / ".flowguard/models/policy.py"
    parent = (
        path.read_text()
        .replace("retained", "replacement")
        .replace('    name="Emit"', '    name="Emit"\n    reads=()\n    writes=("replacement",)')
    )
    parent += '\nHANDOFF={"policy_child":{"replacement":"replacement"}}\n'
    path.write_text(parent)
    child = (
        parent.replace('MODEL_ID="policy"', 'MODEL_ID="policy_child"')
        .replace('PARENT="producer"', 'PARENT="policy"')
        .replace('"producer.py:emit"', '"producer.py:fold"')
        .replace("NATIVE_ARGS=()", 'NATIVE_ARGS=("stale",)')
    )
    child = child[: child.rindex("HANDOFF=")] + 'OUTPUTS={"replacement":("stale",)}\n'
    child_path = path.parent / "policy_child.py"
    child_path.write_text(child)
    with (tmp_path / "producer.py").open("a") as stream:
        stream.write("def fold(value): return value\n")
    changed = [".flowguard/models/policy.py", ".flowguard/models/policy_child.py"]
    result = compute_impact(
        tmp_path,
        data,
        build_inventory(tmp_path, DEFAULT_IGNORE, write_cache=False),
        changed,
        base="HEAD",
    )
    assert "-field retained" in render_impact(result)
    # The same split retains its old field in the child; this must remove the warning.
    child_path.write_text(child.replace("replacement", "retained"))
    path.write_text(parent.replace('"replacement":"replacement"', '"retained":"replacement"'))
    preserved = compute_impact(
        tmp_path,
        data,
        build_inventory(tmp_path, DEFAULT_IGNORE, write_cache=False),
        changed,
        base="HEAD",
    )
    assert "-field retained" not in render_impact(preserved)


def test_removing_one_of_two_bound_tests_is_named(tmp_path):
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
    from flowguard.map.impact import compute_impact, render_impact

    h = literal_fixture()
    data = h["fixture"](tmp_path)
    path = tmp_path / ".flowguard/models/policy.py"
    text = path.read_text().replace(
        '"tests/test_result.py:test_result"]',
        '"tests/test_result.py:test_result","tests/test_result.py:test_other"]',
    )
    path.write_text(text)
    with (tmp_path / "tests/test_result.py").open("a") as stream:
        stream.write("def test_other(): assert True\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "-c",
            "user.name=FlowGuard",
            "-c",
            "user.email=model@example.invalid",
            "commit",
            "-qm",
            "two bound tests",
        ],
        check=True,
        capture_output=True,
    )
    path.write_text(text.replace(',"tests/test_result.py:test_other"', ""))
    result = compute_impact(
        tmp_path,
        data,
        build_inventory(tmp_path, DEFAULT_IGNORE, write_cache=False),
        [".flowguard/models/policy.py"],
        base="HEAD",
    )
    assert len(result.promise_findings) == 1
    assert "-test safe (tests/test_result.py:test_other)" in render_impact(result)
