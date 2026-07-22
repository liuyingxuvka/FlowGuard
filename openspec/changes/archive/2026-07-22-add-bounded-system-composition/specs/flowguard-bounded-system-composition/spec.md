## ADDED Requirements

### Requirement: System composition artifacts are strict and fingerprint-bound
FlowGuard SHALL accept only the current `flowguard.portable_system.v1` definition shape and SHALL bind every included component to an exact current portable model id and fingerprint. A stable `PortableSystemDefinition` SHALL declare only semantic component references, declared dependencies, typed ports/bindings, shared-resource semantics, joint steps, state patterns, and system properties. A separate `SystemCompositionRequest` SHALL carry changed roots, selected properties, an optional requested subset, environment guarantee tokens, and a finite bound so every input that can change the verdict participates in request identity. The derived `PortableSystemSlice` SHALL carry the dependency-closed included/excluded sets and its own fingerprint. None of these records SHALL embed a second copy of component models.

#### Scenario: Component fingerprint is current
- **WHEN** every supplied component id and fingerprint matches its system reference
- **THEN** system validation may continue with distinct canonical definition, request, and derived-slice fingerprints

#### Scenario: Component fingerprint is stale
- **WHEN** a supplied component has the expected id but a different fingerprint
- **THEN** the system check returns blocked before joint-state compilation

#### Scenario: Old or ambiguous schema is supplied
- **WHEN** a system artifact uses an old version, alias field, unknown field, or parallel compatibility shape
- **THEN** validation returns invalid and no fallback reader runs

### Requirement: Affected system slices are dependency-closed
FlowGuard SHALL derive the exact affected slice within the system definition's declared typed graph from request changed roots through declared joint steps, event bindings, queue/resource/clock/fault components, shared readers/writers, state patterns, and selected system properties. Unknown or unresolved declared dependencies and omitted required closure members MUST block the executable-composition claim. The report SHALL preserve the discovery-evidence identity and state that undeclared code/runtime dependencies and unknown unknowns are outside this proof boundary.

#### Scenario: Unrelated component is excluded
- **WHEN** a component has no declared step, binding, resource, pattern, property, or dependency path from the changed roots
- **THEN** the affected slice excludes it and records the exclusion in the slice identity

#### Scenario: Shared resource sibling is required
- **WHEN** an included model reads or writes a resource whose finite resource component is also used by a sibling model
- **THEN** the slice includes the resource component and every affected sibling needed by the declared property

#### Scenario: Dependency is unresolved
- **WHEN** the artifact contains an unresolved dependency id or the requested subset omits a required closure member
- **THEN** the check returns blocked and does not treat the unknown relation as no impact

### Requirement: Joint steps give model relations executable semantics
FlowGuard SHALL compile one-reference steps as ordinary interleavings and multi-reference steps as explicit atomic transitions across distinct component models. Queue delivery, duplicate/drop behavior, retry, resource access, commit/outbox boundaries, clocks, faults, acknowledgements, and compensation SHALL be represented by finite component transitions and exact step rules rather than inferred from prose or token names.

#### Scenario: Independent steps interleave
- **WHEN** two one-reference steps are enabled in different components
- **THEN** the compiled graph contains each reachable ordering unless the resulting state is identical

#### Scenario: Declared atomic step is indivisible
- **WHEN** one system step references enabled transitions from two distinct components
- **THEN** the compiled graph applies both target-state changes in one transition and exposes the atomicity rationale

#### Scenario: Component transition is uncovered
- **WHEN** an included component transition appears in no system step
- **THEN** validation blocks instead of silently deleting that behavior from the joint graph

### Requirement: Typed bindings preserve identity and delivery boundaries
Every event binding SHALL identify exact producer and consumer ports, event/schema identities, and any delivery, ordering, queue, identity, persistence, or compatibility semantics that affect enabled steps, generated state/transitions, slice closure, or a deterministic invalid/blocked decision. Non-semantic code/runtime targets or provenance MAY be carried for trace projection but SHALL NOT become mandatory model semantics. FlowGuard MUST NOT accept `exactly_once` as an unexplained primitive.

#### Scenario: At-least-once delivery is modeled
- **WHEN** a binding declares at-least-once delivery and names finite queue delivery/redelivery transitions
- **THEN** those transitions can participate in distinct compiled schedules

#### Scenario: Business identity is missing
- **WHEN** a binding declares identity-sensitive deduplication, retry, or correlation but lacks the required exact mapping
- **THEN** the system artifact is invalid before exploration

#### Scenario: Exactly-once is asserted as a primitive
- **WHEN** a binding declares exactly-once without modeled delivery, identity, deduplication, and transaction transitions
- **THEN** current-schema validation rejects the declaration

### Requirement: System properties have one owner and compile to canonical portable obligations
Each required system safety or temporal property SHALL name exactly one primary owner and SHALL refer to declared state patterns and, for fairness, declared system steps. Safety, eventuality, bounded eventuality, terminal progress, and weak fairness SHALL compile to the corresponding existing portable invariant or temporal obligation.

