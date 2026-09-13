## 1. Freeze scope and current contracts

- [x] 1.1 Record the stable `completion_work_id` and change-manifest baseline for this change without modifying historical authority or receipts.
- [x] 1.2 Read the existing model-authority, validation-owner, completion, and SkillGuard contracts and add focused regression tests before changing their behavior.
- [x] 1.3 Add the new consumer-current-closure and finite-completion requirements to the implementation traceability map with one native owner per requirement.

## 2. Bound process and completion execution

- [x] 2.1 Extend the existing supervised process-tree core with a byte-preserving input/output entry point and route Git queries through it.
- [x] 2.2 Enforce per-query and aggregate Git observation deadlines, confirmed descendant cleanup, and non-reusable timeout evidence without retry loops.
- [x] 2.3 Add stable `completion_work_id` and `claim_scope` through completion objective, epoch, readiness, run-manifest, parent-receipt, and CLI identities.
- [x] 2.4 Enforce one initial plus one typed-repair production attempt per work item; make plan/readiness/reuse/report operations producer-free and non-consuming.
- [x] 2.5 Separate local-validation parent identity from release-tree identity; keep exact release reachability only on explicit release claims.
- [x] 2.6 Add regression tests for pointer/report/task updates, objective/output changes, concurrent attempt claims, third-attempt rejection, and local-versus-release scope.

## 3. Make light navigation genuinely local

- [x] 3.1 Change existing-model preflight to validate saved authority integrity and select exact model/input/runner/intent/contract paths before any whole-live audit.
- [x] 3.2 Implement typed selected-closure reads with safe Windows path validation, shared-input multi-owner handling, and one read per shared file.
- [x] 3.3 Return `authority_integrity`, selected-source currentness, and execution-evidence status separately; preserve as-of maps and explicit stale obligations.
- [x] 3.4 Make basic affected-blueprint navigation succeed without deep projection and keep deep projection absence as a scoped blocked claim.
- [x] 3.5 Add tests proving unrelated drift does not erase navigation, selected drift returns a map, no projection has zero producers, and full scope still enforces global drift.

## 4. Close first-adoption and authority transitions

- [x] 4.1 Add a private initial-current-intent-pending snapshot representation that preserves real model identities and derives coverage status from unresolved gaps.
- [x] 4.2 Connect each initial intent gap to its exact model endpoint in the typed affected closure; reject missing model intent, owner evidence, leaf evidence, or connection evidence.
- [x] 4.3 Extend the authority rebuild CLI with mutually exclusive expected-absent versus expected-old CAS preconditions and perform finite-input checks under the manifest lock.
- [x] 4.4 Make first adoption publish one accepted current-readable revision and remove the public bootstrap-only false-success path without weakening normal empty-revision rejection.
- [x] 4.5 Add tests for successful one-to-two-model adoption, missing initial evidence, same-source empty normal revision rejection, CAS conflict, and post-publish current readback.

## 5. Separate semantic inputs from pointer bindings

- [x] 5.1 Add one canonical semantic projection for `.flowguard/project.toml` that retains true policy/toolchain/selected-content inputs and excludes pointer/activation/report/task output fields from functional identity.
- [x] 5.2 Keep reverse-surface semantic mapping fingerprint separate from authority head binding and ensure rebinding never performs discovery or native production.
- [x] 5.3 Make accepted-candidate activation perform one pointer-last CAS and finite binding verification; preserve corruption, foreign-object, and selected-content stale failures.
- [x] 5.4 Add self-upgrade regression tests proving pointer-only changes do not rerun functional producers while selected model content changes invalidate only its typed closure.

## 6. Make patch review and relation ownership explicit

