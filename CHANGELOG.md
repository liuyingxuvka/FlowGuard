# Changelog

## v0.61.0 - 2026-07-23

- Added one durable authoritative observed-model system snapshot with explicit
  separation between observed implementation, normative target, and isolated
  counterfactual experiment lanes.
- Added content-addressed model instances, typed cross-model relations, six
  coverage dimensions, exact subject revisions, and authority-first existing
  model preflight so discovery evidence can no longer masquerade as current
  authority.
- Added whole-revision-set activation and operational rollback with shared
  compare-and-swap locking, pointer-last persistence, affected-closure
  fingerprints, prediction/replay evidence, and required effect restoration or
  forward repair for irreversible changes.
- Integrated model authority into project audit, regression receipts, the
  command line, public API, behavior commitment ownership, and the existing
  FlowGuard skill routes without creating a parallel workflow.
- Split the former oversized authority implementation into schema, revision,
  persistence, and inventory owners; centralized the fixed skill-suite
  inventory; and removed the absent lightweight model-miss-review ghost route.
- Retained source-only release authority with an immutable tag and zero GitHub
  Release assets.

## v0.60.0 - 2026-07-22

- Added strict `flowguard.portable_system.v1` system definitions, verification
  requests, and exact declared-graph slices with separate canonical identities.
- Added bounded joint-system compilation and a stage-aware composition report
  that distinguishes `pass`, `fail`, `blocked`, `invalid`, and `not_run`, maps
  counterexamples back to components, and invokes the canonical system checker
  at most once.
- Added `portable-system-check`, Python API exports, and three benchmark
  families covering retry identity, permission revocation, and deletion
  propagation with bad, repaired, missing-semantics, and truncated variants.
- Extended the existing portable-composition behavior commitment, executable
  model evidence, regression manifest, tests, and affected FlowGuard skill
  guidance without adding a second runtime owner or a new satellite skill.
- Retained source-only release authority with an immutable tag and zero GitHub
  Release assets.

## v0.59.0 - 2026-07-22

- Added one manifest-backed `python -m flowguard simulator` surface for model
  listing and explicit selected/all-model execution while preserving every
  model's native runner as its sole domain-result owner.
- Replaced full stdout/parsed-payload replication in model and unified release
  validation with deterministic compressed content objects, bounded
  diagnostics, hashes, and artifact references.
- Added terminal run manifests, atomic scoped current heads, read-only evidence
  audit/GC planning, exact quarantine/restore, and separately authorized purge;
  ordinary validation never silently cleans persistent evidence.
- Registered two previously unaccounted checkout-local models as
  `optional_local`, refreshed one stale model-purpose fingerprint, and extended
  the existing structure-surface model with simulator-takeover, duplicate-
  payload, and automatic-purge known-bad cases.
- Clarified that executable model source is small and distinct from generated
  evidence, build products, installed consumer skills, and extra local
  worktrees.
- Retained source-only release authority with an immutable tag and zero GitHub
  Release assets.

## v0.58.5 - 2026-07-19

- Refreshed every FlowGuard skill's private author-side SkillGuard contract
  with the current affected-only validation ownership and provenance model.
- Kept graduated consumer skills clean: author contracts and receipts remain
  excluded from the installed projection, with no fallback or compatibility
  runtime.
- Retained source-only release authority with an immutable tag and zero GitHub
  Release assets.

## v0.58.4 - 2026-07-19

- Corrected the v0.58.3 artifact-ownership model miss: a numeric
  `schema_version`, producer label, FlowGuard-looking prefix, scan path, or
  partial ledger shape no longer grants FlowGuard write authority.
- Added an exact current-only registry for real FlowGuard `report` and `trace`
  envelopes. Current shapes remain byte-identical; malformed, old, future, and
  unsupported versions block without writing because no evidence-bound
  migrator exists.
- Retained one repository-history-backed behavior-ledger writer, bounded to
  the exact complete bare producer shape from commit `56083c1e`. It
  materializes the full current canonical envelope at the upgrade boundary;
  target-only extra fields and old/future BCL envelopes never enter it.
- Required explicit upgrade-AI plane/actor dispositions in legacy row metadata;
  actor, owner, label, trigger, and commitment-kind text are never used to
  guess new current semantics.
- Migrated historical `primary_path_ids` explicitly at that boundary: zero or
  one value becomes the current singular field, while multiple values block
  for an evidence-bound disposition. No generic version-field writer,
  fallback, dual reader, or compatibility parser was added.
- Removed the normal-runtime plural path reader and its
  `legacy_plural_migrated` / `primary_path_migration_ambiguous` state. The BCL
  loader now requires the exact current envelope field set, current schema and
  format versions, and a canonical current payload.
- Updated the bundled public BCL template to emit that complete current
  canonical payload directly; template loading never fills omitted fields or
  consults a compatibility reader.
- Added a real non-editable-package regression that migrates a historical
  FlowGuard behavior ledger while proving a Khaos-style target fixture remains
  byte- and SHA-256-identical in the same `project-upgrade` run.
- Extended both public upgrade models with target-owned JSON, full
  legacy-lookalike extra-field, and unsupported-envelope known-bad cases.
- Retained source-only release authority with an immutable tag and zero GitHub
  Release assets.

## v0.58.3 - 2026-07-19

- Corrected the v0.58.2 deployment-topology miss: ordinary project audit and
  upgrade no longer look for the author-only suite map through an editable
  package layout.
- Added one deterministic package-owned clean-consumer authority containing
  the exact 15 member ids and complete projected file fingerprints, including
  generated consumer-release manifests.
- Made ordinary project writes require exact package-authority parity with the
  global `$CODEX_HOME/skills/` projection and its ownership manifest. Missing,
  modified, reserved-extra, or author-control-polluted consumers block visibly.
- Added a real non-editable package regression that installs into an isolated
  target directory, upgrades a genuinely empty ordinary project, verifies the
  expected writes, and passes the subsequent project audit.
- Kept author suite maps, SkillGuard contracts, receipts, and check execution
  outside the installed consumer and ordinary project runtime. No fallback,
  alternate reader, compatibility path, or project-local shadow suite was
  added.
- Retained source-only release authority with an immutable tag and zero GitHub
  Release assets.

## v0.58.2 - 2026-07-18

- Repaired an ordinary-project authority regression: generated minimum
  revalidation now invokes only the installed package audit and no longer
  requires the author-repository `verify_skill_suite_markers.py` script.
- Made the one clean consumer projection under `$CODEX_HOME/skills/` the sole
  FlowGuard skill authority for ordinary projects; adopted projects do not
  receive a second `.agents/skills` tree or suite map.
- Added executable temporary-project regressions proving project adoption,
  audit, and minimum revalidation work without local `scripts`,
  `.agents/skills`, or `.skillguard` directories.
- Preserved the author-maintenance boundary: the canonical suite map, full
  fifteen-member SkillGuard validation, and generated author contracts remain
  owned by the FlowGuard source repository.
- Kept one direct current path only; no alias, fallback, compatibility reader,
  or shadow-suite authority was added.
- Retained source-only release authority with an immutable tag and zero GitHub
  Release assets.

## v0.58.1 - 2026-07-18

- Corrected a v0.58.0 model miss in project audit and upgrade: suite
  reconciliation now uses the canonical map from the current FlowGuard package
  source and the clean consumer projection from the current installed Codex
  skills root.
- Added a regression proving ordinary projects need no `.skillguard` directory
  or local FlowGuard skill suite, while missing or mismatched installed
  consumer skills still block before mutation.
- Retained one direct current path only; no target-local compatibility reader,
  alias, or fallback was added.
- Removed the Python 3.10 hand-written TOML parser fallback and made Python
  3.11+ with the standard-library `tomllib` parser the sole current runtime
  path.
- Removed the unused `run_flowguard_self_governance.py` forwarding alias; the
  sole current command is `check_flowguard_self_governance.py`.
- Removed stale regression-manifest registrations for the already retired
  SpecContext and task-local replay models and refreshed the changed
  ModelMissReview purpose identity.
- Made CI materialize the current clean consumer skill projection before the
  project-adoption audit, so a clean runner follows the same declared install
  path instead of depending on undeclared machine state.

## v0.58.0 - 2026-07-18

- Renamed the canonical kernel skill directly from
  `model-first-function-flow` to `flowguard`; no alias, forwarding stub,
  compatibility reader, or fallback path remains.
- Reduced the public Codex surface from seventeen to fifteen skills by moving
  plan detailing and agent-workflow rehearsal into two explicit internal
  routes owned by `flowguard-development-process-flow`.
- Consolidated all fifteen author sources into the single
  `unit:flowguard-suite` SkillGuard maintenance unit while preserving each
  public satellite's native route and check authority.
- Made source tags the sole release authority: v0.58.0 releases contain no
  wheel, source-distribution, or downloadable package assets.
- Added explicit author-source and consumer-distribution parity roles so
  consumer projections are compared without author-only SkillGuard material.

## v0.57.0 - 2026-07-16

Portable compositional-verification kernel release.

- Added a strict, versioned, JSON-serializable finite model IR with canonical
  identities, explicit invariants and temporal obligations, and fail-closed
  rejection of unknown or dangling schema content.
- Added a code-independent reference checker for nondeterministic traces,
  safety, terminal progress, universal and bounded eventuality, weak fairness,
  visible truncation, and smallest counterexample preservation.
- Added explicit child-to-parent refinement and assume/guarantee composition
  checks, including state/transition mappings, stutter declarations,
  assumption weakening, guarantee strengthening, provider closure, and
  conflict detection.
- Exposed one narrow Python API and CLI cohort, registered the kernel in the
  model-regression manifest, and updated ModelMesh, topology-hazard, and
  model-first skill contracts without adding a duplicate public route.
- Revalidated the project artifacts with official OpenSpec 1.6.0. This local
  release deliberately excludes GitHub push, remote tag, and GitHub Release
  evidence.

## v0.56.0 - 2026-07-15

Guard-purpose closure and generic declared-check supervision release.

- Added executable model-purpose contracts so every FlowGuard model declares
  the concrete bad behavior it is intended to block for the current modeling
  task, the accepted boundary, observable evidence, and the safe claim that a
  passing model licenses.
- Propagated purpose evidence through model review, model/test alignment,
  TestMesh, development-process closure, and the complete seventeen-skill
  agent suite without turning SkillGuard into a domain-semantics owner.
- Replaced former SkillGuard authorities with the sole current generic
  declared-check contract shape: exact target-owned checks, one execution
  owner per check, current immutable receipts, fixed `enforced` closure, and no
  selectable quality or integration mode.
- Hardened multi-skill validation ownership, installation projection,
  OpenSpec receipt reuse, stale-evidence rejection, interrupted-process
  cleanup, and source/toolchain identity binding.
- Updated models, contracts, templates, documentation, examples, fixtures,
  OpenSpec work packages, and regression coverage for the direct-current
  release boundary.

## v0.55.0 - 2026-07-12

FlowGuard product-language, behavior-plane, and validated-path reuse hardening.

- Partitioned behavior commitment lookup by execution plane while preserving
  typed actor/relationship bindings and canonical ledger I/O, so plane-aware
  discovery composes with existing commitment ownership instead of replacing
  it.
- Added stable exact business-intent identity, one active commitment per exact
  external promise, one singular selected primary path, deterministic one-item
  legacy plural migration, complete affected-surface/candidate inventories, and
  material current runtime/proof requirements.
- Extended the existing UI Flow Structure owner with product-scope typography,
  component, navigation, interaction, feedback, recovery, and transition
  consistency; repeated business surfaces bind the same commitment/path, while
  pure UI interactions stay local.
- Kept UI content admission exactly `user_visible`, `user_on_demand`, or
  `internal`; internal intent, commitment, path, audit, evidence, and diagnostic
  ids remain outside ordinary UI.
- Hardened RuntimePathEvidence, ObligationFamily, Model-Test Alignment,
  Architecture Reduction, ContractExhaustionMesh, TestMesh, and
  DevelopmentProcessFlow against omitted inventories, opaque handoff ids,
  sibling-obligation evidence, parallel facade success, stale proofs,
  progress-only background runs, cross-domain sync overclaims, and peer-write
  rollback.
- Updated OpenSpec requirements, existing FlowGuard models, tests, templates,
  public API guidance, skill prompts/contracts, local installation parity, and
  non-destructive shadow/formal/Git synchronization evidence without adding a
  product-language route, path-reuse route, intent ledger, or evidence engine.
  Added the read-only `behavior-commitment-query` command under the existing
  Behavior Commitment Ledger / Existing Model Preflight owners; it is not a new
  FlowGuard route and does not execute the retrieved commitment.
