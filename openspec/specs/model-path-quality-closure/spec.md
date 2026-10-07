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
### Compact direct-current boundary (2026-09-22)

The compact closeout keeps one FlowGuard skill and exactly three public operations: `read`, `change`, and `release`. A selected subject loads only its concrete protocol and explicitly named accepted model or evidence. Retired commands, profiles, satellite entrypoints, forwarding files, aliases, compatibility readers, migrations, and fallback routes are removed from the current surface; they are not interpreted or selected as a secondary success path.

#### Scenario: Missing or retired selection blocks

- **WHEN** a request has no unique current subject, names a retired entry, or omits a required accepted identity
- **THEN** FlowGuard reports a typed blocker with zero producer and zero write effects; it does not widen the scope or try another route.

### Requirement: Architectural objectives come from explicit current normative sources
Architectural objectives SHALL be admitted only from exactly one strict JSON `flowguard-architecture-objectives` fenced document in an existing independently verified active normative source. The document SHALL contain only `schema` and `objectives`, with schema `flowguard.architecture_objective_source.v1`. Each typed objective SHALL contain exactly `objective_id`, `required`, `model_ids`, `responsibility_ids`, `applicable_input_class_ids`, `constraint_kind`, `constraint_values`, `native_owner_id` and `protected_failure_ids`; its id SHALL be expressly admitted by the contribution's existing `target_invariant_ids`. Source, owner, contribution and complete-view identities SHALL derive from verified authority rather than objective payload assertions. Duplicate keys, unknown fields, invalid UTF-8, nonfinite values, multiple documents, absent admitted objectives and source drift SHALL block admission.

#### Scenario: Generic requirements contain no current self objective
- **WHEN** an active source has no admitted architecture objective ids and its document declares an empty objective list
- **THEN** it contributes no default centralization or backend objective
- **AND** generic capability and native protection obligations remain required

#### Scenario: A small request intersects a larger required objective
- **WHEN** a required objective spans models or input classes beyond the selected request
- **THEN** evaluation preserves its entire declared scope and resolves exact required members and typed neighbors
- **AND** missing scope facts block completion instead of narrowing the objective to the request

#### Scenario: WorkContext source bytes are unavailable
- **WHEN** an admitted objective names an already verified native artifact but its exact source bytes or identity are unavailable
- **THEN** admission reports the source gap without constructing a document from summary prose

### Requirement: Objective constraints are typed and evidence-bound
Objective evaluation SHALL support finite `unique_owner`, `allowed_layers`, `shared_mechanism` and `cost_bound` conditions against exact observed facts and complete effective intent. Owner and layer predicates SHALL use scoped current primary responsibilities. Shared mechanism SHALL require real current canonical-primary delegation closure. Explicit cost bounds SHALL use independently admitted current measured vector dimensions, units and measurement evidence; missing admission SHALL remain cost_measurement_missing, never zero. Ordinary understanding SHALL have no default cost bound. Conflicting accepted goals SHALL use existing intent-conflict handling.

#### Scenario: Explicit layer objective disagrees with faithful current facts
- **WHEN** a required allowed-layer objective permits a service writer but current evidence places that responsibility in the UI
- **THEN** observation retains the actual writer and records the unmet target
- **AND** any relocation remains a normative candidate until implemented and evidenced

#### Scenario: Cost evidence is missing
- **WHEN** a cost-bound objective has no current measurement for its named dimension and unit
- **THEN** the objective remains unknown and cannot license a lower-cost claim

### Requirement: Improvement suggestions remain finite and authenticated
Path-quality improvement suggestions SHALL bind observed and complete-intent identities, objective ids, affected element ids, candidate lane, hard-semantic differences, retained obligations, declared rewrite rules, required native checks and expected cost dimensions. Only independently evidenced hard-equivalent candidates SHALL enter cost ranking. Behavior-changing candidates SHALL remain normative targets. Detail SHALL be authenticated by the existing result detail fingerprint and written immutably before head acceptance, without another producer or current pointer.

#### Scenario: Duplicate responsibilities suggest a bounded rewrite
- **WHEN** verified overlapping-context duplicate responsibility supports delegation or shared extraction
- **THEN** the detail records a finite candidate direction and required next-owner checks
- **AND** it does not claim implemented sharing, required improvement completion, an unrestricted optimum or a measured speed percentage

### Requirement: Gap projections preserve current persistent contracts
Observation and improvement projections SHALL derive from existing finding and unresolved ids without adding persistent contribution, mapping, result, revision, index or shard fields. Explicit unfinished structural or objective gaps SHALL remain visible improvement gaps only when observation evidence is verified. Unknown codes, stale facts, inventory mismatch, missing providers or grounding, unknown context, intent drift, native hard failures, oracle failures, nonterminal owners and cleanup uncertainty SHALL remain observation blockers. Current strict readers SHALL continue to load existing accepted wire records without rewriting, converters, aliases or bootstrap.

#### Scenario: An unknown finding enters a result
- **WHEN** a finding has no exact admitted improvement classification
- **THEN** the derived observation projection remains blocked
- **AND** reading it preserves the stored version, fields and fingerprint

#### Scenario: Native exporter produces pure declaration
- **WHEN** the original native episode exports declared facts
- **THEN** it exports once before raw evidence identities are frozen and does not embed that episode's future receipt identity
- **AND** the consumer admits semantic evidence only after the original raw bytes and immutable receipt are terminal without mutating the declaration or rerunning the producer

### Requirement: Optional numerical goals do not govern ordinary understanding
No default cost, token, model-count, size or iteration ceiling SHALL determine functional understanding or success. An explicitly admitted cost_bound SHALL remain unresolved as cost_measurement_missing without independent measurement admission; bare scalar, semantic review and self-declared vector SHALL NOT satisfy it. Existing finite PathCostVector comparisons retain exact units/inputs.

#### Scenario: Unrelated semantic review accompanies invalid or low scalar
- **WHEN** NaN, negative, boolean or finite scalar lacks independent measurement admission
- **THEN** the explicit goal is retained and blocked with cost_measurement_missing, with no satisfaction or cost suggestion

### Requirement: Current compromises are visible without waiving goals
A strict flowguard-architecture-compromises fence in the same verified current intent source SHALL name actual contribution/goals/elements/contexts, functional impact, rationale, next owner and source-bound revisit trigger. Missing/conflicting provenance SHALL remain needs_evidence. Deferred annotation SHALL NOT waive required targets; only legitimate current supersession/refinement changes them.

#### Scenario: Deferred duplicate implementation retains an unmet required target
- **WHEN** current source explains temporary retention of two implementations and a required sharing goal remains open
- **THEN** the compromise is visible and the required improvement stays non-pass

### Requirement: Authenticated functional objectives
Functional objectives SHALL require current effective intent, exact CodeContract and native binding identities, independent responsibility semantics and actual observed functional status. A compromise SHALL reference an admitted outcome and a real condition anchor.

#### Scenario: A native check passes but the required observed behavior is blocked
- **WHEN** a native check passes but the required observed behavior is blocked
- **THEN** The functional objective remains mismatched and cannot be closed by that native pass.

## Current self architecture objective source

This is the sole strict objective document for the existing FlowGuard self normative source. Empty objectives declare no additional self centralization target; the generic capability and required native protections above remain obligations. Temporary finite fixture objectives are test-only independent sources and never enter this current self document or contribution inventory.

```flowguard-architecture-objectives
{"schema":"flowguard.architecture_objective_source.v1","objectives":[]}
```
