# API Surface Layers

FlowGuard has one core model and route-specific helper layers. The layers are
named so AI coding agents can start from one formal path and then open only the
route helpers that own the current risk.

The executable core is still:

```text
FunctionBlock: Input x State -> Set(Output x State)
Workflow = composed FunctionBlocks
formal runner = deterministic finite model checks plus evidence gates
```

The formal minimum useful entry for new or deepened models is:

```text
risky boundary -> RiskIntent -> template search/no-match
-> Input x State -> Set(Output x State)
-> MinimumModelContract + KnownBadProof
-> FlowGuardCheckPlan -> run_model_first_checks
-> inspect counterexample/gaps -> close template harvest
```

The deterministic finite exploration engine remains an internal execution
primitive. It is no longer the agent-default public entry for non-trivial model
creation. The sections below are route layers for UI, structure, testing,
hierarchy, process, release, or evidence risk.

## Agent-Default API

`AGENT_DEFAULT_API` is the smallest public first-read surface for AI agents.
It keeps the normal path short:

- formal model-first entry: `RiskIntent`, `RiskProfile`,
  `FlowGuardCheckPlan`, `MinimumModelContract`, `KnownBadProof`,
  `TemplateReuseReview`, `TemplateHarvestReview`, and
  `run_model_first_checks`;
- core modeling primitives: `Workflow`, `Invariant`, and `FunctionResult`;
- route selection: `FLOWGUARD_ROUTE_API`,
  `default_flowguard_route_profiles()`;
- FlowGuard self-maintenance:
  `default_flowguard_self_maintenance_plan()`,
  `review_flowguard_self_maintenance()`;
- project and release gates: `audit_project_adoption()`,
  `review_development_process_simulator()`,
  `review_development_process_flow()`, `review_maintenance_scan()`;
- escalation checks: `review_model_test_alignment()`,
  `review_field_lifecycle()`, and `review_topology_hazards()`.

Use this group before expanding to `FLOWGUARD_ROUTE_API` or the complete
`MODELING_HELPER_API` inventory.

## Route Starter API

`ROUTE_STARTER_API` is the default second step after `AGENT_DEFAULT_API`.
It maps route ids to compact helper names, usually one plan/report shape, one
review function, and one template factory. These are the names an AI agent
should read before opening a full route group.

Use the layers in this order:

```text
AGENT_DEFAULT_API
-> ROUTE_STARTER_API[route_id]
-> ROUTE_ADVANCED_API[route_id]
-> MODELING_HELPER_API / REPORTING_HELPER_API as full indexes only
```

`ROUTE_ADVANCED_API` keeps the full route groups available for deep work.
`PLAN_INTAKE_STARTER_API` is the compact first-read slice for plan-intake claim
review; `PLAN_INTAKE_ADVANCED_API` remains the complete plan-intake inventory.

Template defaults follow the same rule. `model-miss-template`,
`model-test-alignment-template`, and `ui-flow-structure-template` emit compact
runnable scaffolds. Use `model-miss-full-template`,
`model-test-alignment-full-template`, or `ui-flow-structure-full-template` only
when the route needs the deep example.

## Core API

Core APIs are the stable objects used by the formal runner and advanced custom
checks:

- `FunctionBlock`, `FunctionResult`
- `Invariant`, `InvariantResult`
- `Workflow`, `WorkflowPath`, `WorkflowRun`
- `ReachabilityCondition`, `enumerate_input_sequences`
- `CheckReport`, `InvariantViolation`, `DeadBranch`, `ExceptionBranch`,
  `ReachabilityFailure`
- `Trace`, `TraceStep`

These APIs should stay small and semantically stable. New helpers should not
change the meaning of `FunctionBlock` or `Workflow`, and obsolete
compatibility-only aliases should not remain in the first-read surface.
FlowGuard is latest-schema-first: old artifacts may be detected and upgraded at
project/tool boundaries, but normal route logic should consume current-schema
artifacts and current route-first APIs only.

