import unittest

import flowguard
from flowguard import (FIELD_DISPOSITION_DELETED, FIELD_IMPACT_STATE, FIELD_LIFECYCLE_REPLACED,
                       FIELD_ROLE_METADATA, FIELD_ROLE_STATE, FieldLifecyclePlan, FieldLifecycleRow, FieldProjection,
                       add_field_row, field_lifecycle_code_facts, field_lifecycle_explorer, replace_field_row)


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
        for impacts, expected_code in (
            ((flowguard.FIELD_IMPACT_ROUTING,), "behavior_field_projection_missing"),
            ((flowguard.FIELD_IMPACT_PERMISSION,), "behavior_field_projection_missing"),
            (("permisssion",), "field_behavior_impact_invalid"),
            ((flowguard.FIELD_IMPACT_PERMISSION, "permisssion"), "field_behavior_impact_invalid"),
            (("",), "field_behavior_impact_invalid"),
        ):
            with self.subTest(behavior_impacts=impacts):
                report = flowguard.review_field_lifecycle(
                    flowguard.FieldLifecyclePlan(
                        "checkout-fields",
                        discovered_field_ids=("field:mode",),
                        fields=(
                            flowguard.FieldLifecycleRow(
                                "field:mode",
                                role=flowguard.FIELD_ROLE_ROUTING,
                                behavior_impacts=impacts,
                            ),
                        ),
                    ),
                )

                self.assertFalse(report.ok)
                self.assertEqual(flowguard.FIELD_DECISION_BLOCKED, report.decision)
                self.assertIn(expected_code, {finding.code for finding in report.findings})

    def test_unknown_vocabulary_blocks_even_scoped_or_delegated_fields(self):
        for coverage in flowguard.FIELD_COVERAGE_DISPOSITIONS:
            for attribute, value, expected_code in (
                ("role", "metdata", "field_role_invalid"),
                ("role", "", "field_role_invalid"),
                ("lifecycle", "actve", "field_lifecycle_invalid"),
                ("lifecycle", "", "field_lifecycle_invalid"),
                ("behavior_impacts", ("permisssion",), "field_behavior_impact_invalid"),
            ):
                with self.subTest(coverage=coverage, attribute=attribute, value=value):
                    row = flowguard.FieldLifecycleRow(
                        "field:label",
                        coverage_disposition=coverage,
                        scoped_out_reason="display-only label",
                        delegated_owner_id="native:label",
                        coverage_evidence_refs=("test:label",),
                        **{attribute: value},
                    )
                    report = flowguard.review_field_lifecycle(
                        flowguard.FieldLifecyclePlan("labels", fields=(row,))
                    )
                    self.assertFalse(report.ok)
                    self.assertEqual(flowguard.FIELD_DECISION_BLOCKED, report.decision)
                    self.assertIn(expected_code, {finding.code for finding in report.findings})

    def test_valid_metadata_and_presentation_coverage_still_passes(self):
        for role in (flowguard.FIELD_ROLE_METADATA, flowguard.FIELD_ROLE_PRESENTATION):
            for coverage in flowguard.FIELD_COVERAGE_DISPOSITIONS:
                with self.subTest(role=role, coverage=coverage):
                    report = flowguard.review_field_lifecycle(
                        flowguard.FieldLifecyclePlan(
                            "labels",
                            fields=(flowguard.FieldLifecycleRow(
                                "field:label",
                                role=role,
                                coverage_disposition=coverage,
                                behavior_impacts=(flowguard.FIELD_IMPACT_NONE,),
                                scoped_out_reason="display-only label",
                                delegated_owner_id="native:label",
                                coverage_evidence_refs=("test:label",),
                            ),),
                        )
                    )
                    self.assertTrue(report.ok, report.format_text())

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

    def test_complete_inventory_requires_exact_rows_and_explicit_semantics(self):
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
                    flowguard.FieldLifecycleRow("field:unexpected"),
                ),
                inventory_revision="fields:checkout:r1",
                inventory_fingerprint="not-a-sha256",
                discovery_evidence_ids=("scan:checkout-schema:r1",),
                require_complete_inventory=True,
            )
        )

        codes = {finding.code for finding in report.findings}
        self.assertFalse(report.ok)
        self.assertIn("field_inventory_unexpected_row", codes)
        self.assertIn("field_inventory_fingerprint_invalid", codes)
        self.assertIn("field_owner_missing", codes)
        self.assertIn("field_default_semantics_missing", codes)
        self.assertIn("field_content_fingerprint_missing", codes)

    def test_complete_inventory_accepts_delegated_field_with_native_evidence(self):
        report = flowguard.review_field_lifecycle(
            flowguard.FieldLifecyclePlan(
                "checkout-fields",
                discovered_field_ids=("field:mode",),
                fields=(
                    flowguard.FieldLifecycleRow(
                        "field:mode",
                        owner_id="schema:checkout",
                        locations=("checkout/schema.py:mode",),
                        role=flowguard.FIELD_ROLE_ROUTING,
                        behavior_impacts=(flowguard.FIELD_IMPACT_ROUTING,),
                        default_semantics="standard mode is selected when omitted",
                        absence_semantics="omission selects the standard mode",
                        serialization_semantics="serialized as the mode string",
                        privacy_classification="public",
                        content_fingerprint="sha256:" + "1" * 64,
                        coverage_disposition=flowguard.FIELD_COVERAGE_DELEGATED,
                        delegated_owner_id="model:checkout-routing",
                        coverage_evidence_refs=("model-run:checkout-routing:r1",),
                    ),
                ),
                inventory_revision="fields:checkout:r1",
                inventory_fingerprint="sha256:" + "2" * 64,
                discovery_evidence_ids=("scan:checkout-schema:r1",),
                require_complete_inventory=True,
            )
        )

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual(flowguard.FIELD_DECISION_FULL, report.decision)


