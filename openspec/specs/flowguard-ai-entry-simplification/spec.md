# flowguard-ai-entry-simplification Specification

## Purpose
This capability defines FlowGuard's Flowguard Ai Entry Simplification behavior and the evidence required to use it safely in AI-agent maintenance workflows.
## Requirements
### Requirement: FlowGuard exposes a thin default AI entry path

FlowGuard guidance SHALL present the smallest useful workflow before advanced
routes or helper inventories. The default AI entry path SHALL also tell agents
that old FlowGuard artifacts, models, tests, and guidance should be upgraded or
blocked at the boundary, not preserved as long-lived runtime compatibility.

#### Scenario: Agent starts ordinary risky work

- **GIVEN** a task where order, state, side effects, or evidence freshness may
  matter
- **WHEN** an agent reads the kernel, AGENTS snippet, README, or API surface
  guidance
- **THEN** it sees a compact default path before the advanced route map:
  identify the risky boundary, model `Input x State -> Set(Output x State)`,
  add one invariant or scenario, run the check, inspect counterexamples, and
  escalate only when a named risk requires it

#### Scenario: Tiny or read-only work stays lightweight

- **GIVEN** a task that is a trivial copy edit, formatting-only change, direct
  command answer, or read-only explanation with no behavior/state/process risk
- **WHEN** an agent evaluates FlowGuard applicability
- **THEN** the guidance allows `skip_with_reason` without creating a model or
  loading advanced satellites

#### Scenario: Agent enters older FlowGuard repository

- **GIVEN** a repository has a FlowGuard adoption record older than the
  installed FlowGuard package
- **WHEN** an agent follows the default project-entry guidance
- **THEN** the guidance routes the agent to project upgrade and artifact/model
  upgrade scanning
- **AND** it does not instruct the agent to keep old fields, aliases, or
  wrappers for backward compatibility

### Requirement: Advanced FlowGuard routes are escalation paths

FlowGuard guidance SHALL keep mature satellite skills discoverable while
framing them as explicit escalation paths, not mandatory default reading for
every task.

#### Scenario: Advanced route is needed

- **GIVEN** a task clearly involving UI topology, test hierarchy, model/test
  alignment, model hierarchy, structure refactor, process/release freshness,
  architecture reduction, existing-model ownership, or model-miss repair
- **WHEN** an agent reaches the escalation section
- **THEN** the matching satellite skill remains named and searchable
- **AND** the route's trigger is described in concise terms

#### Scenario: Advanced route is not needed

- **GIVEN** an ordinary fit-for-risk FlowGuard model is enough
- **WHEN** an agent reads the default entry
- **THEN** helper APIs, proof ledgers, benchmark suites, and deep mesh routes
  are presented as optional escalation, not prerequisites

### Requirement: Public and internal surfaces remain separated

FlowGuard public guidance SHALL distinguish the ordinary product path from
internal maintenance and release-hardening machinery.

#### Scenario: User reads public product docs

- **GIVEN** a user wants to try FlowGuard on a project
- **WHEN** they read public-facing docs
- **THEN** the docs explain that ordinary use starts with the thin default path
- **AND** internal maintenance suites, benchmark/problem corpus runs, and deep
  release evidence are not presented as mandatory first steps

### Requirement: Prompt hot paths stay compact while implementation surfaces shrink

FlowGuard SHALL keep kernel, AGENTS snippet, and satellite skill hot paths under
their prompt budgets while allowing package implementation surfaces behind those
prompts to be split, grouped, or table-driven.

#### Scenario: Prompt budget remains enforced

- **WHEN** FlowGuard implementation surfaces are simplified
- **THEN** skill documentation tests still enforce kernel, AGENTS snippet, and
  satellite hot-path budgets

#### Scenario: Implementation split does not grow prompt text

- **WHEN** template, API, or evidence structures are reorganized
- **THEN** the AI-facing route shells do not need new long-form protocol text

### Requirement: Satellite topology stays current

FlowGuard tests and docs SHALL prevent stale satellite-count wording from
surviving after route topology changes.

#### Scenario: Satellite count changes

- **GIVEN** the repository contains a set of `flowguard-*` satellite skill
  directories
- **WHEN** skill documentation tests run
- **THEN** they compare guidance text against the current repository topology
- **AND** stale fixed-count wording such as an obsolete "seven satellites"
  claim is reported before release confidence is claimed

