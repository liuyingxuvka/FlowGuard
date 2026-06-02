# API Surface Layers

FlowGuard has one core model and several optional helper layers. The layers are
named so AI coding agents can choose the smallest useful path without treating
every helper as a required gate.

The executable core is still:

```text
FunctionBlock: Input x State -> Set(Output x State)
Workflow = composed FunctionBlocks
Explorer = deterministic finite exploration
```

The minimum useful path remains:

```text
State + FunctionBlock + Invariant + Explorer
```

For AI agents, keep that as the default entry:

```text
risky boundary -> Input x State -> Set(Output x State)
-> one invariant or scenario -> run checks
-> inspect counterexample -> escalate only if a named risk requires it
```

The sections below are escalation layers. They help when the task has a named
UI, structure, testing, hierarchy, process, release, or evidence risk, but they
are not prerequisites for valid FlowGuard use.

## Core API

Core APIs are the stable objects needed to build and run a direct finite model:

- `FunctionBlock`, `FunctionResult`
- `Invariant`, `InvariantResult`
- `Workflow`, `WorkflowPath`, `WorkflowRun`
- `Explorer`, `ReachabilityCondition`, `enumerate_input_sequences`
- `CheckReport`, `InvariantViolation`, `DeadBranch`, `ExceptionBranch`,
  `ReachabilityFailure`
- `Trace`, `TraceStep`

These APIs should stay small and semantically stable. New helpers should not
change the meaning of `FunctionBlock`, `Workflow`, or `Explorer`, and obsolete
compatibility-only aliases should not remain in the first-read surface.
FlowGuard is latest-schema-first: old artifacts may be detected and upgraded at
project/tool boundaries, but normal route logic should consume current-schema
artifacts and current route-first APIs only.

`Explorer.explore()` emits minimal progress visibility by default: a start line
and bounded ten-step progress lines on `stderr`, counted by top-level
`initial_state x input_sequence` work units. This is observability only; it
does not change `CheckReport`, traces, pass/fail status, or stdout output. Use
`Explorer(..., progress_steps=0)` or `FLOWGUARD_PROGRESS=0` for silent runs.

## Route-Scoped Discovery First

For AI agents, route groups are the normal discovery surface:

- `FLOWGUARD_ROUTE_API` names the supported route groups.
- `PLAN_DETAILING_ROUTE_API` is the first stop for vague ideas, short plans,
  and AI-generated outlines that need explicit source, scope, state, side
  effect, step, receipt, validation, rework, human-question, and claim rows.
- `MODEL_SIMILARITY_ROUTE_API` is the first stop for similar A/B/C workflow
  maintenance, shared kernels, adapter variants, sibling tests, and false
  friends.
- `CODE_STRUCTURE_RECOMMENDATION_ROUTE_API`,
  `MODEL_TEST_ALIGNMENT_ROUTE_API`, and `ARCHITECTURE_REDUCTION_ROUTE_API`
  consume `SimilarityHandoff` when model similarity drives their work.
- `MAINTENANCE_SCAN_ROUTE_API` is the thin router for FlowGuard-managed
  project work that needs to surface model/code/test drift, stale evidence,
  skipped candidate routes, or split/reduction pressure before a broad claim.
- `MAINTENANCE_OBLIGATION_MEMORY_API` is the shared memory object used by
  summary reports, maintenance scan, model maturation, and risk ledger so
  unresolved route-owned gaps can be inherited without a separate debt scan.
- `STATE_CLOSURE_ROUTE_API` is the default runner gate for finite input/state
  enumerations that may have unknown, malformed, missing, or old-schema cases.
- `TOPOLOGY_HAZARD_ROUTE_API` is the default runner review for model-shape
  future-use hazards before broad done, release, publish, or full-confidence
  claims.

Use `MODELING_HELPER_API` only as the complete index after the route group is
known. It is intentionally broad and is not first-read guidance.

## Modeling Helpers

Modeling helpers reduce boilerplate around common bug classes. Prefer the
route-scoped groups above when choosing an AI workflow; this section is the full
inventory.

- property factories such as `no_duplicate_by`, `at_most_once_by`,
  `cache_matches_source`, `require_label_order`, and `forbid_label_after`;
