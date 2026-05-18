# AGENTS.md Snippet: Model-First Function Flow

Copy this compact section into another repository's `AGENTS.md`.

```markdown
## Model-first function flow

For coding, repository, process-design work, structured writing/argument, and
decision/planning work, first make a lightweight FlowGuard applicability
decision: `use_flowguard`, `skip_with_reason`, or `needs_human_review`.

Use FlowGuard before non-trivial work involving behavior, workflows, state,
module boundaries, retries, deduplication, idempotency, caching, side effects,
production conformance, repeated bugs, model-test coverage alignment, optional
external code contract coverage, multiple local FlowGuard models, large test
scripts/suites, slow or layered validation evidence, large script/module
splits, public entrypoint compatibility, development lifecycle evidence
freshness, meaningful process side effects, argument prerequisites, or decision
commitments.

Hard gates:

- Verify the real package before modeling:
  `python -c "import flowguard; print(flowguard.SCHEMA_VERSION)"`.
- Do not create a fake mini-framework and claim FlowGuard adoption.
- Keep FlowGuard usable without any external planner or specification workflow.
  Planner handoffs are optional context, not prerequisites.
- Represent each block as `Input x State -> Set(Output x State)`.
- Do not replace executable modeling with prose.
- Do not weaken hard invariants merely to pass checks.
- Skipped, deferred, stale, or not-run checks are not passes.
- Preserve user and peer-agent changes; stale evidence must be rerun or clearly
  bounded.
- For long background checks, progress is liveness only. Completion requires
  final output, error, combined, exit, and metadata artifacts.
- Finish real project use with adoption evidence: trigger, model/risk, commands,
  findings, skipped steps, and next actions.

Route map:

| Trigger | Route |
| --- | --- |
| Ordinary modeling, Risk Intent, state write inventory, invariants, Explorer | `core_modeling` |
| Direct architecture recommendation or model-derived implementation structure | `code_structure_recommendation` |
| Direct comparison between FlowGuard model obligations, optional code external contracts, and ordinary test evidence | `model_test_alignment` |
| Three or more local models, oversized model, parent/child model evidence | `model_mesh_maintenance` |
| Large test script/suite split, parent/child test hierarchy, slow/stale/release-only tests | `test_mesh_maintenance` |
| Large script/module/API split, public entrypoint compatibility, facade, ownership | `structure_mesh_maintenance` |
| Development lifecycle ordering, artifact overwrite, validation freshness, minimum revalidation | `development_process_flow` |
| Runtime/test/replay/manual validation fails after FlowGuard passed | `model_miss_review` |
| Production conformance, install sync, shadow workspace sync, adoption evidence | `conformance_adoption` |
| Long-running model/test/regression checks | `long_check_observability` |
| FlowGuard framework upgrade or broad benchmark/capability claim | `framework_upgrade` |

First-batch directly invokable Codex skills:

| Skill | Route |
| --- | --- |
| `flowguard-model-test-alignment` | `model_test_alignment` |
| `flowguard-development-process-flow` | `development_process_flow` |
| `flowguard-model-miss-review` | `model_miss_review` |
| `flowguard-code-structure-recommendation` | `code_structure_recommendation` |
| `flowguard-model-mesh` | `model_mesh_maintenance` |
| `flowguard-test-mesh` | `test_mesh_maintenance` |
| `flowguard-structure-mesh` | `structure_mesh_maintenance` |

Use a satellite skill directly only when the request clearly matches that
route. For ambiguous, cross-route, or general FlowGuard applicability work,
start with `model-first-function-flow`.

Use the matching Skill reference protocol for support routes. Helper APIs such as
`RiskIntent`, property factories, packs, `FlowGuardCheckPlan`,
`review_code_structure_recommendation()`, `review_model_test_alignment()`,
`review_development_process_flow()`, `review_test_mesh()`,
`review_structure_mesh()`, templates, and starter CLIs are package helpers, not
Codex skills by themselves.

Use Model-Test Alignment when a model's scenarios, invariants, hazards,
transitions, contracts, or optional code external contracts need direct test
evidence. It compares plain `ModelObligation` rows, optional `CodeContract`
rows, and plain `TestEvidence` rows. Include code contracts only when an
externally visible code surface is in scope. It does not invoke TestMesh,
StructureMesh, or ModelMesh, and it does not split tests, split code, or split
models.

When real Python source and tests are available for those rows, add a
conservative source audit first: inspect AST-visible code surfaces and
AST-visible test assertions to generate or check code-contract evidence and
test-assertion evidence, then feed those rows into Model-Test Alignment. Treat
the audit as conservative support, not a perfect semantic proof. Dynamic or
complex behavior requires manual review, and source audit does not replace
conformance replay or other production-facing validation.

If a model, test, script, module, or command is becoming large, slow, or hard
to follow, consider whether a parent/child split would make it easier to
maintain or verify. For models consider ModelMesh; for tests consider TestMesh;
for scripts, modules, or APIs consider StructureMesh; for long checks consider
LongCheck observability.

Treat ModelMesh, TestMesh, and StructureMesh as sibling parent/child partition
routes: models split into child models, tests split into child suites/scripts,
and existing code structure splits into child modules/scripts. StructureMesh
splits must include model-derived target code structure. Parent layers consume
child contracts and evidence; they should not expand every child internal route
into one large parent graph.

Treat DevelopmentProcessFlow as another sibling route, not a parent route. Use
it when development lifecycle ordering, artifact overwrite, verifier changes,
peer writes, or evidence freshness determine whether a done, release, archive,
or publish claim is supported. It may reference sibling route evidence ids, but
it does not inspect, supervise, or replace ModelMesh, TestMesh, StructureMesh,
Model-Test Alignment, LongCheck, or Conformance Adoption internals.

For ModelMesh and TestMesh, the parent split needs a FlowGuard-derived target
structure before green parent confidence: source model, target children,
covered partition items, ownership fields, and rationale. A supplied partition
map or flat child list alone is not enough.

For post-runtime model misses, classify the miss as `boundary_missing`,
`state_too_coarse`, `input_branch_missing`, `invariant_too_weak`, or
`evidence_overclaimed`; represent the observed issue and one same-class
generalized bad case when practical; rerun; then validate with production-facing
evidence. A later green runtime check by itself does not close a known model
miss.

Do not require ordinary project work to run FlowGuard's internal framework
evidence suites. Use those only for FlowGuard/LiveFlowGuard upgrades, benchmark
claims, or broad capability claims.
```