- Migrated all seventeen bundled skills to `skillguard.contract_source.v2`
  with existing-owner model projections, generated V2 contracts/manifests, and
  `contract_mapped` depth profiles. Static contract-depth certification remains
  distinct from actual execution-depth receipts and adds no parallel executor.

## v0.54.1 - 2026-07-10

FlowGuard published-release verification compatibility patch.

- Resolve external commands through the operating system executable search so
  Windows `PATHEXT` shims such as `git.CMD` work in published verification.
- Convert missing external commands into structured failed checks instead of
  terminating the verifier with an unhandled process-launch exception.
- Correct annotated-tag verification by comparing the local release commit
  with the remote tag's peeled commit while retaining lightweight-tag support.

## v0.54.0 - 2026-07-10

FlowGuard skill-suite governance and verified distribution release.

- Rebuilt the canonical seventeen-skill agent suite around concise,
  route-specific prompts, typed ownership, deterministic contract sources,
  generated native-integrated SkillGuard records, and 17/17 deep checks.
- Added immutable evidence receipts whose freshness, covered obligations,
  producer/checker context, child consumption, and proof-artifact bindings are
  independently recomputed instead of accepted from caller-supplied flags.
- Hardened FlowGuard self-governance so broad success requires current exact
  child passes, a complete parent receipt, and visible blocked/scoped/stale or
  skipped states; synthetic in-memory green reports no longer satisfy closure.
- Added a typed route topology with unique owners, bounded cycles, route-parity
  checks, and explicit delegated/internal/public handoffs.
- Productized local model validation with a checked-in inventory, fast,
  focused, and full tiers, filters, shards, bounded parallelism, per-runner
  timeouts, mutation detection, progress events, isolated artifacts, and
  terminal receipts.
- Added safe, idempotent skill install/check/uninstall/parity commands with
  ownership manifests, explicit legacy adoption, user-change conflict
  protection, temporary-home tests, and complete source/shadow/installed tree
  comparison.
- Repaired project adoption integrity, stable rule identities, dry-run
  guarantees, concise validation output, bilingual documentation, and
  OpenSpec verification contracts for the complete upgrade program.

## v0.53.1 - 2026-07-09

FlowGuard self-maintenance gate hardening.

- Added strict Behavior Commitment Ledger self-maintenance checks so FlowGuard
  workflow changes must keep behavior registration, DCAR coverage,
  TestMesh routing, and model-miss backfeed connected before broad confidence.
- Extended behavior commitment records with source freshness, replacement
  synchronization, TestMesh alignment, model-miss status, and change-mode
  handling for new, changed, replacement, discovery, and model-miss work.
- Updated FlowGuard agent skills, templates, public APIs, CLI rendering, and
  tests so missing ledger coverage blocks immediately instead of leaving an
  alternate success path.

## v0.53.0 - 2026-07-08

Behavior Commitment Ledger, Primary Path Authority, and no-fallback coverage.

- Added `behavior_commitment` as the upstream Behavior Commitment Ledger route
  so broad work inventories every external, verifiable behavior commitment
  before assigning one primary owner model and downstream evidence.
- Connected path-sensitive behavior commitments to `primary_path_authority`, so
  the ledger owns full behavior registration while PPA owns single primary path
  authority and rejects alternate success after primary failure.
- Added `primary_path_authority` as a first-class FlowGuard route so each
  path-sensitive business intent declares one primary runtime authority and
  rejects automatic alternate success after primary failure.
- Wired no-fallback evidence through RuntimePath observations,
  RiskEvidenceLedger gates, public API/CLI/template surfaces, AGENTS guidance,
  and installed FlowGuard skill shells.
- Added model-scoped Cartesian coverage for the primary-path boundary with
  actionable oracle binding, TestMesh shard ownership, and downstream risk
  evidence consumption.
- Published the previously untagged OpenSpec readiness verification commit and
  included validated OpenSpec records for ContractExhaustionMesh,
  hierarchical Cartesian coverage, and helper control-plane consolidation.

## v0.52.6 - 2026-07-07

Guard-family simulation readiness patch.

- Restored route-specific diagram intent guidance in the model-first kernel so downstream Guard skills are not flattened into generic flowcharts.
- Hardened FlowGuard SkillGuard work contracts so duplicate SkillGuard-owned execution paths are invalid while native FlowGuard checks remain authoritative.
- Added OpenSpec release tracking and source-side regression coverage for the prompt contract.

## v0.52.5 - 2026-07-06

Model-code-test closure hardening.

- Added first-class optional source-audit gating to Model-Test Alignment for
  real-code claims, including missing, failed, and unrelated-audit blockers.
- Expanded `ModelCodeTestBindingRow` into a behavior closure summary with owner
  code, path/symbol, tests, boundary/runtime/payload ids, source-audit decision,
  and open gap codes.
- Added target-aware counterexample and known-bad replay closure through
  external owner-code-bound `TestEvidence`.
- Added structured runtime writer-inventory evidence for Runtime Gateway
  Adoption and updated public docs, templates, skills, and tests.

## v0.52.4 - 2026-07-03

FlowGuard skill-suite distribution.

- Reframed public onboarding around `.agents/skills/` as the primary AI-agent
  skill-suite surface, with `model-first-function-flow` as the default
  entrypoint and sibling FlowGuard skills kept visible.
- Clarified that the Python `flowguard` module and CLI are executable
  check-engine support, not the AI-agent skill installation surface.
- Added skill-suite marker verification and updated project adoption templates,
  docs, and tests so repository, installed Codex skills, and generated AGENTS
  guidance stay aligned.
- Archived the `reframe-flowguard-as-skill-suite` OpenSpec change into the main
  specs and refreshed release-scope evidence.

## v0.52.3 - 2026-06-27

- Added SkillGuard runtime-contract governance for the installed FlowGuard Codex skill materials.
- Synchronized installed skill copies with accepted source material and local git evidence.
- Recorded release-scope validation so route selection, evidence gates, quality floors, and closure boundaries remain visible before completion claims.

## v0.52.2 - 2026-06-25

FlowGuard current-situation visibility.

- Added lightweight current-situation guidance so non-trivial FlowGuard work
  tells users what is being checked, why it matters, current evidence or gaps,
  and the next step before or with Mermaid snapshots.
- Updated the shared agent snippet, model-first kernel, and direct FlowGuard
  satellite skills with concise status-note wording while preserving hot-path
  prompt budgets and existing route ownership.
- Archived the OpenSpec change into `flowguard-model-visibility` and
  `user-facing-model-diagrams`, and refreshed local model checks so diagram-only
  prompt rollouts without current-situation notes are rejected.

## v0.52.1 - 2026-06-20

FlowGuard self-maintenance and release hygiene.

- Archived the completed ContractExhaustionMesh OpenSpec changes into the main
  specs so the active change list is clean before publication.
- Re-ran FlowGuard self-maintenance, DevelopmentProcessFlow, Model/Test/Code
  alignment, TestMesh, and StructureMesh checks and kept the current route
  structure unchanged because no model-backed split or field deletion was
  required.
- Prepared a source-only patch release that aligns public version metadata,
  project adoption records, changelog, README, Git tag, and GitHub Release.

## v0.52.0 - 2026-06-20

Contract coverage universe and observed-problem backfeed.

- Added `ContractCoverageUniverse`, scoped exclusions, and broad-claim gates so
  ContractExhaustionMesh can prove the declared coverage universe is present
  instead of only proving the generated matrix is internally consistent.
- Added generic `ContractFaultProfile` and `ObservedProblemBackfeed` helpers so
  downstream systems can rehearse bad contract submissions and map real misses
  back to generated, same-class, and coverage-receipt evidence without a
  FlowPilot-specific fake-AI API.
- Updated route profiles, skills, docs, templates, OpenSpec change records, API
  exports, and regression tests for actionable oracle feedback and universe
  completeness.

## v0.51.0 - 2026-06-16

Hierarchical Cartesian contract-exhaustion coverage.

- Added model-scoped axes, interaction groups, generated combination cases,
  coverage shards, and coverage receipts so ContractExhaustionMesh can produce
  finite bad-case matrices per model instead of relying on hand-written
  representative examples.
- Wired generated combination obligations into Model-Test Alignment, TestMesh,
  ModelMesh, RiskEvidenceLedger, bug-family records, and model-miss review so
  a green single-point matrix cannot be mistaken for a closed parent/child
  model chain.
- Updated FlowGuard route profiles, skills, templates, OpenSpec tasks, docs,
  topology, and regression tests so future AI agents see the Cartesian
  coverage checklist and required handoffs before claiming completion.

## v0.50.0 - 2026-06-15

Helper control-plane consolidation.

- Added first-class route-role metadata to `RouteProfile` so public owner
  routes, delegated modes, internal feeders, data helpers, and cleanup
  dispositions are machine-checkable instead of prompt-only guidance.
- Split public route discovery from advanced/internal helper inventories so
  `FLOWGUARD_ROUTE_API` and `ROUTE_STARTER_API` expose owner routes while
  simulator, model-angle, similarity, maintenance-scan, closure, and
  state-closure helpers remain owner-consumed evidence.
- Updated FlowGuard skills, AGENTS guidance, API docs, topology docs, project
  adoption generation, self-maintenance models, and regression tests so
  DevelopmentProcessFlow, ExistingModelPreflight, ContractExhaustionMesh,
  ArchitectureReduction, and RiskEvidenceLedger own the single hot path without
  helper-first fallback routes.

## v0.49.0 - 2026-06-15

Development-process simulator entry consolidation.

- Added `development_process_simulator` helpers so rough-plan discussion,
  multi-skill workflow setup, staged execution, install/sync, release/archive,
  publish, and final process claims enter `flowguard-development-process-flow`
  first with ordered `plan_detailing`, `agent_workflow`, and
  `execution_freshness` modes.
- Reframed PlanDetailing Compiler and AgentWorkflowRehearsal as explicit or
  simulator-delegated mode owners instead of competing generic first entries.
- Updated Codex skill prompts, OpenAI metadata, AGENTS guidance, README, API
  docs, current OpenSpec specs, and active plan-discussion change notes to
  remove stale direct/peer route wording.
- Added routing/model/API/docs regression coverage so old rough-plan and
  multi-skill hot-path wording is rejected.

## v0.48.0 - 2026-06-15

Single formal FlowGuard model entry.

- Added structured `KnownBadProof` review so new or deepened models must prove
  representative broken cases are caught before broad FlowGuard claims.
- Hardened `RiskIntent`, `MinimumModelContract`, template reuse/no-match, and
  runner summary gates so missing protected errors, completion evidence,
  known-bad proof, or template closure blocks instead of silently passing.
- Removed direct `Explorer` from the agent-default API, migrated public
  templates and model-first skills to `FlowGuardCheckPlan` +
  `run_model_first_checks(...)`, and added adoption audit warnings for
  direct-Explorer-only current models.

## v0.47.3 - 2026-06-15

ModelMesh closure and retry/rejection liveness hardening.

- Made parent/child ModelMesh confidence require closure modeling whenever child
  outputs, reattachment contracts, or runtime path evidence are present.
- Added repeated-input retry/rejection closure fields, repair-feedback and
  blocker/progress checks, ModelMesh closure transition projection into
  Model-Test Alignment/TestMesh, and regression tests for stuck-loop hazards.
- Updated skills, templates, docs, OpenSpec coverage, field inventory, public API
  exports, and template/CLI known-bad proof wiring so current evidence, tests,
  and installed skills agree on the strengthened contract.

## v0.47.2 - 2026-06-13

UI functional capability coverage.

- Added UI functional capability inventories, capability/output contracts,
  capability bindings, and coverage review so required user-visible UI
  functions cannot disappear before broad UI completion claims.
- Wired capability coverage into implementation validation, human-operability,
  PlanDetailing, Model-Miss Review, DevelopmentProcessFlow, RiskEvidenceLedger,
  AgentWorkflowRehearsal, and ClosureContract without creating a parallel UI
  route.
- Updated UI skills, public templates, docs, API/field inventory, OpenSpec
  artifacts, and regression tests so greenfield, source-based, and mixed UI
  work use the same generic capability layer.

## v0.47.1 - 2026-06-13

Plan discussion handoff hardening.

- Promoted PlanDetailing as the direct FlowGuard route for non-trivial plan,
  acceptance, rough-outline, and AI-generated workflow discussions before
  execution routes consume the plan.
- Added AgentWorkflowRehearsal completion-ledger report fields for planned,
  completed, blocked, skipped, required-recheck, handoff, and final-claim
  boundaries.
- Updated skill routing docs, public templates, OpenSpec coverage, API/field
  docs, and regression tests so long prose plans no longer count as completion
  or release evidence.

## v0.47.0 - 2026-06-13

Generic UI source-baseline validation.

