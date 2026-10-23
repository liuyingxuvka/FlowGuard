"""Model kits: features and plan edits give a model its five abilities with little code."""

from __future__ import annotations

import pytest

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
    assert report.ok and report.explored_sequence_count == 6
    reached = {path.final_state.features for path in report.traces}
    assert {("empty_id",), ("gift_note",), ("empty_id", "negative_amount"), ("negative_amount", "gift_note")} <= reached


def test_generated_known_bad_variants_fail_the_kit_invariants():
    variants = feature_variants(FEATURES)
    assert list(variants) == ["ignores_empty_id", "reports_first_defect_only", "rejects_gift_note"]
    caught = {name: {v.invariant_name for v in explorer.explore().violations} for name, explorer in variants.items()}
    assert "each_defect_rejected" in caught["ignores_empty_id"]
    assert caught["reports_first_defect_only"] == {"every_defect_reported"}
    assert {"clean_input_accepted", "benign_features_neutral"} <= caught["rejects_gift_note"]
    assert list(feature_variants(FEATURES[:1])) == ["ignores_empty_id", "drops_codes_of_empty_id"]


@pytest.mark.parametrize(
    ("earlier_codes", "later_codes", "max_features", "earlier_exclusive", "later_exclusive", "masked"),
    [
        (("SHARED",), ("SHARED",), 2, False, False, False),
        (("A", "B"), ("A", "B"), 2, False, False, False),
        (("A", "B"), ("A",), 2, False, False, False),
        (("A",), ("A", "B"), 2, False, False, True),
        (("A",), ("B",), 2, False, False, True),
        ((), ("B",), 2, False, False, True),
        (("A",), (), 2, False, False, False),
        (("A",), ("B",), 1, False, False, False),
        (("A",), ("B",), 2, True, False, False),
        (("A",), ("B",), 2, False, True, False),
    ],
    ids=["shared", "shared_multiple", "earlier_contains_later", "later_adds_code", "distinct",
         "earlier_no_code", "later_no_code", "single_feature_bound", "earlier_exclusive", "later_exclusive"],
)
def test_generated_masking_variant_requires_a_reachable_missing_code(
        earlier_codes, later_codes, max_features, earlier_exclusive, later_exclusive, masked):
    # Deliberately reverse lexical name order: judgments use declaration order.
    features = (Feature("z_earlier", True, earlier_codes, exclusive=earlier_exclusive),
                Feature("a_later", True, later_codes, exclusive=later_exclusive))
    assert feature_explorer(features, max_features=max_features).explore().ok
    variants = feature_variants(features, max_features=max_features)
    assert ("reports_first_defect_only" in variants) is masked
    for name, explorer in variants.items():
        report = explorer.explore()
        assert not report.ok, f"{name} is equivalent to the design: {report.format_text()}"
        if name == "reports_first_defect_only":
            assert {v.invariant_name for v in report.violations} == {"every_defect_reported"}


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


def test_reachable_states_collects_every_state_once(monkeypatch):
    from dataclasses import replace
    from types import SimpleNamespace
    from flowguard.core import FunctionResult
    from flowguard.explorer import Explorer
    from flowguard.workflow import Workflow
    from flowguard.kit import reachable_states
    import flowguard

    block = SimpleNamespace(name='increment', apply=lambda inp, state: [FunctionResult(inp, state + 1)])
    explorer = Explorer(Workflow((block,)), initial_states=(0,), external_inputs=(1,),
                        max_sequence_length=3, progress_steps=0)
    report = explorer.explore()
    # Retain one real long path: final-state-only collection would lose 1 and 2.
    longest = max(report.traces, key=lambda trace: len(trace.steps))
    monkeypatch.setattr(Explorer, 'explore', lambda self: replace(report, traces=(longest,)))
    assert reachable_states(explorer) == (0, 1, 2, 3)
    assert reachable_states(explorer, lambda state: state % 2) == (0, 1)
    assert reachable_states(explorer, lambda state: state if state % 2 == 0 else None) == (0, 2)
    assert reachable_states(explorer, lambda state: [state % 2]) == ([0], [1])
    assert 'reachable_states' not in flowguard.__all__


@pytest.mark.parametrize('initial,following,expected', [(None, 0, (None, 0)), (0, None, (0, None))])
def test_reachable_states_keeps_unprojected_none_states(initial, following, expected):
    from types import SimpleNamespace
    from flowguard.core import FunctionResult
    from flowguard.explorer import Explorer
    from flowguard.workflow import Workflow
    from flowguard.kit import reachable_states

    block = SimpleNamespace(name='step', apply=lambda inp, state: [FunctionResult(inp, following)])
    explorer = Explorer(Workflow((block,)), initial_states=(initial,), external_inputs=('step',),
                        max_sequence_length=1, progress_steps=0)
    assert reachable_states(explorer) == expected
    assert reachable_states(explorer, lambda state: state) == (0,)


def test_feature_model_explores_each_combination_once():
    import time
    features = tuple(Feature(f"f{i}", i < 4, (f"C{i}",) if i < 4 else ()) for i in range(8))
    start = time.monotonic()
    report = feature_explorer(features, max_features=4).explore()
    assert report.ok and len(report.traces) == report.explored_sequence_count == 162
    reached = [trace.final_state.features for trace in report.traces]
    assert len(set(reached)) == 162
    for variant in feature_variants(features, max_features=4).values():
        bad = variant.explore()
        assert not bad.ok and not bad.exception_branches
        assert len(bad.traces) == 162
    elapsed = time.monotonic() - start
    print(f"feature design plus variants: {elapsed:.6f}s")
    assert elapsed < 5


