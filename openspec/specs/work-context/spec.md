# work-context Specification

## Purpose
Define a provider-neutral read-only planning context that content-addresses
declared artifacts without taking provider execution or lifecycle authority.
## Requirements
### Requirement: WorkContext is the sole provider-neutral context model
FlowGuard SHALL represent external planning and work material with one
provider-neutral `WorkContext` containing stable context, adapter, native work,
native owner, project root, context root, subject lane, artifact inventory,
required-role, behavior-source-surface, currentness, read-only, metadata, and
content-fingerprint identities. The core schema SHALL contain no preferred
provider, provider-specific field, or provider-specific artifact enum.

#### Scenario: Different planning systems produce peer contexts
- **WHEN** an official OpenSpec adapter and a declared-files profile for
  another planning system read material with equivalent generic roles
- **THEN** FlowGuard SHALL return peer WorkContext rows using the same core
  fields without promoting either adapter to core authority

#### Scenario: Provider-specific data is needed
- **WHEN** an adapter needs to preserve a native identifier or bounded
  descriptive value that is not part of the generic schema
- **THEN** it SHALL preserve that value as canonical native metadata without
  adding a provider-specific core field

### Requirement: WorkContext artifacts use stable generic roles
Every WorkContext artifact SHALL have a stable `artifact_id`,
`artifact_role`, project-bounded `source_ref`, byte-content fingerprint, and
size. `artifact_role` SHALL be exactly one of `scope`, `requirement`,
`acceptance`, `design`, `plan`, `task`, `status`, `history`, or `other`, and
each adapter declaration SHALL identify every role required for its context.

#### Scenario: Native documents have provider-specific names
- **WHEN** a provider calls its documents proposal, constitution, brief,
  checklist, story, or implementation plan
- **THEN** the adapter SHALL map them to generic roles while preserving their
  stable native identities and source references

#### Scenario: A required role is absent
- **WHEN** a context lacks an adapter-declared required artifact role
- **THEN** WorkContext review SHALL report the missing role and SHALL NOT
  synthesize or repair the provider artifact

#### Scenario: An unknown role is supplied
- **WHEN** an artifact declares a role outside the current generic role set
- **THEN** WorkContext review SHALL reject the artifact rather than silently
  treating the provider-specific role as current

### Requirement: WorkContext has zero provider execution authority
WorkContext and every adapter SHALL be read-only and SHALL contain no authoring,
write, apply, execution, validation, dependency-owner, session, cache, receipt,
reuse, completion, synchronization, archive-readiness, or lifecycle-control
authority. Native providers SHALL retain all such authority.

#### Scenario: An adapter exposes a mutating or execution operation
- **WHEN** an adapter or context attempts to expose write, execute, validate,
  resume, synchronize, complete, or archive behavior
- **THEN** registration or review SHALL fail and FlowGuard SHALL NOT invoke the
  operation

#### Scenario: Provider task status is complete
- **WHEN** a status artifact or native metadata reports every provider task as
  complete
- **THEN** FlowGuard SHALL treat that value only as contextual content and
  SHALL NOT use it as model, test, release, or archive evidence

#### Scenario: FlowGuard validation is required
- **WHEN** WorkContext material implies a FlowGuard model or test obligation
- **THEN** the native FlowGuard owner SHALL produce its own current evidence
  without importing provider status, sessions, caches, or receipts

### Requirement: WorkContext discovery is explicit and project bounded
FlowGuard SHALL discover and read WorkContexts only through explicitly
registered adapters and source declarations bounded by one explicit project
root. Every context root and artifact path SHALL resolve beneath that project
root, and unknown or unsafe paths SHALL fail closed.

#### Scenario: A source path escapes the project
- **WHEN** a declaration, native work id, absolute path, traversal, or symlink
  resolves an artifact outside the explicit project root
- **THEN** the adapter SHALL reject the context before reading the escaped path

#### Scenario: No provider declaration authorizes computer-wide discovery
- **WHEN** no configured source declaration names material outside the current
  project
- **THEN** FlowGuard SHALL NOT scan another project or the rest of the computer

#### Scenario: A declared required source discovers nothing
- **WHEN** a required source declaration resolves no readable native work
- **THEN** WorkContext aggregation SHALL report a missing-context blocker
  rather than treating the expected set as empty

### Requirement: WorkContext identities are content addressed and freshness safe
FlowGuard SHALL calculate each context fingerprint from a canonical ordering of
its current artifact inventory, artifact content identities, adapter/native
identities, bounded roots, subject lane, required roles,
behavior-source-surface links, read-only/current flags, and canonical metadata.
`current` SHALL mean only that the reviewed content identity still matches the
source.

