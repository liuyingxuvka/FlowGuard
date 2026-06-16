import unittest

from flowguard import (
    CONTRACT_DIMENSION_FIELD,
    CONTRACT_DIMENSION_INPUT,
    CONTRACT_DIMENSION_PAYLOAD,
    CONTRACT_EXHAUSTION_CONFIDENCE_BLOCKED,
    CONTRACT_EXHAUSTION_CONFIDENCE_FULL,
    CONTRACT_EXHAUSTION_CONFIDENCE_SCOPED,
    CONTRACT_MUTATION_MISSING_REQUIRED_FIELD,
    CONTRACT_MUTATION_CARTESIAN_COMBINATION,
    CONTRACT_MUTATION_REPEAT_WITHOUT_DELTA,
    CONTRACT_MUTATION_UNKNOWN_ENUM,
    CONTRACT_ORACLE_REJECT_BEFORE_SIDE_EFFECT,
    CONTRACT_ROUTE_FIELD_LIFECYCLE,
    CONTRACT_ROUTE_MODEL_MESH,
    CONTRACT_ROUTE_MODEL_TEST_ALIGNMENT,
    CONTRACT_ROUTE_OBLIGATION_FAMILY,
    CONTRACT_ROUTE_RISK_EVIDENCE_LEDGER,
    CONTRACT_ROUTE_TEST_MESH,
    ArtifactPayloadCase,
    ArtifactPayloadContract,
    CompositeHandoffAcceptance,
    ContractDimension,
    ContractAxis,
    ContractInteractionGroup,
    ContractExhaustionPlan,
    ContractMutationCase,
    ContractOracle,
    MeshClosureModel,
    MeshClosureTransition,
    ObligationFamily,
    ObligationFamilyMember,
    Scenario,
    ScenarioExpectation,
    StateClosureCase,
    TransitionCoverageCell,
    TransitionCoverageMatrix,
    artifact_payload_cases_to_contract_cases,
    contract_exhaustion_to_composite_handoff_acceptance_ids,
    contract_exhaustion_to_coverage_receipt_ids,
    contract_exhaustion_to_model_obligations,
    contract_exhaustion_to_risk_gate_ids,
    contract_exhaustion_to_test_mesh_cell_ids,
    contract_exhaustion_to_test_mesh_shard_ids,
    family_bad_case_seed_to_contract_cases,
    model_mesh_closure_to_contract_cases,
    review_contract_exhaustion,
    scenario_matrix_to_contract_cases,
    state_closure_cases_to_contract_cases,
    transition_coverage_to_contract_cases,
)
from flowguard.obligation_family import FamilyBadCaseSeed


