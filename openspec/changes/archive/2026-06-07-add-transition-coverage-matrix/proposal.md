## Why

FlowGuard already checks declared model obligations against test evidence, but ordinary state-transition models do not yet have one default bridge that turns modeled transitions into test-evidence obligations. This change makes transition coverage matrix generation a first-class planning surface so model green, UI green, and test green claims stay aligned.

## What Changes

- Add a transition coverage matrix capability that represents critical `Input/Event x State -> Output x State` cells as coverage obligations.
- Add helper projections from transition coverage cells into Model-Test Alignment obligations and TestMesh leaf-cell requirements.
- Extend UI flow guidance so modeled UI transitions can produce transition coverage cells for implementation evidence.
- Extend model-first guidance so broad coverage claims must derive transition coverage obligations or explicitly scope them out.
- Extend TestMesh guidance so large transition matrices can be delegated to child suites without hiding missing cell evidence.

## Capabilities

### New Capabilities
- `transition-coverage-matrix`: Defines transition coverage cells, matrices, and projections into model-test and test-mesh evidence surfaces.

### Modified Capabilities
- `model-test-alignment`: Consumes transition-derived model obligations and blocks coverage when transition cells lack current evidence.
- `flowguard-ui-flow-structure`: Exposes UI transitions as transition coverage cells for runnable UI validation.
- `test-evidence-mesh`: Allows large transition coverage matrices to become parent/child leaf-cell evidence requirements.
- `model-first-function-flow`: Requires transition coverage projection, or an explicit scoped-out reason, before broad test coverage claims.

## Impact

- Affected modules: `flowguard/transition_coverage.py`, `flowguard/model_test_alignment.py`, `flowguard/ui_structure.py`, `flowguard/testmesh.py`, and public exports.
- Affected docs/templates: model-test alignment, UI flow structure, TestMesh, modeling protocol, check plan, and template text.
- Affected skills: model-first kernel, Model-Test Alignment, UI Flow Structure, TestMesh, and DevelopmentProcessFlow.
- No dependency changes are expected.
