# flowguard-codex-skill-satellites Specification

## Purpose
This capability defines FlowGuard's Flowguard Codex Skill Satellites behavior and the evidence required to use it safely in AI-agent maintenance workflows.
## Requirements
### Requirement: Kernel remains the canonical FlowGuard entrypoint
The repository SHALL keep `model-first-function-flow` as the canonical
FlowGuard Skill Kernel for applicability decisions, hard gates, flow lenses,
ambiguous route selection, package import verification, and adoption evidence.

#### Scenario: Ambiguous request starts at the kernel
- **WHEN** a Codex task involves FlowGuard risks but does not clearly name one
  standalone satellite skill
- **THEN** the `model-first-function-flow` Skill remains the correct entrypoint
  and selects the matching route or routes

### Requirement: Seven route-specific satellite skills are directly discoverable
The repository SHALL provide seven standalone Codex skills:
`flowguard-model-test-alignment`, `flowguard-development-process-flow`,
`flowguard-model-miss-review`, `flowguard-code-structure-recommendation`,
`flowguard-model-mesh`, `flowguard-test-mesh`, and
`flowguard-structure-mesh`.

#### Scenario: Clear route request invokes a satellite
- **WHEN** a user directly asks for a mature route such as Model-Test
  Alignment, DevelopmentProcessFlow, ModelMesh, TestMesh, or StructureMesh
- **THEN** Codex can invoke the matching standalone FlowGuard skill without
  treating package helper APIs as skills

### Requirement: Satellite skills preserve FlowGuard hard gates
Each satellite skill SHALL preserve FlowGuard's hard gates: use the real
`flowguard` package, represent modeled blocks as `Input x State ->
Set(Output x State)` where modeling is needed, keep skipped evidence visible,
avoid fake mini-frameworks, avoid weakening invariants, and route ambiguous
cross-cutting work back to the kernel.

#### Scenario: Satellite skill runs in another repository
- **WHEN** a standalone satellite skill is used in another repository
- **THEN** it tells Codex to verify the real FlowGuard package before claiming
  FlowGuard adoption or route confidence

### Requirement: Satellite skills remain discoverable route shells

FlowGuard SHALL preserve direct satellite skills as concise route shells with
standalone hard gates, trigger/skip criteria, minimum workflow, snapshot
guidance, non-goals, and reference handoff.

#### Scenario: Satellite skill count is not reduced by structure cleanup

- **WHEN** implementation surfaces are simplified
- **THEN** existing satellite skill names remain discoverable and their
  `SKILL.md` files remain within prompt budgets

#### Scenario: Hard gates remain visible

- **WHEN** a satellite skill is read without deep reference files
- **THEN** real-package verification, project adoption records, fake-framework
  rejection, and route-specific evidence honesty remain visible

### Requirement: Global prompt guidance describes the new topology
The reusable AGENTS snippet SHALL describe the FlowGuard architecture as one
kernel plus seven directly invokable satellite skills, while keeping
`conformance_adoption`, `long_check_observability`, and `framework_upgrade` as
kernel-routed support protocols.

#### Scenario: Repository copies AGENTS guidance
- **WHEN** another repository copies `docs/agents_snippet.md`
- **THEN** it learns which FlowGuard skills are direct Codex skills and which
  protocols remain routed through the kernel

### Requirement: Installed skills are synchronized before release
The release process SHALL sync the repository skill directories to the local
Codex installed skills directory and verify the installed skill set before
publishing a GitHub Release.

#### Scenario: Release validation checks installed behavior
- **WHEN** a new FlowGuard release is prepared
- **THEN** repository skills, installed Codex skills, package version,
  shadow workspace import, git tag, and GitHub Release version are checked for
  alignment

### Requirement: Satellite skills preserve target-project adoption
Every directly invokable FlowGuard satellite Skill SHALL preserve the target
project AGENTS/version adoption check so direct satellite use cannot bypass the
kernel's project adoption rule.

#### Scenario: Satellite runs in target project
- **WHEN** a standalone FlowGuard satellite Skill is used for real target
  project work
- **THEN** it tells the agent to ensure the project has a FlowGuard AGENTS
  managed block and project version record, or to record why that update was
  not performed

