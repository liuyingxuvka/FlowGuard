"""Run the existing-model preflight FlowGuard checks."""

from __future__ import annotations

from flowguard import (
    BehaviorCommitmentHit,
    ExistingModelPreflight,
    ExistingOwnershipSnapshot,
    ModelContextHit,
    REUSE_DECISION_REUSE_EXISTING,
    review_existing_model_preflight,
)
from flowguard.formal_runner import FormalWorkflowCase, run_exact_workflow_case, run_formal_workflow_suite

import model


REQUIRED_LABELS = (
    "light_existing_model_grounding",
    "full_existing_model_preflight",
    "blocked_duplicate_risk",
    "preflight_skipped_with_reason",
    "blocked_surface_inventory_incomplete",
    "blocked_affected_index_fingerprint",
    "blocked_affected_object_missing",
    "blocked_affected_ancestor_missing",
    "blocked_affected_whole_builder",
    "blocked_affected_understanding_missing",
    "blocked_implicit_whole_qualification",
)


def _model_hit(model_id: str = "minimum_valuable_model_entry") -> ModelContextHit:
    return ModelContextHit(
        model_id=model_id,
        model_path=".flowguard/minimum_valuable_model_entry/model.py",
        evidence_id="model-authority:sha256:minimum-entry",
        evidence_tier="abstract_green",
        responsibilities=("minimum entry",),
        function_blocks=("SelectMinimumEntry",),
        state_owned=("entry_state",),
        side_effects_owned=(),
        public_entrypoints=("flowguard",),
        validation_evidence=("minimum entry checks",),
    )


def _owner_projection(owner_id: str, *hits: ModelContextHit):
    return review_existing_model_preflight(
        ExistingModelPreflight(
            "owner-identity-model-check",
            "Resolve one exact current owner",
            mode="full",
            model_search_performed=True,
            search_paths=(".flowguard",),
            behavior_lookup_required=True,
            behavior_lookup_status="performed",
            primary_behavior_plane="agent_operation",
            primary_commitment_hits=(
                BehaviorCommitmentHit(
                    "commitment:minimum-entry",
                    "agent_operation",
                    owner_id,
                    100,
                ),
            ),
            ledger_fingerprint="sha256:ledger",
            relevant_models=hits,
            ownership_snapshot=ExistingOwnershipSnapshot(
                function_block_owners=(("SelectMinimumEntry", hits[0].model_id),),
            ),
            reuse_decision=REUSE_DECISION_REUSE_EXISTING,
            downstream_routes=("development_process_flow",),
            rationale="Only one exact logical, path, or fingerprint owner may be projected.",
        )
    )


def run_exact_owner_identity_review() -> bool:
    path_report = _owner_projection(
        ".flowguard/minimum_valuable_model_entry/model.py",
        _model_hit(),
    )
    wrong_report = _owner_projection(
        ".flowguard/other/minimum_valuable_model_entry/model.py",
        _model_hit(),
    )
    ambiguous_report = _owner_projection(
        ".flowguard/minimum_valuable_model_entry/model.py",
        _model_hit("minimum-entry-a"),
        _model_hit("minimum-entry-b"),
    )
    path_codes = {finding.code for finding in path_report.findings}
    wrong_codes = {finding.code for finding in wrong_report.findings}
    ambiguous_codes = {finding.code for finding in ambiguous_report.findings}
    ok = (
        "behavior_lookup_owner_model_not_projected" not in path_codes
        and "behavior_lookup_owner_model_not_projected" in wrong_codes
        and "behavior_lookup_owner_model_ambiguous" in ambiguous_codes
    )
    print(f"exact owner identity reconciliation: {'pass' if ok else 'fail'}")
    print()
    return ok


