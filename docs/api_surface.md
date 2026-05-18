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
  `review_hierarchical_mesh()`, `LegacyModelRecord`, and
  `classify_legacy_model()` for reviewing model-derived target child layouts,
  parent/child partition coverage, sibling overlap, large-model split triggers,
  and legacy compatibility.
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
- optional UI Flow Structure helpers such as `UIInteractionModel`,
  `UIControl`, `UIDisplayElement`, `UIStateNode`, `UITransition`,
  `UIStructureDerivation`, `UIRegionRecommendation`,
  `UITextHierarchyBlueprint`, `UITextElement`, `UITypographyToken`,
  `review_ui_interaction_model()`, and
  `review_ui_structure_derivation()`, and `review_ui_text_hierarchy()` for
  modeling UI interactions first, deriving parent/child UI topology, menu
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
- `run_model_first_checks`
- `audit_model`
- `FlowGuardSummaryReport`
- `FlowGuardFindingLedger` and `build_finding_ledger` for flattening all
  section findings and skipped/not-run gaps before deciding a repair path
- adoption logging and `audit_flowguard_adoption`
- thin adoption logging commands such as `adoption-start` and
  `adoption-finish`
- schema, JSON artifact helpers, and explicit Mermaid source exporters

Warnings, gaps, skipped sections, and `not_run` sections are confidence
boundaries. They should not be hidden, but they also should not be treated as
hard failures unless the underlying section actually failed.

## Evidence And Internal Validation

Evidence APIs are used to keep FlowGuard itself honest:

- evidence baseline reports;
- benchmark scorecards and benchmark coverage audits;
- problem corpus and executable corpus reports;
- pytest/template helpers used by examples and framework validation;
- public template writers, including `model_test_alignment_template_files()`,
  `code_structure_recommendation_template_files()`,
  `development_process_flow_template_files()`, `test_mesh_template_files()`,
  and `structure_mesh_template_files()`.

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
checks visible. When model obligations and tests both exist, use Model-Test
Alignment to compare them directly before claiming coverage agreement; when
code contracts are supplied, also bind each model obligation to the external
code surface and require tests to prove that external contract rather than only
an internal path. When real Python source and tests are available, use
`audit_python_code_contracts()`, `audit_python_test_assertions()`, and
`review_python_contract_source_audit()` to check whether the declared code
contracts and test evidence are supported by AST-visible code and assertions
before trusting the three-way claim; send ambiguous or complex behavior to
manual review and keep conformance replay for production-facing confidence. For large model or
validation meshes, record the target split
derivation from the FlowGuard source model before trusting parent/child
ownership and evidence. For large, slow, or layered validation, use TestMesh to
split the parent test gate into child suites/scripts and make their ownership
and evidence visible before trusting the parent. For large structure refactors,
use StructureMesh to make model-derived target structure, child-module
ownership, and compatibility evidence visible before trusting a parent split.
Use Code Structure Recommendation for direct pre-code architecture
recommendations. Use UI Flow Structure when a UI's controls, state transitions,
navigation, regions, overlays, menu levels, information displays,
duplicate/redundant content, overlapping controls, or parent/child hierarchy
need a reviewed UI interaction model before layout and visual implementation. Use
DevelopmentProcessFlow when development lifecycle
ordering, artifact overwrite, verifier changes, peer writes, or evidence
freshness determine whether a done, release, archive, or publish claim is
supported; do not use it as a universal gate or a supervisor for sibling
routes. Do not claim production confidence from a model-only pass unless
conformance replay or equivalent real-code evidence exists.
