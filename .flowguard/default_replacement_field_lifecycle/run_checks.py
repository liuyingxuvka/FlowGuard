"""Run FlowGuard checks for default replacement and field lifecycle closure."""

from __future__ import annotations

import json
import os
from pathlib import Path

from flowguard import (
    FIELD_ROLE_METADATA,
    FIELD_ROLE_PERMISSION,
    FIELD_ROLE_PRESENTATION,
    FIELD_ROLE_STATE,
    FieldLifecyclePlan,
    FieldLifecycleRow,
    ui_content_visibility_candidate_ids_from_field_lifecycle,
)
from flowguard.formal_runner import FormalWorkflowCase, run_exact_workflow_case, run_formal_workflow_suite

import model


REQUIRED_LABELS = (
            "fields_accounted",
            "field_projection_and_disposition_done",
            "model_code_test_and_bug_repair_done",
            "freshness_and_closure_current",
            "claim_full",
)


def ui_reader_handoff_contract() -> tuple[bool, tuple[str, ...]]:
    plan = FieldLifecyclePlan(
        "ui-reader-handoff-contract",
        discovered_field_ids=(
            "field:title",
            "field:phase",
            "field:permission",
            "field:audit_trace",
        ),
        fields=(
            FieldLifecycleRow(
                "field:title",
                role=FIELD_ROLE_PRESENTATION,
                reader_ids=("ordinary-ui-view",),
            ),
            FieldLifecycleRow(
                "field:phase",
                role=FIELD_ROLE_STATE,
                reader_ids=("ordinary-ui-view",),
            ),
            FieldLifecycleRow(
                "field:permission",
                role=FIELD_ROLE_PERMISSION,
                reader_ids=("ordinary-ui-view",),
            ),
            FieldLifecycleRow(
                "field:audit_trace",
                role=FIELD_ROLE_METADATA,
                reader_ids=("audit-log",),
            ),
        ),
    )
    candidate_ids = ui_content_visibility_candidate_ids_from_field_lifecycle(
        plan,
        ui_reader_ids=("ordinary-ui-view",),
    )
    return (
        candidate_ids == ("field:title", "field:phase", "field:permission"),
        candidate_ids,
    )


def main() -> int:
    exact_ok = run_exact_workflow_case(
        "correct_default_replacement_field_lifecycle",
        workflow=model.build_correct_workflow(),
        initial_state=model.initial_state(),
        external_input_sequence=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        final_state_predicate=lambda state: state.final_claim == "full",
    )
    cases = [
        FormalWorkflowCase(workflow.name, workflow, False, required_labels=REQUIRED_LABELS)
        for workflow in model.build_broken_workflows()
    ]
    report = run_formal_workflow_suite(
        "default_replacement_field_lifecycle",
        tuple(cases),
        initial_states=(model.initial_state(),),
        external_inputs=model.BAD_CASE_EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        max_sequence_length=model.MAX_SEQUENCE_LENGTH,
        terminal_predicate=model.terminal_predicate,
        protected_error_class="old_field_disposition_gap",
    )
    handoff_ok, candidate_ids = ui_reader_handoff_contract()
    ok = exact_ok and report.ok and handoff_ok
    payload = {
        "ok": ok,
        "exact_workflow_ok": exact_ok,
        "formal_report": {
            "ok": report.ok,
            "summary": report.format_text(),
        },
        "ui_reader_handoff": {
            "ok": handoff_ok,
            "candidate_ids": list(candidate_ids),
            "excluded_backend_field_ids": ["field:audit_trace"],
        },
    }
    output_dir = Path(os.environ.get("FLOWGUARD_OUTPUT_DIR", Path(__file__).parent))
    output_dir.mkdir(parents=True, exist_ok=True)
    output_dir.joinpath("result.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    if ok:
        print("default replacement field lifecycle model checks passed")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
