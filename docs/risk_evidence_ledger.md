# Risk Evidence Ledger

Risk Evidence Ledger is FlowGuard's final confidence boundary. It does not make
a model deeper and it does not discover missing scope. It verifies that each
important user-facing risk is connected to the current model obligation, the
owner code contract when public behavior matters, route-specific gates, and
current external proof.

In strict mode a declared `passed/current` flag is not sufficient. Each proof
row needs a `ProofArtifactRef` with a result path, artifact fingerprint,
passing exit status, current route identity, covered obligation ids, and the
right assertion scope.

## Current Chain

```text
user risk
-> behavior commitment + blueprint/model obligation
-> finite ContractExhaustion cases and coverage receipts when required
-> owner code contract + model-code-test binding
-> independently verified ModelMaturation evidence
-> topology/parent/UI/payload/structure gates that the risk actually needs
-> current external proof
-> full, scoped, or blocked claim
```

A risk-sensitive business path must bind its stable path identity and terminal
result. A generic green helper or anonymous progress log cannot prove a path-
sensitive claim.

For a post-green model miss, the Model-Miss owner supplies the affected
commitment, primary owner, blueprint gap, canonical relation ids, generated
ContractExhaustion cases, and task-bound maturation contribution. The ledger
consumes the resulting verified evidence; it does not run another discovery or
recurrence workflow.

## Public API

- `RiskEvidenceRow`: one user-meaningful risk, its model obligation, optional
  owner code contract, proof ids, and typed gates.
- `RiskEvidenceGate`: one route-specific evidence reference with `kind`,
  `evidence_id`, current status, confidence, and scoped reasons.
- `RiskEvidenceProof`: one test, replay, route report, or manual validation
  item. Strict full-confidence review requires its concrete proof artifact.
- `RiskEvidenceLedgerPlan`: rows, proof evidence, route-owned maintenance
  obligations, independently verified maturation evidence, and review policy.
- `RiskEvidenceLedgerReport`: final decision, confidence, findings, and claim
  boundary.
- `review_risk_evidence_ledger(plan)`: the executable review.
- `model_maturation_to_risk_evidence_gate(...)`: the only supported projection
  from `VerifiedModelMaturation` into a maturation gate.

Current generic gate kinds include:

- `model_maturation` and `topology_hazard`;
- `model_split`, `test_split`, `model_cartesian_coverage`,
  `contract_coverage_shard`, and `parent_consumed_child_coverage`;
- `behavior_commitment_coverage`,
  `behavior_commitment_cartesian_coverage`, `primary_path_authority`, and
  `primary_path_authority_cartesian_coverage`;
- `parent_model_evidence` and `maintenance_obligation`;
- UI implementation, real-surface, functional-chain, capability-coverage,
  done-claim, human-operability, and source-baseline-interaction gates;
- `artifact_payload`.

Unknown gate kinds fail visibly. Route-specific helpers produce these gate
identities; the ledger does not infer them from prose.

## ModelMaturation Evidence Boundary

`VerifiedModelMaturation` cannot be constructed directly. A producer first
publishes a canonical maturation receipt. An independent verifier checks the
receipt against the exact task, model, candidate fingerprint, coverage demand
and universe, inputs, evidence, owner-resolution identities, toolchain, and
environment. Only that verifier-created projection can appear in
`RiskEvidenceLedgerPlan.model_maturation_evidence`.

The ordinary wiring is:

```python
# `verification` comes from verify_model_maturation_receipt(...)
verified = verification.verified_maturation
assert verified is not None

gate = model_maturation_to_risk_evidence_gate(verified)
row = RiskEvidenceRow(
    "duplicate_submit",
    model_obligation_id="model:dedupe-submit",
    code_contract_id="api:submit-order",
    proof_evidence_ids=("test:submit-duplicate",),
    gates=(gate,),
)
plan = RiskEvidenceLedgerPlan(
    "submit-final-confidence",
    rows=(row,),
    proof_evidence=(external_submit_proof,),
    model_maturation_evidence=(verified,),
    require_proof_artifacts=True,
)
report = review_risk_evidence_ledger(plan)
```

The names `external_submit_proof` and `verification` above stand for evidence
already produced by their owning routes. A raw mapping, self-declared receipt,
or progress record is intentionally rejected.

## Decisions And Blocking Conditions

- `risk_evidence_full_confidence`: every required in-scope risk has its model
  obligation, required owner code contract, exact route gates, verified
  maturation when required, and current passing proof at the expected external
  boundary.
- `risk_evidence_scoped_confidence`: the accepted evidence supports only the
  explicitly recorded smaller boundary.
- Missing, unknown, stale, blocked, or scoped required gates prevent a full
  claim. The finding code names the gate, for example
  `missing_model_maturation_gate`, `model_maturation_gate_not_current`,
  `model_maturation_gate_blocked`, or
  `model_maturation_gate_scoped_confidence`.
- Missing proof, progress-only proof, internal-path-only proof, mismatched
  obligation coverage, non-passing status, or stale fingerprints also prevent
  full confidence.
- An open maintenance obligation blocks only through its exact owning risk
  row. A resolved obligation needs current owner-route evidence. This memory
  does not become a separate scanning authority.

## Route Responsibilities

- Existing Model Preflight and the Behavior Commitment Ledger identify current
  ownership and the exact promise being evaluated.
- ContractExhaustionMesh materializes declared finite relations and boundaries
  into stable cases, combinations, shards, receipts, and oracles.
- Model-Test Alignment binds model obligations to owner code contracts and
  ordinary external test evidence.
- TestMesh and ModelMesh own layered test evidence and parent/child model
  consumption.
- ModelMaturation owns iterative model-depth gaps and publishes task-bound
  evidence through the canonical receipt route.
- Model Topology Hazard Review, StructureMesh, UI Flow Structure, payload
  validation, and other specialists produce only the gates their risk requires.
- DevelopmentProcessFlow checks freshness and consumes the ledger before done,
  archive, publish, or release claims.
- Risk Evidence Ledger verifies the assembled chain; it neither replaces these
  producers nor promotes a narrower result.

## Old And Alternate Paths

When a repair leaves an old, fallback, alternate, replaced, or deprecated path
reachable, its disposition must be deleted, blocked, migrated, delegated to the
repaired owner, same-contract repaired, or explicitly scoped with a reason.
`unknown` blocks closure. A delegated or same-contract-repaired path needs
current proof of the repaired external contract before full confidence can be
restored.
