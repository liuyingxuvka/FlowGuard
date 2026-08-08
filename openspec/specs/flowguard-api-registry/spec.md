# flowguard-api-registry Specification
## Purpose

Define route-scoped API registry behavior for FlowGuard public helper grouping.
## Requirements
### Requirement: Route-scoped API groups
FlowGuard SHALL expose grouped helper registries that map stable route/group ids
to public helper names while preserving existing flat API lists.

#### Scenario: Starter registry names are public
- **WHEN** a helper name appears in `ROUTE_STARTER_API`
- **THEN** that helper name is also present in `flowguard.__all__`
- **AND** the helper is importable from `flowguard`

#### Scenario: Advanced route remains available
- **WHEN** a consumer needs full route control
- **THEN** `ROUTE_ADVANCED_API` maps the same route id to the route's full helper
  group or full route inventory

#### Scenario: Starter budgets are enforced
- **WHEN** API surface tests run
- **THEN** each route starter group stays within the configured compact budget
- **AND** broad flat groups are not embedded inside starter groups

### Requirement: New helper routes use grouped discovery
New FlowGuard route additions SHALL add grouped registry entries so future
callers do not need to scan a single flat helper list.

#### Scenario: Route addition records group ownership
- **WHEN** a new route-specific helper family is added
- **THEN** tests can assert the route group's required helper names without
  duplicating a long flat-list check

### Requirement: Agent-default API surface
FlowGuard SHALL expose a compact agent-default API group and route starter registry that name the single formal route-first entry points an AI agent should inspect before expanding into full route or helper groups.

#### Scenario: Agent starts FlowGuard maintenance
- **WHEN** an agent reads the public API registry
- **THEN** `AGENT_DEFAULT_API`, `ROUTE_STARTER_API`, and `ROUTE_ADVANCED_API` are available through `API_SURFACE`
- **AND** the existing full public API groups remain available behind full surface names

#### Scenario: Agent-default entry uses hard model helpers
- **WHEN** `AGENT_DEFAULT_API` is inspected
- **THEN** it includes the formal risk intent, check plan, minimum model contract, known-bad proof review, and model-first runner helpers
- **AND** it does not include `Explorer`

#### Scenario: Explorer remains primitive, not entry
- **WHEN** `CORE_API` is inspected by advanced consumers
- **THEN** `Explorer` may remain discoverable as the finite exploration primitive
- **AND** the API registry MUST NOT describe it as the default AI entry

### Requirement: Risk template library is route-scoped public API
FlowGuard SHALL retain risk-template search, review, merge, harvest, and harvest-review helpers in the route-scoped risk_template_library API cohort and advanced discovery surface. They SHALL remain outside CORE_API and ROUTE_STARTER_API so ordinary modeling does not inherit a universal template gate.

#### Scenario: Route group exposes template helpers
- **WHEN** FLOWGUARD_ROUTE_API or advanced route discovery is inspected
- **THEN** the current risk_template_library group remains available for explicitly scoped template operations

#### Scenario: Core API remains model primitive only
- **WHEN** CORE_API or ROUTE_STARTER_API is inspected
- **THEN** risk-template search and harvest helpers are absent from the universal model primitives and direct starter path

### Requirement: Evidence API exposes template files and CLI surfaces
FlowGuard SHALL retain the public risk-template-library template and the explicit risk-template search, harvest, and harvest-review CLI surfaces under the existing template and CLI conventions. Their discoverability SHALL NOT make them mandatory for ordinary model, repair, maintenance, or release completion.

#### Scenario: Template helper is discoverable
- **WHEN** a caller requests template reuse, publication, harvest, or harvest review
- **THEN** the current risk-template-library-template, risk-template-harvest, and risk-template-harvest-review command surfaces remain discoverable

#### Scenario: Ordinary work inspects its required commands
- **WHEN** no accepted template trigger is present
- **THEN** ordinary FlowGuard completion has no required template CLI command or receipt

