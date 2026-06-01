"""Template text for model-topology hazard review."""

TOPOLOGY_HAZARD_MODEL_TEMPLATE = '''"""FlowGuard model-topology hazard review template.

FlowGuard Risk Purpose Header
Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: review model topology for future-use hazards before broad confidence.
Guards against: generic AI risk checklists, unanchored future-risk warnings,
old/new path disposition gaps, coarse terminal states, and local green evidence
being overclaimed for future use.
Use before editing: when local FlowGuard evidence passes but topology shape may
still imply future-use hazards.
Run: python .flowguard/model_topology_hazard_review/run_checks.py
"""

from __future__ import annotations

from dataclasses import dataclass

from flowguard import (
    FunctionResult,
    TOPOLOGY_USAGE_RELEASE,
    UsageIntent,
    Workflow,
    infer_topology_hazard_plan,
    review_topology_hazards,
)


@dataclass(frozen=True)
class Event:
    action: str = "submit"


@dataclass(frozen=True)
class State:
    phase: str = "idle"
    saved_record: str = ""


class SaveRecord:
    name = "SaveRecord"
    reads = ("phase",)
    writes = ("saved_record", "phase")
    side_effects = ("database_write",)

    def apply(self, input_obj, state):
        return (FunctionResult(input_obj, State("done", "saved"), label="saved"),)


def build_review():
    plan = infer_topology_hazard_plan(
        workflow=Workflow((SaveRecord(),), name="save-record"),
        initial_states=(State(),),
        external_inputs=(Event(),),
        usage_intent=UsageIntent(usage_modes=(TOPOLOGY_USAGE_RELEASE,), final_claim="release"),
    )
    return review_topology_hazards(plan)
'''

TOPOLOGY_HAZARD_RUN_CHECKS_TEMPLATE = '''"""Run the model-topology hazard review template."""

from __future__ import annotations

import model


def main() -> int:
    report = model.build_review()
    print(report.format_text())
    return 0 if not report.ok and report.unresolved_hazard_ids else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''

TOPOLOGY_HAZARD_NOTES_TEMPLATE = """# FlowGuard Model Topology Hazard Review Notes

This review is not a generic risk checklist. It starts from the model topology:
states, edges, side effects, terminal states, old/new paths, external
boundaries, and parent/child compression. Future-use hazards should be promoted
only when they name a concrete topology anchor.

Use this route before broad done/release/publish confidence when model shape and
usage intent suggest hidden future-use risk. Unanchored AI concerns remain
observations. Anchored unresolved hazards route to Model Maturation, Model-Test
Alignment, DevelopmentProcessFlow, Architecture Reduction, or Risk Evidence
Ledger.
"""
