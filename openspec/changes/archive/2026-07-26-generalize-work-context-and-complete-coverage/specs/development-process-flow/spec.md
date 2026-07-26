## RENAMED Requirements

- FROM: `### Requirement: DevelopmentProcessFlow consumes spec work packages`
- TO: `### Requirement: DevelopmentProcessFlow consumes read-only WorkContexts`

## MODIFIED Requirements

### Requirement: DevelopmentProcessFlow consumes read-only WorkContexts
DevelopmentProcessFlow SHALL consume an explicit collection of zero, one, or
many reviewed WorkContexts as versioned development-process inputs. It SHALL
preserve context, adapter, native work, native owner, subject lane, artifact
role, behavior-source-surface, and fingerprint identities while ordering
FlowGuard-owned planning, implementation, validation, freshness, and release
actions. It SHALL NOT write provider artifacts, invoke provider execution or
validation, create provider sessions/caches/receipts, interpret provider status
as proof, or claim provider completion, synchronization, or archive authority.

#### Scenario: Work package enters the lifecycle
- **WHEN** one or more reviewed WorkContexts are selected as inputs to a
  DevelopmentProcessFlow plan
- **THEN** DPF SHALL order their read-only normalization, BCL/preflight target
  review, PlanDetail projection, FlowGuard-owned actions, and context
  freshness checks without creating or executing a provider work package

#### Scenario: Peer write occurs during the session
- **WHEN** a peer or unknown writer changes a covered WorkContext artifact
  after its fingerprint was consumed
- **THEN** DevelopmentProcessFlow SHALL preserve the peer write, stale every
  dependent row, and derive minimum owner-specific revalidation without
  rolling back the peer or opening a provider session

#### Scenario: Several contexts feed one lifecycle
- **WHEN** a process consumes contexts from several registered adapters or
  native work units
- **THEN** DevelopmentProcessFlow SHALL retain every context and artifact
  identity through actions, freshness rules, recommendations, and final claim
  boundaries without selecting one provider as the default

#### Scenario: A required artifact role is missing
- **WHEN** a selected WorkContext review reports a missing adapter-declared
  required role
- **THEN** DevelopmentProcessFlow SHALL block dependent actions and identify
  the native provider as the owner of any authoring or repair

#### Scenario: Provider execution metadata enters a context
- **WHEN** a WorkContext carries a command, check owner, session, cache,
  receipt, reuse decision, completion projection, or archive-readiness field
- **THEN** DevelopmentProcessFlow SHALL reject the context and SHALL NOT adopt
  or execute that authority

#### Scenario: A WorkContext targets product behavior
- **WHEN** a process step cites a WorkContext artifact mapped to a
  product-runtime commitment
- **THEN** DevelopmentProcessFlow SHALL preserve the product commitment as a
  typed target and SHALL NOT copy its behavior or primary-model ownership into
  the process action

### Requirement: Process closure requires post-snapshot evidence
DevelopmentProcessFlow SHALL reject done, archive, release, or publish
confidence based only on WorkContext status, provider checkboxes, planning
artifact presence, a pre-run snapshot, background liveness, or provider
metadata. Every FlowGuard-owned completion claim SHALL depend on current
terminal evidence from the exact native validation owner after all covered
artifacts and WorkContext fingerprints are final. Any provider-native
validation or archive action SHALL remain an external required action proved
only by that provider's own workflow.

#### Scenario: Session lacks terminal post evidence
- **WHEN** a FlowGuard-owned validation lacks a matching final input snapshot,
  terminal result, or current native evidence receipt
- **THEN** the process SHALL remain incomplete even if every WorkContext task
  or status artifact reports completion

#### Scenario: Provider status is the only proof
- **WHEN** a plan cites provider validation, task completion, or archive status
  without current evidence from the owner required by the FlowGuard claim
- **THEN** DevelopmentProcessFlow SHALL report the evidence gap and SHALL NOT
  convert the provider status into a FlowGuard receipt

#### Scenario: Provider-native lifecycle remains outstanding
- **WHEN** FlowGuard-owned implementation and validation evidence is current
  but a configured provider still requires native validation or archive
- **THEN** DevelopmentProcessFlow MAY report that external action as
  outstanding but SHALL NOT execute it or claim its completion

#### Scenario: Context changes after native validation
- **WHEN** a required WorkContext fingerprint changes after a dependent
  FlowGuard validation produced terminal evidence
- **THEN** DevelopmentProcessFlow SHALL stale the affected evidence and require
  the exact minimum owner-specific revalidation before closure