### Requirement: Public API exposes harvest closure helpers
FlowGuard SHALL retain TemplateHarvestReview, review_template_harvest_closure, and the current harvest helpers in the route-scoped RISK_TEMPLATE_LIBRARY_API and advanced risk-template discovery surface. FlowGuard SHALL also retain the explicit risk-template-library-template, risk-template-harvest, and risk-template-harvest-review CLI commands. These surfaces SHALL run only for explicit reuse, publication, harvest, or current stable cross-project-pattern work and SHALL NOT be required by CORE_API, the universal kernel hot path, ROUTE_STARTER_API, ordinary model completion, or unrelated maintenance.

#### Scenario: API registry is inspected
- **WHEN** a consumer inspects RISK_TEMPLATE_LIBRARY_API or the advanced risk-template route group
- **THEN** TemplateHarvestReview, review_template_harvest_closure, and the current harvest helpers remain discoverable
- **AND** they are absent from the core finite-state modeling primitives and universal starter path

#### Scenario: Explicit harvest CLI is invoked
- **WHEN** a caller invokes risk-template-harvest or risk-template-harvest-review for an explicitly scoped template operation
- **THEN** FlowGuard executes the current strict harvest or review behavior
- **AND** missing or invalid operation-local evidence remains a visible failure

#### Scenario: Ordinary model work has no template trigger
- **WHEN** a bounded model, repair, maintenance, or release task contains no explicit template reuse or publication scope and no accepted stable cross-project-pattern trigger
- **THEN** its completion does not invoke or require the harvest API, template command, or CLI receipt

#### Scenario: Starter API is inspected
- **WHEN** a consumer inspects ROUTE_STARTER_API or the universal model-first kernel entry
- **THEN** template harvest and harvest-review helpers are absent from that starter surface
- **AND** explicitly scoped callers continue to use the route-scoped risk-template owner

### Requirement: Route registry separates public and internal surfaces
The FlowGuard API registry SHALL separate public owner route discovery from
advanced/internal helper discovery.

#### Scenario: Public route API excludes feeders
- **WHEN** callers inspect `FLOWGUARD_ROUTE_API`
- **THEN** the registry MUST include only public owner route groups and
  explicitly proven public facades
- **AND** internal feeder groups MUST be discoverable only through advanced or
  full helper inventories

#### Scenario: Starter API is direct-entry only
- **WHEN** callers inspect `ROUTE_STARTER_API`
- **THEN** each key MUST represent a direct public owner route or a documented
  direct public facade
- **AND** delegated modes, feeders, and data helpers MUST NOT appear as starter
  keys

### Requirement: Advanced helper availability does not imply route ownership
The API registry SHALL keep advanced helper exports distinct from public route
ownership.

#### Scenario: Helper remains exported
- **WHEN** an internal feeder helper remains in `MODELING_HELPER_API`,
  `REPORTING_HELPER_API`, `EVIDENCE_API`, or `ROUTE_ADVANCED_API`
- **THEN** tests MUST NOT infer that the helper is a public route starter

### Requirement: Route profile metadata drives public discovery
The API registry SHALL derive or validate public route discovery against
route-profile role metadata.

#### Scenario: Role mismatch is blocked
- **WHEN** a route is listed as public but its route profile is not
  `public_owner`
- **THEN** FlowGuard self-maintenance MUST report a route registry mismatch

### Requirement: Primary path route is discoverable
FlowGuard SHALL expose primary-path authority helpers through route-scoped API
groups, route starter APIs, templates, and CLI surfaces.

#### Scenario: Starter API exposes review helper
- **WHEN** callers inspect `ROUTE_STARTER_API["primary_path_authority"]`
- **THEN** the group SHALL include the public plan/report types and
  `review_primary_path_authority`

#### Scenario: API surface exports route helpers
- **WHEN** callers import the public FlowGuard package
- **THEN** primary-path authority helper names SHALL be present in
  `flowguard.__all__` and importable from `flowguard`

### Requirement: Primary path route does not expose internal helpers as owners
The API registry SHALL keep primary-path authority public owner helpers
separate from any internal coverage or formatting helpers.

#### Scenario: Internal helper is not starter route
- **WHEN** an internal coverage helper exists
- **THEN** it SHALL NOT appear as a direct public starter route owner unless it
  has explicit facade evidence

