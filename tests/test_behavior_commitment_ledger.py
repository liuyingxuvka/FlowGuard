import unittest

from flowguard import (
    BCL_COMMITMENT_WORKFLOW,
    BCL_EVIDENCE_CURRENT_PASS,
    BCL_MISS_ORIGIN_OBSERVED,
    BCL_MODEL_SYNC_OWNER_STALE,
    BCL_REPLACEMENT_REPLACED,
    BCL_SCOPE_FULL,
    BCL_SOURCE_DOC,
    BCL_SOURCE_FRESHNESS_CHANGED,
    BCL_TEST_MESH_SHARD_MISSING,
    BehaviorCommitment,
    BehaviorCommitmentLedger,
    BehaviorEvidenceBinding,
    BehaviorSourceSurface,
    review_behavior_commitment_ledger,
)


def evidence(**kwargs):
    defaults = {
        "model_obligation_ids": ("obligation:workflow",),
        "code_contract_ids": ("contract:workflow",),
        "test_evidence_ids": ("test:workflow",),
        "risk_gate_ids": ("risk_gate:behavior_commitment_coverage:ledger",),
        "coverage_case_ids": ("bcl.full_inventory_mapping.workflow.doc.mapped",),
        "coverage_shard_ids": ("contract_shard:behavior_commitment_ledger:full_inventory_mapping",),
        "coverage_receipt_ids": ("contract_coverage:behavior_commitment_ledger",),
        "evidence_state": BCL_EVIDENCE_CURRENT_PASS,
        "current": True,
    }
    defaults.update(kwargs)
    return BehaviorEvidenceBinding(**defaults)


def surface(**kwargs):
    defaults = {
        "surface_id": "surface:docs-workflow",
        "surface_kind": BCL_SOURCE_DOC,
        "label": "docs workflow surface",
        "source_ref": "README.md#usage",
        "commitment_ids": ("commitment:workflow",),
        "owner": "docs-owner",
        "validation_boundary": "docs and tests",
        "rationale": "public docs expose the behavior",
    }
    defaults.update(kwargs)
    return BehaviorSourceSurface(**defaults)


def commitment(**kwargs):
    defaults = {
        "commitment_id": "commitment:workflow",
        "label": "run workflow",
        "commitment_kind": BCL_COMMITMENT_WORKFLOW,
        "actor": "user",
        "trigger": "runs the documented command",
        "expected_result": "documented success or visible repairable error",
        "failure_boundary": "fail closed with repair information",
        "source_surface_ids": ("surface:docs-workflow",),
        "primary_owner_model_id": "model:workflow",
        "validation_boundary": "model, contract, and smoke test",
        "rationale": "external behavior promise",
        "evidence": evidence(),
    }
    defaults.update(kwargs)
    return BehaviorCommitment(**defaults)


def ledger(*, commitments=None, surfaces=None, expected=None, **kwargs):
    defaults = {
        "ledger_id": "ledger",
        "project_boundary": "example project",
        "current_revision": "rev-1",
        "claim_scope": BCL_SCOPE_FULL,
        "owner": "maintainer",
        "validation_boundary": "full behavior claim",
        "rationale": "register all external behavior promises",
        "expected_commitment_ids": expected or ("commitment:workflow",),
        "source_surfaces": tuple(surfaces if surfaces is not None else (surface(),)),
        "commitments": tuple(commitments if commitments is not None else (commitment(),)),
    }
    defaults.update(kwargs)
    return BehaviorCommitmentLedger(**defaults)


def codes(report):
    return {finding.code for finding in report.findings}