- state write inventory guidance for fields named by invariants;
- public starter templates for basic models, Risk Intent check plans,
  model-miss reviews, closure-contract reviews, and recurring maintenance
  workflows;
- scenario review and `ScenarioMatrixBuilder`;
- deterministic counterexample minimization;
- optional domain packs such as `DeduplicationPack`, `CachePack`, `RetryPack`,
  and `SideEffectPack`;
- optional loop, progress, contract, conformance, and replay helpers.
- default state/input closure helpers such as `StateClosurePlan`,
  `StateClosureDimension`, `infer_state_closure_plan()`, and
  `review_state_closure()` for keeping unknown/other cases visible in
  `run_model_first_checks(...)` without changing direct `Explorer` semantics.
- default model topology hazard helpers such as `UsageIntent`,
  `TopologyDigest`, `TopologyHazardCandidate`,
  `infer_topology_digest()`, `infer_topology_hazard_plan()`, and
  `review_topology_hazards()` for grounding future-use risk review in concrete
  model topology anchors.
- optional budgeted model-group helpers such as `BudgetedGraphConfig` and
  `run_budgeted_graph_checks()` for large reachable graph models that need
  shard-by-shard execution with a durable ledger.
- optional hierarchical mesh helpers such as `HierarchyPartitionMap`,
  `ModelTargetSplitDerivation`, `ChildModelEvidence`,
  `ChildReattachmentContract`, `ChildBoundaryChangeSummary`,
  `MeshClosureModel`, `MeshClosureTransition`, `MeshClosureJoin`,
  `MeshClosureTerminal`, `review_mesh_closure_model()`,
  `summarize_child_boundary_change()`, `review_hierarchical_mesh()`,
  `LegacyModelRecord`, and `classify_legacy_model()` for reviewing
  model-derived target child layouts, parent/child partition coverage, repaired
  child reattachment, child boundary propagation, affected sibling review,
  whole-flow closure across model handoffs, bug-class responsibility
  separation, large-model split triggers, and legacy compatibility.
- optional automatic model/test split helpers such as `AutoSplitCandidate`,
  `AutoSplitPolicy`, `AutoSplitPlan`, `AutoSplitReport`, and
  `review_auto_mesh_splits()` for turning oversized, incomplete, slow, broad,
  progress-only, or release-only direct evidence into a required ModelMesh or
  TestMesh split gate before parent confidence is claimed.
- optional layered boundary proof helpers such as `ParentCoverageItem`,
  `ChildProofContract`, `ChildReattachmentProof`, `LeafBoundaryMatrix`,
  `LeafBoundaryMatrixCell`, `LayeredBoundaryProofPlan`, and
  `review_layered_boundary_proof()` for joining parent coverage, child
  disjointness, child reattachment, and leaf
  `Input x State -> Set(Output x State)` boundary-matrix evidence into one
  parent confidence gate.
- optional closure-contract helpers such as `FlowGuardClosureContractPlan`,
  `ClosureEvidenceReport`, `RuntimeTraceMapping`, `ArtifactInvalidation`,
  `ModelQualitySignal`, `SameClassMissClosure`,
  `RuntimeGatewayInventoryClosure`, and
  `review_flowguard_closure_contract()` for consuming current route evidence
  before broad done, release, publish, or production-confidence claims.
- optional architecture reduction helpers such as
  `ObservableArchitectureContract`, `CompatibilitySurfaceClassification`,
  `ArchitectureReductionCandidate`, `ArchitectureReductionTrigger`,
  `TargetArchitectureAction`,
  `ArchitectureReductionPlan`, `ArchitectureReductionReport`, and
  `review_architecture_reduction()` for reviewing whether an existing modeled
  implementation can be contracted without changing declared observable
  behavior, classifying compatibility surfaces such as old aliases, migration
  paths, public facades, retired rejection tests, and archive-only evidence,
  classifying merge/collapse/remove/keep-facade candidates, keeping completed
  or historical candidates out of the active ready queue, and handing target
  structure actions to Code Structure Recommendation or StructureMesh before
  production code is edited.