Formal runs emit minimal progress visibility by default through the internal
finite runner: a start line and bounded progress lines on `stderr`, counted by
top-level `initial_state x input_sequence` work units. This is observability
only; it does not change reports, traces, pass/fail status, or stdout output.
Use `FLOWGUARD_PROGRESS=0` for silent formal runs.

## Route-Scoped Discovery First

For AI agents, route groups are the normal discovery surface:

- `FLOWGUARD_ROUTE_API` names the supported route groups.
- `default_flowguard_route_profiles()` is the compact first-read map for AI
  maintenance: each `RouteProfile` names the trigger, minimal inputs, outputs,
  evidence owner, API group, template, skill, and next actions. Use
  `review_flowguard_self_maintenance()` to check that profile ids stay aligned
  with public route groups.
- `default_ai_maintenance_profiles()` gives thin entry profiles for common
  FlowGuard self-maintenance work such as fields, route graph connection,
  structure, and validation. They are entry profiles only; route-owned evidence
  still expands in the specialist route.
- `PLAN_DETAILING_ROUTE_API` is the first stop for vague ideas, short plans,
  and AI-generated outlines that need explicit source, scope, state, side
  effect, step, receipt, validation, rework, human-question, and claim rows.
- `MODEL_SIMILARITY_ROUTE_API` is the first stop for similar A/B/C workflow
  maintenance, shared kernels, adapter variants, sibling tests, duplicate
  business paths, path-terminal divergence, and false friends.
- `CODE_STRUCTURE_RECOMMENDATION_ROUTE_API`,
  `MODEL_TEST_ALIGNMENT_ROUTE_API`, and `ARCHITECTURE_REDUCTION_ROUTE_API`
  consume `SimilarityHandoff` when model similarity drives their work.
  `MODEL_TEST_ALIGNMENT_ROUTE_API` also exposes transition coverage matrix
  helpers for turning modeled transitions into direct test-evidence
  obligations. Python source-audit execution lives in
  `flowguard.model_test_alignment_source`, while the original
  `flowguard.model_test_alignment` and top-level `flowguard` imports remain
  compatibility facades.
- `MAINTENANCE_SCAN_ROUTE_API` is the thin router for FlowGuard-managed
  project work that needs to surface model/code/test drift, stale evidence,
  skipped candidate routes, duplicate/conflicting/unproven business paths, old
  business-path disposition gaps, or split/reduction pressure before a broad
  claim.
  `maintenance_scan_plan_from_summary_report(...)` bridges structured
  SummaryReport gaps into that same router without making the runner a new
  workflow engine.
- `MAINTENANCE_OBLIGATION_MEMORY_API` is the shared memory object used by
  summary reports, maintenance scan, model maturation, and risk ledger so
  unresolved route-owned gaps can be inherited without a separate debt scan.
- `MODEL_ANGLE_DELIBERATION_API` is the open-ended pre-route review for asking
  what model angle the current boundary may miss before an agent trusts a
  fixed route. It records the candidate angle, what the current model sees and
  misses, the failure if ignored, and whether to reuse, extend, split, create,
  scope, defer, or ask for human review.
- `RISK_TEMPLATE_LIBRARY_API` is the public/local reusable risk-template route
  for searching packaged templates, using a portable per-machine local library,
  reviewing template reuse, harvesting local candidate templates from minimum
  valuable models, and closing template harvest before complete model claims.
- `FIELD_LIFECYCLE_MESH_API` is the field-governance layer for changes where
  fields carry behavior, routing, permissions, schema, replay, migration, or
  external-contract meaning. High-level models project important fields into
  obligations and code contracts; leaf field groups account for every
  discovered field, including display-only fields with scoped-out reasons and
  old/replaced/deprecated fields with closing disposition evidence.
- `STATE_CLOSURE_ROUTE_API` is the default runner gate for finite input/state
  enumerations that may have unknown, malformed, missing, or old-schema cases.
- `TOPOLOGY_HAZARD_ROUTE_API` is the default runner review for model-shape
  future-use hazards before broad done, release, publish, or full-confidence
  claims. It includes `BusinessPathIdentity` so important routes can name the
  useful business path they prove, not only the local model node that ran.
