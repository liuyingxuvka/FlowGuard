## Purpose

Define how every new or materially changed FlowGuard model proves that its own execution path is necessary, bounded, evidence-current, and no more complex than the licensed claim supports.

## Requirements

### Requirement: Every affected model receives a path-quality decision
FlowGuard SHALL produce one path-quality decision for every new or materially changed model before that model enters current DNA. The decision SHALL bind the model, purpose, intent, obligation, provider, dependency, code, test, oracle, and evidence identities it consumes and SHALL remain scoped to the affected model boundary.

#### Scenario: New model is proposed for current DNA
- **WHEN** a new model is proposed for current observed authority
- **THEN** FlowGuard requires a current path-quality decision for that exact model identity
- **AND** absence of a result remains visible rather than inheriting a parent, sibling, prior revision, or installed projection result

#### Scenario: Existing model changes materially
- **WHEN** a model's states, transitions, FunctionBlocks, fields, effects, errors, interfaces, obligations, intent, providers, dependencies, bindings, or oracles change
- **THEN** its prior path-quality result becomes stale
- **AND** only the affected model and topology-required neighbors are reopened

### Requirement: Ordinary path review is lightweight and bounded
Every affected model SHALL receive a lightweight structural review for unreachable states or transitions, duplicate guards or effects, behavior-irrelevant state, pass-through FunctionBlocks, unconsumed intermediate outputs, repeated identical validation, duplicate current owners, and no-progress loops. When the review finds one clear path and no accepted deep trigger, FlowGuard SHALL return `single_clear_path` without expanding deep candidates or materializing a large detail payload.

#### Scenario: One clear ordinary path
- **WHEN** the lightweight review finds no qualifying structural issue and no deep trigger
- **THEN** the result is `single_clear_path`
- **AND** ordinary AI guidance consumes only its compact summary and evidence fingerprint

#### Scenario: Lightweight review finds a structural issue
- **WHEN** the review finds an unreachable, duplicate, irrelevant, pass-through, unconsumed, repeated-validation, duplicate-owner, or no-progress element
- **THEN** the result records the exact element and obligation boundary
- **AND** it triggers bounded resolution or remains `unresolved` rather than silently accepting the model

### Requirement: Deep review is conditional and finite
Deep path review SHALL run only when explicitly requested or when current evidence shows multiple hard-equivalent routes, material state or branch growth, duplicated or unreachable structure, repeated work, a path-design model miss, a missing necessity witness, or a high-cost or release-critical model boundary. It SHALL compare only a declared finite candidate set under declared rewrite rules.

#### Scenario: No deep trigger exists
- **WHEN** the lightweight result is current and no explicit or evidence-derived deep trigger exists
- **THEN** FlowGuard SHALL NOT run a reconstruction exercise, enumerate alternative programs, or require deep optimization ceremony

#### Scenario: Deep trigger exists
- **WHEN** a deep trigger is current
- **THEN** the result names the trigger, finite candidate ids, rewrite-rule ids, comparison boundary, and unresolved gaps
- **AND** it SHALL NOT imply that unenumerated programs were searched

### Requirement: Hard semantics precede cost comparison
FlowGuard SHALL compare path cost only after candidates preserve the same accepted inputs, outputs, state and field transitions, protected errors, side effects, ordering, retry, timeout, progress, permissions, parent/child interfaces, intent, authority, oracles, and evidence obligations. A mismatch SHALL be classified as an intentional behavior change or unresolved comparison, not as a cheaper equivalent path.

#### Scenario: Candidate changes a protected effect
- **WHEN** a candidate removes or reorders work in a way that changes a protected state, output, error, effect, permission, or evidence obligation
- **THEN** the candidate is ineligible for equivalent-path cost ranking
- **AND** any desired change remains a normative target until implemented and evidenced

#### Scenario: Candidates are hard-semantically equivalent
- **WHEN** every hard semantic dimension matches under current executable evidence
- **THEN** FlowGuard MAY compare their declared cost vectors within the finite boundary

