# flowguard-skill-kernel Specification

## Purpose
This capability defines FlowGuard's Flowguard Skill Kernel behavior and the evidence required to use it safely in AI-agent maintenance workflows.
## Requirements
### Requirement: Skill Kernel remains compact and route-oriented
The public `flowguard` Skill SHALL keep its main `SKILL.md` focused on
triggering, hard gates, route selection, its internal model-first workflow,
workflow skeleton, and resource mapping.

#### Scenario: Oversized work receives a soft split hint
- **WHEN** a model, test, script, module, or command is becoming large, slow, or
  hard to follow
- **THEN** the Skill suggests considering whether a parent/child split would
  improve maintainability or verification
- **AND** the Skill does not require fixed runtime thresholds or mandatory
  splitting

#### Scenario: External planning artifacts remain optional
- **WHEN** a compatible planning or specification artifact exists
- **THEN** the Skill may inspect it as optional context
- **AND** FlowGuard remains usable without any external planner

### Requirement: Sub-protocol ownership is explicit
FlowGuard SHALL distinguish agent sub-protocols from package helper APIs.

#### Scenario: API helper is not a sub-skill
- **WHEN** the route map lists `RiskIntent`, templates, property factories, or
  mesh review functions
- **THEN** it identifies them as helper APIs rather than standalone agent
  skills

### Requirement: Hard gates are not delegated away
The Skill Kernel SHALL preserve non-negotiable rules even when detailed
procedures move into references.

#### Scenario: Real package gate remains visible
- **WHEN** FlowGuard applies to repository work
- **THEN** the kernel still requires verifying the real package import and
  forbids fake mini-framework substitutes

#### Scenario: Skipped checks stay visible
- **WHEN** a model, replay, test, release, or adoption check is skipped
- **THEN** the kernel requires a reason and prevents treating the skipped check
  as a pass

### Requirement: Known-bad modularization hazards are modeled
FlowGuard SHALL include executable evidence for Skill Kernel modularization.

#### Scenario: Missing route fails
- **WHEN** a modular Skill removes a required ModelMesh, TestMesh,
  StructureMesh, model-miss, long-check, conformance/adoption, or framework
  upgrade route
- **THEN** the rollout model reports a violation

#### Scenario: Heavy checks over-trigger
- **WHEN** the kernel requires heavy framework checks for ordinary narrow
  project work
- **THEN** the rollout model reports a violation

#### Scenario: Helper APIs become fake sub-skills
- **WHEN** package helper APIs are classified as independently triggerable
  sub-skills
- **THEN** the rollout model reports a violation

### Requirement: Kernel requires target-project adoption rule
The FlowGuard Skill Kernel SHALL tell agents that real FlowGuard use in another
repository must check whether the target project carries a FlowGuard
`AGENTS.md` adoption block.

#### Scenario: Target project lacks FlowGuard AGENTS block
- **WHEN** the kernel is used for non-trivial FlowGuard work in another
  repository
- **AND** the target project lacks a FlowGuard managed `AGENTS.md` block
- **THEN** the kernel instructs the agent to add or update the block from the
  canonical FlowGuard snippet unless the user requested read-only work

#### Scenario: Read-only work does not force writes
- **WHEN** the user explicitly requests read-only analysis
- **THEN** the kernel may report the missing AGENTS block as a gap without
  writing project files

### Requirement: Kernel references use compact handoff stubs for satellite-owned protocols
The FlowGuard Skill Kernel SHALL avoid carrying full duplicate copies of
satellite-owned reference protocols.

#### Scenario: Duplicate protocol copy is detected
- **WHEN** a kernel reference file is byte-for-byte identical to a satellite
  reference file
- **THEN** skill documentation tests fail or require the kernel copy to become
  a compact handoff stub

#### Scenario: Handoff stub remains useful
- **WHEN** an agent opens a kernel-side handoff stub
- **THEN** it states that the satellite owns the detailed protocol
- **AND** it names the satellite skill and detailed reference file to load next

### Requirement: Skill kernel keeps template library compact
The FlowGuard skill kernel SHALL expose risk-template reuse as a compact
pre/post model gate without moving the full template-library protocol into the
first-read skill body.

