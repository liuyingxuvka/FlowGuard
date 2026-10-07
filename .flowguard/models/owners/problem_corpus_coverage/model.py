"""Native source model for executable corpus aggregation and coverage gates.

Purpose: a complete benchmark denominator must not hide failed/unknown results,
missing case kinds or bug classes, or insufficient declared variant depth.
This model runs the real finite checked-in corpus once, then independently
tests the report algorithms against named mutations of those actual results.
It proves those finite aggregation/rejection contracts, not arbitrary software
correctness, a production workload, or an optimum target architecture.
"""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from examples.problem_corpus.executable import review_executable_corpus
from flowguard.coverage import (
    DEFAULT_REQUIRED_BUG_CLASSES,
    DEFAULT_REQUIRED_CASE_KINDS,
    build_benchmark_coverage_audit,
)
from flowguard.executable import build_executable_corpus_report

FLOWGUARD_MODEL_MARKER = "flowguard-executable-model"
PROTECTED_FAILURES = (
    "corpus_failed_result_hidden",
    "corpus_unknown_terminal_accepted",
    "corpus_case_kind_coverage_missing",
    "corpus_bug_class_coverage_missing",
    "corpus_variant_depth_reduced",
    "corpus_case_denominator_reduced",
)
SOURCE_PATHS = (
    ".flowguard/models/owners/problem_corpus_coverage/model.py",
    ".flowguard/verification/owners/problem_corpus_coverage/run_checks.py",
    "flowguard/coverage.py", "flowguard/executable.py", "flowguard/corpus.py",
    "examples/problem_corpus/executable.py", "examples/problem_corpus/matrix.py",
    "examples/problem_corpus/real_models.py", "examples/problem_corpus/taxonomy.py",
)


def run_review() -> dict[str, object]:
    """One real baseline execution; each bad observation has its own oracle."""
    baseline = review_executable_corpus()
    coverage = build_benchmark_coverage_audit(baseline)
    rows = []

    def emit(name, good, observed, accepted, facts):
        rows.append({
            "name": name,
            "case_kind": "good" if good else "bad",
            "ok": bool(accepted), "expected_ok": True,
            "observed_status": observed,
            "finding_codes": [] if good else [name],
            # Native capture reads this exact leaf, never recursively projects
            # the report's unrelated dictionaries into counterfeit leaves.
            "observation_json": json.dumps(facts, sort_keys=True),
        })

    emit("corpus_actual_baseline", True, "ok" if baseline.ok and coverage.ok else "violation",
         baseline.ok and coverage.ok and baseline.failure_cases == 0,
         {"total_cases": baseline.total_cases, "variants": coverage.variant_total,
          "minimum_depth": coverage.variant_min_cases,
          "family_case_kind_matrix": coverage.family_case_kind_matrix,
          "family_bug_class_matrix": coverage.family_bug_class_matrix})

    results = baseline.results
    failed = build_executable_corpus_report((replace(results[0], status="failed"), *results[1:]))
    emit("corpus_failed_result_hidden", False, "blocked" if not failed.ok else "ok",
         not failed.ok and failed.failure_cases == 1 and failed.total_cases == baseline.total_cases,
         {"report_ok": failed.ok, "failure_cases": failed.failure_cases,
          "total_cases": failed.total_cases, "changed_case_id": results[0].case_id})

    unknown = build_executable_corpus_report((replace(results[0], status="unrecognized_terminal_status"), *results[1:]))
    emit("corpus_unknown_terminal_accepted", False, "blocked" if not unknown.ok else "ok",
         not unknown.ok and unknown.accepted_executable_cases == baseline.total_cases - 1,
         {"report_ok": unknown.ok, "accepted_cases": unknown.accepted_executable_cases,
          "total_cases": unknown.total_cases})

    missing_kind = DEFAULT_REQUIRED_CASE_KINDS[0]
    missing_kind_rows = tuple(replace(x, case_kind="declared_other_kind") if x.case_kind == missing_kind else x for x in results)
    missing_kind_report = build_executable_corpus_report(missing_kind_rows)
    kind_coverage = build_benchmark_coverage_audit(missing_kind_report)
    emit("corpus_case_kind_coverage_missing", False, "blocked" if not kind_coverage.ok else "ok",
         not kind_coverage.ok and bool(kind_coverage.families_missing_required_case_kinds)
         and all(missing_kind in kinds for _, kinds in kind_coverage.families_missing_required_case_kinds),
         {"coverage_ok": kind_coverage.ok, "missing": kind_coverage.families_missing_required_case_kinds})

    missing_bug = DEFAULT_REQUIRED_BUG_CLASSES[0]
    def remove_bug(x):
        metadata = dict(x.metadata)
        if metadata.get("bug_class", metadata.get("structural_category", x.failure_mode)) == missing_bug:
            metadata["bug_class"] = "declared_other_bug_class"
        return replace(x, metadata=tuple(metadata.items()))
    bug_coverage = build_benchmark_coverage_audit(build_executable_corpus_report(tuple(remove_bug(x) for x in results)))
    emit("corpus_bug_class_coverage_missing", False, "blocked" if not bug_coverage.ok else "ok",
         not bug_coverage.ok and bool(bug_coverage.families_missing_required_bug_classes)
         and all(missing_bug in bugs for _, bugs in bug_coverage.families_missing_required_bug_classes),
         {"coverage_ok": bug_coverage.ok, "missing": bug_coverage.families_missing_required_bug_classes})

    deeper = build_benchmark_coverage_audit(baseline, variant_target=coverage.variant_max_cases + 1)
    emit("corpus_variant_depth_reduced", False, "blocked" if not deeper.ok else "ok",
         not deeper.ok and bool(deeper.variants_below_target)
         and len(deeper.variants_below_target) == coverage.variant_total,
         {"coverage_ok": deeper.ok, "declared_depth": deeper.variant_target,
          "below_target": deeper.variants_below_target})

    denominator = build_executable_corpus_report(results, total_cases=baseline.total_cases + 1)
    emit("corpus_case_denominator_reduced", False, "blocked" if not denominator.ok else "ok",
         not denominator.ok and denominator.total_cases == len(results) + 1,
         {"report_ok": denominator.ok, "required_cases": denominator.total_cases,
          "observed_cases": len(results)})
    return {"native_cases": rows,
            "claim_boundary": "One actual finite corpus run plus named report mutations; aggregation semantics only."}


def export_path_quality_source(model_instance_fingerprint: str):
    """Declare exact review obligations and sources without running the corpus."""
    from flowguard.model_path_quality import compile_declared_path_quality_source
    from flowguard.source_identity import functional_source_fingerprint
    root = Path(__file__).resolve().parents[4]
    return compile_declared_path_quality_source(
        model_id="problem_corpus_coverage",
        model_instance_fingerprint=model_instance_fingerprint,
        graph_scope="native_check_contract",
        source_refs=tuple({"path": p, "source_fingerprint": functional_source_fingerprint(root, p)} for p in SOURCE_PATHS),
        declared_contracts={failure: {
            "protected_failure_id": failure,
            "oracle": "run_review:" + failure,
            "finite_scope": "actual checked-in finite corpus results; named aggregation mutation",
            "claim_boundary": "No target-project runtime, publication or optimum-architecture proof.",
        } for failure in PROTECTED_FAILURES},
    )
