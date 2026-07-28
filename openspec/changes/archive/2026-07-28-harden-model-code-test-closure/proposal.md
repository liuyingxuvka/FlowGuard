## Why

FlowGuard already has model, code-contract, source-audit, boundary, runtime,
and test evidence rows, but real-code closure can still be overclaimed when
those rows stay disconnected. AI agents need the existing binding layer to act
as one auditable gate: the model obligation, owner code, source audit, runtime
boundary, known-bad replay, and external test must close on the same behavior.

## What Changes

- Make conservative Python source audit a first-class optional gate in
  `ModelTestAlignmentPlan` for real-code claims.
- Expand model-code-test binding rows from one model/code/test triple into a
  dense closure summary that lists owner contracts, paths, symbols, test ids,
  runtime/boundary/payload ids, source-audit decision, and open gap codes.
- Require counterexample and known-bad obligations to close through current
  external tests bound to the owner code contract and the concrete
  counterexample or known-bad target id.
- Harden Runtime Gateway Adoption so complete writer inventory can be
  represented as structured current evidence, not only an opaque inventory id.
- Update agent skills, prompt templates, docs, API exports, tests, and local
  FlowGuard model regressions so agents use the hardened closure path by
  default for real code.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `model-test-alignment`: add source-audit gating, closure-rich binding rows,
  and counterexample/known-bad target closure requirements.
- `runtime-gateway-adoption`: require structured writer inventory evidence for
  runtime-gateway claims while retaining the existing inventory id as a
  compatibility field.
- `post-runtime-model-miss-review`: require known-bad and counterexample
  closure to be projected into owner-code-bound regression evidence before
  broad repair confidence.

## Impact

- Affected code: `flowguard/model_test_alignment.py`,
  `flowguard/model_test_alignment_source.py`, `flowguard/runtime_gateway.py`,
  `flowguard/__init__.py`, and template text modules.
- Affected tests: model-test alignment, source audit, runtime gateway adoption,
  API surface, public templates, skill docs, and local FlowGuard model checks.
- Affected docs/skills: Model-Test Alignment, Model-Miss Review, Runtime
  Gateway Adoption, DevelopmentProcessFlow, model-first protocol, API surface,
  README/CHANGELOG, and prompt templates.
