## 1. Existing ownership and executable model

- [x] 1.1 Record the plane-first Behavior Commitment lookup and full ExistingModelPreflight decision, reusing DevelopmentProcessFlow, PlanDetailing, TestMesh, proof-artifact, test-reuse, and self-maintenance owners.
- [x] 1.2 Add `.flowguard/spec_provider_work_packages/model.py` with `Input x State -> Set(Output x State)` blocks for provider discovery, reconciliation, begin snapshot, execute/reuse, post snapshot, projection, and archive readiness.
- [x] 1.3 Add known-bad model paths for unbounded discovery, missing task mapping, missing obligation mapping, product-owner takeover, derived-output input pollution, input mutation, incomplete receipt, implicit cross-change reuse, duplicate execution, and close without post snapshot.
- [x] 1.4 Add the model runner, register it in the model regression manifest, and prove expected pass/violation scenarios.

## 2. Provider-neutral work-package data model

- [x] 2.1 Add stable canonical structures for provider, work package, task, task/obligation binding, check definition, consumer, scoped-out reason, and reconciliation report identities.
- [x] 2.2 Enforce bidirectional completeness, unique primary ownership, typed infrastructure owners, and development-process plane boundaries.
- [x] 2.3 Add canonical language-neutral JSON serialization and deterministic fingerprints that exclude localized display text.
- [x] 2.4 Add projection helpers into PlanDetail, DevelopmentProcessFlow, TestMesh, `ProofArtifactRef`, and `TestResultReuseTicket` without duplicating their native decisions.

## 3. OpenSpec and Spec Kit read-only adapters

- [x] 3.1 Implement root-bounded OpenSpec discovery for active changes, tasks, current reports, provider version, requirement/check coverage, and explicit unavailable/stale states.
- [x] 3.2 Implement root-bounded Spec Kit discovery that activates only with a `.specify` project marker and reads feature spec/plan/tasks/checklists without requiring a local Spec Kit installation.
- [x] 3.3 Parse stable task ids/statuses for both providers and preserve parallel change identities rather than matching by task prose.
- [x] 3.4 Add adapter-version and unsupported-provider/schema findings; prohibit whole-computer discovery and provider writes.

## 4. Canonical inputs, sessions, receipts, and safe reuse

- [x] 4.1 Implement governed-input discovery and derived-output exclusion for evidence, reports, receipts, results, caches, bytecode, temporary installs, SkillGuard runtime output, and OpenSpec bookkeeping output.
- [x] 4.2 Implement immutable begin and post input manifests, same-session identity, changed-path evidence, peer-write invalidation, and close rejection when post evidence is absent or different.
- [x] 4.3 Implement exact check-definition, command/cwd, tool/schema/version, environment, input, coverage, result, and terminal-status fingerprints.
- [x] 4.4 Implement atomic immutable passing receipts and consumer fan-out references with explicit `executed`, `reused-current`, `stale`, `not-run`, and `blocked` states.
- [x] 4.5 Reuse only complete terminal success; reject running, progress, skipped, failed, timeout, ambiguous, missing-coverage, or fingerprint-mismatched evidence.
- [x] 4.6 Default reuse to one work package and require explicit `cross_change_safe` plus identical execution identity before cross-change reuse.
- [x] 4.7 Add single-writer lock handling that blocks live duplicate execution and recovers abandoned locks only with visible evidence.

## 5. Public API and CLI integration

- [x] 5.1 Export the spec work-package, reconciliation, session, receipt, and runner surfaces through `flowguard.__init__` with one canonical owner.
- [x] 5.2 Add `spec-work-package-audit`, `spec-session-begin`, `spec-check-run`, and `spec-session-close` CLI commands with canonical JSON output and portable path tokens.
- [x] 5.3 Add a portable SkillGuard project-adoption audit wrapper that resolves the installed SkillGuard root without embedding a user-machine path.
- [x] 5.4 Add templates/examples for provider work-package modeling and cached checks without presenting internal tool fields as product UI content.

## 6. Existing FlowGuard owner upgrades

