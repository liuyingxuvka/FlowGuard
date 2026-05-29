## MODIFIED Requirements

### Requirement: Prompt hot paths stay compact while implementation surfaces shrink
FlowGuard SHALL keep kernel, AGENTS snippet, and satellite skill hot paths under
their prompt budgets while allowing package implementation surfaces behind those
prompts to be split, grouped, or table-driven.

#### Scenario: Prompt budget remains enforced
- **WHEN** FlowGuard implementation surfaces are simplified
- **THEN** skill documentation tests still enforce kernel, AGENTS snippet, and
  satellite hot-path budgets

#### Scenario: Implementation split does not grow prompt text
- **WHEN** template, API, or evidence structures are reorganized
- **THEN** the AI-facing route shells do not need new long-form protocol text
