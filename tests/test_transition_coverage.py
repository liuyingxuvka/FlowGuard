import unittest

from flowguard import (
    EVIDENCE_ABSTRACT_GREEN,
    ModelTestAlignmentPlan,
    TEST_EVIDENCE_ROLE_TRANSITION_CELL,
    TEST_KIND_FAILURE_PATH,
    TEST_KIND_HAPPY_PATH,
    TEST_LAYER_LEAF_MATRIX_CELL,
    TestMeshPlan,
    TestPartitionItem,
    TestSuiteEvidence,
    TestTargetSplitDerivation,
    TestEvidence,
    TransitionCoverageCell,
    TransitionCoverageMatrix,
    UIControl,
    UIInteractionModel,
    UIStateNode,
    UITransition,
    review_model_test_alignment,
    review_test_mesh,
    transition_coverage_to_model_obligations,
    transition_coverage_to_required_leaf_cell_ids,
    transition_obligation_id,
    ui_interaction_model_to_transition_coverage,
)


def transition_evidence(evidence_id, obligation_id, cell_id, **kwargs):
    defaults = {
        "result_status": "passed",
        "evidence_current": True,
        "test_kind": TEST_KIND_HAPPY_PATH,
        "covered_obligations": (obligation_id,),
        "evidence_role": TEST_EVIDENCE_ROLE_TRANSITION_CELL,
        "evidence_target_id": cell_id,
    }
    defaults.update(kwargs)
    return TestEvidence(evidence_id, **defaults)


def child_suite(suite_id, *cell_ids, **kwargs):
    defaults = {
        "layer": TEST_LAYER_LEAF_MATRIX_CELL,
        "result_status": "passed",
        "evidence_tier": EVIDENCE_ABSTRACT_GREEN,
        "test_count": 1,
        "selected_count": 1,
        "owned_leaf_cell_ids": tuple(cell_ids),
    }
    defaults.update(kwargs)
    return TestSuiteEvidence(suite_id, **defaults)