- `FLOWGUARD_SELF_MAINTENANCE_ROUTE_API` is the parent route for FlowGuard's
  own maintenance chain: route graph completeness, AI entry profiles, field
  layers, child route reports, install/shadow sync, and closure boundaries.

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
  risk-template library use, model-miss reviews, closure-contract reviews, and
  recurring maintenance workflows;
- risk template helpers such as `search_risk_templates()`,
  `review_minimum_model_contract()`, `harvest_risk_template_candidate()`,
  `TemplateHarvestReview`, and `review_template_harvest_closure()`;
- scenario review and `ScenarioMatrixBuilder`;
- deterministic counterexample minimization;
- optional domain packs such as `DeduplicationPack`, `CachePack`, `RetryPack`,
  and `SideEffectPack`;
- optional loop, progress, contract, conformance, and replay helpers.
- default state/input closure helpers such as `StateClosurePlan`,
  `StateClosureDimension`, `infer_state_closure_plan()`, and
  `review_state_closure()` for keeping unknown/other cases visible in
  `run_model_first_checks(...)` without changing formal model semantics.
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
- model-test alignment helpers such as `ModelObligation`,
  `CodeContract`, `TestEvidence`, `ModelTestAlignmentPlan`, and
  `review_model_test_alignment()` for directly comparing model obligations
  with owner code external contracts and ordinary test evidence without
  invoking TestMesh or StructureMesh. `ModelCodeTestBindingRow` exposes the
  required three-way row status. `TestEvidence` can distinguish primary
  proof, primary `edge_path` proof, supporting contract evidence, integration
  smoke evidence, exact leaf matrix-cell evidence, transition-cell evidence,
  and model-miss closure roles such as observed regression versus same-class
  generalized evidence. `TransitionCoverageCell`,
  `TransitionCoverageMatrix`, `transition_coverage_to_model_obligations()`,
  `transition_coverage_to_code_contracts()`,
  `transition_coverage_to_required_leaf_cell_ids()`,
  `transition_obligation_id()`, and
  `ui_interaction_model_to_transition_coverage()` provide the standard bridge
  from modeled transitions into those alignment and TestMesh evidence targets.
  `model_mesh_closure_to_transition_coverage()` does the same for ModelMesh
  closure transitions, with `MODEL_MESH_CLOSURE_RETRY_TEST_KINDS` enforcing
  retry/rejection evidence breadth for repeated-input handoffs.
  Field lifecycle reports and projections can be supplied directly to
  `ModelTestAlignmentPlan`, where behavior-bearing fields become model
  obligations and code contracts that still require current test evidence.
  `ArtifactPayloadContract`, `ArtifactPayloadCase`,
  `ArtifactPayloadEvidence`, and `review_artifact_payload_validation()` add the
  same evidence gate for import/export files, generated artifacts, saved/load
  payloads, and AI work packages: current external case evidence must prove
  that synthetic payload cases exercised the real payload surface, with an
  evidence reference or proof artifact for expected status, output, error path,
  state writes, side effects, and round-trip behavior before broad payload
  claims are green.
- field lifecycle helpers such as `FieldLifecyclePlan`,
  `FieldLifecycleGroup`, `FieldLifecycleRow`, `FieldProjection`,
  `FieldLifecycleReport`, `review_field_lifecycle()`,
  `field_lifecycle_to_model_obligations()`, and
  `field_lifecycle_to_code_contracts()` for keeping field ownership,
  reader/writer maps, lifecycle state, behavior projection, scoped-out
  reasons, old-field disposition, and broad-claim gate/test/replay route refs
  visible before code or done claims.
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
- optional model-angle deliberation helpers such as
  `ModelAngleDeliberation`, `ModelAngleReviewReport`, and
  `review_model_angle_deliberations()` for preserving open-ended AI reasoning
  before one route is trusted. Rows are not limited to known FlowGuard routes:
  they may name any meaningful missing angle, then hand that angle to the
  owner route that can produce evidence. Existing Model Preflight, Maintenance
  Scan, Risk Evidence Ledger, and Closure Contract can consume unresolved
  model-angle gaps before broad confidence.