def test_first_error_validator_fits_codes_first(tmp_path):
    design = feature_explorer(FEATURES, codes="first")
    assert "first_defect_reported" in [rule.name for rule in design.invariants]
    assert "every_defect_reported" not in [rule.name for rule in design.invariants]
    assert feature_conformance(FEATURES, clean_order, stops_at_first_defect, codes="first").ok
    assert any(v.rule_name == "every_defect_reported" for v in
               feature_conformance(FEATURES, clean_order, stops_at_first_defect).violations)
    reports = [variant.explore() for variant in feature_variants(FEATURES, codes="first").values()]
    assert reports and all(not report.ok and not report.exception_branches for report in reports)
    assert {rule.name for rule in design.invariants} <= {
        v.invariant_name for report in reports for v in report.violations}

    from flowguard.map.proof import run_model
    model_path = tmp_path / "first_model.py"
    model_path.write_text(FEATURE_MODEL.replace("feature_explorer(FEATURES)", 'feature_explorer(FEATURES, codes="first")')
        .replace("feature_variants(FEATURES)", 'feature_variants(FEATURES, codes="first")')
        .replace("lambda order: place(**order))", 'lambda order: place(**order), codes="first")'))
    (tmp_path / "shop.py").write_text("def place(id, amount):\n    if not id:\n        return False, ['missing_id']\n"
        "    return amount >= 0, ['bad_amount'] * (amount < 0)\n")
    result = run_model(tmp_path, model_path)
    expected_warning = ("invariant_untested: each_defect_rejected, first_defect_reported "
                        "have no TESTED_BY test; bind a test that fails when the rule is broken")
    assert result.status == "pass" and result.warnings == [expected_warning], (result.problems, result.warnings)


def test_requires_and_conflicts_limit_the_combinations():
    features = (Feature("a", True, ("A",), requires=("b",)), Feature("b", False),
                Feature("c", False, conflicts=("d",)), Feature("d", False))
    seen = []
    built = tuple(__import__('dataclasses').replace(f, apply=lambda names, n=f.name: names + (n,)) for f in features)
    report = feature_conformance(built, tuple,
        lambda names: seen.append(names) or ("a" not in names, ("A",) if "a" in names else ()), max_features=3)
    assert report.ok, report.format_text()
    assert () in seen and ("b",) in seen and ("a", "b") in seen and ("a",) not in seen
    assert len(seen) == len(set(seen))
    assert all(not ({"c", "d"} <= set(names)) for names in seen)
    # Removing a required benign feature is not a legal control input.
    assert all("a" not in names or "b" in names for names in seen)
    for variant in feature_variants(features, max_features=3).values():
        assert not variant.explore().ok


@pytest.mark.parametrize("features,bound,match", [
    (lambda: (Feature("a", True, requires=("typo",)),), 2, "a"),
    (lambda: (Feature("a", True, conflicts=("typo",)),), 2, "a"),
    (lambda: (Feature("a", True, requires=("b",)), Feature("b", False, requires=("typo",))), 2, "b"),
    (lambda: (Feature("a", True, requires=("b",)), Feature("b", False, requires=("c",)), Feature("c", False)), 2, "a"),
    (lambda: (Feature("a", True, requires=("b",), exclusive=True), Feature("b", False)), 2, "a"),
])
def test_feature_constraints_reject_unreachable_or_unknown_dependencies(features, bound, match):
    with pytest.raises(ValueError, match=match):
        feature_explorer(features(), max_features=bound)


@pytest.mark.parametrize("codes", ["all", "first"])
def test_single_coded_defect_has_a_real_reporting_witness(codes):
    features = (Feature("defect", True, ("BROKEN",)),)
    design = feature_explorer(features, codes=codes)
    variants = feature_variants(features, codes=codes)
    assert "drops_codes_of_defect" in variants
    hits = {v.invariant_name for bad in variants.values() for v in bad.explore().violations}
    assert {rule.name for rule in design.invariants} <= hits
    assert all(not bad.explore().ok for bad in variants.values())


def test_feature_models_without_codes_have_no_reporting_invariant():
    features = (Feature("defect", True), Feature("note", False))
    design = feature_explorer(features)
    assert "every_defect_reported" not in [rule.name for rule in design.invariants]
    assert design.explore().ok


@pytest.mark.parametrize("features,codes", [
    ((Feature("defect", True),), "all"),
    ((Feature("note", False),), "all"),
    ((Feature("uncoded", True), Feature("coded", True, ("C",), requires=("uncoded",))), "first"),
    ((Feature("a", True, requires=("b",)), Feature("b", True, requires=("a",))), "all"),
    ((Feature("a", True, requires=("b",)), Feature("b", False, requires=("a",))), "all"),
])
def test_degenerate_feature_universes_emit_only_real_witnesses(features, codes):
    design = feature_explorer(features, codes=codes)
    assert design.explore().ok
    reports = [bad.explore() for bad in feature_variants(features, codes=codes).values()]
    assert reports and all(not report.ok and not report.exception_branches for report in reports)
    assert {i.name for i in design.invariants} <= {v.invariant_name for report in reports for v in report.violations}


@pytest.mark.parametrize("crashes", [False, True])
def test_reject_only_conformance_still_checks_the_clean_base(crashes):
    feature = Feature("bad", True, apply=lambda value: True)
    def review(bad):
        if not bad and crashes:
            raise ValueError("clean base crashed")
        return False
    report = feature_conformance((feature,), lambda: False, review)
    assert not report.ok
    assert any(not v.features and v.rule_name == ("adapter_exception" if crashes else "matches_design")
               for v in report.violations), report.format_text()
