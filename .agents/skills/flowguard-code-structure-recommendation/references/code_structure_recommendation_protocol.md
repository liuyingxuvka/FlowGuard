# Code Structure Recommendation Protocol

Use this route when a user or agent needs a recommended implementation
structure before production code is written. This is a parallel route beside
ordinary core modeling; it is not a mandatory step for every FlowGuard model.

## Trigger

Use code structure recommendation when:

- the user directly asks for a code architecture, file split, module split, or
  implementation structure recommendation;
- a FlowGuard functional model exists and the next step is writing code whose
  structure is unclear;
- a planned feature has enough workflow, state, side effects, retry,
  deduplication, cache, or public entrypoint complexity that a monolithic script
  is likely;
- the recommendation needs to compare a flat structure against a parent/child
  or hierarchical functional model.

Skip with a reason when the task is small enough that a single file with clear
functions is the simpler, more maintainable structure.

## Inputs

Collect or create the lightest fit-for-risk functional model:

- source model id and path when one already exists;
- function blocks and their reads/writes;
- modeled state fields, caches, config, and durable records;
- FieldLifecycleMesh field ids, behavior projections, reader ids, writer ids,
  and owner route when fields are in scope;
- side effects such as writes, publishes, external calls, generated artifacts,
  database writes, or UI commits;
- public entrypoints, facades, commands, routes, or data shapes;
- validation boundaries that should prove the implementation follows the model.
- leaf boundary-matrix observation points when a child model is expected to
  prove a finite `Input x State -> Set(Output x State)` code boundary.

These validation boundaries are future Risk Evidence Ledger proof ids. This
route names where proof must exist later; it does not turn structure advice into
runtime or test evidence.

If the functional model is itself large, use the existing model mesh guidance to
keep parent and child model boundaries clear. Do not create a second modeling
language for code structure.

## Recommendation Shape

Produce a structured recommendation with:

- parent boundary;
- target modules and paths;
- FunctionBlock-to-module ownership;
- state-owner mapping;
- field-owner, field-reader, and field-writer mapping;
- side-effect-owner mapping;
- config-owner mapping when config/defaults matter;
- facade or public entrypoint plan;
- validation and replay boundaries;
- rationale for grouping related blocks instead of mechanically creating one
  file per block.

The recommendation may group several related FunctionBlocks into one cohesive
module. It should keep orchestration separate from durable state ownership and
external side effects when those boundaries are present in the model.

Every field reader and writer should point to exactly one field owner. If an
old, replaced, deprecated, alias, or compatibility-like field is still visible,
keep it in the recommendation until FieldLifecycleMesh and Architecture
Reduction have closed its disposition.

If a proposed leaf module cannot expose stable inputs, outputs, state writes,
side effects, and error paths for complete boundary-matrix tests, recommend a
smaller model/code boundary before implementation. The answer should not hide a
too-large leaf behind a facade that cannot be observed.

## Software Blueprint Handoff

This extension applies only when the recommendation will support an explicit
whole-software blueprint claim. Freeze the exact current model-element
universe and its fingerprint, including required FunctionBlocks, state,
fields, effects, and public entrypoints. For every element record exactly one
target module/owner or a typed unresolved disposition. A nonempty mapping is
not enough: required ids and mapped-or-dispositioned ids must be exact sets.

Emit reverse implementation-coverage obligations naming the target owner,
expected public or internal realization role, observable boundary, and later
source-audit owner. Those obligations let independent discovery ask whether
every behavior-bearing implementation surface realizes a current model
obligation without turning this recommendation into a source scanner.

This route does not treat proposed source paths as implemented semantics or
prove implementation completeness. Any model-universe
fingerprint change makes the blueprint recommendation stale.

## Relationship To StructureMesh

Code structure recommendation handles direct no-code or pre-code architecture
requests. StructureMesh remains the existing-code split review route.

When StructureMesh reviews an existing large script, module, package, command,
or API surface split, it must include model-derived target structure evidence
inside the StructureMesh plan. That evidence can use the same recommendation
shape, but the StructureMesh protocol owns the requirement for existing-code
decomposition.

ArchitectureReduction is a later conditional route, not a default follow-up.
Use it only when a current model/code map identifies a concrete duplicated or
over-complex implementation responsibility, the observable contract is
frozen, behavior-preservation proof status is explicit, and the required
StructureMesh/DevelopmentProcessFlow revalidation route is named. Size,
neatness, token cost, or a blueprint claim alone is insufficient.

## Completion Standard

A recommendation is complete when:

- the source functional model is named;
- target modules are named;
- FunctionBlock ownership is mapped;
- modeled state and side effects have clear owners when present;
- behavior-bearing fields have clear owners, readers, writers, and downstream
  FieldLifecycleMesh or Model-Test Alignment handoffs when present;
- public entrypoints or facades are mapped when present;
- validation boundaries are visible;
- leaf boundary-matrix observation points are named when layered proof is a
  future confidence requirement;
- future Risk Evidence Ledger proof boundaries are named when the
  recommendation will support a final confidence claim;
- grouping rationale is explicit;
- known-bad alternatives such as a monolithic target, duplicate owners, hidden
  side effects, missing facade, or unexplained mechanical over-splitting are
  rejected or documented as out of scope.

For blueprint use, completion additionally requires exact equality between the
frozen model-element universe and mapped-or-typed-unresolved elements, plus a
reverse implementation-coverage obligation for each required element. This is
still recommendation completeness, not static blueprint qualification.

Implementation-ready requires current admission for the same task, model, and
every proposed module/path. Otherwise it remains recommendation-only.

## Blueprint Layer Contribution

For explicit whole-software scope, this route produces recommendation inputs
for `traceability`: exact model element -> proposed module/path/symbol/owner/
facade/adapter/validation boundary, plus reverse implementation-coverage
obligations. Those rows are targets until independent inventory and source
binding owners verify them. They do not prove implemented traceability,
`independent_semantics`, `model_code_test`, `resource_oracle`, or
`static_blueprint`.

Ordinary recommendation work covers affected model elements only. Missing,
duplicate, ambiguous, or stale project ownership blocks; never fall back to a
FlowGuard self-owner, authoritative root, or guessed product role. Return any
supplied canonical `deepest_proven_layer` unchanged plus the first unresolved
native owner/element/evidence gap.

Keep user execution choice, verified maturation, and DevelopmentProcessFlow
admission separate. A recommendation never generates code.

For a canonical blueprint, derive target module ownership from the exact
primary `BehaviorBlockContract` set and attach helpers/adapters through
`SupportingSurfaceRelation`. Preserve all ten behavior dimensions across the
recommended boundary. A helper path is not a second behavior owner, and a
target application's people or permissions remain inside that application's
model rather than becoming FlowGuard-global structure.