- optional FlowGuard self-maintenance helpers such as `RouteProfile`,
  `AIMaintenanceProfile`, `FieldLayerProfile`,
  `SelfMaintenanceChildReport`, `SelfMaintenancePlan`,
  `default_flowguard_self_maintenance_plan()`,
  `default_flowguard_route_profiles()`,
  `default_ai_maintenance_profiles()`, `default_field_layer_profiles()`,
  `route_graph_completeness_findings()`, and
  `review_flowguard_self_maintenance()` for keeping FlowGuard's own AI-facing
  maintenance path route-first. These helpers make fields and evidence lighter
  at first read, but they do not delete behavior-bearing fields or replace
  Model-Test Alignment, StructureMesh, TestMesh, DevelopmentProcessFlow, Risk
  Evidence Ledger, or Closure Contract.
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
  structure from a FlowGuard functional model before code is written. The
  recommendation surface includes field owner, reader, and writer maps so
  fields do not disappear during module splitting or function movement.
- optional Existing Model Preflight helpers such as `ExistingModelPreflight`,
  `ModelContextHit`, `ExistingOwnershipSnapshot`, `DuplicateBoundaryRisk`, and
  `review_existing_model_preflight()` for grounding discussion, proposal, or
  implementation work in current FlowGuard model ownership before creating a
  new boundary. Full preflight records layered proof evidence id, parent
  coverage, child disjointness, child reattachment, leaf boundary-matrix
  status for parent models with child models, and optional model-similarity
  relation evidence when reuse, family variant, shared-kernel, or false-friend
  decisions depend on cross-model comparison. For field-bearing changes it
  also records behavior field ids, field owners, existing field lifecycle
  model ids, and unresolved field lifecycle gaps before downstream work starts.
- optional UI Flow Structure helpers such as `UIInteractionModel`,
  `UIControl`, `UIDisplayElement`, `UIStateNode`, `UITransition`,
  `UIObservedSurfaceItem`, `UIObservedSurfaceInventory`,
  `UIControlFunctionalChain`, `UIControlFunctionalChainSet`,
  `UIWorkModeDeclaration`, `UISourceBaseline`, `UISourceBaselineItem`,
  `UISourceTargetMapping`, `UISourceTargetMappingRow`,
  `UIObservedSourceAlignment`, `UISourceInteractionSemantics`,
  `UISourceBaselineInteractionGate`,
  `UIFunctionalCapability`, `UIFunctionalCapabilityInventory`,
  `UICapabilityOutputContract`, `UICapabilityCoverageBinding`,
  `UIFunctionalCapabilityCoverageReport`,
  `UIJourneyCoverage`, `UIJourneyEntryPoint`, `UIFeatureJourney`,
  `UITerminalActionAllowance`, `UIBlindspot`,
  `UIJourneyCoverageReport`, `UIFeatureContract`,
  `UIImplementationJourneyRun`, `UIImplementationStepEvidence`,
  `UIImplementationValidation`,
  `UIImplementationValidationReport`,
  `UIUserTaskFrame`, `UIUserTaskCoverageLedger`,
  `UIRegionSemanticMap`, `UIAffordanceContract`, `UIActionGrammar`,
  `UIDialogWindowContract`, `UIKeyboardFocusContract`,
  `UIHumanWalkthroughStep`, `UIHumanWalkthroughScenario`,
  `UIHumanOperabilityAssessment`, `UIHumanOperabilityReport`,
  `UIVisibleSurface`, `UIVisibleSurfaceItem`, `UIVisibleSurfaceReport`,
  `UIRenderEvidence`, `UIRenderEvidenceSet`, `UIRenderEvidenceReport`,
  `UIGeometryLayoutEvidence`, `UIGeometryLayoutEvidenceSet`,
  `UIGeometryLayoutEvidenceReport`, `UIHotPathAction`, `UIColdPathWork`,
  `UIStableRegionRule`, `UIResponsivenessContract`,
  `UIResponsivenessContractReport`,
  `UIStructureDerivation`, `UIRegionRecommendation`,
  `UITextHierarchyBlueprint`, `UITextElement`, `UITypographyToken`,
  `review_ui_observed_surface_inventory()`,
  `review_ui_control_functional_chains()`,
  `review_ui_source_baseline_alignment()`,
  `review_ui_source_baseline_interactions()`,
  `review_ui_functional_capability_coverage()`,
  `review_ui_interaction_model()`, `review_ui_journey_coverage()`,
  `review_ui_human_operability()`,
  `review_ui_implementation_validation()`,
  `review_ui_visible_surface()`, `review_ui_render_evidence()`,
  `review_ui_geometry_layout_evidence()`,
  `review_ui_responsiveness_contract()`,
  `review_ui_structure_derivation()`, and `review_ui_text_hierarchy()` for
  inventorying the real visible UI first, modeling UI interactions, proving
  enabled-control functional chains, aligning source-baseline interactions when
  work is source-based or mixed,
  accounting required user-visible capabilities and result/output contracts
  before broad UI completion claims,
  proving launch-to-terminal journey coverage and reachable visible-control/event coverage when complete app UI is claimed,
  validating task coverage, region semantics, affordance, action grammar,
  native/dialog returns, keyboard/focus, and human walkthroughs before
  human-operable UI confidence is claimed,
  reviewing visible controls/helper/status/placeholder/metadata surface,
  validating implemented/runnable UI claims against feature contracts and real
  screenshot/browser/manual/DOM/geometry/accessibility/runtime/test evidence,
  checking universal geometry and responsiveness contracts, deriving
  parent/child UI topology, menu levels, stable placement, overlays, control
  hierarchy, information-display ownership, and then deriving semantic text
  hierarchy tokens with calm visual handoff guidance before visual design or
  frontend implementation.
