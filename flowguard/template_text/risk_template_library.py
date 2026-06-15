"""Template text for the FlowGuard risk template library route."""

from __future__ import annotations

RISK_TEMPLATE_LIBRARY_MODEL_TEMPLATE = '''"""FlowGuard Risk Purpose Header.

Created with FlowGuard:
https://github.com/liuyingxuvka/FlowGuard

Purpose:
Shows how to search packaged public risk templates, record template reuse, and
prepare a local candidate template for a reusable minimum valuable model.

Guards against:
- generating a model without checking public/local reusable risk templates;
- claiming completion without evidence or a known-bad case;
- harvesting a project-specific note instead of an abstract reusable template.

Use before editing:
model-first entry prompts, local risk template library behavior, template
harvest rules, or public starter examples.

Run:
python .flowguard/risk_template_library/run_checks.py

Replace this sample risk with the workflow under review.
"""

from __future__ import annotations

from flowguard import (
    KnownBadProof,
    MinimumModelContract,
    TemplateHarvestReview,
    TemplateReuseReview,
    harvest_risk_template_candidate,
    review_minimum_model_contract,
    review_template_harvest_closure,
    search_risk_templates,
)


def search_public_templates():
    return search_risk_templates(
        "complete after ACK without output evidence",
        workflow_families=("task", "work_package"),
        protected_error_classes=("premature_completion",),
        include_local=False,
    )


def minimum_contract():
    return MinimumModelContract(
        protected_error_classes=("premature_completion",),
        modeled_state=("pending", "evidence_recorded", "completed"),
        modeled_side_effects=("output_write",),
        completion_evidence=("durable_output_ref",),
        known_bad_cases=("ack_without_output_marked_completed",),
    )


def known_bad_proofs():
    return (
        KnownBadProof(
            "ack_without_output_marked_completed",
            protected_error_class="premature_completion",
            method="broken_workflow_variant",
            observed_status="failed",
            observed_failure="ACK-only completion variant lacks durable output evidence",
            evidence_id="risk-template-library:known-bad",
        ),
    )


def template_reuse_review():
    search = search_public_templates()
    used = (search.matches[0].template.template_id,) if search.matches else ()
    return TemplateReuseReview(
        used_template_ids=used,
        searched_layers=("public", "local"),
        match_template_ids=used,
    )


def candidate_harvest(write=False):
    return harvest_risk_template_candidate(
        template_id="completion-requires-evidence-sample",
        title="Completion requires durable output evidence",
        summary="A completed state must not be set from ACK-only evidence.",
        workflow_families=("task", "work_package"),
        protected_error_classes=("premature_completion",),
        required_state=("pending", "evidence_recorded", "completed"),
        required_side_effects=("output_write",),
        required_evidence=("durable_output_ref",),
        known_bad_cases=("ack_without_output_marked_completed",),
        known_bad_proofs=known_bad_proofs(),
        merge_keys=("completion", "evidence", "ack"),
        write=write,
    )


def harvest_closure_review():
    search = search_public_templates()
    linked = (search.matches[0].template.template_id,) if search.matches else ()
    review = TemplateHarvestReview(
        disposition="duplicate_linked" if linked else "not_harvestable",
        linked_template_ids=linked,
        not_harvestable_reason="" if linked else "no_new_pattern",
    )
    return review, review_template_harvest_closure(review)


def run_checks():
    return (
        search_public_templates(),
        review_minimum_model_contract(
            minimum_contract(),
            template_reuse_review=template_reuse_review(),
        ),
        candidate_harvest(write=False),
        *harvest_closure_review(),
    )
'''

RISK_TEMPLATE_LIBRARY_RUN_CHECKS_TEMPLATE = '''"""Run the Risk Template Library template."""

from model import run_checks


def main() -> int:
    search, review, harvest, harvest_review, closure = run_checks()
    print(search.format_text())
    print()
    print(review.format_text())
    print()
    print(harvest.format_text())
    print()
    print(harvest_review.format_text())
    print()
    print(closure.format_text())
    return 0 if search.matches and review.ok and review.status == "pass" and harvest.ok and closure.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''

RISK_TEMPLATE_LIBRARY_NOTES_TEMPLATE = """# FlowGuard Risk Template Library Notes

Use this scaffold when a model should reuse public/package templates and close
the harvest loop by writing, merging, linking, or explicitly not harvesting a
per-machine local candidate template.

Default layers:

- packaged public templates shipped with FlowGuard;
- per-machine local templates under FlowGuard's portable user data root, or the
  `FLOWGUARD_TEMPLATE_LIBRARY_ROOT` override.

Do not store project source code or private payloads in local templates. Save
abstract protected error classes, required state, side effects, completion
evidence, known-bad cases, and current proof that the known-bad case is caught.
"""

__all__ = [
    "RISK_TEMPLATE_LIBRARY_MODEL_TEMPLATE",
    "RISK_TEMPLATE_LIBRARY_RUN_CHECKS_TEMPLATE",
    "RISK_TEMPLATE_LIBRARY_NOTES_TEMPLATE",
]