#### Scenario: Kernel first read stays compact
- **WHEN** the model-first skill kernel is read
- **THEN** it states the minimum valuable model gate and template search/harvest rule without embedding long public template catalogs

#### Scenario: Detailed protocol remains referenced
- **WHEN** an agent needs implementation detail for template library behavior
- **THEN** the kernel points to route docs, helpers, or CLI commands rather than expanding every field inline

### Requirement: Kernel identifies the skill-suite entrypoint
The public `flowguard` skill SHALL identify itself as the default entrypoint
for the FlowGuard skill suite. `model-first-function-flow` MAY remain an
internal behavior route id but SHALL NOT be installed as another public skill.

#### Scenario: Kernel SKILL is read first
- **WHEN** an AI agent opens the installed public
  `$CODEX_HOME/skills/flowguard/SKILL.md`
- **THEN** it MUST learn that the sibling FlowGuard skills under
  `$CODEX_HOME/skills/` are part of the same package-authority projection
- **AND** it MUST NOT treat a Python package import as proof that the AI-agent
  skill suite is installed

### Requirement: Kernel separates check execution from skill availability
The kernel SHALL distinguish skill availability from executable check
availability.

#### Scenario: Check engine is unavailable
- **WHEN** the agent can read FlowGuard skills but cannot run executable checks
- **THEN** it MUST report executable evidence as blocked or scoped
- **AND** it MUST still preserve the route decision and skill-suite handoff
  boundary

### Requirement: Compact Kernel Entrypoint
The kernel skill SHALL implement the standard entrypoint contract within a target budget of 120 lines. Detailed route inventories and specialist protocols SHALL be directly referenced rather than copied into the kernel. Any budget exception MUST be explicit, test-backed, and SHALL NOT weaken required headings or hard gates.

#### Scenario: Route table expansion exceeds budget
- **WHEN** generated or manually copied route details push the kernel beyond its approved budget without an exception
- **THEN** prompt-budget validation fails and directs the details to a routed reference

### Requirement: Generated Route Index
The kernel route index SHALL be generated from or parity-checked against the canonical route registry and suite inventory. It MUST identify public owner, delegated, and kernel-owned internal routes without inventing a new owner.

#### Scenario: New satellite is registered
- **WHEN** a canonical public satellite is added to the inventory and route registry
- **THEN** route-index check fails until the kernel projection includes the new route

### Requirement: Strict Broad Claim Boundary
The kernel SHALL state that missing, stale, skipped, `not_run`, `progress_only`, `scoped`, or `pass_with_gaps` evidence cannot support a broad done, full-governance, release, archive, or publication claim.

#### Scenario: Child result has gaps
- **WHEN** a required child route returns `pass_with_gaps`
- **THEN** the kernel output preserves that status and blocks broad closure

### Requirement: The default kernel recognizes bounded system-composition triggers
The default FlowGuard skill SHALL select bounded system composition when a non-trivial change affects multiple current models and involves event delivery, business identity, retry, ordering, shared resources, cache authority, external confirmation, atomicity, compensation, or an owner-bound system property. It SHALL route discovery, case generation, evidence, and process work to their existing satellite owners while retaining one canonical execution owner.

#### Scenario: Multiple models are merely colocated
- **WHEN** models have no declared interaction or shared property within the task boundary
- **THEN** the kernel does not create a composite slice solely because the model count is greater than one

#### Scenario: Local green could hide an interaction
- **WHEN** current local evidence cannot decide a cross-model event/resource/retry property
- **THEN** the kernel requests exact composite context and executable evidence rather than treating token closure as system proof

### Requirement: Kernel outputs preserve candidate model-delta status
Kernel guidance SHALL expose affected model/component ids, fingerprints, slice/binding status, shared identities/resources, system-property owner, finite bounds, composite evidence status, minimal trace target, and model-delta disposition. Proposed deltas MUST NOT be labeled current until accepted by the owner.

#### Scenario: Candidate relation is inferred
- **WHEN** code or topology suggests a relation that is not current authority
- **THEN** the output records `model_delta_status=proposed` and blocks broad use of that relation

