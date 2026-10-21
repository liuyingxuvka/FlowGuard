"""Model kits: case tables and plan edits give a model its five abilities with little code."""

from __future__ import annotations

from flowguard.kit import Case, case_table_conformance, case_table_explorer, case_table_variants, plan_explorer

CASES = (Case("valid", True), Case("empty_id", False, ("missing_id",)), Case("negative_amount", False))
INPUTS = {"valid": ("o1", 5), "empty_id": ("", 5), "negative_amount": ("o1", -1)}


def place(order_id, amount):
    if not order_id:
        return ("rejected", ["missing_id"])
    if amount < 0:
        return ("rejected", ["bad_amount"])
    return ("placed", [])


def observe(case):
    status, codes = place(*INPUTS[case.name])
    return status == "placed", codes


def test_case_table_design_passes_and_both_known_bad_designs_fail():
    assert case_table_explorer(CASES).explore().ok
    variants = case_table_variants(CASES)
    assert sorted(variants) == ["accepts_every_case", "rejects_every_case"]
    for explorer in variants.values():
        report = explorer.explore()
        assert not report.ok and report.violations[0].invariant_name == "verdict_matches_case"
    assert list(case_table_variants([Case("valid", True)])) == ["rejects_every_case"]


def test_case_table_conformance_compares_the_real_code_with_the_model():
    report = case_table_conformance(CASES, observe)
    assert report.ok and report.executed == 3
    assert report.format_text() == "executed against code: 3 of 3 cases; declared only: 0; disagree with the model: 0"
    lenient = case_table_conformance(CASES, lambda case: True)
    assert not lenient.ok and [r.case for r in lenient.violations] == ["empty_id", "negative_amount"]
    no_codes = case_table_conformance(CASES, lambda case: case.accept)
    assert [r.message for r in no_codes.violations] == ["missing finding codes: missing_id"]
    declared = case_table_conformance(CASES, lambda case: None if case.name == "valid" else False)
    assert not declared.ok and "declared only: 1" in declared.format_text()
    crashed = case_table_conformance(CASES, lambda case: 1 / 0)
    assert crashed.violations[0].rule_name == "adapter_exception" and "ZeroDivisionError" in crashed.violations[0].message


def test_plan_explorer_uses_an_existing_review_as_the_invariant():
    from types import SimpleNamespace

    def review(fields):
        return SimpleNamespace(ok="old_mode" not in fields or "migrated" in fields,
                               findings=[SimpleNamespace(code="old_field_open")])

    edits = {"add_mode": lambda f: f | {"mode"}, "migrate": lambda f: f | {"migrated"},
             "keep_old_unmigrated": lambda f: f | {"old_mode"}}
    design = plan_explorer(lambda: frozenset({"old_mode", "migrated"}), edits, review, explore=["add_mode", "migrate"])
    assert design.explore().ok
    bad = plan_explorer(lambda: frozenset(), edits, review, explore=["keep_old_unmigrated"]).explore()
    assert not bad.ok and "old_field_open" in bad.violations[0].message


MODEL = """
from flowguard.kit import Case, case_table_conformance, case_table_explorer, case_table_variants

MODEL_ID = "place_cases"
IMPLEMENTED_BY = {"place": "shop.py:place"}
TESTED_BY = {}
CASES = (Case("valid", True), Case("empty_id", False))


def build_explorer():
    return case_table_explorer(CASES)


def broken_variants():
    return case_table_variants(CASES)


def conformance():
    from shop import place
    return case_table_conformance(CASES, lambda case: place("o1" if case.accept else "") == "placed")
"""


def test_case_table_model_runs_under_the_proof_runner(tmp_path):
    from flowguard.map.proof import run_model
    (tmp_path / ".flowguard/models").mkdir(parents=True)
    path = tmp_path / ".flowguard/models/place_cases.py"
    path.write_text(MODEL, encoding="utf-8")
    (tmp_path / "shop.py").write_text("def place(order_id):\n    return 'placed' if order_id else 'rejected'\n")
    result = run_model(tmp_path, path)
    assert result.status == "pass", result.problems
    (tmp_path / "shop.py").write_text("def place(order_id):\n    return 'placed'\n")
    result = run_model(tmp_path, path)
    assert result.status == "fail" and "empty_id: expected rejected, observed accepted" in " ".join(result.problems)
