## ADDED Requirements

### Requirement: Architecture Reduction consumes but does not own model path quality
Architecture Reduction SHALL consume a current model-path-quality result as provenance only when exact blueprint bindings identify corresponding implementation, helper, module, adapter, public-entrypoint, or validation-layer candidates. It SHALL apply its own consumer, facade, side-effect, equivalence, retirement, and evidence requirements and SHALL NOT run a second model optimizer.

#### Scenario: Model-only contraction has no code effect
- **WHEN** an equivalent model representation contracts without changing a mapped implementation surface
- **THEN** ModelMaturation owns the revised model and Architecture Reduction makes no code-contraction claim

#### Scenario: Model result exposes duplicate code
- **WHEN** exact bindings map a proved model contraction to duplicate implementation surfaces
- **THEN** Architecture Reduction materializes concrete candidates and validates them under its own contract
