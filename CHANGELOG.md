# Changelog

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