- Added generic `greenfield`, `source_based`, and `mixed` UI work-mode modeling
  plus source baseline, target mapping, approved difference, observed-source
  alignment, and source interaction review helpers.
- Replaced source-specific UI migration wording, APIs, process/risk gates,
  closure evidence, agent-workflow roles, public templates, docs, and active
  OpenSpec changes with generic source-baseline terminology.
- Added regression coverage so active skills, templates, docs, and OpenSpec
  guidance do not hard-code a specific source UI technology while still
  allowing historical archive records.

## v0.46.0 - 2026-06-12

Mandatory template harvest closure.

- Added `TemplateHarvestReview`, accepted harvest dispositions, not-harvestable
  reasons, and `review_template_harvest_closure(...)`.
- Extended check plans, audit, runner summaries, CLI, public API exports, and
  starter templates so new or materially deepened models must close template
  harvest as written, merged, duplicate-linked, or accepted not-harvestable.
- Updated FlowGuard skills, AGENTS snippet, modeling protocol, README, API docs,
  OpenSpec coverage, and self-model evidence so template absorption is a hard
  completion gate rather than optional "when useful" guidance.

## v0.45.0 - 2026-06-12

UI human-operability gate.

- Added user task coverage, region semantics, affordance contracts, action
  grammar, dialog/window return contracts, keyboard/focus contracts, human
  walkthroughs, and `review_ui_human_operability(...)`.
- Extended UI Flow Structure, Model Miss Review, PlanDetailing,
  DevelopmentProcessFlow, RiskEvidenceLedger, ClosureContract, and
  AgentWorkflowRehearsal so broad UI done/release confidence requires
  human-operability evidence, not only labels, routes, or click wiring.
- Updated public templates, API docs, UI docs, README, OpenSpec artifacts, and
  skill guidance so supported UI tasks must connect to function model features,
  UI journeys, primary controls, functional chains, feedback, cancel/error,
  keyboard/focus, native dialogs, and walkthrough evidence.

## v0.44.0 - 2026-06-12

Minimum valuable model entry and risk-template reuse.

- Added packaged public risk templates plus a portable per-machine local risk
  template library with search, review, merge, and harvest helpers.
- Raised the default AI model-first entry from a thin starter to a minimum
  valuable model that names protected errors, state/side effects, completion
  evidence, and known-bad cases.
- Updated RiskIntent, CheckPlan, audit, runner, model similarity, CLI,
  templates, skills, docs, and OpenSpec coverage so template reuse and local
  candidate absorption become part of normal model creation.

## v0.43.3 - 2026-06-12

UI real-surface validation hardening.

- Added observed real UI inventory, enabled-control functional chain, MATLAB
  baseline callback semantics, and UI model-miss review helpers.
- Added PlanDetailing, DevelopmentProcessFlow, RiskEvidenceLedger,
  ClosureContract, and AgentWorkflowRehearsal gates so UI completion requires
  typed current evidence and final done-claim review.
- Updated OpenSpec specs, FlowGuard skills, docs, templates, and API surface so
  labels, routes, planned evidence, and API existence cannot stand in for real
  UI click-through behavior.

## v0.43.2 - 2026-06-11

Artifact payload real-flow evidence tightening.

- Tightened Model-Test Alignment artifact payload validation so current
  external passing payload evidence must include an execution proof reference
  or proof artifact for the real payload surface.
- Updated FlowGuard skills, protocols, docs, and templates to describe
  synthetic payload cases as inputs for real import/export/save/load/generate
  or AI work-package surfaces, not standalone payload-only paths.
- Added regression coverage for declaration-only payload evidence and refreshed
  local sync guidance for repository, Gate, and installed Codex skill surfaces.

## v0.43.1 - 2026-06-11

Agent workflow rehearsal completion ledger upgrade.

- Added `planned_steps`, `completed_steps`, `blocked_steps`, `skipped_steps`,
  `required_rechecks`, `handoff_points`, and `final_claim_boundary` to
  `AgentWorkflowRehearsalReport`.
- Updated the AgentWorkflowRehearsal skill and protocol so multi-skill plans
  expose what is planned, what is blocked, what was skipped, which evidence is
  handed off, and why rehearsal is not execution proof.
- Added focused regression coverage for the new report fields.

## v0.43.0 - 2026-06-09

Writing quality-gate process upgrade.

- Added DevelopmentProcessFlow guidance for thesis and source-backed writing
  quality-gate evidence, including literature/technology progression,
  method-depth, figure/table treatment, citation/footnote support,
  source/trace handoff, AI-style integration, final prose, and revision-report
  freshness.
- Updated PlanDetailing and AgentWorkflowRehearsal skills so large writing
  plans and multi-skill workflows expose these quality gates before execution
  or done/release confidence.
- Updated public release metadata for the new process-surface guidance.

## v0.42.0 - 2026-06-08

Validation evidence gate upgrade for UI and artifact payload claims.

- Added Model-Test Alignment artifact payload helpers for file import/export,
  generated artifact, save/load, and AI work-package validation cases.
- Integrated payload contracts/evidence into `ModelTestAlignmentPlan` and the
  public API surface so missing, stale, internal-only, manual prose-only, or
  mismatched payload evidence blocks broad alignment claims.
- Added Risk Evidence Ledger gates for UI implementation evidence and artifact
  payload validation before done/release/full-confidence claims.
- Strengthened UI, Model-Test Alignment, TestMesh, DevelopmentProcessFlow,
  PlanDetailing, AgentWorkflowRehearsal, kernel guidance, docs, and templates
  so runnable UI claims require reachable control click-through evidence and
  payload/work-package claims require synthetic payload packs.

## v0.41.8 - 2026-06-07

AI-entry surface reduction for thinner default FlowGuard authoring.

- Added `ROUTE_STARTER_API`, `ROUTE_ADVANCED_API`,
  `PLAN_INTAKE_STARTER_API`, and `PLAN_INTAKE_ADVANCED_API` so agents can read
  compact route-specific entry points before full helper inventories.
- Made model-miss, model-test-alignment, and UI-flow template commands emit
  compact runnable defaults while adding explicit full-template commands for
  deep scaffolds.
- Added AI surface tier and route-owner metadata to the generated field
  lifecycle inventory so later field deletion can start from starter,
  advanced, and internal exposure evidence.
- Added a FlowGuard self-check model for AI-entry reduction and updated docs,
  skills, and tests to keep starter surfaces compact without hiding full
  escalation paths.

## v0.41.7 - 2026-06-07

Breaking field-schema cleanup for thinner AI-authored route inputs.

- Replaced route-specific `RiskEvidenceRow` gate columns with a compact
  `RiskEvidenceGate` list and updated ledger checks, docs, templates, tests,
  and local FlowGuard models to reject old field shapes.
- Removed AutoSplit metric fields from `ProcessEvidence`; split review now
  stays in AutoSplit, ModelMesh, or TestMesh evidence instead of being copied
  into development-process rows.
- Removed duplicate PlanIntake mapping/source evidence shapes and adapter
  fixture flags from normal mapping rows.
- Merged duplicate UI blindspot helper classes into `UIBlindspot` and reused
  `ProcessArtifact` in PlanDetail instead of maintaining a duplicate
  `PlanDetailArtifact` class.

## v0.41.6 - 2026-06-07

FieldLifecycleMesh route-evidence handoff binding.

- Added minimal `gate:`, `test:`, and `replay:` evidence-route checks for
  broad behavior-bearing field lifecycle claims while keeping bounded plans
  backward compatible.
- Updated the default replacement field-lifecycle model so full replacement
  claims require a route-bound field projection before disposal can close.
- Updated public templates, docs, tests, and installed skill guidance to make
  field models behave like route tracking instead of a field dictionary.

## v0.41.5 - 2026-06-07

Deep CI portability repair after v0.41.4.

- Fixed the shadow workspace sync helper so ignored project directories are
  evaluated relative to the source set instead of treating Linux system `/tmp`
  as a project `tmp` directory.
- Made the local closure-contract model-runner test skip gracefully when a
  GitHub checkout does not include ignored local `.flowguard` model artifacts.
- Kept the v0.41.4 maintenance hardening release intact and superseded it with
  this clean patch release instead of moving a public tag.

## v0.41.4 - 2026-06-07

Complete FlowGuard maintenance hardening.

- Added `AGENT_DEFAULT_API` as a compact first-read surface for agents while
  preserving the full route and helper API registry.
- Added tracked maintenance helpers for aggregate local `.flowguard` model
  regression and no-delete shadow workspace synchronization.
- Added a generated field lifecycle inventory so field reduction can start
  from ownership and lifecycle clues instead of text-search deletion.
- Split Model-Test Alignment Python source-audit execution into a dedicated
  module while preserving the original public imports.
- Split GitHub CI into fast push checks and scheduled/manual deep checks that
  include full unit and aggregate model regression.

## v0.41.3 - 2026-06-07

GitHub CI portability fix.

- Fixed artifact upgrade scanning so repository-relative ignored folders such
  as `tmp` are skipped without accidentally skipping Linux system temp roots.
- Kept public template privacy checks focused on real private markers while
  avoiding GitHub Actions' generic `runner` home directory false positive.
- Added regression coverage for the temp-root scan behavior exposed by CI.

## v0.41.2 - 2026-06-07

Post-release maintenance hygiene.

- Archived completed OpenSpec changes into the durable archive and kept the
  active change list focused on current work.
- Added a compact `default_flowguard_self_maintenance_plan()` helper so agents
  can start FlowGuard self-maintenance with route, API, AI-entry, and field
  defaults instead of manually filling the common plan fields.
- Added a minimal GitHub Actions CI gate for install, project audit, OpenSpec
  strict validation, the self-maintenance model, and focused unit tests.

## v0.41.1 - 2026-06-07

FlowGuard self-maintenance optimization.

- Added a route-first FlowGuard self-maintenance mesh with compact route
  profiles, AI entry profiles, field layer profiles, and child closure reports
  so agents can maintain FlowGuard without starting from the full helper list.
- Expanded public route grouping and API-surface tests so installed satellite
  routes are discoverable through stable route entries instead of scattered
  flat fields.
- Added OpenSpec coverage, a self-maintenance model, skill/docs updates,
  focused regression evidence, and shadow-workspace sync checks for the new
  maintenance path.

## v0.41.0 - 2026-06-07

Open-ended model-angle deliberation.

- Added `ModelAngleDeliberation`, `ModelAngleReviewReport`, and
  `review_model_angle_deliberations()` so agents must record what a current
  model sees, what it misses, what fails if ignored, and whether to reuse,
  extend, add a child model, create a new model, scope/defer, or ask for human
  review.
- Connected unresolved model-angle gaps to Existing Model Preflight,
  Maintenance Scan, Risk Evidence Ledger, and Closure Contract so broad
  confidence cannot hide a missing model viewpoint.
- Added `model-angle-template`, API/docs/skill guidance, OpenSpec coverage,
  focused tests, and FlowGuard self-model evidence for the new route.

## v0.40.12 - 2026-06-07

Guard-family closure contract upgrade.

- Added a reusable Guard closure contract checker for child Guard skills so
  passing claims cannot hide hard findings, missing inputs, stale evidence, or
  skipped checks.
- Updated the model-first skill guidance so SourceGuard, TraceGuard,
  LogicGuard, PhysicsGuard, research, and thesis workflows can hand AI agents
  structured next actions instead of relying on prose-only reminders.
- Added OpenSpec and FlowGuard self-model evidence for the closure-report
  maintenance path.

## v0.40.11 - 2026-06-06

Default replacement and field lifecycle hardening.

- Added FieldLifecycleMesh helpers, route-scoped API discovery, a public
  `field-lifecycle-template`, and a Codex skill route for complete leaf-level
  field accounting.
- Connected behavior-bearing field projections and old-field disposition to
  existing model preflight, code structure, architecture reduction,
  Model-Test Alignment, Model-Miss Review, DevelopmentProcessFlow, legacy path
  disposition, and Closure Contract.
- Updated project AGENTS guidance, docs, public templates, OpenSpec coverage,
  skill protocols, and FlowGuard self-model checks so replacement work cleans
  up old paths/fields by default unless compatibility is explicit and evidenced.

## v0.40.10 - 2026-06-05

AI route handoff optimization.

- Added structured owner-route, action, proof-gap, required-input, and claim
  boundary fields to SummaryReport findings, maintenance obligations,
  maintenance scan actions, and DevelopmentProcessFlow revalidation guidance.
- Added `maintenance_scan_plan_from_summary_report(...)` and
  `existing_model_preflight_from_project(...)` so agents can continue through
  existing FlowGuard routes instead of inventing a parallel session runner.
- Refreshed templates, compact skill guidance, API docs, OpenSpec artifacts,
  tests, and FlowGuard self-model evidence for the SummaryReport ->
  MaintenanceScan -> specialist-route handoff.

