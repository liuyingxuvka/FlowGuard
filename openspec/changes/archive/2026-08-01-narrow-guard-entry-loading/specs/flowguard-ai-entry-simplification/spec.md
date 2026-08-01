## ADDED Requirements

### Requirement: Guaranteed prompt bundles are derived from declared loading
FlowGuard SHALL derive each guaranteed first-read prompt bundle from the selected skill shell and its declared unconditional reference edges. A hand-maintained manifest MAY set budgets and conditional reference declarations, but it MUST NOT omit an unconditional reference that the skill instructs the agent to read before route work begins.

#### Scenario: Skill adds an unconditional reference
- **WHEN** a selected skill shell adds an instruction to read a local reference before route execution
- **THEN** the prompt-bundle check includes that reference automatically or blocks with a load-graph mismatch

#### Scenario: Reference is conditional
- **WHEN** a skill instructs the agent to read a reference only after a named route, task shape, or evidence gap is selected
- **THEN** the reference is reported as conditional and is not charged to the guaranteed first-read bundle

### Requirement: Narrow entry preserves triggered depth
FlowGuard SHALL treat a narrow entry as a smaller initial materialization scope, not a weaker correctness or understanding mode. After a public route or kernel route is selected, every reference needed by a triggered native gap, broad claim, prediction, model miss, ambiguity, or high-impact obligation MUST remain loadable and the task MUST continue until route-native closure or an explicit external, scoped, stalled, or bounded terminal reason.

#### Scenario: Ordinary route is sufficient
- **WHEN** route selection and the first route action expose no deepening trigger
- **THEN** the agent may finish within the selected narrow claim boundary without loading unrelated deep references

#### Scenario: Important gap appears
- **WHEN** native evidence exposes a broad-claim, prediction, model-miss, ambiguity, high-impact, or still-addressable gap
- **THEN** the selected route loads only the reference mapped to that trigger and continues native model-predict-validate-revise work

### Requirement: Prompt budget reports practical headroom
FlowGuard prompt telemetry SHALL report deterministic UTF-8 source-size metrics, budget headroom bytes and ratio, and whether a configured minimum headroom is satisfied. It SHALL label any bytes-to-token calculation as a regression proxy and SHALL NOT describe it as provider token usage or billing evidence.

#### Scenario: Bundle fits by only a negligible margin
- **WHEN** a guaranteed bundle is below its maximum bytes but below its required headroom
- **THEN** the prompt-bundle check blocks the route as budget-fragile

#### Scenario: Telemetry is presented
- **WHEN** prompt-bundle telemetry is generated
- **THEN** it distinguishes measured source bytes from the conservative token proxy and from unavailable provider usage

