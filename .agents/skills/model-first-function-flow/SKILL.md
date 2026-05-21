---
name: model-first-function-flow
description: FlowGuard kernel for ordinary behavior/state modeling, unclear FlowGuard route selection, cross-route coordination, and core model-first preflight. Use when no direct FlowGuard satellite skill clearly matches or when multiple FlowGuard routes must be coordinated; route clear existing-model preflight, staged development, UI, structure, test, mesh, alignment, and model-miss work to the matching FlowGuard satellite skill directly.
---

# Model-First Function Flow

This Skill is the **FlowGuard Skill Kernel**. Keep this file as the compact
router and hard-gate layer. Put detailed procedures in `references/*.md` or in
the route-specific standalone satellite skills.

Installed FlowGuard satellite skills are peer routes. When one direct
satellite route clearly matches the task, use that satellite skill directly.
Use this kernel for ordinary behavior/state modeling, unclear route selection,
cross-route coordination, or core model work before a more specific route is
known.

For non-trivial discussion, proposal, bug-fix, feature, refactor, UI, test,
prompt, skill, agent-workflow, or process changes inside an existing modeled
system, use `flowguard-existing-model-preflight` when model ownership may
matter. It is not a universal parent route; pair it with the downstream route.

For repository, coding, process-design, structured writing/argument, and
decision/planning work, first make a lightweight applicability decision:
`use_flowguard`, `skip_with_reason`, or `needs_human_review`.

Use FlowGuard when work may affect behavior, workflow state, retries,
deduplication, caching, side effects, module boundaries, data flow, production
conformance, repeated-bug handling, large model layout, model-backed code
contraction, architecture reduction, model-test obligations, slow validation,
irreversible process actions, evidence freshness, release side effects, UI
interaction topology, visible UI state transitions, display/text ownership, UI
structure, argument prerequisites, or decision commitments.

Skip only for clearly trivial copy edits, formatting-only changes, read-only
explanation, or work with no behavior/state/process impact. If the boundary is
unclear, narrow the task or mark `needs_human_review`.

## Hard Gates

- Verify the real package before modeling in another repository:
  `python -c "import flowguard; print(flowguard.SCHEMA_VERSION)"`.
- If the import fails, connect the real toolchain or record the task as
  blocked/partial. do not write a temporary mini-framework or fake mini-framework and claim FlowGuard use.
- FlowGuard must remain useful without any external planner or specification
  workflow. Planner handoffs are optional context, not prerequisites.
- Represent each modeled block as `Input x State -> Set(Output x State)`.
- Do not replace executable modeling with prose.
- For non-trivial FlowGuard work, default to a user-facing Mermaid model
  snapshot once the route or model shape is stable enough to explain. Run a
  FlowGuard diagram intent gate first: choose behavior/state, development
  process, UI state, model-test coverage, code structure, or mesh semantics.
  Do not flatten these into a generic flowchart. Tiny or user-suppressed tasks
  may stay concise. Diagrams explain, not validate; they do not count as
  validation evidence; guidance must remain complete without LogicGuard.
- Do not weaken hard invariants merely to pass checks.
- Skipped, deferred, stale, or not-run checks must stay visible. Skipped is not
  pass.
- Preserve user and peer-agent changes. If model, test, or workspace inputs
  changed after earlier evidence, treat that evidence as stale unless the
  unchanged boundary is explicit.
- Long-running checks may run in the background, but completion evidence needs
  final artifacts and exit status. Progress lines are liveness, not pass evidence.
- Finish real project usage with adoption evidence: why FlowGuard was used or
  skipped, what risk was modeled, what commands ran, what was found, and what
  remains.

## Route Map

Choose one or more routes. Some routes also have directly invokable Codex
satellite skills. The routes are agent behavior protocols, not package APIs.