- optional model-similarity consolidation helpers such as
  `model_signature_minimal()`, `model_signature_maintenance()`,
  `model_similarity_plan_for_changed_member()`, `SimilarityHandoff`,
  `ModelSignature`,
  `ModelSimilarityEvidence`, `ModelSimilarityRelation`,
  `ModelSimilarityMaintenanceGroup`, `ModelSimilarityChangeImpact`,
  `ModelSimilarityTestObligation`, `ModelSimilarityCodeObligation`,
  `ModelSimilarityPlan`, `ModelSimilarityReport`, and
  `review_model_similarity_consolidation()` for comparing structured model
  signatures, classifying typed relations such as same workflow, family
  variant, shared kernel, duplicate boundary, adapter-only difference, evidence
  duplicate, false friend, and unrelated, deriving maintenance groups,
  changed-sibling review obligations, shared/variant test obligations, and
  shared-kernel/adapter/duplicate-boundary code obligations, and handing
  reviewable next-route advice through one typed handoff to Existing Model
  Preflight, ModelMesh,
  Architecture Reduction, Code Structure Recommendation, StructureMesh,
  Model-Test Alignment, or manual review without merging models or rewriting
  code automatically.
- optional model-test alignment helpers such as `ModelObligation`,
  `CodeContract`, `TestEvidence`, `ModelTestAlignmentPlan`, and
  `review_model_test_alignment()` for directly comparing model obligations
  with ordinary test evidence and optional code external contracts without
  invoking TestMesh or StructureMesh. `TestEvidence` can distinguish primary
  proof, primary `edge_path` proof, supporting contract evidence, integration
  smoke evidence, exact leaf matrix-cell evidence, and model-miss closure roles
  such as observed regression versus same-class generalized evidence.
- optional obligation-family parity helpers such as `ObligationFamily`,
  `ObligationFamilyMember`, `ObligationFamilyEvidence`,
  `FamilyBadCaseSeed`, `derive_same_class_bad_cases()`, and
  `review_obligation_family_parity()` for checking that related obligations
  have the same required mechanism coverage from allowed provenance sources
  before a family-level claim is promoted to full confidence. For bug-repair
  workflows, `AnalogousDefectCandidate` and
  `review_analogous_defect_scan()` record where the same failure shape might
  recur before broad closure is claimed.
- optional model maturation helpers such as `ModelMaturationSignal`,
  `ModelMaturationPlan`, `ModelMaturationReport`, and
  `review_model_maturation_loop()` for turning model-miss, model-test,
  ModelMesh, code-boundary, and freshness signals into explicit model-upgrade
  actions, scoped-claim decisions, and maintenance obligations before a broad
  FlowGuard claim is made.
- optional conservative Python source-audit helpers such as
  `PythonCodeContractEvidence`, `PythonTestAssertionEvidence`,
  `ContractSourceAuditReport`, `audit_python_code_contracts()`,
  `audit_python_test_assertions()`, and
  `review_python_contract_source_audit()` for feeding AST-visible code and test
  assertion evidence into Model-Test Alignment without presenting it as perfect
  semantic proof or a replacement for conformance replay.
- optional code-boundary conformance helpers such as
  `CodeBoundaryContract`, `CodeBoundaryObservation`,
  `CodeBoundaryConformanceReport`, and
  `review_code_boundary_conformance()` for checking whether real code
  observations stay inside a model-declared finite input/output boundary before
  alignment confidence is claimed.
- optional runtime gateway adoption helpers such as
  `RuntimeStateSurface`, `RuntimeGatewayContract`,
  `RuntimeWriteObservation`, `RuntimeGatewayAdoptionPlan`,
  `RuntimeGatewayAdoptionReport`, and
  `review_runtime_gateway_adoption()` for distinguishing design-only,
  test-aligned, and runtime-gateway FlowGuard adoption, and for blocking
  runtime protection claims when critical state writes can still bypass the
  declared gateway.
- optional runtime path evidence helpers such as `RuntimeNodeContract`,
  `RuntimeNodeObservation`, `RuntimePathRecorder`, and
  `review_runtime_path_alignment()` for comparing real code progress output to
  named FlowGuard model nodes. These helpers live in `MODELING_HELPER_API`, not
  `CORE_API`, and progress lines should include `model_id`, `model_path`, and
  `node_id`.
