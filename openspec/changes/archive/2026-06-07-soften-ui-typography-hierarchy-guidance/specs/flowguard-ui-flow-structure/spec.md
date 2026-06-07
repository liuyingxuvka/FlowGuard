## ADDED Requirements

### Requirement: UI text hierarchy handoff guides visual review
The FlowGuard UI Flow Structure route SHALL hand off text hierarchy evidence to
frontend, Figma, design-review, and design-iteration workflows with soft
typography hygiene guidance instead of treating the semantic hierarchy as final
visual styling.

#### Scenario: Handoff names downstream typography hygiene
- **WHEN** the route produces or references a UI text hierarchy blueprint before
  frontend implementation or visual design
- **THEN** the route guidance tells downstream workflows to preserve calm
  hierarchy, reuse visual text treatments for similar text jobs, and explain
  intentional visual differences

#### Scenario: Implementation review checks hierarchy calm without hard caps
- **WHEN** a running UI or screenshot is reviewed after a UI text hierarchy
  blueprint exists
- **THEN** the review may flag chaotic one-off text treatments as actionable
  design findings while avoiding a fixed maximum font-size rule