#### Scenario: An artifact changes after context creation
- **WHEN** any covered artifact bytes, identity, role, root, lane, required
  role, source link, or canonical metadata changes
- **THEN** the context fingerprint SHALL change and every dependent review,
  plan, process, maintenance, and evidence row SHALL become stale

#### Scenario: Provider acceptance is confused with current content
- **WHEN** a context is content-current but the provider has not validated,
  completed, or archived the native work
- **THEN** WorkContext SHALL remain current only for content identity and SHALL
  make no provider lifecycle claim

#### Scenario: Artifact order varies
- **WHEN** the same artifact set is returned in a different incidental
  filesystem or adapter iteration order
- **THEN** canonical ordering SHALL produce the same context fingerprint

### Requirement: FlowGuard consumes zero one or many WorkContexts
Every WorkContext-aware operation SHALL accept an explicit canonical collection
of zero, one, or many reviewed contexts. Context and artifact identities SHALL
remain distinct across providers and native work units, and aggregation SHALL
never select the first discovered provider as an implicit primary context.

#### Scenario: Several planning systems are in scope
- **WHEN** one operation uses an OpenSpec change, a declared Superpowers plan,
  and an independent release-note context
- **THEN** FlowGuard SHALL preserve three context identities, owners, lanes,
  artifact inventories, and fingerprints through downstream projections

#### Scenario: Context ids collide
- **WHEN** two discovered contexts reuse one `context_id` for different
  adapter, native work, owner, lane, or content identities
- **THEN** aggregation SHALL block the ambiguous set rather than merge or
  prefer one context

#### Scenario: No WorkContext is configured
- **WHEN** an operation has no required or optional external work source
- **THEN** it MAY proceed with an explicit empty context collection without
  constructing an OpenSpec default

### Requirement: WorkContext preserves lane and behavior-plane boundaries
Every WorkContext SHALL declare exactly one of `observed_implementation`,
`normative_target`, or `counterfactual_experiment` as its subject lane.
Behavior ownership and behavior-plane selection SHALL remain in Behavior
Commitment Ledger, linked only through declared behavior source surface ids and
typed targets.

#### Scenario: A plan promises product behavior
- **WHEN** a normative WorkContext artifact describes a product-runtime
  behavior
- **THEN** the matching product-runtime commitment and its current primary
  model SHALL remain the behavior owner while WorkContext remains read-only
  source and process context

#### Scenario: A skill creates a plan
- **WHEN** an agent-operation skill produces a planning document containing a
  product-runtime target
- **THEN** FlowGuard SHALL keep the skill operation, the WorkContext artifact,
  and the product commitment as separately owned typed identities

#### Scenario: A target or experiment passes review
- **WHEN** a normative-target or counterfactual-experiment context is current
  and all local checks pass
- **THEN** it SHALL NOT become observed-implementation model authority without
  an accepted ModelRevisionSet

### Requirement: WorkContext adapters are explicit peers without fallback
FlowGuard SHALL register every adapter under one unique stable id and SHALL use
only the adapter explicitly named by the source declaration or call. The
built-in OpenSpec and declared-files adapters SHALL satisfy the same protocol,
and future adapters SHALL not require a core schema change.

#### Scenario: Spec Kit or Superpowers files are declared
- **WHEN** a project maps Spec Kit or Superpowers-produced files and required
  roles through the declared-files adapter
- **THEN** FlowGuard SHALL read them as ordinary WorkContexts without a
  provider-specific core branch

#### Scenario: An adapter is not registered
- **WHEN** a declaration names an unknown adapter id
- **THEN** FlowGuard SHALL report an unregistered-adapter blocker and SHALL NOT
  fall back to OpenSpec, declared files, or an inferred reader

#### Scenario: An adapter id is registered twice
- **WHEN** a second adapter attempts to claim an existing adapter id with a
  different implementation
- **THEN** registration SHALL fail unless an explicit current replacement is
  performed before context discovery

### Requirement: WorkContext is a direct current-format replacement
Normal runtime SHALL expose only the WorkContext API, generic adapter
selection, `work-context` CLI, `work-context-template`, and current
`work_context_*` fields. It SHALL reject legacy `SpecContext`,
`spec_context_*`, `spec-context`, and provider-work-package runtime inputs
without aliases, dual emission, automatic conversion, or fallback.

#### Scenario: A legacy API or command is invoked
- **WHEN** a caller uses a removed SpecContext type, field, template, or CLI
  command in normal runtime
- **THEN** FlowGuard SHALL fail with a current-format migration diagnostic and
  SHALL NOT execute an alternate successful path

#### Scenario: An older project is upgraded
- **WHEN** `project-upgrade` recognizes a supported legacy project artifact at
  the explicit upgrade boundary