- development-process simulator helpers such as
  `DevelopmentProcessSimulationRequest`,
  `DevelopmentProcessSimulatorReport`,
  `review_development_process_simulator()`, `ProcessArtifact`,
  `ProcessAction`, `ProcessEvidence`, `ValidationRequirement`,
  `DevelopmentProcessPlan`, `review_development_process_flow()`, and
  `derive_revalidation_plan()` for selecting `plan_detailing`,
  `agent_workflow`, and `execution_freshness` modes, then reviewing lifecycle
  ordering, artifact overwrite, evidence freshness, and minimum revalidation
  without supervising ModelMesh, TestMesh, StructureMesh, or Model-Test
  Alignment. Field lifecycle artifacts, field projections, replacement
  disposition records, and bug-repair closure records have route-specific
  freshness codes so later writes cannot reuse stale field evidence.

These helpers return or consume the same core model objects. They are route
layers, not a new modeling language. For non-trivial model creation, the
formal `FlowGuardCheckPlan` path remains the required public entry.

## Reporting Helpers

Reporting helpers help an AI agent explain what was checked and what was not:

- `AssumptionCard` and `ConditionalAssumption` for visible bounded assumptions
  with explicit preconditions, a `why_not_modeled` explanation, invalidation
  conditions, rationale, and checks
- `RiskIntent`, `RiskProfile`, `FlowGuardCheckPlan`,
  `MinimumModelContract`, `KnownBadProof`, `TemplateReuseReview`,
  `TemplateHarvestReview`, and `review_known_bad_proofs`
- `RiskEvidenceRow`, `RiskEvidenceProof`, `RiskEvidenceLedgerPlan`,
  `RiskEvidenceLedgerReport`, and `review_risk_evidence_ledger()` for the final
  confidence ledger that connects user risks to FlowGuard model obligations,
  optional public code contracts, obligation-family gates, analogous defect
  scans, recurring defect-family gates, model/test split gates, UI
  implementation, real-surface, functional-chain, source-baseline interaction, and
  done-claim gates, artifact-payload gates, model-angle deliberation
  evidence, remembered maintenance obligations, and current proof evidence
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
  `plan_detail_to_agent_workflow_plan()` for delegated `plan_detailing` mode
  row construction after the development-process simulator decides rough plans
  need checkable rows
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
- lightweight evidence gates such as `EvidenceGate`,
  `summarize_evidence_gates()`, and `evidence_gates_from_process_like()` for
  grouping broad evidence fields without hiding skipped, stale, not-run, or
  progress-only states;
