## MODIFIED Requirements

### Requirement: Strategy selection is multi-objective and bounded
The system SHALL compare process effort, rework, coordination, information value, or measured cost only among current candidates that satisfy the same declared terminal outcome, validation obligations, evidence boundary, safety constraints, protected side effects, dependency authority, and execution-owner boundary. A candidate SHALL cite current equivalence evidence rather than copying those owner structures into an optimizer-owned outcome contract. When the complete declared candidate set contains exactly one candidate, the system SHALL still enforce every hard admissibility check but MAY select that sole eligible route without requiring cost vectors or Pareto comparison; it SHALL describe the route as un-compared and SHALL NOT claim a minimum, Pareto result, or cost superiority. Any malformed cost value or stale/missing reference that the caller did provide SHALL remain a finding. When more than one candidate is declared, the existing complete comparison requirements SHALL apply even if hard filtering leaves only one eligible candidate.

#### Scenario: Interleaved derived artifacts cause repeat work
- **WHEN** one eligible sequence writes documentation, inventories, installation projections, or release evidence before a later step invalidates their source identity while another equivalent sequence freezes source first and writes those artifacts once
- **THEN** the system assigns the interleaved sequence invalidated-output and repeated-write cost and selects the freeze-first sequence when its complete derived score is uniquely lower

#### Scenario: Caller preselects a higher-cost candidate
- **WHEN** the caller names an eligible candidate whose derived score is higher than another current hard-equivalent candidate
- **THEN** the system rejects that preference and returns the model-derived lower-cost candidate or a visible inconsistency rather than endorsing the supplied id

#### Scenario: Eligible candidates tie
- **WHEN** two current hard-equivalent candidates have the same complete derived score
- **THEN** the system exposes the tied candidate ids and does not silently claim that declaration order, lexical order, or an unsupported caller preference is optimal

#### Scenario: Measured cost input is incomplete
- **WHEN** a candidate in a declared multi-candidate set claims `comparison_basis=measured` but one declared step lacks comparable effort input or required cost evidence is not current
- **THEN** measured selection is blocked instead of treating missing cost as zero

#### Scenario: One declared candidate passes hard admissibility without ranking
- **WHEN** the complete declared candidate set contains exactly one candidate and all required hard outcome, evidence, safety, dependency, isolation, currentness, and owner checks pass
- **THEN** the system selects that candidate as the only admissible declared route without requiring a cost vector or running Pareto comparison
- **AND** the result makes clear that no cost comparison or minimum claim was produced

#### Scenario: Invalid supplied cost data remains rejected for one candidate
- **WHEN** the complete declared candidate set contains exactly one candidate and the candidate supplies a malformed cost, stale cost evidence, or an invalid reference
- **THEN** hard or reference validation reports the exact finding instead of ignoring the supplied invalid data

#### Scenario: A multi-candidate declaration does not use the single-candidate path
- **WHEN** the declared set contains more than one candidate but hard admissibility leaves only one eligible candidate
- **THEN** the system retains the declared multi-candidate comparison requirements and SHALL NOT use the single-candidate fast path

#### Scenario: Multiple-route reason has only one declaration
- **WHEN** the activation reason claims multiple equivalent routes but the complete declared set contains only one candidate
- **THEN** the system reports the contradiction and does not treat the incomplete declaration as a complete one-route universe
