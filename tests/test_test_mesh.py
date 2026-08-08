import unittest
from dataclasses import replace

from flowguard.evidence_receipts import (
    EvidenceReceipt,
    ReceiptVerificationContext,
    build_environment_fingerprint,
    fingerprint_value,
    snapshot_bytes,
    verify_evidence_receipt,
)
from flowguard.model_path_quality import PathQualityResult, PathQualitySubject
from flowguard import (
    EVIDENCE_ABSTRACT_GREEN,
    EVIDENCE_CONFORMANCE_GREEN,
    ProofArtifactRef,
    TEST_LAYER_CONTRACT_COMBINATION_SHARD,
    TEST_LAYER_LEAF_MATRIX_CELL,
    TestMeshPlan,
    TestPartitionItem,
    TestResultReuseTicket,
    TestSuiteEvidence,
    TestTargetSplitDerivation,
    review_test_mesh,
)


def suite(suite_id, **kwargs):
    defaults = {
        "result_status": "passed",
        "evidence_tier": EVIDENCE_ABSTRACT_GREEN,
        "test_count": 1,
        "selected_count": 1,
    }
    defaults.update(kwargs)
    return TestSuiteEvidence(suite_id, **defaults)


def path_quality(model_id="checkout", currentness_id="snapshot:current"):
    fp = lambda value: fingerprint_value({"value": value})
    owner = PathQualitySubject(
        model_id=model_id,
        boundary_id=f"boundary:{model_id}",
        model_fingerprint=fp(f"model:{model_id}"),
        normalized_facts_fingerprint=fp(f"facts:{model_id}"),
        retained_element_inventory_fingerprint=fp(f"retained:{model_id}"),
        purpose_fingerprint=fp(f"purpose:{model_id}"),
        intent_fingerprint=fp(f"intent:{model_id}"),
        obligation_fingerprint=fp(f"obligations:{model_id}"),
        provider_fingerprint=fp(f"provider:{model_id}"),
        dependency_fingerprint=fp(f"dependencies:{model_id}"),
        code_fingerprint=fp(f"code:{model_id}"),
        test_fingerprint=fp(f"tests:{model_id}"),
        oracle_fingerprint=fp(f"oracles:{model_id}"),
        evidence_fingerprint=fp(f"evidence:{model_id}"),
        currentness_id=currentness_id,
    )
    result = PathQualityResult(
        result_id=f"path-quality:{model_id}",
        subject_fingerprint=owner.fingerprint,
        mode="lightweight",
        trigger_ids=(),
        finding_ids=(),
        candidate_ids=(),
        rewrite_rule_ids=(),
        conclusion="single_clear_path",
        unresolved_ids=(),
        selected_candidate_id="",
        selected_candidate_lane="",
        comparison_boundary_id="",
        candidate_set_fingerprint="",
        rewrite_set_fingerprint="",
        necessity_witness_set_fingerprint=fp(f"witnesses:{model_id}"),
        detail_evidence_fingerprint=fp(f"detail:{model_id}"),
        producer_id="model_maturation",
        currentness_id=currentness_id,
    )
    return owner, result


def path_quality_suite_binding(owner, result):
    return {
        "path_quality_model_fingerprints": {
            owner.model_id: owner.model_fingerprint
        },
        "path_quality_subject_fingerprints": {
            owner.model_id: owner.fingerprint
        },
        "path_quality_result_fingerprints": {
            owner.model_id: result.fingerprint
        },
        "path_quality_currentness_ids": {
            owner.model_id: owner.currentness_id
        },
    }


def verified_suite_binding(
    suite_id,
    *,
    obligation_ids,
    partition_item_ids=(),
    leaf_cell_ids=(),
    transition_cell_ids=(),
    payload_case_ids=(),
    generated_case_ids=(),
    coverage_shard_ids=(),
    producer_id="flowguard.test-mesh",
):
    environment = build_environment_fingerprint(
        {
            "python_implementation": "CPython",
            "python_version": "3.12.10",
            "platform_system": "Windows",
            "platform_machine": "AMD64-test",
            "flowguard_version": "0.64.1",
        }
    )
    digest = lambda label: fingerprint_value({"label": label, "suite": suite_id})
    inventory = {
        "partition_item_ids": tuple(partition_item_ids),
        "leaf_cell_ids": tuple(leaf_cell_ids),
        "transition_cell_ids": tuple(transition_cell_ids),
        "payload_case_ids": tuple(payload_case_ids),
        "generated_case_ids": tuple(generated_case_ids),
        "coverage_shard_ids": tuple(coverage_shard_ids),
        "required_obligation_ids": tuple(obligation_ids),
    }
    value = EvidenceReceipt(
        receipt_id=f"receipt:{suite_id}",
        subject_id=suite_id,
        subject_kind="test_mesh_child",
        producer_id=producer_id,
        producer_version="0.64.1",
        claim_scope="full",
        command=("python", "-m", "pytest", suite_id),
        working_directory_token="<WORKSPACE>",
        started_at="2026-07-28T08:00:00+00:00",
        finished_at="2026-07-28T08:00:01+00:00",
        exit_code=0,
        environment_fingerprint=environment.fingerprint,
        environment_metadata=environment.metadata,
        contract_hash=digest("contract"),
        check_manifest_hash=digest("manifest"),
        suite_map_hash=digest("suite"),
        input_snapshots=(
            snapshot_bytes(
                "suite-input",
                suite_id.encode(),
                path_token=f"<WORKSPACE>/tests/{suite_id}.py",
                obligation_ids=obligation_ids,
            ),
        ),
        proof_artifact_id=f"proof:{suite_id}",
        proof_artifact_fingerprint=digest("proof"),
        result_status="pass",
        result_fingerprint=digest("result"),
        covered_obligations=tuple(obligation_ids),
        claim_boundary="Exact TestMesh child fixture only.",
        metadata={
            "coverage_inventory": {
                key: list(values) for key, values in inventory.items()
            }
        },
    )
    context = ReceiptVerificationContext(
        input_snapshots={item.artifact_id: item for item in value.input_snapshots},
        contract_hash=value.contract_hash,
        check_manifest_hash=value.check_manifest_hash,
        suite_map_hash=value.suite_map_hash,
        producer_id=value.producer_id,
        producer_version=value.producer_version,
        environment_fingerprint=value.environment_fingerprint,
        proof_artifact_fingerprint=value.proof_artifact_fingerprint,
        result_fingerprint=value.result_fingerprint,
        command=value.command,
        working_directory_token=value.working_directory_token,
        proof_artifact_id=value.proof_artifact_id,
        required_obligation_ids=value.covered_obligations,
        eligible_claim_scopes=("full",),
    )
    verification = verify_evidence_receipt(value, context)
    if not verification.ok:
        raise AssertionError(verification.to_dict())
    return {
        "loaded_receipt": value,
        "receipt_verification_context": context,
        "receipt_verification": verification,
        "receipt_producer_id": producer_id,
    }


