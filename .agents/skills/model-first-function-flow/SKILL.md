---
name: model-first-function-flow
description: For coding, repository, process-design work, structured writing/argument, and decision/planning work, first decide whether FlowGuard applies. Use before implementing or changing non-trivial behavior, stateful workflows, repeated bug fixes, module-boundary changes, idempotency-sensitive logic, deduplication logic, caching, retry handling, data-flow changes, UI interaction topology, model-test alignment, multi-model FlowGuard projects that need ModelMesh, slow or layered tests that need TestMesh, large script or module refactors that need StructureMesh, post-runtime model misses, framework upgrades, or any meaningful multi-step process, argument chain, or decision path that needs validation, adjustment, observation, or loss-prevention preflight.
---

# Model-First Function Flow

This Skill is the **FlowGuard Skill Kernel**. Keep this file as the compact
router and hard-gate layer. Put detailed procedures in `references/*.md` or in
the route-specific standalone satellite skills.

For repository, coding, process-design, structured writing/argument, and
decision/planning work, first make a lightweight applicability decision:
`use_flowguard`, `skip_with_reason`, or `needs_human_review`.

Use FlowGuard when the work may affect behavior, workflow state, retries,
deduplication, idempotency, caching, side effects, module boundaries, data
flow, production conformance, repeated-bug handling, large model layout,
UI information display ownership, duplicate UI information or overlapping
same-level controls, model-test obligation and optional external code contract coverage, large
test/script validation layout, large script/module decomposition, slow
validation evidence, irreversible process actions, development lifecycle
ordering, artifact overwrite, evidence freshness, publication/release side
effects, UI interaction topology, screen or region ownership, navigation state,
component event flow, visible UI state transitions, validation/error states,
parent/child UI structure derived from modeled user interactions, argument
prerequisites, or decision commitments.

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
- Do not weaken hard invariants merely to pass checks.
- Skipped, deferred, stale, or not-run checks must stay visible. Skipped is not
  pass.
- Preserve user and peer-agent changes. If model, test, or workspace inputs
  changed after earlier evidence, treat that evidence as stale unless the
  unchanged boundary is explicit.
- Long-running checks may run in the background, but completion evidence needs
  final artifacts and exit status, not progress lines alone.
- Finish real project usage with adoption evidence: why FlowGuard was used or
  skipped, what risk was modeled, what commands ran, what was found, and what
  remains.

## Route Map

Choose one or more routes. Some routes also have directly invokable Codex
satellite skills. The routes are agent behavior protocols, not package APIs.

| Trigger | Route | Direct skill or reference |
| --- | --- | --- |
| Ordinary model-first workflow, flow types, Risk Intent, state write inventory | `core_modeling` | `references/modeling_protocol.md` |
| Direct architecture recommendation, model-derived implementation structure, pre-code module split planning | `code_structure_recommendation` | `flowguard-code-structure-recommendation` |
| UI interaction flow model, screen/region topology, parent/child UI structure, navigation/state/event/display ownership, duplicate information, or overlapping same-level controls derived from modeled UI behavior | `ui_flow_structure` | `flowguard-ui-flow-structure` |
| FlowGuard model obligations, optional code external contracts, and ordinary test evidence need direct comparison | `model_test_alignment` | `flowguard-model-test-alignment` |
| Three or more local FlowGuard models, oversized model, stale child evidence, parent/child model partition | `model_mesh_maintenance` | `flowguard-model-mesh` |
| Large test script/suite split, parent/child test hierarchy, slow/background/stale/skipped/release-only validation evidence | `test_mesh_maintenance` | `flowguard-test-mesh` |
| Large script/module/package/command/API split, facade-first refactor, public entrypoint compatibility, ownership split | `structure_mesh_maintenance` | `flowguard-structure-mesh` |
| Development lifecycle ordering, artifact overwrite, validation freshness, minimum revalidation, V-style process confidence | `development_process_flow` | `flowguard-development-process-flow` |
| Runtime, test, replay, log, or manual validation fails after a FlowGuard pass | `model_miss_review` | `flowguard-model-miss-review` |
| Production confidence, multiple production writers, install sync, shadow workspace sync, adoption evidence | `conformance_adoption` | `references/conformance_adoption_protocol.md` |
| Long model/test/check command that should not block the agent thread | `long_check_observability` | `references/long_check_protocol.md` |
| FlowGuard/LiveFlowGuard self-upgrade, benchmark/corpus capability claim, broad framework behavior claim | `framework_upgrade` | `references/framework_upgrade_protocol.md` |
| Compatible planning or specification artifact already decomposed the work | `optional_planner_handoff` | `docs/skill_orchestrator_collaboration.md` |

