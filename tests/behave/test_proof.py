"""Fresh evidence, shipped replay and current-code reproof."""

import sys

import pytest

from flowguard.behave.engine import audit, content_identity, prove
from flowguard.behave.project import replay
from flowguard.behave.report import item_id
from flowguard.behave.skeleton import derive
from flowguard.behave.why import why
from .test_explore import program, goal

pytestmark = pytest.mark.skipif(sys.version_info < (3, 12), reason="pilot behavior needs Python 3.12")


def test_observed_witness_uses_a_new_child_and_why_rechecks_current_code(program):
    result = audit(program, worlds=["small"], seeds=[0], steps=2, use_cache=False)
    assert not result["errors"]
    run = result["runs"][0]["facts"]
    witness = next(row for row in run["witnesses"] if row["semantic"].get("kind") == "action" and row["semantic"].get("outcome") == "success")
    proof = prove(program, witness)
    assert proof["matched"]
    assert proof["proof"]["execution"]["child_pid"] != run["execution"]["child_pid"]
    assert why(program, proof["id"])["matched"]
    path = program / "program.py"
    path.write_text(path.read_text().replace('        self._value += 1', '        raise Refusal("fixed implementation")'))
    changed = why(program, proof["id"])
    assert not changed["matched"] and changed["state"] == "no-longer-reproduces"


def test_test_setting_witness_cannot_clear_a_shipped_goal(program):
    candidate = {"semantic": goal(4), "start": {"world": "small", "settings": {"ceiling": 8}},
                 "prefix": [{"name": "advance", "args": ["U1"]}] * 4, "outcomes": ["success"] * 4}
    result = prove(program, candidate)
    assert not result["matched"]
    assert result["ignored_settings"] == {"ceiling": 8}
    assert result["proof"]["divergence"] == 3


def test_private_edits_and_nonreproducing_same_input_claims_are_not_proofs(program):
    private = {"semantic": goal(1), "prefix": [{"name": "_value", "args": [1]}], "start": {"world": "small"}}
    assert prove(program, private)["state"] == "engine-defect"
    spec = derive(program)
    initial = replay(spec, [], {"world": "small"})
    impossible = {"semantic": goal(9), "prefix": [], "start": {"world": "small"},
                  "identity": content_identity(spec), "footprint": initial["footprint"]}
    result = prove(program, impossible)
    assert not result["matched"] and result["state"] == "engine-defect"


def test_semantic_ids_ignore_seed_and_incidental_trace_metadata():
    semantic = goal(2)
    assert item_id(semantic) == item_id({**semantic, "seed": 99, "prefix": [{"name": "extra"}], "timestamp": "later"})
    assert item_id(semantic) != item_id(goal(3))
