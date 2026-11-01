"""A finished walk is not a completed set of generic checks."""

import json
from pathlib import Path
import subprocess
import sys

import pytest

from flowguard.behave.engine import audit
from flowguard.behave.report import render
from .test_explore import program

pytestmark = pytest.mark.skipif(sys.version_info < (3, 12), reason="pilot behavior needs Python 3.12")
ROOT = Path(__file__).resolve().parents[2]


def test_completed_and_capped_walks_stay_unchecked_without_generic_checks(program):
    complete = audit(program, worlds=["small"], seeds=[0], steps=2, use_cache=False)
    capped = audit(program, worlds=["small"], seeds=[0], steps=20, node_cap=2, use_cache=False)
    for result in (complete, capped):
        payload = json.loads(render(result, as_json=True))
        assert payload["verdict"] == "UNCHECKED"
        assert payload["missing_checks"] and payload["items"] == []
        assert render(result).startswith("UNCHECKED ")
    assert capped["runs"][0]["facts"]["extent"]["capped"]


def test_unproven_input_is_not_printed_as_a_finding(program):
    result = audit(program, worlds=["small"], seeds=[0], steps=1)
    result["items"] = [{"id": "forged", "matched": False}]
    assert "forged" not in render(result)
    assert json.loads(render(result, as_json=True))["items"] == []


def test_audit_cli_json_is_one_scoped_line(program):
    result = subprocess.run([sys.executable, "-m", "flowguard.behave", "audit", "--root", str(program),
                             "--world", "small", "--seeds", "0", "--steps", "2", "--json"],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert len(result.stdout.splitlines()) == 1
    assert json.loads(result.stdout)["verdict"] == "UNCHECKED"
