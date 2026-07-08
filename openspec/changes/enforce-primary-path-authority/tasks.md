## 1. OpenSpec And Route Grounding

- [x] 1.1 Validate the OpenSpec change artifacts before implementation.
- [x] 1.2 Confirm current FlowGuard package/schema/project audit and record the route scope.
- [x] 1.3 Inspect existing primary-related models, runtime path evidence, topology hazards, legacy path disposition, RiskLedger, ContractExhaustionMesh, TestMesh, templates, and API registry patterns.

## 2. Core Primary Path Authority Route

- [x] 2.1 Add `flowguard/primary_path_authority.py` with contract, candidate, coverage, finding, report, and `review_primary_path_authority()` types.
- [x] 2.2 Implement hard blockers for missing primary owner, unknown disposition, primary failure masked by fallback success, facade business logic, auto-invoked manual recovery, and missing broad-claim coverage.
- [x] 2.3 Expose stable case ids, shard ids, coverage receipt ids, risk gate ids, and default finite axes/interaction groups.

## 3. Integration With Existing FlowGuard Routes

- [x] 3.1 Extend runtime path evidence to record primary path id, fallback path id, primary failure id, fallback invocation, and fallback success masking.
- [x] 3.2 Extend Risk Evidence Ledger with primary-path authority and primary-path Cartesian coverage gates.
- [x] 3.3 Add API registry and public export entries for the new route without exposing internal helpers as public route owners.
- [x] 3.4 Add CLI/template support for `primary-path-authority-template`.

## 4. FlowGuard Self Model And Tests

- [x] 4.1 Add `.flowguard/primary_path_authority/model.py` and `run_checks.py` that prove the new route rejects known bad workflows.
- [x] 4.2 Add primary-path authority unit tests for contract declaration, candidate disposition, and report formatting.
- [x] 4.3 Add core, compatibility, facade, field, runtime, contract-exhaustion, and release-gate matrix tests.
- [x] 4.4 Update existing runtime path, RiskLedger, API surface, template, and TestMesh tests for the new evidence/gate surfaces.

## 5. Docs, Agent Guidance, And Skills

- [x] 5.1 Update `AGENTS.md` and `docs/agents_snippet.md` with primary-path authority default behavior.
- [x] 5.2 Update relevant FlowGuard skill prompts to require path enumeration, one primary authority, no automatic fallback success, compatibility disposition, and Cartesian coverage gates.
- [x] 5.3 Add docs/skill tests that verify the guidance remains installed-facing and not only hidden in OpenSpec artifacts.

## 6. Validation, Install Sync, And Workspace Sync

- [x] 6.1 Run OpenSpec validation, FlowGuard self-model checks, focused tests, and project audit; fix failures.
- [x] 6.2 Run broader pytest regression or the strongest practical regression, preserving failures caused by unrelated peer work as scoped evidence if needed.
- [x] 6.3 Sync global installed skills from the repository skill sources and verify relevant installed skill content.
- [x] 6.4 Sync the shadow workspace changes to the local git checkout without reverting unrelated work, then verify local package import path, metadata version, and new public API.
- [x] 6.5 Run final OpenSpec validation and postflight evidence recording.
