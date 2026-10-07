## ADDED Requirements

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
