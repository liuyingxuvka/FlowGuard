import unittest

from flowguard import (
    CodeStructureRecommendation,
    EVIDENCE_ABSTRACT_GREEN,
    EVIDENCE_CONFORMANCE_GREEN,
    ModuleStructureEvidence,
    PublicEntrypointEvidence,
    STRUCTURE_SCOPE_RELEASE,
    STRUCTURE_SCOPE_ROUTINE,
    StructureMeshPlan,
    StructurePartitionItem,
    TargetModuleRecommendation,
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


def recommendation(
    parent_module_id: str = "router",
    *,
    modules: tuple[str, ...] = ("facade", "dispatch"),
    function_map: tuple[tuple[str, str], ...] = (("dispatch", "dispatch"),),
    state_map: tuple[tuple[str, str], ...] = (),
    side_effect_map: tuple[tuple[str, str], ...] = (),
    config_map: tuple[tuple[str, str], ...] = (),
    entrypoint_map: tuple[tuple[str, str], ...] = (("cli", "facade"),),
    facade_module_id: str = "facade",
) -> CodeStructureRecommendation:
    module_items = []
    for module_id in modules:
        module_items.append(
            TargetModuleRecommendation(
                module_id,
                owns_function_blocks=tuple(item for item, owner in function_map if owner == module_id),
                owns_state=tuple(item for item, owner in state_map if owner == module_id),
                owns_side_effects=tuple(item for item, owner in side_effect_map if owner == module_id),
                owns_config=tuple(item for item, owner in config_map if owner == module_id),
                public_entrypoints=tuple(item for item, owner in entrypoint_map if owner == module_id),
                validation_boundaries=("focused parity test",),
                rationale=f"{module_id} owns its model-derived structure boundary",
            )
        )
    return CodeStructureRecommendation(
        "router-target-structure",
        source_model_id="router-functional-model",
        source_model_path=".flowguard/router/model.py",
        parent_module_id=parent_module_id,
        target_modules=tuple(module_items),
        function_block_map=function_map,
        state_owner_map=state_map,
        side_effect_owner_map=side_effect_map,
        config_owner_map=config_map,
        public_entrypoint_map=entrypoint_map,
        facade_module_id=facade_module_id,
        validation_boundaries=("focused parity test",),
        rationale="model blocks, state owners, and side effects define the target split",
    )


class StructureMeshTests(unittest.TestCase):
    def test_complete_structure_mesh_can_continue(self):
        plan = StructureMeshPlan(
            parent_module_id="router",
            target_structure=recommendation(
                state_map=(("route_state", "dispatch"),),
                side_effect_map=(("write_event", "dispatch"),),
            ),
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
            target_structure=recommendation(
                modules=("startup",),
                function_map=(("startup", "startup"),),
                entrypoint_map=(),
                facade_module_id="",
            ),
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
            target_structure=recommendation(
                modules=("startup_child", "other"),
                function_map=(("startup", "startup_child"),),
                entrypoint_map=(),
                facade_module_id="",
            ),
            partition_items=(StructurePartitionItem("startup", owner_module_id="startup_child"),),
            child_modules=(module("other"),),
        )

        report = review_structure_mesh(plan)

        self.assertFalse(report.ok)
        self.assertEqual("coverage_gap_blocked", report.decision)

    def test_duplicate_partition_state_side_effect_and_config_ownership_block(self):
        plan = StructureMeshPlan(
            parent_module_id="router",
            target_structure=recommendation(
                modules=("route_a", "route_b"),
                function_map=(("route-state", "route_a"),),
                state_map=(("route_state", "route_a"),),
                side_effect_map=(("write_packet", "route_a"),),
                config_map=(("route_config", "route_a"),),
                entrypoint_map=(),
                facade_module_id="",
            ),
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
            target_structure=recommendation(
                modules=("facade",),
                function_map=(("main", "facade"),),
                entrypoint_map=(("cli", "facade"),),
            ),
            partition_items=(StructurePartitionItem("cli", item_type="entrypoint", owner_module_id="facade"),),
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
                    target_structure=recommendation(
                        modules=("dispatch",),
                        function_map=(("dispatch", "dispatch"),),
                        entrypoint_map=(),
                        facade_module_id="",
                    ),
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
            target_structure=recommendation(
                modules=("dispatch",),
                function_map=(("dispatch", "dispatch"),),
                entrypoint_map=(),
                facade_module_id="",
            ),
            partition_items=(StructurePartitionItem("dispatch", owner_module_id="dispatch"),),
            child_modules=(module("dispatch", dependency_cycles=("known_plugin_cycle",)),),
            allowed_dependency_cycles=("known_plugin_cycle",),
        )

        report = review_structure_mesh(plan)

        self.assertTrue(report.ok)

    def test_evidence_tier_below_required_is_visible(self):
        plan = StructureMeshPlan(
            parent_module_id="release",
            target_structure=recommendation(
                parent_module_id="release",
                modules=("publish",),
                function_map=(("publish", "publish"),),
                entrypoint_map=(),
                facade_module_id="",
            ),
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
            target_structure=recommendation(
                modules=("unit",),
                function_map=(("unit", "unit"),),
                entrypoint_map=(("release-cli", "unit"),),
                facade_module_id="unit",
            ),
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
            target_structure=recommendation(
                parent_module_id="router-release",
                modules=("unit",),
                function_map=(("unit", "unit"),),
                entrypoint_map=(),
                facade_module_id="",
            ),
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

    def test_missing_model_derived_target_structure_blocks(self):
        plan = StructureMeshPlan(
            parent_module_id="router",
            partition_items=(StructurePartitionItem("dispatch", owner_module_id="dispatch"),),
            child_modules=(module("dispatch"),),
        )

        report = review_structure_mesh(plan)

        self.assertFalse(report.ok)
        self.assertEqual("target_structure_missing", report.decision)
        self.assertIn("missing_target_structure", [finding.code for finding in report.findings])

    def test_target_structure_owner_mismatch_blocks(self):
        plan = StructureMeshPlan(
            parent_module_id="router",
            target_structure=recommendation(
                modules=("dispatch", "wrong"),
                function_map=(("dispatch", "wrong"),),
                state_map=(("route_state", "wrong"),),
                entrypoint_map=(),
                facade_module_id="",
            ),
            partition_items=(StructurePartitionItem("dispatch", owner_module_id="dispatch"),),
            child_modules=(module("dispatch", owns_state=("route_state",)),),
        )

        report = review_structure_mesh(plan)
        codes = {finding.code for finding in report.findings}

        self.assertFalse(report.ok)
        self.assertEqual("target_structure_blocked", report.decision)
        self.assertIn("target_function_owner_mismatch", codes)
        self.assertIn("target_state_owner_mismatch", codes)


if __name__ == "__main__":
    unittest.main()
