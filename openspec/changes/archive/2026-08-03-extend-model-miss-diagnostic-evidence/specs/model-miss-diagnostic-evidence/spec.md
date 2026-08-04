## ADDED Requirements

### Requirement: A model miss can expose a bounded subset-minimal conflict

FlowGuard SHALL derive a diagnostic core from exact observation, model expectation, code/test surface, and failure-boundary atoms under the model-miss review oracle.

#### Scenario: Redundant atoms exist

- **WHEN** removing an atom leaves the disagreement inconsistent
- **THEN** that atom SHALL be removed from the diagnostic core

#### Scenario: Budget expires

- **WHEN** the diagnostic budget expires before every retained atom is tested
- **THEN** the report SHALL say `bounded_incomplete` and SHALL NOT claim subset minimality

### Requirement: Diagnosis does not replace review authority

The diagnostic report SHALL remain subordinate to the existing model-miss review status and receipt.

#### Scenario: The parent review is blocked

- **WHEN** model-miss review lacks current observed evidence
- **THEN** a diagnostic projection SHALL remain blocked and SHALL NOT create a green terminal

### Requirement: Repairs preserve positive behavior

Every repair candidate SHALL name at least one positive obligation that remains accepted and SHALL explain why the original miss is rejected.

#### Scenario: A repair only weakens the invariant

- **WHEN** a repair accepts the miss by deleting the affected obligation or removing all positive behavior
- **THEN** FlowGuard SHALL reject it as vacuous

#### Scenario: A repair is non-vacuous

- **WHEN** the original miss is rejected for the intended reason and named positive behaviors remain accepted
- **THEN** the report SHALL expose the preserved obligations and required next validation route
