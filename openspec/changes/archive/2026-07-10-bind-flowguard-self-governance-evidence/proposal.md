## Why

FlowGuard's self-maintenance model can currently construct `current=True` and `closure_status=pass` child reports in memory, allowing a parent green result without proving that required child checks actually ran against the current repository. Full self-governance must be derived from immutable, freshness-checked receipts and exact parent consumption, never from caller-supplied pass booleans.

## What Changes

- Add a canonical evidence-receipt schema binding subject, claim scope, producer version, command, environment, input snapshots, contract/check hashes, result fingerprint, covered obligations, child receipts, skipped checks, blockers, and claim boundary.
- Derive `current` and eligible status from receipt contents at read time; input, contract, checker, environment, or required-child changes invalidate affected evidence.
- Rebuild the self-maintenance parent as a ModelMesh that consumes exact current child receipts for suite inventory, SkillGuard contracts, behavior commitments, route topology, model/test alignment, TestMesh, installation/version state, and documentation/distribution gates.
- Remove synthetic transitions and runners that set all evidence flags or manufacture passing child reports.
- Tighten formal summary semantics so `pass_with_gaps`, `scoped`, `stale`, `skipped`, `not_run`, and `progress_only` cannot satisfy a broad full-self-governance claim.
- Backfill the Behavior Commitment Ledger across the complete public suite and bind each commitment to one primary owner model, source surfaces, ContractExhaustionMesh cases, TestMesh shards, and current receipts.
- Add known-bad oracles for stale/mismatched/unconsumed child receipts, forged current flags, omitted children, and scoped results promoted to full.
- **BREAKING**: callers can no longer assert authoritative `current` or `pass`; existing unbound self-maintenance result files are not valid full-governance evidence.

## Capabilities

### New Capabilities

- `flowguard-evidence-receipts`: Defines immutable proof receipts, freshness derivation, exact parent-child consumption, invalidation, and claim-scope eligibility.

### Modified Capabilities

- `flowguard-self-maintenance-mesh`: Requires full self-maintenance closure to consume current child evidence instead of synthetic status fields.
- `proof-artifact-bound-evidence`: Extends proof binding to contract/checker/environment fingerprints and covered obligation identifiers.
- `model-test-alignment`: Requires suite-level commitment-to-owner-to-test mappings and current TestMesh receipts for broad governance claims.

## Impact

Affected surfaces include self-maintenance models/runners, `flowguard/self_maintenance.py`, formal summary handling, evidence schemas and storage, Behavior Commitment Ledger models, ModelMesh reattachment, Model-Test Alignment, TestMesh, ContractExhaustionMesh fixtures, tests, and adoption records. This change depends on completed suite membership, topology ownership, and skill contracts; it does not own the model regression scheduler, installation commands, three-way distribution sync, documentation copy, or GitHub release.
