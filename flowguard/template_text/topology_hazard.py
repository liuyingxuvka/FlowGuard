"""Contract-model template built from the existing review kit."""

TOPOLOGY_HAZARD_MODEL_TEMPLATE = '''"""Review a behavior model's topology, with explicit old/new path dispositions.
Replace the example: import the behavior model at top level, set PARENT to its MODEL_ID,
and use its build_explorer().workflow, initial_states and external_inputs in plan().
This example makes a local in-memory claim. Use the real UsageIntent and external effects
of the reviewed model, then resolve the resulting hazards without inventing external proof.
Fill current code/test anchors before running map models topology_hazard.
"""
from dataclasses import dataclass, replace
from pathlib import Path
from flowguard import (BusinessPathIdentity, FunctionResult, TOPOLOGY_USAGE_LOCAL, UsageIntent,
                       Workflow, infer_topology_hazard_plan, review_topology_hazards)
from flowguard.kit import plan_explorer
from flowguard.map.facts import CodeFacts

MODEL_ID = "topology_hazard"
IMPLEMENTED_BY = {"Owner": "REPLACE_ME/module.py:Owner"}
TESTED_BY = {"topology_review_accepts": ["REPLACE_ME/test_x.py:test_name"]}
ROOT = Path(__file__).resolve().parents[2]
# import behavior_model
# PARENT = "<behavior model MODEL_ID>"


@dataclass(frozen=True)
class Event:
    action: str = "submit"


@dataclass(frozen=True)
class State:
    record: str = ""


class SaveRecord:
    name = "SaveRecord"
    reads = ()
    writes = ("record",)
    side_effects = ()  # This example updates memory; declare actual external effects in your model.
    def apply(self, inp, state):
        return (FunctionResult(inp, State("saved"), label="saved"),)


def plan():
    paths = (BusinessPathIdentity("current", business_intent="save record", trigger="submit",
                 expected_terminal="saved", source_labels=(IMPLEMENTED_BY["Owner"],),
                 supersedes=("previous",), compatibility_disposition="preserve_compatibility",
                 exclusive_with=("previous",)),
             BusinessPathIdentity("previous", business_intent="save record", trigger="submit",
                 expected_terminal="saved", source_labels=(IMPLEMENTED_BY["Owner"],), exclusive_with=("current",)))
    return _with_paths(paths)


def _with_paths(paths):
    result = infer_topology_hazard_plan(workflow=Workflow((SaveRecord(),)), initial_states=(State(),),
        external_inputs=(Event(),), business_paths=paths,
        usage_intent=UsageIntent(usage_modes=(TOPOLOGY_USAGE_LOCAL,), final_claim="local"))
    # This review model requires explicit dispositions rather than scoped unresolved hazards.
    return replace(result, allow_scoped_confidence=False)


def duplicate_paths(value):
    return _with_paths(tuple(replace(path, exclusive_with=(), supersedes=(), compatibility_disposition="unknown") for path in value.digest.business_paths))


def old_path_without_disposition(value):
    current, previous = value.digest.business_paths
    return _with_paths((replace(current, compatibility_disposition="unknown"), previous))


EDITS = {"declare_paths": lambda value: value, "duplicate_paths": duplicate_paths,
         "old_path_without_disposition": old_path_without_disposition}


def build_explorer():
    return plan_explorer(plan, EDITS, review_topology_hazards, explore=["declare_paths"],
                         invariant_name="topology_review_accepts")


def broken_variants():
    return {name: plan_explorer(plan, EDITS, review_topology_hazards, explore=[name],
                               invariant_name="topology_review_accepts")
            for name in ("duplicate_paths", "old_path_without_disposition")}


def conformance():
    facts = CodeFacts(ROOT)
    facts.anchors_exist(IMPLEMENTED_BY)
    return facts.report()
'''

__all__ = ["TOPOLOGY_HAZARD_MODEL_TEMPLATE"]
