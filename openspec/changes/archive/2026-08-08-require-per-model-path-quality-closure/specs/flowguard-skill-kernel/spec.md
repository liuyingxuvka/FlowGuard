## ADDED Requirements

### Requirement: Kernel exposes compact path quality without a new route
The FlowGuard skill kernel SHALL request the lightweight path-quality result for every new or materially changed model and expose only the current conclusion, trigger state, unresolved gap, and detailed-evidence reference needed by the task. It SHALL keep deep review conditional inside ModelMaturation and SHALL NOT present reconstruction, global optimization, or a separate path-optimization skill as ordinary work.

#### Scenario: Lightweight result is sufficient
- **WHEN** the result is current `single_clear_path` with no deep trigger
- **THEN** kernel guidance proceeds through the selected specialist using the compact summary

#### Scenario: Deep result is required
- **WHEN** a current trigger requires finite candidate comparison
- **THEN** guidance names the exact affected model boundary and bounded conclusion vocabulary
- **AND** it does not add a public route or load unrelated model details