#### Scenario: Cross-model forbidden state is reachable
- **WHEN** the joint graph reaches a state matching a forbidden system pattern
- **THEN** the canonical portable checker fails the owning invariant and returns a mapped system trace

#### Scenario: Cross-model eventuality has a target-avoiding cycle
- **WHEN** a declared eventual target can be avoided by a reachable dead end or fair cycle
- **THEN** the canonical portable checker fails the temporal obligation

#### Scenario: Property owner is missing
- **WHEN** a required system property lacks one non-empty owner id
- **THEN** the system artifact cannot support an executable-composition pass

### Requirement: Executable composition preserves one checker authority
The system check SHALL run and report component-local checks, existing assumption/guarantee composition, affected-slice compilation, and at most one eligible `check_portable_model()` invocation for the system stage. A complete compiled graph is eligible once. A truncated exploration is eligible only when the compiler has selected a reachable forbidden-state safety witness graph for confirmation by the canonical checker; the compiler itself SHALL NOT issue the semantic verdict. A token-level composition pass SHALL NOT be reported as an executable system pass.

#### Scenario: Local and token checks pass but system property fails
- **WHEN** every component is locally green and assumption/provider closure is green but a compiled system property is violated
- **THEN** executable composition returns fail with `local_green=true`, `contract_composition_green=true`, and `system_green=false`

#### Scenario: Component is blocked
- **WHEN** a selected component local check is blocked by its finite-state bound
- **THEN** executable composition returns blocked and does not downgrade the condition to an ordinary semantic failure

### Requirement: Incomplete exploration fails closed
FlowGuard SHALL use a deterministic joint-state limit and SHALL report any unexplored frontier as truncation. A reachable forbidden-state safety witness confirmed by the canonical checker remains a failure with residual truncation risk. Dead ends, cycles, eventuality, bounded-eventuality, terminal-progress, or fairness findings require a complete graph; when the graph is truncated they MUST return blocked. An otherwise clean truncated graph MUST return blocked and MUST NOT be passed to downstream consumers as complete evidence.

#### Scenario: Clean search reaches the state bound
- **WHEN** the compiler reaches its joint-state limit while enabled unexplored successors remain
- **THEN** the report returns blocked with the bound, explored-state count, and frontier identity

#### Scenario: Violation is found before truncation
- **WHEN** a forbidden state is reached within the explored prefix even though another frontier would exceed the bound
- **THEN** the checker is invoked once on the selected reachable witness graph and, if it confirms the invariant violation, the report returns fail with the concrete witness and separately records truncation residual risk

#### Scenario: Temporal finding appears in a truncated prefix
- **WHEN** an explored prefix contains a dead end, target-avoiding cycle, or apparent fairness violation but another frontier remains unexplored
- **THEN** the report returns blocked and does not promote that incomplete-graph observation to temporal failure

### Requirement: Counterexamples are minimal and actionable
The system report SHALL preserve the shortest available joint-step trace and SHALL map every step to component model ids, component transition ids, before/after component states, related binding/resource ids, and declared code/runtime target ids. It SHALL expose the involved model subset separately from the full affected slice.

#### Scenario: Emergent failure has a mapped witness
- **WHEN** executable composition finds a system property violation
- **THEN** the report identifies the owning property, stable system step ids, exact component transitions, involved model ids, and real-code/runtime targets when declared

#### Scenario: Input ordering changes only presentation order
- **WHEN** the same components and system rows are supplied in a different array order
- **THEN** canonical system, slice, compiled-model, and report identities remain unchanged

### Requirement: Public API and CLI expose the same system-composition path
FlowGuard SHALL expose one public system-composition API cohort and one `portable-system-check` CLI command. Both SHALL load exact current artifacts, invoke the same canonical implementation, preserve pass/fail/blocked/invalid status, and emit either canonical JSON or a concise human projection.

#### Scenario: CLI checks one system artifact
- **WHEN** a user supplies a system file and every referenced component model file
- **THEN** the command returns the same status, identities, evidence boundary, and counterexample as the Python API

#### Scenario: Component file is missing or extra
- **WHEN** a required component is absent or a supplied component is not referenced by the exact system definition
- **THEN** the command returns invalid visibly rather than discovering an alternate model catalog

### Requirement: Emergent Integration Benchmark proves the intended delta
FlowGuard SHALL include payment/order retry identity, permission-revocation/cache, and deletion/index/export benchmark families. Each family SHALL include local-green components, token-green bad composition, executable system failure, minimal trace, repaired system pass, missing-semantics blocker, and truncated-search blocker.

#### Scenario: Bad and repaired variants are compared
- **WHEN** the benchmark runs one family
- **THEN** the bad variant fails only at executable composition, the repaired variant passes, and malformed/truncated variants remain blocked

#### Scenario: Benchmark only proves bounded declared cases
- **WHEN** all benchmark cases pass their expected outcomes
- **THEN** the claim boundary reports coverage of those finite families and does not claim arbitrary future system correctness
