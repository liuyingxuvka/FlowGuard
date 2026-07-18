# AGENTS.md Snippet: Global FlowGuard Skill Routing
Copy this compact section into another repository's `AGENTS.md`.
```markdown
## Global FlowGuard Skill Routing

FlowGuard repository: https://github.com/liuyingxuvka/FlowGuard
Keep the managed AGENTS.md block and `.flowguard/project.toml` current.

Primary agent surface: the current clean consumer projection under `$CODEX_HOME/skills/`; Default entry skill: `$CODEX_HOME/skills/flowguard/SKILL.md`
Complete AI-agent setup means the agent can read `AGENTS.md` and all FlowGuard sibling `SKILL.md` files under `$CODEX_HOME/skills/`. An ordinary target project does not copy the FlowGuard suite into its local `.agents/skills/` tree and does not own the canonical suite map. Project audit and upgrade verify the package-owned clean-consumer authority directly against that global projection and its ownership manifest. The Python `flowguard` module/CLI is executable check support, not the AI-agent skill installation surface.
### Decision

For coding, repository, process, prompt, skill, documentation, release, archive, publish, UI, test, and software-maintenance work, first decide:
`use_direct_flowguard_skill`, `use_model_first_kernel`, `skip_with_reason`, or `needs_human_review`.

- Use `use_direct_flowguard_skill` when a route-specific satellite clearly matches.
- Use `use_model_first_kernel` for ordinary behavior/state modeling, unclear route selection, or cross-route coordination.
- Use `skip_with_reason` only for tiny copy edits, formatting-only changes, direct command answers, read-only explanation, or work with no behavior/state/process/release impact.
- Use `needs_human_review` when the risk boundary cannot be narrowed safely.
### Minimum Valuable Model

```text
risky boundary -> protected error class -> public/local risk template search
-> Input x State -> Set(Output x State)
-> state + side effects + completion evidence + known-bad case
-> FlowGuardCheckPlan + KnownBadProof + run_model_first_checks
-> inspect counterexample -> record template harvest closure
```

This is still compact, but it must have teeth. A new or deepened model names the real error it prevents, records used public/local template ids or a no-match reason, models completion evidence, includes a representative bad case, proves that bad case is caught, and closes template harvest as written, merged, duplicate-linked, or accepted not-harvestable. Complete FlowGuard use needs current evidence for the selected route; skipped, stale, deferred, progress-only, or not-run checks are not passes.

### Hard Gates
- Verify the real FlowGuard check engine before claiming executable evidence: `python -c "import flowguard; print(flowguard.SCHEMA_VERSION)"`.
- Verify the check-engine version when adoption/version freshness matters: `python -c "import importlib.metadata as m; print(m.version('flowguard'))"`.
- If the managed AGENTS block or `.flowguard/project.toml` is missing, use `python -m flowguard project-adopt --root .`; if the installed check engine is newer than the project record, use `python -m flowguard project-upgrade --root .`. Project upgrade scans known FlowGuard artifacts, model evidence, tests, docs, and guidance; use `--records-only` only when intentionally scoping out that scan.
- FlowGuard is latest-schema-first: old artifacts may be upgraded at project/tool boundaries, but route logic should not keep long-lived old branches for obsolete fields, aliases, or wrappers.
- Default replacement means dispose the old path, old field, alias, wrapper, or alternate success path. Delete, block, migrate, delegate, repair, replace, or scope it out with a concrete reason; do not leave it as a second successful route.
- Behavior Commitment Ledger is the default upstream inventory for broad behavior claims: register external promises, map every source surface, and assign exactly one primary owner model. Classify every production commitment as exactly one of `product_runtime`, `agent_operation`, or `development_process`; `commitment_kind` describes form, not ownership. Record `actor_kind`, typed relations, lookup bindings, evidence, and scoped disposition. Cross-plane context never transfers ownership. Before changing or claiming coverage, classify the ledger mode as `bootstrap_ledger`, `add_behavior`, `change_behavior`, `remove_or_replace_behavior`, `coverage_gap_backfill`, or `model_miss_check`; Model Miss searches the affected plane first and creates a gap only when no matching promise exists. Do not register every helper function, force every ordinary action through a model, or treat lookup as a guarantee of future AI behavior.
- Primary Path Authority is the default for path-sensitive work: enumerate all runtime paths, old paths, aliases, wrappers, helper routes, old fields, backup caches, migration paths, and recovery paths before implementation; select exactly one primary runtime authority per business intent; when the primary path fails, expose the failure and repair the primary path rather than automatically invoking an alternate path that returns success.
- Give one exact external user purpose one stable `business_intent_id`, one active behavior commitment, and one singular `primary_path_id`. Repeated UI, API, CLI, alias, adapter, wrapper, helper, and compatibility surfaces delegate to that same authority instead of creating another successful implementation.
- Broad done/release claims need Behavior Commitment Ledger evidence, Primary Path Authority evidence for `path_sensitive=true` commitments, ContractExhaustionMesh Cartesian coverage, TestMesh shard evidence, and Risk Evidence Ledger consumption. Old paths must be disposed or scoped out, not kept as successful route alternatives.
- Field-bearing work needs a FieldLifecycleMesh view: high-level models include behavior-bearing fields, while child/leaf field models account all discovered fields and record owner, readers, writers, projection, lifecycle, and old-field disposition. For full/runtime/release/production field claims, behavior projections should include minimal `gate:`, `test:`, and `replay:` evidence refs instead of only naming the field. FieldLifecycleMesh hands every field whose reader reaches an ordinary UI boundary to UI Flow Structure as a candidate field id or grouped source id, regardless of source role; it does not decide visibility or force fields with no ordinary-UI reader into the UI model.
- Same-class, field/schema, payload, transition, parent/child, or no-delta bad-case generation uses ContractExhaustionMesh after the owning route declares the finite boundary; model-scoped Cartesian coverage also needs axes, interaction groups, shards/receipts, and MTA/TestMesh/ModelMesh/RiskLedger consumption. Hand-written analogous examples are seeds, not canonical coverage.
- Do not create a fake mini-framework or replace executable modeling with prose.
- Represent each modeled block as `Input x State -> Set(Output x State)`.
- Treat direct finite-engine calls as internal mechanics, not the formal entry for non-trivial model creation.
- Preserve user and peer-agent changes; later writes can stale earlier evidence.
- Long background checks are liveness only until final output and exit/status artifacts exist.
- For existing/runnable UI, first inventory real visible items and map each to `UIControl`, `UIDisplayElement`, `UIVisibleSurfaceItem`, or blindspot; observation records reality but grants no display permission.
- Before state-exposing candidate content enters display/text/surface modeling, classify it exactly once as `user_visible`, `user_on_demand`, or `internal`. Unclassified/internal content cannot render; user content needs a typed and resolvable `task:`, `state:`, `recovery:`, or `safety:` reference. Only the exact normal label of a registered, in-scope task-owned control—with no extra state, disabled reason, or metadata—needs no duplicate row; do not add audience/role/persona categories. `user_on_demand` stays hidden across display/text/visible/observed mappings, has visible/enabled reveal and return controls, binds to content-specific feedback, and gives hover a distinct keyboard/focus event. Runnable claims use an observed inventory plus structured per-content visibility evidence.
- Review typography hierarchy, components, navigation, interaction, feedback, recovery, and transition semantics as one product-wide UI language inside UI Flow Structure. Equal semantic roles reuse one rule/token across pages, dialogs, capsules, and repeated components; exceptions are bounded and presentation-only, never a different business intent, commitment, path, visibility class, or result.
- Every reachable enabled UI control needs a visible-control -> event -> code owner -> backend/local function -> UI state update -> click/test evidence chain; API existence or label matching is not enough.
- Every supported UI task needs task coverage plus human-operability evidence: primary control, feedback, cancel/error, affordance, dialog/window return, keyboard/focus, and walkthrough.
- Source-based UI work needs generic source-baseline interaction semantics for native pickers, external opens, save/custom dialogs, no-handler controls, trigger/confirm/cancel/value/result/error branches. Greenfield UI should use user-task, visible-surface, functional-chain, and implementation evidence without inventing a source baseline.
- UI done/runnable/button-wired claims need current `UIImplementationValidation` and UI done-claim review; planned/background/artifact-only evidence is not release completion.
- Reused test results need current `TestResultReuseTicket` and `ProofArtifactRef`; old `passed` output is not current evidence by itself.
- Rough-plan discussion, multi-skill/tool workflow setup, staged execution, install/sync, release/archive/publish, post-change owner scans, and final process claims enter `flowguard-development-process-flow` first. Record `plan_detailing`, internal `strategy_selection`, `agent_workflow`, and `execution_freshness` in that order. Internal optimization stays inactive for ordinary work and activates only for `explicit_request`, `multiple_equivalent_routes`, `material_rework_risk`, or `diagnostic_boundary_choice`. Active comparison first proves outcome/obligation-evidence/safety/protected-side-effect/dependency-authority/execution-owner equivalence, then chooses `targeted`, `declared_complete`, or `budgeted` diagnosis plus `sequential` or isolation-proven `safe_parallel` execution. Hard blockers stop invalid descendants; material evidence stales the decision; TestMesh owns counts; relation-backed repairs use ordinary owners and affected revalidation. Estimated evidence supports a preference, never a global optimum.
- After `run_model_first_checks()`, read structured ledger routes and obligations before manual route inference.
- New/deepened models need template harvest closure before broad claims: written, merged, duplicate-linked, or accepted not-harvestable.
- Before trusting that one existing route or model is enough, let ExistingModelPreflight query the canonical behavior ledger by primary plane before path discovery, keep primary and typed related-plane hits separate, and then consume model-angle/similarity evidence when a missing viewpoint or same-plane workflow may matter. Ambiguity or fallback is a visible limitation, not permission to merge owners.
- When a workflow has multiple useful routes, old/new alternatives, or path-sensitive external proof, record business path identity: stable path id, intent, trigger, expected terminal, state writes, side effects, equivalent/exclusive paths, old-path disposition, and evidence ids.
- For non-trivial FlowGuard work, first show a short current-situation note: what is being checked, why it matters, current evidence or gaps, and the next step. Add or refresh a route-specific Mermaid snapshot when it clarifies the route/model; diagrams explain and do not validate.
- Before full done/release/publish confidence, connect risks, obligations, UI click-through gates, artifact-payload gates, code/test evidence, proof artifacts, automatic state-closure gaps, and topology-hazard gaps through Risk Evidence Ledger or equivalent.
- After non-trivial work, let DevelopmentProcessFlow consume post-change scan signals for SummaryReport gaps, changed artifacts, open obligations, skipped routes, stale evidence, state/topology gaps, or split/reduction pressure.
### Route Map
| Trigger | Route | Entry |
| --- | --- | --- |
| FlowGuard itself feels heavy, route groups are incomplete, field layers need folding, or AI needs route-first self-maintenance | `flowguard_self_maintenance` | `default_flowguard_self_maintenance_plan()` then `review_flowguard_self_maintenance()` |
| Older adopted project, old FlowGuard artifact, old model/test evidence, obsolete API aliases | `artifact_schema_upgrade` | `artifact-upgrade` or `project-upgrade` |
| Existing modeled system, ownership lookup, duplicate-boundary risk, model-angle gaps, or similar workflow evidence | `existing_model_preflight` | `flowguard-existing-model-preflight`; consumes model-angle and similarity rows |
| Full external behavior inventory, source-to-commitment coverage, one primary model owner per behavior, or broad behavior claim | `behavior_commitment_ledger` | `flowguard-behavior-commitment-ledger`; path-sensitive rows hand off to Primary Path Authority |
| Field lifecycle, behavior-bearing field projection, old/replaced/deprecated field disposition | `field_lifecycle_mesh` | `flowguard-field-lifecycle-mesh` |
| Canonical finite bad-case generation from declared fields, state/input boundaries, Cartesian interaction groups, same-class families, payload contracts, transition cells, parent/child closure, no-delta loops, broad coverage universe, or observed-problem backfeed | `contract_exhaustion_mesh` | `flowguard-contract-exhaustion-mesh` |
| New/deepened model must reuse/search and close public/local template harvest | `risk_template_library` | `risk-template-search`, `risk-template-harvest`, `risk-template-harvest-review`, or `risk-template-library-template` |
| Rough plan, multi-skill/tool setup, staged execution, conditional process optimization, post-change scan, install/sync, release/archive/publish, or final process claim | `development_process_flow` | `flowguard-development-process-flow`; owns internal `plan_detailing_compiler`, conditional `strategy_selection`, and `agent_workflow_rehearsal` routes |
| Ordinary behavior/state modeling, Risk Intent, state inventory | `core_modeling` | `flowguard` |
| Existing code/prompt flow should shrink without behavior loss | `architecture_reduction` | `flowguard-architecture-reduction` |
| Pre-code module/function/block ownership recommendation | `code_structure_recommendation` | `flowguard-code-structure-recommendation` |
| UI content admission, real visible surface inventory, controls, enabled-control functional chains, source-baseline interaction semantics when applicable, screens, journeys, display/text ownership, on-demand disclosure, runnable UI click-through evidence | `ui_flow_structure` | `flowguard-ui-flow-structure` |
| Locally green model topology implies future-use hazards, duplicate/conflicting paths, or old/new route gaps before broad confidence | `model_topology_hazard_review` | `flowguard-model-topology-hazard-review` |
| Model obligations versus tests, code contracts, boundary observations, or artifact payload cases | `model_test_alignment` | `flowguard-model-test-alignment` |
| Three or more models, oversized model, stale child evidence, parent/child mesh | `model_mesh_maintenance` | `flowguard-model-mesh` |
| Large/slow/stale/release-only tests or parent/child test hierarchy | `test_mesh_maintenance` | `flowguard-test-mesh` |
| Large script/module/package/API split, facade or public entrypoint parity | `structure_mesh_maintenance` | `flowguard-structure-mesh` |
| Non-trivial bug repair, false confidence, or runtime/test/replay/manual evidence shows a missed failure class | `model_miss_review` | `flowguard-model-miss-review` |
| Model too coarse after state-closure/code/test/mesh/freshness evidence | `model_maturation_loop` | `flowguard` reference |
| Final broad confidence boundary | `risk_evidence_ledger` | `docs/risk_evidence_ledger.md` |
| Production conformance, install sync, shadow workspace sync | `conformance_adoption` | `flowguard` reference |
| Long-running model/test/regression check | `long_check_observability` | `flowguard` reference |
| FlowGuard framework upgrade or benchmark/corpus claim | `framework_upgrade` | `flowguard` reference |
### Reference Handoff

Use the matching satellite `references/*.md` file after selecting a route.
Check-engine helpers such as `review_model_test_alignment()`,
`review_development_process_flow()`, `review_test_mesh()`,
`review_structure_mesh()`, `review_architecture_reduction()`,
`review_existing_model_preflight()`, `review_model_angle_deliberations()`,
`review_flowguard_self_maintenance()`, `review_model_similarity_consolidation()`,
`review_plan_detail()`, `review_agent_workflow_rehearsal()`, templates, and
starter CLIs are helpers, not separate Codex skills.
When a change touches a feature that resembles another workflow, model,
test family, or code path, feed Model Similarity Consolidation evidence into
ExistingModelPreflight or the selected owner route before claiming maintenance
coverage. Record whether the relation creates a maintenance group, which
sibling models/code/tests must be checked, which tests are shared versus
variant-specific, and whether shared-kernel/adapter work or false-friend
separation applies.

Do not require ordinary project work to run FlowGuard's internal framework evidence suites; reserve them for FlowGuard upgrades, benchmark claims, or broad capability claims.
```
