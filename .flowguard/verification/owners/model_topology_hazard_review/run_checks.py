"""Run FlowGuard checks for model-topology hazard review."""

from __future__ import annotations

from pathlib import Path
import os
import sys

_FLOWGUARD_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_FLOWGUARD_MODEL_ROOT = _FLOWGUARD_PROJECT_ROOT / ".flowguard" / "models" / "owners" / "model_topology_hazard_review"
for _flowguard_path in (_FLOWGUARD_PROJECT_ROOT, _FLOWGUARD_MODEL_ROOT):
    if str(_flowguard_path) not in sys.path:
        sys.path.insert(0, str(_flowguard_path))

from pathlib import Path
import sys


from flowguard import (
    TOPOLOGY_CONFIDENCE_BLOCKED,
    TOPOLOGY_DISPOSITION_BLOCKED,
    TOPOLOGY_SEVERITY_BLOCKER,
    TopologyHazardCandidate,
    TopologyHazardReviewPlan,
    UsageIntent,
    Workflow,
    infer_topology_digest,
    review_topology_hazards,
    run_exact_sequence,
)
from flowguard.formal_runner import FormalWorkflowCase, run_formal_workflow_suite
import model


class EffectBlock:
    name = "EffectBlock"
    reads = ("phase",)
    writes = ("saved_record",)
    side_effects = ("database_write",)

    def apply(self, input_obj, state):
        return ()


REQUIRED_LABELS = (
    "anchor_observed",
    "anchored_hazard_inferred",
    "required_route_created",
    "hazard_handled_or_scoped",
    "compatibility_disposition_chosen",
    "full_claim_accepted",
    "scoped_or_blocked_claim",
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
        and exact.final_states[0].final_claim == "full"
    )
    print(
        "correct_topology_hazard_review: "
        + ("observed=OK expected=OK match=yes exact=yes" if exact_ok else "observed=VIOLATION expected=OK match=no")
    )
    # Each known-bad variant has a minimal finite counterexample.  Running
    # every five-step Cartesian sequence for every broken workflow repeats the
    # same invariant violation and can dominate the owner runtime.  Keep the
    # adversarial boundary explicit: the unanchored gate fails on its first
    # action, the route omission needs anchor -> infer -> claim, and the
    # compatibility omission needs legacy-history -> claim.
    max_length_by_case = {
        "topology_hazard_unanchored_hard_gate": 1,
        "topology_hazard_full_without_route": 3,
        "topology_hazard_compatibility_ignored": 2,
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
        "model_topology_hazard_review",
        tuple(cases),
        initial_states=(model.initial_state(),),
        external_inputs=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        max_sequence_length=model.MAX_SEQUENCE_LENGTH,
        terminal_predicate=model.terminal_predicate,
        required_labels=REQUIRED_LABELS,
        protected_error_class="topology_hazard_not_handled",
    )
    return exact_ok and report.ok


def helper_case(name: str, plan: TopologyHazardReviewPlan, *, expect_ok: bool) -> bool:
    report = review_topology_hazards(plan)
    ok = report.ok is expect_ok
    print(f"{name}: {'OK' if ok else 'VIOLATION'}")
    print(report.format_text())
    print()
    return ok


def run_helper_cases() -> bool:
    digest = infer_topology_digest(
        workflow=Workflow((EffectBlock(),), name="effect"),
        external_inputs=("event",),
        usage_intent=UsageIntent(usage_modes=("release",), final_claim="release"),
    )
    return all(
        (
            helper_case(
                "unanchored_hazard_is_observation",
                TopologyHazardReviewPlan(
                    "unanchored",
                    digest=digest,
                    candidates=(
                        TopologyHazardCandidate(
                            "hazard:generic",
                            "generic warning with no anchor",
                            disposition=TOPOLOGY_DISPOSITION_BLOCKED,
                            confidence_effect=TOPOLOGY_CONFIDENCE_BLOCKED,
                            severity=TOPOLOGY_SEVERITY_BLOCKER,
                        ),
                    ),
                    auto_generate_candidates=False,
                ),
                expect_ok=True,
            ),
            helper_case(
                "anchored_side_effect_blocks_release",
                TopologyHazardReviewPlan("anchored", digest=digest),
                expect_ok=False,
            ),
        )
    )


def main() -> int:
    workflow_checks = run_workflow_suite()
    helper_checks = run_helper_cases()
    return 0 if workflow_checks and helper_checks else 1

from flowguard.native_case_runner import native_main
if __name__ == "__main__":
    # Native evidence must never scan the repository root.  A root-level
    # default re-ingests historical model/receipt JSON and turns this finite
    # owner into an apparently non-terminating run.  Keep an invocation-local
    # controlled workspace unless the caller deliberately supplies one.
    os.environ.setdefault(
        "FLOWGUARD_OUTPUT_DIR",
        str(
            _FLOWGUARD_PROJECT_ROOT
            / "work"
            / "flowguard"
            / "native-owner-tests"
            / f"model-topology-hazard-review-{os.getpid()}"
        ),
    )
    raise SystemExit(native_main("model:model_topology_hazard_review", main))