def main() -> int:
    exact_inputs = tuple(
        input_obj
        for input_obj in model.EXTERNAL_INPUTS
        if input_obj.task_id not in {
            "unhandled-duplicate",
            "omitted-same-intent-surface",
            "wrong-plane-promotion",
            "stale-spec-context",
            "mutable-spec-context",
            "over-materialized-selection",
            "affected-index-fingerprint-drift",
            "affected-object-missing",
            "affected-ancestor-missing",
            "affected-whole-builder-invoked",
            "affected-understanding-not-derived",
            "whole-qualification-implicit",
        }
    )
    exact_ok = run_exact_workflow_case(
        "correct_existing_model_preflight",
        workflow=model.build_workflow(),
        initial_state=model.initial_state(),
        external_input_sequence=exact_inputs,
        invariants=model.INVARIANTS,
        final_state_predicate=lambda state: not state.blocked
        and len(state.route_selected) == len(exact_inputs),
    )
    report = run_formal_workflow_suite(
        "existing_model_preflight",
        (
            FormalWorkflowCase(
                "broken_bypasses_existing_model_search",
                model.build_workflow(search_block=model.BrokenBypassSearch()),
                False,
            ),
            FormalWorkflowCase(
                "broken_uses_light_grounding_for_full_work",
                model.build_workflow(search_block=model.BrokenLightForFull()),
                False,
            ),
            FormalWorkflowCase(
                "broken_ignores_same_intent_surface_inventory",
                model.build_workflow(search_block=model.BrokenIgnoresSurfaceInventory()),
                False,
            ),
            FormalWorkflowCase(
                "broken_promotes_related_plane_context",
                model.build_workflow(search_block=model.BrokenPromotesRelatedPlane()),
                False,
            ),
            FormalWorkflowCase(
                "broken_preflight_claims_implementation_ready",
                model.build_workflow(
                    search_block=model.BrokenPreflightAsImplementationReadiness()
                ),
                False,
                required_labels=("broken_preflight_inferred_implementation_ready",),
            ),
            FormalWorkflowCase(
                "stale_spec_context_blocks",
                model.build_workflow(search_block=model.BrokenIgnoresSurfaceInventory()),
                False,
                required_labels=("broken_grounded_from_caller_selected_surface_subset",),
                external_inputs=(
                    next(item for item in model.EXTERNAL_INPUTS if item.task_id == "stale-spec-context"),
                ),
                max_sequence_length=3,
            ),
            FormalWorkflowCase(
                "broken_accepts_stale_affected_index",
                model.build_workflow(
                    search_block=model.BrokenAcceptsUnverifiedBlueprintScope()
                ),
                False,
                required_labels=("broken_accepts_affected_index_fingerprint_drift",),
                external_inputs=(
                    next(
                        item
                        for item in model.EXTERNAL_INPUTS
                        if item.task_id == "affected-index-fingerprint-drift"
                    ),
                ),
                max_sequence_length=3,
            ),
            FormalWorkflowCase(
                "broken_accepts_missing_affected_object",
                model.build_workflow(
                    search_block=model.BrokenAcceptsUnverifiedBlueprintScope()
                ),
                False,
                required_labels=("broken_accepts_missing_affected_object",),
                external_inputs=(
                    next(
                        item
                        for item in model.EXTERNAL_INPUTS
                        if item.task_id == "affected-object-missing"
                    ),
                ),
                max_sequence_length=3,
            ),
            FormalWorkflowCase(
                "broken_accepts_missing_affected_ancestor",
                model.build_workflow(
                    search_block=model.BrokenAcceptsUnverifiedBlueprintScope()
                ),
                False,
                required_labels=("broken_accepts_missing_affected_ancestor",),
                external_inputs=(
                    next(
                        item
                        for item in model.EXTERNAL_INPUTS
                        if item.task_id == "affected-ancestor-missing"
                    ),
                ),
                max_sequence_length=3,
            ),
            FormalWorkflowCase(
                "broken_accepts_whole_builder_on_affected_path",
                model.build_workflow(
                    search_block=model.BrokenAcceptsUnverifiedBlueprintScope()
                ),
                False,
                required_labels=("broken_accepts_affected_whole_builder",),
                external_inputs=(
                    next(
                        item
                        for item in model.EXTERNAL_INPUTS
                        if item.task_id == "affected-whole-builder-invoked"
                    ),
                ),
                max_sequence_length=3,
            ),
            FormalWorkflowCase(
                "broken_accepts_missing_affected_understanding",
                model.build_workflow(
                    search_block=model.BrokenAcceptsUnverifiedBlueprintScope()
                ),
                False,
                required_labels=("broken_accepts_missing_affected_understanding",),
                external_inputs=(
                    next(
                        item
                        for item in model.EXTERNAL_INPUTS
                        if item.task_id == "affected-understanding-not-derived"
                    ),
                ),
                max_sequence_length=3,
            ),
            FormalWorkflowCase(
                "broken_accepts_implicit_whole_qualification",
                model.build_workflow(
                    search_block=model.BrokenAcceptsUnverifiedBlueprintScope()
                ),
                False,
                required_labels=("broken_accepts_implicit_whole_qualification",),
                external_inputs=(
                    next(
                        item
                        for item in model.EXTERNAL_INPUTS
                        if item.task_id == "whole-qualification-implicit"
                    ),
                ),
                max_sequence_length=3,
            ),
        ),
        initial_states=(model.initial_state(),),
        external_inputs=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        max_sequence_length=model.MAX_SEQUENCE_LENGTH,
        terminal_predicate=model.terminal_predicate,
        required_labels=REQUIRED_LABELS,
        protected_error_class="existing_model_preflight_bypassed",
    )
    owner_identity_ok = run_exact_owner_identity_review()
    return 0 if exact_ok and report.ok and owner_identity_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
