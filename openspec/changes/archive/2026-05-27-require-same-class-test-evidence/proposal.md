## Why

Post-runtime model-miss repair already requires the observed failure and a
same-class generalized bad case, but agents can still close the miss after a
model repair and one green regression test. That leaves the same bug family
able to return through a different input, state, or code boundary.

The same weakness is larger when a defect family appears more than once across
projects or integrations: another local green fix can look successful while the
framework has still not created a reusable gate for that family. FlowGuard needs
to promote recurring same-class misses into a defect-family confidence boundary,
not teach each downstream product to remember that history.

## What Changes

- Require every in-scope model-miss repair to include same-class test evidence
  before full closure is claimed.
- Promote recurring or high-risk same-class model misses into an explicit
  defect-family gate with an owner model obligation, authority boundary,
  observed failure case, same-class generalized case, historical holdout, and
  current proof evidence.
- Route repaired model obligations through Model-Test Alignment so new model
  obligations, code contracts when in scope, and ordinary tests are compared
  explicitly.
- Feed defect-family gate status into the Risk Evidence Ledger so final
  confidence is blocked, scoped, or full at the FlowGuard layer instead of
  depending on a product-specific reminder.
- Require stale or overclaimed pre-repair test evidence to stay visible until
  DevelopmentProcessFlow records the minimum revalidation needed for the final
  claim.
- Route large, slow, layered, or release-only same-class validation into
  TestMesh instead of expanding Model-Test Alignment into a test hierarchy.
- Update public templates, docs, skill guidance, and focused tests so the
  workflow rejects point-fix-only test upgrades.

## Capabilities

### New Capabilities
- `model-miss-test-evidence-closure`: Defines the closure gate that links
  model-miss repair to same-class test evidence, model-test alignment,
  revalidation freshness, and TestMesh escalation.
- `recurring-model-miss-defect-family-gate`: Defines the promotion rule for
  repeated same-class misses and the ledger-facing proof needed before a broad
  full-confidence claim is allowed.

### Modified Capabilities
- `risk-evidence-ledger`: Adds a defect-family gate reference and freshness
  boundary for final confidence claims.

## Impact

- Affected helper APIs: `flowguard.model_test_alignment`,
  `flowguard.recurring_model_miss`, `flowguard.risk_evidence_ledger`,
  `flowguard.development_process_flow`, and public template scaffolds where
  they represent model-miss closure evidence.
- Affected docs and skills: model-miss review, model-test alignment,
  development process flow, TestMesh, README, adoption notes, and generated
  template notes.
- Affected tests: focused model-test alignment, recurring model-miss gate,
  risk evidence ledger, development-process, public-template, skill-doc, and
  model-miss example regression tests.