### Requirement: Kernel coordinates sufficiency and admission through native owners
For non-trivial production changes, the kernel SHALL coordinate current-model preflight, triggered specialist contributions, task-local Model Maturation, DevelopmentProcessFlow admission, admitted Code Structure Recommendation, and downstream risk/closure without taking over their native semantics.

#### Scenario: Kernel cannot self-rate understanding
- **WHEN** an agent provides prose stating that it understands the system
- **THEN** the kernel MUST ignore that prose as sufficiency evidence and require the current task-local maturation result

#### Scenario: Specialist remains native owner
- **WHEN** a UI, field, behavior, mesh, alignment, or test trigger fires
- **THEN** the kernel MUST consume the specialist's typed contribution and MUST NOT reinterpret or replace the specialist's native result

### Requirement: Kernel routes target-system blueprints independently of language
The FlowGuard kernel SHALL route blueprint work by target boundary, provider capabilities, required understanding layers, and affected behavior rather than by a Python-only software branch. Existing satellite owners SHALL retain their native semantics.

#### Scenario: Target is a mixed workflow and service
- **WHEN** the task requires blueprint reasoning across a workflow and an external service contract
- **THEN** the kernel SHALL compose the required provider and satellite contributions under one target-system request
- **AND** it SHALL NOT create a new DNA skill or a language-specific core route

### Requirement: The kernel exposes one canonical blueprint model
The FlowGuard kernel SHALL coordinate target-system blueprint work through the existing implementation inventory, model, structure, test, resource, intent, topology, and process owners. It SHALL use that one owner graph with direct typed gaps and SHALL NOT add a DNA mode, duplicate authority head, compatibility reader, or generic fallback owner.

#### Scenario: Whole blueprint task is explicit
- **WHEN** task facts explicitly request whole-target blueprint qualification
- **THEN** the kernel SHALL coordinate the existing native owners and return their exact layer results
- **AND** it SHALL NOT create a parallel blueprint format

### Requirement: Target product roles remain inside target models
The kernel MAY model actors, permissions, and roles declared by a target software or workflow, but SHALL NOT promote those target-specific roles into FlowGuard-global role catalogs or blueprint admission requirements.

#### Scenario: Approval workflow declares an administrator
- **WHEN** a target workflow contains administrator and requester roles
- **THEN** those roles SHALL remain members of that workflow model
- **AND** unrelated targets SHALL NOT inherit them

### Requirement: The compact kernel follows the canonical DNA path without universal template work
The FlowGuard skill kernel SHALL lead an AI from target/adoption identity to the canonical blueprint owner, affected topology, required specialist route, executable negative cases, and current evidence. Template search or harvest SHALL appear only when the task explicitly requests reuse/publication or current evidence identifies a stable reusable cross-project pattern.

#### Scenario: Ordinary target modeling or maintenance begins
- **WHEN** no explicit template-reuse/publication request or stable reusable pattern is present
- **THEN** the kernel proceeds through the canonical DNA path without requiring template search, no-match prose, or harvest closure

#### Scenario: Reusable cross-project pattern is identified
- **WHEN** current evidence demonstrates a bounded pattern intended for reuse beyond the target project
- **THEN** the kernel routes to the template-library owner and preserves its separate evidence

### Requirement: Kernel exposes compact path quality without a new route
The FlowGuard skill kernel SHALL request the lightweight path-quality result for every new or materially changed model and expose only the current conclusion, trigger state, unresolved gap, and detailed-evidence reference needed by the task. It SHALL keep deep review conditional inside ModelMaturation and SHALL NOT present reconstruction, global optimization, or a separate path-optimization skill as ordinary work.

#### Scenario: Lightweight result is sufficient
- **WHEN** the result is current `single_clear_path` with no deep trigger
- **THEN** kernel guidance proceeds through the selected specialist using the compact summary

#### Scenario: Deep result is required
- **WHEN** a current trigger requires finite candidate comparison
- **THEN** guidance names the exact affected model boundary and bounded conclusion vocabulary
- **AND** it does not add a public route or load unrelated model details