| Trigger | Route | Direct skill or reference |
| --- | --- | --- |
| Existing modeled system discussion/change, model ownership lookup, reuse-first route grounding, duplicate-boundary risk before proposal or implementation | `existing_model_preflight` | `flowguard-existing-model-preflight` |
| Ordinary model-first workflow, flow types, Risk Intent, state write inventory | `core_modeling` | `references/modeling_protocol.md` |
| Existing code can likely be smaller without behavior change, repeated handlers/adapters/modules/branches, model-to-code contraction, or simplification before StructureMesh | `architecture_reduction` | `flowguard-architecture-reduction` |
| Direct architecture recommendation, model-derived implementation structure, pre-code module split planning | `code_structure_recommendation` | `flowguard-code-structure-recommendation` |
| UI interaction flow model, complete app launch-to-terminal journey coverage, implemented/runnable UI validation against feature contracts and browser/manual click-through evidence, reachable visible-control branches, screen/region topology, parent/child UI structure, navigation/state/event/display/text ownership, text hierarchy blueprint, duplicate information, or overlapping same-level controls derived from modeled UI behavior | `ui_flow_structure` | `flowguard-ui-flow-structure` |
| FlowGuard model obligations, optional code external contracts, and ordinary test evidence need direct comparison | `model_test_alignment` | `flowguard-model-test-alignment` |
| Three or more local FlowGuard models, oversized model, stale child evidence, parent/child model partition, affected sibling review, whole-flow mesh closure | `model_mesh_maintenance` | `flowguard-model-mesh` |
| Large test script/suite split, parent/child test hierarchy, slow/background/stale/skipped/release-only validation evidence | `test_mesh_maintenance` | `flowguard-test-mesh` |
| Large script/module/package/command/API split, facade-first refactor, public entrypoint compatibility, ownership split | `structure_mesh_maintenance` | `flowguard-structure-mesh` |
| Non-trivial staged development/modification, step ordering, touched artifacts, validation evidence, evidence freshness, peer writes, minimum revalidation, V-style process confidence | `development_process_flow` | `flowguard-development-process-flow` |
| Runtime, test, replay, log, or manual validation fails after a FlowGuard pass | `model_miss_review` | `flowguard-model-miss-review` |
| Production confidence, multiple production writers, install sync, shadow workspace sync, adoption evidence | `conformance_adoption` | `references/conformance_adoption_protocol.md` |
| Long model/test/check command that should not block the agent thread | `long_check_observability` | `references/long_check_protocol.md` |
| FlowGuard/LiveFlowGuard self-upgrade, benchmark/corpus capability claim, broad framework behavior claim | `framework_upgrade` | `references/framework_upgrade_protocol.md` |
| Compatible planning or specification artifact already decomposed the work | `optional_planner_handoff` | `docs/skill_orchestrator_collaboration.md` |

If a model, test, script, module, or command is becoming large, slow, or hard
to follow, consider whether a parent/child split, Architecture Reduction,
LongCheck observability, or the mesh routes would make it easier to maintain or
verify. For models consider ModelMesh; for tests consider TestMesh; for
structure consider StructureMesh; for long checks consider LongCheck.

When a post-runtime model miss is repaired in a child under a parent ModelMesh,
route through `model_miss_review` and `model_mesh_maintenance`: Model-Miss owns
the current bug instance and same-class bug responsibility; ModelMesh owns the
parent reattachment gate, upward propagation, and affected sibling review.

### Flow Lenses

Classify the main lens when using FlowGuard:

- `behavior_flow`: software, automation, operations, releases, UI state, or
  human workflow actions. Model phases, persisted records, side effects,
  retries, terminal status, rollback state, and stuck states.
- `argument_flow`: papers, reports, design docs, README claims, proposals,
  proofs, or explanations. Model introduced context, defined terms, evidence,
  supported claims, referenced figures, and allowed conclusions.
- `decision_flow`: planning, technical choices, releases, roadmap tradeoffs, or
  architecture decisions. Model goals, constraints, assumptions, evidence,
  options, commitments, irreversible steps, and changed-condition triggers.

## Workflow Skeleton

1. Decide applicability: `use_flowguard`, `skip_with_reason`, or
   `needs_human_review`.
2. Classify the main lens: `behavior_flow`, `argument_flow`, or
   `decision_flow`.
3. Choose the needed route(s) from the Route Map.
4. If a compatible upstream planning or specification artifact exists, inspect
   it as optional context. Continue standalone if no handoff exists.
5. Verify the real FlowGuard package is importable.
6. Start or plan adoption evidence for real project work.
7. Follow the chosen sub-protocol reference(s).
8. Build or update the smallest fit-for-risk executable model or mesh that
   exposes the customer-relevant risk.
9. Make representative known-bad hazards fail before trusting a route-specific
   pass. A happy-path pass is not enough for complex work.
10. Inspect counterexamples. If a trace is impossible or misses known behavior,
    revise the model, oracle, replay adapter, or architecture before claiming
    confidence.
