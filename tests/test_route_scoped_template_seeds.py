import unittest
from dataclasses import replace
from tempfile import TemporaryDirectory
from pathlib import Path

from flowguard.template_packs import (
    HardPredicate,
    TemplateSeed,
    builtin_template_seeds,
    close_template_seed,
    select_template_seeds,
    validate_template_seed,
)
from flowguard.risk_templates import (
    harvest_template_seed_candidate,
    load_local_template_seeds,
    promote_template_seed,
    write_local_template_seed,
)


def seed(*, template_id="mesh", promotion_status="promoted", closure_disposition="pending"):
    return TemplateSeed(
        template_id=template_id,
        version="1",
        route_ids=("route:model-mesh",),
        layers={
            "route_scaffold": {"owner": "model_mesh"},
            "reusable_branch_seed": {"required_tests": ["positive", "known_bad"]},
            "operator_guide": {"steps": ["declare", "close"]},
            "flowguard_self_model": {"claim_boundary": "candidate only"},
        },
        predicates=(HardPredicate("route_id", "equals", "route:model-mesh"),),
        protected_error_classes=("mesh_missing_partition",),
        required_states=("declared", "closed"),
        required_side_effects=("owner_record",),
        completion_evidence=("current_target_record",),
        positive_cases=("complete_partition",),
        known_bad_cases=("missing_partition",),
        false_friend_cases=("three_models_without_topology",),
        target_fields=("parent_partition", "child_owner"),
        non_applicable_disposition="proved_or_blocked",
        source_proof_refs=("tests:test_hierarchical_mesh",),
        promotion_status=promotion_status,
        closure_disposition=closure_disposition,
    )


