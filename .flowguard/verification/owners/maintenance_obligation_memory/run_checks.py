"""Run FlowGuard checks for maintenance obligation memory."""

from __future__ import annotations

from pathlib import Path
import sys

_FLOWGUARD_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_FLOWGUARD_MODEL_ROOT = _FLOWGUARD_PROJECT_ROOT / ".flowguard" / "models" / "owners" / "maintenance_obligation_memory"
for _flowguard_path in (_FLOWGUARD_PROJECT_ROOT, _FLOWGUARD_MODEL_ROOT):
    if str(_flowguard_path) not in sys.path:
        sys.path.insert(0, str(_flowguard_path))

from pathlib import Path
import sys


from flowguard import (
    OBLIGATION_STATUS_RESOLVED,
    MaintenanceObligation,
    build_maintenance_obligation_report,
    run_exact_sequence,
)
from flowguard.formal_runner import FormalWorkflowCase, run_formal_workflow_suite
import model


STRUCTURE_MESH_OWNER_ROUTE = "structure_mesh_maintenance"


REQUIRED_LABELS = (
    "anchored_obligation_recorded",
    "unanchored_observation_recorded",
    "anchor_touched",
    "owner_evidence_recorded",
    "scoped_claim_only",
    "full_claim_accepted",
)


def run_workflow_suite() -> bool:
    exact = run_exact_sequence(
        workflow=model.build_correct_workflow(),
        initial_state=model.initial_state(),
        external_input_sequence=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
    )
    exact_ok = (
        exact.model_report.ok
        and len(exact.final_states) == 1
        and exact.final_states[0].broad_claim == "full_accepted"
    )
    print(
        "correct_maintenance_obligation_memory: "
        + ("observed=OK expected=OK match=yes exact=yes" if exact_ok else "observed=VIOLATION expected=OK match=no")
    )
    # Each known-bad variant has a minimal finite counterexample.  Replaying
    # every five-step Cartesian sequence for every broken workflow only
    # duplicates the same invariant violation and can consume gigabytes while
    # producing no stronger proof.  Keep the adversarial boundary explicit:
    # the first three defects fail on their recording action, while the broad
    # claim defect needs the record-then-claim pair.
    max_length_by_case = {
        "maintenance_obligation_missing_owner_route": 1,
        "maintenance_obligation_hard_gated_observation": 1,
        "maintenance_obligation_self_resolved": 1,
        "maintenance_obligation_bad_claim": 2,
    }
    cases = [
        FormalWorkflowCase(
            broken.name,
            broken,
            False,
            max_sequence_length=max_length_by_case[broken.name],
        )
        for broken in model.build_broken_workflows()
    ]
    report = run_formal_workflow_suite(
        "maintenance_obligation_memory",
        tuple(cases),
        initial_states=(model.initial_state(),),
        external_inputs=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        max_sequence_length=model.MAX_SEQUENCE_LENGTH,
        terminal_predicate=model.terminal_predicate,
        # These are expected-bad cases; their contract is the invariant
        # counterexample itself, not reachability of every positive label.
        # The canonical positive sequence above and helper cases cover the
        # positive labels without re-running the Cartesian product.
        required_labels=(),
        protected_error_class="maintenance_obligation_not_remembered",
    )
    return exact_ok and report.ok


def helper_case(name: str, ok: bool, text: str) -> bool:
    print(f"{name}: {'OK' if ok else 'VIOLATION'}")
    print(text)
    print()
    return ok


def run_helper_cases() -> bool:
    open_obligation = MaintenanceObligation(
        "structure:checkout",
        owner_route=STRUCTURE_MESH_OWNER_ROUTE,
        reason_code="large_module",
        anchor_paths=("flowguard/checkout.py",),
    )
    open_report = build_maintenance_obligation_report(
        "self-model-open-obligation",
        (open_obligation,),
    )

    resolved_obligation = MaintenanceObligation(
        "structure:checkout",
        owner_route=STRUCTURE_MESH_OWNER_ROUTE,
        reason_code="large_module",
        status=OBLIGATION_STATUS_RESOLVED,
        evidence_ids=("structuremesh:passed",),
    )
    resolved_report = build_maintenance_obligation_report(
        "self-model-resolved-obligation",
        (resolved_obligation,),
    )

    return all(
        (
            helper_case(
                "anchored_obligation_remains_a_route_owned_action",
                open_report.open_required_obligation_ids == ("structure:checkout",)
                and open_obligation.has_anchor(),
                open_report.format_text(),
            ),
            helper_case(
                "owner_evidence_resolves_the_route_owned_obligation",
                not resolved_report.open_required_obligation_ids
                and resolved_obligation.has_resolution_evidence(),
                resolved_report.format_text(),
            ),
        )
    )


def main() -> int:
    workflow_checks = run_workflow_suite()
    helper_checks = run_helper_cases()
    return 0 if workflow_checks and helper_checks else 1

from flowguard.map.runner import run_owner
if __name__ == "__main__":
    raise SystemExit(run_owner(main))
