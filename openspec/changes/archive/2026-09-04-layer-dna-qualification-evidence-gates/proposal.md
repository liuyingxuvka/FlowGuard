## Why

FlowGuard currently exposes layered static, semantic, code-binding, and
test-binding facts, but a caller can still read all four as a broad DNA
qualification even when executable evidence is `not_run` or its currentness
identity is absent. This change makes the claim boundary explicit and keeps
static blueprint readiness useful without licensing a runtime-complete claim.

## What Changes

- Add an explicit execution-evidence layer to the provider-neutral DNA
  qualification result.
- Distinguish a statically ready DNA binding from a fully qualified current
  runtime claim; only the latter may expose `qualified=true`.
- Require a current, non-empty execution evidence fingerprint for the broad
  claim and preserve `not_run`, stale, blocked, failed, and missing reasons.
- Derive the execution layer from the canonical readiness ledger rather than
  from caller-authored booleans or static binding status.
- Add an execution-evidence fingerprint to the behavior readiness report so a
  runtime claim can bind to exact native execution inputs without executing
  work during a readiness review.
- Add focused negative and round-trip tests for static-only, missing-current,
  stale, failed, and fully executed qualification states.

## Capabilities

### New Capabilities

- `layered-dna-qualification-evidence`: Explicit static-versus-executed DNA
  qualification and fail-closed claim projection.

### Modified Capabilities

- `software-blueprint-readiness`: Expose an exact execution-evidence identity
  separately from static behavior/checker readiness.

## Impact

The change affects `flowguard/target_system_blueprint.py` and
`flowguard/software_blueprint_readiness.py`, their focused tests, and the
native provider-neutral qualification schema. It does not change the model
authority, install projection, provider execution, current pointers, or the
existing narrow static readiness claim. Existing static `implementation_admitted`
and pre-code readiness remain separate from broad DNA qualification.
