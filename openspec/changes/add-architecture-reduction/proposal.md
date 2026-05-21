## Why

FlowGuard can already model behavior and recommend code structure, but it does not yet have a first-class route for asking whether an existing flow has become unnecessarily complex and whether code can be safely contracted without changing public behavior. This change adds a model-to-code architecture reduction capability so agents can find provable simplification opportunities before adding more branches, adapters, modules, or validation layers.

## What Changes

- Add an architecture reduction capability that reviews existing FlowGuard model ownership, code boundaries, and observable behavior contracts before recommending code contraction.
- Add structured reduction candidates for merging handlers/modules, collapsing pass-through adapters, removing dead branches, removing irrelevant state fields, and keeping public facades when compatibility requires them.
- Add proof-status levels so recommendations distinguish fully behavior-preserving reductions from property-only reductions, missing-evidence cases, and risky branches that should be kept.
- Add a target structure recommendation handoff so reduced model evidence can feed Code Structure Recommendation and StructureMesh before production code is changed.
- Add Codex skill routing guidance so DevelopmentProcessFlow, Existing Model Preflight, ModelMesh, StructureMesh, Code Structure Recommendation, Model-Test Alignment, and UI Flow Structure can invoke architecture reduction when complexity growth is detected.
- No breaking changes to existing FlowGuard core APIs.

## Capabilities

### New Capabilities
- `architecture-reduction`: Reviews model-to-code architecture contraction opportunities, proof status, target structure recommendations, and required refactor gates.

### Modified Capabilities
- None.

## Impact

- Affected package areas: new architecture reduction helper module, public exports, CLI/template surface if needed, and focused tests.
- Affected docs and skills: API surface docs, FlowGuard skill routing docs, DevelopmentProcessFlow guidance, StructureMesh/Code Structure Recommendation handoff guidance, and a new Codex subskill.
- Validation: focused unit tests for candidate classification and routing, FlowGuard self-model checks for the new route, OpenSpec validation, and broader pytest/regression runs before install and git synchronization.
