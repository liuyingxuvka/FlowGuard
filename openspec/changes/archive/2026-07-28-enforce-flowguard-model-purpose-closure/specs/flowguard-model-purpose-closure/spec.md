## ADDED Requirements

### Requirement: Concrete model instances declare purpose before construction
FlowGuard SHALL require every new or materially changed concrete model instance to freeze one task-specific purpose declaration before candidate construction. The declaration SHALL name one stable model-instance id, one task-intent id, a reviewable guarded purpose, one or more finite protected-failure ids, and a claim boundary. A reusable model type SHALL NOT be restricted to one permanent protected failure.

#### Scenario: One instance protects several failures
- **WHEN** the AI declares two concrete failure ids for the current model instance before building it
- **THEN** FlowGuard preserves both ids under the same task-specific declaration and requires closure for both

#### Scenario: Same model type is reused for another task
- **WHEN** a later task creates another instance of the same model type for a different guarded purpose
- **THEN** FlowGuard requires a new instance declaration and does not inherit a fixed permanent purpose from the reusable type

#### Scenario: Purpose is added only after candidate construction
- **WHEN** the candidate exists without a frozen prior declaration
- **THEN** FlowGuard blocks model-purpose closure until the current candidate is re-adopted under a declaration and revalidated

### Requirement: Every protected failure has native good and bad proof coverage
Each model-purpose closure SHALL bind at least one native known-good case and exactly one declared native known-bad case for every protected-failure id. Every case SHALL resolve to the declared native oracle owner and current terminal evidence for the same model instance and request identity.

#### Scenario: Two failures have complete native proof
- **WHEN** both protected failures have their own known-bad case, share or separately name a valid native oracle, and the instance has a passing known-good case
- **THEN** the proof coverage gate can pass for the declared boundary

#### Scenario: A failure has no bad case
- **WHEN** one protected-failure id lacks a matching known-bad case or its oracle/evidence identity is stale
- **THEN** the whole model-purpose closure is blocked and the missing failure remains visible

### Requirement: Current manifest entries bind purpose to exact candidate and runner identities
The canonical model-regression manifest SHALL directly store the current purpose closure for every registered regression instance and SHALL bind the declaration, model content, runner content, native proof inventory, and claim boundary. Missing, duplicate, placeholder, stale, disconnected, or non-current bindings SHALL fail manifest audit before model execution can support a protection claim.

#### Scenario: All current instances are fully bound
- **WHEN** every registered entry has a unique current instance declaration and exact model/runner fingerprints
- **THEN** manifest audit can continue to model execution

#### Scenario: Runner changes after closure
- **WHEN** a bound runner file changes without a new current closure
- **THEN** manifest audit reports stale purpose evidence and blocks the affected instance

### Requirement: Purpose closure has one non-optional lifecycle
FlowGuard SHALL expose exactly one lifecycle: declare, freeze, build or materially update, bind candidate, execute native good/bad proofs, and close. It SHALL NOT expose a selectable mode, bypass, fallback reader, dual manifest, or alternate success route.

#### Scenario: Caller omits the declaration stage
- **WHEN** a caller attempts to run or register a materially changed model without a frozen declaration
- **THEN** the canonical route fails visibly rather than selecting a weaker mode

### Requirement: Current inventory migration does not claim historical order
The existing checked-in regression instances SHALL be directly re-adopted under current declarations and revalidated. The resulting evidence SHALL prove current candidate-purpose closure only and SHALL NOT claim that the purpose was declared before the historical first creation of those models.

#### Scenario: Existing model is adopted
- **WHEN** a pre-existing checked-in model receives a current declaration and passes current native good/bad proof
- **THEN** FlowGuard may claim current adopted closure within the declared boundary while keeping historical creation order outside the claim