class ContractExhaustionTests(unittest.TestCase):
    def test_required_field_dimension_generates_cases_and_route_handoffs(self):
        report = review_contract_exhaustion(
            ContractExhaustionPlan(
                "field-contract",
                dimensions=(
                    ContractDimension(
                        "packet.kind",
                        CONTRACT_DIMENSION_FIELD,
                        source_route="field_lifecycle_mesh",
                        field_refs=("packet.kind",),
                    ),
                ),
            )
        )

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual(CONTRACT_EXHAUSTION_CONFIDENCE_FULL, report.confidence)
        self.assertEqual(3, len(report.generated_cases))
        self.assertEqual(
            tuple(case.case_id for case in report.generated_cases),
            report.required_route_case_ids[CONTRACT_ROUTE_MODEL_TEST_ALIGNMENT],
        )
        self.assertEqual(
            tuple(case.case_id for case in report.generated_cases),
            report.required_route_case_ids[CONTRACT_ROUTE_FIELD_LIFECYCLE],
        )
        self.assertEqual(3, len(report.composite_handoff_acceptances))
        self.assertIsInstance(report.composite_handoff_acceptances[0], CompositeHandoffAcceptance)
        self.assertEqual(
            tuple(acceptance.acceptance_id for acceptance in report.composite_handoff_acceptances),
            contract_exhaustion_to_composite_handoff_acceptance_ids(report),
        )
        self.assertIn("composite_handoff", report.format_text())
        obligations = contract_exhaustion_to_model_obligations(report)
        self.assertEqual(3, len(obligations))
        self.assertTrue(all("contract_exhaustion:" in obligation.obligation_id for obligation in obligations))

    def test_model_local_cartesian_interaction_group_generates_receipt_and_route_obligations(self):
        report = review_contract_exhaustion(
            ContractExhaustionPlan(
                "model-cartesian",
                model_id="packet-router",
                parent_model_id="flowpilot-parent",
                axes=(
                    ContractAxis("packet_status", values=("missing", "wrong_type")),
                    ContractAxis("evidence_path", values=("missing_file", "old_packet_dir")),
                ),
                interaction_groups=(
                    ContractInteractionGroup(
                        "packet-evidence-contract",
                        axis_ids=("packet_status", "evidence_path"),
                    ),
                ),
                require_model_coverage_receipt=True,
            )
        )

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual(4, len(report.combination_cases))
        self.assertEqual(4, len([case for case in report.generated_cases if case.mutation_type == CONTRACT_MUTATION_CARTESIAN_COMBINATION]))
        self.assertEqual(("contract_coverage:packet-router",), contract_exhaustion_to_coverage_receipt_ids(report))
        self.assertEqual(("contract_shard:packet-router:packet-evidence-contract",), contract_exhaustion_to_test_mesh_shard_ids(report))
        self.assertTrue(all(case.model_id == "packet-router" for case in report.combination_cases))
        self.assertTrue(set(report.required_combination_case_ids).issubset(set(contract_exhaustion_to_test_mesh_cell_ids(report))))
        self.assertTrue(contract_exhaustion_to_risk_gate_ids(report))
        obligations = contract_exhaustion_to_model_obligations(report)
        cartesian_obligations = [
            obligation
            for obligation in obligations
            if "cartesian:packet-router:packet-evidence-contract" in obligation.obligation_id
        ]
        self.assertEqual(4, len(cartesian_obligations))
        self.assertTrue(all("packet-evidence-contract" in obligation.external_inputs for obligation in cartesian_obligations))

    def test_model_local_cartesian_group_blocks_when_limit_cannot_close_all_cases(self):
        report = review_contract_exhaustion(
            ContractExhaustionPlan(
                "model-cartesian-limit",
                model_id="packet-router",
                axes=(
                    ContractAxis("status", values=("a", "b", "c")),
                    ContractAxis("evidence", values=("x", "y")),
                ),
                interaction_groups=(
                    ContractInteractionGroup(
                        "too-wide",
                        axis_ids=("status", "evidence"),
                    ),
                ),
                cartesian_case_limit=5,
                require_model_coverage_receipt=True,
            )
        )

        self.assertFalse(report.ok)
        self.assertIn("contract_cartesian_case_limit_exceeded", {finding.code for finding in report.findings})
        self.assertIn("contract_coverage_shard_incomplete", {finding.code for finding in report.findings})
        self.assertEqual(5, len(report.combination_cases))

    def test_parent_receipt_blocks_when_required_child_receipt_is_not_consumed(self):
        report = review_contract_exhaustion(
            ContractExhaustionPlan(
                "parent-receipt",
                model_id="parent",
                axes=(
                    ContractAxis("child_summary", values=("pass",)),
                    ContractAxis("parent_handoff", values=("consume",)),
                ),
                interaction_groups=(
                    ContractInteractionGroup(
                        "parent-consumes-child",
                        axis_ids=("child_summary", "parent_handoff"),
                    ),
                ),
                required_child_receipt_ids=("contract_coverage:child-a",),
                consumed_child_receipt_ids=(),
                require_model_coverage_receipt=True,
            )
        )

        self.assertFalse(report.ok)
        self.assertIn("contract_child_receipt_unconsumed", {finding.code for finding in report.findings})

    def test_unknown_oracle_blocks_required_case(self):
        report = review_contract_exhaustion(
            ContractExhaustionPlan(
                "unknown-oracle",
                seed_cases=(
                    ContractMutationCase(
                        "packet-missing-kind",
                        dimension_id="packet.kind",
                        mutation_type=CONTRACT_MUTATION_MISSING_REQUIRED_FIELD,
                        oracle_id="not-declared",
                    ),
                ),
                oracles=(
                    ContractOracle(
                        "declared",
                        CONTRACT_ORACLE_REJECT_BEFORE_SIDE_EFFECT,
                    ),
                ),
            )
        )

        self.assertFalse(report.ok)
        self.assertEqual(CONTRACT_EXHAUSTION_CONFIDENCE_BLOCKED, report.confidence)
        self.assertIn("contract_oracle_unknown", {finding.code for finding in report.findings})

    def test_missing_oracle_blocks_custom_required_case(self):
        report = review_contract_exhaustion(
            ContractExhaustionPlan(
                "missing-oracle",
                seed_cases=(
                    ContractMutationCase(
                        "custom-case",
                        dimension_id="custom.boundary",
                        mutation_type="project_specific_corruption",
                    ),
                ),
            )
        )

        self.assertFalse(report.ok)
        self.assertEqual(("custom-case",), report.missing_oracle_case_ids)
        self.assertIn("custom.boundary", report.model_gap_dimension_ids)

    def test_unbounded_dimension_scopes_or_blocks_by_claim_policy(self):
        scoped = review_contract_exhaustion(
            ContractExhaustionPlan(
                "unbounded-scoped",
                dimensions=(
                    ContractDimension(
                        "free_text",
                        CONTRACT_DIMENSION_INPUT,
                        finite=False,
                    ),
                ),
            )
        )

        self.assertTrue(scoped.ok, scoped.format_text())
        self.assertEqual(CONTRACT_EXHAUSTION_CONFIDENCE_SCOPED, scoped.confidence)
        self.assertIn("contract_dimension_unbounded", {finding.code for finding in scoped.findings})

        blocked = review_contract_exhaustion(
            ContractExhaustionPlan(
                "unbounded-blocked",
                dimensions=(
                    ContractDimension(
                        "free_text",
                        CONTRACT_DIMENSION_INPUT,
                        finite=False,
                    ),
                ),
                claim_scope="release",
                allow_unbounded_scoped=False,
            )
        )

        self.assertFalse(blocked.ok)
        self.assertEqual(CONTRACT_EXHAUSTION_CONFIDENCE_BLOCKED, blocked.confidence)

    def test_empty_plan_blocks_as_undeclared_model_gap(self):
        report = review_contract_exhaustion(ContractExhaustionPlan("empty"))

        self.assertFalse(report.ok)
        self.assertIn("contract_boundary_missing", {finding.code for finding in report.findings})

    def test_broad_claim_blocks_when_matrix_case_has_no_composite_handoff(self):
        report = review_contract_exhaustion(
            ContractExhaustionPlan(
                "single-route-release",
                seed_cases=(
                    ContractMutationCase(
                        "only-mta",
                        mutation_type=CONTRACT_MUTATION_MISSING_REQUIRED_FIELD,
                        required_routes=(CONTRACT_ROUTE_MODEL_TEST_ALIGNMENT,),
                        expected_status=CONTRACT_ORACLE_REJECT_BEFORE_SIDE_EFFECT,
                    ),
                ),
                claim_scope="release",
            )
        )

        self.assertFalse(report.ok)
        self.assertIn(
            "composite_handoff_acceptance_missing",
            {finding.code for finding in report.findings},
        )
        self.assertEqual((), report.required_composite_handoff_acceptance_ids)

    def test_state_closure_and_scenario_matrix_feed_common_cases(self):
        state_cases = state_closure_cases_to_contract_cases(
            (
                StateClosureCase(
                    "unknown-status",
                    "input.status",
                    CONTRACT_MUTATION_UNKNOWN_ENUM,
                    value="surprise",
                ),
            )
        )
        scenarios = scenario_matrix_to_contract_cases(
            (
                Scenario(
                    "retry",
                    "duplicate retry challenge",
                    initial_state="idle",
                    external_input_sequence=("submit", "submit"),
                    expected=ScenarioExpectation(expected_status="needs_human_review"),
                    tags=("challenge", "repeat_same"),
                ),
            )
        )
        report = review_contract_exhaustion(
            ContractExhaustionPlan("imported-cases", seed_cases=state_cases + scenarios)
        )

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual(2, len(report.generated_cases))
        self.assertIn(CONTRACT_ROUTE_MODEL_TEST_ALIGNMENT, report.required_route_case_ids)
        self.assertIn(CONTRACT_ROUTE_TEST_MESH, report.required_route_case_ids)

    def test_obligation_family_seed_projects_same_class_bad_cases(self):
        family = ObligationFamily(
            "packets",
            members=(
                ObligationFamilyMember("packet-a", required_mechanisms=("evidence-bind",)),
                ObligationFamilyMember("packet-b", required_mechanisms=("evidence-bind",)),
                ObligationFamilyMember("packet-c", required_mechanisms=("other",)),
            ),
            required_mechanisms=("evidence-bind",),
        )
        seed = FamilyBadCaseSeed(
            "miss-a",
            family_id="packets",
            source_member_id="packet-a",
            mechanism_id="evidence-bind",
            failure_mode="missing_current_evidence",
            source_case_id="observed-a",
        )

        cases = family_bad_case_seed_to_contract_cases(family, seed)
        report = review_contract_exhaustion(ContractExhaustionPlan("same-class", seed_cases=cases))

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual(("same_class:miss-a:packet-b:evidence-bind",), tuple(case.case_id for case in cases))
        self.assertEqual(
            ("same_class:miss-a:packet-b:evidence-bind",),
            report.required_route_case_ids[CONTRACT_ROUTE_OBLIGATION_FAMILY],
        )

    def test_payload_transition_and_mesh_closure_project_to_single_report(self):
        payload_cases = artifact_payload_cases_to_contract_cases(
            ArtifactPayloadContract(
                "packet-payload",
                payload_surface="flowpilot packet",
                payload_kind="json",
                cases=(
                    ArtifactPayloadCase(
                        "missing-body",
                        expected_status="rejected",
                        expected_error_path="body_ref",
                    ),
                ),
            )
        )
        transition_cases = transition_coverage_to_contract_cases(
            TransitionCoverageMatrix(
                "packet-transitions",
                cells=(
                    TransitionCoverageCell(
                        "submit-review",
                        "packet_ready",
                        "submit",
                        "reviewer_waiting",
                        runtime_node_id="router.submit",
                    ),
                ),
            )
        )
        closure_cases = model_mesh_closure_to_contract_cases(
            MeshClosureModel(
                "parent",
                transitions=(
                    MeshClosureTransition(
                        "retry-without-new-evidence",
                        consumes=("blocked",),
                        emits=("blocked",),
                        loop=True,
                        repeat_input_tokens=("blocked",),
                    ),
                ),
            )
        )
        report = review_contract_exhaustion(
            ContractExhaustionPlan(
                "combined",
                dimensions=(
                    ContractDimension(
                        "artifact-proof",
                        CONTRACT_DIMENSION_PAYLOAD,
                        mutation_types=(),
                        metadata={"risk_gate_id": "artifact-proof-gate"},
                    ),
                ),
                seed_cases=payload_cases + transition_cases + closure_cases,
            )
        )

        self.assertTrue(report.ok, report.format_text())
        self.assertIn(CONTRACT_ROUTE_RISK_EVIDENCE_LEDGER, report.required_route_case_ids)
        self.assertIn(CONTRACT_ROUTE_MODEL_MESH, report.required_route_case_ids)
        self.assertIn(CONTRACT_ROUTE_TEST_MESH, report.required_route_case_ids)
        self.assertIn(
            "mesh_closure:parent:retry-without-new-evidence",
            report.required_route_case_ids[CONTRACT_ROUTE_MODEL_MESH],
        )
        self.assertEqual(
            CONTRACT_MUTATION_REPEAT_WITHOUT_DELTA,
            closure_cases[0].mutation_type,
        )
        self.assertIn("artifact-proof-gate", contract_exhaustion_to_risk_gate_ids(report))
        self.assertTrue(contract_exhaustion_to_test_mesh_cell_ids(report))


if __name__ == "__main__":
    unittest.main()
