# user-facing-model-diagrams Specification

## Purpose
TBD - created by archiving change add-user-facing-model-diagrams. Update Purpose after archive.
## Requirements
### Requirement: Lightweight Diagram Guidance
FlowGuard skills SHALL allow agents to use a user-facing Mermaid diagram or
compact flow sketch when the value of a non-trivial model would otherwise be
hard for the user to understand.

#### Scenario: Abstract model explanation needs a diagram
- **WHEN** a FlowGuard route explains a model upgrade, abstract multi-stage
  check, counterexample, missing branch, or claim boundary
- **THEN** the skill guidance permits a Mermaid diagram or compact flow sketch
  that explains what was modeled and why it matters

#### Scenario: Obvious task does not require a diagram
- **WHEN** a task is tiny, obvious, or mechanically reported without meaningful
  model interpretation
- **THEN** the skill guidance does not force a diagram

### Requirement: Expressive Diagram Content
When a user-facing model diagram is used, the skill guidance SHALL encourage it
to show major states, branches, gates, evidence, and claim boundaries rather
than only a shallow linear chain.

#### Scenario: Diagram communicates model value
- **WHEN** a FlowGuard route chooses to show a diagram
- **THEN** the diagram guidance describes enough structure to help the user see
  the main flow, important alternatives, evidence links, and what can or cannot
  be claimed

### Requirement: Focused Route Coverage
The initial prompt upgrade SHALL add route-specific diagram guidance to the
FlowGuard kernel, UI Flow Structure, ModelMesh, and DevelopmentProcessFlow
skills without requiring every satellite skill to be edited at once.

#### Scenario: Kernel and high-value routes are covered
- **WHEN** the change is implemented
- **THEN** the shared kernel and the three selected satellite skills contain
  lightweight user-facing diagram guidance

#### Scenario: Other routes inherit the kernel guidance
- **WHEN** another FlowGuard satellite skill is used
- **THEN** the shared kernel guidance still permits a diagram when the model
  explanation would benefit from one

### Requirement: No Runtime Semantics Change
The diagram guidance SHALL NOT change FlowGuard's executable model semantics,
public Python API, schema version, or validation pass/fail criteria.

#### Scenario: Prompt-only upgrade
- **WHEN** the release is validated
- **THEN** existing runtime tests and public API checks continue to pass without
  requiring a new FlowGuard schema version