- optional TestMesh helpers such as `TestMeshPlan`, `TestPartitionItem`,
  `TestTargetSplitDerivation`, `TestSuiteEvidence`, and `review_test_mesh()`
  for reviewing model-derived target suite/script layouts, parent/child test
  hierarchy coverage, child suite/script ownership, evidence freshness,
  background completion, exact leaf matrix-cell evidence ownership, and
  routine-vs-release validation confidence.
- optional StructureMesh helpers such as `StructureMeshPlan`,
  `StructurePartitionItem`, `ModuleStructureEvidence`,
  `PublicEntrypointEvidence`, and `review_structure_mesh()` for reviewing large
  script or module splits, child ownership, public entrypoint compatibility,
  facades, dependency cycles, config drift, behavior parity, and
  routine-vs-release refactor confidence.
- optional Code Structure Recommendation helpers such as
  `CodeStructureRecommendation`, `TargetModuleRecommendation`, and
  `review_code_structure_recommendation()` for recommending implementation
  structure from a FlowGuard functional model before code is written.
- optional Existing Model Preflight helpers such as `ExistingModelPreflight`,
  `ModelContextHit`, `ExistingOwnershipSnapshot`, `DuplicateBoundaryRisk`, and
  `review_existing_model_preflight()` for grounding discussion, proposal, or
  implementation work in current FlowGuard model ownership before creating a
  new boundary. Full preflight records layered proof evidence id, parent
  coverage, child disjointness, child reattachment, leaf boundary-matrix
  status for parent models with child models, and optional model-similarity
  relation evidence when reuse, family variant, shared-kernel, or false-friend
  decisions depend on cross-model comparison.
- optional UI Flow Structure helpers such as `UIInteractionModel`,
  `UIControl`, `UIDisplayElement`, `UIStateNode`, `UITransition`,
  `UIJourneyCoverage`, `UIJourneyEntryPoint`, `UIFeatureJourney`,
  `UITerminalActionAllowance`, `UIResidualBlindspot`,
  `UIJourneyCoverageReport`, `UIFeatureContract`,
  `UIImplementationJourneyRun`, `UIImplementationStepEvidence`,
  `UIImplementationBlindspot`, `UIImplementationValidation`,
  `UIImplementationValidationReport`,
  `UIStructureDerivation`, `UIRegionRecommendation`,
  `UITextHierarchyBlueprint`, `UITextElement`, `UITypographyToken`,
  `review_ui_interaction_model()`, `review_ui_journey_coverage()`,
  `review_ui_implementation_validation()`,
  `review_ui_structure_derivation()`, and `review_ui_text_hierarchy()` for
  modeling UI interactions first, proving launch-to-terminal journey coverage
  and reachable visible-control/event coverage when complete app UI is claimed,
  validating implemented/runnable UI claims against feature contracts and real
  browser/manual click-through evidence, deriving parent/child UI topology, menu
  levels, stable placement, overlays, control hierarchy, information-display
  ownership, and then deriving semantic text hierarchy tokens before visual
  design or frontend implementation.
- optional DevelopmentProcessFlow helpers such as `ProcessArtifact`,
  `ProcessAction`, `ProcessEvidence`, `ValidationRequirement`,
  `DevelopmentProcessPlan`, `review_development_process_flow()`, and
  `derive_revalidation_plan()` for reviewing lifecycle ordering, artifact
  overwrite, evidence freshness, and minimum revalidation as a sibling route
  without supervising ModelMesh, TestMesh, StructureMesh, or Model-Test
  Alignment.

These helpers return or consume the same core model objects. They are useful
shortcuts, not a new modeling language and not mandatory for valid FlowGuard
use.

## Reporting Helpers

Reporting helpers help an AI agent explain what was checked and what was not:

- `AssumptionCard` and `ConditionalAssumption` for visible bounded assumptions
  with explicit preconditions, a `why_not_modeled` explanation, invalidation
  conditions, rationale, and checks
- `RiskIntent`, `RiskProfile`, and `FlowGuardCheckPlan`
- `RiskEvidenceRow`, `RiskEvidenceProof`, `RiskEvidenceLedgerPlan`,
  `RiskEvidenceLedgerReport`, and `review_risk_evidence_ledger()` for the final
  confidence ledger that connects user risks to FlowGuard model obligations,
  optional public code contracts, obligation-family gates, analogous defect
  scans, recurring defect-family gates, model/test split gates, remembered
  maintenance obligations, and current proof evidence
