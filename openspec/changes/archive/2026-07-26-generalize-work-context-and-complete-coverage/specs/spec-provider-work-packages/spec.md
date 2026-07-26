## ADDED Requirements

### Requirement: Provider work-package runtime remains retired
FlowGuard SHALL NOT expose a provider work-package runtime, compatibility
reader, session, cache, receipt bridge, task reconciliation authority, or
archive-readiness projection. Declared provider artifacts SHALL enter only
through the provider-neutral, read-only WorkContext capability.

#### Scenario: Retired work-package input is presented
- **WHEN** a caller presents a legacy provider work-package payload or asks
  FlowGuard to resume its session, receipt, reconciliation, or archive path
- **THEN** FlowGuard SHALL reject the retired surface and SHALL direct current
  planning input through a registered WorkContext adapter without fallback

## REMOVED Requirements

### Requirement: Specification providers retain native authority
**Reason**: The provider work-package capability is retired. Provider
authority preservation now belongs to the provider-neutral, read-only
WorkContext boundary without retaining a work-package runtime.

**Migration**: Use a registered WorkContext adapter to read declared planning
artifacts and derived authoring status. Use each provider's native workflow
for creation, verification, implementation, synchronization, and archive.

### Requirement: Work-package identities are stable and plane-safe
**Reason**: Work-package, provider-task, obligation, check, session, and
cross-plane execution identities are no longer FlowGuard runtime authorities.

**Migration**: Preserve only WorkContext identity, provider and adapter
identity, project-bounded artifact roles and ids, content fingerprints,
current/read-only state, and typed contextual target references.

### Requirement: Task and obligation reconciliation is bidirectionally complete
**Reason**: Bidirectional reconciliation incorrectly couples provider task
bookkeeping to FlowGuard obligation and execution ownership.

**Migration**: Treat provider tasks as read-only WorkContext artifacts.
FlowGuard commitments, models, contracts, tests, and evidence SHALL declare
and close their own obligations independently.

### Requirement: Canonical inputs and derived results are disjoint
**Reason**: The work-package canonical-input system is retired together with
provider sessions, execution, caches, receipts, and result projection.

**Migration**: WorkContext content-addresses only the declared read-only
planning artifacts and adapter-derived authoring status. FlowGuard native
owners fingerprint their own governed inputs and derived evidence separately.

### Requirement: Verification uses same-session begin and post snapshots
**Reason**: WorkContext never opens or participates in FlowGuard verification
sessions and cannot own provider execution.

**Migration**: FlowGuard validation owners snapshot only their own exact
inputs. Provider validation and lifecycle currentness remain entirely
provider-native.

### Requirement: Check receipts are immutable and exact
**Reason**: Planning contexts do not execute checks, create receipts, or
transport FlowGuard evidence.

**Migration**: Keep every FlowGuard model, contract, test, and process receipt
with its exact native execution owner; WorkContext may expose only a read-only
artifact reference without upgrading it to FlowGuard evidence.

### Requirement: Reuse and deduplication are fail-closed
**Reason**: The retired work-package bridge no longer executes, caches,
resumes, or reuses provider or FlowGuard checks.

**Migration**: Any execution reuse remains inside the exact native FlowGuard
or provider owner. WorkContext rereads current artifacts and computes current
content identities without a compatibility cache or receipt-reuse path.

### Requirement: Provider reports distinguish execution states
**Reason**: WorkContext reports artifact availability, declared provider
status, and currentness as context; it does not project provider bookkeeping
as FlowGuard execution state.

**Migration**: Keep provider-native status explicitly typed as contextual
data. Use only native FlowGuard evidence owners for `executed`, passing,
failed, blocked, stale, skipped, or not-run validation claims.

### Requirement: Provider archive readiness is evidence-bound
**Reason**: Archive readiness and its verification gates belong exclusively to
the selected provider and cannot be projected or approved by FlowGuard.

**Migration**: Use the provider's native validation and archive workflow.
FlowGuard may consume the resulting current WorkContext after the provider
changes its artifacts, but it SHALL NOT authorize archive.
