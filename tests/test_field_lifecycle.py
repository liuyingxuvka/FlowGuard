import unittest

import flowguard


class FieldLifecycleTests(unittest.TestCase):
    def _projection(self) -> flowguard.FieldProjection:
        return flowguard.FieldProjection(
            "projection:mode",
            "field:mode",
            model_obligation_id="field:mode:obligation",
            code_contract_id="contract:mode",
            external_inputs=("mode",),
            external_outputs=("mode applied",),
            state_reads=("mode",),
            state_writes=("mode",),
            required_test_kinds=(flowguard.TEST_KIND_HAPPY_PATH, flowguard.TEST_KIND_FAILURE_PATH),
            rationale="mode controls routing",
        )

    def _projection_with_route_refs(self) -> flowguard.FieldProjection:
        return flowguard.FieldProjection(
            "projection:mode",
            "field:mode",
            model_obligation_id="field:mode:obligation",
            code_contract_id="contract:mode",
            external_inputs=("mode",),
            external_outputs=("mode applied",),
            state_reads=("mode",),
            state_writes=("mode",),
            required_test_kinds=(
                flowguard.TEST_KIND_NEGATIVE_PATH,
                flowguard.TEST_KIND_REPLAY,
            ),
            evidence_refs=(
                "gate:checkout-mode-boundary",
                "test:missing-mode-rejected",
                "replay:mode-runtime-path",
            ),
            rationale="mode controls routing",
        )

    def test_complete_field_lifecycle_passes_and_projects(self):
        plan = flowguard.FieldLifecyclePlan(
            "checkout-fields",
            discovered_field_ids=("field:mode", "field:label", "field:old_mode"),
            groups=(
                flowguard.FieldLifecycleGroup(
                    "checkout-payload",
                    boundary_kind="api_payload",
                    field_ids=("field:mode", "field:label", "field:old_mode"),
                ),
            ),
            fields=(
                flowguard.FieldLifecycleRow(
                    "field:mode",
                    role=flowguard.FIELD_ROLE_ROUTING,
                    group_id="checkout-payload",
                    behavior_impacts=(flowguard.FIELD_IMPACT_ROUTING,),
                    reader_ids=("checkout.router",),
                    writer_ids=("checkout.form",),
                    projection=self._projection(),
                ),
                flowguard.FieldLifecycleRow(
                    "field:label",
                    role=flowguard.FIELD_ROLE_PRESENTATION,
                    group_id="checkout-payload",
                    scoped_out_reason="display-only label, no behavior branch",
                ),
                flowguard.FieldLifecycleRow(
                    "field:old_mode",
                    role=flowguard.FIELD_ROLE_ROUTING,
                    lifecycle=flowguard.FIELD_LIFECYCLE_REPLACED,
                    group_id="checkout-payload",
                    behavior_impacts=(flowguard.FIELD_IMPACT_ROUTING,),
                    replacement_field_id="field:mode",
                    disposition=flowguard.FIELD_DISPOSITION_MIGRATED,
                    disposition_evidence_refs=("test_old_mode_migrates",),
                    projection=self._projection(),
                ),
            ),
        )

        report = flowguard.review_field_lifecycle(plan)

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual(flowguard.FIELD_DECISION_FULL, report.decision)
        self.assertEqual(2, len(report.projections))
        self.assertEqual(2, len(flowguard.field_lifecycle_to_model_obligations(report)))
        self.assertEqual(2, len(flowguard.field_lifecycle_to_code_contracts(report)))

    def test_missing_discovered_field_blocks(self):
        report = flowguard.review_field_lifecycle(
            flowguard.FieldLifecyclePlan(
                "checkout-fields",
                discovered_field_ids=("field:mode",),
                fields=(),
            )
        )

        self.assertFalse(report.ok)
        self.assertIn("field_lifecycle_missing_field_row", {finding.code for finding in report.findings})

    def test_behavior_field_without_projection_blocks(self):
        report = flowguard.review_field_lifecycle(
            flowguard.FieldLifecyclePlan(
                "checkout-fields",
                discovered_field_ids=("field:mode",),
                fields=(
                    flowguard.FieldLifecycleRow(
                        "field:mode",
                        role=flowguard.FIELD_ROLE_ROUTING,
                        behavior_impacts=(flowguard.FIELD_IMPACT_ROUTING,),
                    ),
                ),
            )
        )

        self.assertFalse(report.ok)
        self.assertIn("behavior_field_projection_missing", {finding.code for finding in report.findings})

    def test_bounded_behavior_projection_does_not_require_route_refs(self):
        report = flowguard.review_field_lifecycle(
            flowguard.FieldLifecyclePlan(
                "checkout-fields",
                discovered_field_ids=("field:mode",),
                fields=(
                    flowguard.FieldLifecycleRow(
                        "field:mode",
                        role=flowguard.FIELD_ROLE_ROUTING,
                        behavior_impacts=(flowguard.FIELD_IMPACT_ROUTING,),
                        projection=self._projection(),
                    ),
                ),
            )
        )

        self.assertTrue(report.ok, report.format_text())

    def test_full_behavior_projection_requires_gate_test_and_replay_refs(self):
        report = flowguard.review_field_lifecycle(
            flowguard.FieldLifecyclePlan(
                "checkout-fields",
                discovered_field_ids=("field:mode",),
                claim_scope="full",
                fields=(
                    flowguard.FieldLifecycleRow(
                        "field:mode",
                        role=flowguard.FIELD_ROLE_ROUTING,
                        behavior_impacts=(flowguard.FIELD_IMPACT_REPLAY,),
                        projection=flowguard.FieldProjection(
                            "projection:mode",
                            "field:mode",
                            model_obligation_id="field:mode:obligation",
                            code_contract_id="contract:mode",
                            required_test_kinds=(
                                flowguard.TEST_KIND_NEGATIVE_PATH,
                                flowguard.TEST_KIND_REPLAY,
                            ),
                        ),
                    ),
                ),
            )
        )

        codes = {finding.code for finding in report.findings}
        self.assertFalse(report.ok)
        self.assertIn("field_gate_evidence_missing", codes)
        self.assertIn("field_negative_test_evidence_missing", codes)
        self.assertIn("field_replay_evidence_missing", codes)

    def test_full_behavior_projection_accepts_minimal_route_refs(self):
        report = flowguard.review_field_lifecycle(
            flowguard.FieldLifecyclePlan(
                "checkout-fields",
                discovered_field_ids=("field:mode",),
                claim_scope="full",
                fields=(
                    flowguard.FieldLifecycleRow(
                        "field:mode",
                        role=flowguard.FIELD_ROLE_ROUTING,
                        behavior_impacts=(flowguard.FIELD_IMPACT_REPLAY,),
                        projection=self._projection_with_route_refs(),
                    ),
                ),
            )
        )

        self.assertTrue(report.ok, report.format_text())

    def test_old_field_unknown_disposition_blocks(self):
        report = flowguard.review_field_lifecycle(
            flowguard.FieldLifecyclePlan(
                "checkout-fields",
                discovered_field_ids=("field:old_mode",),
                fields=(
                    flowguard.FieldLifecycleRow(
                        "field:old_mode",
                        lifecycle=flowguard.FIELD_LIFECYCLE_REPLACED,
                        replacement_field_id="field:mode",
                        behavior_impacts=(flowguard.FIELD_IMPACT_ROUTING,),
                        projection=self._projection(),
                    ),
                ),
            )
        )

        self.assertFalse(report.ok)
        self.assertIn("old_field_disposition_open", {finding.code for finding in report.findings})

    def test_every_field_with_an_ordinary_ui_reader_hands_off_for_content_admission(self):
        plan = flowguard.FieldLifecyclePlan(
            "ordinary-ui-reader-fields",
            discovered_field_ids=(
                "field:title",
                "field:phase",
                "field:permission",
                "field:audit_trace",
            ),
            fields=(
                flowguard.FieldLifecycleRow(
                    "field:title",
                    role=flowguard.FIELD_ROLE_PRESENTATION,
                    reader_ids=("ordinary-ui-view",),
                ),
                flowguard.FieldLifecycleRow(
                    "field:phase",
                    role=flowguard.FIELD_ROLE_STATE,
                    reader_ids=("ordinary-ui-view",),
                ),
                flowguard.FieldLifecycleRow(
                    "field:permission",
                    role=flowguard.FIELD_ROLE_PERMISSION,
                    reader_ids=("ordinary-ui-view",),
                ),
                flowguard.FieldLifecycleRow(
                    "field:audit_trace",
                    role=flowguard.FIELD_ROLE_METADATA,
                    reader_ids=("audit-log",),
                ),
            ),
        )

        candidate_ids = flowguard.ui_content_visibility_candidate_ids_from_field_lifecycle(
            plan,
            ui_reader_ids=("ordinary-ui-view",),
        )

        self.assertEqual(
            ("field:title", "field:phase", "field:permission"),
            candidate_ids,
        )
        self.assertNotIn("field:audit_trace", candidate_ids)

    def test_field_lifecycle_api_is_route_scoped_not_core(self):
        for name in ("FieldLifecyclePlan", "FieldLifecycleRow", "review_field_lifecycle"):
            self.assertIn(name, flowguard.FIELD_LIFECYCLE_MESH_API)
            self.assertIn(name, flowguard.MODELING_HELPER_API)
            self.assertIn(name, flowguard.__all__)
            self.assertTrue(hasattr(flowguard, name))
            self.assertNotIn(name, flowguard.CORE_API)


if __name__ == "__main__":
    unittest.main()
