"""FlowGuard Risk Purpose Header.

Purpose:
Models the model-similarity consolidation review route before exposing it as a
public FlowGuard helper.

Guards against:
- similarity advice without current evidence;
- false friends being treated as merge candidates;
- family variants bypassing ModelMesh or Model-Test Alignment handoff;
- duplicate boundaries bypassing Architecture Reduction;
- unrelated models receiving consolidation routes.

Use before editing:
model_similarity.py, route integration fields, templates, docs, or public API
exports for model comparison.

Run:
python .flowguard/model_similarity_consolidation/run_checks.py
"""

from __future__ import annotations

from dataclasses import dataclass

from flowguard import (
    ModelSignature,
    ModelSimilarityEvidence,
    ModelSimilarityPlan,
    review_model_similarity_consolidation,
)


@dataclass(frozen=True)
class Case:
    name: str
    plan: ModelSimilarityPlan
    expected_ok: bool
    expected_relation_type: str
    expected_routes: tuple[str, ...] = ()
    expected_findings: tuple[str, ...] = ()


def family_variant_case() -> Case:
    return Case(
        "family_variant",
        ModelSimilarityPlan(
            "family-variant",
            signatures=(
                ModelSignature(
                    "checkout-simple",
                    workflow_family="checkout",
                    variant_id="simple",
                    function_blocks=("ValidateOrder", "PersistOrder"),
                    state_owned=("orders",),
                    failure_modes=("duplicate_submit",),
                    evidence_ids=("sim:checkout-family",),
                ),
                ModelSignature(
                    "checkout-retry",
                    workflow_family="checkout",
                    variant_id="retry",
                    function_blocks=("ValidateOrder", "PersistOrder"),
                    state_owned=("orders",),
                    failure_modes=("duplicate_submit",),
                    evidence_ids=("sim:checkout-family",),
                ),
            ),
            comparison_pairs=(("checkout-simple", "checkout-retry"),),
            evidence=(ModelSimilarityEvidence("sim:checkout-family"),),
            require_current_evidence=True,
        ),
        True,
        "same_family_variant",
        ("model_mesh", "model_test_alignment"),
    )


def missing_evidence_case() -> Case:
    return Case(
        "missing_evidence",
        ModelSimilarityPlan(
            "missing-evidence",
            signatures=(
                ModelSignature(
                    "billing-simple",
                    workflow_family="billing",
                    variant_id="simple",
                    function_blocks=("ValidateInvoice",),
                    failure_modes=("duplicate_invoice",),
                ),
                ModelSignature(
                    "billing-retry",
                    workflow_family="billing",
                    variant_id="retry",
                    function_blocks=("ValidateInvoice",),
                    failure_modes=("duplicate_invoice",),
                ),
            ),
            comparison_pairs=(("billing-simple", "billing-retry"),),
            require_current_evidence=True,
        ),
        False,
        "same_family_variant",
        ("model_mesh", "model_test_alignment"),
        ("missing_current_similarity_evidence",),
    )


def false_friend_case() -> Case:
    return Case(
        "false_friend",
        ModelSimilarityPlan(
            "false-friend",
            signatures=(
                ModelSignature(
                    "cache-refresh",
                    function_blocks=("RefreshCache",),
                    state_owned=("cache_entries",),
                    side_effects_owned=("write_cache",),
                    failure_modes=("stale_cache",),
                    false_friend_model_ids=("cache-report",),
                ),
                ModelSignature(
                    "cache-report",
                    function_blocks=("RenderReport",),
                    state_owned=("report_rows",),
                    side_effects_owned=("write_report",),
                    failure_modes=("missing_report_row",),
                ),
            ),
            comparison_pairs=(("cache-refresh", "cache-report"),),
        ),
        True,
        "false_friend",
    )


def duplicate_boundary_case() -> Case:
    return Case(
        "duplicate_boundary",
        ModelSimilarityPlan(
            "duplicate-boundary",
            signatures=(
                ModelSignature(
                    "writer-a",
                    function_blocks=("WriteRecord",),
                    state_owned=("records",),
                    side_effects_owned=("write_record",),
                    failure_modes=("duplicate_write",),
                ),
                ModelSignature(
                    "writer-b",
                    function_blocks=("WriteRecord",),
                    state_owned=("records",),
                    side_effects_owned=("write_record",),
                    failure_modes=("duplicate_write",),
                ),
            ),
            comparison_pairs=(("writer-a", "writer-b"),),
        ),
        True,
        "duplicate_boundary",
        ("architecture_reduction",),
    )


def unrelated_case() -> Case:
    return Case(
        "unrelated",
        ModelSimilarityPlan(
            "unrelated",
            signatures=(
                ModelSignature("search", function_blocks=("SearchIndex",)),
                ModelSignature("mailer", function_blocks=("SendEmail",)),
            ),
            comparison_pairs=(("search", "mailer"),),
        ),
        True,
        "unrelated",
    )


CASES = (
    family_variant_case(),
    missing_evidence_case(),
    false_friend_case(),
    duplicate_boundary_case(),
    unrelated_case(),
)


def run_case(case: Case) -> tuple[bool, str]:
    report = review_model_similarity_consolidation(case.plan)
    if report.ok != case.expected_ok:
        return False, f"{case.name}: expected ok={case.expected_ok}, got {report.ok}"
    relation_type = report.relations[0].relation_type if report.relations else ""
    if relation_type != case.expected_relation_type:
        return False, f"{case.name}: expected relation {case.expected_relation_type}, got {relation_type}"
    routes = set(report.recommended_next_routes)
    for route in case.expected_routes:
        if route not in routes:
            return False, f"{case.name}: missing route {route}"
    finding_codes = {finding.code for finding in report.findings}
    for code in case.expected_findings:
        if code not in finding_codes:
            return False, f"{case.name}: missing finding {code}"
    return True, report.summary


def run_review() -> tuple[tuple[str, bool, str], ...]:
    rows = []
    for case in CASES:
        ok, summary = run_case(case)
        rows.append((case.name, ok, summary))
    return tuple(rows)
