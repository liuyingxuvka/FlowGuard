import unittest

import flowguard
from flowguard import (
    ADOPTION_LEVEL_DESIGN_MODEL,
    ADOPTION_LEVEL_RUNTIME_GATEWAY,
    RUNTIME_WRITE_DIRECT,
    RUNTIME_WRITE_GATEWAY,
    RuntimeGatewayAdoptionPlan,
    RuntimeGatewayContract,
    RuntimeStateSurface,
    RuntimeWriterInventoryEvidence,
    RuntimeWriteObservation,
    review_runtime_gateway_adoption,
)


def surface(**overrides):
    values = {
        "surface_id": "router_state",
        "paths": ("runtime/router_state.json",),
        "critical": True,
        "owner_gateway_ids": ("control_plane_gateway",),
    }
    values.update(overrides)
    return RuntimeStateSurface(**values)


def gateway(**overrides):
    values = {
        "gateway_id": "control_plane_gateway",
        "managed_surface_ids": ("router_state",),
        "step_contract_ids": ("consume_controller_receipt",),
        "code_boundary_ids": ("control_plane_gateway.boundary",),
        "runtime_node_ids": ("runtime:control_plane_gateway",),
    }
    values.update(overrides)
    return RuntimeGatewayContract(**values)


def observation(observation_id="router_state_write", **overrides):
    values = {
        "observation_id": observation_id,
        "surface_id": "router_state",
        "write_kind": RUNTIME_WRITE_GATEWAY,
        "gateway_id": "control_plane_gateway",
        "step_contract_ids": ("consume_controller_receipt",),
        "code_boundary_ids": ("control_plane_gateway.boundary",),
        "runtime_node_ids": ("runtime:control_plane_gateway",),
        "proof_artifact_ids": ("artifact:router-state-write",),
    }
    values.update(overrides)
    return RuntimeWriteObservation(**values)


def writer_inventory(evidence_id="inventory:critical-state-writers", **overrides):
    values = {
        "evidence_id": evidence_id,
        "covered_surface_ids": ("router_state",),
        "discovered_writer_ids": ("writer:router_state_write",),
        "proof_artifact_ids": ("artifact:writer-inventory",),
        "current": True,
        "result_status": "passed",
    }
    values.update(overrides)
    return RuntimeWriterInventoryEvidence(**values)


def runtime_plan(**overrides):
    values = {
        "project_id": "flowpilot",
        "target_level": ADOPTION_LEVEL_RUNTIME_GATEWAY,
        "state_surfaces": (surface(),),
        "gateways": (gateway(),),
        "write_observations": (observation(),),
        "complete_inventory_evidence_ids": ("inventory:critical-state-writers",),
        "writer_inventory_evidence": (writer_inventory(),),
    }
    values.update(overrides)
    return RuntimeGatewayAdoptionPlan(**values)


def finding_codes(report):
    return [finding.code for finding in report.findings]


