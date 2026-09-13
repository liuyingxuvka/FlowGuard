## ADDED Requirements

### Requirement: Independent behavior denominator is discovery-owned

Before a broad behavior claim opts into complete behavior-inventory coverage,
the canonical Behavior Commitment Ledger SHALL carry one independently
discovered behavior inventory whose expected ids, discovery revision,
discovery fingerprint, evidence ids, project boundary, and claim boundary are
supplied by the native discovery owner. The inventory SHALL NOT be generated
from existing BCL commitment rows, test cases, or caller-selected candidates.

#### Scenario: Discovery owner supplies a current denominator

- **WHEN** a native discovery owner supplies a current revision, source
  fingerprint, evidence ids, and exact expected behavior ids
- **THEN** the BCL SHALL preserve that identity and validate materialized rows
  against the supplied expected set

#### Scenario: Missing opted-in denominator blocks

- **WHEN** `require_complete_behavior_inventory=true` and no independent
  behavior inventory is attached
- **THEN** the BCL review SHALL report
  `independent_behavior_inventory_missing`
  **AND** SHALL NOT support an unqualified complete behavior claim

### Requirement: Each independent behavior has an immutable external contract

Every independent behavior item SHALL carry a stable `behavior_id`, source
kind, source reference and `sha256:` source fingerprint, public surface,
intent, success outcome, at least one explicit error outcome, at least one
explicit recovery path or not-applicable reason, and one non-empty owner.

#### Scenario: Missing external outcome detail blocks

- **WHEN** an item omits its public surface, intent, success, error, recovery,
  owner, or source identity
- **THEN** item construction or inventory review SHALL fail closed rather than
  silently treating the behavior as tested

### Requirement: Current intent and lifecycle evidence are explicit

The current independent behavior inventory SHALL use the
`flowguard.independent-behavior-inventory.v2` schema. Every item SHALL retain
one or more `intent_source_refs` plus an explicit current intent disposition
from `accepted_current`, `superseded`, `merged`, `retired`, `rejected`, or
`unresolved`. An `accepted_current` item SHALL bind a function or route,
model obligation ids, required check ids, test references, evidence subjects,
oracle ids, failure-case ids, recovery-case ids, and a current effective-intent
fingerprint.

An accepted current item SHALL also carry all lifecycle lanes:
`happy_path`, `boundary`, `negative`, `fault`, `recovery`, `cleanup`,
`idempotency`, `repeated`, `interruption`, `runtime`, `ui`, `consumer`,
`installation`, `platform`, `release`, and `observed_miss_backfeed`. Each lane
must be either `required_and_covered` or `verified_not_applicable` with its
native proof supplied by the target owner. The inventory SHALL reject the old
v1 schema directly; it SHALL NOT provide a compatibility reader or automatic
inheritance path.

#### Scenario: Accepted current behavior omits a lifecycle lane

- **WHEN** an accepted current item omits a required semantic link or one of
  the lifecycle lanes
- **THEN** inventory review SHALL emit a typed blocker and SHALL NOT count the
  item as covered

#### Scenario: Historical intent is unresolved

- **WHEN** an item marks its intent disposition as `unresolved`
- **THEN** review SHALL keep the behavior denominator blocked until a current
  owner explicitly accepts, supersedes, merges, retires, or rejects it

#### Scenario: Legacy inventory is supplied

- **WHEN** a caller supplies `flowguard.independent-behavior-inventory.v1`
- **THEN** the current reader SHALL reject it visibly and SHALL NOT reinterpret
  it as v2 or choose a fallback authority

### Requirement: Independent behavior dispositions are explicit

Each independent behavior item SHALL use exactly one canonical disposition:
`modeled`, `delegated_to_named_owner`,
`explicitly_out_of_scope_with_reason`, or `blocked_gap`.

- A `modeled` item SHALL name one BCL commitment and one primary model owner.
- A `delegated_to_named_owner` item SHALL name one native owner inventory and
  one typed delegation relation.
- An `explicitly_out_of_scope_with_reason` item SHALL record an out-of-scope
  reason, validation boundary, and rationale.
- A `blocked_gap` item SHALL record a gap reason, validation boundary, and
  rationale, and SHALL remain a visible blocker rather than being treated as
  out of scope.

Historical BCL source-surface dispositions `delegated` and `scoped` SHALL
remain separate from the inventory vocabulary and SHALL NOT be accepted as
inventory dispositions, aliases, or fallback values. Callers materializing an
independent inventory MUST use one of the four canonical values above; the
existing BCL source-surface contract remains unchanged.

