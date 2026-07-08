# FlowGuard Behavior Commitment Ledger

Behavior Commitment Ledger is the full behavior account book for a project,
work package, or release boundary.

In plain language: before an AI says a feature, project, release, UI flow, CLI
command, skill, or workflow is covered, the ledger asks, "What exact external
behaviors are promised, where did those promises come from, and which model is
the one primary owner for each one?"

## What Counts As A Commitment

A commitment is an external, verifiable promise. Examples:

- a public API or CLI command behavior;
- a UI capability users can perform;
- a documented workflow;
- a skill or agent workflow behavior;
- a release, archive, publish, or process behavior that downstream work relies on.

A commitment is not every helper function, private class, implementation file,
internal field, or model. A model proves a commitment; it is not automatically
the whole feature inventory.

## What The Ledger Checks

The ledger checks both directions:

- every in-scope source surface maps to one or more commitments;
- every in-scope commitment maps back to source evidence or source surfaces.

It also checks:

- missing expected commitments;
- extra invented commitments with no source;
- one primary owner model per commitment;
- supporting or child models that accidentally overlap the primary owner;
- unknown dependency ids;
- scoped-out behavior without owner, reason, validation boundary, and rationale;
- broad claims without current evidence or risk gates.

## How It Connects To Primary Path Authority

The ledger is upstream. Primary Path Authority is downstream.

Use this rule:

```text
Behavior Commitment Ledger
-> path_sensitive=true commitment
-> Primary Path Authority
-> no automatic A failed -> B succeeded path
-> TestMesh shards + Risk Evidence Ledger gates
```

The ledger should not recreate fallback detection. If a behavior is
path-sensitive, attach PPA evidence with
`behavior_path_binding_from_primary_path_report()`. If PPA blocks, the ledger
blocks that commitment and any broad claim depending on it.

## Public API Shape

Core objects:

- `BehaviorCommitmentLedger`
- `BehaviorSourceSurface`
- `BehaviorCommitment`
- `BehaviorEvidenceBinding`
- `BehaviorPathAuthorityBinding`
- `review_behavior_commitment_ledger()`
- `behavior_path_binding_from_primary_path_report()`
- `behavior_commitment_contract_exhaustion_plan()`

Template:

```powershell
python -m flowguard behavior-commitment-ledger-template --output <target>
```

## Broad Claim Rule

For done, release, publish, archive, production, or full-confidence claims, use
current ledger evidence plus downstream evidence:

- ContractExhaustionMesh commitment coverage cases;
- TestMesh child shard ownership;
- Model-Test Alignment bindings to model obligations, code contracts, tests,
  and commitment ids;
- Risk Evidence Ledger gates;
- PPA evidence for every `path_sensitive=true` commitment.

If the ledger says behavior is missing, extra, overlapping, stale, or
PPA-blocked, repair the root commitment, owner model, evidence, or primary
path. Do not add a second runtime path as a workaround.
