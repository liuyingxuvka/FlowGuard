## ADDED Requirements

### Requirement: Model-Test Alignment consumes transition coverage obligations
Model-Test Alignment SHALL support obligations generated from transition coverage cells and apply the same evidence freshness, status, required-kind, and target-id rules as hand-authored obligations.

#### Scenario: Transition obligation has evidence
- **WHEN** a transition-derived obligation has current passing test evidence of an allowed required kind
- **THEN** Model-Test Alignment SHALL treat the transition obligation as covered

#### Scenario: Transition obligation lacks evidence
- **WHEN** a transition-derived obligation has no current passing test evidence
- **THEN** Model-Test Alignment SHALL report missing test evidence for that transition obligation

#### Scenario: Transition cell evidence names target
- **WHEN** a test evidence row is marked as leaf matrix-cell or transition-cell evidence
- **THEN** it MUST identify the target cell id before it can support the transition-derived obligation

### Requirement: Transition coverage stays independent from TestMesh
Model-Test Alignment SHALL evaluate transition-derived obligations directly for ordinary evidence and SHALL route large or slow evidence hierarchy to TestMesh instead of becoming a mesh route.

#### Scenario: Ordinary transition coverage does not require TestMesh
- **WHEN** the matrix is small and ordinary tests provide evidence
- **THEN** Model-Test Alignment can review transition-derived obligations without requiring a TestMesh plan

#### Scenario: Large transition coverage routes outward
- **WHEN** the matrix is large, slow, layered, stale-prone, or release-only
- **THEN** agents use TestMesh for child-suite evidence ownership while Model-Test Alignment keeps semantic obligations visible