## v0.40.9 - 2026-06-04

Bug repair closure hardening.

- Broadened Model-Miss Review so non-trivial bug repairs use the existing
  model-miss route instead of falling back to implementation-only patches.
- Added root-cause backpropagation, owner code-contract binding, same-class
  evidence, legacy path disposition, DevelopmentProcessFlow freshness, and
  Risk Evidence Ledger closure requirements to the bug repair loop.
- Refreshed the public model-miss template, self-model, OpenSpec change,
  focused tests, and docs so model, code, and tests stay tied to the same
  repaired behavior before broad confidence.

## v0.40.8 - 2026-06-03

Soft UI typography hierarchy guidance.

- Clarified that UI text hierarchy blueprints are semantic handoff artifacts,
  not instructions to create one visual font size per hierarchy level.
- Updated FlowGuard UI Flow Structure guidance, templates, docs, and focused
  tests so typography noise is treated as a design smell with intentional
  exceptions rather than a hard numeric rule.
- Synced first-pass design, implementation review, and design iteration skills
  with calm hierarchy, reusable text treatment, and clear-rationale guidance.

## v0.40.5 - 2026-06-02

Maintenance obligation memory.

- Added route-owned `MaintenanceObligation` memory helpers so unresolved
  structure, evidence, model, and risk gaps can stay visible without creating a
  standalone technical-debt scanner.
- Extended summary reports, maintenance scans, model maturation, and Risk
  Evidence Ledger reviews so anchored open obligations reopen owner routes and
  broad confidence is blocked or scoped until obligations are resolved.
- Updated public templates, OpenSpec coverage, FlowGuard skills, docs, version
  records, and self-model checks for the maintenance-obligation memory flow.

## v0.40.4 - 2026-06-01

Model topology hazard review.

- Added `review_topology_hazards()` with `UsageIntent`, topology digests,
  anchored hazard candidates, confidence decisions, runner integration, and
  route-scoped API discovery.
- Added automatic `topology_hazard` summary sections to
  `run_model_first_checks(...)` so model-shape future-use hazards stay visible
  before broad done, release, publish, archive, or full-confidence claims.
- Connected topology hazard gaps to maintenance scan, Risk Evidence Ledger,
  public templates, OpenSpec artifacts, docs, Codex skill guidance, and
  FlowGuard self-model checks.

## v0.40.3 - 2026-06-01

Latest-schema-first upgrade policy.

- Added deterministic artifact upgrade scanning for old FlowGuard artifacts,
  model/test evidence, docs, scripts, and skill guidance.
- Extended `project-upgrade` so older adopted repositories upgrade known old
  artifacts by default, with `--records-only` for narrow record refreshes.
- Added the `artifact-upgrade` CLI, public report helpers, OpenSpec coverage,
  self-model checks, focused tests, and updated agent guidance.

## v0.40.2 - 2026-06-01

Automatic state/input closure gate.

- Added `review_state_closure()` with typed closure dimensions, representative
  unknown cases, safe handling policies, reports, and route-scoped API
  discovery.
- Added automatic `state_closure` summary sections to
  `run_model_first_checks(...)` so inferred unknown/other cases scope
  confidence by default and unsafe handling blocks confidence.
- Routed state closure maintenance gaps to `model_maturation_loop` and updated
  docs, skill guidance, OpenSpec artifacts, tests, and the FlowGuard self-model.

## v0.40.1 - 2026-06-01

FlowGuard field prompt reduction.

- Collapsed Model-Test Alignment, DevelopmentProcessFlow, TestMesh, ModelMesh,
  and adoption-log prompt fields into grouped field families.
- Preserved required evidence, freshness, boundary, skipped/not-run, release,
  and scoped-gap fields while moving rare details behind expand-when-applicable
  guidance.
- Added skill documentation tests and a FlowGuard self-model to prevent long
  blank field lists or evidence-dropping reductions from returning.

## v0.40.0 - 2026-06-01

FlowGuard maintenance scan router.

- Added `review_maintenance_scan()` with typed changed-artifact, evidence,
  signal, skipped-route, action, plan, and report rows.
- Added route-scoped `maintenance_scan_router` API discovery plus a
  `maintenance-scan-template` CLI scaffold.
- Added a FlowGuard self-model and tests that catch missing model/test
  alignment, missing StructureMesh routing, skipped-route drops, and broad
  claims without owner-route evidence.
- Updated docs and AGENTS guidance so non-trivial FlowGuard-managed work can
  route model/code/test drift, stale evidence, split pressure, and skipped
  routes to the owning maintenance skill without turning the scan into a heavy
  universal gate.

## v0.39.4 - 2026-06-01

FlowGuard guidance surface fold-down.

- Folded model-first satellite trigger detail into a compact handoff table.
- Replaced duplicate kernel reference protocol copies with satellite-owned
  handoff stubs.
- Moved long ModelMesh and Model-Test Alignment delegation prompts into
  lazy-loaded template files.
- Added skill documentation tests and guidance-compression model checks to keep
  duplicate reference bodies and eager long templates from returning.

## v0.39.3 - 2026-05-31

Codex skill diagram semantics sync.

- Added route-specific diagram intent guidance to installed FlowGuard skill surfaces.
- Clarified diagram edge meanings for development process, UI flow, model-test alignment, code-structure recommendation, and model mesh routes.
- Kept package runtime behavior unchanged.

## v0.39.2 - 2026-05-31

- Added `TestResultReuseTicket` so previous test results can be reused only
  with current command, source, tested artifact, dependency, environment,
  result fingerprint, and coverage-scope proof.
- Extended Model-Test Alignment and TestMesh to reject reused test evidence
  unless it has both a current reuse ticket and current proof artifact.
- Updated public templates, docs, OpenSpec artifacts, and FlowGuard skill
  guidance for model/test result reuse and background evidence boundaries.

## v0.39.1 - 2026-05-30

- Refreshed FlowGuard source-only release metadata after confirming the
  publication target.
- Updated package, README, and project adoption version surfaces to `0.39.1`.
- No runtime behavior, helper API, schema, or model semantics changed from
  `v0.39.0`.

## v0.39.0 - 2026-05-30

- Added Plan Detailing Compiler so rough ideas, short plans, and AI-generated
  outlines can be reviewed as typed `PlanDetail` rows before downstream
  FlowGuard routes run.
- Added projection helpers from PlanDetail to PlanIntake, Workflow Step
  Contracts, DevelopmentProcessFlow, and AgentWorkflowRehearsal.
- Added `python -m flowguard plan-detailing-template`, executable examples,
  public docs, API exports, and the `flowguard-plan-detailing-compiler`
  satellite skill.

## v0.38.0 - 2026-05-29

- Removed compatibility-only public aliases that no current FlowGuard route
  should teach agents to use: `FunctionResult.state` and the old Plan Intake
  alias exports `PlanIntakeSurface`, `PlanIntakeCompletenessFinding`,
  `FalseNegativeBackpropagationCase`, `FlowGuardClaimFinding`, and
  `review_plan_mutation_results`.
- Added a legacy compatibility cleanup FlowGuard self-model that rejects done
  claims when agents delete safety classifiers or skip installed Codex skill
  content parity.
- Updated API/check-plan docs to describe core API semantic stability and
  route-first usage without preserving obsolete compatibility-only wording.
- Added tests that keep the removed aliases out of the public API while
  preserving `SimilarityHandoff`, route-scoped discovery, and
  compatibility-surface safety classifiers.

## v0.37.0 - 2026-05-29

- Streamlined the AI-facing model-similarity surface: ordinary A/B/C
  maintenance reviews can now use `model_signature_minimal()`,
  `model_signature_maintenance()`, and
  `model_similarity_plan_for_changed_member()` before opening the full schema.
- Added `SimilarityHandoff` and `ModelSimilarityReport.to_handoff()` so
  downstream routes consume one typed handoff instead of repeated scalar
  relation/group/test/code obligation fields.
- Breaking cleanup: removed the old repeated similarity id fields from Existing
  Model Preflight, Code Structure Recommendation, Model-Test Alignment, and
  Architecture Reduction in favor of `similarity_handoff`.
- Updated route-first API docs and model-similarity templates so
  `MODELING_HELPER_API` is treated as the full index, not the first-read AI
  workflow.

## v0.36.0 - 2026-05-29

- Split public template bodies into route-scoped internal modules while
  preserving the `flowguard.templates` facade and all template CLI commands.
- Added route-scoped API registry groups so callers can discover helper families
  without scanning only the flat `MODELING_HELPER_API` list.
- Added lightweight evidence gate/detail structures for gradual contraction of
  overloaded risk and development-process evidence fields while preserving
  skipped, stale, not-run, and progress-only visibility.
- Expanded Model Similarity Consolidation into a maintenance-oriented review:
  signatures can carry code/test paths, public behaviors, shared-kernel ids,
  adapters, maintenance tags, and changed refs; reports now derive maintenance
  groups, changed-sibling impacts, shared/variant test obligations, and code
  obligations without creating a separate audit route.
- Refactored public template/API tests toward table-driven coverage and added a
  FlowGuard structure-surface simplification model for template/API/evidence
  contraction hazards.

## v0.35.0 - 2026-05-29

- Compressed FlowGuard AI-facing guidance so the kernel, satellite skills, and
  reusable AGENTS snippet now present a shorter first-read route: task triage,
  hard gates, the thin default model/check loop, compact route selection, and
  reference handoffs.
- Converted directly invokable FlowGuard satellite `SKILL.md` files into
  concise route shells while preserving standalone package verification,
  AGENTS/version adoption checks, evidence honesty, Mermaid snapshot guidance,
  and non-goals.
- Added guidance-compression FlowGuard checks that reject prompt-only
  completion claims until prompt budgets, validation, editable install,
  installed skills, shadow workspace, and local git evidence are aligned.
- Added prompt-budget tests for the kernel, satellite skills, and AGENTS
  snippet to prevent the hot path from regrowing into long protocol text.

## v0.34.0 - 2026-05-29

- Added Model Similarity Consolidation so structured model signatures can be
  compared before agents create parallel model boundaries or shared code. The
  new route classifies same-workflow, family-variant, symmetric-flow,
  shared-kernel, duplicate-boundary, overlapping-ownership, parent/child,
  sibling-overlap, adapter-only, evidence-duplicate, false-friend, unrelated,
  and manual-review relations.
- Added `ModelSignature`, `ModelSimilarityEvidence`,
  `ModelSimilarityRelation`, `ModelSimilarityPlan`,
  `ModelSimilarityReport`, and `review_model_similarity_consolidation()` with
  evidence-gated recommendations and downstream handoffs to Existing Model
  Preflight, ModelMesh, Architecture Reduction, Code Structure Recommendation,
  StructureMesh, Model-Test Alignment, or manual review.
- Integrated model-similarity evidence into Existing Model Preflight,
  Architecture Reduction, Code Structure Recommendation, and Model-Test
  Alignment, plus CLI/template support through
  `python -m flowguard model-similarity-template`.
- Added Runtime Path Evidence so real code and tests can emit ordered runtime
  node observations that name their matching FlowGuard model ids, node ids,
  child model ids, proof artifacts, inputs, outputs, state, and behavior
  boundaries.
- Added `RuntimeNodeContract`, `RuntimePathObservation`,
  `RuntimePathAlignmentPlan`, `RuntimePathAlignmentReport`,
  `RuntimePathRecorder`, and `review_runtime_path_alignment()` with checks for
  missing, extra, stale, non-passing, out-of-order, model-binding, proof
  artifact, and boundary gaps.
- Integrated runtime path evidence into Model-Test Alignment, layered boundary
  proof, hierarchical ModelMesh child reattachment, Runtime Gateway Adoption,
  Closure Contract, workflow step contracts, CLI templates, docs, and Codex
  skill guidance so agents can compare code execution traces with parent and
  child FlowGuard model structure.
- Added Architecture Reduction compatibility-surface classification for old
  aliases, public facades, boundary adapters, archive-only surfaces, negative
  legacy tests, prune candidates, and evidence-needed compatibility surfaces
  before contraction is reported as ready.
- Archived the compatibility-surface and runtime-path OpenSpec changes into the
  main specs. Schema remains `1.0`; runtime dependencies remain Python
  standard library only.

## v0.33.0 - 2026-05-28

- Added AgentWorkflowRehearsal so AI agents can take a fresh current-machine
  skill inventory before non-trivial multi-skill work, then rehearse selected
  skills, skipped candidate skills, ordering, continue/rework gates,
  validation gaps, side effects, and final evidence claims before execution.
