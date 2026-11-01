"""Text facts accompany real commands without becoming behavior findings or state."""

import json
from pathlib import Path
import sys

import pytest

from flowguard.behave import __main__ as entry
from flowguard.behave.engine import audit
from .test_gc6_crash import CSV_PROGRAM

pytestmark = pytest.mark.skipif(sys.version_info < (3, 12), reason="pilot init/audit require Python 3.12")


def test_init_audit_and_text_view_report_without_creating_a_rule_registry(tmp_path, capsys):
    (tmp_path / "library.py").write_text(
        'raise RuntimeError("the text report imported the application")\n'
        'def convert(value): return value + 1\n')
    passage = "Always preserve the original source label when returning the artifact.\n"
    (tmp_path / "README.md").write_text(passage + "Use `missing_name` in `library.py`.\n")
    (tmp_path / "GUIDE.md").write_text(passage)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    assert entry.main(["init", "--root", str(tmp_path)]) == 0
    assert capsys.readouterr().out.startswith("NO SKELETON:")
    assert entry.main(["audit", "--root", str(tmp_path), "--json"]) == 0
    reported = json.loads(capsys.readouterr().out)
    assert reported["word"] == "UNCHECKED" and not reported["items"]
    assert isinstance(reported["textrules"], dict)
    assert entry.main(["where", "--text", "--root", str(tmp_path), "--json"]) == 0
    assert isinstance(json.loads(capsys.readouterr().out)["textrules"], dict)
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before


def test_text_changes_do_not_add_or_clear_actual_behavior_findings(tmp_path):
    (tmp_path / "program.py").write_text(CSV_PROGRAM)
    options = dict(worlds=["small"], seeds=[0], steps=1, node_cap=8, alphabet_cap=16)
    first = audit(tmp_path, **options)
    (tmp_path / "README.md").write_text("The `old_missing_name` rule has a separate original source.\n")
    changed = audit(tmp_path, **options)
    assert first["items"] and {row["id"] for row in first["items"]} == {row["id"] for row in changed["items"]}
    assert all(row["label"] == "CRASH" for row in changed["items"])
    assert "textrules" in changed and not (tmp_path / "rules.json").exists()
