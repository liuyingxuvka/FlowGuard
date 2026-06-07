# AGENTS.md Snippet: Global FlowGuard Skill Routing

Copy this compact section into another repository's `AGENTS.md`.

```markdown
## Global FlowGuard Skill Routing

FlowGuard repository: https://github.com/liuyingxuvka/FlowGuard
Keep the managed AGENTS.md block and `.flowguard/project.toml` current.

### Decision

For coding, repository, process, prompt, skill, documentation, release, archive, publish, UI, test, and software-maintenance work, first decide:
`use_direct_flowguard_skill`, `use_model_first_kernel`, `skip_with_reason`, or `needs_human_review`.

- Use `use_direct_flowguard_skill` when a route-specific satellite clearly matches.
- Use `use_model_first_kernel` for ordinary behavior/state modeling, unclear route selection, or cross-route coordination.
- Use `skip_with_reason` only for tiny copy edits, formatting-only changes, direct command answers, read-only explanation, or work with no behavior/state/process/release impact.
- Use `needs_human_review` when the risk boundary cannot be narrowed safely.

### Thin Default Path

```text
risky boundary -> Input x State -> Set(Output x State)
-> one invariant or scenario -> run checks
-> inspect counterexample -> escalate only if a named risk requires it
```

This is the entry path, not a completion shortcut. Complete FlowGuard use needs current evidence for the selected route; skipped, stale, deferred, progress-only, or not-run checks are not passes.

### Hard Gates

- Verify the real package before modeling: `python -c "import flowguard; print(flowguard.SCHEMA_VERSION)"`.
- Verify the package version when adoption/version freshness matters: `python -c "import importlib.metadata as m; print(m.version('flowguard'))"`.
- If the managed AGENTS block or `.flowguard/project.toml` is missing, use `python -m flowguard project-adopt --root .`; if installed FlowGuard is newer than the project record, use `python -m flowguard project-upgrade --root .`. Project upgrade scans known FlowGuard artifacts, model evidence, tests, docs, and guidance; use `--records-only` only when intentionally scoping out that scan.
- FlowGuard is latest-schema-first: old artifacts may be upgraded at project/tool boundaries, but route logic should not preserve long-lived compatibility branches for obsolete fields, aliases, or wrappers.
- Default replacement means dispose the old path, old field, alias, wrapper, or fallback unless the user explicitly requests compatibility or preservation. If compatibility is explicit, record the preserved surface and evidence; otherwise delete, block, migrate, delegate, repair, or scope it out with a concrete reason.
- Field-bearing work needs a FieldLifecycleMesh view: high-level models include behavior-bearing fields, while child/leaf field models account all discovered fields and record owner, readers, writers, projection, lifecycle, and old-field disposition.
- Do not create a fake mini-framework or replace executable modeling with prose.
- Represent each modeled block as `Input x State -> Set(Output x State)`.
- Preserve user and peer-agent changes; later writes can stale earlier evidence.
- Long background checks are liveness only until final output and exit/status
  artifacts exist.
- Reused test results need current `TestResultReuseTicket` and
  `ProofArtifactRef`; old `passed` output is not current evidence by itself.
- After `run_model_first_checks()`, read structured ledger routes and obligations before manual route inference.
- Before trusting that one existing route or model is enough, record
  model-angle deliberation when the task may need a missing viewpoint: what the
  current model sees, what it misses, what fails if ignored, and whether to
  reuse, extend, add child model, create a new model, scope/defer, or ask for
  human review.
- For non-trivial FlowGuard work, show a route-specific Mermaid snapshot once the route/model is stable; diagrams explain and do not validate.
- Before full done/release/publish confidence, connect risks, obligations, maintenance obligations, code/test evidence, proof artifacts, automatic state-closure gaps, and topology-hazard gaps through Risk Evidence Ledger or equivalent.
- After non-trivial work, use `maintenance_scan_router` for SummaryReport gaps, changed artifacts, open obligations, skipped routes, stale evidence, state/topology gaps, or split/reduction signals.
- Finish real project use with adoption evidence: trigger, model/risk,
  commands, findings, skipped gaps, validation results, and next actions.

### Route Map

| Trigger | Route | Entry |
| --- | --- | --- |
| Changed artifacts, open maintenance obligations, stale evidence, skipped routes, split/reduction pressure after project work | `maintenance_scan_router` | `review_maintenance_scan()` or `maintenance-scan-template` |
| Older adopted project, old FlowGuard artifact, old model/test evidence, obsolete API aliases | `artifact_schema_upgrade` | `artifact-upgrade` or `project-upgrade` |
| Existing modeled system, ownership lookup, duplicate-boundary risk | `existing_model_preflight` | `flowguard-existing-model-preflight` |
| Current route/model may be too narrow or a new model angle may be needed | `model_angle_deliberation` | `model-angle-template` or `review_model_angle_deliberations()` |
| Field lifecycle, behavior-bearing field projection, old/replaced/deprecated field disposition | `field_lifecycle_mesh` | `flowguard-field-lifecycle-mesh` |
| Similar features, A/B workflow drift, sibling tests, shared-kernel/adapter suspicion | `model_similarity_consolidation` | `model-first-function-flow` reference |
| Rough idea/short plan needs detailed scope, state, evidence, receipts, rework | `plan_detailing_compiler` | `flowguard-plan-detailing-compiler` |
| Multi-skill/tool/plugin planning, skipped skill consequences, rework gates | `agent_workflow_rehearsal` | `flowguard-agent-workflow-rehearsal` |
| Ordinary behavior/state modeling, Risk Intent, state inventory | `core_modeling` | `model-first-function-flow` |
| Existing code/prompt flow should shrink without behavior loss | `architecture_reduction` | `flowguard-architecture-reduction` |
| Pre-code module/function/block ownership recommendation | `code_structure_recommendation` | `flowguard-code-structure-recommendation` |
| UI controls, screens, journeys, display/text ownership, runnable UI evidence | `ui_flow_structure` | `flowguard-ui-flow-structure` |
| Locally green model topology implies future-use hazards before broad confidence | `model_topology_hazard_review` | `flowguard-model-topology-hazard-review` |
| Model obligations versus tests, code contracts, or boundary observations | `model_test_alignment` | `flowguard-model-test-alignment` |
| Three or more models, oversized model, stale child evidence, parent/child mesh | `model_mesh_maintenance` | `flowguard-model-mesh` |
| Large/slow/stale/release-only tests or parent/child test hierarchy | `test_mesh_maintenance` | `flowguard-test-mesh` |
| Large script/module/package/API split, facade or public entrypoint parity | `structure_mesh_maintenance` | `flowguard-structure-mesh` |
| Staged development, edits, validation freshness, install/shadow/git sync | `development_process_flow` | `flowguard-development-process-flow` |
| Non-trivial bug repair, false confidence, or runtime/test/replay/manual evidence shows a missed failure class | `model_miss_review` | `flowguard-model-miss-review` |
| Model too coarse after state-closure/code/test/mesh/freshness evidence | `model_maturation_loop` | `model-first-function-flow` reference |
| Final broad confidence boundary | `risk_evidence_ledger` | `docs/risk_evidence_ledger.md` |
| Production conformance, install sync, shadow workspace sync | `conformance_adoption` | `model-first-function-flow` reference |
| Long-running model/test/regression check | `long_check_observability` | `model-first-function-flow` reference |
| FlowGuard framework upgrade or benchmark/corpus claim | `framework_upgrade` | `model-first-function-flow` reference |

### Reference Handoff

Use the matching satellite `references/*.md` file after selecting a route.
Package helpers such as `review_model_test_alignment()`,
`review_development_process_flow()`, `review_test_mesh()`,
`review_structure_mesh()`, `review_architecture_reduction()`,
`review_existing_model_preflight()`, `review_model_angle_deliberations()`,
`review_model_similarity_consolidation()`,
`review_plan_detail()`, `review_agent_workflow_rehearsal()`, templates, and
starter CLIs are helpers, not separate Codex skills.

When a change touches a feature that resembles another workflow, model,
test family, or code path, use Model Similarity Consolidation before claiming
maintenance coverage. Record whether the relation creates a maintenance group,
which sibling models/code/tests must be checked, which tests are shared versus
variant-specific, and whether shared-kernel/adapter work or false-friend
separation applies.

Do not require ordinary project work to run FlowGuard's internal framework
evidence suites. Use those only for FlowGuard upgrades, benchmark claims, or
broad capability claims.
```
