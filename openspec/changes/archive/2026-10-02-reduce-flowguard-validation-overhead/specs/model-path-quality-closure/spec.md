## MODIFIED Requirements

### Requirement: Deep review is conditional and finite
Deep path review SHALL run only when explicitly requested or when current evidence shows multiple hard-equivalent routes, material state or branch growth, duplicated or unreachable structure, repeated work, a path-design model miss, a necessity-witness gap within an already triggered reduction or candidate-comparison boundary, or a high-cost or release-critical model boundary. The absence of per-element necessity witnesses outside such an explicit boundary SHALL NOT by itself trigger deep review. Deep review SHALL compare only a declared finite candidate set under declared rewrite rules.

#### Scenario: No deep trigger exists
- **WHEN** the lightweight result is current and no explicit or evidence-derived deep trigger exists within the declared review boundary
- **THEN** FlowGuard SHALL NOT run a reconstruction exercise, enumerate alternative programs, or require deep optimization ceremony
- **AND** it SHALL NOT require per-element necessity witnesses for ordinary current model acceptance

#### Scenario: Deep trigger exists
- **WHEN** a deep trigger is current
- **THEN** the result names the trigger, finite candidate ids, rewrite-rule ids, comparison boundary, and unresolved gaps
- **AND** it SHALL NOT imply that unenumerated programs were searched

#### Scenario: Witness gap is outside a deep boundary
- **WHEN** a model has no per-element necessity witness but no explicit reduction or candidate-comparison boundary is active
- **THEN** the missing witness alone SHALL NOT block the ordinary lightweight path-quality result

#### Scenario: Witness gap is inside an explicit deep boundary
- **WHEN** an explicit reduction or candidate-comparison review identifies a missing, stale, duplicate, or circular witness for an element it evaluates
- **THEN** that review SHALL keep the affected row unresolved until the witness or an evidence-backed contraction disposition is supplied

### Requirement: Every retained model element has a necessity witness
For an explicitly triggered deep reduction or candidate-comparison boundary, every retained state, transition, branch, FunctionBlock, field, effect, or validation step included in that comparison SHALL have a necessity witness naming the active obligation and counterexample it protects. Ordinary lightweight review and accepted current model status SHALL NOT require a witness for every element. Missing, duplicate, stale, or circular witnesses within the declared deep boundary SHALL remain unresolved.

#### Scenario: Retained element protects a unique case
- **WHEN** removing an element inside the declared deep boundary violates a current obligation under an executable counterexample
- **THEN** the witness records the element, obligation, oracle, counterexample, and current evidence identity

#### Scenario: Retained element has no witness
- **WHEN** no unique active obligation or counterexample requires an element included in an explicit deep comparison
- **THEN** the element becomes a contraction candidate or an unresolved row
- **AND** mere age, authorship, or existing code presence SHALL NOT count as necessity

#### Scenario: Ordinary current model has no per-element witnesses
- **WHEN** the ordinary lightweight path-quality review is current and no explicit deep reduction or candidate-comparison boundary is active
- **THEN** FlowGuard SHALL permit the ordinary result without generating or requiring per-element witness rows