### Requirement: Process optimization is exported only through the existing process API group
The public API SHALL expose at most five compact process-optimization dataclasses and one canonical review function through the existing DevelopmentProcessFlow group: an inspectable equivalence contract, candidate, repair group, decision, report, and `review_process_optimization`. The standalone strategy API group, former `review_development_process_strategy`, cost vector, campaign/observation/cluster/hypothesis/batch/reevaluation/dependency-graph types, six-policy constants, rollout constants, Pareto helpers, and former projection helpers SHALL NOT be public or current runtime authority.

#### Scenario: API discovery
- **WHEN** a caller inspects the DevelopmentProcessFlow route API group
- **THEN** the five compact records and one optimization review are discoverable under the existing DPF group without a new public route id

#### Scenario: Retired strategy symbol remains exported
- **WHEN** any retired strategy type, constant, helper, review, or API group remains in `flowguard.__all__` or public route discovery
- **THEN** API registry validation fails

### Requirement: Portable Verification API Cohort
The public API registry SHALL expose the portable schema, canonical identity, interpreter, model checker, refinement checker, and composition checker as one versioned ownership cohort.

#### Scenario: Public API cohort is complete
- **WHEN** a supported portable verification symbol is exported
- **THEN** it is present in the registry, import facade, documentation, and API parity tests

#### Scenario: Internal helper remains private
- **WHEN** an implementation helper is not part of the declared cohort
- **THEN** it is absent from the public registry and package facade

### Requirement: Bounded system composition is one portable-verification API cohort
The public API registry SHALL expose current system schema/artifact/report types and the canonical `check_system_composition` entrypoint inside portable verification discovery. Internal graph-construction, state-expansion, and trace-projection helpers MUST remain private.

#### Scenario: Public system symbol is exported
- **WHEN** a supported bounded system-composition name is present in the package facade
- **THEN** it is registered, documented, importable, and covered by exact API parity tests

#### Scenario: Internal compiler helper exists
- **WHEN** a helper only constructs joint states or rewrites portable traces
- **THEN** it is absent from public route-starter and package API cohorts

### Requirement: WorkContext is the sole public planning-context API cohort
FlowGuard SHALL expose provider-neutral, project-bounded, content-addressed,
read-only planning context through one `flowguard.work_context` owner, one
`WORK_CONTEXT_API` registry cohort, one `API_SURFACE["work_context"]` entry,
one `work-context` CLI command, and one `work-context-template` template
command backed by `work_context_template_files`. The API, CLI, and templates
SHALL use the same canonical WorkContext artifact roles, provider identity,
adapter identity, content fingerprints, currentness rules, and
language-neutral JSON schema.

#### Scenario: Public WorkContext cohort is inspected
- **WHEN** a caller inspects `flowguard.__all__`, `WORK_CONTEXT_API`,
  `API_SURFACE`, route discovery, CLI parsers, and public template commands
- **THEN** every supported WorkContext public symbol is present in the exact
  declared cohort
- **AND** all of those surfaces delegate to the same canonical WorkContext
  model and review owner

#### Scenario: Declared provider adapter is unavailable
- **WHEN** a WorkContext request names an unregistered adapter, a missing
  declared root, or unsupported provider artifacts
- **THEN** the sole WorkContext API returns an explicit
  unavailable/unsupported result
- **AND** it does not select an OpenSpec-specific reader, declared-file
  fallback, compatibility alias, or alternate success path

#### Scenario: WorkContext templates are generated
- **WHEN** a caller invokes the public WorkContext template command
- **THEN** the generated model, runner, and notes use only current
  `work_context` names, fields, API helpers, and CLI commands
- **AND** no generated path or content refers to `spec_context`,
  `SpecContext`, or a spec work-package execution bridge

