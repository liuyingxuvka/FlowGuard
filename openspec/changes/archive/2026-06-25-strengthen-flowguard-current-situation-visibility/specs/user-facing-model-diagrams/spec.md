## MODIFIED Requirements

### Requirement: Lightweight Diagram Guidance
FlowGuard skills SHALL allow agents to use a user-facing Mermaid diagram or
compact flow sketch when the value of a non-trivial model would otherwise be
hard for the user to understand. When the task is non-trivial, the skill
guidance SHALL pair any diagram with a short plain-language current situation
explanation unless the user suppresses progress detail.

#### Scenario: Abstract model explanation needs a diagram
- **WHEN** a FlowGuard route explains a model upgrade, abstract multi-stage
  check, counterexample, missing branch, or claim boundary
- **THEN** the skill guidance permits a Mermaid diagram or compact flow sketch
  that explains what was modeled and why it matters, paired with the current
  status, evidence or gap, and next step

#### Scenario: Obvious task does not require a diagram
- **WHEN** a task is tiny, obvious, or mechanically reported without meaningful
  model interpretation
- **THEN** the skill guidance does not force a diagram or expanded current
  situation explanation

### Requirement: Expressive Diagram Content
When a user-facing model diagram is used, the skill guidance SHALL encourage it
to show major states, branches, gates, evidence, and claim boundaries rather
than only a shallow linear chain. The adjacent current situation explanation
SHALL keep the user's immediate position in the workflow visible.

#### Scenario: Diagram communicates model value
- **WHEN** a FlowGuard route chooses to show a diagram
- **THEN** the diagram guidance describes enough structure to help the user see
  the main flow, important alternatives, evidence links, and what can or cannot
  be claimed, while the adjacent explanation states what FlowGuard is doing now

### Requirement: Focused Route Coverage
The prompt upgrade SHALL add route-specific current situation and diagram
guidance to the FlowGuard kernel, UI Flow Structure, ModelMesh,
DevelopmentProcessFlow, and ExistingModelPreflight skills without requiring
every satellite skill to be deeply rewritten at once.

#### Scenario: Kernel and high-value routes are covered
- **WHEN** the change is implemented
- **THEN** the shared kernel and the selected satellite skills contain
  lightweight user-facing current situation and diagram guidance

#### Scenario: Other routes inherit the kernel guidance
- **WHEN** another FlowGuard satellite skill is used
- **THEN** the shared kernel guidance still permits a current situation
  explanation and diagram when the model explanation would benefit from them
