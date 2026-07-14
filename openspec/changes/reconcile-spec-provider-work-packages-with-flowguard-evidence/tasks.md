## 1. Existing ownership and executable model

- [x] 1.1 Record the plane-first Behavior Commitment lookup and full ExistingModelPreflight decision, reusing DevelopmentProcessFlow, PlanDetailing, TestMesh, proof-artifact, test-reuse, and post-change routing owners.
- [x] 1.2 Add `.flowguard/spec_provider_work_packages/model.py` with `Input x State -> Set(Output x State)` blocks for provider discovery, receipt-only reconciliation, frozen owner session, child execution/reuse, exact aggregation, execution close, OpenSpec read-only consumption/report, and post-report archive-readiness review.
- [x] 1.3 Add known-bad model paths for unbounded discovery, missing mappings, derived-output input pollution, missing/swapped child receipts, mixed snapshots, input mutation, provider re-execution, provider lifecycle cycles, duplicate execution, stale report rows, and post-report review before a report exists.
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
- [x] 5.2 Add `spec-work-package-audit`, `spec-session-begin`, `spec-check-run`, `spec-session-close`, `spec-receipt-consume`, and `spec-provider-close-review` CLI commands with canonical JSON output and portable path tokens.
- [x] 5.3 Add a portable SkillGuard project-adoption audit wrapper that resolves the installed SkillGuard root without embedding a user-machine path.
- [x] 5.4 Add templates/examples for provider work-package modeling and cached checks without presenting internal tool fields as product UI content.

## 6. Existing FlowGuard owner upgrades

- [x] 6.1 Extend DevelopmentProcessFlow artifacts/actions/evidence/freshness reviews to consume work packages, session snapshots, receipt fan-out, and provider-native close prerequisites.
- [x] 6.2 Extend TestMesh child evidence to preserve spec-check consumers, execution/reuse state, explicit cross-change scope, and receipt completeness.
- [x] 6.3 Extend PlanDetail source/step/validation projections with stable provider/work-package/change/task identities and bidirectional mapping rows.
- [x] 6.4 Extend ExistingModelPreflight to accept provider context after plane-first commitment lookup and reject provider/task ownership takeover.
- [x] 6.5 Extend proof-artifact and test-reuse validation for exact session/receipt identities and current consumer coverage.
- [x] 6.6 Register the new development-process behavior commitment and typed relations in the canonical BCL without touching product UI commitment ownership.
- [x] 6.7 Keep work-package session/receipt closure in DevelopmentProcessFlow and route missing/stale evidence through the existing generic post-change signal; remove the duplicate change-contract/check-id binding from SelfMaintenance.

## 7. SkillGuard current authority and maintained skills

- [x] 7.1 Inventory all seventeen former runtime surfaces and current trio consumers before direct replacement.
- [x] 7.2 Remove former runtime surfaces and require exactly one current contract trio; former shapes are rejection fixtures, never migration or fallback routes.
- [x] 7.3 Recompile all seventeen current compiled contracts and check manifests with the official FlowGuard and installed SkillGuard compilers.
- [x] 7.4 Update DevelopmentProcessFlow, TestMesh, PlanDetailing, ExistingModelPreflight, and model-first guidance/protocols/agents/templates for spec work packages while preserving native ownership.
- [x] 7.5 Update affected current contract sources/model projections and regenerate; execution depth comes only from current owner receipts.
- [x] 7.6 Run per-target runtime-authority, project audit, contract/depth/static suite, prompt parity, installed layout, and former-residual rejection checks.

## 8. OpenSpec verification integration and regression tests

- [x] 8.1 Narrow the two current OpenSpec freshness watch sets to canonical sources/contracts and exclude derived SkillGuard/FlowGuard results.
- [x] 8.2 Wrap their identical full-model command with the same explicitly cross-change-safe semantic execution definition and shared immutable receipt.
- [x] 8.3 Wrap full pytest and other justified long checks with safe package-local or explicit cross-change receipt boundaries; retain fast focused checks for early failure.
- [x] 8.4 Add unit tests for both adapters, stable identities, bidirectional reconciliation, canonical JSON, and provider-authority boundaries.
- [x] 8.5 Add known-bad tests for output-as-input, input mutation after begin, missing post, progress as pass, unsafe cache hit, parallel-change receipt collision, peer-write staleness, missing mappings, and repeated identical execution.
- [x] 8.6 Add CLI/API/template/docs tests and verify the second exact cross-change consumer reports `reused-current` while a changed input/tool/coverage reruns.
- [x] 8.7 Add release-freshness tests proving OpenSpec/FlowGuard result files do not stale canonical topology while real spec/model/test/contract changes do.

## 9. Documentation, synchronization, and closure

- [x] 9.1 Update API, DevelopmentProcessFlow, TestMesh, ExistingModelPreflight, SkillGuard distribution, validation, and product architecture documentation with provider and claim boundaries.
- [x] 9.2 Update AGENTS/project guidance through owned templates so future agents use provider reconciliation without mixing it into product UI rules.
- [x] 9.3 Run focused tests and models, provider audit, SkillGuard project/static/depth checks, project audit, and strict OpenSpec validation; fix every failure.
- [ ] 9.4 Run the full registered model inventory and full pytest through the new receipt runner on a frozen snapshot; consume terminal receipts and verify no watched input changed during either run.
- [ ] 9.5 Synchronize the canonical repository and installed skills without deleting or rolling back peer work; audit the retired shadow read-only, record it as non-authoritative, and verify canonical/installed parity.
- [ ] 9.6 Run `openspec verify reconcile-spec-provider-work-packages-with-flowguard-evidence`, confirm the report is current, and archive only after every task/evidence gate passes.
- [ ] 9.7 Return to the two UI/product-language/execution-plane changes, rerun only their current required evidence using safe shared receipts, then archive and complete local Git version/tag closure.

## Current source-freeze candidate evidence (2026-07-13)

- Spec receipt/work-package/CLI focused tests: `43 passed, 12 subtests passed`.
- DevelopmentProcessFlow/TestMesh/PlanDetail/ExistingModelPreflight/reuse/proof focused tests: `84 passed, 18 subtests passed`.
- Narrow public API and template contract nodes: `1 passed` each; both left zero matching descendant processes.
- Packaging contract: canonical `pyproject.toml` declares `spec-providers = ["PyYAML>=6.0"]`; the exact positive/missing-empty/wrong-version `tomllib` node passes (`1 passed`) without installing the extra and leaves zero matching descendant processes.
- Executable model: scenario, conformance, loop/deduplication, progress, and function-block contract reviews all pass; FlowGuard owner execution count is two (child plus aggregate), OpenSpec execution count is zero, and only the post-report read-only review returns archive readiness.
- Earlier API/template commands that timed out or overlapped are explicitly invalid evidence and are not counted.
- Items 9.4-9.7 close only from current terminal receipts, canonical/installed parity, read-only retired-shadow disposition, OpenSpec verification/archive evidence, and local Git/tag closure; this note does not claim those gates by itself.
