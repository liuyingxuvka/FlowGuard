"""Run FlowGuard checks for model-topology hazard review."""

from __future__ import annotations

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
    cases = [FormalWorkflowCase(broken.name, broken, False) for broken in model.build_broken_workflows()]
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


if __name__ == "__main__":
    raise SystemExit(main())
