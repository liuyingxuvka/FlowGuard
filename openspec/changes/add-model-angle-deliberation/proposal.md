## Why

FlowGuard already helps agents reuse existing models and route known gaps to
specialist checks, but agents can still over-trust one model without pausing to
ask whether the feature needs another model angle. This change makes that
reflection explicit without turning FlowGuard into a fixed checklist of lens
types or a new all-in-one runner.

## What Changes

- Add a lightweight Model Angle Deliberation capability where an agent records
  free-form candidate model angles, what the current model sees, what it may
  miss, the failure risk if ignored, and a disposition such as reuse, extend,
  create, add child model, defer, scope out, or human review.
- Integrate model-angle rows into Existing Model Preflight so broad confidence
  is blocked or scoped when required reflection is missing, unexplained, or
  unresolved.
- Extend AI-facing guidance so agents treat known FlowGuard routes as hints,
  not the full set of possible model angles.
- Add summary-report and maintenance-scan handoff metadata for unresolved
  model-angle findings while preserving MaintenanceScan as a thin router.
- Add closure/risk evidence consumption so full claims cannot silently omit a
  required model-angle review.
- Add public docs, templates, tests, and a FlowGuard self-model that catch
  checklist-only, no-reflection, no-rationale, and no-route variants.

## Capabilities

### New Capabilities
- `model-angle-deliberation`: Free-form model-angle reflection before relying on
  one FlowGuard model for a non-trivial feature or workflow claim.

### Modified Capabilities
- `existing-model-preflight`: Preflight can require and validate model-angle
  deliberation rows before downstream work or broad confidence.
- `flowguard-ai-entry-simplification`: AI hot paths must ask for open-ended
  model-angle reflection, with known routes as hints rather than a closed
  checklist.
- `flowguard-global-routing`: Route guidance must include the model-angle
  deliberation route and its relationship to existing specialist routes.
- `flowguard-closure-contract`: Closure checks can require current
  model-angle-review evidence for broad FlowGuard confidence.
- `risk-evidence-ledger`: Risk rows can consume model-angle review evidence and
  downgrade claims when required review is missing, stale, scoped, or blocked.
- `maintenance-scan-router`: Maintenance scan can route unresolved model-angle
  gaps to owner routes without validating those owner routes itself.

## Impact

- Public helper API: new dataclasses, report type, review helper, route API
  group, and template command for model-angle deliberation.
- Existing APIs: additive fields in ExistingModelPreflight, summary handoff,
  closure contract, risk ledger, and maintenance scan signal handling.
- Docs and skills: compact route-first guidance, AGENTS snippet, productized
  helper docs, API surface docs, and installed/project skill copies.
- Evidence: OpenSpec specs, a FlowGuard self-model, focused unit/template/skill
  tests, project audit, editable install sync, shadow workspace verification,
  adoption logs, and local git sync.
