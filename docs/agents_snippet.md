# AGENTS.md Snippet: Global FlowGuard Skill Routing

Copy this compact section into another repository's `AGENTS.md`.

```markdown
## Global FlowGuard skill routing

For coding, repository, process-design, structured writing/argument,
decision/planning, documentation, prompt, skill, release, archive, publish, and
software-maintenance work, first make a lightweight FlowGuard routing decision:
`use_direct_flowguard_skill`, `use_model_first_kernel`, `skip_with_reason`, or
`needs_human_review`.

Use `use_direct_flowguard_skill` when the task clearly matches a directly
installed FlowGuard satellite skill. Treat installed FlowGuard skills as peer
routes: route clear existing-model preflight, staged-development, UI,
structure, test, mesh, alignment, or model-miss work directly to the matching
satellite skill.

Use `use_model_first_kernel` when the task needs ordinary behavior/state
modeling, the correct FlowGuard route is unclear, multiple FlowGuard routes
must be coordinated, or a small core model is needed before narrowing to a
satellite route.

Use `skip_with_reason` only for clearly trivial copy edits, formatting-only
changes, direct command answers, read-only explanation, or work with no
behavior/state/process/release impact. If the behavior or process boundary is
unclear, use `needs_human_review` or narrow the task before deciding whether to
model.

Thin default path:

```text
risky boundary -> Input x State -> Set(Output x State)
-> one invariant or scenario -> run checks
-> inspect counterexample -> escalate only if a named risk requires it
```

Use this smallest useful path first when it can expose the important state,
ordering, retry, side-effect, or evidence-freshness failure. Treat satellite
skills, helper APIs, ledgers, meshes, and framework suites as escalation paths,
not default reading for every FlowGuard task.

This path is only the entry shape. Complete FlowGuard use requires the
FlowGuard closure contract for the claim: required plan/risk intake, model
ownership or new boundary, same-class miss evidence when relevant,
model-test/code alignment, mesh or boundary proof when relevant, model
maturation when later evidence says the model is too coarse, evidence freshness,
Risk Evidence Ledger, and typed claim-chain support must be current.
If a required gate is missing, stale, skipped, progress-only, internal-path-only,
release-only, or scoped out, report partial/scoped FlowGuard evidence rather
than full FlowGuard completion.

Hard gates:

- Verify the real package before modeling:
  `python -c "import flowguard; print(flowguard.SCHEMA_VERSION)"`.
- Do not create a fake mini-framework and claim FlowGuard adoption.
- Keep FlowGuard usable without any external planner or specification workflow.
  Planner handoffs are optional context, not prerequisites.
- Represent each block as `Input x State -> Set(Output x State)`.
- Do not replace executable modeling with prose.
- For non-trivial discussion, analysis, proposal, feature, bug fix, refactor,
  UI flow change, test change, prompt change, skill change, agent-workflow
  change, or process change in an existing modeled system, ground reasoning in
  existing FlowGuard models before choosing the technical route. Use
  `flowguard-existing-model-preflight` as a companion skill when model
  ownership may matter. This is not a universal parent route; pair it with the
  downstream FlowGuard skill that owns the concrete work.
- Do not weaken hard invariants merely to pass checks.
- Skipped, deferred, stale, or not-run checks are not passes.
- For non-trivial FlowGuard work, default to a user-facing Mermaid model
  snapshot during the work once the route or model shape is stable enough to
  explain. Run a FlowGuard diagram intent gate first: choose behavior/state,
  development process, UI state, model-test coverage, code structure, or mesh
  semantics from the active route. Show major states, branches, gates, evidence, claim boundaries,
  and skipped/not-run gaps; update the snapshot when
  the route, model, evidence, or claim boundary materially changes. Tiny,
  obvious, direct-command, formatting-only, or user-suppressed tasks may stay
  concise. The diagram explains the model and does not count as validation
  evidence. FlowGuard diagram guidance is standalone and must not require
  LogicGuard or a shared cross-family diagram protocol.
- Preserve user and peer-agent changes; stale evidence must be rerun or clearly
  bounded.
- For long background checks, progress is liveness only. Completion requires
  final output, error, combined, exit, and metadata artifacts.
- Before full done, release, publish, or production-confidence claims, use a
  Risk Evidence Ledger boundary to connect user risks, model obligations,
  optional code contracts, recurring defect-family gates, model/test split
  gates, and current proof evidence.
- When an AI-built plan or evidence adapter feeds that claim, run the
  plan-intake and typed claim-chain helpers first: plan completeness,
  evidence-adapter conformance, false-negative backpropagation, known-bad
  mutation rejection, and `production_confidence` dependency typing.
- Finish real project use with adoption evidence: trigger, model/risk, commands,
  findings, skipped steps, risk evidence summary, and next actions.

Route map (escalation only):

Think in buckets first: core modeling, implementation structure, UI,
tests/evidence, model hierarchy, process/release, and model-miss repair. Pick a
named route only when that bucket matches the actual risk.

| Trigger | Route |
| --- | --- |
| Existing modeled system discussion/change, model ownership lookup, reuse-first route grounding, duplicate-boundary risk before proposal or implementation | `existing_model_preflight` |
| Ordinary modeling, Risk Intent, state write inventory, invariants, Explorer | `core_modeling` |
| Existing code can likely be smaller without behavior change, repeated handlers/adapters/modules/branches, model-to-code contraction, or simplification before StructureMesh | `architecture_reduction` |
| Direct architecture recommendation or model-derived implementation structure | `code_structure_recommendation` |
| UI interaction model, app-level launch-to-terminal journey coverage, implemented/runnable UI validation against feature contracts and browser/manual click-through evidence, reachable visible-control branches, screen/region topology, parent/child UI hierarchy, menu levels, overlays, stable placement, display/text ownership, text hierarchy blueprint, duplicate information, or overlapping controls | `ui_flow_structure` |
| Direct comparison between FlowGuard model obligations, optional code external contracts, code-boundary runtime observations, and ordinary test evidence | `model_test_alignment` |
| Post-code, post-miss, model-test, mesh, code-boundary, or freshness signals say the model itself must be refined before broad confidence | `model_maturation_loop` |
| Final done/release/publish/full-confidence claim needs risk-to-model-to-code-to-evidence proof boundary | `risk_evidence_ledger` |
| Three or more local models, oversized model, parent/child model evidence | `model_mesh_maintenance` |
| Large test script/suite split, parent/child test hierarchy, slow/stale/release-only tests | `test_mesh_maintenance` |
| Large script/module/API split, public entrypoint compatibility, facade, ownership | `structure_mesh_maintenance` |
| Non-trivial staged development/modification, step ordering, touched artifacts, validation evidence, evidence freshness, peer writes, minimum revalidation | `development_process_flow` |
| Runtime/test/replay/manual validation fails after FlowGuard passed | `model_miss_review` |
| Production conformance, install sync, shadow workspace sync, adoption evidence | `conformance_adoption` |
| Long-running model/test/regression checks | `long_check_observability` |
| FlowGuard framework upgrade or broad benchmark/capability claim | `framework_upgrade` |

Directly invokable FlowGuard satellite skills are peer routes:

| Skill | Route |
| --- | --- |
| `flowguard-existing-model-preflight` | `existing_model_preflight` |
| `flowguard-model-test-alignment` | `model_test_alignment` |
| `flowguard-development-process-flow` | `development_process_flow` |
| `flowguard-model-miss-review` | `model_miss_review` |
| `flowguard-architecture-reduction` | `architecture_reduction` |
| `flowguard-code-structure-recommendation` | `code_structure_recommendation` |
| `flowguard-ui-flow-structure` | `ui_flow_structure` |
| `flowguard-model-mesh` | `model_mesh_maintenance` |
| `flowguard-test-mesh` | `test_mesh_maintenance` |
| `flowguard-structure-mesh` | `structure_mesh_maintenance` |

Use the direct FlowGuard satellite skill when the request clearly matches that
route. For ambiguous, cross-route, or general FlowGuard applicability work, use
`model-first-function-flow` as the kernel route.

Use the matching Skill reference protocol for support routes. Helper APIs such as
`RiskIntent`, property factories, packs, `FlowGuardCheckPlan`,
`RiskEvidenceLedgerPlan`, `review_risk_evidence_ledger()`,
`DefectFamilyGatePlan`, `review_defect_family_gates()`,
`PlanIntakeCompletenessPlan`, `review_plan_intake_completeness()`,
`EvidenceAdapterConformancePlan`, `review_evidence_adapter_conformance()`,
`FalseNegativeBackpropagationPlan`, `review_false_negative_backpropagation()`,
`PlanMutationReviewPlan`, `review_plan_mutations()`,
`FlowGuardClaimChainPlan`, `review_flowguard_claim_chain()`,
`review_code_structure_recommendation()`, `review_model_test_alignment()`,
`ExistingModelPreflight`, `review_existing_model_preflight()`,
`ObservableArchitectureContract`, `ArchitectureReductionCandidate`,
`review_architecture_reduction()`,
`UIDisplayElement`, `UIJourneyCoverage`, `UIImplementationValidation`,
`UITextHierarchyBlueprint`,
`review_ui_interaction_model()`, `review_ui_journey_coverage()`,
`review_ui_implementation_validation()`,
`review_ui_structure_derivation()`, `review_ui_text_hierarchy()`,
`review_development_process_flow()`, `review_auto_mesh_splits()`,
`review_test_mesh()`,
`review_structure_mesh()`, `review_layered_boundary_proof()`, templates, and
starter CLIs are package helpers, not Codex skills by themselves.

Use Model-Test Alignment when a model's scenarios, invariants, hazards,
transitions, contracts, optional code external contracts, or finite code
boundaries need direct test evidence. It compares plain `ModelObligation` rows,
optional `CodeContract` rows, optional `CodeBoundaryContract` /
`CodeBoundaryObservation` rows, and plain `TestEvidence` rows. Include code
contracts only when an externally visible code surface is in scope. Include
boundary observations when real code must prove it accepts only declared inputs
and emits only declared outputs, errors, state writes, and side effects. It does not invoke TestMesh, StructureMesh, or ModelMesh, and it does not split tests,
split code, or split models.

When real Python source and tests are available for those rows, add a
conservative source audit first: inspect AST-visible code surfaces and
AST-visible test assertions to generate or check code-contract evidence and
test-assertion evidence, then feed those rows into Model-Test Alignment. Treat
the audit as conservative support, not a perfect semantic proof. Dynamic or
complex behavior requires manual review, and source audit does not replace
conformance replay or other production-facing validation.

Use Risk Evidence Ledger as the final claim boundary. It consumes evidence ids
from Model-Test Alignment, TestMesh, ModelMesh, StructureMesh, UI Flow
Structure, DevelopmentProcessFlow, conformance replay, manual validation, or
ordinary tests, and it can also consume recurring defect-family gate status. It
then reports whether each user-facing risk is fully supported, scoped, or
blocked. It does not run those routes for you.

If a model, test, script, module, or command is becoming large, slow, or hard
to follow, consider whether a parent/child split would make it easier to
maintain or verify. For models consider ModelMesh; for tests consider TestMesh;
for scripts, modules, or APIs consider StructureMesh; when the goal is to make
existing code smaller without behavior change, consider Architecture Reduction
before Code Structure Recommendation or StructureMesh. Keep already-completed
or historical reduction candidates visible as evidence, but do not leave them
in the active ready queue; for long checks consider LongCheck observability.

When direct model/test evidence includes state counts, pending budgeted states,
duration, selected test counts, broad obligation counts, background
progress-only status, or release-only status, run `review_auto_mesh_splits()`.
It does not create a new route; it turns those signals into the existing
ModelMesh or TestMesh split gate and keeps parent confidence scoped or blocked
until current mesh evidence is consumed.

Treat ModelMesh, TestMesh, and StructureMesh as sibling parent/child partition
routes: models split into child models, tests split into child suites/scripts,
and existing code structure splits into child modules/scripts. StructureMesh
splits must include model-derived target code structure. Parent layers consume
child contracts and evidence; they should not expand every child internal route
into one large parent graph.

Treat DevelopmentProcessFlow as another sibling route, not a parent route. Use
it for non-trivial staged development or modification work with validation,
including plan, edit, test, fix, and verify sequences. Also use it when
development lifecycle ordering, artifact overwrite, verifier changes, peer
writes, or evidence freshness determine whether a done, release, archive, or
publish claim is supported. It may reference sibling route evidence ids, but it
does not inspect, supervise, or replace ModelMesh, TestMesh, StructureMesh,
Model-Test Alignment, LongCheck, or Conformance Adoption internals.

Use UI Flow Structure when the missing artifact is the UI interaction model
itself: initial UI state, controls, events, state nodes, transitions, recovery
paths, and state availability. After that model is reviewed, derive first-level
persistent menus, second-level contextual regions, third-level local controls,
overlays, stable layout positions, navigation ownership, and parent/child UI
topology. If the work claims complete app-level UI coverage, first review
launch-to-terminal journey coverage: launch state, entry points, feature
journeys, success terminals, recovery/cancel/exit handling, terminal action
allowances, and residual blindspots. Then derive the UI text hierarchy
blueprint from the reviewed structure: page and region headings, labels,
primary/secondary/contextual
action text, status/helper messages, validation text, empty/error/recovery copy
slots, semantic display labels, and text ownership by state, control, display,
region, and hierarchy level. Do not route this as ordinary Code Structure
Recommendation when the question is still UI behavior, hierarchy, and text
ownership; use code structure only for implementation module advice and
StructureMesh only for existing-code refactor governance.
If the work claims the running UI is implemented or complete, add UI
implementation validation after the model/design stages: user-visible feature
contracts, mapped journeys, browser/desktop/manual journey runs, step evidence,
current model revision, pure UI actions, and residual implementation blindspots.
Do not treat "manually tested" prose as proof unless it is recorded as
structured click-through evidence.

For ModelMesh and TestMesh, the parent split needs a FlowGuard-derived target
structure before green parent confidence: source model, target children,
covered partition items, ownership fields, and rationale. A supplied partition
map or flat child list alone is not enough.

For layered parent/child model confidence, keep four proof tables visible:
parent coverage, child disjointness, child reattachment, and leaf boundary
matrix. Parent and intermediate models may consume child contracts and evidence;
the lowest leaf models need complete finite
`Input x State -> Set(Output x State)` real-code boundary evidence. If a leaf
cannot be covered that way, split it again or scope the gap explicitly before
claiming parent confidence.
If Model-Test Alignment shows multiple primary `edge_path` proofs under one
obligation, treat that as a too-coarse model boundary and split child
obligations or reattach the tests to leaf matrix cells; do not merely downgrade
one proof label.

For whole-flow ModelMesh confidence, add a mesh closure model. It should model
root entries, child outputs, parent or sibling consumers, required joins,
normal/failure exits, out-of-scope dispositions, and loop-progress rules as
FlowGuard-style handoff obligations. Without a green closure model, the mesh may
support partition or reattachment confidence, but not entry-to-exit closure.

When a bug repair changes a local child FlowGuard model, child-local green is
not enough. The affected parent ModelMesh must consume the current child
evidence id and confirm the child's inputs, outputs, state ownership,
side-effect ownership, and outgoing guarantees still reattach to the parent
flow. If the child boundary changed, propagate that review upward to every
parent that consumes the child evidence id and review only the affected sibling
models that share or depend on the same parent partition items, state writes,
side effects, invariants, failure modes, or contracts.

For post-runtime model misses, classify the miss as `boundary_missing`,
`code_boundary_mismatch`, `state_too_coarse`, `input_branch_missing`,
`invariant_too_weak`, or `evidence_overclaimed`; represent the observed issue
and one same-class generalized bad case when practical; add
observed-regression and same-class test evidence; rerun Model-Test Alignment;
run `review_model_maturation_loop(...)`; then validate with production-facing evidence. The current bug instance and
bug-class responsibility are separate: patching the observed instance or
testing only the observed instance is not closure until the class is represented
and tested, or explicitly out of scope. If the same-class test space is large,
slow, layered,
background, or release-only, route it through TestMesh and report scoped
confidence until current child evidence exists; an in-progress background run
is still blocked evidence, not a pass. If the repair changed a child model
under a parent mesh, rerun the parent reattachment gate and affected sibling review
before closing the miss. A later green runtime check by itself does not close a
known model miss; it must be attached to the same-class test evidence and
alignment record that now owns the bug family. If the same-class miss recurs or
is high risk, promote it to a defect-family gate and feed that gate into the
Risk Evidence Ledger before claiming full confidence.

Do not require ordinary project work to run FlowGuard's internal framework
evidence suites. Use those only for FlowGuard/LiveFlowGuard upgrades, benchmark
claims, or broad capability claims.
```