- [x] 6.1 Add and validate `flowguard.patch_change_manifest.v1` with baseline/current input manifests and planned changed paths; distinguish planned changes from observed test-time drift.
- [x] 6.2 Remove empty-delta all-model authorization, reject missing/stale change manifests, and reject functional test receipts when functional inputs drift during execution.
- [x] 6.3 Replace alphabetical or substring relation-owner guessing with typed source/endpoints and explicit governance mappings while retaining both endpoint obligations.
- [x] 6.4 Make prepare-only outputs self-contained and validate review-map source identity against the current root, work ID, and tested input manifest.
- [x] 6.5 Add patch-review tests for empty delta, limited owner selection, test drift, stale map, prepare-only flags, typed relation ownership, and no activation on no semantic change.

## 7. Prove the real consumer lifecycle

- [x] 7.1 Add the non-mocked two-model consumer fixture with finite alpha/beta boundaries, real runners, exact intent inputs, and one dependent connection fixture.
- [x] 7.2 Exercise first adoption, basic navigation, unrelated-model drift, selected-model stale map, affected leaf/connection validation, one revision activation, and current readback through public CLI/API entry points.
- [x] 7.3 Exercise report/task updates and repeated same-operation reads, asserting zero new producer, epoch, lease, or pointer writes after terminal completion.
- [x] 7.4 Exercise missing evidence, unsafe path, corrupt object, CAS race, Git timeout, and required-connection failure as finite non-pass outcomes with preserved diagnostics.

## 8. Align routing, self-model, and author projections

- [x] 8.1 Update FlowGuard and DevelopmentProcessFlow route text so light/affected/full and risk-admitted Agent Workflow Rehearsal boundaries match executable profiles.
- [x] 8.2 Update existing self-model scenarios for first-current reachability, local navigation, pointer binding separation, finite budget, and one final author validation without creating a second governance layer.
- [x] 8.3 Reconcile all newly changed files to their existing model owners and verify the owner DAG before any final full validation.
- [x] 8.4 Compile the direct-current contract trios, consumer-suite authority, self-blueprint, shadow projection, installed projection, and parity once after source freeze.

## 9. Validate and close exactly once

- [x] 9.1 Run targeted tests for each completed group and fix failures only within the declared owner/dependency closure.
- [x] 9.2 Freeze source, model inputs, toolchain, change manifest, review map, owner plan, claim scope, and work ID; do not add code or tests afterward.
- [ ] 9.3 Build the affected model parent and accepted revision using the frozen inputs, activate the sole pointer once, and verify normal current readback. Do not reopen readiness/epoch/repair or create a second functional route.
- [ ] 9.4 Run the one frozen functional owner plan required by the requested claim, then form the author-maintenance terminal by consuming its canonical receipts. Exact-current reuse is read-only and may have zero producers; do not force a second full or reuse-only producer pass.
- [ ] 9.5 Write the completion summary with executed/reused/blocked counts, evidence paths, local/release boundaries, temporary-evidence retention, and any explicit not-run external claims; mark this change complete only when the current acceptance criteria pass.

## 10. Universal finite hierarchy and external release convergence

- [ ] 10.1 Make the recursive hierarchy reviewer iterative for arbitrary finite depth; preserve cycle, reachability, direct-child receipt, finite-leaf, and cross-child-connection diagnostics.
- [ ] 10.2 Separate model-authority pointer provenance from node functional freshness: resolve one current snapshot, compare each affected node's actual model/partition/obligation/connection closure, and keep unchanged siblings reusable when only a pointer/head record changes.
- [ ] 10.3 Add real external-target release fixtures (ordinary Python and non-Python) using the same release consumer with an explicit target descriptor; do not require FlowGuard self-installation or SkillGuard author state.
- [ ] 10.4 Add generated depth 1/2/5/8/12 execution fixtures, a depth-1500 structural-only fixture, shared-producer diamond edges, local invalidation propagation, and publish-after-finalize zero-producer replay.
- [ ] 10.5 Validate this change and the existing source/consumer projection boundaries, then mark the OpenSpec tasks complete only after the focused and end-to-end gates pass.
