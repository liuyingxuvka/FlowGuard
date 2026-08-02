## ADDED Requirements

### Requirement: A FlowGuard release proves the exact whole-system understanding path
Before a FlowGuard release claims current self-understanding, self-maintenance SHALL execute the exact current task through task-fact demand, one resolution per demanded owner, maturation, canonical receipt publication, independent receipt verification, implementation admission, risk review, and closure. Every stage SHALL consume the same current task and model-system identity.

#### Scenario: One stage uses a previous model-system identity
- **WHEN** any self-maintenance stage consumes an identity from an earlier revision
- **THEN** the whole-system self-understanding claim is stale and release closure is blocked

#### Scenario: User authorization is present but maturation was not run
- **WHEN** release work is authorized but the exact current self-understanding task lacks verified maturation
- **THEN** self-maintenance reports understanding not-run and does not claim ready

### Requirement: Parent evidence remains publishable from deep Windows worktrees
The evidence lifecycle SHALL read and atomically publish content-addressed evidence objects when the resolved Windows path exceeds the legacy path limit. A passing child set without a publishable parent result SHALL NOT support a completion claim.

#### Scenario: Model children pass under a deep worktree
- **WHEN** selected model runners pass but the parent evidence object resolves beyond the legacy Windows path limit
- **THEN** the parent result and its object are stored and independently readable without shortening or changing the governed worktree identity
