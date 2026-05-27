## Why

FlowGuard now has the pieces for model-first work, model misses, alignment,
meshes, ledgers, and closure claims, but the pieces are still easy to use as a
one-time checklist. Users need a concrete loop that asks, after code, tests, or
bugs appear, whether the model itself must become more precise before any broad
confidence claim is made.

## What Changes

- Add a model maturation loop that turns post-code evidence, model misses,
  scenario results, child-boundary changes, stale evidence, and ledger gaps
  into explicit model-upgrade actions.
- Add a small public helper API that reports whether no model change is needed,
  a state/transition/invariant/scenario/child split/parent reattachment is
  required, or the final claim must be downgraded.
- Update FlowGuard guidance so the thin model remains the entry point, while
  post-implementation and post-miss evidence must feed back into model
  obligations before closure claims.
- Add focused tests and documentation so the helper stays an orchestration
  layer over existing sub-capabilities rather than a replacement for
  Model-Miss Review, Model-Test Alignment, ModelMesh, TestMesh, Risk Evidence
  Ledger, or the closure contract.
- Sync source, installed package, installed skill guidance, shadow workspace,
  and visible version surfaces after validation.

## Capabilities

### New Capabilities

- `model-maturation-loop`: Defines the post-code/post-miss model upgrade
  decision loop and its supported outcomes.

### Modified Capabilities

- `model-first-function-flow`: Clarifies that later implementation evidence can
  force the original thin model to be revised, strengthened, connected, split,
  or scoped down.
- `post-runtime-model-miss-review`: Routes model-miss repair outcomes through
  model maturation decisions before closure.
- `model-test-alignment`: Treats too-coarse obligations, missing same-class
  evidence, and boundary observations as maturation signals.
- `hierarchical-model-mesh`: Treats child-boundary changes as parent
  reattachment or split signals in the maturation loop.
- `risk-evidence-ledger`: Lets missing model obligations or stale evidence
  point back to model maturation instead of being treated as a ledger-only
  failure.
- `flowguard-closure-contract`: Consumes the maturation decision before
  allowing complete FlowGuard-use claims.

## Impact

- Affected code: new `flowguard.model_maturation` helper and public exports.
- Affected docs and skills: modeling protocol, API surface, closure contract,
  README, AGENTS snippet, model-first skill, and relevant satellite guidance.
- Affected tests: focused unit tests, public API surface tests, and skill/doc
  checks.
- Runtime dependencies remain Python standard library only; schema remains
  `1.0`.
