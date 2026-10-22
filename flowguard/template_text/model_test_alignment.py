"""A contract model reviewing literal model, code and test bindings."""

MODEL_TEST_ALIGNMENT_MODEL_TEMPLATE = r'''"""Review the model's code/test bindings; fill today's real anchors first.
Add a top-level import of the reviewed parent model file (never its children),
then set PARENT to its actual MODEL_ID so change selects this review alongside it.
Design statuses are assumptions. Conformance runs the bound tests once and uses
FG120's actual per-item pass and ANY-one code-anchor call/read results.
"""
from dataclasses import replace
from pathlib import Path
from flowguard.kit import Feature, feature_conformance, feature_explorer, feature_variants
from flowguard.map.facts import CodeFacts
from flowguard.map.proof import ModelResult, run_bound_tests
from flowguard.model_test_alignment import alignment_plan_from_model, review_model_test_alignment

MODEL_ID = "model_test_alignment"
PARENT = "REPLACE_ME"
REVIEWED = ".flowguard/models/REPLACE_ME.py"
IMPLEMENTED_BY = {"Reviewed": "REPLACE_ME/module.py:Owner"}
TESTED_BY = {"each_defect_rejected": ["REPLACE_ME/test_module.py:test_owner"]}
ROOT = Path(__file__).resolve().parents[2]


def _tests(plan, **values):
    return replace(plan, test_evidence=tuple(replace(t, **values) for t in plan.test_evidence))


FEATURES = (
    Feature("missing_code_contract", True, ("missing_code_contract", "missing_test_evidence"),
            lambda p: replace(p, code_contracts=()), exclusive=True),
    Feature("unbound_tests", True, ("test_not_bound_to_code_contract", "missing_test_evidence"),
            lambda p: _tests(p, covered_code_contracts=())),
    Feature("internal_only", True, ("test_checks_internal_path_only", "missing_test_evidence"),
            lambda p: _tests(p, assertion_scope="internal_path")),
    Feature("missing_test", True, ("missing_test_evidence",),
            lambda p: replace(p, test_evidence=()), exclusive=True),
)


def build_explorer():
    return feature_explorer(FEATURES)


def broken_variants():
    return feature_variants(FEATURES)


def _review(plan):
    report = review_model_test_alignment(plan)
    return report.ok, tuple(f.code for f in report.findings)


def conformance():
    facts = CodeFacts(ROOT)
    facts.anchors_exist(IMPLEMENTED_BY)
    base = alignment_plan_from_model(REVIEWED, root=ROOT)
    facts.anchors_exist({c.code_contract_id: c.code_contract_id for c in base.code_contracts})
    design = feature_conformance(FEATURES, lambda: alignment_plan_from_model(REVIEWED, root=ROOT), _review)
    facts.check("alignment defect checks", design.ok, design.format_text(max_examples=1))
    actual = ModelResult("reviewed", REVIEWED)
    statuses = {}
    run_bound_tests(ROOT, ROOT / REVIEWED, actual, statuses=statuses)
    facts.check("bound tests executed and touched code", actual.status == "pass", "; ".join(actual.problems))
    report = review_model_test_alignment(alignment_plan_from_model(REVIEWED, root=ROOT, statuses=statuses))
    facts.check("actual test alignment", report.ok, report.format_text())
    return facts.report()
'''

__all__ = ["MODEL_TEST_ALIGNMENT_MODEL_TEMPLATE"]
