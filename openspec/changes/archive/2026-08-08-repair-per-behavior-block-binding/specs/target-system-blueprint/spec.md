## ADDED Requirements

### Requirement: One model owner preserves block-local child contracts
When one model owner governs several independently observed behavior surfaces, FlowGuard SHALL preserve each surface as its own behavior block with an exact portable binding, one good case, one boundary case, and only the protected-failure cases explicitly scoped to that surface. The owner-level model identity and shared semantics SHALL remain the parent authority and SHALL NOT substitute for any child's input, output, state, effect, implementation, model-member, failure, case, coverage owner, or execution binding. A module or class aggregate SHALL NOT become an independent behavior block solely because it contains those children or matches the owner path.

#### Scenario: One owner governs two different function shapes
- **WHEN** one model owner governs two behavior surfaces with different input, output, or state fields
- **THEN** each behavior block SHALL carry a portable binding whose fields exactly match that surface
- **AND** neither block SHALL inherit the other block's field mapping

#### Scenario: Sibling block cases are present
- **WHEN** an owner declares cases for two valid sibling behavior blocks
- **THEN** FlowGuard SHALL partition and evaluate the cases by their exact behavior block
- **AND** a case belonging to one sibling SHALL NOT be rejected merely because another sibling is being evaluated

#### Scenario: Case targets an unowned block
- **WHEN** an owner's case names a behavior block outside the owner's independently observed behavior surface set
- **THEN** FlowGuard SHALL reject the declaration as an ownership-boundary violation
- **AND** filtering the case out SHALL NOT restore readiness

#### Scenario: Parent failure has one exact child edge
- **WHEN** an owner has several behavior surfaces and one protected failure is explicitly bound to one surface
- **THEN** only that surface SHALL carry the failure member and corresponding bad case
- **AND** sharing the owner SHALL NOT copy the failure to sibling surfaces
- **AND** a parent test result or receipt SHALL NOT be copied as sibling execution evidence

#### Scenario: Parent model exposes a composite behavior surface
- **WHEN** a provider supplies one exact observed composite surface with an independent input, state/effect, output, completion, and semantic contract for the owner-level workflow
- **THEN** parent transitions and protected failures MAY bind to that composite block
- **AND** detailed child blocks SHALL remain separately bound without inheriting the composite member set

#### Scenario: Module or class merely contains child behavior
- **WHEN** a module or class matches an owner path or contains behavior-bearing functions but has no independent observed composite contract
- **THEN** the aggregate SHALL remain a supporting surface bound to the exact model owner
- **AND** FlowGuard SHALL NOT fabricate an aggregate behavior block, cases, failures, coverage, or execution evidence

### Requirement: The complete implementation map distinguishes behavior from support
FlowGuard SHALL retain every independently discovered current implementation surface in the target code map while requiring independent behavior contracts only for surfaces classified by the active observation provider as callable behavior, entrypoints, state/effect/dynamic writers, or explicit workflow transitions. A supporting disposition SHALL preserve one exact behavior/model owner and SHALL NOT remove the surface from the DNA.

#### Scenario: Structural helper remains in the DNA
- **WHEN** an observation provider discovers a module, class, nested function, or pure private helper that is not independently behavior-bearing
- **THEN** the surface SHALL remain in the implementation inventory with one exact supporting owner relation
- **AND** FlowGuard SHALL NOT fabricate a separate good, boundary, and bad case set merely because the structural surface exists

#### Scenario: Hidden writer cannot be demoted for size
- **WHEN** a private or nested surface performs an observed state write, external effect, dynamic dispatch, entry transition, or other provider-declared behavior
- **THEN** it SHALL remain in the behavior denominator
- **AND** a size or performance limit SHALL NOT authorize demotion to supporting