def final_suite(suite_id, *inventory_item_ids, revision="inventory:v1", **kwargs):
    defaults = {
        "inventory_revision": revision,
        "owned_inventory_item_ids": tuple(inventory_item_ids),
        "run_id": f"run:{suite_id}:1",
        "terminal_status": "passed",
        "exit_code": 0,
        "result_path": f"tmp/{suite_id}.json",
        "result_fingerprint": f"sha256:{suite_id}",
        "covered_obligation_ids": tuple(inventory_item_ids),
        "artifact_version": "artifact:v1",
        "verifier_version": "flowguard:0.54.1",
    }
    defaults.update(kwargs)
    return suite(suite_id, **defaults)


def proof_artifact(artifact_id, *covered):
    return ProofArtifactRef(
        artifact_id,
        result_status="passed",
        exit_code=0,
        result_path=f"tmp/{artifact_id.replace(':', '_')}.json",
        artifact_fingerprints={f"tmp/{artifact_id.replace(':', '_')}.json": "sha256:test"},
        covered_obligation_ids=covered,
    )


def reuse_ticket(suite_id, *covered, **kwargs):
    defaults = {
        "previous_evidence_id": f"{suite_id}@previous",
        "reason": "same command, source, tested artifact, dependency, environment, and result fingerprints",
        "command_fingerprint": "sha256:command",
        "test_source_fingerprint": "sha256:test-source",
        "tested_artifact_fingerprint": "sha256:tested-artifact",
        "dependency_fingerprints": {"flowguard": "0.39.2"},
        "environment_fingerprint": "python:3.12",
        "result_fingerprint": "sha256:result",
        "covered_obligation_ids": covered,
        "producer_receipt_id": f"receipt:{suite_id}",
        "producer_terminal": True,
        "producer_status": "pass",
        "producer_execution_owner_id": "owner:test-mesh",
        "current_execution_owner_id": "owner:test-mesh",
        "producer_fingerprints": {
            "command": "sha256:command",
            "test_source": "sha256:test-source",
            "tested_artifact": "sha256:tested-artifact",
            "dependencies": "sha256:dependencies",
            "environment": "python:3.12",
            "result": "sha256:result",
            "coverage_scope": "sha256:coverage",
        },
        "current_fingerprints": {
            "command": "sha256:command",
            "test_source": "sha256:test-source",
            "tested_artifact": "sha256:tested-artifact",
            "dependencies": "sha256:dependencies",
            "environment": "python:3.12",
            "result": "sha256:result",
            "coverage_scope": "sha256:coverage",
        },
    }
    defaults.update(kwargs)
    return TestResultReuseTicket(suite_id, **defaults)


def target(source_model_id, suite_ids, item_ids, *, state=False, side_effect=False):
    return TestTargetSplitDerivation(
        source_model_id,
        target_suite_ids=tuple(suite_ids),
        covered_partition_item_ids=tuple(item_ids),
        state_owner_fields=("state_owner_map",) if state else (),
        side_effect_owner_fields=("side_effect_owner_map",) if side_effect else (),
        rationale="derived from parent FlowGuard validation structure model",
    )