#### Scenario: Delegation without a named owner blocks

- **WHEN** a delegated item lacks a native owner inventory or typed relation
- **THEN** review SHALL report `behavior_inventory_delegated_owner_incomplete`

#### Scenario: Blocked gap cannot be hidden as scope

- **WHEN** a `blocked_gap` item lacks a gap reason, validation boundary, or
  rationale
- **THEN** review SHALL report `behavior_inventory_blocked_gap_incomplete`
  **AND** SHALL keep the denominator blocked

#### Scenario: Complete blocked gap remains visible

- **WHEN** a `blocked_gap` item has its reason, validation boundary, and
  rationale recorded
- **THEN** review SHALL still report `behavior_inventory_blocked_gap`
  **AND** SHALL NOT count that item as successful coverage until its owner
  changes the disposition

### Requirement: Behavior inventory conservation is enforced

The validator SHALL enforce exact conservation between the discovery owner's
expected behavior ids and the materialized inventory rows. Duplicate expected
ids, duplicate materialized ids, missing expected rows, and unexpected rows
SHALL each be visible blockers. The discovery inventory id and fingerprint
SHALL remain distinct from the BCL ledger authority identity.

#### Scenario: Expected behavior is absent

- **WHEN** an expected behavior id has no materialized row
- **THEN** review SHALL report `behavior_inventory_expected_item_missing`
  and identify the missing id

#### Scenario: Materialized behavior is outside the denominator

- **WHEN** a materialized row is not in the expected id set
- **THEN** review SHALL report `behavior_inventory_unexpected_item`
  and identify the unexpected id

#### Scenario: Duplicate identity is supplied

- **WHEN** expected or materialized behavior ids are duplicated
- **THEN** review SHALL report the corresponding duplicate-id blocker rather
  than counting duplicate rows as independent coverage

### Requirement: Public-surface discovery gaps remain fail-closed

The native discovery owner SHALL be able to emit a
`flowguard.public_behavior_surface_gap.v1` report for the complete declarable
public surface. The report MAY count explicit production declarations such as
the Python API registry, CLI parser, templates, and console entrypoints, but
it SHALL NOT infer semantic behavior rows from declaration names, test names,
model artifacts, or package exports. It SHALL record the missing semantic
inventory classes and keep the broad denominator blocked until each class has
independently authored source, intent, outcome, owner, and disposition data.
Once every finite class has those explicit rows, a current manifest MAY license
the complete public-surface claim; the report SHALL preserve the rows as
authored evidence and SHALL generate zero rows from declaration names.

#### Scenario: Explicit declarations do not become behavior rows

- **WHEN** the current project exposes API, CLI, or template declarations but
  the native manifest contains only a scoped subset
- **THEN** the gap report SHALL preserve the scoped row count and declaration
  fingerprints
- **AND** SHALL emit a blocker explaining that declarations lack semantic
  intent/error/recovery/owner/disposition rows
- **AND** SHALL emit zero generated behavior ids

#### Scenario: Current authority is invalid

- **WHEN** the current project-audit reports an invalid or non-terminal model
  authority
- **THEN** the public-surface gap report SHALL remain `blocked`
- **AND** SHALL record the authority reason as a blocker
- **AND** SHALL NOT license the BCL complete-inventory opt-in

#### Scenario: Complete current public behavior manifest

- **WHEN** the native manifest declares `complete_current`, enumerates every
  finite public surface class, and supplies explicit source, intent,
  success/error/recovery, owner, disposition, and current-intent identity rows
- **AND** no row is unresolved or a blocked gap
- **AND** the current model authority status is passed
- **THEN** the public-surface gap report SHALL be `passed`
- **AND** SHALL set `denominator_expansion` to `explicit_manifest`
- **AND** SHALL preserve the materialized rows and emit zero generated
  behavior ids
- **AND** SHALL still report a blocker when any class is absent, regardless of
  the number of declaration names discovered

### Requirement: Reverse implementation surfaces are independently conserved

The native implementation-surface owner SHALL discover production source
surfaces without importing the target or reading model/test names as a
denominator. The observation SHALL preserve stable surface identity, source
span, current source fingerprint, surface fingerprint, and the observed kind
for code, exports, API, CLI, templates, configuration, effects, faults,
recovery, placeholders, installation, and UI-like actions. It SHALL also
publish one finite `surface_class` from `code`, `api`, `cli`, `ui_like`,
`config`, `effect`, `fault`, `recovery`, or `install`; parser-specific kinds
must not silently create new denominator classes. A separately authored map
SHALL bind every discovered surface to one typed disposition, owner, test,
and current terminal receipt, and (for governed or internal-proven rows)
intent, model owner, and model obligation.

