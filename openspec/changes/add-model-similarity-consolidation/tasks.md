## 1. Core Model Similarity API

- [x] 1.1 Add `flowguard/model_similarity.py` with signature, relation, plan, finding, report, and review helper objects.
- [x] 1.2 Implement deterministic relation classification for same workflow, family variant, symmetric/shared-kernel, duplicate/overlap, adapter-only, evidence duplicate, false friend, unrelated, and manual-review cases.
- [x] 1.3 Implement confidence, recommendation, downstream-route, required-evidence, and evidence-gap decisions without treating similarity as implementation proof.
- [x] 1.4 Export the new API through `flowguard/__init__.py` and `docs/api_surface.md`.

## 2. Route Integrations

- [x] 2.1 Extend Existing Model Preflight to consume optional model-similarity evidence and block only when required similarity evidence is missing or unresolved.
- [x] 2.2 Extend Architecture Reduction candidates with optional similarity relation provenance and keep observable contract proof as the readiness authority.
- [x] 2.3 Extend Code Structure Recommendation with optional similarity relation provenance for shared-kernel and family-variant target structures.
- [x] 2.4 Extend Model-Test Alignment with optional similarity relation provenance for same-family and evidence-duplicate family evidence checks.

## 3. Templates, CLI, And Docs

- [x] 3.1 Add a model-similarity-consolidation template with runnable example review code and notes.
- [x] 3.2 Register `python -m flowguard model-similarity-template` for stdout and file output.
- [x] 3.3 Add `docs/model_similarity_consolidation.md` with usage, relation types, route handoffs, and limitations.
- [x] 3.4 Update README, CHANGELOG, and public API docs with the new capability.

## 4. FlowGuard Self-Model And Adoption Evidence

- [x] 4.1 Add `.flowguard/model_similarity_consolidation/model.py` and `run_checks.py` covering required relation and evidence-gate hazards.
- [x] 4.2 Run the executable self-model and record current evidence in adoption logs.

## 5. Tests And Validation

- [x] 5.1 Add focused unit tests for model-similarity relation classification, evidence gates, route handoffs, and false friends.
- [x] 5.2 Add focused tests for Existing Model Preflight, Architecture Reduction, Code Structure Recommendation, and Model-Test Alignment integration.
- [x] 5.3 Add CLI/template/API-surface tests for the new public surface.
- [x] 5.4 Run OpenSpec validation, focused pytest, FlowGuard model checks, full regression, project audit, and import/version checks.

## 6. Sync And Finalization

- [x] 6.1 Refresh the editable install from the git checkout and verify `flowguard.__file__`, version, schema, and new API availability.
- [x] 6.2 Sync the updated git checkout back to `C:\Users\liu_y\Documents\FlowGuard_20260427` without overwriting unrelated work.
- [x] 6.3 Verify the shadow workspace imports and focused tests against the synced code.
- [x] 6.4 Update OpenSpec task status, adoption evidence, and KB postflight before final response.
