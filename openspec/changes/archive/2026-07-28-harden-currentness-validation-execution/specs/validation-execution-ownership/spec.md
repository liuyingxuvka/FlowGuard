## ADDED Requirements

### Requirement: Validation freezes one complete owner DAG before execution
Before any validation producer starts, FlowGuard SHALL construct and validate
one immutable owner DAG and one `ParentCurrent` identity. The frozen plan MUST
bind every required owner, obligation, functional input component, dependency,
declared shared resource, command, toolchain, environment policy, output
subject, and disposition. The DAG MUST be acyclic, every required obligation
MUST have exactly one execution owner, and every owner disposition MUST be
`execute`, `reuse_current`, or `blocked`.

#### Scenario: An owner is discovered after execution starts
- **WHEN** a required owner, obligation, dependency, or shared resource was not
  present in the frozen owner DAG
- **THEN** the validation parent MUST block
- **AND** FlowGuard MUST NOT append the owner to the running plan or start it
  under the existing `ParentCurrent`

#### Scenario: The owner graph is cyclic
- **WHEN** the declared owner dependencies contain a cycle
- **THEN** FlowGuard MUST block before acquiring a lease or starting a producer

#### Scenario: An obligation has duplicate owners
- **WHEN** two owners claim execution authority for the same required obligation
- **THEN** FlowGuard MUST block the plan rather than choose an owner by order,
  command similarity, or fallback

### Requirement: Affected-only execution follows declared component edges
FlowGuard SHALL derive the invalidated owner set from changed functional
components and the transitive dependency edges in the frozen owner DAG. It
MUST execute only invalidated, missing, or failed required owners and MUST
reuse independently verified exact-current terminal receipts for unaffected
owners. Evidence outputs, receipts, logs, progress events, and pointers MUST
NOT invalidate an owner unless the owner plan explicitly declares their
content as a functional input.

#### Scenario: One leaf component changes
- **WHEN** a functional component consumed by one leaf owner changes
- **THEN** FlowGuard MUST invalidate that owner and its dependent owner closure
- **AND** unrelated owners with exact-current receipts MUST remain reusable

#### Scenario: A changed component has no exact mapping
- **WHEN** a governed changed component is unmapped or maps ambiguously to
  several owners without a declared shared dependency edge
- **THEN** the plan MUST be `blocked`
- **AND** FlowGuard MUST NOT fall back to running every owner

#### Scenario: Only a progress file changes
- **WHEN** a progress log changes and no owner declares it as a functional input
- **THEN** the affected owner set and reusable receipt identities MUST remain
  unchanged

### Requirement: Owner and resource leases are atomic single-flight gates
Before starting a producer, FlowGuard SHALL atomically acquire the frozen owner
lease and every declared shared-resource lease for that execution identity.
An owner MUST NOT start while any required lease is held by another live or
cleanup-unconfirmed execution. Lease state MUST distinguish live execution,
terminal settlement, and residual cleanup blockage.

#### Scenario: Different owners require the same mutable resource
- **WHEN** two otherwise independent owners require the same declared mutable
  cache, installation, workspace, port, or evidence store
- **THEN** their producers MUST NOT overlap
- **AND** the later owner MUST wait or remain blocked under the frozen DAG

#### Scenario: A residual lease remains after interruption
- **WHEN** an interrupted owner has not proved complete descendant-process
  cleanup
- **THEN** its owner and resource leases MUST remain blocking
- **AND** no later owner in the frozen parent or automatic retry may start

### Requirement: Child results are persisted and independently reverified
Every terminal child result SHALL be persisted immediately as an immutable
receipt before parent composition. The parent MUST load each required child
from the receipt store and independently verify its exact identity, subject,
scope, obligations, functional-input fingerprints, toolchain, environment,
terminal result, and supersession state against the frozen `ParentCurrent`.

#### Scenario: A successful child precedes a later failure
- **WHEN** one child succeeds and a later child fails
- **THEN** the successful child's immutable receipt MUST remain available for
  exact-current reuse by a later frozen parent

#### Scenario: A caller supplies a verified flag
- **WHEN** a caller marks a child current or verified without a matching
  successful independent verification result
- **THEN** the parent MUST reject the child for composition

### Requirement: Process-tree settlement precedes lease release
Timeout, cancellation, interruption, or launcher failure SHALL trigger
platform-appropriate containment and termination of the complete descendant
process tree. FlowGuard MUST confirm zero live descendants before it publishes
an owner receipt, releases any owner or resource lease, starts any later owner
in the frozen parent, or permits a retry. Cleanup-unconfirmed execution MUST remain
blocked and MUST NOT publish an authoritative receipt.

#### Scenario: A grandchild survives launcher timeout
- **WHEN** the launcher and direct child exit but a descendant remains live
- **THEN** cleanup MUST be `cleanup-unconfirmed`
- **AND** no receipt, lease release, later owner, or automatic retry
  is allowed

#### Scenario: Every descendant is confirmed terminated
- **WHEN** an interrupted execution reaches zero live descendants
- **THEN** FlowGuard MAY settle the episode as terminal non-pass evidence and
  release its leases
- **AND** any retry MUST use a new immutable execution identity

### Requirement: One verified full parent owns broad completion
Only a terminal-success parent receipt whose subject is exactly
`validation-parent:full` MAY support broad done, release, archive, or publish
claims. That receipt SHALL bind the frozen owner DAG, `ParentCurrent`, complete
required owner and obligation inventory, and exact verified child tuple set.
FlowGuard MUST verify every child again immediately before atomically
publishing the parent receipt and current-parent pointer.

#### Scenario: Every child is current under the frozen parent
- **WHEN** all required children independently verify as terminal success for
  the same frozen `ParentCurrent`
- **THEN** FlowGuard MAY publish one immutable `validation-parent:full` receipt
  and point to it atomically

#### Scenario: A child receipt supports a broad claim
- **WHEN** a done, release, archive, or publish claim cites only a child,
  focused, routine, plan, progress, or synchronization receipt
- **THEN** FlowGuard MUST reject broad completion even if that receipt passes

#### Scenario: A child is superseded before parent publication
- **WHEN** receipt-store verification finds that a required child is no longer
  the current eligible receipt before parent publication
- **THEN** the parent MUST remain unpublished and the exact affected owner MUST
  be replanned under a new frozen parent identity