### Requirement: Agent workflow rehearsal satellite is discoverable as a delegated mode owner
The repository SHALL provide `flowguard-agent-workflow-rehearsal` as a
FlowGuard skill that Codex can invoke when explicitly requested or delegated by
the development-process simulator `agent_workflow` mode.

#### Scenario: Rehearsal satellite is listed with delegated role
- **WHEN** a Codex agent reads the FlowGuard skill topology or reusable AGENTS
  guidance
- **THEN** `flowguard-agent-workflow-rehearsal` appears as the delegated
  `agent_workflow` owner
- **AND** generic multi-skill workflow routing enters
  `flowguard-development-process-flow` first

#### Scenario: Rehearsal satellite preserves hard gates
- **WHEN** the satellite is used in another repository or machine
- **THEN** it requires the real FlowGuard package for FlowGuard claims
- **AND** it requires a fresh current-machine skill inventory before rehearsal

### Requirement: Installed skill synchronization includes rehearsal satellite
The release and local synchronization process SHALL include
`flowguard-agent-workflow-rehearsal` in repository and installed Codex skill
surface checks.

#### Scenario: Installed skill is synchronized
- **WHEN** the change is validated for local use
- **THEN** the installed Codex skills directory contains the new rehearsal
  satellite
- **AND** repository skill docs tests verify the satellite topology

#### Scenario: Installed prompt behavior is not claimed from repository-only changes
- **WHEN** the repository copy of the skill has changed
- **THEN** the change is not reported as active installed behavior until the
  installed skill surface is synchronized or explicitly reported as unsynced

### Requirement: Installed skill route alignment
Installed FlowGuard Codex skill route maps SHALL stay aligned with the package route graph, including route ids, triggers, minimal workflow, hard gates, evidence boundaries, and downstream handoffs.

#### Scenario: Package route graph adds a group
- **WHEN** the package route graph adds or changes a route group
- **THEN** installed skill guidance SHALL be updated or the mismatch SHALL be recorded as a scoped maintenance obligation

### Requirement: Codex exposes a topology hazard satellite skill

FlowGuard SHALL expose `flowguard-model-topology-hazard-review` as a direct
Codex satellite skill while keeping the model-first kernel as the router for
ambiguous or cross-route work.

#### Scenario: Skill route is present and prompt-grounded

- **WHEN** the Codex skill directories are inspected
- **THEN** `flowguard-model-topology-hazard-review` MUST have a concise
  `SKILL.md`, OpenAI agent metadata, a protocol reference, and a lazy-loaded
  prompt template
- **AND** the kernel route map MUST route model-shape future-use hazards to the
  new satellite skill.

### Requirement: Satellite reference protocols own detailed route guidance
Each directly invokable FlowGuard satellite SHALL own its detailed protocol in
the satellite `references/` directory when that route has a standalone skill.

#### Scenario: Kernel reference duplicates are folded
- **WHEN** the kernel reference directory includes a protocol whose detailed
  route is owned by a standalone satellite
- **THEN** the kernel copy is either absent or a compact handoff stub
- **AND** the satellite reference remains reachable and substantive

#### Scenario: Standalone satellite remains usable
- **WHEN** a satellite skill is installed or copied independently
- **THEN** its `SKILL.md` and satellite reference provide the route trigger,
  hard gates, workflow checklist, validation boundary, and non-goals without
  requiring the kernel's duplicate copy

### Requirement: Plan detailing is exposed as a delegated mode owner
FlowGuard SHALL include `flowguard-plan-detailing-compiler` as the delegated
`plan_detailing` owner that remains directly invokable when explicitly named.

#### Scenario: Delegated skill is discoverable
- **WHEN** the FlowGuard Codex skill topology is read
- **THEN** plan detailing appears as the `plan_detailing` owner
- **AND** generic rough-plan routing enters `flowguard-development-process-flow`
  first

#### Scenario: Installed skill sync covers plan detailing
- **WHEN** the repository skill is updated
- **THEN** installed Codex skill synchronization checks include the plan-detailing satellite