### Requirement: Sync evidence covers local install, installed skills, shadow workspace, and git version
FlowGuard local release-quality synchronization SHALL verify all user-facing
local surfaces after guidance changes. Installed Codex skill verification SHALL
include content-level parity for affected repository-managed skills, including
critical route rows and handoff wording, rather than relying only on FlowGuard
package version, project audit, or source/shadow workspace sync.

#### Scenario: AI entry simplification is finalized
- **GIVEN** docs, skills, tests, and OpenSpec artifacts are updated
- **WHEN** the change is finalized locally
- **THEN** validation includes OpenSpec checks, focused docs/skill tests,
  practical model or regression checks, editable install verification,
  installed skill sync verification, shadow workspace import verification, and
  a scoped local git commit/tag when validation passes
- **AND** unrelated peer-agent changes remain unstaged unless they are part of
  this change

#### Scenario: Installed skill content drifts from repository source
- **WHEN** repository-managed FlowGuard skill prompts contain newer route or
  handoff guidance than the installed Codex skill root
- **THEN** completion evidence MUST report active AI behavior as unsynced until
  the installed skill files are refreshed and content parity is verified

#### Scenario: Version checks pass but skill text is stale
- **WHEN** package version, schema version, project audit, and shadow workspace
  checks pass
- **AND** an affected installed `SKILL.md` differs from the repository-managed
  `SKILL.md`
- **THEN** FlowGuard SHALL treat installed AI guidance evidence as incomplete
  for the affected skill until the text difference is resolved or explicitly
  scoped out

### Requirement: AI hot paths prefer structured handoff outputs
FlowGuard AI-facing hot paths SHALL instruct agents to read structured
SummaryReport ledger, maintenance obligations, maintenance scan actions, and
revalidation recommendations before manually inferring the next route from
prompt prose.

#### Scenario: Summary report has route-owned gaps
- **WHEN** an agent finishes a model-first check and the summary report has
  route-owned gaps
- **THEN** the hot-path guidance SHALL direct the agent to the structured
  action hints and maintenance scan handoff before broad confidence claims

#### Scenario: No structured handoff is available
- **WHEN** a legacy report lacks structured handoff fields
- **THEN** the agent may fall back to the compact route table without treating
  the missing structure as validation evidence

### Requirement: Compact route profiles
FlowGuard AI entry surfaces SHALL expose compact route profiles that identify route id, trigger, minimal inputs, outputs, evidence owner, and next actions before exposing broad helper lists.

#### Scenario: Route-first API lookup
- **WHEN** an AI consumer asks how to perform a FlowGuard maintenance task
- **THEN** the API documentation and public route helpers SHALL point to the compact route profile for that task

#### Scenario: Full helper list remains available
- **WHEN** a consumer needs the full helper API
- **THEN** the full helper lists SHALL remain available behind the route-first entry surface

### Requirement: Flat surface warning
FlowGuard AI guidance SHALL warn against treating `__all__`, `MODELING_HELPER_API`, or broad helper lists as the first planning surface.

#### Scenario: Large helper API exists
- **WHEN** the helper API contains many exported names
- **THEN** docs and tests SHALL continue to prefer route profile discovery for AI usage

### Requirement: AI guidance asks open-ended model-angle questions
FlowGuard AI entry guidance SHALL ask agents to consider additional model
angles without presenting known FlowGuard routes as a closed checklist.

#### Scenario: Agent starts non-trivial model-first work
- **WHEN** an agent starts a non-trivial feature, workflow, bug repair, prompt, process, or model change
- **THEN** compact guidance MUST ask what the current model sees, what it may miss, what failure would be missed, and whether to reuse, extend, create, split, defer, scope out, or ask a human

#### Scenario: Known routes are examples
- **WHEN** AI guidance mentions fields, information flow, authority, evidence freshness, or parent-child handoffs
- **THEN** the guidance MUST state that those examples are route hints rather than the full set of valid model angles

### Requirement: AI entry guidance points to field replacement handoffs
FlowGuard AI entry guidance SHALL point agents to structured field lifecycle
and replacement disposition evidence without adding a parallel session runner
or a long prompt checklist.

#### Scenario: Agent starts field-heavy work
- **WHEN** an agent starts work involving fields, schemas, modes, feature
  flags, prompt/config surfaces, or feature replacement
- **THEN** compact guidance MUST direct the agent to existing model preflight,
  field lifecycle mesh, model-code-test alignment, development freshness, and
  closure gates

#### Scenario: Entry guidance does not replace owner routes
- **WHEN** field lifecycle review reports missing tests, code owner gaps,
  old-field disposition gaps, stale evidence, or oversized field groups
