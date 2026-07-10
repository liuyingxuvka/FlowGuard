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


if __name__ == "__main__":
    unittest.main()