- Added `SkillInventorySnapshot`, `SkillCapability`, `AgentWorkflowPlan`,
  `AgentWorkflowStep`, `SkippedSkill`, `AgentWorkflowRehearsalReport`, and
  `review_agent_workflow_rehearsal()` with pass, needs-revision, scoped, and
  blocked outcomes.
- Added the `flowguard-agent-workflow-rehearsal` Codex satellite skill as a
  peer route beside the existing FlowGuard satellites, plus executable example
  scenarios for stale snapshots, skipped required skills, wrong order, weak
  validation, missing rework gates, overbroad claims, and trivial over-trigger.
- Archived the project-adoption and agent-workflow OpenSpec changes into the
  main specs. Schema remains `1.0`; runtime dependencies remain Python
  standard library only.

## v0.32.0 - 2026-05-28

- Added project adoption/version gate helpers so target repositories can carry
  a managed FlowGuard `AGENTS.md` block, `.flowguard/project.toml`, and
  adoption logs that name the FlowGuard GitHub repository and current
  package/schema versions.
- Added `project-audit`, `project-adopt`, `project-upgrade`, and
  `project-adoption-template` CLI/template entry points.
- Updated kernel and satellite Skill guidance so real target-project FlowGuard
  use checks or records the project AGENTS/version adoption state instead of
  relying on unstated machine-local knowledge.
- Updated project integration docs, README, API docs, OpenSpec artifacts, and
  focused tests. Schema remains `1.0`; runtime dependencies remain Python
  standard library only.

## v0.31.0 - 2026-05-28

- Added obligation-family parity helpers so related obligations must carry
  member-by-member mechanism evidence before a family-level confidence claim.
- Added `ObligationFamily`, `ObligationFamilyMember`,
  `ObligationFamilyEvidence`, `FamilyBadCaseSeed`,
  `derive_same_class_bad_cases()`, and
  `review_obligation_family_parity()` with provenance-aware coverage matrices.
- Added `AnalogousDefectCandidate`,
  `review_analogous_defect_scan()`, scan-radius constants, and disposition
  states so post-miss reviews ask where the same failure shape may recur before
  broad closure.
- Integrated family parity into Model-Test Alignment and the Risk Evidence
  Ledger, and added analogous-scan gates to the Risk Evidence Ledger, so wrong
  provenance, missing sibling coverage, stale/non-passing family evidence,
  open analogous candidates, and scoped gates cannot be silently promoted to
  full confidence.
- Updated OpenSpec, README, docs, skill guidance, and focused tests for the
  new generic FlowGuard gate. Schema remains `1.0`; runtime dependencies
  remain Python standard library only.

## v0.30.0 - 2026-05-28

- Added executable Closure Contract review helpers so broad done, release,
  publish, and production-confidence claims can be classified as full, scoped,
  or blocked from current route evidence.
- Added `FlowGuardClosureContractPlan`, `ClosureEvidenceReport`,
  `RuntimeTraceMapping`, `ArtifactInvalidation`, `ModelQualitySignal`,
  `SameClassMissClosure`, `RuntimeGatewayInventoryClosure`, and
  `review_flowguard_closure_contract()`.
- Added the public `closure-contract-template` CLI/template scaffold plus
  README, API, closure-contract docs, and archived OpenSpec coverage for the
  final claim boundary.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.29.0 - 2026-05-28

- Added Runtime Gateway Adoption helpers so projects can distinguish
  design-only, test-aligned, and runtime-gateway FlowGuard adoption.
- Added `RuntimeStateSurface`, `RuntimeGatewayContract`,
  `RuntimeWriteObservation`, `RuntimeGatewayAdoptionPlan`,
  `RuntimeGatewayAdoptionReport`, and `review_runtime_gateway_adoption()` to
  block runtime protection claims when critical state writes can still bypass
  declared gateways.
- Updated OpenSpec, README, API docs, Model-Test Alignment guidance, and the
  closure contract so code-boundary evidence does not get overclaimed as full
  runtime state-write protection.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.28.1 - 2026-05-27

- Added lifecycle disposition support to Architecture Reduction candidates so
  completed or historical reductions remain visible as evidence without being
  re-reported as active ready work.
- Refreshed the structure simplification and public facade maintenance boundary
  so completed CLI/template and export-surface reductions close cleanly while
  shadow-only `.flowguard` duplicate cleanup stays a local sync concern.
- Updated OpenSpec, API-surface docs, agent guidance, and focused tests for the
  completed-candidate queue semantics.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.28.0 - 2026-05-27

- Added workflow step contracts so staged process plans can declare required,
  produced, and invalidated receipts and map them into DevelopmentProcessFlow
  validation gates.
- Connected workflow step contracts to claim readiness so done/release
  confidence can reject missing or stale step receipts instead of relying on
  prose-only process order.
- Updated public docs, examples, OpenSpec artifacts, and tests for the new
  workflow-step contract helper path.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.27.0 - 2026-05-27

- Added the FlowGuard model maturation loop with `ModelMaturationSignal`,
  `ModelMaturationPlan`, `ModelMaturationReport`, and
  `review_model_maturation_loop()` so post-code, post-miss, model-test, mesh,
  code-boundary, and freshness signals become explicit model-upgrade or
  scoped-claim decisions.
- Updated README, API docs, modeling protocol, closure contract, Risk Evidence
  Ledger guidance, DevelopmentProcessFlow, Model-Test Alignment, ModelMesh, and
  installed skill-source guidance so later evidence can force model refinement
  before broad confidence is claimed.
- Added focused unit tests for current, upgrade-required, scoped, blocked,
  mesh-driven, and caller-specified model maturation decisions.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.26.0 - 2026-05-27

- Defined the FlowGuard closure contract as intrinsic to complete FlowGuard
  use: plan/risk intake, model ownership, same-class model-miss evidence,
  model-test/code alignment, mesh or boundary proof when required, evidence
  freshness, Risk Evidence Ledger, and typed claim-chain support must be
  current before full done/release/publish/production-confidence claims.
- Updated README, AGENTS snippet, model-first skill guidance, modeling
  protocol, OpenSpec artifacts, and local self-review docs so partial model or
  test evidence is reported as partial/scoped FlowGuard evidence rather than
  complete FlowGuard use.
- Added a local executable closure-contract model and focused skill-doc tests
  that reject optional-mode framing and block completion without closure gates.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.25.1 - 2026-05-27

- Added `ProofArtifactRef` and legacy path disposition helpers so strict
  FlowGuard confidence checks can reject declaration-only `passed/current`
  evidence rows.
- Updated layered boundary proof, Risk Evidence Ledger, recurring model-miss
  defect-family gates, Model-Test Alignment, and DevelopmentProcessFlow with
  `require_proof_artifacts` gates that require result paths, fingerprints,
  current route evidence, and matching obligation coverage.
- Updated docs, skills, and templates so full confidence routes consume
  proof-artifact-bound evidence and explicit old-path disposition before
  closure.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.25.0 - 2026-05-27

- Added adversarial scenario synthesis on the existing Scenario Sandbox and
  model-first runner path so Explorer counterexamples, dead branches, exception
  branches, repeated state visits, and risk semantics can become candidate
  challenge routes without creating a parallel testing workflow.
- Updated retry, deduplication, cache, and side-effect packs to reuse the
  bounded input-shape fallback builder while preserving generated scenarios as
  `needs_human_review` candidate evidence until a domain oracle is supplied.
- Updated Scenario Sandbox, helper docs, README, OpenSpec artifacts, and focused
  tests for model-derived challenge-route evidence.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.24.0 - 2026-05-27

- Added model-impact freshness helper APIs so FlowGuard framework upgrades
  classify existing `.flowguard` models before broad freshness claims.
- Added `ModelFreshnessRecord`, `UpgradeImpact`, `ModelImpactAssessment`,
  `ModelReuseTicket`, `ModelRerunEvidence`, `ModelImpactFreshnessPlan`,
  `ModelImpactFreshnessReport`, and `review_model_impact_freshness()`.
- Added an executable `.flowguard/model_impact_freshness_gate` model that
  rejects missing classification, blind reuse of old evidence, and affected
  models accepted without current rerun evidence.
- Updated framework-upgrade, DevelopmentProcessFlow, modeling protocol, helper
  layer, README, API surface docs, OpenSpec artifacts, and focused tests.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.23.1 - 2026-05-27

- Added plan-intake and typed claim-chain helper APIs so broad FlowGuard
  confidence cannot be promoted from under-declared plan inputs, lossy evidence
  adapter mappings, unbackpropagated false negatives, or known-bad mutations
  that still pass.
- Added `PlanIntakeRiskSurface`, `EvidenceAdapterMapping`,
  `FalseNegativeCase`, `PlanMutationCase`, `FlowGuardClaimDependency`, their
  review plans/reports, and the corresponding public review helpers.
- Updated public docs, model-first skill guidance, API surface exports, and
  focused tests for the new plan/adapter/miss/mutation/claim boundary.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.23.0 - 2026-05-27

- Added automatic model/test split diagnostics with `AutoSplitCandidate`,
  `AutoSplitPolicy`, `AutoSplitPlan`, `AutoSplitReport`, and
  `review_auto_mesh_splits()` so oversized, incomplete, slow, broad,
  progress-only, or release-only direct evidence routes to ModelMesh or
  TestMesh before broad parent confidence.
- Connected automatic split evidence to DevelopmentProcessFlow so done,
  release, archive, and publish claims stay blocked or scoped until current
  ModelMesh/TestMesh split gates exist.
- Added model/test split gate fields to Risk Evidence Ledger rows so final
  confidence can consume or reject required split evidence at the FlowGuard
  layer.
- Updated public templates, README, API docs, ModelMesh/TestMesh docs,
  DevelopmentProcessFlow guidance, installed skill protocols, and OpenSpec
  artifacts so automatic split is an existing-route evidence gate rather than
  a new first-class skill.
- OpenSpec validation, focused auto-split route tests, ModelMesh/TestMesh
  tests, public template tests, skill-doc tests, model examples, and full
  unittest discovery passed locally.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.22.2 - 2026-05-27

- Added model-miss closure roles to Model-Test Alignment so repaired misses can
  require both observed-regression evidence and same-class generalized test
  evidence before closure.
- Added recurring defect-family gate helpers so repeated or high-risk
  same-class model misses must name a promoted family, model obligation,
  authority boundary, observed failure, generalized case, historical holdout,
  and current external proof before full closure.
- Connected required defect-family gate status to the Risk Evidence Ledger so
  final confidence is blocked, scoped, or full at the FlowGuard layer instead
  of depending on a downstream product reminder.
- Blocked observed-bug-only, wrong-target, internal-path-only, and overclaimed
  evidence from satisfying same-class model-miss closure.
- Updated model-miss examples, public templates, FlowGuard skill protocols,
  README, API notes, check-plan guidance, and TestMesh handoff rules so tests
  must generalize with the upgraded model.
- OpenSpec validation, FlowGuard model-miss example checks, focused route tests,
  full pytest, and unittest discovery passed locally.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.22.1 - 2026-05-22

- Clarified the public README positioning: FlowGuard is a universal AI-agent
  skill layer and lightweight Python toolkit, while Codex support is an
  integration path rather than the boundary of the project.
- Updated the English and Chinese README intro so the first screen presents
  FlowGuard as a general AI-agent skill.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.22.0 - 2026-05-22

- Added explicit model-test evidence roles for primary evidence, primary
  `edge_path` evidence, leaf matrix-cell evidence, supporting contract
  evidence, and integration smoke evidence.
- Model-Test Alignment now treats multiple current primary `edge_path` proofs
  for the same obligation as a `child_model_split_required` blocker instead of
  allowing a label-only downgrade.
- Strengthened leaf boundary matrices with optional input/state axes,
  Cartesian completeness checks, unexpected-cell checks, missing observed
  behavior checks, and external-contract assertion-scope checks.
- Extended TestMesh so parent gates can require current passing evidence for
  exact leaf matrix-cell ids.
- Extended Existing Model Preflight so full parent/child preflight records
  layered proof evidence, parent coverage, child disjointness, child
  reattachment, and leaf boundary-matrix status before claiming the existing
  boundary is understood.
- Updated FlowGuard skills, docs, templates, and focused tests for the stronger
  leaf-boundary evidence path.
- Added a thin default AI entry path across the FlowGuard kernel, AGENTS
  snippet, README, API surface docs, and product architecture docs:
  model the risky boundary as `Input x State -> Set(Output x State)`, add one
  invariant or scenario, run checks, inspect counterexamples, and escalate only
  when a named risk requires it.
- Reframed advanced satellites, helper APIs, meshes, ledgers, and framework
  suites as escalation paths rather than default reading for every FlowGuard
  task.
- Updated the skill-kernel FlowGuard model and skill-doc tests to catch a
  buried default path, advanced-route over-triggering, public/internal surface
  mixing, and stale satellite-count topology.