### Requirement: Satellite skills use concise route shells
Each directly invokable FlowGuard satellite skill SHALL keep its `SKILL.md`
first-read surface to a concise route shell while preserving standalone hard
gates and a clear reference handoff.

#### Scenario: Satellite route shell is inspected
- **WHEN** a repository-managed satellite `SKILL.md` is read by an agent
- **THEN** it contains the skill name, route trigger, skip/return guidance, hard
  gates, a minimum workflow, validation/claim boundary notes, non-goals, and a
  route-specific reference path without embedding the full protocol inline

#### Scenario: Standalone use keeps hard gates
- **WHEN** a satellite skill is copied or installed outside the FlowGuard repo
- **THEN** it still tells the agent to use the real FlowGuard package, preserve
  AGENTS/version adoption checks for real project use, keep skipped evidence
  visible, and avoid fake mini-frameworks

### Requirement: Installed satellite sync is content-aware
Installed FlowGuard satellite skill synchronization SHALL verify repository and
installed skill content rather than only checking that a directory exists.

#### Scenario: Existing installed skill is refreshed
- **WHEN** a repository-managed satellite skill already exists in the local
  installed Codex skills directory
- **THEN** synchronization refreshes changed content or reports an explicit
  mismatch before local installed behavior is claimed

### Requirement: Installed UI skills require human-operability routing
FlowGuard Codex skill satellites SHALL route UI completion, usability, and
human-operable claims through user task coverage and human-operability evidence
rather than treating visible inventory or functional chains as sufficient.

#### Scenario: Skill prompt omits task coverage
- **WHEN** the UI Flow skill is used for a complete UI claim
- **THEN** its guidance must require user task coverage, task-to-feature,
  task-to-UI, affordance, action grammar, dialog/window, keyboard/focus, and
  walkthrough evidence before human-operable confidence

### Requirement: Installed UI skills use generic source-baseline routing
FlowGuard Codex skill satellites SHALL keep installed UI and process skill guidance generic for source-based UI work.

#### Scenario: UI skill names generic work mode
- **WHEN** the installed UI Flow Structure skill is read
- **THEN** it routes by greenfield, source-based, and mixed work mode and names source-baseline mapping, approved differences, generic source interactions, and observed-source alignment

#### Scenario: Installed skill hard-codes one source technology
- **WHEN** installed FlowGuard UI or development process skill guidance hard-codes one source technology as a generic gate
- **THEN** the installed skill sync is incomplete

### Requirement: FlowGuard skills expose writing-quality process gates
FlowGuard Codex skill guidance SHALL mention writing-quality ledgers as process
evidence when prompt, skill, or document workflows depend on academic or
source-backed writing quality.

#### Scenario: DevelopmentProcessFlow skill is read
- **WHEN** an agent uses DevelopmentProcessFlow for thesis, report, paper, or
  source-backed writing upgrades
- **THEN** the skill guidance MUST name literature progression, method depth,
  figure/table argument treatment, AI-style density, and citation/footnote
  verification as possible freshness-sensitive artifacts

### Requirement: Plan detailing is a delegated simulator mode owner
FlowGuard Codex skill guidance SHALL present `flowguard-plan-detailing-compiler`
as the delegated `plan_detailing` owner for non-trivial plan discussions and
rough AI outlines after the DevelopmentProcessFlow simulator front door records
the mode.

#### Scenario: Plan detailing appears as delegated owner
- **WHEN** a Codex agent reads FlowGuard skill topology or reusable AGENTS guidance
- **THEN** `flowguard-plan-detailing-compiler` appears as the delegated
  `plan_detailing` owner under `flowguard-development-process-flow`

#### Scenario: Plan discussion records mode before delegation
- **WHEN** the task is a non-trivial plan discussion before implementation
- **THEN** Codex skill guidance selects DevelopmentProcessFlow first and records
  `plan_detailing` before any delegated PlanDetailing pass

### Requirement: Installed skills include updated plan-detailing guidance
Installed FlowGuard Codex skill synchronization SHALL refresh the local installed `flowguard-plan-detailing-compiler`, `flowguard-agent-workflow-rehearsal`, and `flowguard-development-process-flow` guidance when repository routing changes.

