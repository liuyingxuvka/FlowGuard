## REMOVED Requirements

### Requirement: Specification providers retain native authority
**Reason**: The provider-neutral work-package adapter is retired. FlowGuard now
accepts only official OpenSpec authoring artifacts as read-only context.

**Migration**: Use `SpecContext` for proposal, design, specification, task, and
derived-status reading; use official OpenSpec for every OpenSpec lifecycle
operation.

### Requirement: Work-package identities are stable and plane-safe
**Reason**: Work-package, provider-task mapping, and cross-plane target
relations are no longer FlowGuard runtime authorities.

**Migration**: Preserve only the official OpenSpec change id, artifact ids and
hashes, current/read-only flags, and context hash.

### Requirement: Task and obligation reconciliation is bidirectionally complete
**Reason**: Reconciliation created an unnecessary bridge between OpenSpec
authoring tasks and FlowGuard evidence ownership.

**Migration**: FlowGuard models and tests declare and prove their own
obligations independently; OpenSpec remains contextual input only.

### Requirement: Canonical inputs and derived results are disjoint
**Reason**: The broader provider-work-package canonical-input system is
retired together with provider sessions and execution.

**Migration**: `SpecContext` fingerprints only the supported official OpenSpec
authoring artifacts and derived task status.

### Requirement: Verification uses same-session begin and post snapshots
**Reason**: OpenSpec context never participates in FlowGuard verification
sessions.

**Migration**: FlowGuard validations snapshot only their own native inputs.

### Requirement: Check receipts are immutable and exact
**Reason**: OpenSpec changes do not own or transport FlowGuard receipts.

**Migration**: Native FlowGuard test/model owners retain their own evidence.

### Requirement: Reuse and deduplication are fail-closed
**Reason**: The retired bridge no longer executes or reuses checks.

**Migration**: Any reuse remains inside the exact native FlowGuard execution
owner and is unrelated to OpenSpec.

### Requirement: Provider reports distinguish execution states
**Reason**: Read-only OpenSpec context reports authoring/task status, not
FlowGuard execution state.

**Migration**: FlowGuard execution reports use only native evidence.

### Requirement: Provider archive readiness is evidence-bound
**Reason**: Archive readiness belongs exclusively to official OpenSpec.

**Migration**: Use the official OpenSpec validation and archive workflow.
