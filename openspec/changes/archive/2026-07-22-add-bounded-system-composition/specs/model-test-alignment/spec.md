## ADDED Requirements

### Requirement: Executable composition evidence maps from property to real regression
Model-Test Alignment SHALL preserve one chain from system property through affected slice, interaction case, minimal system trace step, component transition, and any declared code contract/runtime node to current external regression evidence. Code/runtime targets are optional non-semantic provenance at the model-checking layer; their presence, currentness, and production-conformance claim are owned here. Local component, token-composition, and executable-composition evidence MUST remain distinct.

#### Scenario: System failure becomes a regression target
- **WHEN** a bounded system check returns a counterexample
- **THEN** alignment creates stable targets for the owning property and each material trace step and binds them to real code/runtime/test evidence or visible gaps

#### Scenario: Unit tests are the only evidence
- **WHEN** local unit tests pass but no current executable-composition or mapped integration evidence covers the system property
- **THEN** alignment keeps the composite obligation open