If a model, test, script, module, or command is becoming large, slow, or hard
to follow, consider whether a parent/child split would make it easier to
maintain or verify. For models consider ModelMesh; for tests consider TestMesh;
for scripts, modules, or APIs consider StructureMesh; for long checks consider
LongCheck observability.

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
12. Update adoption evidence with commands, findings, skipped checks, residual
    risk, and next actions.

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
  `review_test_mesh()`, and `review_structure_mesh()`.
- Alignment APIs such as `review_model_test_alignment()`,
  `audit_python_code_contracts()`, `audit_python_test_assertions()`,
  `review_python_contract_source_audit()`, and optional code external contract
  rows consumed by the model-test alignment plan.
- Development lifecycle helpers such as `review_development_process_flow()`
  and `derive_revalidation_plan()`.
- UI flow structure helpers such as `UIDisplayElement`,
  `review_ui_interaction_model()`, and `review_ui_structure_derivation()`.
- Template CLIs such as `project-template`, `risk-intent-template`,
  `model-miss-template`, `model-test-alignment-template`,
  `ui-flow-structure-template`, `development-process-flow-template`,
  `test-mesh-template`, `structure-mesh-template`, and
  `maintenance-template`.

## Standalone Satellite Skills

The directly invokable satellite skills are:
`flowguard-model-test-alignment`, `flowguard-development-process-flow`,
`flowguard-model-miss-review`, `flowguard-code-structure-recommendation`,
`flowguard-ui-flow-structure`, `flowguard-model-mesh`,
`flowguard-test-mesh`, and `flowguard-structure-mesh`. Use them directly only
when the user's request
clearly matches that route; otherwise start here in the kernel.

## Resource Map

- `references/skill_kernel_protocol.md`: ownership map for this kernel and its
  sub-protocols.
- `references/modeling_protocol.md`: core modeling protocol, flow lenses,
  Risk Intent, state write inventory, invariants, Explorer, and CheckPlan.
- `references/code_structure_recommendation_protocol.md`: model-derived
  implementation structure recommendation, ownership maps, facades, and
  validation boundaries.
- `flowguard-ui-flow-structure`: directly invokable route for building a UI
  interaction model first, then deriving parent/child UI topology, menu levels,
  overlays, stable control placement, and interface hierarchy.
- `references/model_test_alignment_protocol.md`: direct model-obligation,
  optional code external contract, and ordinary test-evidence alignment without
  TestMesh, StructureMesh, or ModelMesh.
- `references/model_mesh_protocol.md`: ModelMesh trigger, evidence tiers,
  required hazards, prompt template, and completion standard.
- `references/test_mesh_protocol.md`: TestMesh test-hierarchy trigger,
  parent/child partition, evidence checklist, prompt template, and
  routine/release standard.
- `references/structure_mesh_protocol.md`: StructureMesh trigger, ownership,
  facade, public entrypoint, dependency, config, parity, and release standard.
- `references/development_process_flow_protocol.md`: development lifecycle
  ordering, artifact overwrite, validation freshness, and revalidation standard.
- `references/model_miss_protocol.md`: post-runtime model-miss handling.
- `references/conformance_adoption_protocol.md`: conformance replay, install
  sync, shadow workspace sync, release sync, and adoption evidence.
- `references/long_check_protocol.md`: background log artifact contract.
- `references/framework_upgrade_protocol.md`: FlowGuard self-upgrade and broad
  capability-claim validation.
- `references/project_integration.md`: connecting the real package in another
  repository.
- `references/invariant_examples.md`: invariant patterns.
- `references/adoption_protocol.md`: legacy adoption logging reference.
- `assets/model_template/model.py` and `assets/model_template/run_checks.py`:
  minimal model starter.
- `assets/toolchain_preflight.py`: standard-library helper for locating or
  connecting the local FlowGuard toolchain.

## Constraints

- Use only Python standard library code in FlowGuard models.
- Do not call LLM APIs, databases, network services, clocks, random sources,
  probability models, or Monte Carlo from the model.
- Keep abstract state finite, immutable, and inspectable.
- Use internal FlowGuard evidence suites only for FlowGuard framework upgrades,
  benchmark/corpus claims, or broad capability claims, not ordinary project
  work.