- Corrected the local satellite topology rollout model from the obsolete
  seven-satellite wording to the current ten-satellite topology.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.21.0 - 2026-05-22

- Added layered boundary proof helpers:
  `ParentCoverageItem`, `ChildProofContract`, `ChildReattachmentProof`,
  `LeafBoundaryMatrix`, `LeafBoundaryMatrixCell`,
  `LayeredBoundaryProofPlan`, and `review_layered_boundary_proof(...)`.
- Added a four-table parent confidence gate for parent coverage, child
  disjointness, child reattachment, and leaf
  `Input x State -> Set(Output x State)` boundary-matrix evidence.
- Added `python -m flowguard layered-boundary-proof-template`, public docs, and
  focused tests for green proof, coverage gaps, illegal overlap, stale
  reattachment, missing leaf cells, output overflow, progress-only evidence,
  and too-large leaf split-required cases.
- Updated the FlowGuard kernel, ModelMesh, Model-Test Alignment, TestMesh,
  Existing Model Preflight, DevelopmentProcessFlow, Code Structure
  Recommendation, StructureMesh, Architecture Reduction, and Model-Miss Review
  guidance so parent/child model confidence now has an explicit leaf-boundary
  proof chain.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.20.0 - 2026-05-21

- Added code-boundary conformance helpers: `CodeBoundaryContract`,
  `CodeBoundaryObservation`, `CodeBoundaryConformanceReport`, and
  `review_code_boundary_conformance(...)`.
- Extended Model-Test Alignment so a plan can include runtime boundary
  observations and block green alignment when real code accepts forbidden
  inputs or emits undeclared outputs, error paths, state writes, or side
  effects.
- Updated the model-test-alignment template, public docs, AGENTS snippet, and
  FlowGuard satellite skills so finite model-backed code boundaries require
  current boundary evidence before code conformance is claimed.
- Added an executable FlowGuard rollout model and focused tests for accepted
  inputs, rejected input gates, extra outputs, extra side effects, stale or
  internal-path-only observations, and alignment integration.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.19.1 - 2026-05-21

- Added Risk Evidence Ledger public APIs: `RiskEvidenceRow`,
  `RiskEvidenceProof`, `RiskEvidenceLedgerPlan`,
  `RiskEvidenceLedgerReport`, and `review_risk_evidence_ledger(...)`.
- Added `risk-evidence-ledger-template`, public docs, and an executable rollout
  model that catches internal-path-only and progress-only final confidence
  claims.
- Updated FlowGuard kernel and satellite skill guidance so final done, release,
  publish, and full-confidence claims must connect user risks to model
  obligations, optional public code contracts, and current proof evidence.
- Extended adoption logging with `risk_evidence_summary` so scoped or blocked
  confidence boundaries are recorded alongside commands, skipped steps, and
  findings.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.19.0 - 2026-05-21

- Added Architecture Reduction as a FlowGuard route for using existing models to
  find behavior-preserving code contraction opportunities before implementation.
- Added public helper APIs `ObservableArchitectureContract`,
  `ArchitectureReductionCandidate`, `ArchitectureReductionPlan`, and
  `review_architecture_reduction(...)`.
- Added candidate types, proof statuses, target actions, public-entrypoint
  StructureMesh gates, and target-structure handoff checks so risky shrinkage
  stays visible instead of becoming a silent rewrite.
- Added the `flowguard-architecture-reduction` Codex skill and updated
  companion FlowGuard skills so development, existing-model preflight,
  structure, mesh, model-test, and UI routes know when to invoke it.
- Added OpenSpec artifacts, local FlowGuard route-safety model checks, API
  docs, README coverage, and focused regression tests for the new route.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.18.6 - 2026-05-20

- Added validation-failure triage to DevelopmentProcessFlow so failed, stale,
  oversized, progress-only, or parent/child-sensitive validation is classified
  before agents keep patching or claim done.
- Added handoff guidance from DevelopmentProcessFlow to ModelMesh, TestMesh,
  and Model-Test Alignment for model-too-thick, test-too-thick, model-test
  mismatch, stale-evidence, and parent/child reattachment cases.
- Added Existing Model Preflight as a FlowGuard companion route for grounding
  discussion, proposals, bug fixes, feature work, refactors, prompts, skills,
  UI, test, and process changes in current FlowGuard model ownership before a
  new boundary is proposed.
- Added public helper APIs `ExistingModelPreflight`, `ModelContextHit`,
  `ExistingOwnershipSnapshot`, `DuplicateBoundaryRisk`, and
  `review_existing_model_preflight(...)`.
- Added `python -m flowguard existing-model-preflight-template`, a Codex skill,
  OpenSpec artifacts, local FlowGuard model checks, README/API docs, and route
  trigger coverage for the new preflight path.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.18.5 - 2026-05-20

- Refined FlowGuard diagram guidance so agents choose route-specific diagram
  semantics before drawing: behavior/state, development process, UI state,
  model-test coverage, code structure, or mesh.
- Clarified that FlowGuard diagrams are standalone FlowGuard guidance and do
  not require LogicGuard or a shared cross-family protocol.
- Kept diagrams explanatory only; executable checks, evidence freshness, and
  route-specific validation remain the confidence source.

## v0.18.4 - 2026-05-20

- Strengthened user-facing FlowGuard model visibility: non-trivial FlowGuard
  work now defaults to a Mermaid model snapshot during the work once the route
  or model shape is stable enough to explain.
- Extended route-specific diagram guidance across all installed FlowGuard
  satellite skills, while preserving concise output for tiny, obvious,
  direct-command, formatting-only, or user-suppressed tasks.
- Standardized global FlowGuard routing so clear staged-development, UI,
  structure, test, mesh, alignment, and model-miss work can select direct
  satellite skills instead of treating the model-first kernel as a universal
  first stop.
- Added OpenSpec artifacts and a local FlowGuard prompt-behavior model for the
  visibility rollout; diagrams remain explanation aids and do not count as
  validation evidence.
- Schema remains `1.0`; runtime dependencies and public Python APIs are
  unchanged.

## v0.18.3 - 2026-05-19

- Added lightweight user-facing Mermaid diagram guidance to the FlowGuard skill
  kernel so non-trivial model value can be explained when prose alone would hide
  the states, branches, gates, evidence, or claim boundary.
- Added route-specific optional diagram guidance for UI Flow Structure,
  ModelMesh, and DevelopmentProcessFlow while keeping diagrams as explanation
  aids, not validation evidence.
- Added OpenSpec artifacts and used a local FlowGuard self-model for the prompt
  behavior so the rollout rejects overbroad mandatory diagrams, shallow diagram
  guidance, and missing selected-route coverage.
- Schema remains `1.0`; runtime dependencies and public Python APIs are
  unchanged.

## v0.18.2 - 2026-05-19

- Added UI implementation validation for implemented/runnable UI completion
  claims, aligning user-visible feature contracts, reviewed UI journey
  coverage, and browser, desktop, or manual click-through evidence.
- Added public helper APIs `UIFeatureContract`, `UIImplementationValidation`,
  `UIImplementationJourneyRun`, `UIImplementationStepEvidence`,
  `UIImplementationBlindspot`, `UIImplementationValidationReport`, and
  `review_ui_implementation_validation(...)`.
- Updated the UI Flow Structure template so generated scaffolds now demonstrate
  feature contracts, implementation journey runs, model revision/freshness, pure
  UI actions, residual implementation blindspots, and known-bad missing
  implementation evidence.
- Updated the UI Flow Structure skill, Skill Kernel route guidance, AGENTS
  snippet, API docs, UI docs, README, OpenSpec artifacts, and focused tests so
  "model-complete UI" is not confused with "running UI clicked through."
- Broadened DevelopmentProcessFlow routing guidance so staged implementation,
  validation freshness, archive readiness, and release confidence checks are
  selected earlier for non-trivial development work.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.18.1 - 2026-05-19

- Added ModelMesh mesh-closure meta-models so parent/child model handoffs can be
  checked as executable FlowGuard-style obligations before whole-flow parent
  confidence is claimed.
- Added public helper APIs `MeshClosureModel`, `MeshClosureTransition`,
  `MeshClosureJoin`, `MeshClosureTerminal`, `MeshClosureReport`,
  `MeshClosureFinding`, and `review_mesh_closure_model(...)`.
- Updated `review_hierarchical_mesh(...)` so a declared closure model must pass
  before `mesh_green_can_continue`; closure blockers include missing root
  entries, unknown output references, unconsumed child outputs, incomplete joins,
  terminal leaks, missing out-of-scope rationale, and loop-like handoffs without
  progress evidence.
- Updated OpenSpec artifacts, ModelMesh docs, API docs, README, hierarchical
  examples, skill guidance, and focused tests for the new whole-flow closure
  gate.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.18.0 - 2026-05-19

- Added app-level UI journey coverage for complete UI claims, including launch
  state, top-level entry points, feature journeys, success terminals,
  failure/recovery/cancel/exit handling, terminal action allowances, and
  residual blindspots.
- Added public helper APIs `UIJourneyCoverage`, `UIJourneyEntryPoint`,
  `UIFeatureJourney`, `UITerminalActionAllowance`, `UIResidualBlindspot`,
  `UIJourneyCoverageReport`, and `review_ui_journey_coverage(...)`.
- Updated the UI Flow Structure template so generated scaffolds now model
  launch, new-project, load-existing, failure, cancel, export, exit, terminal,
  and residual-blindspot coverage before structure and text hierarchy handoff.
- Updated the UI Flow Structure skill, Skill Kernel route guidance, AGENTS
  snippet, API docs, UI protocol docs, README, OpenSpec artifacts, and focused
  tests so "complete app UI" is not claimed from layout/text evidence alone.
- Added known-bad coverage cases for missing launch entries, unreachable path
  states, unknown path events, missing success terminals, unhandled failures,
  visible controls without modeled events, reachable events outside all
  journeys, terminal forward actions, misclassified terminal exports, and
  blindspots without validation boundaries.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.17.1 - 2026-05-19

- Added ModelMesh boundary-diff propagation so repaired child models can report
  `unaffected`, `reattach_only`, `parent_rerun_required`,
  `sibling_rerun_required`, or `split_review_required` before parent
  confidence is claimed.
- Added public helper API `ChildBoundaryChangeSummary` and
  `summarize_child_boundary_change(...)`, and extended `ChildModelEvidence`
  with function, invariant, risk-class, and validation-evidence ownership
  fields.
- Updated ModelMesh review to expose boundary change decisions, reject
  point-fix-only bug-instance targets, and mark affected parent or sibling
  evidence stale when a child boundary changes.
- Hardened the public `model-miss-template` so generated review models now
  distinguish the observed issue, a same-class generalized bad case, and the
  known bug's holdout validation role before a repair can be finalized.
- Added generated negative scenarios that reject point-fix-only validation and
  validation that forgets to record the known bug as holdout evidence.
- Updated focused ModelMesh, public-template, Skill-doc, and OpenSpec artifacts
  for the boundary propagation and template hardening release.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.17.0 - 2026-05-18

- Added the ModelMesh child reattachment gate for local child model repairs:
  parent mesh confidence now requires current child evidence consumption plus
  stable input, output, state ownership, side-effect ownership, and outgoing
  contract handoffs.
- Added public helper API `ChildReattachmentContract` and extended
  `ChildModelEvidence` with evidence id, accepted inputs, emitted outputs, and
  incoming contract fields.
- Updated post-runtime model-miss review so a miss repaired inside a child model
  under a parent mesh remains open until the affected parent reattachment gate
  passes or records a blocker.
- Updated OpenSpec artifacts, Skill docs, public docs, examples, README, and
  focused tests to make "child-local green is not parent green" explicit.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.16.0 - 2026-05-18

- Added the UI Text Hierarchy Blueprint capability as the next public UI route.
  It reviews visible and assistive UI text by state, region, role, semantic
  key, owner, priority, duplication rationale, and warning/error escalation
  before copy, layout, or implementation flatten everything into equal prose.
- Added UI text hierarchy helper APIs:
  `UITypographyToken`, `UITextElement`, `UITextHierarchyBlueprint`,
  `UITextHierarchyReport`, and `review_ui_text_hierarchy(...)`.
- Updated `ui-flow-structure-template` so generated UI models now run the full
  three-stage review: interaction model, structure derivation, and text
  hierarchy blueprint, including known-bad text hierarchy hazards.
- Positioned UI Text Hierarchy Blueprint as a sibling to UI Flow Structure:
  UI Flow Structure derives controls, regions, overlays, and stable placement
  from modeled interaction behavior, while UI Text Hierarchy Blueprint derives
  which headings, labels, helper text, status text, empty/loading/success/
  failure text, CTA text, warnings, and errors should dominate or stay local in
  each state.
