## ADDED Requirements

### Requirement: Triggered UI coverage contributes to maturation
UI Flow Structure SHALL project the current in-scope surface, journey, control, transition, recovery, blindspot, implementation, and operability coverage into task-local maturation when UI work is triggered.

#### Scenario: Screenshot lacks functional chain evidence
- **WHEN** a UI contribution has visual or screenshot evidence but lacks a required current functional journey, transition, recovery, or real-surface result
- **THEN** maturation MUST preserve the missing UI obligation rather than count the screenshot as full coverage

#### Scenario: UI does not introduce a global persona taxonomy
- **WHEN** the target UI varies by a target-software role or permission
- **THEN** UI Flow Structure MUST preserve the target-owned role reference without defining a FlowGuard-wide audience, role, or persona taxonomy
