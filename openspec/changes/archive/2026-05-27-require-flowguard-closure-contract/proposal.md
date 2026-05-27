## Why

FlowGuard guidance currently describes the thin model-first path and the route
inventory, but it still leaves room for agents to treat plan intake, same-class
bug coverage, model-test alignment, evidence freshness, and final claim review
as optional escalation. The desired product contract is stricter: if those
closure gates are needed for the claim and are missing, the work must be
reported as partial FlowGuard use, not as FlowGuard completion.

## What Changes

- Define a mandatory FlowGuard closure contract for any full done, release,
  publish, or production-confidence claim.
- Clarify that the thin path is only the entry shape; completion requires the
  closure contract whenever the claim crosses model, code, test, process, UI,
  mesh, adapter, or evidence boundaries.
- Update kernel, satellite-adjacent guidance, AGENTS snippet, README, modeling
  docs, changelog, and local self-review models so "FlowGuard used" cannot mean
  a partial model or test pass.
- Add focused tests and a small executable FlowGuard model that rejects
  optional-mode wording and rejects completion without the closure gates.
- Sync the source checkout, shadow workspace, installed Codex skills, editable
  install, and visible package version surfaces after validation.

## Capabilities

### New Capabilities

- `flowguard-closure-contract`: Defines the mandatory closure chain that must
  be satisfied before a task can claim complete FlowGuard use.

### Modified Capabilities

- `model-first-function-flow`: Clarifies that the thin path starts FlowGuard
  work but does not itself authorize full confidence or completion claims.
- `development-process-flow`: Treats the closure contract as part of done,
  release, archive, publish, and production-confidence evidence freshness.
- `risk-evidence-ledger`: Remains the final evidence boundary consumed by the
  closure contract rather than an optional add-on.

## Impact

- Affected docs and skills: README, changelog, AGENTS snippet,
  `model-first-function-flow` kernel, kernel reference protocol, modeling
  protocol, and a new closure-contract doc.
- Affected local models/tests: new `.flowguard/flowguard_closure_contract`
  check, existing skill-satellite release model, and focused skill-doc tests.
- Affected install/version surfaces: package version, editable install, shadow
  workspace, installed Codex skill directories, and source git checkout.
- Runtime dependencies remain Python standard library only; schema remains
  `1.0`.