#### Scenario: Installed guidance is synchronized
- **WHEN** repository skill guidance is updated for plan discussion handoff
- **THEN** local installed skill copies are synchronized or an explicit unsynced boundary is reported before local Codex behavior is claimed

### Requirement: Installed UI skill guidance teaches real-surface first gate
FlowGuard Codex skill satellite guidance SHALL state that existing/runnable UI
work starts from observed real UI inventory, maps every visible item to a model
owner or blindspot, validates enabled controls through real functional chains,
and uses final done-claim review before broad completion wording.

#### Scenario: Repository and installed skills align
- **WHEN** the repository UI Flow, Model Miss, DevelopmentProcessFlow,
  AgentWorkflowRehearsal, or Closure guidance changes
- **THEN** installed Codex skill copies must be synchronized or final
  confidence must stay scoped

#### Scenario: Compact template cannot prove completion
- **WHEN** a public compact template is used for UI route exploration
- **THEN** the guidance says compact output is not runnable/complete UI
  evidence unless observed inventory, functional-chain, and implementation
  validation gates are also current

### Requirement: Satellite skill guidance teaches validation gates
FlowGuard Codex satellite skills SHALL surface the new UI and artifact payload
validation evidence gates in their concise route shells or reference protocols.

#### Scenario: UI satellite is read
- **WHEN** an agent reads `flowguard-ui-flow-structure`
- **THEN** the guidance MUST say runnable UI completion requires reachable
  actionable controls/events to have run evidence, pure-UI classification, or
  scoped blindspots

#### Scenario: Alignment and TestMesh satellites are read
- **WHEN** an agent reads Model-Test Alignment or TestMesh guidance
- **THEN** the guidance MUST route artifact payload contracts to Model-Test
  Alignment and large payload evidence matrices to TestMesh

### Requirement: Installed skill sync covers validation gate changes
Installed FlowGuard skill synchronization SHALL verify that local installed
skills include validation gate guidance before active installed behavior is
claimed.

#### Scenario: Installed skill is stale
- **WHEN** repository skill content includes validation gate guidance
- **AND** the installed skill copy does not
- **THEN** release or local sync confidence MUST remain scoped until the
  installed skill is refreshed or the mismatch is reported

### Requirement: Contract-exhaustion route has a thin satellite skill
FlowGuard MUST expose a `flowguard-contract-exhaustion-mesh` satellite skill
that routes finite bad-case generation through ContractExhaustionMesh while
preserving existing proof-route ownership.

#### Scenario: Agent routes same-class generation to thin skill
- **WHEN** an agent needs to generate same-class or finite boundary bad cases
- **THEN** the skill directs the agent to use ExistingModelPreflight and
  ContractExhaustionMesh before handing off to proof routes

#### Scenario: Skill refuses fallback case generation
- **WHEN** an agent tries to use hand-written same-class cases as canonical
  coverage
- **THEN** the skill instructs the agent to produce canonical case ids or report
  a scoped/model-gap result

### Requirement: Installed skill shells mirror route roles
FlowGuard Codex skill shells SHALL describe public owner routes, delegated
modes, internal feeders, and data helpers consistently with the route registry.

#### Scenario: Public skill names owner route
- **WHEN** an installed FlowGuard skill is a public owner route
- **THEN** its `SKILL.md` MUST identify that owner route and its hard gates

#### Scenario: Delegated mode skill is not generic first stop
- **WHEN** an installed FlowGuard skill is a delegated mode
- **THEN** its `SKILL.md` MUST say it is selected by the owning route except
  when explicitly requested

#### Scenario: Internal helper has no installed direct skill
- **WHEN** a helper is classified as an internal feeder or data helper
- **THEN** the installed skill set MUST NOT expose it as a direct Codex
  satellite unless a public facade is proven

### Requirement: Stale prompt wording is cleaned
FlowGuard Codex skill prompts SHALL NOT describe old helper-first same-class,
analogous-bug, simulator, scan, or closure routes as current canonical paths.

#### Scenario: Old same-class wording appears
- **WHEN** skill docs or prompt templates mention hand-written same-class cases
  as coverage