### Requirement: SpecContext surfaces are removed by direct replacement
The WorkContext introduction SHALL directly remove the
`flowguard.spec_context` module, `SPEC_CONTEXT_API`,
`API_SURFACE["spec_context"]`, `SpecContext` types and readers, the
`spec-context` CLI, the `spec-context-template` command,
`spec_context_template_files`, generated `.flowguard/spec_context` paths, and
SpecContext-specific documentation templates. No deprecated export, alias,
forwarder, compatibility reader, fallback parser, dual emission, or migration
runtime SHALL preserve those surfaces.

#### Scenario: Retired Python surface is imported
- **WHEN** a caller imports a retired SpecContext type, helper, module,
  registry group, or template helper
- **THEN** the retired name is absent rather than forwarding to WorkContext
- **AND** current API parity checks require the corresponding WorkContext
  surface where applicable

#### Scenario: Retired CLI or template command is invoked
- **WHEN** a caller invokes `spec-context`, `spec-context-template`, or a
  generated SpecContext runner
- **THEN** the retired command or path is unavailable
- **AND** FlowGuard does not silently reinterpret it as `work-context` or
  `work-context-template`

#### Scenario: Installed or generated surface is scanned
- **WHEN** source, templates, generated artifacts, public docs, and installed
  consumer projections are checked after replacement
- **THEN** the governed inventory contains zero current SpecContext public
  surfaces
- **AND** exactly one WorkContext API, CLI, and template owner remains

### Requirement: UI consistency helpers extend the existing UI Flow Structure API group
FlowGuard SHALL expose product-scope UI consistency types and review helpers
through the existing `ui_flow_structure` public owner group. The helpers SHALL
remain discoverable through `UI_FLOW_STRUCTURE_ROUTE_API`,
`FLOWGUARD_ROUTE_API["ui_flow_structure"]`,
`ROUTE_ADVANCED_API["ui_flow_structure"]`, and the flat public package exports
without creating a Product Design Language or Functional Path Reuse API group.

#### Scenario: Extended UI consistency helper is exported
- **WHEN** a public UI consistency type or review helper is added for this
  change
- **THEN** its name MUST be present in `flowguard.__all__` and importable from
  `flowguard`
- **AND** it MUST be discoverable through the existing `ui_flow_structure`
  route group

#### Scenario: Starter surface remains compact
- **WHEN** the extended UI consistency API is registered
- **THEN** `ROUTE_STARTER_API["ui_flow_structure"]` MUST remain a compact direct
  entry to the existing UI Flow Structure owner
- **AND** advanced data types and helpers MUST remain available through the
  existing advanced or full UI group instead of becoming starter routes

#### Scenario: Parallel UI route is rejected
- **WHEN** API registry changes introduce a `product_design_language`,
  `functional_path_reuse`, or equivalent parallel public owner key
- **THEN** API surface and self-maintenance validation MUST report a route
  registry mismatch

### Requirement: Extended existing models preserve public compatibility
FlowGuard SHALL extend the existing UI Flow Structure, behavior identity, path
binding, transition, and evidence model families rather than publishing
replacement wrapper models. Existing public type and helper names SHALL remain
importable, and additive fields SHALL preserve existing valid construction and
serialization behavior except where this change explicitly defines the
singular primary-path migration.

#### Scenario: Existing constructor omits additive fields
- **WHEN** existing consumer code constructs an extended public model using a
  previously valid argument set that does not rely on ambiguous plural primary
  paths
- **THEN** the construction MUST remain valid with deterministic defaults for
  the additive fields

#### Scenario: Existing public import remains available
- **WHEN** a model family gains UI consistency, business-intent, path-binding,
  inventory, or evidence fields
- **THEN** its existing public class and review-helper names MUST remain in the
  flat exports and their existing route-scoped API groups

#### Scenario: Compatibility surface does not become an owner
- **WHEN** a migration adapter accepts a legacy deterministic one-item input or
  projects an extended model into an existing public shape
- **THEN** the adapter MUST delegate to the existing owner model and reviewer
- **AND** the API registry MUST NOT expose the adapter as a new route owner

### Requirement: UI consistency API adds no CLI command
The FlowGuard API registry and CLI discovery surfaces MUST keep UI consistency
review inside the existing `ui_flow_structure` route and existing commands.
This change MUST NOT add a Product Design Language, Functional Path Reuse, or
UI consistency CLI command.

