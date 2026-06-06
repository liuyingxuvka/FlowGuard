# FlowGuard Closure Contract

Complete FlowGuard use is not a mode. It is the contract that must be current
before a task can claim full done, release, publish, or production confidence
from FlowGuard evidence.

The thin model-first path remains the entry shape:

```text
risky boundary -> Input x State -> Set(Output x State)
-> one invariant or scenario -> run checks
-> inspect counterexample -> escalate only if a named risk requires it
```

That path can support a bounded local claim. It does not by itself support a
broad completion claim. A broad claim needs the closure contract for every
in-scope risk boundary that the result depends on.

## Executable Review Helper

Use `review_flowguard_closure_contract()` to turn the closure contract into a
machine-checkable final gate. The helper consumes summaries from existing
routes; it does not replace the route that owns each proof.

Build a `FlowGuardClosureContractPlan` with:

- `RuntimeTraceMapping` rows for runtime traces mapped to model obligations.
- `ArtifactInvalidation` rows for changed files or generated artifacts that can
  stale older evidence.
- `ModelQualitySignal` rows for hidden state, missing side effects, owner
  ambiguity, helper-only proof, missing public boundary, or parent/child
  evidence gaps.
- `SameClassMissClosure` rows for observed failures plus same-class proof.
- `RuntimeGatewayInventoryClosure` rows for critical runtime state writer
  inventory and gateway adoption evidence.
- `field_lifecycle_reports` or `ClosureEvidenceReport` rows with
  `field_lifecycle_mesh` kind when behavior-bearing fields, replacements, or
  old-field disposition are in scope.
- `ClosureEvidenceReport` rows for the Risk Evidence Ledger and route reports
  that the final claim consumes.

The report returns `flowguard_closure_full_confidence`,
`flowguard_closure_scoped_confidence`, or `flowguard_closure_blocked`. A scoped
report is still not a full-confidence claim.

To create a project scaffold:

```bash
python -m flowguard closure-contract-template --output .
python .flowguard/closure_contract/run_checks.py
```

## Required Gates

Use the gates that match the claim:

- Plan/risk intake: current source evidence, user-facing risk surfaces,
  omitted/out-of-scope reasons, and historical miss context are declared.
- Existing model ownership: current model boundaries have been consulted, or a
  new boundary is justified.
- Model obligation: the relevant `Input x State -> Set(Output x State)` model,
  invariant, scenario, replay, or parent/child obligation is current.
- Model-miss or bug repair: every non-trivial in-scope bug class has the
  observed failure, root-cause backpropagation when a prior claim existed, and
  a same-class generalized bad case when practical.
- Model-test/code alignment: model obligations, code contracts, code-boundary
  observations, and test evidence line up at the external boundary being
  claimed.
- Legacy path disposition: old, fallback, compatibility, or alternate paths
  left reachable by the repair are deleted, blocked, delegated to a repaired
  contract, same-contract repaired, or explicitly scoped with a reason.
- Field lifecycle: behavior-bearing fields are projected into model
  obligations and code contracts, display-only fields are scoped out with
  reasons, and old/replaced/deprecated fields have closing disposition
  evidence.
- Obligation-family parity: when related obligations share one confidence
  claim, each sibling has the required mechanism evidence from allowed
  provenance sources, or the family gap stays visible.
- Analogous defect scan: after a post-green miss, same-shape sibling risks have
  been reviewed, covered, assigned to a separate change, or excluded with a
  concrete reason before broad closure is restored.
- Runtime gateway adoption: when the claim says FlowGuard protects production
  state mutation, every critical state surface has complete writer inventory,
  gateway ownership, mediated write observations, and current step, boundary,
  replay, and proof evidence.
- Runtime path alignment: when the claim depends on real code following the
  model's node path, a current `runtime_path_alignment` report exists so full
  confidence cannot rest on anonymous progress logs.
- Mesh or layered boundary proof: parent/child model or test confidence
  consumes current child evidence and finite leaf boundary-matrix evidence when
  required.
- Model maturation: post-code, post-miss, model-test, mesh, code-boundary, or
  freshness signals that say the model is too coarse, stale, or disconnected
  have been resolved, or the claim is explicitly scoped down.
- Evidence freshness: later edits, peer writes, adapter changes, generated
  artifacts, and long-running checks have not made earlier evidence stale.
- Risk Evidence Ledger: user risks connect to model obligations, owner code
  contracts, model-code-test binding rows, obligation-family gates, analogous
  defect scans, defect-family gates, split gates, and current proof evidence.
- Typed claim chain: broad claims consume the right support type instead of
  promoting plan-only, model-only, or test-only evidence into production
  confidence.

## Reporting Rule

If a required gate is missing, stale, skipped, progress-only, release-only,
internal-path-only, a direct runtime write can bypass the declared gateway, or
the gate is explicitly scoped out, report the result as partial or scoped
FlowGuard evidence. Do not say FlowGuard is complete for that claim.

If a later runtime, test, replay, log, manual validation failure, or
non-trivial bug report appears after a green FlowGuard result, treat it as a
closure-contract miss until Model-Miss Review, root-cause backpropagation,
same-class evidence, owner code contract binding, family parity, analogous
defect scan, legacy path disposition, alignment, model maturation, freshness,
ledger, and claim-chain evidence have been repaired.
If the miss or replacement involved fields, include FieldLifecycleMesh and
old-field disposition repair in that same closure chain.

## What This Does Not Mean

The closure contract does not claim that arbitrary unmodeled behavior is bug
free. It means FlowGuard cannot honestly report green completion while a
declared in-scope risk is unsupported by the current evidence chain.