- **THEN** the wording MUST be rewritten to say those cases are seeds for
  ContractExhaustionMesh

#### Scenario: Old final-claim wording appears
- **WHEN** skill docs imply closure helpers or maintenance scans can support
  broad final confidence by themselves
- **THEN** the wording MUST be rewritten to require RiskEvidenceLedger and
  DevelopmentProcessFlow owner consumption

### Requirement: Skill sync verifies the whole FlowGuard suite
Installed FlowGuard skill synchronization SHALL verify the complete current
suite of repository-managed FlowGuard skills rather than only package import or
one kernel skill.

#### Scenario: Local installed skills are checked
- **WHEN** local installed Codex skills are inspected after this guidance change
- **THEN** every repository-managed FlowGuard skill directory under
  `.agents/skills/` MUST have a corresponding installed skill directory or an
  explicit unsynced finding
- **AND** affected installed skill files MUST include the current skill-suite
  and check-script guidance markers before active behavior is claimed

### Requirement: Satellite wording does not imply package-first use
FlowGuard satellite skill wording SHALL preserve executable evidence gates
without teaching agents that package installation is the skill installation.

#### Scenario: Satellite hard gate is read
- **WHEN** a satellite skill mentions real executable FlowGuard checks
- **THEN** it MUST keep fake-framework rejection and skipped-evidence honesty
- **AND** it MUST NOT say that Python package setup alone completes the
  AI-agent skill setup

### Requirement: Satellite Activation And Non-Use Boundaries
Every satellite skill SHALL define specific `Use When` and `Do Not Use When` conditions that distinguish it from the kernel and peer satellites. Delegated-only routes MUST state the permitted delegator and SHALL NOT activate as generic public fallbacks.

#### Scenario: Plan detailing is invoked generically
- **WHEN** PlanDetailing is selected without explicit user request or DevelopmentProcessFlow delegation
- **THEN** activation validation rejects the route and returns the correct owner handoff

### Requirement: Satellite Workflow And Evidence Output
Every satellite SHALL declare its required workflow, native checks, evidence fields, blockers, skipped-check handling, residual risk, claim boundary, and typed next actions. Its output MUST distinguish checked, unchecked, blocked, and uncertain obligations.

#### Scenario: Satellite omits residual risk
- **WHEN** a satellite reports completion without its required residual-risk and claim-boundary fields
- **THEN** its contract check fails and the result cannot satisfy parent closure

### Requirement: Prompt Size And Routed References
Satellite prompts SHOULD remain at or below 60 lines and 3000 characters. Required detail beyond the prompt budget SHALL move to directly linked, layout-resolvable references with explicit local-material routing.

#### Scenario: Installed reference is repository-only
- **WHEN** a satellite direct reference resolves in the source tree but not in a temporary installed layout
- **THEN** layout validation fails for the installed profile

### Requirement: Satellite Specific Contract Checks
Each satellite's check manifest SHALL include at least one check specific to its owned behavior or evidence gate in addition to shared schema/layout checks. A suite of only shared field-presence checks MUST NOT qualify as deep certification.

#### Scenario: Manifest contains only shared checks
- **WHEN** a satellite manifest lists no owner-specific check or test-gap disposition
- **THEN** depth validation fails with an insufficient-native-depth finding

### Requirement: Agent skills prompt primary path authority
FlowGuard Codex skills SHALL instruct agents to enumerate runtime paths,
select one primary authority, classify non-primary surfaces, reject automatic
fallback success, and require coverage evidence before broad claims.

#### Scenario: Agent starts non-trivial implementation
- **WHEN** an agent uses FlowGuard for feature work, bug repair, refactor,
  prompt/skill changes, install sync, or release confidence
- **THEN** the skill guidance SHALL prompt for primary path authority when
  runtime paths or compatibility surfaces are in scope

#### Scenario: Skill warns against A failed B succeeded
- **WHEN** a skill describes fallback policy
- **THEN** it SHALL state that primary failure must be visible and repaired
  rather than automatically routed to alternate success

### Requirement: Agent skills prompt default commitment registration
FlowGuard Codex skill satellites SHALL instruct agents to register or review
behavior commitments before non-trivial FlowGuard work that changes, validates,
publishes, or claims external behavior.