11. Run the strongest practical model, replay, test, or manual validation for
    the touched boundary.
12. Update the user-facing model snapshot when route choice, branch coverage,
    evidence status, or claim boundaries materially change.
13. Update adoption evidence with commands, findings, skipped checks, residual
    risk, next actions, and the visible model boundary; diagrams explain, not validate.

## Helper APIs Are Not Sub-Skills

The following are FlowGuard package helpers or CLI scaffolds. Use them when they
fit, but do not describe the helper itself as an independently triggerable
Codex skill:

- `RiskIntent`, `RiskProfile`, `FlowGuardCheckPlan`,
  `run_model_first_checks()`.
- Property factories and packs such as `no_duplicate_by`, `at_most_once_by`,
  `cache_matches_source`, `DeduplicationPack`, `CachePack`, `RetryPack`, and
  `SideEffectPack`.
- Mesh review APIs such as `review_hierarchical_mesh()`,
  `review_mesh_closure_model()`, `review_test_mesh()`, and
  `review_structure_mesh()`.
- Alignment APIs such as `review_model_test_alignment()`,
  `audit_python_code_contracts()`, `audit_python_test_assertions()`,
  `review_python_contract_source_audit()`, and optional code external contract
  rows consumed by the model-test alignment plan.
- Development lifecycle helpers such as `review_development_process_flow()`
  and `derive_revalidation_plan()`.
- Existing-model grounding helpers such as `ExistingModelPreflight`,
  `ModelContextHit`, `ExistingOwnershipSnapshot`, `DuplicateBoundaryRisk`, and
  `review_existing_model_preflight()`.
- Architecture reduction helpers such as `ObservableArchitectureContract`,
  `ArchitectureReductionCandidate`, `ArchitectureReductionPlan`, and
  `review_architecture_reduction()`.
- UI flow structure helpers such as `UIDisplayElement`, `UIJourneyCoverage`,
  `UIImplementationValidation`, `UITextHierarchyBlueprint`,
  `review_ui_interaction_model()`, `review_ui_journey_coverage()`,
  `review_ui_implementation_validation()`, `review_ui_structure_derivation()`,
  and `review_ui_text_hierarchy()`.
- Template CLIs such as `project-template`, `risk-intent-template`,
  `model-miss-template`, `model-test-alignment-template`,
  `ui-flow-structure-template`, `development-process-flow-template`,
  `existing-model-preflight-template`, `test-mesh-template`,
  `structure-mesh-template`, and `maintenance-template`.

## Standalone Satellite Skills
The directly invokable satellite skills are:
`flowguard-model-test-alignment`, `flowguard-development-process-flow`,
`flowguard-model-miss-review`, `flowguard-code-structure-recommendation`,
`flowguard-existing-model-preflight`, `flowguard-architecture-reduction`,
`flowguard-ui-flow-structure`,
`flowguard-model-mesh`, `flowguard-test-mesh`, and
`flowguard-structure-mesh`. Use the matching satellite directly when the user's
request clearly matches that route; otherwise use this kernel.

## Resource Map

- Kernel and core modeling: `references/skill_kernel_protocol.md`,
  `references/modeling_protocol.md`, `references/invariant_examples.md`, and
  `references/adoption_protocol.md`.
- Direct route references: `references/code_structure_recommendation_protocol.md`,
  `flowguard-architecture-reduction`, `flowguard-existing-model-preflight`, `flowguard-ui-flow-structure`,
  `references/model_test_alignment_protocol.md`,
  `references/model_mesh_protocol.md`, `references/test_mesh_protocol.md`,
  `references/structure_mesh_protocol.md`,
  `references/development_process_flow_protocol.md`, and
  `references/model_miss_protocol.md`.
- Validation and integration references:
  `references/conformance_adoption_protocol.md`,
  `references/long_check_protocol.md`,
  `references/framework_upgrade_protocol.md`, and
  `references/project_integration.md`.
- Starter assets: `assets/model_template/model.py`, `assets/model_template/run_checks.py`, and `assets/toolchain_preflight.py`.

## Constraints

- Use only Python standard library code in FlowGuard models.
- Do not call LLM APIs, databases, network services, clocks, random sources,
  probability models, or Monte Carlo from the model.
- Keep abstract state finite, immutable, and inspectable.
- Use internal FlowGuard evidence suites only for FlowGuard framework upgrades,
  benchmark/corpus claims, or broad capability claims, not ordinary project
  work.