- Added OpenSpec artifacts under
  `openspec/changes/add-ui-text-hierarchy/` covering proposal, design, tasks,
  and requirements for text inventory, primary/secondary hierarchy, duplicate
  semantic text, state-specific copy, blocking warnings, assistive rationale,
  and handoff boundaries.
- Updated README and product architecture docs to foreground the new capability
  while preserving the `v0.15.0` UI Flow Structure material.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.15.0 - 2026-05-18

- Added the UI Flow Structure route for model-first interface design. The new
  helper first reviews a UI interaction model covering initial states, controls,
  events, state nodes, transitions, failures, recovery paths, terminal states,
  and control availability before deriving layout structure.
- Added UI flow structure helper APIs:
  `UIControl`, `UIDisplayElement`, `UIStateNode`, `UITransition`,
  `UIInteractionModel`, `UIRegionRecommendation`, `UIStructureDerivation`,
  `UIFlowStructureFinding`, `UIInteractionModelReport`,
  `UIStructureDerivationReport`, `review_ui_interaction_model(...)`, and
  `review_ui_structure_derivation(...)`.
- Added findings for missing initial states, missing availability matrices,
  unmodeled controls, failures without recovery, destructive primary/global
  controls, duplicate information in one state, same-level controls that
  trigger the same modeled function without a rationale, structure derivation
  before reviewed interaction evidence, missing parent surfaces, missing region
  maps, duplicate region ownership, duplicate information in one region,
  contextual controls placed globally, and overlays without origin or return
  paths.
- Added a `ui-flow-structure-template` CLI scaffold and public documentation
  for deriving first-level persistent areas, second-level contextual regions,
  third-level local actions, overlays, navigation ownership, and stable control
  placement from modeled UI behavior.
- Added the `flowguard-ui-flow-structure` Codex satellite skill and updated the
  Skill Kernel route map, AGENTS snippet, modeling protocol docs, API surface,
  product architecture docs, README, OpenSpec artifacts, and focused tests.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.14.0 - 2026-05-18

- Upgraded the Codex-facing skill architecture to one FlowGuard Skill Kernel
  plus seven directly invokable satellite skills:
  `flowguard-model-test-alignment`, `flowguard-development-process-flow`,
  `flowguard-model-miss-review`, `flowguard-code-structure-recommendation`,
  `flowguard-model-mesh`, `flowguard-test-mesh`, and
  `flowguard-structure-mesh`.
- Updated the global AGENTS snippet, README, product architecture docs, release
  checklist, OpenSpec artifacts, and skill-doc tests so the first-batch
  satellite topology is explicit while helper APIs and CLI templates remain
  package helpers rather than Codex skills.
- Added DevelopmentProcessFlow helper APIs:
  `ProcessArtifact`, `ActionEffect`, `ProcessAction`, `ProcessEvidence`,
  `FreshnessRule`, `ValidationRequirement`, `DevelopmentProcessPlan`,
  `RevalidationRecommendation`, `ProcessFlowFinding`,
  `DevelopmentProcessFlowReport`, `review_development_process_flow(...)`, and
  `derive_revalidation_plan(...)`.
- Added lifecycle findings for stale evidence after artifact changes, verifier
  changes after validation, model-test alignment evidence after model changes,
  requirement freshness propagation, unknown peer writes, ambiguous freshness
  policy, progress-only evidence, hidden skipped validation, failed/not-run
  evidence, missing V-style validation pairs, and release overclaims.
- Added a `development-process-flow-template` CLI scaffold and public docs for
  modeling development lifecycle ordering, artifact overwrite, evidence
  freshness, and minimum revalidation as a sibling route.
- Updated the model-first Skill Kernel, AGENTS snippet, API surface, README,
  OpenSpec artifacts, focused tests, and FlowGuard rollout model.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.13.0 - 2026-05-18

- Added conservative Python source-audit helpers for Model-Test Alignment:
  `PythonCodeContractEvidence`, `PythonTestAssertionEvidence`,
  `ContractSourceAuditFinding`, `ContractSourceAuditReport`,
  `audit_python_code_contracts(...)`, `audit_python_test_assertions(...)`, and
  `review_python_contract_source_audit(...)`.
- The source audit checks real Python functions for declared symbols, external
  inputs, return values for external outputs, state writes, declared side
  effects, and side-effect-looking extra calls before trusting `CodeContract`
  rows.
- The test audit checks real Python tests for target code-contract calls and
  assertions before trusting `TestEvidence` rows that claim external-contract
  proof.
- Added source-level findings such as `source_contract_missing_symbol`,
  `source_contract_missing_input`, `source_contract_missing_output`,
  `source_contract_missing_state_write`, `source_contract_extra_side_effect`,
  `source_test_missing_code_contract_call`,
  `source_test_missing_external_assertion`, and
  `source_test_internal_path_only`.
- Updated templates, docs, Skill guidance, OpenSpec artifacts, focused tests,
  and a FlowGuard rollout model for source-audit hazards.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.12.0 - 2026-05-18

- Upgraded Model-Test Alignment so `review_model_test_alignment(...)` can
  compare FlowGuard model obligations, optional code external contracts, and
  ordinary test evidence in one direct review.
- Added `CodeContract`, code-contract role constants, test assertion-scope
  constants, and optional external-contract fields on `ModelObligation`,
  `TestEvidence`, and `ModelTestAlignmentPlan`.
- Added findings for missing code contract owners, code contracts that miss
  model-declared external behavior, exact contracts that add extra external
  behavior, missing code-contract test evidence, tests that bind only model
  obligations when code contracts are in scope, internal-path-only tests,
  unknown code contract references, duplicate code contract owners, and
  model-code-test binding mismatches.
- Kept model-test-only reviews backward compatible: code contracts are optional
  unless a plan explicitly requires them.
- Updated the Model-Test Alignment template, CLI help, public documentation,
  README, API surface docs, Skill Kernel route guidance, AGENTS snippet,
  OpenSpec artifacts, focused tests, and a FlowGuard rollout model for the new
  contract-alignment hazards.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.11.0 - 2026-05-17

- Added Code Structure Recommendation helper APIs:
  `TargetModuleRecommendation`, `CodeStructureRecommendation`,
  `CodeStructureFinding`, `CodeStructureRecommendationReport`, and
  `review_code_structure_recommendation(...)`.
- Added review checks for missing source FlowGuard model evidence, missing
  parent boundary, missing target modules, missing FunctionBlock maps, missing
  validation plans, missing module rationales, unregistered owners, and
  duplicate FunctionBlock/state/side-effect/config ownership.
- Added a `code-structure-recommendation-template` CLI scaffold, public
  documentation, Skill Kernel route guidance, OpenSpec artifacts, focused
  tests, and a StructureMesh rollout model that catches target structures that
  are not model-derived or do not map model boundaries.
- Upgraded StructureMesh so existing large-script or large-module splits must
  include model-derived target code structure evidence inside the
  `StructureMeshPlan`; missing or mismatched target structure now blocks
  refactor confidence.
- Upgraded ModelMesh and TestMesh parent confidence checks to require
  FlowGuard-derived target split derivations before trusting child model or
  child suite/script ownership.
- Added `ModelTargetSplitDerivation` and `TestTargetSplitDerivation` helper
  records, protocol guidance, focused tests, and a FlowGuard rollout model for
  target split derivation coverage.
- Kept ordinary model-first work flexible: Code Structure Recommendation is a
  parallel route for direct architecture/file-split recommendations, not a hard
  gate for every FlowGuard model.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.10.0 - 2026-05-17

- Added standalone Model-Test Alignment helper APIs:
  `ModelObligation`, `TestEvidence`, `ModelTestAlignmentPlan`,
  `ModelTestAlignmentFinding`, `ModelTestAlignmentReport`, and
  `review_model_test_alignment(...)`.
- Added coverage checks for missing model obligations, missing required test
  kinds, orphan or unknown test evidence, duplicate evidence ownership,
  stale/non-passing evidence, overclaimed confidence, and duplicate model
  obligation IDs.
- Added a `model-test-alignment-template` CLI scaffold, public documentation,
  Skill Kernel route guidance, OpenSpec artifacts, focused tests, and a
  FlowGuard rollout model that catches missing route visibility and accidental
  dependency on TestMesh, StructureMesh, or ModelMesh.
- Kept Model-Test Alignment independent from mesh split helpers: it compares
  explicit model obligations with explicit test evidence and does not split
  tests, refactor code, or read mesh reports.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.9.0 - 2026-05-17

- Added StructureMesh helper APIs for parent/child structure refactor
  governance: `StructureMeshPlan`, `StructurePartitionItem`,
  `ModuleStructureEvidence`, `PublicEntrypointEvidence`,
  `StructureMeshFinding`, `StructureMeshReport`, and
  `review_structure_mesh(...)`.
- Added checks for missing or unregistered partition owners, duplicate
  partition owners, duplicate state/side-effect/config ownership, removed
  public entrypoints, missing facades, unsafe dependency cycles, config/default
  drift, missing or stale behavior parity, insufficient evidence tiers, and
  release-required parity gaps.
- Split routine and release refactor scopes so release-only structure evidence
  can remain visible as deferred obligations during routine work while still
  blocking release confidence when missing.
- Added a `structure-mesh-template` CLI scaffold, StructureMesh documentation,
  OpenSpec artifacts, Skill guidance, reusable AGENTS guidance, focused tests,
  and a FlowGuard rollout model for large script/module split governance.
- Modularized the `model-first-function-flow` Skill into a compact FlowGuard
  Skill Kernel plus dedicated sub-protocol references for core modeling,
  ModelMesh, TestMesh, StructureMesh, post-runtime model misses,
  conformance/adoption, long-check observability, and FlowGuard framework
  upgrades.
- Added a Skill Kernel rollout model that catches missing hard gates, route
  gaps, duplicate rule ownership, helper APIs mislabeled as sub-skills,
  standalone FlowGuard regressions, heavy-check over-triggering, and missing
  release/install sync routes.
- Clarified TestMesh as the test-side sibling of ModelMesh and StructureMesh:
  large test scripts, suites, or validation flows split into parent/child test
  hierarchy layers while parent gates consume child ownership and evidence
  contracts instead of expanded child internals.
- Added a soft oversize hint to the Skill Kernel so agents consider
  parent/child splits for large, slow, or hard-to-follow models, tests, scripts,
  modules, and commands without adding fixed thresholds or external planner
  dependencies.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.8.0 - 2026-05-17

- Added TestMesh helper APIs for layered validation governance:
  `TestMeshPlan`, `TestPartitionItem`, `TestSuiteEvidence`,
  `TestMeshFinding`, `TestMeshReport`, and `review_test_mesh(...)`.
- Added parent/child test partition checks for missing owners, unregistered
  owners, duplicate partition ownership, duplicate state-write ownership, and
  duplicate side-effect ownership.
- Added evidence checks for stale results, hidden skipped tests, failed suites,
  timeout suites, insufficient evidence tiers, and background progress without
  final exit/result artifacts.
- Split routine and release validation scopes so release-only suites can remain
  visible as deferred obligations during routine work while still blocking
  release confidence when missing.
- Added a `test-mesh-template` CLI scaffold, TestMesh documentation, OpenSpec
  artifacts, Skill guidance, reusable AGENTS guidance, focused tests, and a
  FlowGuard rollout model that catches flat slow gates, missing/unregistered
  owners, duplicate owners, stale/hidden/timeout evidence, background
  progress-only overclaims, missing release evidence, and direct-test-runner
  scope creep.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.7.3 - 2026-05-16

- Added hierarchical model-mesh helper APIs for parent partition maps, child
  model evidence summaries, mesh findings, and mesh decisions.
- Added `review_hierarchical_mesh(...)` to check parent coverage gaps, unsafe
  sibling overlap, duplicate state-write ownership, duplicate side-effect
  ownership, stale/skipped child evidence, large-model split triggers, and
  legacy compatibility boundaries.
- Added `classify_legacy_model(...)` so existing model scripts can be
  registered and wrapped before they are trusted as strong child evidence.
- Extended model-mesh guidance to trigger from both model count and single-model
  scale, including estimated/observed state counts above 10,000, incomplete
  budgeted model groups, and models with unrelated functional areas.
- Added a nested hierarchy example, OpenSpec artifacts, focused tests, and a
  FlowGuard rollout model that catches missing scale triggers, coverage gaps,
  hidden overlap, duplicate ownership, legacy direct trust, child-graph
  expansion, background-check overclaims, and release-sync omissions.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.7.2 - 2026-05-15

- Simplified post-runtime model-miss review in the `model-first-function-flow`
  Skill to five practical miss types: `boundary_missing`,
  `state_too_coarse`, `input_branch_missing`, `invariant_too_weak`, and
  `evidence_overclaimed`.
