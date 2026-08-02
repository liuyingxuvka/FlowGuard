## ADDED Requirements

### Requirement: Blueprint structure recommendations cover the exact model-element universe
When a code-structure recommendation supports a software-blueprint claim, it SHALL bind the exact current set and fingerprint of required FunctionBlocks, state, fields, effects, and public entrypoints. Every required element SHALL map to one target owner or a typed unresolved disposition, and the recommendation SHALL emit reverse implementation-coverage obligations for later source audit.

#### Scenario: Nonempty mapping omits one current effect
- **WHEN** a recommendation maps several model elements but omits one effect from the bound current model universe
- **THEN** the recommendation is incomplete for blueprint use

#### Scenario: Model revision changes
- **WHEN** the model-element universe changes after recommendation
- **THEN** the recommendation and its reverse coverage obligations become stale