class BehaviorCommitmentLedgerTests(unittest.TestCase):
    def test_complete_ledger_passes_and_exposes_downstream_ids(self):
        report = review_behavior_commitment_ledger(ledger())

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual("behavior_commitment_coverage_green", report.decision)
        self.assertIn("commitment:workflow", report.covered_commitment_ids)
        self.assertIn("risk_gate:behavior_commitment_coverage:ledger", report.required_risk_gate_ids)
        self.assertIn("contract_coverage:behavior_commitment_ledger", report.coverage_receipt_ids)

    def test_missing_expected_commitment_blocks(self):
        report = review_behavior_commitment_ledger(ledger(expected=("commitment:missing",)))

        self.assertFalse(report.ok)
        self.assertIn("expected_commitment_missing", codes(report))

    def test_source_surface_without_commitment_blocks(self):
        report = review_behavior_commitment_ledger(
            ledger(surfaces=(surface(commitment_ids=()),))
        )

        self.assertFalse(report.ok)
        self.assertIn("source_surface_missing_commitment", codes(report))
        self.assertIn("surface:docs-workflow", report.unmapped_surface_ids)

    def test_commitment_without_source_ref_blocks_as_extra_behavior(self):
        report = review_behavior_commitment_ledger(
            ledger(commitments=(commitment(source_surface_ids=(), source_refs=()),))
        )

        self.assertFalse(report.ok)
        self.assertIn("commitment_missing_source_ref", codes(report))
        self.assertIn("commitment:workflow", report.extra_commitment_ids)

    def test_primary_owner_overlap_blocks(self):
        report = review_behavior_commitment_ledger(
            ledger(commitments=(commitment(supporting_model_ids=("model:workflow",)),))
        )

        self.assertFalse(report.ok)
        self.assertIn("primary_owner_also_supporting", codes(report))

    def test_unknown_dependency_blocks(self):
        report = review_behavior_commitment_ledger(
            ledger(commitments=(commitment(dependency_commitment_ids=("commitment:missing",)),))
        )

        self.assertFalse(report.ok)
        self.assertIn("commitment_dependency_unknown", codes(report))

    def test_scoped_out_commitment_requires_disposition(self):
        report = review_behavior_commitment_ledger(
            ledger(
                commitments=(
                    commitment(
                        in_scope=False,
                        scoped_out_reason="",
                        owner="",
                        validation_boundary="",
                        rationale="",
                    ),
                )
            )
        )

        self.assertFalse(report.ok)
        self.assertIn("scoped_out_behavior_missing_disposition", codes(report))

    def test_changed_source_surface_blocks_broad_claim_until_ledger_is_refreshed(self):
        report = review_behavior_commitment_ledger(
            ledger(surfaces=(surface(freshness_state=BCL_SOURCE_FRESHNESS_CHANGED),))
        )

        self.assertFalse(report.ok)
        self.assertIn("source_surface_freshness_not_current", codes(report))

    def test_replaced_behavior_requires_replacement_disposition(self):
        report = review_behavior_commitment_ledger(
            ledger(commitments=(commitment(replacement_state=BCL_REPLACEMENT_REPLACED),))
        )

        self.assertFalse(report.ok)
        self.assertIn("commitment_replacement_disposition_missing", codes(report))
        self.assertIn("commitment_lifecycle_disposition_missing", codes(report))

    def test_stale_owner_model_blocks_broad_claim(self):
        report = review_behavior_commitment_ledger(
            ledger(commitments=(commitment(model_sync_state=BCL_MODEL_SYNC_OWNER_STALE),))
        )

        self.assertFalse(report.ok)
        self.assertIn("commitment_model_sync_not_current", codes(report))

    def test_missing_test_mesh_shard_blocks_broad_claim(self):
        report = review_behavior_commitment_ledger(
            ledger(commitments=(commitment(evidence=evidence(test_mesh_state=BCL_TEST_MESH_SHARD_MISSING)),))
        )

        self.assertFalse(report.ok)
        self.assertIn("commitment_test_mesh_not_current", codes(report))

    def test_model_miss_backfeed_requires_existing_commitment_model_and_dcar_case(self):
        report = review_behavior_commitment_ledger(
            ledger(
                commitments=(
                    commitment(
                        miss_origin_state=BCL_MISS_ORIGIN_OBSERVED,
                        model_sync_state=BCL_MODEL_SYNC_OWNER_STALE,
                        evidence=evidence(coverage_case_ids=()),
                    ),
                )
            )
        )

        self.assertFalse(report.ok)
        self.assertIn("commitment_model_miss_backfeed_incomplete", codes(report))

    def test_model_miss_on_existing_commitment_must_not_create_duplicate_commitment(self):
        report = review_behavior_commitment_ledger(
            ledger(
                commitments=(
                    commitment(miss_origin_state=BCL_MISS_ORIGIN_OBSERVED),
                    commitment(
                        label="duplicate point-fix commitment",
                        miss_origin_state=BCL_MISS_ORIGIN_OBSERVED,
                    ),
                )
            )
        )

        self.assertFalse(report.ok)
        self.assertIn("duplicate_commitment_id", codes(report))


if __name__ == "__main__":
    unittest.main()