class TemplateSeedTests(unittest.TestCase):
    def test_builtin_public_seeds_are_portable_and_exactly_selectable(self):
        seeds = builtin_template_seeds()
        self.assertEqual(3, len(seeds))
        self.assertEqual(("public-contract-exhaustion-branch", "public-model-mesh-branch", "public-reverse-surface-closure-branch"), tuple(sorted(item.template_id for item in seeds)))
        for item in seeds:
            self.assertEqual("pass", validate_template_seed(item).status)
            self.assertEqual("selected", select_template_seeds((item,), {"route_id": item.route_ids[0]}).status)

    def test_complete_promoted_seed_selects_by_exact_facts(self):
        selected = select_template_seeds((seed(),), {"route_id": "route:model-mesh"})
        self.assertEqual("selected", selected.status)
        self.assertEqual(("mesh",), selected.selected_template_ids)

    def test_zero_unknown_or_unpromoted_seed_never_falls_back(self):
        self.assertEqual("blocked", select_template_seeds((seed(),), {"route_id": "route:unknown"}).status)
        self.assertEqual(
            "blocked",
            select_template_seeds((seed(promotion_status="candidate"),), {"route_id": "route:model-mesh"}).status,
        )

    def test_multiple_exact_matches_block(self):
        report = select_template_seeds(
            (seed(template_id="left"), seed(template_id="right")),
            {"route_id": "route:model-mesh"},
        )
        self.assertEqual("blocked", report.status)
        self.assertIn("seed_multiple_exact_matches:left,right", report.findings)

    def test_missing_branch_contract_is_blocked(self):
        invalid = replace(seed(), known_bad_cases=(), false_friend_cases=())
        report = validate_template_seed(invalid)
        self.assertEqual("blocked", report.status)
        self.assertIn("missing_known_bad_cases", report.findings)
        self.assertIn("missing_false_friend_cases", report.findings)

    def test_private_seed_is_not_promotable(self):
        private = replace(seed(), privacy_disposition="private_blocked")
        report = validate_template_seed(private)
        self.assertEqual("blocked", report.status)
        self.assertIn("private_seed_not_promotable", report.findings)

    def test_self_owner_identifier_is_not_portable_seed_content(self):
        self_owner = replace(seed(), target_fields=("flowguard",))
        report = validate_template_seed(self_owner)
        self.assertEqual("blocked", report.status)
        self.assertIn("self_owner_id_not_allowed", report.findings)

    def test_pending_branch_requires_target_owned_closure(self):
        self.assertEqual("blocked", close_template_seed(seed(), disposition="pending").status)
        self.assertEqual(
            "pass",
            close_template_seed(seed(), disposition="modeled", proof_ref="record:target-current").status,
        )
        self.assertEqual(
            "pass",
            close_template_seed(seed(), disposition="not_applicable", proof_ref="proof:target-na").status,
        )

    def test_non_current_closure_cannot_be_selected(self):
        closed = replace(seed(), closure_disposition="modeled", closure_proof_ref="record:old")
        selected = select_template_seeds((closed,), {"route_id": "route:model-mesh"})
        self.assertEqual("blocked", selected.status)

    def test_risk_harvest_emits_candidate_only_from_explicit_fields(self):
        candidate = harvest_template_seed_candidate(
            template_id="mesh-candidate",
            version="1",
            route_ids=("route:model-mesh",),
            layers=seed().layers,
            predicates=seed().predicates,
            protected_error_classes=seed().protected_error_classes,
            required_states=seed().required_states,
            required_side_effects=seed().required_side_effects,
            completion_evidence=seed().completion_evidence,
            positive_cases=seed().positive_cases,
            known_bad_cases=seed().known_bad_cases,
            false_friend_cases=seed().false_friend_cases,
            target_fields=seed().target_fields,
            source_proof_refs=seed().source_proof_refs,
            write=False,
        )
        self.assertTrue(candidate.ok)
        self.assertEqual("candidate_ready", candidate.status)
        self.assertEqual("candidate", candidate.seed.promotion_status)
        self.assertEqual("blocked", select_template_seeds((candidate.seed,), {"route_id": "route:model-mesh"}).status)

    def test_seed_promotion_requires_explicit_review_and_can_be_loaded_current_only(self):
        promoted = promote_template_seed(
            seed(promotion_status="candidate"),
            review_status="passed",
            privacy_review_ref="review:portable-seed",
            proof_complete=True,
            promotion_proof_refs=("proof:positive", "proof:known-bad", "proof:false-friend"),
        )
        self.assertTrue(promoted.ok)
        self.assertEqual("promoted", promoted.seed.promotion_status)
        with TemporaryDirectory() as directory:
            path = write_local_template_seed(promoted.seed, Path(directory))
            self.assertTrue(path.exists())
            loaded = load_local_template_seeds(Path(directory))
        self.assertEqual(("mesh",), tuple(item.template_id for item in loaded))

    def test_seed_promotion_blocks_without_privacy_or_proof_review(self):
        report = promote_template_seed(
            seed(),
            review_status="passed",
            privacy_review_ref="",
            proof_complete=False,
        )
        self.assertEqual("blocked", report.status)
        self.assertIn("missing_privacy_review_ref", report.findings)
        self.assertIn("proof_not_complete", report.findings)

    def test_seed_harvest_does_not_infer_missing_branch_fields(self):
        report = harvest_template_seed_candidate(
            template_id="incomplete",
            version="1",
            route_ids=("route:model-mesh",),
            layers=seed().layers,
            predicates=seed().predicates,
            protected_error_classes=seed().protected_error_classes,
            required_states=seed().required_states,
            required_side_effects=seed().required_side_effects,
            completion_evidence=seed().completion_evidence,
            positive_cases=(),
            known_bad_cases=seed().known_bad_cases,
            false_friend_cases=seed().false_friend_cases,
            target_fields=seed().target_fields,
            source_proof_refs=seed().source_proof_refs,
            write=False,
        )
        self.assertEqual("blocked", report.status)
        self.assertIn("missing_positive_cases", report.findings)

    def test_predicate_validation_is_bounded(self):
        invalid = replace(seed(template_id="invalid"), predicates=(
            HardPredicate("", "execute_python", {"code": "pass"}),
            HardPredicate("tier", "one_of", []),
            HardPredicate("optional", "exists", "false"),
        ))
        findings = validate_template_seed(invalid).findings
        self.assertIn("predicate:invalid:0:missing_key", findings)
        self.assertIn("predicate:invalid:0:unsupported_operator:execute_python", findings)
        self.assertIn("predicate:invalid:1:one_of_expected_must_be_nonempty_array", findings)
        self.assertIn("predicate:invalid:2:exists_expected_must_be_boolean", findings)
        fallback = validate_template_seed(replace(invalid, template_id="")).findings
        self.assertIn("predicate:seed:0:missing_key", fallback)

    def test_all_bounded_predicate_operators_are_conjunctive_and_composable(self):
        item = replace(seed(template_id="all-operators"), predicates=(
            HardPredicate("kind", "equals", "doc"),
            HardPredicate("tier", "one_of", ["pro", "enterprise"]),
            HardPredicate("tags", "contains", "blue"),
            HardPredicate("roles", "contains_all", ["author", "reviewer"]),
            HardPredicate("optional", "exists", False),
        ))
        context = {"kind": "doc", "tier": "pro", "tags": ("green", "blue"),
                   "roles": ("reviewer", "author", "reader")}
        selected = select_template_seeds((item,), context)
        self.assertEqual("selected", selected.status)
        self.assertEqual(("all-operators",), selected.selected_template_ids)
        # The live seed owner selects one branch by the conjunction, never pack composition.
        for key, wrong in (("kind", "sheet"), ("tier", "basic"), ("tags", ("green",)),
                           ("roles", ("author",)), ("optional", True)):
            with self.subTest(predicate=key):
                blocked = select_template_seeds((item,), dict(context, **{key: wrong}))
                self.assertEqual("blocked", blocked.status)
                self.assertEqual((), blocked.matched_template_ids)
                self.assertIn("seed_no_exact_match", blocked.findings)

    def test_failed_or_missing_predicate_excludes_entry(self):
        items = tuple(replace(seed(template_id=name), predicates=(HardPredicate(key, "equals", value),))
                      for name, key, value in (("matching", "kind", "document"),
                                               ("failing", "kind", "spreadsheet"), ("missing", "tier", "pro")))
        selected = select_template_seeds(items, {"kind": "document"})
        self.assertEqual("selected", selected.status)
        self.assertEqual(("matching",), selected.matched_template_ids)

    def test_equals_and_one_of_use_strict_json_types(self):
        equals_true = replace(seed(template_id="equals-true"), predicates=(HardPredicate("kind", "equals", True),))
        one_of_true = replace(seed(template_id="one-of-true"), predicates=(HardPredicate("kind", "one_of", [True]),))
        selected = select_template_seeds((equals_true, one_of_true), {"kind": 1})
        self.assertEqual("blocked", selected.status)
        self.assertEqual((), selected.matched_template_ids)
        self.assertIn("seed_no_exact_match", selected.findings)


if __name__ == "__main__":
    unittest.main()