#### Scenario: CLI command inventory is inspected
- **WHEN** CLI and API surface tests inspect the commands added by this change
- **THEN** no new product-language, path-reuse, or UI-consistency command name
  is present
- **AND** Python callers use the existing `ui_flow_structure` public helpers

### Requirement: Plane-aware BCL APIs stay in existing route groups
The public API registry SHALL export behavior-plane constants, actor-kind constants, relation/lookup-binding types, canonical ledger load/write helpers, lookup query/hit/report types, and query functions through existing behavior-commitment or existing-preflight API groups.

#### Scenario: New public type lacks route ownership
- **WHEN** a plane-aware public export is added without membership in an existing API group
- **THEN** API registry review SHALL report an unowned public export

### Requirement: Query command adds no route id
The read-only `behavior-commitment-query` CLI SHALL be owned by the existing BCL/preflight API surface and SHALL NOT create a new public route or self-maintenance profile.

#### Scenario: Route inventory remains stable
- **WHEN** the query command is registered
- **THEN** the public route id inventory SHALL remain unchanged
- **AND** self-maintenance SHALL continue to use the existing BCL and preflight owners

### Requirement: Serialization and CLI JSON are stable
Public plane/relation/lookup reports SHALL serialize deterministically and expose canonical machine values independent of localized display wording.

#### Scenario: Same ledger and query repeat
- **WHEN** the same canonical ledger and query are executed twice
- **THEN** ordered hit ids, scores, reasons, relation roles, and ledger fingerprint SHALL be stable

### Requirement: API Registry Reflects Thin Breaking Schema
FlowGuard's public API registry SHALL export only the current thin schema
types and names. It MUST NOT preserve removed dataclass fields, former helper
types, aliases, converters, or fallback readers as public compatibility
success paths.

#### Scenario: Thin gate type exported
- **WHEN** callers import risk-evidence-ledger helpers from `flowguard`
- **THEN** the current `RiskEvidenceGate` type is exported with its owner
  helpers

#### Scenario: Removed aliases absent
- **WHEN** API-surface tests inspect first-read and full exports
- **THEN** removed compatibility names and old field aliases are absent

### Requirement: Understanding status extends the existing kernel API group
The public understanding-status types and functions SHALL be registered under the existing model-first kernel owner. They SHALL NOT create a new public route or skill, and registry, import, serialization, and CLI projections SHALL remain in parity.

#### Scenario: Status API is added to another route
- **WHEN** the public status surface appears under a new or unrelated route owner
- **THEN** registry validation fails with an ownership mismatch

#### Scenario: CLI field lacks API serialization parity
- **WHEN** a status field is exposed through the CLI but omitted from the public serialized API result
- **THEN** parity validation fails

### Requirement: Implementation blueprint APIs belong to the existing kernel owner
Public implementation-inventory, model-binding, blueprint-qualification, and deterministic-projection APIs SHALL be registered as one cohort under the existing model-first kernel owner. They SHALL NOT create a new route, skill, mutable authority head, or compatibility alias.

#### Scenario: Blueprint API is registered as a new public route
- **WHEN** registry metadata assigns the blueprint cohort to a new route identity
- **THEN** public API topology validation fails

#### Scenario: Public import and registry differ
- **WHEN** a blueprint symbol is publicly importable but absent from its registered cohort, or the registry lists a missing symbol
- **THEN** API parity validation fails

### Requirement: Project-neutral blueprint APIs extend the existing kernel cohort
The public API registry SHALL expose provider-neutral target-system descriptor, provider declaration/registry/result, frozen snapshot, compiler, understanding projection, canonical target projection, and project-specialized inventory/binding/qualification APIs through the existing FlowGuard kernel API cohort. The target and Python-project projection APIs SHALL return the same existing `CanonicalBlueprintProjection` envelope and use its writer/verifier rather than introducing a second export authority. These APIs SHALL operate on explicit target definitions and native provider evidence without introducing a new public route, `DNA` skill, or alternate authority cohort.

