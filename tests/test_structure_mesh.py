import unittest

from flowguard import (
    EVIDENCE_ABSTRACT_GREEN,
    EVIDENCE_CONFORMANCE_GREEN,
    ModuleStructureEvidence,
    PublicEntrypointEvidence,
    STRUCTURE_SCOPE_RELEASE,
    STRUCTURE_SCOPE_ROUTINE,
    StructureMeshPlan,
    StructurePartitionItem,
    review_structure_mesh,
)


def module(module_id: str, **kwargs) -> ModuleStructureEvidence:
    defaults = {
        "behavior_parity_current": True,
        "behavior_parity_tier": EVIDENCE_ABSTRACT_GREEN,
    }
    defaults.update(kwargs)
    return ModuleStructureEvidence(module_id, **defaults)


def entrypoint(entrypoint_id: str, **kwargs) -> PublicEntrypointEvidence:
    defaults = {
        "compatibility_preserved": True,
        "facade_available": True,
        "parity_evidence_current": True,
        "parity_evidence_tier": EVIDENCE_ABSTRACT_GREEN,
    }
    defaults.update(kwargs)
    return PublicEntrypointEvidence(entrypoint_id, **defaults)


class StructureMeshTests(unittest.TestCase):
    def test_complete_structure_mesh_can_continue(self):
        plan = StructureMeshPlan(
            parent_module_id="router",
            partition_items=(
                StructurePartitionItem("cli", item_type="entrypoint", owner_module_id="facade"),
                StructurePartitionItem("dispatch", item_type="function", owner_module_id="dispatch"),
            ),
            child_modules=(
                module("facade", facade_retained=True, owns_functions=("main",)),
                module("dispatch", owns_state=("route_state",), owns_side_effects=("write_event",)),
            ),
            public_entrypoints=(entrypoint("python -m router", old_path="router.py", new_path="router.py"),),
        )

        report = review_structure_mesh(plan)

        self.assertTrue(report.ok)
        self.assertEqual("structure_mesh_green_can_continue", report.decision)
        self.assertEqual(0, report.blocker_count())

    def test_missing_partition_owner_blocks_parent_green(self):
        plan = StructureMeshPlan(
            parent_module_id="router",
            partition_items=(StructurePartitionItem("startup", owner_module_id=""),),
            child_modules=(module("startup"),),
        )

        report = review_structure_mesh(plan)

        self.assertFalse(report.ok)
        self.assertEqual("coverage_gap_blocked", report.decision)
        self.assertIn("coverage_gap", [finding.code for finding in report.findings])

    def test_unregistered_partition_owner_blocks_parent_green(self):
        plan = StructureMeshPlan(
            parent_module_id="router",
            partition_items=(StructurePartitionItem("startup", owner_module_id="startup_child"),),
            child_modules=(module("other"),),
        )

        report = review_structure_mesh(plan)

        self.assertFalse(report.ok)
        self.assertEqual("coverage_gap_blocked", report.decision)

    def test_duplicate_partition_state_side_effect_and_config_ownership_block(self):
        plan = StructureMeshPlan(
            parent_module_id="router",
            partition_items=(
                StructurePartitionItem("route-state", owner_module_id="route_a"),
                StructurePartitionItem("route-state", owner_module_id="route_b"),
            ),
            child_modules=(
                module(
                    "route_a",
                    owns_state=("route_state",),
                    owns_side_effects=("write_packet",),
                    owns_config=("route_config",),
                ),
                module(
                    "route_b",
                    owns_state=("route_state",),
                    owns_side_effects=("write_packet",),
                    owns_config=("route_config",),
                ),
            ),
        )

        report = review_structure_mesh(plan)
        codes = {finding.code for finding in report.findings}

        self.assertFalse(report.ok)
        self.assertEqual("ownership_conflict", report.decision)
        self.assertIn("duplicate_partition_owner", codes)
        self.assertIn("duplicate_state_owner", codes)
        self.assertIn("duplicate_side_effect_owner", codes)
        self.assertIn("duplicate_config_owner", codes)

    def test_public_entrypoint_and_facade_compatibility_are_required(self):
        plan = StructureMeshPlan(
            parent_module_id="router",
            partition_items=(StructurePartitionItem("cli", owner_module_id="facade"),),
            child_modules=(module("facade", facade_retained=False),),
            public_entrypoints=(
                entrypoint(
                    "router-cli",
                    compatibility_preserved=False,
                    facade_available=False,
                ),
            ),
        )

        report = review_structure_mesh(plan)
        codes = [finding.code for finding in report.findings]

        self.assertFalse(report.ok)
        self.assertEqual("entrypoint_compatibility_blocked", report.decision)
        self.assertIn("entrypoint_removed", codes)
        self.assertIn("facade_missing", codes)

    def test_dependency_cycle_config_drift_and_parity_gaps_block(self):
        for kwargs, decision, code in (
            ({"dependency_cycles": ("module_a->module_b->module_a",)}, "dependency_cycle_blocked", "dependency_cycle"),
            ({"config_defaults_changed": True}, "config_drift_blocked", "config_drift"),
            ({"behavior_parity_tier": ""}, "missing_behavior_parity", "missing_behavior_parity"),
            ({"behavior_parity_current": False}, "stale_behavior_parity", "stale_behavior_parity"),
        ):
            with self.subTest(code=code):
                plan = StructureMeshPlan(
                    parent_module_id="router",
                    partition_items=(StructurePartitionItem("dispatch", owner_module_id="dispatch"),),
                    child_modules=(module("dispatch", **kwargs),),
                )
                report = review_structure_mesh(plan)
                self.assertFalse(report.ok)
                self.assertEqual(decision, report.decision)
                self.assertIn(code, [finding.code for finding in report.findings])

    def test_allowed_dependency_cycle_does_not_block(self):
        plan = StructureMeshPlan(
            parent_module_id="router",
            partition_items=(StructurePartitionItem("dispatch", owner_module_id="dispatch"),),
            child_modules=(module("dispatch", dependency_cycles=("known_plugin_cycle",)),),
            allowed_dependency_cycles=("known_plugin_cycle",),
        )

        report = review_structure_mesh(plan)

        self.assertTrue(report.ok)

    def test_evidence_tier_below_required_is_visible(self):
        plan = StructureMeshPlan(
            parent_module_id="release",
            required_evidence_tier=EVIDENCE_CONFORMANCE_GREEN,
            partition_items=(StructurePartitionItem("publish", owner_module_id="publish"),),
            child_modules=(module("publish", behavior_parity_tier=EVIDENCE_ABSTRACT_GREEN),),
        )

        report = review_structure_mesh(plan)

        self.assertFalse(report.ok)
        self.assertEqual("insufficient_evidence", report.decision)

    def test_routine_scope_can_defer_release_only_module_and_entrypoint(self):
        plan = StructureMeshPlan(
            parent_module_id="router",
            decision_scope=STRUCTURE_SCOPE_ROUTINE,
            partition_items=(StructurePartitionItem("unit", owner_module_id="unit"),),
            child_modules=(
                module("unit"),
                module("release-parity", layer="release", release_required=True, behavior_parity_current=False),
            ),
            public_entrypoints=(
                entrypoint("release-cli", release_required=True, parity_evidence_current=False),
            ),
        )

        report = review_structure_mesh(plan)

        self.assertTrue(report.ok)
        self.assertEqual("structure_mesh_green_can_continue", report.decision)
        self.assertIn("release-parity", report.release_obligations)
        self.assertIn("release-cli", report.release_obligations)

    def test_release_scope_requires_release_parity_current(self):
        plan = StructureMeshPlan(
            parent_module_id="router-release",
            decision_scope=STRUCTURE_SCOPE_RELEASE,
            partition_items=(StructurePartitionItem("unit", owner_module_id="unit"),),
            child_modules=(
                module("unit"),
                module("release-parity", layer="release", release_required=True, behavior_parity_current=False),
            ),
        )

        report = review_structure_mesh(plan)

        self.assertFalse(report.ok)
        self.assertEqual("missing_release_evidence", report.decision)


if __name__ == "__main__":
    unittest.main()