class RuntimeGatewayAdoptionTests(unittest.TestCase):
    def test_design_model_does_not_require_runtime_gateway(self):
        report = review_runtime_gateway_adoption(
            RuntimeGatewayAdoptionPlan("sketch", target_level=ADOPTION_LEVEL_DESIGN_MODEL)
        )

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual(ADOPTION_LEVEL_DESIGN_MODEL, report.decision)

    def test_complete_runtime_gateway_adoption_passes(self):
        report = review_runtime_gateway_adoption(runtime_plan())

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual("runtime_gateway_adoption_green", report.decision)
        self.assertEqual((), report.findings)

    def test_missing_inventory_blocks_runtime_gateway_claim(self):
        report = review_runtime_gateway_adoption(
            runtime_plan(
                complete_inventory_evidence_ids=(),
                writer_inventory_evidence=(),
            )
        )

        self.assertFalse(report.ok)
        self.assertIn("missing_complete_writer_inventory", finding_codes(report))
        self.assertIn("missing_structured_writer_inventory_evidence", finding_codes(report))

    def test_opaque_inventory_id_without_structured_evidence_blocks_runtime_gateway_claim(self):
        report = review_runtime_gateway_adoption(
            runtime_plan(writer_inventory_evidence=())
        )

        self.assertFalse(report.ok)
        self.assertIn("missing_structured_writer_inventory_evidence", finding_codes(report))

    def test_stale_and_non_passing_writer_inventory_blocks(self):
        report = review_runtime_gateway_adoption(
            runtime_plan(
                writer_inventory_evidence=(
                    writer_inventory(current=False, result_status="skipped"),
                )
            )
        )

        codes = finding_codes(report)
        self.assertFalse(report.ok)
        self.assertIn("writer_inventory_stale", codes)
        self.assertIn("writer_inventory_not_passing", codes)
        self.assertIn("writer_inventory_missing_critical_surface", codes)

    def test_writer_inventory_must_cover_critical_surface(self):
        report = review_runtime_gateway_adoption(
            runtime_plan(
                writer_inventory_evidence=(
                    writer_inventory(covered_surface_ids=("other_surface",)),
                )
            )
        )

        self.assertFalse(report.ok)
        self.assertIn("writer_inventory_missing_critical_surface", finding_codes(report))

    def test_writer_inventory_scoped_writer_requires_reason(self):
        report = review_runtime_gateway_adoption(
            runtime_plan(
                writer_inventory_evidence=(
                    writer_inventory(
                        scoped_out_writer_ids=("writer:legacy_router_state_write",),
                    ),
                )
            )
        )

        self.assertFalse(report.ok)
        self.assertIn("writer_inventory_scoped_without_reason", finding_codes(report))

    def test_writer_inventory_requires_proof_artifact(self):
        report = review_runtime_gateway_adoption(
            runtime_plan(
                writer_inventory_evidence=(writer_inventory(proof_artifact_ids=()),)
            )
        )

        self.assertFalse(report.ok)
        self.assertIn("writer_inventory_missing_proof_artifact", finding_codes(report))

    def test_unmanaged_critical_surface_blocks(self):
        report = review_runtime_gateway_adoption(
            runtime_plan(
                state_surfaces=(surface(owner_gateway_ids=()),),
                gateways=(),
                write_observations=(),
            )
        )

        codes = finding_codes(report)
        self.assertFalse(report.ok)
        self.assertIn("critical_surface_missing_gateway_owner", codes)
        self.assertIn("critical_surface_missing_writer_observation", codes)

    def test_direct_critical_write_blocks_runtime_gateway_claim(self):
        report = review_runtime_gateway_adoption(
            runtime_plan(
                write_observations=(
                    observation(
                        write_kind=RUNTIME_WRITE_DIRECT,
                        gateway_id="",
                        step_contract_ids=(),
                        code_boundary_ids=(),
                        proof_artifact_ids=(),
                    ),
                )
            )
        )

        self.assertFalse(report.ok)
        self.assertIn("direct_state_write_bypasses_gateway", finding_codes(report))

    def test_gateway_surface_mismatch_blocks(self):
        report = review_runtime_gateway_adoption(
            runtime_plan(gateways=(gateway(managed_surface_ids=("scheduler_ledger",)),))
        )

        self.assertFalse(report.ok)
        self.assertIn("gateway_surface_mismatch", finding_codes(report))

    def test_missing_gateway_evidence_ids_block(self):
        report = review_runtime_gateway_adoption(
            runtime_plan(
                write_observations=(
                    observation(
                        step_contract_ids=(),
                        code_boundary_ids=(),
                        runtime_node_ids=(),
                        proof_artifact_ids=(),
                    ),
                )
            )
        )

        codes = finding_codes(report)
        self.assertFalse(report.ok)
        self.assertIn("missing_step_contract_evidence", codes)
        self.assertIn("missing_code_boundary_evidence", codes)
        self.assertIn("missing_runtime_path_evidence", codes)
        self.assertIn("missing_proof_artifact_evidence", codes)

    def test_gateway_runtime_node_mismatch_blocks(self):
        report = review_runtime_gateway_adoption(
            runtime_plan(write_observations=(observation(runtime_node_ids=("wrong-node",)),))
        )

        self.assertFalse(report.ok)
        self.assertIn("runtime_path_gateway_node_mismatch", finding_codes(report))

    def test_stale_and_non_passing_writer_observations_block(self):
        report = review_runtime_gateway_adoption(
            runtime_plan(
                write_observations=(
                    observation(current=False, result_status="skipped"),
                )
            )
        )

        codes = finding_codes(report)
        self.assertFalse(report.ok)
        self.assertIn("writer_observation_stale", codes)
        self.assertIn("writer_observation_not_passing", codes)

    def test_declared_legacy_bypass_stays_blocking(self):
        report = review_runtime_gateway_adoption(
            runtime_plan(
                write_observations=(
                    observation(legacy_bypass_reason="temporary migration path"),
                )
            )
        )

        self.assertFalse(report.ok)
        self.assertIn("declared_legacy_gateway_bypass", finding_codes(report))

    def test_public_api_exports_runtime_gateway_adoption(self):
        expected = (
            "RuntimeGatewayAdoptionPlan",
            "RuntimeGatewayAdoptionReport",
            "RuntimeGatewayContract",
            "RuntimeGatewayFinding",
            "RuntimeStateSurface",
            "RuntimeWriterInventoryEvidence",
            "RuntimeWriteObservation",
            "review_runtime_gateway_adoption",
        )
        for name in expected:
            self.assertIn(name, flowguard.MODELING_HELPER_API)
            self.assertIn(name, flowguard.__all__)
            self.assertTrue(hasattr(flowguard, name), name)
            self.assertNotIn(name, flowguard.CORE_API)


if __name__ == "__main__":
    unittest.main()
