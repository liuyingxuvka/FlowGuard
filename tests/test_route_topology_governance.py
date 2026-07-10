from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import unittest

import flowguard
from flowguard.route_topology import (
    DEFAULT_ROUTE_CYCLE_LIVENESS,
    LOOP_DECISION_BLOCKED_BOUND,
    LOOP_DECISION_BLOCKED_UNCHANGED,
    LOOP_DECISION_CONTINUE,
    LegacyRouteHandoffError,
    RouteCycleLiveness,
    RouteHandoff,
    TARGET_KIND_EXTERNAL_ACTION,
    TARGET_KIND_HELPER_API,
    TARGET_KIND_INTERNAL_ROUTE,
    TARGET_KIND_SKILL,
    load_suite_routing_snapshot,
    probe_cycle_liveness,
    validate_route_topology,
)


ROOT = Path(__file__).resolve().parents[1]


def finding_codes(report) -> set[str]:
    return {finding.code for finding in report.findings}


class RouteTopologyGovernanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = load_suite_routing_snapshot(ROOT)
        cls.profiles = flowguard.default_flowguard_route_profiles()

    def test_default_topology_resolves_every_typed_handoff(self):
        report = validate_route_topology(self.profiles, self.snapshot)

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual(31, len(report.route_ids))
        self.assertEqual(83, report.edge_count)
        self.assertEqual(2, len(report.cycle_components))
        kinds = {
            handoff.target_kind
            for profile in self.profiles
            for handoff in profile.next_actions
        }
        self.assertEqual(
            {
                TARGET_KIND_SKILL,
                TARGET_KIND_INTERNAL_ROUTE,
                TARGET_KIND_HELPER_API,
                TARGET_KIND_EXTERNAL_ACTION,
            },
            kinds,
        )

    def test_cross_cutting_and_delegated_routes_have_canonical_owners(self):
        profiles = {profile.route_id: profile for profile in self.profiles}

        self.assertEqual("behavior_commitment_ledger", profiles["primary_path_authority"].canonical_owner_route)
        for route_id in (
            "risk_evidence_ledger",
            "flowguard_self_maintenance",
            "risk_template_library",
        ):
            self.assertEqual("model_first_function_flow", profiles[route_id].canonical_owner_route)
            self.assertNotEqual(flowguard.ENTRY_POLICY_DIRECT, profiles[route_id].entry_policy)
        for route_id in ("plan_detailing_compiler", "agent_workflow_rehearsal"):
            self.assertEqual(flowguard.ROUTE_ROLE_DELEGATED_MODE, profiles[route_id].route_role)
            self.assertEqual("development_process_flow", profiles[route_id].canonical_owner_route)

    def test_legacy_bare_string_is_a_migration_error(self):
        with self.assertRaisesRegex(LegacyRouteHandoffError, "target_kind"):
            flowguard.RouteProfile(
                "legacy",
                "legacy",
                next_actions=("risk_evidence_ledger",),
            )

    def test_all_target_kinds_fail_when_dangling(self):
        source = self.profiles[0]
        for target_kind in (
            TARGET_KIND_SKILL,
            TARGET_KIND_INTERNAL_ROUTE,
            TARGET_KIND_HELPER_API,
            TARGET_KIND_EXTERNAL_ACTION,
        ):
            with self.subTest(target_kind=target_kind):
                bad = replace(
                    source,
                    next_actions=(RouteHandoff(target_kind, "missing-target", "always", "test"),),
                )
                profiles = (bad,) + self.profiles[1:]
                report = validate_route_topology(profiles, self.snapshot)
                self.assertIn("dangling_target", finding_codes(report))

    def test_wrong_target_kind_is_not_treated_as_dangling(self):
        source = self.profiles[0]
        bad = replace(
            source,
            next_actions=(
                RouteHandoff(TARGET_KIND_SKILL, "primary_path_authority", "always", "test"),
            ),
        )

        report = validate_route_topology((bad,) + self.profiles[1:], self.snapshot)

        self.assertIn("target_kind_mismatch", finding_codes(report))

    def test_missing_and_duplicate_owners_block(self):
        public = next(item for item in self.profiles if item.route_id == "architecture_reduction")
        internal = next(item for item in self.profiles if item.route_id == "primary_path_authority")

        missing_public = replace(public, skill_name="")
        report = validate_route_topology(
            tuple(missing_public if item.route_id == public.route_id else item for item in self.profiles),
            self.snapshot,
        )
        self.assertIn("missing_public_owner", finding_codes(report))

        missing_internal = replace(internal, canonical_owner_route="")
        report = validate_route_topology(
            tuple(missing_internal if item.route_id == internal.route_id else item for item in self.profiles),
            self.snapshot,
        )
        self.assertIn("missing_internal_owner", finding_codes(report))

        duplicate = replace(public, skill_name="flowguard-code-structure-recommendation")
        report = validate_route_topology(self.profiles + (duplicate,), self.snapshot)
        self.assertIn("duplicate_route_owner", finding_codes(report))

    def test_cycle_contract_requires_progress_terminals_and_finite_bound(self):
        first = DEFAULT_ROUTE_CYCLE_LIVENESS[0]
        broken = replace(
            first,
            progress_measure="",
            allowed_delta="",
            success_terminal="",
            blocked_terminal="",
            max_reentries=0,
        )

        report = validate_route_topology(
            self.profiles,
            self.snapshot,
            cycle_policies=(broken, DEFAULT_ROUTE_CYCLE_LIVENESS[1]),
        )

        self.assertIn("cycle_liveness_metadata_missing", finding_codes(report))
        self.assertIn("unbounded_cycle", finding_codes(report))

    def test_cycle_probes_continue_only_with_delta_inside_bound(self):
        policy = DEFAULT_ROUTE_CYCLE_LIVENESS[0]
        unchanged = probe_cycle_liveness(
            policy,
            previous_progress=("receipt-a",),
            current_progress=("receipt-a",),
            reentries=0,
        )
        changed = probe_cycle_liveness(
            policy,
            previous_progress=("receipt-a",),
            current_progress=("receipt-a", "receipt-b"),
            reentries=0,
        )
        bounded = probe_cycle_liveness(
            policy,
            previous_progress=("receipt-a",),
            current_progress=("receipt-a", "receipt-b"),
            reentries=policy.max_reentries,
        )

        self.assertEqual(LOOP_DECISION_BLOCKED_UNCHANGED, unchanged.decision)
        self.assertEqual(LOOP_DECISION_CONTINUE, changed.decision)
        self.assertEqual(LOOP_DECISION_BLOCKED_BOUND, bounded.decision)

    def test_multiple_findings_have_stable_machine_order(self):
        public = next(item for item in self.profiles if item.route_id == "architecture_reduction")
        bad = replace(
            public,
            skill_name="",
            next_actions=(RouteHandoff(TARGET_KIND_HELPER_API, "missing", "always", "test"),),
        )
        profiles = tuple(bad if item.route_id == public.route_id else item for item in self.profiles)

        first = validate_route_topology(profiles, self.snapshot).to_json_text()
        second = validate_route_topology(profiles, self.snapshot).to_json_text()

        self.assertEqual(first, second)
        self.assertIn('"dangling_target"', first)
        self.assertIn('"missing_public_owner"', first)


if __name__ == "__main__":
    unittest.main()
