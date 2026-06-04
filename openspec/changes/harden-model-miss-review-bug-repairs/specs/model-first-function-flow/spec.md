## ADDED Requirements

### Requirement: Kernel routes bug repairs to existing model-miss ownership
The model-first kernel SHALL route non-trivial bug repairs through Existing
Model Preflight and Model-Miss Review when the repair may affect modeled
behavior, evidence, tests, code contracts, compatibility paths, or final
confidence.

#### Scenario: Non-trivial bug repair has route map entry
- **WHEN** the FlowGuard route map is read
- **THEN** bug repairs are visibly routed to existing model ownership preflight
  and Model-Miss Review before implementation-only work can claim completion

#### Scenario: Direct implementation remains narrow
- **WHEN** the bug is typo-only, formatting-only, or has no behavior/state/test
  confidence impact
- **THEN** the kernel may skip FlowGuard with a concrete reason
