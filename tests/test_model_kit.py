"""Model kits: features, case tables and plan edits give a model its five abilities with little code."""

from __future__ import annotations

from flowguard.kit import Case, case_table_conformance, case_table_explorer, case_table_variants, plan_explorer
from flowguard.kit import Feature, feature_conformance, feature_explorer, feature_variants

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


FEATURES = (Feature("empty_id", True, ("missing_id",), lambda order: {**order, "id": ""}),
            Feature("negative_amount", True, ("bad_amount",), lambda order: {**order, "amount": -1}),
            Feature("gift_note", False, (), lambda order: {**order, "note": "happy birthday"}))


def clean_order():
    return {"id": "o1", "amount": 5}


def review_order(order):
    """Reports every defect it finds."""
    codes = ["missing_id"] * (not order["id"]) + ["bad_amount"] * (order["amount"] < 0)
    return not codes, codes


def stops_at_first_defect(order):
    """A fake review that returns as soon as it finds one defect."""
    if not order["id"]:
        return False, ["missing_id"]
    if order["amount"] < 0:
        return False, ["bad_amount"]
    return True, []


def test_feature_design_explores_every_single_feature_and_pair_and_passes_the_kit_invariants():
    explorer = feature_explorer(FEATURES)
    assert [invariant.name for invariant in explorer.invariants] == [
        "clean_input_accepted", "each_defect_rejected", "every_defect_reported", "benign_features_neutral"]
    report = explorer.explore()
    assert report.ok and report.explored_sequence_count == 12
    reached = {path.final_state.features for path in report.traces}
    assert {("empty_id",), ("gift_note",), ("empty_id", "negative_amount"), ("negative_amount", "gift_note")} <= reached


def test_generated_known_bad_variants_fail_the_kit_invariants():
    variants = feature_variants(FEATURES)
    assert list(variants) == ["ignores_empty_id", "reports_first_defect_only", "rejects_gift_note"]
    caught = {name: {v.invariant_name for v in explorer.explore().violations} for name, explorer in variants.items()}
    assert "each_defect_rejected" in caught["ignores_empty_id"]
    assert caught["reports_first_defect_only"] == {"every_defect_reported"}
    assert {"clean_input_accepted", "benign_features_neutral"} <= caught["rejects_gift_note"]
    assert list(feature_variants(FEATURES[:1])) == ["ignores_empty_id"]       # masking needs two coded defects


def test_conformance_runs_every_combination_on_the_real_code_and_finds_masking():
    report = feature_conformance(FEATURES, clean_order, review_order)
    assert report.ok and report.executed == 7, report.format_text()
    masked = feature_conformance(FEATURES, clean_order, stops_at_first_defect)
    assert not masked.ok
    assert [(v.rule_name, v.features) for v in masked.violations] == [
        ("every_defect_reported", ("empty_id", "negative_amount"))]


def test_counterexample_trace_names_the_features_and_both_verdicts():
    masked = feature_conformance(FEATURES, clean_order, stops_at_first_defect)
    assert masked.format_text() == (
        "executed against code: 7 of 7 feature combinations; declared only: 0; errors: 0; counterexamples: 1\n"
        "- every_defect_reported: empty_id + negative_amount: expected rejected [bad_amount, missing_id], "
        "observed rejected [missing_id]")
    noisy = feature_conformance(FEATURES, clean_order, lambda order: (False, []) if "note" in order else review_order(order))
    assert noisy.violations[0].format_text() == "- clean_input_accepted: gift_note: expected accepted, observed rejected"


def test_an_adapter_returning_none_leaves_the_combination_declared_only_and_fails():
    report = feature_conformance(FEATURES, clean_order, lambda order: None if "note" in order else review_order(order))
    assert not report.ok and report.declared_only == 3 and report.executed == 4
    assert report.violations[0].format_text().startswith("- declared_only: gift_note: expected accepted, observed declared only")
    crashed = feature_conformance(FEATURES, clean_order, lambda order: 1 / 0)
    assert crashed.errors == 7 and crashed.violations[0].rule_name == "adapter_exception"
    assert "ZeroDivisionError" in crashed.violations[0].message


def test_an_exclusive_feature_is_explored_alone():
    features = FEATURES + (Feature("order_deleted", True, ("no_order",), lambda order: {}, exclusive=True),)
    seen = []
    report = feature_conformance(features, clean_order,
                                 lambda order: seen.append(tuple(sorted(order))) or
                                 ((False, ["no_order"]) if not order else review_order(order)))
    assert report.ok and report.executed == 8 and seen.count(()) == 1


FEATURE_MODEL = """
from flowguard.kit import Feature, feature_conformance, feature_explorer, feature_variants

MODEL_ID = "place_features"
IMPLEMENTED_BY = {"place": "shop.py:place"}
TESTED_BY = {}
FEATURES = (Feature("empty_id", True, ("missing_id",), lambda order: {**order, "id": ""}),
            Feature("negative_amount", True, ("bad_amount",), lambda order: {**order, "amount": -1}))


def build_explorer():
    return feature_explorer(FEATURES)


def broken_variants():
    return feature_variants(FEATURES)


def conformance():
    from shop import place
    return feature_conformance(FEATURES, lambda: {"id": "o1", "amount": 5}, lambda order: place(**order))
"""


def test_feature_model_runs_under_the_proof_runner(tmp_path):
    from flowguard.map.proof import run_model
    (tmp_path / ".flowguard/models").mkdir(parents=True)
    path = tmp_path / ".flowguard/models/place_features.py"
    path.write_text(FEATURE_MODEL, encoding="utf-8")
    (tmp_path / "shop.py").write_text(
        "def place(id, amount):\n    codes = ['missing_id'] * (not id) + ['bad_amount'] * (amount < 0)\n"
        "    return not codes, codes\n")
    result = run_model(tmp_path, path)
    assert result.status == "pass", result.problems
    (tmp_path / "shop.py").write_text(
        "def place(id, amount):\n    if not id:\n        return False, ['missing_id']\n"
        "    return amount >= 0, ['bad_amount'] * (amount < 0)\n")
    result = run_model(tmp_path, path)
    assert result.status == "fail" and ("every_defect_reported: empty_id + negative_amount: expected rejected "
                                        "[bad_amount, missing_id], observed rejected [missing_id]") in result.problems[0]