#### Scenario: New project starts FlowGuard work
- **WHEN** an agent begins non-trivial FlowGuard adoption or planning for a project without a current behavior ledger
- **THEN** the skill guidance SHALL route to Behavior Commitment Ledger baseline creation

#### Scenario: Existing behavior changes
- **WHEN** an agent changes a registered behavior
- **THEN** the skill guidance SHALL update the ledger row, owner model, evidence, and PPA binding when path-sensitive

### Requirement: Existing skills teach behavior-plane ownership
The existing BCL, Existing Model Preflight, Model Miss, DevelopmentProcessFlow, AgentWorkflowRehearsal, PlanDetailing, and model-first skill guidance SHALL describe the three behavior planes and their route-native ownership boundaries without adding a new skill route.

#### Scenario: BCL skill creates a commitment
- **WHEN** the BCL skill adds, changes, removes/replaces, gap-backfills, or checks a model-miss commitment
- **THEN** it SHALL classify behavior plane and actor kind before broad confidence
- **AND** SHALL require typed cross-plane relations

#### Scenario: Preflight skill retrieves related product context
- **WHEN** an AI-operation task relates to a product commitment
- **THEN** the preflight skill SHALL keep the AI commitment primary and label the product commitment as related context

#### Scenario: Model Miss asks whose promise failed
- **WHEN** a concrete post-green failure is reviewed
- **THEN** the Model Miss skill SHALL identify the affected plane before backfeed

### Requirement: Process and agent skills do not absorb sibling planes
DevelopmentProcessFlow SHALL remain the development lifecycle owner, and AgentWorkflowRehearsal SHALL remain the AI-operation plan/evidence owner; neither SHALL treat related product behavior as its own implementation instructions.

#### Scenario: Product behavior model is consulted by agent workflow
- **WHEN** an agent operation invokes or validates a product commitment
- **THEN** AgentWorkflowRehearsal SHALL treat the product model as target context
- **AND** its own ordered steps SHALL come from the agent-operation owner model

### Requirement: Skill source, generated contract, and installed copy stay synchronized
Affected skill changes SHALL update canonical `SKILL.md`, directly required references, `agents/openai.yaml`, and `.skillguard/contract-source.json`, then regenerate derived contracts and verify shadow/formal installed parity.

#### Scenario: Generated contract is hand-edited
- **WHEN** a derived compiled contract differs without a matching contract-source change
- **THEN** SkillGuard validation SHALL fail the skill target

#### Scenario: Installed copy is stale
- **WHEN** canonical and compiled skill checks pass but the installed skill differs
- **THEN** project closure SHALL remain blocked until installer check/parity passes

### Requirement: Guidance remains advisory outside existing hard gates
Skill guidance SHALL make registered same-plane models visible without imposing a new universal requirement that every trivial action execute a model.

#### Scenario: Existing release gate applies
- **WHEN** a task reaches an existing irreversible/release/full-claim gate
- **THEN** route-native evidence requirements SHALL still apply
- **AND** this change SHALL NOT weaken them

#### Scenario: Ordinary task has no registered hit
- **WHEN** a non-trivial lookup returns no same-plane commitment and no concrete miss exists
- **THEN** Codex MAY continue through existing routing with an explicit no-hit boundary rather than fabricating a commitment

### Requirement: Native skills route spec reconciliation through existing owners
FlowGuard's maintained skills SHALL direct spec work-package planning and verification through DevelopmentProcessFlow, PlanDetailing, ExistingModelPreflight, and TestMesh native routes with SkillGuard as contract supervisor only.

#### Scenario: Agent plans a multi-spec workflow
- **WHEN** an agent uses OpenSpec or Spec Kit with FlowGuard in one non-trivial change
- **THEN** skill guidance SHALL require provider authority, bidirectional mapping, begin/post freshness, terminal receipts, and explicit reuse boundaries without creating a second spec workflow

#### Scenario: Product UI guidance is rendered
- **WHEN** the task concerns internal spec-tool orchestration
- **THEN** the skill guidance SHALL NOT project work-package fields into product UI content or visibility rules