- benchmark scorecards and benchmark coverage audits;
- problem corpus and executable corpus reports;
- pytest/template helpers used by examples and framework validation;
- public template writers, including `model_test_alignment_template_files()`,
  `model_test_alignment_full_template_files()`,
  `code_structure_recommendation_template_files()`,
  `existing_model_preflight_template_files()`,
  `model_angle_deliberation_template_files()`,
  `field_lifecycle_template_files()`,
  `model_similarity_consolidation_template_files()`,
  `plan_detailing_template_files()`,
  `risk_evidence_ledger_template_files()`,
  `development_process_flow_template_files()`,
  `maintenance_scan_template_files()`,
  `project_adoption_template_files()`, `model_miss_review_full_template_files()`,
  `ui_flow_structure_full_template_files()`, `test_mesh_template_files()`,
  `structure_mesh_template_files()`, `closure_contract_template_files()`, and
  `layered_boundary_proof_template_files()`, and
  `runtime_path_evidence_template_files()`. The public facade remains
  `flowguard.templates`; route template text is internally owned by
  route-scoped modules.

These tools are valuable for FlowGuard maintenance. Ordinary project models do
not have to run the full evidence baseline, problem corpus, or benchmark suite
before using `run_model_first_checks`.

## Introspection Constants

The package exports lightweight grouping constants:

- route-scoped discovery groups such as `FLOWGUARD_ROUTE_API`,
  `TEMPLATE_STRUCTURE_API`, `EVIDENCE_FIELD_STRUCTURE_API`,
  `FLOWGUARD_SELF_MAINTENANCE_ROUTE_API`,
  `MODEL_SIMILARITY_ROUTE_API`, `ARCHITECTURE_REDUCTION_ROUTE_API`,
  `CODE_STRUCTURE_RECOMMENDATION_ROUTE_API`,
  `MODEL_TEST_ALIGNMENT_ROUTE_API`, `MODEL_ANGLE_DELIBERATION_API`,
  `MAINTENANCE_OBLIGATION_MEMORY_API`,
  `MAINTENANCE_SCAN_ROUTE_API`, and `PLAN_DETAILING_ROUTE_API`
- `CORE_API`
- `REPORTING_HELPER_API`
- `EVIDENCE_API`
- `API_SURFACE`
- `MODELING_HELPER_API`, the complete helper index and migration inventory

They are descriptive lists of exported public names. Runtime policy is enforced
by the runner, audits, templates, and route checks rather than by these grouping
constants alone.

## Agent Guidance

Start with the formal model-first path and keep skipped checks visible. Add
route helpers when they clarify a real risk, reduce repetitive code, or improve
reporting honesty. In an existing modeled system, use Existing Model Preflight to
look up current model responsibilities, FunctionBlocks, state owners,
side-effect owners, and public entrypoints before proposing new ownership or a
parallel workflow. Before trusting that one existing route is enough, record
model-angle deliberation when the task may need a different viewpoint: what the
current model sees, what it misses, what fails if ignored, and whether the
answer is reuse, extend, child model, new model, scoped/deferred, or human
review. When model obligations and tests both exist, use Model-Test
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
progress-only, or release-only, run AutoSplit, ModelMesh, or TestMesh
separately and consume that route evidence before claiming broad parent
confidence. For
large model or validation meshes, record the target split derivation from the
FlowGuard source model before trusting parent/child ownership and evidence.
After non-trivial FlowGuard-managed work, run or construct a maintenance scan
with `review_maintenance_scan()` when changed artifacts, remembered maintenance
obligations, skipped routes, stale evidence, or structure/reduction signals may
require another owner route.
When parent confidence claims whole-flow closure, add a
mesh closure model so root entries, child outputs, joins, terminal
dispositions, repeated-input repair feedback, blocker/progress tokens, and
out-of-scope branches are checked as executable handoff obligations before
`mesh_green_can_continue`. When a parent model relies on
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
that aligns feature contracts, reviewed journeys, every reachable enabled
control's real click-through evidence or scoped blindspot, model revision, and
residual implementation blindspots. Use
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