- Required in-scope model misses to represent the observed issue plus one
  same-class generalized bad case when practical, so repairs do not stop at the
  exact bug that was just found.
- Kept the model-miss workflow lightweight: ordinary model misses do not add a
  default hazard registry, upgrade reviewer, model mesh, full coverage matrix,
  or evidence-level field.
- Updated OpenSpec artifacts, the reusable AGENTS snippet, modeling protocol,
  focused docs tests, and a FlowGuard rollout model for the revised workflow.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.7.1 - 2026-05-15

- Added a pre-implementation model-hardening gate to the
  `model-first-function-flow` Skill for complex optimizations, repeated bug
  repairs, stateful refactors, and model-miss-sensitive work.
- Required agents to write a change inventory, risk catalog, and risk-to-model
  coverage matrix before complex FlowGuard-backed edits.
- Clarified that representative known-bad hazards must fail before a model is
  trusted for the target bug class; happy-path checks alone are not enough.
- Added tiered handling for expensive project-specific model groups without
  hard-coding local model names as universally heavy or skippable.
- Updated the reusable AGENTS snippet, OpenSpec artifacts, focused tests, and a
  FlowGuard rollout model that catches code-first, happy-path-only, hard-coded
  heavy-model, peer-change, touched-heavy-skip, and premature-release variants.
- Ignored `tmp/` so background check logs and template smoke outputs do not
  appear as release candidates.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.7.0 - 2026-05-14

- Added budgeted model-group execution for large reachable graph models via
  `BudgetedGraphConfig` and `run_budgeted_graph_checks()`.
- Added a SQLite ledger that records seen, pending, processed, labels, failure
  samples, and shard summaries so repeated runs continue from pending work
  instead of starting over.
- Added fingerprinted run directories so changed model inputs, budgets,
  invariants, required labels, or caller-provided fingerprint parts do not reuse
  stale model evidence.
- Added whole-group reporting that distinguishes `complete`, `incomplete`, and
  `failed`; `ok` is true only when no pending states, failures, or missing
  required labels remain.
- Added shard-local progress plus model-group processed/pending totals on
  `stderr`, while preserving existing `Explorer` progress behavior.
- Added OpenSpec artifacts, a FlowGuard rollout self-model, focused tests,
  documentation, and a FlowPilot-style example for budgeted graph checks.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.6.1 - 2026-05-14

- Added a standard background-log contract for long-running FlowGuard checks:
  `tmp/flowguard_background/` with stdout, stderr, combined output, exit-code,
  and metadata artifacts.
- Updated the `model-first-function-flow` Skill and reusable AGENTS snippet so
  agents must inspect actual log and exit artifacts before reporting long checks
  as complete.
- Clarified that direct `Explorer(...)` progress and legacy/custom runner final
  reports are different evidence types; final summaries are not live progress.
- Added OpenSpec change artifacts and doc tests that pin the log root, artifact
  names, completion evidence, and proof-reuse reporting expectations.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.6.0 - 2026-05-14

- Added an optional spec/SPAC-style skill-orchestrator collaboration model that
  keeps FlowGuard standalone while allowing upstream planning tools to hand off
  structured plans for risk review.
- Added `docs/skill_orchestrator_collaboration.md` with the three operating
  modes, the handoff contract, the upgrade sequence, known hazards, validation
  order, and non-goals.
- Updated the `model-first-function-flow` Skill, reusable AGENTS snippet, and
  project integration docs so upstream planner handoffs are optional context,
  not a FlowGuard dependency.
- Added tests that prove complete handoffs pass, missing upstream planners fall
  back to standalone FlowGuard, incomplete handoffs block collaboration only,
  and broken variants are caught for hard dependencies, hidden side effects,
  missing parallel ownership, skip-without-reason, ignored counterexamples,
  over-triggering trivial work, and completion without evidence.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.5.5 - 2026-05-13

- Added default ten-step progress output for `Explorer.explore()` so long
  serial model runs emit start and progress lines on `stderr` while preserving
  `stdout` for reports and JSON pipelines.
- Counted progress by top-level `initial_state x input_sequence` work units and
  kept the run serial and deterministic.
- Added `progress_steps=0` and `FLOWGUARD_PROGRESS=0` opt-outs for strict CI or
  callers that need silent runs.
- Added a FlowGuard rollout model plus focused tests for stderr routing,
  bounded output, small totals, opt-outs, runner inheritance, and report
  stability.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.5.4 - 2026-05-12

- Added Risk Purpose Headers to generated FlowGuard model templates so future
  agents can see the FlowGuard source repository, modeled workflow, guarded
  failure modes, use-before-editing guidance, and companion run command.
- Updated the `model-first-function-flow` Skill and reusable AGENTS snippet so
  AI-created or AI-updated FlowGuard model files carry the same lightweight
  header instead of only saying that they are FlowGuard artifacts.
- Used a local FlowGuard rollout model for this release that catches generic
  link-only headers, partial template coverage, missing Skill/AGENTS guidance,
  missing tests, manifest-style scope creep, and premature publication.
- Added focused tests for generated model template headers and Skill/AGENTS
  header guidance.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.5.3 - 2026-05-12

- Added a local model mesh protocol for projects with three or more FlowGuard
  models, including inventory fields, evidence tiers, required hazards, a prompt
  template, and a completion standard.
- Updated the `model-first-function-flow` Skill so multi-model FlowGuard
  projects must inventory and connect existing models before broad continue,
  release, completion, or production-confidence claims.
- Extended the FlowGuard Skill trigger self-review with a multi-model
  maintenance scenario and a broken variant that catches omitted model-mesh
  checks.
- Updated the reusable AGENTS snippet and modeling protocol docs with the
  model-of-models trigger.
- Schema remains `1.0`; runtime dependencies and CLI templates are unchanged.

## v0.5.2 - 2026-05-10

- Clarified the `model-first-function-flow` Skill around three broad FlowGuard
  scopes: Behavior Flow, Argument Flow, and Decision Flow.
- Added concise modeling hints for behavior state, reader/argument state, and
  decision/commitment state without adding new template families or changing
  the core API.
- Updated the README and reusable AGENTS snippet so users see that the existing
  model templates remain the execution scaffolds for all three flow types.
- Extended the Skill trigger self-review with structured argument and decision
  planning scenarios.
- Schema remains `1.0`; runtime dependencies and CLI templates are unchanged.

## v0.5.1 - 2026-05-09

- Refreshed the public project template so package-generated starter files
  match the richer model-first Skill template with validation, rejection,
  repeated-input handling, and traceability checks.
- Added public-safe Risk Intent + CheckPlan and post-runtime model-miss review
  template scaffolds, including CLI writers for `project-template`,
  `risk-intent-template`, and `model-miss-template`.
- Added template execution tests and privacy-marker checks to keep public
  scaffolds neutral and free of local project details.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.5.0 - 2026-05-08

- Added `FlowGuardFindingLedger`, `FlowGuardFindingLedgerEntry`, and
  `build_finding_ledger` to flatten summary findings and skipped/not-run gaps
  into one coverage-first repair ledger.
- `FlowGuardSummaryReport.finding_ledger` now exposes the ledger, and
  `to_dict()` includes it as machine-readable output for agents.
- Updated the helper-runner self-review with a broken variant that catches
  point-rule patches made before a full finding ledger is built.
- Updated the model-first Skill, AGENTS snippet, check-plan docs, framework
  upgrade guidance, modeling protocol, and README to route FlowGuard or
  LiveFlowGuard self-upgrades through coverage-first triage.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.4.2 - 2026-05-07

- Added Post-Runtime Model-Miss Review guidance to the model-first Skill:
  runtime, test, replay, or manual-validation failures after a FlowGuard pass
  must reopen the model-first loop instead of becoming direct patch-and-finish
  work.
- Clarified that agents should classify why the prior model missed the issue,
  represent in-scope misses as scenarios, invariants, replays, representative
  traces, or explicit out-of-scope boundaries, then rerun checks before
  validating the repair.
- Updated the reusable AGENTS snippet, modeling protocol, project integration
  notes, README, and Skill doc tests for the new completion gate.
- No core API, schema, runtime dependency, or CLI behavior changed.

## v0.4.1 - 2026-05-07

- Clarified that when no FlowGuard model exists yet, the AI agent should create
  one from the current plan or adapt the included model template instead of
  refusing the task.
- Reframed the model as a fit-for-risk, customer-purpose artifact rather than
  always a minimal script: it should capture the failure modes the customer
  wants to expose and grow as new risks appear.
- Updated the README, AGENTS snippet, modeling protocol, project integration
  notes, and Skill wording to make evolving model scripts part of the public
  onboarding path.
- No core API, schema, runtime dependency, or CLI behavior changed.

## v0.4.0 - 2026-05-02

- Added `RiskIntent` for explicit pre-modeling briefs that name failure modes,
  protected harms, model-critical state, adversarial inputs, hard invariants,
  and blindspots.
- Extended `RiskProfile` with an optional `risk_intent` field and audit
  suggestions for missing or thin Risk Intent Briefs.
- Updated the model-first Skill, modeling protocol, check plan docs, API
  surface docs, and README to make Risk Intent Briefs part of the public
  FlowGuard workflow.
- Fixed README version-section ordering so release notes read newest to oldest:
  `v0.4.0`, `v0.3.1`, `v0.3.0`, then `v0.2.0`.

## v0.3.1 - 2026-05-02

- Added opt-in Mermaid source exporters for representative traces, generic
  state graphs, and loop review graphs.
- Exposed `trace_to_mermaid_text`, `graph_to_mermaid_text`,
  `loop_report_to_mermaid_text`, and `mermaid_code_block` through the public
  FlowGuard reporting helper API.
- Updated the README with English and Chinese Mermaid examples showing how
  FlowGuard turns a risky request into a finite model, reachable traces,
  findings, and optional conformance replay.
- Added a runnable `examples/mermaid_export_example.py` script that prints a
  Markdown Mermaid code block.
- Documented that Mermaid output is copyable text source and remains off by
  default so routine reports stay concise.

## v0.3.0 - 2026-04-30

- Expanded the `model-first-function-flow` Skill from coding/repository-only
  framing to coding, repository, and process-design work.
- Added `process_preflight` mode for non-code or mixed workflows that need
  validation, adjustment, observation, or loss-prevention review before action.
- Clarified that booking, purchase, publication handoff, operational runbook,
  data migration, support escalation, and multi-agent coordination flows can be
  modeled when they have meaningful state, side effects, external dependencies,
  rollback concerns, or irreversible cost.
- Preserved the skip boundary for trivial reversible tasks and clarified that
  non-code process models are risk-discovery preflights, not proof of real-world
  prices, availability, policies, or vendor behavior.
- Updated the README, AGENTS snippet, Skill documentation, and Skill doc tests
  for the broader process-preflight scope.

## v0.2.1 - 2026-04-30

- Simplified the `model-first-function-flow` Skill adoption-note wording so
  agents leave a short plain-language record instead of treating adoption
  logging as a heavy field checklist.
- Clarified that the adoption CLI can help create the log entry, but it is not
  a substitute for a short human-readable note when the model found something
  important.
- Updated the reusable AGENTS snippet with the same lighter note guidance.
- Clarified that `SCHEMA_VERSION` / `python -m flowguard schema-version`
  reports the artifact schema version, not the GitHub/package release version.

## v0.2.0 - 2026-04-30

- Added optional standard property factories, model quality audit,
  `RiskProfile`, `FlowGuardCheckPlan`, and `run_model_first_checks()` to make
  model-first checks easier for AI coding agents without changing the core
  `Input x State -> Set(Output x State)` model.
- Added deterministic counterexample minimization, scenario matrix generation,
  unified summary reporting, and lightweight domain packs for deduplication,
  cache, retry, and side-effect risks.
- Added helper surfaces for adoption evidence review, state-write inventory,
  low-friction adoption logging, and optional maintenance workflow scaffolding.
- Expanded public examples, benchmark/evidence documentation, self-review
  models, and tests while keeping runtime dependencies at Python standard
  library only.
- Clarified that warnings, skipped checks, and `pass_with_gaps` are confidence
  boundaries, not hard failures and not production conformance claims.

## v0.1.3 - 2026-04-29

- Added model-fidelity calibration guidance to the `model-first-function-flow`
  Skill.
- Added a modeling protocol step that treats FlowGuard models as falsifiable
  simulators of real workflows, not ground truth.
- Clarified that conformance replay and replay adapters must not hide relevant
  production behavior.
- Updated the reusable AGENTS.md snippet to record model-fidelity gaps and
  calibration changes.
- Refreshed the README positioning around FlowGuard as an architecture
  simulator / finite-state workflow simulator, including the hero tagline and
  AI-agent install path.
