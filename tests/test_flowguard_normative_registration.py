"""Normative registration is distinct from observed broad behavior evidence."""

from dataclasses import replace
from pathlib import Path

from flowguard.behavior_commitment import (
    load_behavior_commitment_ledger,
    review_behavior_commitment_ledger,
)


ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / ".flowguard" / "behavior" / "inventory" / "ledger.json"
NEW_PRIMARY_MODELS = {
    "python-function-state-verification-current": "python_function_state_verification",
    "problem-corpus-coverage-current": "problem_corpus_coverage",
    "evidence-storage-lifecycle-current": "evidence_storage_lifecycle",
    "producer-execution-current": "development_process_flow",
    "primary-path-authority-current": "primary_path_authority",
    "model-code-test-alignment-current": "model_test_code_alignment",
    "provider-neutral-blueprint-current": "implementation_blueprint",
    "native-hierarchical-composition-current": "hierarchical_model_mesh",
    "project-adoption-current": "project_adoption_version_gate",
    "runtime-writer-gateway-current": "runtime_gateway_adoption",
    "unknown-state-closure-current": "state_closure_gate",
    "plan-detailing-current": "plan_detailing_compiler",
    "runtime-path-evidence-current": "runtime_path_evidence",
    "architecture-reduction-current": "architecture_reduction",
    "code-structure-partition-current": "structure_refactor_mesh",
    "model-impact-freshness-current": "model_impact_freshness_gate",
    "existing-model-preflight-current": "existing_model_preflight",
    "topology-hazard-current": "model_topology_hazard_review",
    "contract-exhaustion-current": "contract_source_audit",
    "risk-minimum-model-entry-current": "minimum_valuable_model_entry",
    "flowguard-example-demonstration-current": "template_public_release",
}
NEW_IDS = {"commitment:" + slug for slug in NEW_PRIMARY_MODELS}


def test_source_ledger_registers_promises_without_fabricating_execution():
    ledger = load_behavior_commitment_ledger(LEDGER)
    assert ledger.claim_scope == "registration"
    assert ledger.require_current_evidence is False
    assert not ledger.broad_claim()
    assert len(ledger.commitments) == 25 + len(NEW_IDS)
    assert len(ledger.source_surfaces) == 33 + len(NEW_IDS)
    by_id = {row.commitment_id: row for row in ledger.commitments}
    assert NEW_IDS <= set(by_id)
    assert len(by_id) == 25 + len(NEW_IDS)
    for slug, model_id in NEW_PRIMARY_MODELS.items():
        row = by_id["commitment:" + slug]
        assert row.business_intent_id == "intent:" + slug
        assert row.primary_owner_model_id == f".flowguard/models/owners/{model_id}/model.py"
        assert row.evidence.model_obligation_ids == ("obligation:" + slug,)
        assert row.evidence.evidence_state == "missing"
        assert row.evidence.current is False
        assert row.evidence.test_mesh_state == "shard_missing"
        assert row.model_sync_state == "owner_model_stale"
        assert not row.evidence.has_current_pass()
        assert not row.evidence.proof_artifact_ids
        assert not row.evidence.coverage_receipt_ids
        assert row.evidence.metadata["execution_status"] == "NOT_RUN"
    report = review_behavior_commitment_ledger(ledger, project_root=ROOT)
    assert report.ok, report.format_text()
    assert not any(f.code == "commitment_current_evidence_missing" for f in report.findings)


def test_same_source_full_projection_rejects_all_pending_responsibilities():
    registration = load_behavior_commitment_ledger(LEDGER)
    full = replace(registration, claim_scope="full", require_current_evidence=True)
    assert full.commitments == registration.commitments
    assert full.source_surfaces == registration.source_surfaces
    assert full.broad_claim()
    report = review_behavior_commitment_ledger(full, project_root=ROOT)
    assert not report.ok
    assert report.confidence == "blocked"
    for code in (
        "commitment_current_evidence_missing",
        "commitment_model_sync_not_current",
        "commitment_test_mesh_not_current",
    ):
        pending_ids = {finding.commitment_id for finding in report.findings if finding.code == code}
        assert pending_ids == NEW_IDS, (code, pending_ids ^ NEW_IDS)
    unchanged = load_behavior_commitment_ledger(LEDGER)
    assert unchanged == registration
    assert not any(row.evidence.has_current_pass() for row in unchanged.commitments if row.commitment_id in NEW_IDS)
