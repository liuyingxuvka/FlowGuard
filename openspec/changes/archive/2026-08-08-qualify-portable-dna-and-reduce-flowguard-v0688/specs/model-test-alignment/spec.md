## ADDED Requirements

### Requirement: Test receipts bind to exact behavior blocks and coverage edges
Model-Test Alignment SHALL bind each declared behavior block and coverage edge to one current code contract, exact test/native member, oracle, execution owner, and terminal receipt, while allowing one receipt to cover several members only through an explicit coverage set.

#### Scenario: One parent receipt covers several behavior blocks
- **WHEN** one current test receipt covers several behavior blocks
- **THEN** the alignment result SHALL list every covered behavior and edge explicitly
- **AND** the parent receipt SHALL not be copied as independent leaf execution evidence

#### Scenario: A behavior has only design evidence
- **WHEN** a checker design and code contract exist but no current terminal execution receipt exists
- **THEN** static design MAY remain complete
- **AND** execution coverage SHALL remain `not_run` and SHALL not be relabeled as passing

### Requirement: Alignment remains affected-only during ordinary work
Ordinary alignment SHALL load only the affected model, owner, behavior, test, and oracle neighborhood; whole-target alignment SHALL require an explicit qualification or release scope.

#### Scenario: One binding changes
- **WHEN** one model-code-test binding changes without changing unrelated owners
- **THEN** only that binding and its affected parent/child closure SHALL become stale
- **AND** unrelated current receipts SHALL remain eligible for exact reuse