### Requirement: Cost remains a vector and conclusions remain bounded
Path cost SHALL remain a vector covering steps; states, transitions, and branches; repeated reads, writes, and validation; invalidation and rework; coordination; side-effect exposure; latency; token or payload materialization; runtime resources; and maintenance complexity. FlowGuard SHALL report only `single_clear_path`, `preferred_within_candidates`, `non_dominated_within_boundary`, `minimum_within_exhausted_finite_set`, `locally_irreducible_under_declared_rewrites`, or `unresolved` and SHALL NOT claim an unrestricted global optimum.

#### Scenario: Candidates trade off different costs
- **WHEN** no hard-equivalent candidate dominates the others across current comparable dimensions
- **THEN** FlowGuard reports `non_dominated_within_boundary` or `unresolved` with the exact trade-offs
- **AND** it SHALL NOT hide incomparable units in an unexplained scalar total

#### Scenario: Finite measured set has one minimum
- **WHEN** the named candidate set is proven complete for the declared boundary, every required cost input is current and comparable, and one candidate is uniquely minimum within that set
- **THEN** FlowGuard MAY report `minimum_within_exhausted_finite_set`
- **AND** the report still disclaims global optimality

#### Scenario: Declared rewrites cannot reduce the model further
- **WHEN** every declared rewrite rule has been applied or rejected with current hard-semantic evidence and no accepted rewrite reduces the model within the boundary
- **THEN** FlowGuard MAY report `locally_irreducible_under_declared_rewrites`
- **AND** it names the exact rule set and evidence identity

### Requirement: Every retained model element has a necessity witness
Every retained state, transition, branch, FunctionBlock, field, effect, and validation step SHALL have one necessity witness naming the active obligation and counterexample it protects. Missing, duplicate, stale, or circular witnesses SHALL remain unresolved.

#### Scenario: Retained element protects a unique case
- **WHEN** removing an element violates a current obligation under an executable counterexample
- **THEN** the witness records the element, obligation, oracle, counterexample, and current evidence identity

#### Scenario: Retained element has no witness
- **WHEN** no unique active obligation or counterexample requires an element
- **THEN** the element becomes a contraction candidate or an unresolved row
- **AND** mere age, authorship, or existing code presence SHALL NOT count as necessity

### Requirement: Path-quality evidence is compact and freshness-bound
Current model authority SHALL carry only the compact result, trigger state, subject fingerprint, detailed-evidence fingerprint, conclusion, and unresolved ids needed by parents and ordinary consumers. Detailed candidates, rewrite traces, cost rows, and necessity witnesses SHALL remain referenced evidence loaded only for a triggered deep review or claim.

#### Scenario: Parent consumes a current child summary
- **WHEN** a parent needs to aggregate path quality from affected children
- **THEN** it consumes compact child summaries and fingerprints
- **AND** it does not copy every deep candidate or witness into the parent payload

#### Scenario: Consumed identity changes
- **WHEN** a bound model, purpose, intent, obligation, provider, dependency, code, test, oracle, or evidence identity changes
- **THEN** the result is stale and cannot support current activation

### Requirement: Observed truth and normative improvement remain separate
An observed model SHALL continue to represent the current implementation path faithfully even when that path is inefficient. A safer or cheaper intentional path SHALL remain a normative target until the implementation, model-code-test bindings, affected topology, and current evidence match it.

#### Scenario: Better path is not yet implemented
- **WHEN** a path-quality review proposes a behavior-changing improvement
- **THEN** current observed authority keeps the real implemented path
- **AND** the proposal is recorded only in the normative target lane

### Requirement: Path quality reuses existing FlowGuard owners
ModelMaturation SHALL own single-model path quality; ModelMesh SHALL own cross-model topology; Architecture Reduction SHALL own mapped implementation contraction; DevelopmentProcessFlow SHALL own work and validation order; and Model-Test Alignment and TestMesh SHALL own executable binding and evidence. FlowGuard SHALL add no public path-optimizer skill, route, CLI command, compatibility reader, reconstruction workflow, or second current authority pointer.

#### Scenario: FlowGuard audits its own models
- **WHEN** FlowGuard performs release-bound self-maintenance
- **THEN** it uses the same model-path-quality capability and ownership boundaries used for any target project
- **AND** no self-only optimizer or special reconstruction branch is accepted