- `MaintenanceObligation`, `MaintenanceObligationReport`, and
  `build_maintenance_obligation_report()` for preserving unresolved
  route-owned gaps as future scan/ledger inputs without making them a separate
  skill route
- `ProofArtifactRef`, `proof_artifact_gap_codes()`, and proof-artifact status
  constants for binding declared evidence rows to concrete result paths,
  fingerprints, exit status, current route evidence, obligation coverage, and
  external-contract scope in strict confidence reviews
- `TestResultReuseTicket`, `coerce_test_result_reuse_ticket()`, and
  `test_result_reuse_gap_codes()` for proving that a previous test result can
  still count as current evidence when the command, test source, tested
  artifact, dependency, environment, result fingerprint, and coverage scope
  have not changed
- `DefectFamilyGate`, `DefectFamilyEvidence`, `DefectFamilyGatePlan`,
  `DefectFamilyGateReport`, and `review_defect_family_gates()` for promoting
  recurring or high-risk same-class model misses into a reusable FlowGuard gate
  before a broad final-confidence claim
- `LegacyPathDisposition` and `review_legacy_path_dispositions()` for blocking
  closure when an old route remains executable with an unknown, unproved, or
  out-of-scope-without-reason disposition
- plan-intake and typed claim helpers such as `PlanIntakeRiskSurface`,
  `PlanIntakeCompletenessPlan`, `review_plan_intake_completeness()`,
  `EvidenceAdapterMapping`, `review_evidence_adapter_conformance()`,
  `FalseNegativeCase`, `review_false_negative_backpropagation()`,
  `PlanMutationCase`, `review_plan_mutations()`,
  `FlowGuardClaimDependency`, and `review_flowguard_claim_chain()` for blocking
  under-declared plan inputs, lossy adapters, known false negatives,
  known-bad mutations, and unsupported promotion from narrow reports to broad
  confidence claims
- plan-detailing helpers such as `PlanDetail`, `PlanDetailStep`,
  `PlanDetailValidation`, `PlanDetailFailureBranch`,
  `review_plan_detail()`, `plan_detail_to_plan_intake()`,
  `plan_detail_to_step_contracts()`,
  `plan_detail_to_development_process()`, and
  `plan_detail_to_agent_workflow_plan()` for forcing rough plans into
  checkable rows before downstream routes review them
- model-impact freshness helpers such as `ModelFreshnessRecord`,
  `UpgradeImpact`, `ModelImpactAssessment`, `ModelReuseTicket`,
  `ModelRerunEvidence`, `ModelImpactFreshnessPlan`,
  `ModelImpactFreshnessReport`, and `review_model_impact_freshness()` for
  classifying existing models after a FlowGuard upgrade, accepting current
  reuse tickets for unchanged models, and requiring current rerun evidence for
  affected models before broad upgrade freshness is claimed
- `run_model_first_checks`
- `audit_model`
- `FlowGuardSummaryReport`
- `FlowGuardFindingLedger`, `build_finding_ledger`, and summary-derived
  `maintenance_obligations` for flattening all section findings and
  skipped/not-run gaps before deciding or inheriting a repair path
- adoption logging and `audit_flowguard_adoption`
- thin adoption logging commands such as `adoption-start` and
  `adoption-finish`
- artifact/project upgrade helpers such as `ArtifactUpgradeReport`,
  `review_artifact_upgrades()`, and `artifact-upgrade` for detecting old
  FlowGuard artifacts, applying deterministic current-schema upgrades, and
  reporting blocked/manual-review cases without adding runtime compatibility
  branches
- project adoption/version helpers such as `audit_project_adoption()`,
  `adopt_project()`, and `upgrade_project()` for writing the managed
  FlowGuard `AGENTS.md` block, `.flowguard/project.toml`, and adoption records
  in target repositories. Project upgrade scans older adopted repositories for
  deterministic artifact/model/test/guidance upgrades unless records-only mode
  is explicitly requested. These helpers record FlowGuard's GitHub repository
  and package/schema versions; they do not replace executable model checks.
