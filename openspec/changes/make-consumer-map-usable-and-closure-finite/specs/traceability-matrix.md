# Consumer-map and finite-closure traceability

This matrix is the implementation map for this change. Each requirement has
one native owner; aggregate readers and the final parent consume that owner's
evidence but do not replace it.

| Requirement | Native owner | Implementation surface | Focused verification |
| --- | --- | --- | --- |
| First adoption yields a current-readable observed authority | `authoritative_model_system` | `flowguard.model_authority_store.bootstrap_initial_current_model_authority`, `flowguard.__main__` initial-current route | `tests/test_model_authority.py`, `tests/test_model_authority_store.py`, `tests/test_accepted_boundary_contract.py` |
| Initial intent gaps are typed to the affected model endpoint | `authoritative_model_system` + `model_test_alignment` | `flowguard.model_system_inventory.build_initial_intent_pending_snapshot`, `flowguard.model_revision_set.derive_revision_affected_closure` | `tests/test_model_revision_builder.py`, `tests/test_model_revision_owner_evidence.py` |
| Basic consumer navigation is local and read-only | `existing_model_preflight` | `flowguard.model_authority_store.read_selected_model_closure`, `flowguard.existing_model_preflight` | `tests/test_existing_model_preflight.py`, `tests/test_light_read_boundary.py`, `tests/test_affected_blueprint_reader.py` |
| Affected updates preserve unrelated model entries and typed connections | `model_mesh_maintenance` | `flowguard.model_revision_set`, `scripts/build_direct_model_rebuild_inputs.py` | `tests/test_direct_rebuild_candidate_coherence.py`, `tests/test_model_authority.py` |
| Pointer binding is separate from selected semantic content | `authoritative_model_system` + `validation_ownership` | semantic/authority projections in `flowguard.validation_ownership`, pointer-last activation in `flowguard.model_authority_store` | `tests/test_accepted_boundary_contract.py`, `tests/test_model_authority_store.py` |
| Local validation and release claims have separate freshness boundaries | `validation_ownership` + `release_verification` | `ValidationOwnerPlan.claim_scope`, `build_validation_parent_current`, release verifier binding | `tests/test_validation_execution_ownership.py`, `tests/test_release_verification.py` |
| One stable completion identity and at most one typed repair | `development_process_flow` | `flowguard.completion_epoch`, `flowguard.completion_readiness`, `scripts/check_flowguard_skill_suite.py` | `tests/test_completion_epoch.py`, `tests/test_completion_run_manifest.py`, `tests/test_completion_repair_admission.py` |
| Producers and Git observations are bounded and cleanup-confirmed | `development_process_flow` | `flowguard.process_supervision`, `flowguard.validation_ownership` | `tests/test_process_supervision.py`, `tests/test_validation_execution_ownership.py` |
| Patch scope and relation ownership are explicit | `model_test_alignment` | `scripts/check_closure_patch_regressions.py`, `scripts/build_direct_model_rebuild_inputs.py` | `tests/test_direct_rebuild_candidate_coherence.py`, patch-regression smoke in the final receipt |
| Agent Workflow Rehearsal is risk-admitted, not universal | `development_process_flow` | route text, simulator facts, prompt bundle | `tests/test_development_process_simulator.py`, `tests/test_flowguard_agent_workflow_rehearsal.py`, `tests/test_flowguard_skill_trigger.py` |
| Author projection and consumer distribution remain separate | `skillguard` (author maintenance) | direct-current contract/projection compilation and installed consumer checks | SkillGuard owner receipts and final author validation receipt |
| Target-neutral release convergence and arbitrary finite hierarchy | `release_verification` + `authoritative_model_system` | `ReleaseTarget`, candidate receipt binding, iterative recursive review | external Python/non-Python fixtures; depth 8/12/1500 structure and shared-connection tests |

The final completion receipt must name this matrix, the selected owner plan,
the exact work identity, and the local/release claim scope. Temporary output,
reports, checkboxes, and historical receipts remain evidence, not new semantic
inputs.