- **THEN** it SHALL write the direct current WorkContext shape and remove old
  active authority before normal runtime resumes

#### Scenario: Historical evidence names SpecContext
- **WHEN** an archived specification, changelog, release, or immutable receipt
  records the former name
- **THEN** FlowGuard SHALL preserve it as historical evidence without treating
  it as an active alias or readable runtime format

### Requirement: WorkContext behavior-source admission is explicit
WorkContext artifacts SHALL remain read-only planning and change context by
default. They SHALL enter the expected behavior-source inventory only through
explicit behavior-source-surface identities and an admitted typed mapping.

#### Scenario: Planning artifact has no behavior mapping
- **WHEN** a current proposal, design, task, changelog, Spec Kit, Superpowers,
  or other declared-file artifact has no admitted behavior-source-surface id
- **THEN** it SHALL remain fingerprinted WorkContext and freshness input but
  SHALL NOT create an expected behavior commitment row

#### Scenario: Artifact explicitly maps behavior
- **WHEN** a current WorkContext artifact declares an admitted behavior source
  identity and typed commitment target
- **THEN** coverage inventory MAY include that exact source without treating
  provider status as behavior or validation evidence
<<<<<<< HEAD

### Requirement: WorkContext projects typed intent contributions
WorkContext SHALL project admitted requirement, design, plan, history, Spark/OpenSpark, changelog, and direct user-decision material into content-addressed intent contributions. Each contribution SHALL preserve its logical model or explicit unresolved owner, source kind and fingerprint, subject role, effective revision, decision state, supersession references, target obligation references, and rationale.

#### Scenario: Declared Spark material seeds an initial intent
- **WHEN** a project declares bounded Spark or OpenSpark material with an admitted intent mapping
- **THEN** WorkContext emits fingerprinted initial-intent contributions linked to the declared logical model or an explicit unresolved owner
- **AND** the provider retains authoring, execution, validation, and lifecycle authority

#### Scenario: A user decision supersedes an earlier idea
- **WHEN** a current user decision explicitly supersedes an admitted earlier contribution
- **THEN** both immutable contributions remain traceable in the same model lineage
- **AND** only the superseding contribution remains active for the candidate target

#### Scenario: A changelog entry has no semantic mapping
- **WHEN** a changelog or history artifact is current but has no admitted mapping to a model obligation or evolution decision
- **THEN** it remains fingerprinted planning or historical context
- **AND** it does not create, remove, or satisfy a behavior commitment

### Requirement: Intent context never becomes current behavior or test evidence by itself
An intent contribution SHALL be context and provenance only until its native model and revision owners consume it. WorkContext status, timestamps, task checkboxes, document wording, or provider completion SHALL NOT establish current model authority, implementation completion, or passing test evidence.

#### Scenario: A later document conflicts with an active decision
- **WHEN** two admitted contributions conflict and neither carries an explicit accepted supersession decision
- **THEN** WorkContext reports both contributions and the unresolved conflict
- **AND** it does not choose a winner from timestamp order alone

#### Scenario: Optional history is absent during ordinary work
- **WHEN** a scoped affected-only task has current requirements and owner evidence but no declared Spark or changelog source
- **THEN** the task MAY continue within its evidenced scope
- **AND** only a broad intent-history or whole-lineage completeness claim remains unavailable

#### Scenario: Provider status reports complete
- **WHEN** an OpenSpec, Spark, or other provider reports its native work item complete
- **THEN** FlowGuard preserves that status as WorkContext
- **AND** no model, code, test, or release evidence row becomes passing solely because of that status

### Requirement: WorkContext projects intent into exact target-system behaviors
Admitted WorkContext contributions SHALL retain their canonical model-intent identities and bind only to exact current-realization or future-target behavior rows. Blanket projection to every model or behavior in a target SHALL be rejected.

#### Scenario: Active proposal targets one future behavior
- **WHEN** an admitted proposal contribution names one future model obligation and has no accepted current-realization disposition
- **THEN** it SHALL remain a future-target intent binding for that obligation
- **AND** it SHALL NOT make any current behavior or blueprint layer complete

### Requirement: WorkContext remains provider-neutral
WorkContext SHALL accept declared planning and workflow material for software and non-software targets without assuming a source language. Its provider status SHALL remain context and freshness evidence only.

#### Scenario: Workflow specification supplies intended transitions
- **WHEN** a workflow WorkContext maps exact intended transitions to the target authority
- **THEN** the canonical intent inventory MAY preserve those mappings
- **AND** native model, behavior, test, and validation owners SHALL still decide current authority and completion
=======
>>>>>>> agent/harden-currentness-validation
