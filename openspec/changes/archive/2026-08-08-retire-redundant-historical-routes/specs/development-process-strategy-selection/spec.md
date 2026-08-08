## MODIFIED Requirements

### Requirement: Strategy selection is multi-objective and bounded
The system SHALL expose the eligible candidates, each candidate's derived comparable score, the model-selected candidate, comparison basis, current comparison evidence, and selection rationale. Before preference, the system SHALL verify that the declared step sequence satisfies every dependency edge and SHALL derive invalidated-output, repeated-write, repeated-validation, coordination, side-effect-exposure, and comparable-effort components from current step/artifact bindings. `comparison_basis` SHALL be `qualitative` or `measured`; qualitative evidence, including bounded estimates or structural rules, MUST NOT be described as a measured minimum, and no result may claim an unrestricted global optimum. DPF MAY retain a bounded minimum claim only for a complete declared finite candidate set with current comparable measured inputs. A caller-supplied `selected_candidate_id` SHALL NOT make a higher-score route preferred; a score tie SHALL remain visible until current tie-break evidence selects one tied candidate.

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
- **WHEN** a candidate claims `comparison_basis=measured` but one declared step lacks comparable effort input or required cost evidence is not current
- **THEN** measured selection is blocked instead of treating missing cost as zero

### Requirement: Optimization composes diagnostic boundary and execution mode
The internal `strategy_selection` mode SHALL represent process choice through composable `diagnostic_boundary` values `targeted`, `declared_complete`, or `budgeted`, plus `execution_mode` values `sequential` or `safe_parallel`. Each candidate SHALL declare an acyclic dependency graph and an ordered step list that is a valid linearization of that graph. Hard invalidation, safety, dependency, or declared-order failures SHALL be universal stop conditions rather than selectable strategies; material new evidence SHALL stale every active decision rather than requiring an `adaptive` candidate. The six former policy names SHALL NOT remain a current successful vocabulary.

#### Scenario: Declared order violates a dependency
- **WHEN** a candidate lists a derived projection or release step before the source-freeze, self-audit, or validation step that its dependency graph requires
- **THEN** that candidate is ineligible even if its graph is acyclic and its terminal outcome label matches

#### Scenario: Independent work is proposed in parallel
- **WHEN** two steps have no dependency edge or shared mutable state but current dependency, state, side-effect, and execution-owner isolation evidence is incomplete
- **THEN** `safe_parallel` remains ineligible and sequential execution is retained

### Requirement: Optimizer complexity remains bounded
The current implementation SHALL add no public skill, route, commitment, or model owner; SHALL use at most five optimizer dataclasses in total and at most six public optimizer symbols; SHALL keep every hard-equivalence, derived-order, cost, tie, freshness, and closure gate; and SHALL leave zero current-runtime residuals for retired policy, rollout, Pareto, duplicate projection, alias, wrapper, or dual-reader surfaces. Source layout SHALL remain normally readable and SHALL NOT satisfy a mechanical line budget by placing independent field declarations, statements, or report arguments on the same physical line. A private formatting or source-line count is not a behavior authority.

#### Scenario: New ordering behavior reaches the former line ceiling
- **WHEN** complete dependency, artifact, cost, rationale, and tie behavior no longer fits the former 500-nonblank-line formatting limit without code compression
- **THEN** the implementation keeps one public route and the six-symbol surface while retaining ordinary readable formatting instead of code-golfing or adding a second owner

#### Scenario: Simplification adds another public optimizer path
- **WHEN** implementation introduces a new public route, review function, compatibility wrapper, or successful old vocabulary
- **THEN** architecture-reduction closure is blocked even if focused tests are green
