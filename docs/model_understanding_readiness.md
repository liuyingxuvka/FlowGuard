# Model Understanding Readiness

FlowGuard does not ask an AI to say, “I understand this software.” It asks the
AI to publish a checkable chain showing what it examined, what remains open,
and whether implementation is currently admissible.

## The Chain

```text
task facts
-> TaskCoverageDemand
-> owner evidence or visible dispositions
-> Model Maturation
-> canonical receipt
-> independent receipt verification
-> separate implementation admission
-> RiskLedger confidence
-> thin ClosureContract integrity check
```

This is one adaptive path. `ordinary`, `standard`, `deep`, and `release` are
derived presentation tiers, not modes the caller selects to avoid work. Every
triggered owner remains required in every tier.

## What Each Part Means

1. **Task facts** describe the actual change: read-only or implementation,
   affected surfaces, UI/field/API/release concerns, existing models, and
   affected model relationships.
2. **TaskCoverageDemand** deterministically derives which FlowGuard owners must
   contribute. The caller may add obligations but cannot subtract built-in
   triggered obligations.
3. **Owner dispositions** say `satisfied`, `not_triggered`, `unresolved`, or
   `blocked`, with current evidence or blocker identity. “Not run” is not a
   pass.
4. **Model Maturation** checks whether the exact candidate model closes the
   demanded behavior/state/transition/boundary/evidence gaps for this task.
5. **Receipt verification** independently reloads the canonical receipt and
   verifies task, candidate, coverage universe, input, evidence, and terminal
   identities. A hand-written mapping claiming `current=true` is rejected.
6. **Implementation admission** is separate from understanding sufficiency.
   Read-only work needs no code admission; normal code requires closed current
   maturation. Explicit user permission can bound an attempt with visible open
   gaps, but cannot turn those gaps into proof or waive toolchain, destructive,
   or active-owner blockers.
7. **RiskLedger** owns full/scoped/blocked broad confidence. ClosureContract
   checks exact identity continuity, required terminal material, and agreement
   with that decision; it does not calculate risk again.

## Roles And Permissions

FlowGuard does not invent the target software's users. A plan administrator,
end user, operator, service account, or external system belongs in the target
software's own behavior model when relevant. FlowGuard's records name only its
development-process actors and evidence owners. Likewise, the Behavior
Commitment Ledger records externally visible promises and their primary owner;
it is not a database of the target application's user accounts or permissions.

## ModelMesh Is Topology-Triggered

ModelMesh runs when affected models are related, a parent/child boundary
changes, child evidence is stale, a model needs partitioning, a cross-model
refinement is claimed, or whole-flow confidence is requested. A repository
having three or more unrelated models is only a discovery clue and does not
trigger ModelMesh by itself.

## Distribution Evidence

DevelopmentProcessFlow does not carry a fixed skill count or perform
installation. For install or release work it consumes one typed
`DistributionEvidence` from the distribution owner. That evidence is current
only when the source projection and installed projection fingerprints match
and the independent verification result is terminal and passing.

## Command-Line Entry

Create a current-schema `TaskFacts.to_dict()` JSON file, then derive the demand:

```powershell
python -m flowguard task-coverage-demand --facts task-facts.json --json
```

After an owner publishes a canonical maturation receipt, verify it from the
receipt store with the exact verification context:

```powershell
python -m flowguard model-maturation-receipt-verify --context verification-context.json --root . --receipt-root .flowguard/receipts --json
```

The CLI result proves only the declared identity and checks. It does not prove
unknown behavior outside the frozen task or target model.