- schema, JSON artifact helpers, and explicit Mermaid source exporters for
  user-facing model explanations when a compact diagram helps clarify major
  states, branches, gates, evidence, and claim boundaries

Warnings, gaps, skipped sections, and `not_run` sections are confidence
boundaries. They should not be hidden, but they also should not be treated as
hard failures unless the underlying section actually failed.
Mermaid diagrams are explanation aids; they do not change pass/fail semantics
or replace executable validation evidence.

## Evidence And Internal Validation

Evidence APIs are used to keep FlowGuard itself honest:

- evidence baseline reports;
- lightweight evidence gate/detail helpers such as `EvidenceGate`,
  `CommandEvidenceDetail`, `BackgroundEvidenceDetail`,
  `MeshSplitEvidenceDetail`, `summarize_evidence_gates()`, and
  `evidence_gates_from_process_like()` for grouping broad evidence fields
  without hiding skipped, stale, not-run, or progress-only states;
- benchmark scorecards and benchmark coverage audits;
- problem corpus and executable corpus reports;
- pytest/template helpers used by examples and framework validation;
- public template writers, including `model_test_alignment_template_files()`,
  `code_structure_recommendation_template_files()`,
  `existing_model_preflight_template_files()`,
  `model_similarity_consolidation_template_files()`,
  `plan_detailing_template_files()`,
  `risk_evidence_ledger_template_files()`,
  `development_process_flow_template_files()`,
  `maintenance_scan_template_files()`,
  `project_adoption_template_files()`, `test_mesh_template_files()`,
  `structure_mesh_template_files()`, `closure_contract_template_files()`, and
  `layered_boundary_proof_template_files()`, and
  `runtime_path_evidence_template_files()`. The public facade remains
  `flowguard.templates`; route template text is internally owned by
  route-scoped modules.

These tools are valuable for FlowGuard maintenance. Ordinary project models do
not have to run the full evidence baseline, problem corpus, or benchmark suite
before using `Explorer` or `run_model_first_checks`.

## Introspection Constants

The package exports lightweight grouping constants:

- route-scoped discovery groups such as `FLOWGUARD_ROUTE_API`,
  `TEMPLATE_STRUCTURE_API`, `EVIDENCE_FIELD_STRUCTURE_API`,
  `MODEL_SIMILARITY_ROUTE_API`, `ARCHITECTURE_REDUCTION_ROUTE_API`,
  `CODE_STRUCTURE_RECOMMENDATION_ROUTE_API`,
  `MODEL_TEST_ALIGNMENT_ROUTE_API`, `MAINTENANCE_OBLIGATION_MEMORY_API`,
  `MAINTENANCE_SCAN_ROUTE_API`, and `PLAN_DETAILING_ROUTE_API`
- `CORE_API`
- `REPORTING_HELPER_API`
- `EVIDENCE_API`
- `API_SURFACE`
- `MODELING_HELPER_API`, the complete helper index and fallback inventory

They are descriptive lists of exported public names. They do not enforce a
runtime policy and they do not make helper layers mandatory.

## Agent Guidance

