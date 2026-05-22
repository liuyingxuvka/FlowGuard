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

## Core API

Core APIs are the stable objects needed to build and run a direct finite model:

- `FunctionBlock`, `FunctionResult`
- `Invariant`, `InvariantResult`
- `Workflow`, `WorkflowPath`, `WorkflowRun`
- `Explorer`, `ReachabilityCondition`, `enumerate_input_sequences`
- `CheckReport`, `InvariantViolation`, `DeadBranch`, `ExceptionBranch`,
  `ReachabilityFailure`
- `Trace`, `TraceStep`

These APIs should stay small and backward compatible. New helpers should not
change the meaning of `FunctionBlock`, `Workflow`, or `Explorer`.

`Explorer.explore()` emits minimal progress visibility by default: a start line
and bounded ten-step progress lines on `stderr`, counted by top-level
`initial_state x input_sequence` work units. This is observability only; it
does not change `CheckReport`, traces, pass/fail status, or stdout output. Use
`Explorer(..., progress_steps=0)` or `FLOWGUARD_PROGRESS=0` for silent runs.

## Modeling Helpers

Modeling helpers reduce boilerplate around common bug classes:

- property factories such as `no_duplicate_by`, `at_most_once_by`,
  `cache_matches_source`, `require_label_order`, and `forbid_label_after`;
- state write inventory guidance for fields named by invariants;
- public starter templates for basic models, Risk Intent check plans,
  model-miss reviews, and recurring maintenance workflows;
- scenario review and `ScenarioMatrixBuilder`;
- deterministic counterexample minimization;
- optional domain packs such as `DeduplicationPack`, `CachePack`, `RetryPack`,
  and `SideEffectPack`;
- optional loop, progress, contract, conformance, and replay helpers.
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
- optional layered boundary proof helpers such as `ParentCoverageItem`,
  `ChildProofContract`, `ChildReattachmentProof`, `LeafBoundaryMatrix`,
  `LeafBoundaryMatrixCell`, `LayeredBoundaryProofPlan`, and
  `review_layered_boundary_proof()` for joining parent coverage, child
  disjointness, child reattachment, and leaf
  `Input x State -> Set(Output x State)` boundary-matrix evidence into one
  parent confidence gate.
- optional architecture reduction helpers such as
  `ObservableArchitectureContract`, `ArchitectureReductionCandidate`,
  `ArchitectureReductionTrigger`, `TargetArchitectureAction`,
  `ArchitectureReductionPlan`, `ArchitectureReductionReport`, and
  `review_architecture_reduction()` for reviewing whether an existing modeled
  implementation can be contracted without changing declared observable
  behavior, classifying merge/collapse/remove/keep-facade candidates, and
  handing target structure actions to Code Structure Recommendation or
  StructureMesh before production code is edited.
- optional model-test alignment helpers such as `ModelObligation`,
  `CodeContract`, `TestEvidence`, `ModelTestAlignmentPlan`, and
  `review_model_test_alignment()` for directly comparing model obligations
  with ordinary test evidence and optional code external contracts without
  invoking TestMesh or StructureMesh.
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
- optional TestMesh helpers such as `TestMeshPlan`, `TestPartitionItem`,
  `TestTargetSplitDerivation`, `TestSuiteEvidence`, and `review_test_mesh()`
  for reviewing model-derived target suite/script layouts, parent/child test
  hierarchy coverage, child suite/script ownership, evidence freshness,
  background completion, and routine-vs-release validation confidence.
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
  new boundary.
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
  optional public code contracts, and current proof evidence
- `run_model_first_checks`
- `audit_model`
- `FlowGuardSummaryReport`
- `FlowGuardFindingLedger` and `build_finding_ledger` for flattening all
  section findings and skipped/not-run gaps before deciding a repair path
- adoption logging and `audit_flowguard_adoption`
- thin adoption logging commands such as `adoption-start` and
  `adoption-finish`
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
- benchmark scorecards and benchmark coverage audits;
- problem corpus and executable corpus reports;
- pytest/template helpers used by examples and framework validation;
- public template writers, including `model_test_alignment_template_files()`,
  `code_structure_recommendation_template_files()`,
  `existing_model_preflight_template_files()`,
  `risk_evidence_ledger_template_files()`,
  `development_process_flow_template_files()`, `test_mesh_template_files()`,
  `structure_mesh_template_files()`, and
  `layered_boundary_proof_template_files()`.

These tools are valuable for FlowGuard maintenance. Ordinary project models do
not have to run the full evidence baseline, problem corpus, or benchmark suite
before using `Explorer` or `run_model_first_checks`.

## Introspection Constants

The package exports lightweight grouping constants:

- `CORE_API`
- `MODELING_HELPER_API`
- `REPORTING_HELPER_API`
- `EVIDENCE_API`
- `API_SURFACE`

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
before trusting the three-way claim. When a code contract is supposed to be a
closed boundary, add `CodeBoundaryContract` and `CodeBoundaryObservation` rows
and run `review_code_boundary_conformance()` so forbidden inputs, unknown
accepted inputs, extra outputs, extra errors, extra state writes, and extra
side effects stay visible. Send ambiguous or complex behavior to manual review
and keep conformance replay for production-facing confidence. For large model or
validation meshes, record the target split
derivation from the FlowGuard source model before trusting parent/child
ownership and evidence. When parent confidence claims whole-flow closure, add a
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
