"""Run the permanent user-facing diagram projection model checks."""

from __future__ import annotations

from flowguard import run_exact_sequence

import model


def run_case(workflow, sequence):
    return run_exact_sequence(
        workflow=workflow,
        initial_state=model.initial_state(),
        external_input_sequence=sequence,
        invariants=model.INVARIANTS,
    )


def accepted(run, expected_status: str) -> bool:
    return (
        run.model_report.ok
        and len(run.final_states) == 1
        and run.final_states[0].projection_claim == "accepted"
        and run.final_states[0].projection_status == expected_status
    )


def rejected(run, expected_status: str) -> bool:
    return (
        run.model_report.ok
        and len(run.final_states) == 1
        and run.final_states[0].projection_claim == "rejected"
        and run.final_states[0].projection_status == expected_status
    )


def print_case(name: str, run, expected_ok: bool) -> None:
    observed_ok = run.model_report.ok
    verdict = observed_ok if expected_ok else not observed_ok
    print(f"{name}: {'OK' if verdict else 'UNEXPECTED'}")
    print(run.model_report.format_text(max_examples=1))
    print()


def main() -> int:
    projected = run_case(model.build_correct_workflow(), model.GOOD_SEQUENCE)
    reordered = run_case(model.build_correct_workflow(), model.REORDERED_SEQUENCE)
    skipped = run_case(model.build_correct_workflow(), model.SKIP_SEQUENCE)
    not_applicable = run_case(
        model.build_correct_workflow(),
        model.NOT_APPLICABLE_SEQUENCE,
    )
    stale_rejected = run_case(model.build_correct_workflow(), model.STALE_SEQUENCE)

    broken_mismatch = run_case(
        model.build_broken_model_mismatch_workflow(),
        model.GOOD_SEQUENCE,
    )
    broken_evidence = run_case(
        model.build_broken_evidence_substitution_workflow(),
        model.GOOD_SEQUENCE,
    )
    broken_edges = run_case(
        model.build_broken_edge_semantics_workflow(),
        model.GOOD_SEQUENCE,
    )
    broken_stale = run_case(
        model.build_broken_stale_reuse_workflow(),
        model.STALE_SEQUENCE,
    )

    print_case("correct_deterministic_projection", projected, True)
    print_case("correct_reordered_source_projection", reordered, True)
    print_case("correct_explicit_skip", skipped, True)
    print_case("correct_not_applicable", not_applicable, True)
    print_case("correct_source_change_rejects_stale_projection", stale_rejected, True)
    print_case("broken_diagram_model_mismatch", broken_mismatch, False)
    print_case("broken_diagram_as_checker_evidence", broken_evidence, False)
    print_case("broken_route_edge_semantics_lost", broken_edges, False)
    print_case("broken_stale_diagram_reused", broken_stale, False)

    deterministic = (
        accepted(reordered, "current")
        and projected.final_states[0].source_fingerprint
        == reordered.final_states[0].source_fingerprint
        and projected.final_states[0].projection_fingerprint
        == reordered.final_states[0].projection_fingerprint
        and projected.final_states[0].mermaid_text
        == reordered.final_states[0].mermaid_text
        and "&lt;model&gt;" in projected.final_states[0].mermaid_text
        and "&#124;" in projected.final_states[0].mermaid_text
        and "&quot;current&quot;" in projected.final_states[0].mermaid_text
    )
    ok = (
        accepted(projected, "current")
        and deterministic
        and accepted(skipped, "skipped")
        and accepted(not_applicable, "not_applicable")
        and rejected(stale_rejected, "stale")
        and not broken_mismatch.model_report.ok
        and not broken_evidence.model_report.ok
        and not broken_edges.model_report.ok
        and not broken_stale.model_report.ok
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
