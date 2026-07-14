## ADDED Requirements

### Requirement: Plane upgrade preserves route ownership
DevelopmentProcessFlow SHALL own lifecycle ordering and freshness for this change while leaving product-runtime behavior with its product owner, AI-operation behavior with AgentWorkflowRehearsal/owner models, and external behavior inventory with BCL.

#### Scenario: Development plan references product target
- **WHEN** a process step validates a product-runtime commitment
- **THEN** DevelopmentProcessFlow SHALL reference the commitment/evidence ids without becoming the product behavior owner

### Requirement: Plane upgrade lifecycle is explicitly ordered
The process plan SHALL order OpenSpec artifacts, model/field/structure decisions, schema/direct replacement, lookup/preflight, miss/similarity integration, prompts/contracts, focused owner validation, installation parity, source freeze, one final parent validation, and read-only OpenSpec consumption.

#### Scenario: Implementation begins before apply-ready artifacts
- **WHEN** required OpenSpec design/spec/verification/task artifacts are missing
- **THEN** the lifecycle review SHALL block implementation edits

#### Scenario: Prompt installation precedes focused checks
- **WHEN** installation is attempted before source prompt and contract checks pass
- **THEN** the lifecycle review SHALL report an out-of-order process step

### Requirement: Peer writes invalidate affected evidence without rollback
DevelopmentProcessFlow SHALL record peer/unknown writer changes as artifact-version changes, preserve those changes, and derive minimum revalidation rather than resetting or overwriting the workspace.

#### Scenario: Peer updates a shared module
- **WHEN** a peer changes a shared BCL/preflight/model file after local evidence was produced
- **THEN** affected evidence SHALL be stale
- **AND** the process SHALL reread, merge, and rerun the affected validations without reverting the peer change

### Requirement: Validation execution remains single-owner and bounded
Long model regressions and full tests SHALL have one explicit execution owner. A full gate starts only after source/tool freeze and SHALL NOT use scheduled tasks, `--resume`, or unattended retry scripts.

#### Scenario: A launcher times out
- **WHEN** a validation launcher times out or is interrupted
- **THEN** the entire descendant process tree SHALL be confirmed absent before any result is accepted or another owner starts
- **AND** cleanup-unconfirmed output SHALL be non-reusable
