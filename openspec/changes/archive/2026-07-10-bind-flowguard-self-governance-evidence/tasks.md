## 1. Confirm Governed Inputs

- [x] 1.1 Verify suite inventory, route topology, and 17/17 deep skill contract changes pass and record their current hashes.
- [x] 1.2 Inventory all existing self-maintenance status fields, child report constructors, result files, formal summary promotions, BCL commitments, MTA rows, TestMesh shards, and evidence consumers.

## 2. Implement Evidence Receipts

- [x] 2.1 Add `flowguard/evidence_receipts.py` with canonical receipt schema, validation, tokenized paths, allowlisted environment fingerprint, covered obligations, child links, and deterministic serialization/fingerprint.
- [x] 2.2 Implement raw/semantic input snapshots and obligation-specific hash policy; do not allow semantic equality to mask raw-required distribution mismatch.
- [x] 2.3 Implement derived freshness for input, contract, checker, suite, producer, environment, proof artifact, and required-child changes; reject or ignore caller-supplied authoritative `current`.
- [x] 2.4 Implement exact required/consumed child receipt checks, supersession, minimum revalidation, and configured `.flowguard/evidence/skill-suite` storage without raw private paths.
- [x] 2.5 Add diagnostic-only import for legacy reports classified as unbound historical evidence, never current full evidence.

## 3. Build Suite Behavior And Test Alignment

- [x] 3.1 Run Behavior Commitment Ledger `coverage_gap_backfill` over README/docs, CLI, prompts, registry, contracts, models, project adoption, installer, distribution, and release surfaces.
- [x] 3.2 Give every external commitment bidirectional source mappings, exactly one primary owner model, dependencies, path-sensitive flag, CEM cases, TestMesh shard, and receipt obligation.
- [x] 3.3 Extend Model-Test Alignment to map commitment → owner code/prompt contract → scenarios → TestMesh receipt and fail green endpoints with a missing owner contract.
- [x] 3.4 Require current internal PPA receipts for every path-sensitive commitment, including one authority, visible failure, no alternate success, CEM, TestMesh, and Risk Ledger evidence.

## 4. Rebuild Self Maintenance As A Real Parent

- [x] 4.1 Refactor `SelfMaintenanceChildReport` to require receipt identity, fingerprint, claim scope, covered obligations, and verifier-derived freshness.
- [x] 4.2 Remove transitions that set multiple evidence domains/current/pass together; derive any view booleans only from verified child receipts.
- [x] 4.3 Replace in-memory passing child construction in `.flowguard/self_maintenance_mesh/run_checks.py` with loading and validating exact current receipts.
- [x] 4.4 Declare required child subjects for suite inventory, SkillGuard, BCL, topology, MTA, TestMesh, model regression, install/version, and docs/distribution; require exact parent consumption.
- [x] 4.5 Preserve the public self-maintenance facade while delegating receipt and parent logic to focused modules; retain no synthetic full-pass fallback.

## 5. Tighten Status And Formal Semantics

- [x] 5.1 Change formal expected-success handling so default success means exact `pass`; allow `pass_with_gaps` only when the case explicitly declares a scoped allowed status.
- [x] 5.2 Report `engine_and_core_tests`, `skill_contract_governance`, and `full_self_governance` separately with evidence, blockers, skipped checks, residual risk, and claim boundary.
- [x] 5.3 Ensure `pass_with_gaps`, scoped, stale, skipped, not-run, progress-only, blocked, and missing child remain visible and cannot satisfy full/release/archive/publication closure.

## 6. Add Known-Bad And Regression Evidence

- [x] 6.1 Add `tests/test_evidence_receipts.py` for missing fields, deterministic serialization, path privacy, wrong hashes, changed environment/checker/contract, forged current, stale/superseded/unconsumed child, and raw/semantic policies.
- [x] 6.2 Add `tests/test_proof_artifact_binding.py` for missing obligation coverage and unbound green command results.
- [x] 6.3 Add `tests/test_skill_self_governance.py` for missing child, omitted inventory member, manufactured pass report, all-flags transition, partial-to-full promotion, and the three-layer status matrix.
- [x] 6.4 Update formal, BCL, MTA, TestMesh, PPA, self-review, and conformance tests without weakening existing hard invariants.

## 7. Close And Handoff

- [x] 7.1 Implement `scripts/run_flowguard_self_governance.py` and run it in full JSON mode after all required child receipts are current.
- [x] 7.2 Run every command in `verification-contract.yaml`, the self-maintenance model, known-bad universe, and strict OpenSpec validation; require all expected failures to be observed.
- [x] 7.3 Confirm current self-governance cannot pass if any required member/contract/topology/alignment/TestMesh receipt is stale, partial, missing, or unconsumed.
- [x] 7.4 Hand receipt schemas and self-governance command semantics to `productize-flowguard-validation-and-distribution`; leave scheduling, installation, full-tree parity, docs, version, and publication to that change.