def _kit_plan():
    return FieldLifecyclePlan("orders", discovered_field_ids=("field:mode",), fields=(
        FieldLifecycleRow("field:mode", role=FIELD_ROLE_STATE, behavior_impacts=(FIELD_IMPACT_STATE,),
                          locations=("shop/orders.py:mode",),
                          projection=FieldProjection("projection:mode", "field:mode", model_obligation_id="obligation:mode",
                                                     code_contract_id="contract:mode")),))


_KIT_EDITS = {
    "add_old": lambda plan: add_field_row(plan, FieldLifecycleRow("field:old_mode", role=FIELD_ROLE_METADATA,
                                                                  scoped_out_reason="label only")),
    "delete_old": lambda plan: replace_field_row(plan, "field:old_mode", lifecycle=FIELD_LIFECYCLE_REPLACED,
                                                 replacement_field_id="field:mode", disposition=FIELD_DISPOSITION_DELETED,
                                                 disposition_evidence_refs=("test:old_mode_gone",))
    if any(row.field_id == "field:old_mode" for row in plan.fields) else plan,
    "drop_old": lambda plan: replace_field_row(plan, "field:old_mode", lifecycle=FIELD_LIFECYCLE_REPLACED)
    if any(row.field_id == "field:old_mode" for row in plan.fields) else plan,
}


def test_field_lifecycle_kit_explores_edits_with_the_review_as_invariant():
    assert field_lifecycle_explorer(_kit_plan, _KIT_EDITS, explore=["add_old", "delete_old"]).explore().ok
    bad = field_lifecycle_explorer(_kit_plan, _KIT_EDITS, explore=["add_old", "drop_old"]).explore()
    assert not bad.ok and "old_field_disposition_open" in bad.violations[0].message


def test_field_lifecycle_code_facts_compare_the_plan_with_the_code(tmp_path):
    (tmp_path / "shop").mkdir()
    source = tmp_path / "shop/orders.py"
    source.write_text("class Order:\n    mode = 'fast'\n", encoding="utf-8")
    target = _KIT_EDITS["delete_old"](_KIT_EDITS["add_old"](_kit_plan()))
    report = field_lifecycle_code_facts(target, ["shop/orders.py"], anchors={"Order": "shop/orders.py:Order"}, root=tmp_path)
    assert report.ok, report.format_text()
    source.write_text("class Order:\n    mode = 'fast'\n    old_mode = None\n", encoding="utf-8")
    report = field_lifecycle_code_facts(target, ["shop/orders.py"], root=tmp_path)
    assert not report.ok and "field:old_mode: deleted field has no reference left" in report.format_text()
    source.write_text("class Order:\n    kind = 'fast'\n", encoding="utf-8")
    text = field_lifecycle_code_facts(target, ["shop/orders.py"], root=tmp_path).format_text()
    assert "replacement field:mode exists" in text and "field:mode: declared at shop/orders.py:mode" in text


if __name__ == "__main__":
    unittest.main()
