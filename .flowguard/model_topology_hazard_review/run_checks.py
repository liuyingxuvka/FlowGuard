"""Run FlowGuard checks for model-topology hazard review."""

from __future__ import annotations

from flowguard import (
    Explorer,
    TOPOLOGY_CONFIDENCE_BLOCKED,
    TOPOLOGY_DISPOSITION_BLOCKED,
    TOPOLOGY_SEVERITY_BLOCKER,
    TopologyHazardCandidate,
    TopologyHazardReviewPlan,
    UsageIntent,
    Workflow,
    infer_topology_digest,
    review_topology_hazards,
)
import model


class EffectBlock:
    name = "EffectBlock"
    reads = ("phase",)
    writes = ("saved_record",)
    side_effects = ("database_write",)

    def apply(self, input_obj, state):
        return ()


def run_workflow(name: str, workflow, *, expect_ok: bool) -> bool:
    report = Explorer(
        workflow=workflow,
        initial_states=(model.initial_state(),),
        external_inputs=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        max_sequence_length=model.MAX_SEQUENCE_LENGTH,
        terminal_predicate=model.terminal_predicate,
        required_labels=(
            "anchor_observed",
            "anchored_hazard_inferred",
            "required_route_created",
            "hazard_handled_or_scoped",
            "compatibility_disposition_chosen",
            "full_claim_accepted",
            "scoped_or_blocked_claim",
        ),
    ).explore()
    ok = report.ok
    print(f"{name}: {'OK' if ok else 'VIOLATION'}")
    print(report.format_text(max_examples=1))
    print()
    return ok is expect_ok


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
    workflow_checks = [
        run_workflow("correct_topology_hazard_review", model.build_correct_workflow(), expect_ok=True)
    ]
    for broken in model.build_broken_workflows():
        workflow_checks.append(run_workflow(broken.name, broken, expect_ok=False))
    helper_checks = run_helper_cases()
    return 0 if all(workflow_checks) and helper_checks else 1


if __name__ == "__main__":
    raise SystemExit(main())
