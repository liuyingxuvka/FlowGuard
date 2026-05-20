## ADDED Requirements

### Requirement: Global routing prefers direct FlowGuard satellite skills
The global Codex FlowGuard guidance SHALL first check whether a direct
FlowGuard satellite skill clearly matches the task and SHALL prefer that direct
skill over `model-first-function-flow` when the match is clear.

#### Scenario: Staged development routes directly
- **WHEN** a task is non-trivial staged development or modification with
  validation, such as plan, edit, test, fix, and verify
- **THEN** the global guidance routes to `flowguard-development-process-flow`
  instead of treating `model-first-function-flow` alone as sufficient

#### Scenario: UI interaction routes directly
- **WHEN** UI controls, screens, menus, navigation, overlays, visible states,
  journey coverage, UI text hierarchy, or implementation click-through
  evidence are the main risk
- **THEN** the global guidance routes to `flowguard-ui-flow-structure`

#### Scenario: Model-test evidence routes directly
- **WHEN** model obligations, tests, code contracts, scenarios, invariants,
  hazards, or evidence coverage need direct comparison
- **THEN** the global guidance routes to `flowguard-model-test-alignment`

#### Scenario: Ambiguous routing uses kernel
- **WHEN** no direct satellite route clearly matches, several routes apply, or
  a core behavior/state model is needed before narrowing
- **THEN** the global guidance routes to `model-first-function-flow`

### Requirement: FlowGuard satellite routes are peers
The global guidance SHALL list FlowGuard satellite skills as peer routes and
SHALL NOT describe `model-first-function-flow` as the mandatory parent entry
for every FlowGuard task.

#### Scenario: Peer route table is visible
- **WHEN** a Codex agent reads the global FlowGuard section or repository
  AGENTS snippet
- **THEN** it sees a route table for `flowguard-development-process-flow`,
  `flowguard-ui-flow-structure`, `flowguard-code-structure-recommendation`,
  `flowguard-model-test-alignment`, `flowguard-test-mesh`,
  `flowguard-structure-mesh`, `flowguard-model-mesh`,
  `flowguard-model-miss-review`, and `model-first-function-flow`

#### Scenario: Kernel scope is bounded
- **WHEN** the `model-first-function-flow` skill guidance is read
- **THEN** it says the kernel owns ordinary behavior/state modeling, unclear
  route selection, and cross-route coordination, while clear direct satellite
  matches should use the matching satellite