The map MAY author one explicit `component_groups` row for a complete
deterministic `review_granularity=component` boundary whose members are only
ordinary module/function/class implementation observations. The validator SHALL
expand that row to every listed member before applying the surface contract;
the group member list SHALL equal the complete current observed group, and the
effective binding SHALL be identical for every member. Public/API/CLI/UI-like,
configuration, effect, fault, recovery, installation, dynamic, plugin,
placeholder, and unreachable/unbound observations SHALL remain individual map
rows. Grouping is input compression only and SHALL NOT reduce the independent
surface denominator or hide an omitted member.

#### Scenario: A component group compresses only a complete internal boundary

- **WHEN** an authored component group lists exactly every current
  module/function/class member of one deterministic component review group
- **THEN** reverse review SHALL expand the binding to each member and validate
  intent/model/obligation/test/owner/receipt independently
- **AND** the effective mapped-surface count SHALL still equal the observed
  member count

#### Scenario: A component group omits a member or absorbs a public surface

- **WHEN** a component group lists only part of its current group, or includes
  a public/external surface
- **THEN** reverse review SHALL emit a component-group membership blocker
- **AND** SHALL keep reverse closure blocked

#### Scenario: Source-only discovery finds a new UI-like action

- **WHEN** production source contains a reachable UI-like action that is not in
  the independent map
- **THEN** reverse review SHALL emit
  `implementation_surface_mapping_missing` and
  `implementation_surface_unmodeled_ui_like_action`
- **AND** SHALL keep reverse closure blocked

#### Scenario: A surface has no terminal receipt or the test is empty

- **WHEN** a mapped reachable surface has no current receipt reference, or
  its test reference resolves to a function containing only `pass`/a
  docstring
- **THEN** reverse review SHALL emit a receipt or empty-test blocker
- **AND** SHALL NOT count the surface as covered merely because the path and
  test name exist

#### Scenario: Model obligation points nowhere

- **WHEN** an authored model-obligation row names no current implementation
  surface, or a governed surface is absent from the reverse obligation map
- **THEN** review SHALL emit a model-obligation conservation blocker
- **AND** SHALL NOT treat model-only intent as proof of implemented behavior

#### Scenario: Reverse map invents an intent or model obligation

- **WHEN** a target declares the current behavior ledger and an authored
  reverse map uses an `intent_id` or governed/model-only `obligation_id` that
  is absent from that exact current ledger projection
- **THEN** reverse review SHALL emit a current-ledger identity or vocabulary
  blocker
- **AND** SHALL require the map to carry the exact current behavior-ledger
  join before any surface can be considered semantically current
- **AND** SHALL NOT infer a replacement intent, obligation, owner, test, or
  receipt from names, paths, historical ledgers, or source similarity

#### Scenario: Current model-obligation inventory has a typed non-governed proof

- **WHEN** a current model-obligation inventory row is not implemented by a
  discovered source surface
- **THEN** the row SHALL use `model_only_proven`, `retired_proven`, or
  `not_applicable_proven` with an explicit current proof reference and reason
- **AND** reverse review SHALL keep the row in the denominator while refusing
  to count it as implementation coverage

#### Scenario: Current model-obligation inventory lacks owner proof

- **WHEN** a current model-obligation row cannot yet be proven as governed,
  model-only, retired, or not applicable by the target owner
- **THEN** the row SHALL use the explicit `blocked_gap` disposition with an
  empty `surface_ids` array and a non-empty current `gap_reason`
- **AND** reverse review SHALL keep the obligation in the denominator and
  SHALL keep reverse closure blocked
- **AND** the row SHALL NOT be rewritten as `model_only_proven` merely because
  no implementation binding has been authored

#### Scenario: Mutation changes source identity

- **WHEN** production source changes after a map was authored
- **THEN** the current discovery fingerprint SHALL differ from the map
- **AND** review SHALL emit `implementation_surface_mapping_stale` rather than
  reuse the prior mapping as current evidence

### Requirement: Bounded implementation discovery SHALL partition before truncation

When the complete production source boundary would exceed the native
implementation-surface observation bound, the discovery owner SHALL create a
deterministic source-path shard plan. Each shard SHALL carry its plan identity,
current source fingerprints, a source-only call-graph observation, and no more
than the hard row bound. A merged report SHALL be accepted only when every
planned source path occurs exactly once and every shard and row is current.

