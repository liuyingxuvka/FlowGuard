from __future__ import annotations

from pathlib import Path
import unittest

import flowguard
from flowguard.route_topology import (
    INTERNAL_ROUTE_OWNERS,
    PUBLIC_ROUTE_SKILL_OWNERS,
    TARGET_KIND_INTERNAL_ROUTE,
    load_suite_routing_snapshot,
    validate_route_parity,
)


ROOT = Path(__file__).resolve().parents[1]


class RouteProfileProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profiles = flowguard.default_flowguard_route_profiles()
        cls.snapshot = load_suite_routing_snapshot(ROOT)

    def test_registry_covers_public_and_internal_route_projections(self):
        profile_ids = {profile.route_id for profile in self.profiles}

        self.assertEqual(set(PUBLIC_ROUTE_SKILL_OWNERS), set(flowguard.FLOWGUARD_ROUTE_API))
        self.assertEqual(set(INTERNAL_ROUTE_OWNERS), set(flowguard.FLOWGUARD_INTERNAL_ROUTE_API))
        self.assertEqual(set(PUBLIC_ROUTE_SKILL_OWNERS) | set(INTERNAL_ROUTE_OWNERS), profile_ids)

    def test_route_parity_matches_suite_and_prompts(self):
        report = validate_route_parity(
            ROOT,
            self.profiles,
            self.snapshot,
            public_route_ids=tuple(flowguard.FLOWGUARD_ROUTE_API),
            internal_route_ids=tuple(flowguard.FLOWGUARD_INTERNAL_ROUTE_API),
        )

        self.assertTrue(report.ok, report.format_text())

    def test_projection_mismatch_names_affected_route(self):
        report = validate_route_parity(
            ROOT,
            self.profiles,
            self.snapshot,
            public_route_ids=tuple(
                route_id
                for route_id in flowguard.FLOWGUARD_ROUTE_API
                if route_id != "model_test_alignment"
            ),
            internal_route_ids=tuple(flowguard.FLOWGUARD_INTERNAL_ROUTE_API),
        )

        self.assertFalse(report.ok)
        finding = next(item for item in report.findings if item.code == "public_route_projection_mismatch")
        self.assertIn("model_test_alignment", finding.affected_route_ids)

    def test_primary_path_handoff_from_behavior_ledger_is_internal(self):
        ledger = next(item for item in self.profiles if item.route_id == "behavior_commitment_ledger")
        ppa = next(item for item in ledger.next_actions if item.target_id == "primary_path_authority")

        self.assertEqual(TARGET_KIND_INTERNAL_ROUTE, ppa.target_kind)
        self.assertEqual("behavior_commitment_ledger", INTERNAL_ROUTE_OWNERS[ppa.target_id])

    def test_registry_serialization_is_typed(self):
        rows = [profile.to_dict() for profile in self.profiles]
        next_actions = [action for row in rows for action in row["next_actions"]]

        self.assertTrue(next_actions)
        self.assertTrue(
            all(
                set(action) == {"target_kind", "target_id", "condition", "claim_scope"}
                for action in next_actions
            )
        )

    def test_public_profiles_expose_complete_narrow_admission_contract(self):
        public_profiles = {
            profile.route_id: profile
            for profile in self.profiles
            if profile.route_id in flowguard.FLOWGUARD_ROUTE_API
        }

        self.assertEqual(set(flowguard.FLOWGUARD_ROUTE_API), set(public_profiles))
        for route_id, profile in public_profiles.items():
            with self.subTest(route=route_id):
                self.assertTrue(profile.positive_condition_ids)
                self.assertTrue(profile.forbidden_condition_ids)
                self.assertTrue(profile.minimal_inputs)
                self.assertTrue(profile.first_action)
                self.assertTrue(profile.reference_edges)
                self.assertTrue(profile.deepening_trigger_ids)
                self.assertTrue(profile.claim_boundary)

    def test_route_admission_selects_exactly_one_owner(self):
        result = flowguard.review_route_admission(
            self.profiles,
            ("behavior_preserving_contraction",),
        )

        self.assertTrue(result.ok, result.to_dict())
        self.assertEqual("architecture_reduction", result.selected_route_id)

    def test_route_admission_preserves_forbidden_and_conflict_results(self):
        forbidden = flowguard.review_route_admission(
            self.profiles,
            ("behavior_preserving_contraction", "behavior_change"),
        )
        conflict = flowguard.review_route_admission(
            self.profiles,
            ("field_lifecycle_change", "finite_bad_case_universe"),
        )

        self.assertEqual("no_match", forbidden.status)
        self.assertIn(
            ("architecture_reduction", ("behavior_change",)),
            forbidden.excluded_routes,
        )
        self.assertEqual("conflict", conflict.status)
        self.assertEqual(
            ("contract_exhaustion_mesh", "field_lifecycle_mesh"),
            conflict.candidate_route_ids,
        )

    def test_five_newly_covered_routes_have_discriminating_known_bads(self):
        cases = (
            ("architecture_reduction", "behavior_preserving_contraction", "behavior_change", "pre_code_structure", "code_structure_recommendation"),
            ("behavior_commitment_ledger", "broad_behavior_inventory", "helper_inventory_only", "ordinary_behavior_state", "model_first_function_flow"),
            ("contract_exhaustion_mesh", "finite_bad_case_universe", "unbounded_open_world", "model_code_test_alignment", "model_test_alignment"),
            ("field_lifecycle_mesh", "field_lifecycle_change", "no_field_change", "ui_interaction_flow", "ui_flow_structure"),
            ("model_topology_hazard_review", "future_use_hazard", "runtime_failure_present", "runtime_model_miss", "model_miss_review"),
        )
        for route_id, positive, forbidden_id, neighbor, neighbor_route in cases:
            with self.subTest(route=route_id):
                positive_result = flowguard.review_route_admission(self.profiles, (positive,))
                forbidden_result = flowguard.review_route_admission(
                    self.profiles,
                    (positive, forbidden_id),
                )
                near_neighbor_result = flowguard.review_route_admission(self.profiles, (neighbor,))
                conflict_result = flowguard.review_route_admission(
                    self.profiles,
                    (positive, neighbor),
                )

                self.assertEqual(route_id, positive_result.selected_route_id)
                self.assertIn(
                    route_id,
                    {item[0] for item in forbidden_result.excluded_routes},
                )
                self.assertEqual(neighbor_route, near_neighbor_result.selected_route_id)
                self.assertEqual("conflict", conflict_result.status)
                self.assertEqual(
                    {route_id, neighbor_route},
                    set(conflict_result.candidate_route_ids),
                )


if __name__ == "__main__":
    unittest.main()
