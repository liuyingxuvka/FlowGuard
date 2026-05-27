## Why

FlowGuard already has ModelMesh, TestMesh, target split derivation, and
budgeted model-group support. The remaining gap is earlier in the route: large
or slow models and tests can still be kept as one broad evidence object until a
human explicitly decides to split them. That lets long-running checks produce
progress without becoming a parent/child evidence structure.

FlowGuard should automatically diagnose when direct model or test evidence is
too large, slow, coarse, background-only, or incomplete for a full-confidence
claim, then route that evidence into ModelMesh or TestMesh split derivation.

## What Changes

- Add an auto split diagnostic helper that reviews model/test evidence metrics
  against FlowGuard thresholds and returns required ModelMesh/TestMesh split
  actions.
- Generate target model split and target test split derivation stubs from the
  diagnostic when suggested child ids and parent partition items are available.
- Feed required auto split status into DevelopmentProcessFlow so done/release
  claims cannot treat oversized direct evidence as current full proof.
- Feed required model/test split status into the Risk Evidence Ledger so final
  risk confidence is blocked or scoped until child evidence is current.
- Update ModelMesh/TestMesh/DevelopmentProcessFlow docs, skills, templates, and
  tests so large direct evidence becomes a split route rather than a long
  monolithic run.

## Capabilities

### New Capabilities

- `auto-model-test-mesh-split-derivation`: Derives whether model/test evidence
  must be routed to ModelMesh or TestMesh, and emits target split derivation
  recommendations from the same diagnostic.

### Modified Capabilities

- `hierarchical-model-mesh`: Consumes auto split diagnostics as the default
  escalation path for oversized or coarse model evidence.
- `test-evidence-mesh`: Consumes auto split diagnostics as the default
  escalation path for slow, broad, background, release-only, or progress-only
  validation evidence.
- `development-process-flow`: Blocks done/release claims that rely on oversized
  direct evidence without current auto split review.
- `risk-evidence-ledger`: Blocks or scopes final confidence when a risk requires
  a current model/test split gate.

## Impact

- Public API: new auto split dataclasses and review helper, plus small optional
  status fields on DevelopmentProcessFlow and Risk Evidence Ledger objects.
- Behavior: direct oversized model/test evidence can no longer support broad
  full confidence without a current ModelMesh/TestMesh split route.
- Documentation/templates: teach automatic split triggers and parent evidence
  consumption.
- Validation: focused unit tests, template/docs tests, OpenSpec strict
  validation, model examples, install sync, shadow sync, and full practical
  regression.