#### Scenario: A complete source boundary exceeds one observation bound

- **WHEN** a production source tree would produce more than 5,000 observation
  rows
- **THEN** discovery SHALL emit multiple bounded child shards and a frozen
  plan fingerprint
- **AND** it SHALL NOT truncate the source boundary and call the partial result
  complete

#### Scenario: Missing or stale shard

- **WHEN** a planned shard is omitted, duplicated, overlaps another shard, or
  contains a stale source fingerprint
- **THEN** the merge SHALL emit a visible shard conservation blocker
- **AND** SHALL NOT produce a complete implementation-surface observation

### Requirement: Reachability and call boundaries SHALL be closed

The source-only implementation observer SHALL preserve local call-graph edges
and emit an explicit unreachable_or_unbound observation for a function with no
resolved local incoming edge and no explicit export/API/console binding.
Reachability SHALL be recomputed after shard merge so cross-shard callers are
considered. Every call-site edge SHALL close to one current source target, an
exact finite source dispatch set, or a deterministic external/dynamic boundary
 target. The discovery SHALL NOT emit `surface_call_graph_ambiguous` or
`external_or_dynamic_unknown` as a current resolution. Dynamic and plugin
surface rows SHALL be individually visible and SHALL be closed by a current
governed, internally proven, or retired disposition; a typed N/A or blocked
gap is not a current closure when this validation boundary exists. That
semantic boundary SHALL NOT be confused with an unresolved call edge.

#### Scenario: A helper is only visible in a source file

- **WHEN** a function has no resolved incoming call and no explicit external
  binding
- **THEN** discovery SHALL emit an unreachable_or_unbound row
- **AND** reverse review SHALL require a current governed, internal, or
  retired disposition with the row's own owner/test/receipt or proof join;
  typed N/A and blocked-gap dispositions do not close the current boundary

#### Scenario: A caller and callee are split across shards

- **WHEN** one shard contains a caller and another contains its uniquely
  resolvable local callee
- **THEN** merged reachability SHALL resolve the cross-shard edge
- **AND** SHALL NOT retain the callee's child-local unbound observation

#### Scenario: Full and merged observations conserve every call site

- **WHEN** a complete shard set is merged and a module, class body, or function
  child observation contains a source-only call edge
- **THEN** the merged call graph SHALL contain that edge exactly as an
  observation, including module and class-body callers
- **AND** merged reachability SHALL use the child call-site observation for
  target resolution rather than reconstructing only from surface-row facts
- **AND** a dynamic/external expression SHALL carry one deterministic current
  external-contract id, while a finite set of source candidates SHALL carry
  `resolved_static_dispatch` with the complete candidate set
- **AND** the current discovery SHALL contain no unresolved call-graph
  resolution or ambiguity finding
- **AND** any missing, orphaned, stale, or structurally invalid edge SHALL keep
  the merged observation blocked

#### Scenario: An unqualified call has one same-source definition

- **WHEN** an unqualified call has exactly one candidate defined in the
  caller's source file and other production files merely reuse the same leaf
  name
- **THEN** source-only discovery SHALL resolve the call to the same-source
  candidate without importing or executing the target package
- **AND** candidates from unrelated files SHALL NOT manufacture an ambiguity

#### Scenario: Same-source definitions form an exact dispatch set

- **WHEN** an unqualified call has multiple candidates in the caller's source
  file and static syntax does not distinguish the binding
- **THEN** discovery SHALL emit `resolved_static_dispatch` with every exact current
  candidate surface id
- **AND** SHALL NOT choose a single target from declaration order or a
  compatibility path

#### Scenario: Dynamic or plugin loading is observed

- **WHEN** source uses dynamic import, reflection, plugin registration, or
  entry-point loading
- **THEN** discovery SHALL preserve a dynamic/plugin surface observation
- **AND** every resulting call-site edge SHALL carry a deterministic current
  external-contract id rather than an unresolved or boundary-only resolution
- **AND** reverse review SHALL bind the dynamic/plugin row to its current
  owner, intent, model obligation, test, and receipt (or a current retired
  proof) rather than inventing a source target or leaving a typed uncertainty

#### Scenario: Zero mapped surfaces is not a pass

- **WHEN** the discovered production denominator is non-empty but the
  independently authored map contains zero rows
- **THEN** reverse review SHALL emit an explicit zero-mapping blocker
- **AND** SHALL keep `reverse_closure_complete=false`

### Requirement: Dynamic targets SHALL be current resolved contracts

