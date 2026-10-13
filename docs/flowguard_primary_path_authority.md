# FlowGuard Primary Path Authority

Primary Path Authority enforces one rule for path-sensitive work: one business
intent has one primary runtime path. If the primary path fails, expose the
failure and repair that primary path instead of automatically running an
alternate implementation and returning success.

Use it when feature work, bug repair, compatibility cleanup, field migration,
helper-route cleanup, install sync, or release confidence could leave old
paths, aliases, wrappers, helper routes, compatibility facades, old fields,
backup caches, migration paths, or recovery tools as a hidden second success
path at runtime.

Broad claims require ContractExhaustionMesh Cartesian coverage, TestMesh shard
evidence, and risk gates (`risk_gate_ids` on the plan).

Uniqueness is keyed by the stable exact `business_intent_id`, not by the pair
of intent text and path name. Two different path ids for the same exact intent
are still two competing primary paths. PPA consumes the complete affected
surface/candidate inventory from Existing Model Preflight and the Behavior
Commitment Ledger (`preflight_id`, `behavior_commitment_ledger_id`), reuses an
equivalent current path when one exists (`existing_current_path_ids`), and,
when `require_material_runtime_evidence=True`, requires observed runtime
evidence (`runtime_observation_ids`, see
[`runtime_path_evidence.md`](runtime_path_evidence.md)) plus `proof_artifact`
coverage before a green decision. Additional public surfaces may delegate,
remain manual-only, migrate, be removed, or be scoped with evidence; they
cannot become a second independent success path.

## Public API

- `PrimaryPathContract`: the one primary path for one business intent.
- `FallbackPathCandidate`: a non-primary surface that might silently take over.
- `PrimaryPathAuthorityPlan`: the primary paths, candidates, and claim scope.
- `review_primary_path_authority(plan)`: returns a `PrimaryPathAuthorityReport`.
- `primary_path_authority_contract_exhaustion_plan(...)`: the Cartesian
  coverage plan for broad claims.

Starter model:

```powershell
python -m flowguard template primary-path-authority            # print
python -m flowguard template primary-path-authority --write .  # write files
```

The review is a model check. It does not prove the code: run the project's
tests and the executable models (`python -m flowguard map models`) as the proof.