class TransitionCoverageTests(unittest.TestCase):
    def test_matrix_projects_to_obligations_and_required_leaf_cells(self):
        matrix = TransitionCoverageMatrix(
            "map-ui-transitions",
            model_id="map-ui",
            cells=(
                TransitionCoverageCell(
                    "idle.drag->dragging",
                    source_state="idle",
                    trigger="drag",
                    target_state="dragging",
                    expected_output="viewport_changed",
                    function_block="PanMap",
                    required_test_kinds=(TEST_KIND_HAPPY_PATH, TEST_KIND_FAILURE_PATH),
                    side_effects=("render_viewport",),
                ),
                TransitionCoverageCell(
                    "idle.zoom->zooming",
                    source_state="idle",
                    trigger="zoom",
                    target_state="zooming",
                ),
            ),
            scoped_out_cell_reasons={"idle.zoom->zooming": "covered by a release-only matrix in this review"},
        )

        obligations = transition_coverage_to_model_obligations(matrix)
        required_cell_ids = transition_coverage_to_required_leaf_cell_ids(matrix)

        self.assertEqual(("idle.drag->dragging",), required_cell_ids)
        self.assertEqual(1, len(obligations))
        self.assertEqual("transition:idle.drag->dragging", obligations[0].obligation_id)
        self.assertEqual("transition_coverage", obligations[0].obligation_type)
        self.assertEqual(("drag",), obligations[0].external_inputs)
        self.assertEqual(("viewport_changed",), obligations[0].external_outputs)
        self.assertEqual(("idle",), obligations[0].state_reads)
        self.assertEqual(("dragging",), obligations[0].state_writes)
        self.assertEqual(("render_viewport",), obligations[0].side_effects)
        self.assertEqual((TEST_KIND_HAPPY_PATH, TEST_KIND_FAILURE_PATH), obligations[0].required_test_kinds)

    def test_transition_obligation_without_test_evidence_blocks_alignment(self):
        matrix = TransitionCoverageMatrix(
            "map-ui-transitions",
            model_id="map-ui",
            cells=(TransitionCoverageCell("idle.drag->dragging", "idle", "drag", "dragging"),),
        )

        report = review_model_test_alignment(
            ModelTestAlignmentPlan(
                "map-ui",
                obligations=transition_coverage_to_model_obligations(matrix),
            )
        )

        self.assertFalse(report.ok)
        self.assertIn("missing_test_evidence", [finding.code for finding in report.findings])

    def test_transition_cell_evidence_covers_projected_obligation(self):
        matrix = TransitionCoverageMatrix(
            "map-ui-transitions",
            model_id="map-ui",
            cells=(TransitionCoverageCell("idle.drag->dragging", "idle", "drag", "dragging"),),
        )
        obligation_id = transition_obligation_id("idle.drag->dragging")

        report = review_model_test_alignment(
            ModelTestAlignmentPlan(
                "map-ui",
                obligations=transition_coverage_to_model_obligations(matrix),
                test_evidence=(
                    transition_evidence(
                        "test_drag_updates_viewport",
                        obligation_id,
                        "idle.drag->dragging",
                    ),
                ),
            )
        )

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual("model_test_alignment_green", report.decision)

    def test_transition_cell_evidence_requires_matching_target(self):
        matrix = TransitionCoverageMatrix(
            "map-ui-transitions",
            model_id="map-ui",
            cells=(TransitionCoverageCell("idle.drag->dragging", "idle", "drag", "dragging"),),
        )
        obligation_id = transition_obligation_id("idle.drag->dragging")

        report = review_model_test_alignment(
            ModelTestAlignmentPlan(
                "map-ui",
                obligations=transition_coverage_to_model_obligations(matrix),
                test_evidence=(
                    transition_evidence(
                        "test_drag_updates_viewport",
                        obligation_id,
                        "wrong.cell",
                    ),
                ),
            )
        )

        self.assertFalse(report.ok)
        codes = [finding.code for finding in report.findings]
        self.assertIn("transition_cell_target_mismatch", codes)
        self.assertIn("missing_test_evidence", codes)

    def test_ui_interaction_model_projects_to_transition_matrix(self):
        ui_model = UIInteractionModel(
            "map-ui",
            initial_state_id="idle",
            states=(
                UIStateNode("idle", enabled_controls=("drag",)),
                UIStateNode("dragging", enabled_controls=("drag",)),
            ),
            controls=(UIControl("drag", label="Drag"),),
            transitions=(
                UITransition(
                    "drag",
                    "drag",
                    "idle",
                    "dragging",
                    function_block="PanMap",
                    output="viewport_changed",
                ),
            ),
        )

        matrix = ui_interaction_model_to_transition_coverage(ui_model)
        obligations = transition_coverage_to_model_obligations(matrix)

        self.assertEqual("map-ui:transition-coverage", matrix.matrix_id)
        self.assertEqual("ui_flow_structure", matrix.source_route)
        self.assertEqual(("idle.drag->dragging",), matrix.required_cell_ids())
        self.assertEqual("transition:idle.drag->dragging", obligations[0].obligation_id)
        self.assertEqual(("viewport_changed",), obligations[0].external_outputs)

    def test_transition_matrix_required_cells_feed_test_mesh(self):
        matrix = TransitionCoverageMatrix(
            "map-ui-transitions",
            model_id="map-ui",
            cells=(
                TransitionCoverageCell("idle.drag->dragging", "idle", "drag", "dragging"),
                TransitionCoverageCell("dragging.release->idle", "dragging", "release", "idle"),
            ),
        )
        required_cells = transition_coverage_to_required_leaf_cell_ids(matrix)
        plan = TestMeshPlan(
            parent_suite_id="map-ui-transition-suite",
            partition_items=tuple(
                TestPartitionItem(cell_id, item_type="transition_coverage", owner_suite_id="browser-cells")
                for cell_id in required_cells
            ),
            child_suites=(child_suite("browser-cells", *required_cells),),
            target_split_derivation=TestTargetSplitDerivation(
                "map-ui",
                target_suite_ids=("browser-cells",),
                covered_partition_item_ids=required_cells,
                rationale="transition coverage matrix cells are owned by browser tests",
            ),
            required_leaf_cell_ids=required_cells,
        )

        report = review_test_mesh(plan)

        self.assertTrue(report.ok, report.format_text())

    def test_missing_transition_matrix_required_cell_blocks_test_mesh(self):
        matrix = TransitionCoverageMatrix(
            "map-ui-transitions",
            model_id="map-ui",
            cells=(
                TransitionCoverageCell("idle.drag->dragging", "idle", "drag", "dragging"),
                TransitionCoverageCell("dragging.release->idle", "dragging", "release", "idle"),
            ),
        )
        required_cells = transition_coverage_to_required_leaf_cell_ids(matrix)
        plan = TestMeshPlan(
            parent_suite_id="map-ui-transition-suite",
            partition_items=tuple(
                TestPartitionItem(cell_id, item_type="transition_coverage", owner_suite_id="browser-cells")
                for cell_id in required_cells
            ),
            child_suites=(child_suite("browser-cells", "idle.drag->dragging"),),
            target_split_derivation=TestTargetSplitDerivation(
                "map-ui",
                target_suite_ids=("browser-cells",),
                covered_partition_item_ids=required_cells,
                rationale="transition coverage matrix cells are owned by browser tests",
            ),
            required_leaf_cell_ids=required_cells,
        )

        report = review_test_mesh(plan)

        self.assertFalse(report.ok)
        self.assertEqual("leaf_matrix_cell_evidence_required", report.decision)
        self.assertIn("leaf_matrix_cell_evidence_missing", [finding.code for finding in report.findings])


if __name__ == "__main__":
    unittest.main()