The current reverse discovery SHALL not retain dynamic, ambiguous, unknown, or
boundary-only call states. Every call edge SHALL resolve to one current source
surface, one complete finite static-dispatch set, or one explicitly identified
external contract. An external contract identity SHALL be deterministic,
conserved in the discovery artifact, and joined to the exact caller and call
expression. Each `resolved_external_contract` edge and its matching registry row
SHALL also carry `target_kind=external_contract`, `target_identity` equal to
the canonical external-contract id, `target_status=current_resolved`, and
`target_proof=external_contract_registry`. Missing, mismatched, or
`typed_current_observation` target fields SHALL be a blocker; they SHALL NOT be
accepted as a typed uncertainty or observation-only substitute. The current
semantic map SHALL not leave dynamic, plugin,
unreachable, or placeholder implementation rows as `not_applicable_proven`
when the current validation boundary already supplies their owner and oracle;
each such row SHALL be governed, internally proven, or retired with a current
proof, and the audit SHALL reject `not_applicable_proven` and `blocked_gap` for
those current rows.

#### Scenario: Dynamic receiver or callback is resolved

- **WHEN** source contains a receiver, callback, reflection, or dynamic import
  call whose source target cannot be proven from lexical imports
- **THEN** discovery SHALL emit `resolved_external_contract` with a canonical
  `contract:<kind>:<hash>` identity and no source target ids
- **AND** the same contract row SHALL appear exactly once in the current
  `external_contracts` registry
- **AND** the edge and registry row SHALL carry the same exact
  `target_identity`, with `target_kind=external_contract`,
  `target_status=current_resolved`, and
  `target_proof=external_contract_registry`
- **AND** discovery SHALL NOT emit `resolved_dynamic_boundary`,
  `resolved_external_boundary`, `surface_call_graph_ambiguous`, or
  `external_or_dynamic_unknown`

#### Scenario: Finite same-source candidates are resolved

- **WHEN** static syntax proves a finite set of current source candidates
- **THEN** discovery SHALL emit `resolved_static_dispatch` with every exact
  candidate surface id
- **AND** it SHALL NOT label the set as ambiguous or choose one by declaration
  order

#### Scenario: Existing typed dynamic rows are re-authored

- **WHEN** the current validation-evidence boundary has an owner, oracle,
  current receipt, and model obligation for a previously typed dynamic,
  plugin, unreachable, or placeholder observation
- **THEN** the reverse semantic map SHALL bind that row to the current
  obligation and owner, or record a current retired proof
- **AND** it SHALL not use `not_applicable_proven` merely because the static
  scanner previously could not name a target
- **AND** it SHALL not retain `blocked_gap` merely because a previous scanner
  emitted a boundary-only observation
- **AND** implementation-to-model and model-to-implementation joins SHALL
  remain exact after the rewrite

### Requirement: Persistent reverse owner receipts are a separate current denominator

The persistent reverse implementation-surface map SHALL use one exact current
owner receipt per declared persistent owner route. That denominator SHALL be
independent of the affected-owner evidence set of any one model revision, and
it SHALL bind the current discovery fingerprint, owner-binding fingerprint,
full model-parent receipt, route set, child model receipts, and active model
authority identity. A delta-local revision receipt for a route SHALL NOT be
appended as a second identity for the same persistent route; the persistent
receipt replaces that route in the reverse join. Missing, stale, duplicate,
foreign-unit, or mismatched receipts SHALL block reverse closure. No fallback,
legacy reader, or automatic inheritance is allowed.

#### Scenario: A revision omits a persistent reverse owner route

- **WHEN** the accepted model revision's affected-owner evidence does not
  include one of the routes used by the persistent reverse map
- **THEN** the reverse owner authority SHALL still require a fresh current
  receipt for that route composed from the current full model parent
- **AND** the reverse join SHALL contain exactly one receipt identity for every
  persistent route

#### Scenario: Delta-local and persistent identities share a route

- **WHEN** a current accepted revision and the persistent reverse authority
  both expose a receipt for the same owner route
- **THEN** the reverse join SHALL retain only the persistent authority receipt
- **AND** it SHALL reject duplicate route identities rather than treating two
  receipts as additive coverage

#### Scenario: Persistent owner receipt becomes stale

- **WHEN** the discovery, owner bindings, full model parent, child receipt,
  route set, or active authority identity changes
- **THEN** the persistent reverse authority loader SHALL block
- **AND** it SHALL not reuse a predecessor receipt or downgrade the map to a
  boundary-only or uncertain state
