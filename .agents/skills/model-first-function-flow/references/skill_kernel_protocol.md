# FlowGuard Skill Kernel Protocol

The `model-first-function-flow` Skill is a kernel, not a monolith. The kernel
owns trigger selection, hard gates, route selection, and resource discovery.
Detailed procedures live in sub-protocol references or in route-specific
standalone satellite skills.

## Kernel Owns

- applicability decision: `use_flowguard`, `skip_with_reason`, or
  `needs_human_review`;
- flow lens: `behavior_flow`, `argument_flow`, or `decision_flow`;
- a soft oversize hint that suggests considering parent/child splits for large
  or hard-to-follow models, tests, scripts, modules, and commands;
- hard gates: real package import, no fake mini-framework, executable evidence
  over prose, skipped is not pass, and adoption evidence for real use;
- route map to specialized protocols and directly invokable satellite skills;
- distinction between agent sub-protocols and package helper APIs.

## Standalone Satellite Skills

These route-specific Codex skills can be invoked directly when the user's
request clearly matches their trigger:

| Satellite skill | Route |
| --- | --- |
| `flowguard-model-test-alignment` | `model_test_alignment` |
| `flowguard-development-process-flow` | `development_process_flow` |
| `flowguard-model-miss-review` | `model_miss_review` |
| `flowguard-architecture-reduction` | `architecture_reduction` |
| `flowguard-code-structure-recommendation` | `code_structure_recommendation` |
| `flowguard-ui-flow-structure` | `ui_flow_structure` |
| `flowguard-model-mesh` | `model_mesh_maintenance` |
| `flowguard-test-mesh` | `test_mesh_maintenance` |
| `flowguard-structure-mesh` | `structure_mesh_maintenance` |

If a task is ambiguous, cross-route, or starts from a general FlowGuard
applicability question, use the kernel first. Satellite skills must route back
to the kernel instead of taking ownership of unclear work.

## Sub-Protocols Own

| Sub-protocol | Owns |
| --- | --- |
| `core_modeling` | Risk Intent, state write inventory, function blocks, invariants, Explorer, CheckPlan |
| `architecture_reduction` | behavior-preserving code contraction candidates, observable architecture contracts, and target StructureMesh handoff |
| `ui_flow_structure` | UI interaction model, app-level journey coverage, implemented/runnable UI click-through evidence alignment, reachable visible-control branches, state/control/event/display transitions, parent/child UI topology, menu levels, overlays, stable placements, UI text hierarchy blueprint, and intentional redundancy |
| `model_test_alignment` | direct comparison of model obligations with ordinary test evidence |
| `model_mesh_maintenance` | parent/child model hierarchy, child reattachment, whole-flow mesh closure, and oversized-model governance |
| `test_mesh_maintenance` | parent/child test hierarchy plus validation evidence |
| `structure_mesh_maintenance` | parent/child script/module structure split evidence |
| `development_process_flow` | non-trivial staged development or modification, lifecycle ordering, artifact overwrite, evidence freshness, and minimum revalidation |
| `model_miss_review` | post-runtime model miss classification, current bug instance handling, and same-class bug responsibility closure |
| `conformance_adoption` | replay, install sync, shadow workspace sync, release sync, adoption evidence |
| `long_check_observability` | background log artifacts, liveness-only progress, and completion proof |
| `framework_upgrade` | FlowGuard self-upgrades and broad capability claims |

## Helper APIs Are Not Sub-Skills

These are package helpers:

- `RiskIntent`, `RiskProfile`, `FlowGuardCheckPlan`;
- property factories and packs;
- `review_model_test_alignment()`;
- `review_hierarchical_mesh()`, `review_mesh_closure_model()`,
  `review_test_mesh()`, `review_structure_mesh()`;
- `review_development_process_flow()` and `derive_revalidation_plan()`;
- `review_architecture_reduction()` and architecture reduction candidate rows;
- `UIDisplayElement`, `UIJourneyCoverage`, `UIImplementationValidation`,
  `UITextHierarchyBlueprint`,
  `review_ui_interaction_model()`, `review_ui_journey_coverage()`,
  `review_ui_implementation_validation()`,
  `review_ui_structure_derivation()`, and `review_ui_text_hierarchy()`;
- public starter templates.

They can support a route, but they are not independently triggerable agent
sub-skills.

## Maintenance Rules

- Keep `SKILL.md` short enough to scan as a router.
- Add detailed procedures to references, not the kernel.
- Keep satellite skills concise and self-contained enough for direct Codex use.
- Keep ModelMesh, TestMesh, and StructureMesh aligned as sibling
  parent/child partition routes for models, tests, and code structure.
- When a model miss repair changes a child model under a parent ModelMesh, keep
  Model-Miss Review responsible for the miss and ModelMesh responsible for the
  parent reattachment gate, upward child-boundary propagation, and affected
  sibling model review.
- Keep the current bug instance separate from bug-class responsibility:
  patching the observed instance is not closure until the miss is classified
  and the same-class case is represented or explicitly out of scope.
- Keep LongCheck evidence boundaries explicit: background progress is liveness,
  not pass evidence, until final output, error, combined log, exit, and
  metadata artifacts exist.
- Keep Model-Test Alignment independent from mesh routes; it compares plain
  obligation rows with plain evidence rows and does not split tests or code.
- Keep Architecture Reduction as the model-to-code contraction route. It may
  recommend merge/collapse/remove/keep-facade candidates, but it must hand
  production refactors to StructureMesh and lifecycle evidence to
  DevelopmentProcessFlow.
- Keep DevelopmentProcessFlow as a sibling lifecycle route. It may reference
  evidence ids from ModelMesh, TestMesh, StructureMesh, Model-Test Alignment,
  LongCheck, or Conformance Adoption, but it must not supervise, inspect, or
  replace those sibling route internals.
- Keep UI Flow Structure as a UI interaction/topology route. It builds or
  reviews the UI-level interaction model and, for complete app claims,
  launch-to-terminal journey coverage before deriving menus, regions, overlays,
  stable placements, display ownership, intentional redundancy, parent/child UI
  topology, and the UI text hierarchy blueprint for headings, labels, action
  text, state/status messages, helper text, and error/recovery copy slots; it
  aligns feature contracts with browser/desktop/manual click-through evidence
  when implemented/runnable UI completion is claimed; it
  does not replace visual design, final copywriting, or code-structure routes.
- Keep oversize guidance as a short consideration hint, not a threshold policy
  or forced split rule.
- Avoid duplicate ownership of the same rule across multiple references.
- Preserve standalone FlowGuard use; external planner handoffs remain optional.
- Before broad release, verify the installed kernel and satellite skills match
  the source skill directories.
