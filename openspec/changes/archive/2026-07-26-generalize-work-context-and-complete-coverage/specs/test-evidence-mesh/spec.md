## ADDED Requirements

### Requirement: Test evidence binds the complete coverage inventory
Before broad behavior confidence, TestMesh SHALL bind its parent gate to the exact current coverage inventory identity, revision, and fingerprint produced by the shared behavior reconciliation. Every required test or evidence identity derived from a `modeled` or `delegated` expected item SHALL have exactly one native child owner and an explicit current state. A caller-selected green subset SHALL NOT establish complete evidence coverage.

#### Scenario: A green subset omits a required child
- **WHEN** all selected tests pass but the bound coverage inventory requires an additional test or evidence child
- **THEN** TestMesh SHALL keep the parent gate incomplete and SHALL identify the missing child owner

#### Scenario: The coverage inventory changes
- **WHEN** the expected inventory or any modeled, delegated, or scoped disposition changes after a TestMesh result
- **THEN** the affected TestMesh parent and child evidence SHALL become stale according to their declared dependency edges

### Requirement: Coverage dispositions determine evidence ownership
TestMesh SHALL preserve the evidence consequence of every shared coverage disposition. `modeled` items SHALL bind to current model and test evidence, `delegated` items SHALL bind to the exact current evidence owned by the delegated native route, and `scoped` items SHALL remain visible with their boundary and SHALL NOT be projected as passed tests.

#### Scenario: A delegated item lacks native evidence
- **WHEN** an expected item is delegated to a specialist inventory but its required native evidence is missing, stale, skipped, blocked, or not run
- **THEN** TestMesh SHALL preserve that state and SHALL NOT synthesize a passing child from the delegation itself

#### Scenario: An item is intentionally scoped
- **WHEN** an expected item has a valid scoped disposition
- **THEN** TestMesh SHALL retain the scope boundary in the parent accounting without manufacturing an executed test result

### Requirement: Work context and provider status are not test evidence
WorkContext artifacts, provider status, proposals, plans, tasks, checkboxes, and completion markers SHALL be treated as read-only planning context rather than test execution evidence, execution-owner receipts, or reuse authority. An actual provider-native validator MAY appear as ordinary TestMesh evidence only when it ran under a separately declared native execution owner with exact terminal identity, inputs, and freshness.

#### Scenario: A provider task list is complete
- **WHEN** OpenSpec, Spec Kit, Superpowers, a declared-file profile, or another provider reports that all planning tasks are complete
- **THEN** TestMesh SHALL NOT mark any FlowGuard model, test, replay, or native validation child as passed solely from that status

#### Scenario: A provider-native validator executes
- **WHEN** a provider-native validator runs under its own declared execution owner and produces current terminal evidence
- **THEN** TestMesh MAY reference that evidence as an ordinary native child while WorkContext itself remains non-executing and receipt-free

## REMOVED Requirements

### Requirement: TestMesh governs spec-check receipt children
**Reason**: Provider-specific spec-check receipt children belonged to the retired Spec Work Package execution bridge. Provider-neutral WorkContext has no provider execution, receipt, resume, cache, or terminal-state authority.

**Migration**: Represent an actually executed provider-native validation as an ordinary TestMesh child owned by that provider's native validator. Treat provider artifacts and status as context only.

#### Scenario: WorkContext artifacts enter TestMesh planning
- **WHEN** a requirement, design, plan, task, or provider status is available through WorkContext
- **THEN** TestMesh SHALL NOT create a provider-specific spec-check receipt child from that contextual artifact

### Requirement: TestMesh keeps spec-check states visible
**Reason**: The provider-specific spec-check child category is removed with the Spec Work Package bridge.

**Migration**: Preserve actual test and validator states through the existing generic TestMesh state vocabulary. Keep provider planning status visible only in WorkContext and never project it as execution evidence.

#### Scenario: Provider planning status changes
- **WHEN** a provider changes a task or artifact status without executing a native validator
- **THEN** TestMesh SHALL keep that status outside its execution-state children and SHALL NOT infer a test transition