Start with the core path when it is enough. Add helpers only when they clarify a
real risk, reduce repetitive code, or improve reporting honesty. Keep skipped
checks visible. In an existing modeled system, use Existing Model Preflight to
look up current model responsibilities, FunctionBlocks, state owners,
side-effect owners, and public entrypoints before proposing new ownership or a
parallel workflow. When model obligations and tests both exist, use Model-Test
Alignment to compare them directly before claiming coverage agreement; when
code contracts are supplied, also bind each model obligation to the external
code surface and require tests to prove that external contract rather than only
an internal path. When real Python source and tests are available, use
`audit_python_code_contracts()`, `audit_python_test_assertions()`, and
`review_python_contract_source_audit()` to check whether the declared code
contracts and test evidence are supported by AST-visible code and assertions
before trusting the three-way claim. When related obligations are being treated
as one family-level promise, add `ObligationFamily` and
`ObligationFamilyEvidence` rows so missing sibling mechanisms or wrong
provenance keep the alignment report scoped or blocked. When a post-green bug
shows a reusable failure shape, run `review_analogous_defect_scan()` and feed
that scan status into the final ledger before claiming full closure. When a code contract is supposed to be a
closed boundary, add `CodeBoundaryContract` and `CodeBoundaryObservation` rows
and run `review_code_boundary_conformance()` so forbidden inputs, unknown
accepted inputs, extra outputs, extra errors, extra state writes, and extra
side effects stay visible. When a project claims FlowGuard protects production
state mutation, add `RuntimeStateSurface`, `RuntimeGatewayContract`, and
`RuntimeWriteObservation` rows and run
`review_runtime_gateway_adoption()` so complete writer inventory, gateway
ownership, direct-write bypasses, stale observations, and proof-artifact gaps
stay visible. Send ambiguous or complex behavior to manual review and keep
conformance replay for production-facing confidence. When direct
model or validation evidence is oversized, incomplete, slow, broad,
progress-only, or release-only, run `review_auto_mesh_splits()` and route the
result to ModelMesh or TestMesh before claiming broad parent confidence. For
large model or validation meshes, record the target split derivation from the
FlowGuard source model before trusting parent/child ownership and evidence.
After non-trivial FlowGuard-managed work, run or construct a maintenance scan
with `review_maintenance_scan()` when changed artifacts, remembered maintenance
obligations, skipped routes, stale evidence, or structure/reduction signals may
require another owner route.
When parent confidence claims whole-flow closure, add a
mesh closure model so root entries, child outputs, joins, terminal
dispositions, and out-of-scope branches are checked as executable handoff
obligations before `mesh_green_can_continue`. When a parent model relies on
child models for confidence, add layered boundary proof so each parent item has
an owner, child ownership is disjoint except for explicit bridge/shared-kernel
cases, current child evidence is reattached to the parent, and each leaf proves
its finite real-code boundary matrix. For large, slow, or layered validation, use TestMesh to
split the parent test gate into child suites/scripts and make their ownership
and evidence visible before trusting the parent. For large structure refactors,
use StructureMesh to make model-derived target structure, child-module
ownership, and compatibility evidence visible before trusting a parent split.
Before turning all of those route reports into a broad done, release, publish,
or production-confidence claim, run `review_flowguard_closure_contract()` so
runtime trace mapping, artifact freshness, model quality, same-class miss
closure, runtime gateway inventory, and Risk Evidence Ledger support are all
current at the claim boundary.
When the incoming work is still a vague idea or thin plan, run
`review_plan_detail()` first and project the resulting rows into PlanIntake,
WorkflowStepContracts, DevelopmentProcessFlow, or AgentWorkflowRehearsal as
needed; do not treat the plan-detail pass as implementation proof.
Use Code Structure Recommendation for direct pre-code architecture
recommendations. Use Architecture Reduction when an existing implementation has
repeated handlers, adapters, modules, branches, or validation layers and the
goal is behavior-preserving code contraction; it should produce a review and
handoff, not rewrite production code. Use UI Flow Structure when a UI's controls, state transitions,
navigation, regions, overlays, menu levels, information displays,
duplicate/redundant content, overlapping controls, or parent/child hierarchy
need a reviewed UI interaction model before layout and visual implementation;
when the claim is complete app-level UI coverage, require UI journey coverage
from launch entry points through declared success, recovery, cancel, exit, and
residual blindspot boundaries before structure or visual handoff. When the
claim is implemented/runnable UI completion, require implementation validation
that aligns feature contracts, reviewed journeys, real click-through evidence,
model revision, and residual implementation blindspots. Use
DevelopmentProcessFlow when staged development or modification work has
validation, or when lifecycle ordering, artifact overwrite, verifier changes,
peer writes, or evidence freshness determine whether the agent can safely
continue or whether a done, release, archive, or publish claim is supported; do
not use it as a universal gate or a supervisor for sibling routes. Before a
final confidence claim, use the Risk Evidence Ledger to check whether each
important user risk has a model obligation, code contract when required, and
current external proof evidence; stale, skipped, progress-only, or
internal-path-only proof can support only a scoped or blocked claim. Do not
claim production confidence from a model-only pass unless conformance replay or
equivalent real-code evidence exists.
When repeated issues or broad completion claims depend on upstream plan
construction, first run the plan-intake, adapter-conformance,
false-negative-backpropagation, mutation, and typed claim-chain helpers so
omitted surfaces or narrow reports cannot be silently upgraded.