- [x] 6.1 Extend DevelopmentProcessFlow artifacts/actions/evidence/freshness reviews to consume work packages, session snapshots, receipt fan-out, and provider-native close prerequisites.
- [x] 6.2 Extend TestMesh child evidence to preserve spec-check consumers, execution/reuse state, explicit cross-change scope, and receipt completeness.
- [x] 6.3 Extend PlanDetail source/step/validation projections with stable provider/work-package/change/task identities and bidirectional mapping rows.
- [x] 6.4 Extend ExistingModelPreflight to accept provider context after plane-first commitment lookup and reject provider/task ownership takeover.
- [x] 6.5 Extend proof-artifact and test-reuse validation for exact session/receipt identities and current consumer coverage.
- [x] 6.6 Register the new development-process behavior commitment and typed relations in the canonical BCL without touching product UI commitment ownership.
- [x] 6.7 Update self-maintenance and post-change scan inputs so missing/stale work-package evidence cannot hide behind locally green checks.

## 7. SkillGuard authority lifecycle and maintained skills

- [x] 7.1 Inventory all seventeen former V1 runtime surfaces and current V2 trio consumers before lifecycle changes.
- [x] 7.2 Add `v1_runtime_authority.status=migration-evidence` to all seventeen V2 sources with exact former paths and a claim boundary that makes V2 the only runtime authority.
- [x] 7.3 Recompile all seventeen V2 compiled contracts and check manifests with the official FlowGuard and installed SkillGuard compilers.
- [x] 7.4 Update DevelopmentProcessFlow, TestMesh, PlanDetailing, ExistingModelPreflight, and model-first guidance/protocols/agents/templates for spec work packages while preserving native ownership.
- [x] 7.5 Update affected V2 contract sources/model projections and regenerate; do not invent execution-depth calibration or claim `v2-only`.
- [x] 7.6 Run per-target runtime-authority, project audit, contract/depth/static suite, prompt parity, installed layout, and negative legacy-residual checks.

## 8. OpenSpec verification integration and regression tests

- [x] 8.1 Narrow the two current OpenSpec freshness watch sets to canonical sources/contracts and exclude derived SkillGuard/FlowGuard results.
- [x] 8.2 Wrap their identical full-model command with the same explicitly cross-change-safe semantic execution definition and shared immutable receipt.
- [x] 8.3 Wrap full pytest and other justified long checks with safe package-local or explicit cross-change receipt boundaries; retain fast focused checks for early failure.
- [x] 8.4 Add unit tests for both adapters, stable identities, bidirectional reconciliation, canonical JSON, and provider-authority boundaries.
- [x] 8.5 Add known-bad tests for output-as-input, input mutation after begin, missing post, progress as pass, unsafe cache hit, parallel-change receipt collision, peer-write staleness, missing mappings, and repeated identical execution.
- [x] 8.6 Add CLI/API/template/docs tests and verify the second exact cross-change consumer reports `reused-current` while a changed input/tool/coverage reruns.
- [x] 8.7 Add release-freshness tests proving OpenSpec/FlowGuard result files do not stale canonical topology while real spec/model/test/contract changes do.
- [x] 8.8 Model provider-orchestrator reuse separately from inner FlowGuard receipt reuse; require stateful begin/check/close wrappers to use `never` while ordinary pure checks default to exact reuse.
- [x] 8.9 Add the matching OpenSpec contract/runtime support and a frozen-resume regression after the active OpenSpec receipt-lifecycle writer releases its overlapping files.

## 9. Documentation, synchronization, and closure

- [x] 9.1 Update API, DevelopmentProcessFlow, TestMesh, ExistingModelPreflight, SkillGuard distribution, validation, and product architecture documentation with provider and claim boundaries.
- [x] 9.2 Update AGENTS/project guidance through owned templates so future agents use provider reconciliation without mixing it into product UI rules.
- [x] 9.3 Run focused tests and models, provider audit, SkillGuard project/static/depth checks, project audit, and strict OpenSpec validation; fix every failure.
- [x] 9.4 Run the full registered model inventory and full pytest through the new receipt runner on a frozen snapshot; consume terminal receipts and verify no watched input changed during either run.
- [x] 9.5 Synchronize shadow, formal repository, and installed skills without deleting or rolling back peer work; verify source/shadow/installed parity.
- [x] 9.6 Run `openspec verify reconcile-spec-provider-work-packages-with-flowguard-evidence`, confirm the report is current, and archive only after every task/evidence gate passes.
- [x] 9.7 Scope boundary recorded: the UI/product-language and execution-plane changes retain their own verification, archive, and Git/version owners; this provider-bridge package neither reruns nor closes them.