class TestMeshTests(unittest.TestCase):
    def test_test_mesh_consumes_exact_current_model_path_quality_per_partition(self):
        owner, result = path_quality()
        plan = TestMeshPlan(
            parent_suite_id="checkout-parent",
            partition_items=(
                TestPartitionItem(
                    "behavior:checkout",
                    owner_suite_id="checkout-tests",
                    model_id=owner.model_id,
                ),
            ),
            child_suites=(
                suite(
                    "checkout-tests",
                    owned_obligation_ids=("behavior:checkout",),
                    covered_obligation_ids=("behavior:checkout",),
                    **path_quality_suite_binding(owner, result),
                ),
            ),
            target_split_derivation=target(
                "checkout-validation",
                ("checkout-tests",),
                ("behavior:checkout",),
            ),
            required_path_quality_model_ids=(owner.model_id,),
            path_quality_subjects=(owner,),
            path_quality_results=(result,),
            path_quality_currentness_id=owner.currentness_id,
            current_model_fingerprints={
                owner.model_id: owner.model_fingerprint
            },
        )

        report = review_test_mesh(plan)

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual((owner.model_id,), report.path_quality_verified_model_ids)
        self.assertEqual((), report.path_quality_blocked_model_ids)
        self.assertTrue(report.path_quality_result_set_fingerprint)

    def test_test_mesh_blocks_missing_or_foreign_path_quality_test_binding(self):
        owner, result = path_quality()
        foreign = fingerprint_value({"value": "foreign-path-result"})
        cases = (
            ({}, "path_quality_test_model_fingerprint_mismatch"),
            (
                {
                    **path_quality_suite_binding(owner, result),
                    "path_quality_result_fingerprints": {
                        owner.model_id: foreign
                    },
                },
                "path_quality_test_result_fingerprint_mismatch",
            ),
        )
        for bindings, expected_code in cases:
            with self.subTest(expected_code=expected_code):
                report = review_test_mesh(
                    TestMeshPlan(
                        parent_suite_id="checkout-parent",
                        partition_items=(
                            TestPartitionItem(
                                "behavior:checkout",
                                owner_suite_id="checkout-tests",
                                model_id=owner.model_id,
                            ),
                        ),
                        child_suites=(
                            suite(
                                "checkout-tests",
                                owned_obligation_ids=("behavior:checkout",),
                                covered_obligation_ids=("behavior:checkout",),
                                **bindings,
                            ),
                        ),
                        target_split_derivation=target(
                            "checkout-validation",
                            ("checkout-tests",),
                            ("behavior:checkout",),
                        ),
                        required_path_quality_model_ids=(owner.model_id,),
                        path_quality_subjects=(owner,),
                        path_quality_results=(result,),
                        path_quality_currentness_id=owner.currentness_id,
                        current_model_fingerprints={
                            owner.model_id: owner.model_fingerprint
                        },
                    )
                )

                self.assertFalse(report.ok)
                self.assertEqual(
                    "path_quality_test_evidence_required", report.decision
                )
                codes = {finding.code for finding in report.findings}
                self.assertIn(expected_code, codes)
                self.assertIn("path_quality_test_evidence_missing", codes)
                self.assertEqual(
                    (owner.model_id,), report.path_quality_blocked_model_ids
                )

    def test_test_mesh_blocks_unresolved_normative_and_stale_path_quality(self):
        owner, clean_result = path_quality()
        fp = lambda value: fingerprint_value({"value": value})
        normative = replace(
            clean_result,
            mode="deep",
            trigger_ids=("explicit_request",),
            candidate_ids=("observed", "target"),
            conclusion="preferred_within_candidates",
            selected_candidate_id="target",
            selected_candidate_lane="normative_target",
            comparison_boundary_id="boundary:named",
            candidate_set_fingerprint=fp("candidate-set"),
        )
        cases = (
            (
                replace(
                    clean_result,
                    conclusion="unresolved",
                    unresolved_ids=("gap:path-quality",),
                ),
                "path_quality_result_unresolved",
            ),
            (normative, "path_quality_normative_target_not_observed"),
            (replace(clean_result, current=False), "path_quality_result_stale"),
        )
        for result, expected_code in cases:
            with self.subTest(expected_code=expected_code):
                report = review_test_mesh(
                    TestMeshPlan(
                        parent_suite_id="checkout-parent",
                        partition_items=(
                            TestPartitionItem(
                                "behavior:checkout",
                                owner_suite_id="checkout-tests",
                                model_id=owner.model_id,
                            ),
                        ),
                        child_suites=(
                            suite(
                                "checkout-tests",
                                owned_obligation_ids=("behavior:checkout",),
                                covered_obligation_ids=("behavior:checkout",),
                                **path_quality_suite_binding(owner, result),
                            ),
                        ),
                        target_split_derivation=target(
                            "checkout-validation",
                            ("checkout-tests",),
                            ("behavior:checkout",),
                        ),
                        required_path_quality_model_ids=(owner.model_id,),
                        path_quality_subjects=(owner,),
                        path_quality_results=(result,),
                        path_quality_currentness_id=owner.currentness_id,
                        current_model_fingerprints={
                            owner.model_id: owner.model_fingerprint
                        },
                    )
                )

                self.assertFalse(report.ok)
                self.assertIn(
                    expected_code,
                    {finding.code for finding in report.findings},
                )
                self.assertEqual(
                    (owner.model_id,), report.path_quality_blocked_model_ids
                )

    def test_diagnostic_campaign_preserves_complete_execution_accounting(self):
        child = suite(
            "diagnostic:complete",
            planned_count=2,
            executed_count=2,
            failed_count=0,
            not_run_count=0,
            diagnostic_campaign_id="campaign:complete",
            diagnostic_boundary="declared_complete",
        )
        report = review_test_mesh(TestMeshPlan("diagnostic-parent", child_suites=(child,)))
        campaign_codes = {
            finding.code for finding in report.findings if finding.code.startswith("diagnostic_")
        }
        self.assertEqual(set(), campaign_codes)

    def test_diagnostic_campaign_blocks_false_completeness_and_unlinked_failures(self):
        child = suite(
            "diagnostic:false-complete",
            planned_count=3,
            executed_count=1,
            failed_count=1,
            not_run_count=2,
            not_run_reason="stopped after a hard blocker",
            diagnostic_campaign_id="campaign:false-complete",
            diagnostic_boundary="declared_complete",
        )
        report = review_test_mesh(TestMeshPlan("diagnostic-parent", child_suites=(child,)))
        codes = {finding.code for finding in report.findings}
        self.assertIn("diagnostic_false_completeness", codes)
        self.assertIn("diagnostic_finding_missing", codes)

    def test_test_mesh_has_no_openspec_session_or_receipt_bridge(self):
        child = suite("check.one")
        payload = child.to_dict()
        for retired in (
            "spec_session_id",
            "spec_consumer_ids",
            "spec_execution_state",
            "spec_receipt_id",
            "spec_work_package_id",
            "spec_check_id",
        ):
            self.assertNotIn(retired, payload)

        with self.assertRaises(TypeError):
            suite("legacy", spec_session_id="session:one")
    def test_complete_test_mesh_can_continue(self):
        plan = TestMeshPlan(
            parent_suite_id="router-runtime",
            partition_items=(
                TestPartitionItem("controller", owner_suite_id="controller"),
                TestPartitionItem("packets", owner_suite_id="packets"),
            ),
            child_suites=(suite("controller"), suite("packets")),
            target_split_derivation=target(
                "router-runtime-validation",
                ("controller", "packets"),
                ("controller", "packets"),
            ),
        )

        report = review_test_mesh(plan)

        self.assertTrue(report.ok)
        self.assertEqual("test_mesh_green_can_continue", report.decision)
        self.assertEqual([], report.to_dict()["findings"])
        self.assertIn("flowguard test mesh", report.format_text())

    def test_revisioned_required_inventory_with_final_receipts_can_continue(self):
        plan = TestMeshPlan(
            parent_suite_id="router-runtime",
            partition_items=(
                TestPartitionItem("controller", owner_suite_id="controller", inventory_revision="inventory:v1"),
                TestPartitionItem("packets", owner_suite_id="packets", inventory_revision="inventory:v1"),
            ),
            child_suites=(
                final_suite("controller", "controller"),
                final_suite("packets", "packets"),
            ),
            target_split_derivation=target(
                "router-runtime-validation",
                ("controller", "packets"),
                ("controller", "packets"),
            ),
            inventory_revision="inventory:v1",
            coverage_inventory_id="coverage:router-runtime",
            coverage_inventory_revision="inventory:v1",
            coverage_inventory_fingerprint="sha256:coverage-v1",
            coverage_inventory_evidence_ids=("inventory-discovery:v1",),
            required_inventory_item_ids=("controller", "packets"),
            require_complete_inventory=True,
            require_final_receipts=True,
        )

        report = review_test_mesh(plan)

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual(("controller", "packets"), report.covered_inventory_item_ids)
        self.assertEqual("inventory:v1", report.inventory_revision)

    def test_caller_subset_cannot_replace_complete_required_inventory(self):
        plan = TestMeshPlan(
            parent_suite_id="router-runtime",
            partition_items=(
                TestPartitionItem("controller", owner_suite_id="controller", inventory_revision="inventory:v2"),
            ),
            child_suites=(final_suite("controller", "controller", revision="inventory:v2"),),
            target_split_derivation=target(
                "router-runtime-validation",
                ("controller",),
                ("controller",),
            ),
            inventory_revision="inventory:v2",
            coverage_inventory_id="coverage:router-runtime",
            coverage_inventory_revision="inventory:v2",
            coverage_inventory_fingerprint="sha256:coverage-v2",
            coverage_inventory_evidence_ids=("inventory-discovery:v2",),
            required_inventory_item_ids=("controller", "packets"),
            require_complete_inventory=True,
        )

        report = review_test_mesh(plan)

        self.assertFalse(report.ok)
        self.assertEqual("test_inventory_required", report.decision)
        self.assertIn("required_inventory_item_missing", [finding.code for finding in report.findings])
        self.assertEqual(("packets",), report.missing_inventory_item_ids)

    def test_work_context_status_cannot_become_test_evidence(self):
        context_id = "work-context:planner:status"
        report = review_test_mesh(
            TestMeshPlan(
                parent_suite_id="context-is-not-evidence",
                partition_items=(
                    TestPartitionItem(
                        context_id,
                        owner_suite_id="provider-status",
                        planning_context_only=True,
                    ),
                ),
                child_suites=(
                    suite(
                        "provider-status",
                        owned_inventory_item_ids=(context_id,),
                        covered_obligation_ids=(context_id,),
                    ),
                ),
                planning_context_ids=(context_id,),
                inventory_revision="inventory:v1",
                coverage_inventory_id="coverage:context",
                coverage_inventory_revision="inventory:v1",
                coverage_inventory_fingerprint="sha256:coverage-context",
                coverage_inventory_evidence_ids=("discovery:context",),
                required_inventory_item_ids=(context_id,),
                require_complete_inventory=True,
            )
        )

        self.assertFalse(report.ok)
        self.assertIn(
            "planning_context_not_test_evidence",
            {finding.code for finding in report.findings},
        )

    def test_delegated_item_requires_current_native_evidence(self):
        item_id = "ui:observed:button"
        report = review_test_mesh(
            TestMeshPlan(
                parent_suite_id="delegated-native-evidence",
                partition_items=(
                    TestPartitionItem(
                        item_id,
                        owner_suite_id="ui-validator",
                        inventory_revision="inventory:v1",
                        coverage_disposition="delegated",
                        native_owner_id="ui:observed",
                        required_native_evidence_ids=("evidence:browser-click",),
                    ),
                ),
                child_suites=(
                    final_suite(
                        "ui-validator",
                        item_id,
                        covered_obligation_ids=(item_id,),
                    ),
                ),
                inventory_revision="inventory:v1",
                coverage_inventory_id="coverage:ui",
                coverage_inventory_revision="inventory:v1",
                coverage_inventory_fingerprint="sha256:coverage-ui",
                coverage_inventory_evidence_ids=("discovery:ui",),
                required_inventory_item_ids=(item_id,),
                require_complete_inventory=True,
                require_final_receipts=True,
            )
        )

        self.assertFalse(report.ok)
        self.assertIn(
            "delegated_inventory_native_evidence_not_current",
            {finding.code for finding in report.findings},
        )

    def test_leaf_matrix_cell_evidence_can_support_parent_gate(self):
        plan = TestMeshPlan(
            parent_suite_id="leaf-validation",
            partition_items=(
                TestPartitionItem("submit.empty:idle", item_type="leaf_boundary_matrix", owner_suite_id="leaf-cells"),
            ),
            child_suites=(
                suite(
                    "leaf-cells",
                    layer=TEST_LAYER_LEAF_MATRIX_CELL,
                    owned_leaf_cell_ids=("submit.empty:idle",),
                ),
            ),
            target_split_derivation=target(
                "leaf-validation-model",
                ("leaf-cells",),
                ("submit.empty:idle",),
            ),
            required_leaf_cell_ids=("submit.empty:idle",),
        )

        report = review_test_mesh(plan)

        self.assertTrue(report.ok, report.format_text())

    def test_contract_coverage_shard_evidence_can_support_parent_gate(self):
        plan = TestMeshPlan(
            parent_suite_id="contract-validation",
            partition_items=(
                TestPartitionItem(
                    "contract_shard:packet-router:packet-evidence",
                    item_type="contract_coverage_shard",
                    owner_suite_id="contract-shards",
                ),
            ),
            child_suites=(
                suite(
                    "contract-shards",
                    layer=TEST_LAYER_CONTRACT_COMBINATION_SHARD,
                    owned_coverage_shard_ids=("contract_shard:packet-router:packet-evidence",),
                ),
            ),
            target_split_derivation=target(
                "contract-validation-model",
                ("contract-shards",),
                ("contract_shard:packet-router:packet-evidence",),
            ),
            required_coverage_shard_ids=("contract_shard:packet-router:packet-evidence",),
        )

        report = review_test_mesh(plan)

        self.assertTrue(report.ok, report.format_text())

    def test_missing_contract_coverage_shard_evidence_blocks_parent_gate(self):
        plan = TestMeshPlan(
            parent_suite_id="contract-validation",
            partition_items=(
                TestPartitionItem(
                    "contract_shard:packet-router:packet-evidence",
                    item_type="contract_coverage_shard",
                    owner_suite_id="contract-shards",
                ),
            ),
            child_suites=(
                suite("contract-shards", layer=TEST_LAYER_CONTRACT_COMBINATION_SHARD),
            ),
            target_split_derivation=target(
                "contract-validation-model",
                ("contract-shards",),
                ("contract_shard:packet-router:packet-evidence",),
            ),
            required_coverage_shard_ids=("contract_shard:packet-router:packet-evidence",),
        )

        report = review_test_mesh(plan)

        self.assertFalse(report.ok)
        self.assertEqual("contract_coverage_shard_evidence_required", report.decision)
        self.assertIn("contract_coverage_shard_evidence_missing", [finding.code for finding in report.findings])

    def test_missing_leaf_matrix_cell_evidence_blocks_parent_gate(self):
        plan = TestMeshPlan(
            parent_suite_id="leaf-validation",
            partition_items=(
                TestPartitionItem("submit.empty:idle", item_type="leaf_boundary_matrix", owner_suite_id="leaf-cells"),
            ),
            child_suites=(
                suite("leaf-cells", layer=TEST_LAYER_LEAF_MATRIX_CELL),
            ),
            target_split_derivation=target(
                "leaf-validation-model",
                ("leaf-cells",),
                ("submit.empty:idle",),
            ),
            required_leaf_cell_ids=("submit.empty:idle",),
        )

        report = review_test_mesh(plan)

        self.assertFalse(report.ok)
        self.assertEqual("leaf_matrix_cell_evidence_required", report.decision)
        self.assertIn("leaf_matrix_cell_owner_missing", [finding.code for finding in report.findings])
        self.assertIn("leaf_matrix_cell_evidence_missing", [finding.code for finding in report.findings])

    def test_background_leaf_matrix_cell_progress_is_not_parent_evidence(self):
        plan = TestMeshPlan(
            parent_suite_id="leaf-validation",
            partition_items=(
                TestPartitionItem("submit.empty:idle", item_type="leaf_boundary_matrix", owner_suite_id="leaf-cells"),
            ),
            child_suites=(
                suite(
                    "leaf-cells",
                    layer=TEST_LAYER_LEAF_MATRIX_CELL,
                    owned_leaf_cell_ids=("submit.empty:idle",),
                    background=True,
                    has_exit_artifact=False,
                    has_result_artifact=False,
                    progress_only=True,
                ),
            ),
            target_split_derivation=target(
                "leaf-validation-model",
                ("leaf-cells",),
                ("submit.empty:idle",),
            ),
            required_leaf_cell_ids=("submit.empty:idle",),
        )

        report = review_test_mesh(plan)

        self.assertFalse(report.ok)
        self.assertEqual("final_receipt_required", report.decision)
        self.assertIn("background_incomplete", [finding.code for finding in report.findings])
        self.assertIn("leaf_matrix_cell_evidence_missing", [finding.code for finding in report.findings])

    def test_missing_partition_owner_blocks_parent_green(self):
        plan = TestMeshPlan(
            parent_suite_id="router-runtime",
            partition_items=(TestPartitionItem("startup", owner_suite_id=""),),
            child_suites=(suite("controller"),),
            target_split_derivation=target("router-runtime-validation", ("controller",), ("startup",)),
        )

        report = review_test_mesh(plan)

        self.assertFalse(report.ok)
        self.assertEqual("coverage_gap_blocked", report.decision)
        self.assertIn("coverage_gap", [finding.code for finding in report.findings])

    def test_unregistered_partition_owner_blocks_parent_green(self):
        plan = TestMeshPlan(
            parent_suite_id="router-runtime",
            partition_items=(TestPartitionItem("startup", owner_suite_id="startup-daemon"),),
            child_suites=(suite("controller"),),
            target_split_derivation=target("router-runtime-validation", ("controller",), ("startup",)),
        )

        report = review_test_mesh(plan)

        self.assertFalse(report.ok)
        self.assertEqual("coverage_gap_blocked", report.decision)

    def test_duplicate_partition_state_and_side_effect_ownership_block(self):
        plan = TestMeshPlan(
            parent_suite_id="router-runtime",
            partition_items=(
                TestPartitionItem("route-state", owner_suite_id="route-a"),
                TestPartitionItem("route-state", owner_suite_id="route-b"),
            ),
            child_suites=(
                suite("route-a", owns_state=("run_state",), owns_side_effects=("write_ledger",)),
                suite("route-b", owns_state=("run_state",), owns_side_effects=("write_ledger",)),
            ),
            target_split_derivation=target(
                "router-runtime-validation",
                ("route-a", "route-b"),
                ("route-state",),
                state=True,
                side_effect=True,
            ),
        )

        report = review_test_mesh(plan)
        codes = [finding.code for finding in report.findings]

        self.assertFalse(report.ok)
        self.assertEqual("ownership_conflict", report.decision)
        self.assertIn("duplicate_partition_owner", codes)
        self.assertIn("duplicate_state_owner", codes)
        self.assertIn("duplicate_side_effect_owner", codes)

    def test_background_progress_without_exit_artifact_is_incomplete(self):
        plan = TestMeshPlan(
            parent_suite_id="router-runtime",
            partition_items=(TestPartitionItem("startup", owner_suite_id="startup"),),
            child_suites=(
                suite(
                    "startup",
                    background=True,
                    has_exit_artifact=False,
                    has_result_artifact=False,
                    progress_only=True,
                ),
            ),
            target_split_derivation=target("router-runtime-validation", ("startup",), ("startup",)),
        )

        report = review_test_mesh(plan)

        self.assertFalse(report.ok)
        self.assertEqual("final_receipt_required", report.decision)
        self.assertIn("background_incomplete", [finding.code for finding in report.findings])

    def test_foreground_progress_only_status_never_counts_as_pass(self):
        plan = TestMeshPlan(
            parent_suite_id="router-runtime",
            partition_items=(TestPartitionItem("startup", owner_suite_id="startup"),),
            child_suites=(suite("startup", progress_only=True),),
            target_split_derivation=target("router-runtime-validation", ("startup",), ("startup",)),
        )

        report = review_test_mesh(plan)

        self.assertFalse(report.ok)
        self.assertEqual("final_receipt_required", report.decision)
        self.assertIn("suite_progress_only", [finding.code for finding in report.findings])

    def test_reused_child_suite_requires_ticket_and_proof_artifact(self):
        plan = TestMeshPlan(
            parent_suite_id="router-runtime",
            partition_items=(TestPartitionItem("startup", owner_suite_id="startup"),),
            child_suites=(suite("startup", result_reused=True),),
            target_split_derivation=target("router-runtime-validation", ("startup",), ("startup",)),
        )

        report = review_test_mesh(plan)
        codes = [finding.code for finding in report.findings]

        self.assertFalse(report.ok)
        self.assertEqual("test_reuse_proof_required", report.decision)
        self.assertIn("missing_test_reuse_ticket", codes)
        self.assertIn("test_reuse_missing_proof_artifact", codes)

    def test_reused_child_suite_can_support_parent_with_current_proof(self):
        plan = TestMeshPlan(
            parent_suite_id="router-runtime",
            partition_items=(TestPartitionItem("startup", owner_suite_id="startup"),),
            child_suites=(
                suite(
                    "startup",
                    result_reused=True,
                    reuse_ticket=reuse_ticket(
                        "startup",
                        "startup",
                        "obligation:startup",
                    ),
                    proof_artifact=proof_artifact(
                        "artifact:startup",
                        "startup",
                        "obligation:startup",
                    ),
                    owned_obligation_ids=("obligation:startup",),
                    **verified_suite_binding(
                        "startup",
                        obligation_ids=("obligation:startup",),
                        partition_item_ids=("startup",),
                    ),
                ),
            ),
            target_split_derivation=target("router-runtime-validation", ("startup",), ("startup",)),
        )

        report = review_test_mesh(plan)

        self.assertTrue(report.ok, report.format_text())

    def test_self_consistent_ticket_and_proof_cannot_replace_loaded_receipt(self):
        report = review_test_mesh(
            TestMeshPlan(
                parent_suite_id="router-runtime",
                partition_items=(
                    TestPartitionItem("startup", owner_suite_id="startup"),
                ),
                child_suites=(
                    suite(
                        "startup",
                        result_reused=True,
                        reuse_ticket=reuse_ticket("startup", "startup"),
                        proof_artifact=proof_artifact(
                            "artifact:startup",
                            "startup",
                        ),
                    ),
                ),
                target_split_derivation=target(
                    "router-runtime-validation",
                    ("startup",),
                    ("startup",),
                ),
            )
        )

        self.assertFalse(report.ok)
        self.assertEqual("test_reuse_receipt_required", report.decision)
        self.assertIn(
            "verified_receipt_missing",
            [finding.code for finding in report.findings],
        )

    def test_reused_child_receipt_requires_exact_typed_owner_inventory(self):
        all_owned = (
            "partition:startup",
            "leaf:startup",
            "transition:startup",
            "payload:startup",
            "generated:startup",
            "shard:startup",
            "obligation:startup",
        )
        common = {
            "result_reused": True,
            "reuse_ticket": reuse_ticket("startup", *all_owned),
            "proof_artifact": proof_artifact("artifact:startup", *all_owned),
            "owned_inventory_item_ids": ("partition:startup",),
            "owned_leaf_cell_ids": ("leaf:startup",),
            "owned_transition_cell_ids": ("transition:startup",),
            "owned_payload_case_ids": ("payload:startup",),
            "owned_generated_case_ids": ("generated:startup",),
            "owned_coverage_shard_ids": ("shard:startup",),
            "owned_obligation_ids": ("obligation:startup",),
        }
        exact_binding = verified_suite_binding(
            "startup",
            obligation_ids=("obligation:startup",),
            partition_item_ids=("partition:startup",),
            leaf_cell_ids=("leaf:startup",),
            transition_cell_ids=("transition:startup",),
            payload_case_ids=("payload:startup",),
            generated_case_ids=("generated:startup",),
            coverage_shard_ids=("shard:startup",),
        )
        exact_plan = TestMeshPlan(
            parent_suite_id="router-runtime",
            partition_items=(
                TestPartitionItem(
                    "partition:startup",
                    owner_suite_id="startup",
                ),
            ),
            child_suites=(suite("startup", **common, **exact_binding),),
            required_leaf_cell_ids=("leaf:startup",),
            required_coverage_shard_ids=("shard:startup",),
            target_split_derivation=target(
                "router-runtime-validation",
                ("startup",),
                ("partition:startup",),
            ),
        )
        self.assertTrue(
            review_test_mesh(exact_plan).ok,
            review_test_mesh(exact_plan).format_text(),
        )

        incomplete_binding = verified_suite_binding(
            "startup",
            obligation_ids=("obligation:startup",),
            partition_item_ids=("partition:startup",),
        )
        incomplete = review_test_mesh(
            TestMeshPlan(
                parent_suite_id="router-runtime",
                partition_items=exact_plan.partition_items,
                child_suites=(suite("startup", **common, **incomplete_binding),),
                required_leaf_cell_ids=exact_plan.required_leaf_cell_ids,
                required_coverage_shard_ids=exact_plan.required_coverage_shard_ids,
                target_split_derivation=exact_plan.target_split_derivation,
            )
        )
        self.assertFalse(incomplete.ok)
        self.assertIn(
            "verified_receipt_inventory_mismatch",
            [finding.code for finding in incomplete.findings],
        )

    def test_reused_child_rejects_tampered_verification_projection(self):
        binding = verified_suite_binding(
            "startup",
            obligation_ids=("obligation:startup",),
            partition_item_ids=("startup",),
        )
        binding["receipt_verification"] = replace(
            binding["receipt_verification"],
            receipt_id="receipt:another-suite",
        )
        report = review_test_mesh(
            TestMeshPlan(
                parent_suite_id="router-runtime",
                partition_items=(
                    TestPartitionItem("startup", owner_suite_id="startup"),
                ),
                child_suites=(
                    suite(
                        "startup",
                        result_reused=True,
                        reuse_ticket=reuse_ticket(
                            "startup",
                            "startup",
                            "obligation:startup",
                        ),
                        proof_artifact=proof_artifact(
                            "artifact:startup",
                            "startup",
                            "obligation:startup",
                        ),
                        owned_inventory_item_ids=("startup",),
                        owned_obligation_ids=("obligation:startup",),
                        **binding,
                    ),
                ),
                target_split_derivation=target(
                    "router-runtime-validation",
                    ("startup",),
                    ("startup",),
                ),
            )
        )

        self.assertFalse(report.ok)
        self.assertEqual("test_reuse_receipt_required", report.decision)
        self.assertIn(
            "receipt_verification_projection_mismatch",
            [finding.code for finding in report.findings],
        )

    def test_reused_background_progress_artifact_is_not_completion(self):
        plan = TestMeshPlan(
            parent_suite_id="router-runtime",
            partition_items=(TestPartitionItem("startup", owner_suite_id="startup"),),
            child_suites=(
                suite(
                    "startup",
                    result_reused=True,
                    reuse_ticket=reuse_ticket("startup"),
                    proof_artifact=ProofArtifactRef(
                        "artifact:startup",
                        result_status="passed",
                        exit_code=0,
                        result_path="tmp/startup.json",
                        artifact_fingerprints={"tmp/startup.json": "sha256:test"},
                        progress_only=True,
                    ),
                ),
            ),
            target_split_derivation=target("router-runtime-validation", ("startup",), ("startup",)),
        )

        report = review_test_mesh(plan)

        self.assertFalse(report.ok)
        self.assertEqual("test_reuse_proof_required", report.decision)
        self.assertIn("test_reuse_progress_only_proof_artifact", [finding.code for finding in report.findings])

    def test_failed_timeout_and_stale_suites_are_not_parent_green(self):
        for status, decision in (("failed", "test_failure_blocked"), ("timeout", "test_timeout_blocked")):
            with self.subTest(status=status):
                plan = TestMeshPlan(
                    parent_suite_id="router-runtime",
                    partition_items=(TestPartitionItem(status, owner_suite_id=status),),
                    child_suites=(suite(status, result_status=status),),
                    target_split_derivation=target("router-runtime-validation", (status,), (status,)),
                )
                self.assertEqual(decision, review_test_mesh(plan).decision)

        stale = TestMeshPlan(
            parent_suite_id="router-runtime",
            partition_items=(TestPartitionItem("controller", owner_suite_id="controller"),),
            child_suites=(suite("controller", evidence_current=False, stale_reasons=("source_changed",)),),
            target_split_derivation=target("router-runtime-validation", ("controller",), ("controller",)),
        )
        self.assertEqual("stale_test_evidence", review_test_mesh(stale).decision)

    def test_hidden_skipped_tests_are_not_accepted(self):
        plan = TestMeshPlan(
            parent_suite_id="router-runtime",
            partition_items=(TestPartitionItem("cards", owner_suite_id="cards"),),
            child_suites=(suite("cards", skipped_count=2, skipped_visible=False),),
            target_split_derivation=target("router-runtime-validation", ("cards",), ("cards",)),
        )

        report = review_test_mesh(plan)

        self.assertFalse(report.ok)
        self.assertEqual("hidden_skipped_tests", report.decision)

    def test_evidence_tier_below_required_is_visible(self):
        plan = TestMeshPlan(
            parent_suite_id="release",
            required_evidence_tier=EVIDENCE_CONFORMANCE_GREEN,
            partition_items=(TestPartitionItem("publish", owner_suite_id="publish"),),
            child_suites=(suite("publish", evidence_tier=EVIDENCE_ABSTRACT_GREEN),),
            target_split_derivation=target("release-validation", ("publish",), ("publish",)),
        )

        report = review_test_mesh(plan)

        self.assertFalse(report.ok)
        self.assertEqual("insufficient_evidence", report.decision)
        self.assertIn("insufficient_evidence_tier", [finding.code for finding in report.findings])

    def test_routine_scope_can_defer_release_only_suite(self):
        plan = TestMeshPlan(
            parent_suite_id="validation",
            decision_scope="routine",
            partition_items=(TestPartitionItem("unit", owner_suite_id="unit"),),
            child_suites=(
                suite("unit"),
                suite("full-release", layer="release", release_required=True, result_status="not_run"),
            ),
            target_split_derivation=target("validation-model", ("unit", "full-release"), ("unit",)),
        )

        report = review_test_mesh(plan)

        self.assertTrue(report.ok)
        self.assertEqual("test_mesh_green_can_continue", report.decision)
        self.assertEqual(("full-release",), report.release_obligations)
        self.assertIn("release_suite_deferred", [finding.code for finding in report.findings])

    def test_release_scope_requires_release_suite_current(self):
        plan = TestMeshPlan(
            parent_suite_id="validation",
            decision_scope="release",
            partition_items=(TestPartitionItem("unit", owner_suite_id="unit"),),
            child_suites=(
                suite("unit"),
                suite("full-release", layer="release", release_required=True, result_status="not_run"),
            ),
            target_split_derivation=target("validation-model", ("unit", "full-release"), ("unit",)),
        )

        report = review_test_mesh(plan)

        self.assertFalse(report.ok)
        self.assertEqual("missing_release_evidence", report.decision)
        self.assertIn("release_suite_not_current", [finding.code for finding in report.findings])

    def test_missing_target_split_derivation_blocks_parent_green(self):
        plan = TestMeshPlan(
            parent_suite_id="router-runtime",
            partition_items=(TestPartitionItem("controller", owner_suite_id="controller"),),
            child_suites=(suite("controller"),),
        )

        report = review_test_mesh(plan)

        self.assertFalse(report.ok)
        self.assertEqual("target_split_derivation_required", report.decision)
        self.assertIn("missing_target_split_derivation", [finding.code for finding in report.findings])

    def test_incomplete_target_split_derivation_blocks_parent_green(self):
        plan = TestMeshPlan(
            parent_suite_id="router-runtime",
            partition_items=(
                TestPartitionItem("controller", owner_suite_id="controller"),
                TestPartitionItem("packets", owner_suite_id="packets"),
            ),
            child_suites=(suite("controller"), suite("packets")),
            target_split_derivation=TestTargetSplitDerivation(
                "router-runtime-validation",
                target_suite_ids=("controller", "unknown"),
                covered_partition_item_ids=("controller",),
                rationale="derived from a partial validation model",
            ),
        )

        report = review_test_mesh(plan)
        codes = [finding.code for finding in report.findings]

        self.assertFalse(report.ok)
        self.assertEqual("target_split_derivation_required", report.decision)
        self.assertIn("unknown_target_suite", codes)
        self.assertIn("incomplete_target_suites", codes)
        self.assertIn("incomplete_target_split_coverage", codes)


if __name__ == "__main__":
    unittest.main()