- **THEN** AI guidance MUST route to the existing owner route instead of
  claiming the entry path solved the gap

### Requirement: Reference prompt surfaces remain layered
FlowGuard AI guidance SHALL keep long examples, agent prompt templates, and
route-specific protocol detail behind explicit reference handoffs rather than
embedding them in first-read or core second-read surfaces.

#### Scenario: Core modeling reference points outward
- **WHEN** an agent reads the core modeling protocol for ordinary FlowGuard work
- **THEN** satellite trigger detail is represented as a compact handoff table
- **AND** the agent can load the matching satellite protocol only after the
  route is selected

#### Scenario: Long templates are separated
- **WHEN** a protocol needs a reusable agent prompt template
- **THEN** the primary protocol points to a template reference file
- **AND** the long template body is not embedded in the primary protocol

### Requirement: Guidance fold-down preserves synchronization evidence
FlowGuard guidance fold-down SHALL be finalized only after source, editable
install behavior, installed Codex skill content, shadow workspace imports, and
local git evidence are checked after the final prompt/reference edits.

#### Scenario: Fold-down is finalized locally
- **WHEN** guidance reference compression is ready to claim done
- **THEN** validation includes OpenSpec checks, FlowGuard model checks, focused
  skill docs tests, broader regression, editable install verification,
  installed skill parity, shadow workspace verification, and local git status
  or commit/tag evidence

### Requirement: Route-first AI surface exposes basic and full paths
FlowGuard SHALL present route-scoped starter discovery and compact route
templates before flat helper inventories when documenting routine AI use.

#### Scenario: Agent starts route maintenance
- **WHEN** an AI consumer reads API docs or uses public template commands for a
  route covered by this change
- **THEN** the documented first path is the route starter API and compact
  template for that route
- **AND** the full helper list and full template remain discoverable as explicit
  advanced paths

#### Scenario: Compact path preserves safety gates
- **WHEN** the AI uses a compact template for model miss, model-test alignment,
  or UI-flow structure
- **THEN** the generated files still include the route's required gate, test,
  replay, validation, or implementation evidence boundaries

### Requirement: Flat helper inventory is not first-read guidance
FlowGuard SHALL document `MODELING_HELPER_API`, `REPORTING_HELPER_API`, and
`__all__` as complete indexes rather than preferred first-read surfaces for AI
agents.

#### Scenario: API documentation is read from top to bottom
- **WHEN** an agent reads `docs/api_surface.md`
- **THEN** `AGENT_DEFAULT_API` and `ROUTE_STARTER_API` appear before full helper
  inventory discussion
- **AND** the full helper inventories are labeled as full or fallback indexes

### Requirement: Existing similarity route remains the owner
FlowGuard SHALL extend the existing Model Similarity Consolidation route instead
of adding a second similarity-maintenance capability.

#### Scenario: A/B/C maintenance similarity is reviewed
- **WHEN** a workflow has similar variants, shared kernels, adapters,
  duplicate boundaries, tests, or false-friend risks
- **THEN** the review MUST use Model Similarity Consolidation as the owning
  route and pass handoff evidence to downstream FlowGuard routes

### Requirement: Hot-path prompt budgets are enforced
FlowGuard AI guidance SHALL enforce explicit size budgets for first-read prompt
surfaces so the thin default path remains operational rather than aspirational.

#### Scenario: Skill docs tests inspect first-read surfaces
- **WHEN** repository skill documentation tests run
- **THEN** they verify the kernel skill, satellite skill shells, and reusable
  AGENTS snippet remain within their configured hot-path budgets

#### Scenario: Prompt detail moves to references
- **WHEN** guidance needs route-specific protocol detail, helper inventories, or
  long examples
- **THEN** the first-read prompt points to a reference document instead of
  duplicating that detail inline

### Requirement: Guidance compression preserves local synchronization evidence
FlowGuard guidance compression SHALL be finalized only after repository source,
editable install behavior, installed Codex skills, shadow workspace imports,
formal local repository sync, and local git evidence are aligned or explicitly
scoped out.

#### Scenario: Compressed guidance is finalized locally
- **WHEN** compact AI entry guidance is ready to claim done
- **THEN** validation includes OpenSpec checks, FlowGuard self-checks, focused
  API/template tests, broader regression, editable install verification, shadow
  workspace verification, formal repository sync verification, and local git
  status or commit/tag evidence

