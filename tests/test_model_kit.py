"""Model kits: features and plan edits give a model its five abilities with little code."""

from __future__ import annotations

from flowguard.kit import Feature, feature_conformance, feature_explorer, feature_variants, plan_explorer

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


def test_plan_explorer_checks_several_existing_reviews_and_names_the_first_blocker():
    from types import SimpleNamespace

    def no_old(fields):
        return SimpleNamespace(ok="old_mode" not in fields, findings=[
            SimpleNamespace(code="style", severity="warning", message="naming"),
            SimpleNamespace(code="old_field_open", severity="blocker", message="old_mode is still read")])

    def has_mode(fields):
        return SimpleNamespace(ok="mode" in fields, findings=[SimpleNamespace(code="mode_missing")])

    edits = {"add_mode": lambda f: f | {"mode"}, "keep_old": lambda f: f | {"old_mode"}}
    explorer = plan_explorer(lambda: frozenset({"mode"}), edits, no_old, invariant_name="no_old_field",
                             extra_reviews={"mode_present": has_mode}, explore=["add_mode", "keep_old"])
    assert [invariant.name for invariant in explorer.invariants] == ["no_old_field", "mode_present"]
    bad = explorer.explore()
    assert {v.invariant_name for v in bad.violations} == {"no_old_field"}
    assert bad.violations[0].message.endswith("style, old_field_open (old_mode is still read)")
    assert not plan_explorer(lambda: frozenset(), edits, no_old, extra_reviews={"mode_present": has_mode},
                             explore=["keep_old"]).explore().ok


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