#### Scenario: A consumer builds a non-Python target blueprint
- **WHEN** a consumer supplies a strict target descriptor, frozen provider evidence, the current native observation/authority report set, and an explicit affected or whole scope
- **THEN** the public qualifier mechanically derives the canonical provider-neutral layers, gaps, readiness, and admission result
- **AND** caller-authored downstream layer, gap, status, or admission rows are not a public qualification input
- **AND** the consumer does not import FlowGuard's Python self-blueprint preset

#### Scenario: FlowGuard builds its own blueprint
- **WHEN** FlowGuard invokes self-blueprint qualification
- **THEN** its software preset delegates to the same public target-system and project-neutral APIs
- **AND** no duplicate FlowGuard-only builder owns the generic semantics

#### Scenario: A generic API name is missing or duplicated
- **WHEN** registry compilation finds an expected target-system or blueprint API absent, duplicated, or assigned to a conflicting route group
- **THEN** the API-registry check fails with the exact name and owner conflict
- **AND** package export cannot claim the provider-neutral cohort current

#### Scenario: A target export projection is requested through Python
- **WHEN** a consumer supplies the exact typed descriptor, frozen evidence, complete native report set, and native qualification report
- **THEN** `canonical_target_system_blueprint_projection` SHALL return the existing content-addressed projection type with the exact audit-input and readiness identities
- **AND** no caller-authored status or alternate envelope API SHALL be registered

### Requirement: API results expose one canonical layered-understanding result
Project-neutral API results SHALL expose the deepest proven understanding layer, per-layer statuses, exact findings and owners, and implementation-admission status when supplied by its native owner. Construction, inventory, audit, qualification, affected-neighborhood, and projection APIs SHALL consume and return the same canonical blueprint-readiness semantics.

#### Scenario: Static blueprint is complete
- **WHEN** all static layers pass
- **THEN** the API reports static blueprint complete with `static_blueprint` as the deepest proven layer

#### Scenario: Caller supplies an undeclared alternate status field
- **WHEN** a strict current API payload contains a status field outside the canonical layered-understanding schema
- **THEN** the payload is rejected as non-current rather than routed to an alternate qualification branch

### Requirement: Static manifest qualification remains an internal child result
The static manifest consistency report SHALL be derived only by its private qualifier, SHALL NOT be exported from the root package or registered implementation-blueprint API cohort, and SHALL expose a manifest-specific status, readiness boolean, layers, findings, and exact claim boundary without a generic success field or completion sentence.

#### Scenario: Caller attempts to construct or publish manifest success
- **WHEN** a caller constructs the internal report directly or looks up either the retired report name or its current internal type through the public API
- **THEN** direct construction SHALL fail and the public lookup SHALL be absent
- **AND** project or target readiness SHALL remain the only owner of whole readiness and implementation admission

### Requirement: Retired historical routes leave no public or compatibility surface
When a route or behavior is intentionally retired, FlowGuard SHALL remove its route registry entry, starter/advanced group, top-level exports, template helper, CLI command, documentation cohort, and public commitment. A compact shared data type may remain only under its canonical consuming owner and MUST NOT preserve the retired route identity.

#### Scenario: Public registry is inspected after retirement
- **WHEN** a retired Model Angle, Maintenance Scan, standalone Model Similarity, duplicate non-canonical route template, or retired model owner name is inspected
- **THEN** it is absent from public route discovery and package exports

#### Scenario: Retired name is invoked
- **WHEN** a caller imports or invokes a retired name
- **THEN** the operation fails visibly without aliasing, forwarding, translating, or falling back to a current owner

#### Scenario: Advanced consumer needs an internal type
- **WHEN** a small typed relation or maintenance-obligation carrier remains necessary
- **THEN** it is available through the canonical owner module only and does not recreate the retired public route

#### Scenario: Explicit risk-template work is inspected
- **WHEN** a caller explicitly requests risk-template reuse, publication, harvest, or harvest review
- **THEN** the current risk-template library APIs, template surface, and CLI commands remain available
- **AND** their presence MUST NOT reintroduce them into the universal modeling hot path
