## Context

FlowGuard already models UI controls, displays, states, visible-surface items, text hierarchy, observed UI inventory, human operability, and runnable evidence. Those layers currently assume that once content is assigned to a display or text owner it is eligible to appear. Free-text `purpose` and a small internal-term lint cannot reliably distinguish user-needed status from audit/model/test/diagnostic state, and an observed item can map directly to a display without proving that it should have been visible.

The existing owner is `ui_flow_structure`; `.flowguard/harden_ui_real_surface_validation` owns the final actual-surface comparison, and the behavior commitment ledger owns the external promise. Full existing-model preflight selected `extend_existing`, with no new route, skill, or audience system.

## Goals / Non-Goals

**Goals:**

- Put a typed content-admission decision before display/text/surface mapping.
- Keep the conceptual model to two groups: ordinary user content and internal content. Use three executable values only to distinguish default-visible from user-requested details.
- Make unclassified and internal content unable to support ordinary UI rendering or a complete UI claim.
- Model on-demand details as default-hidden state plus explicit reveal and close paths, including keyboard/focus equivalence for hover.
- Keep the compact public template compact while making it impossible to omit the admission decision.
- Bind model obligations, code contracts, finite known-bad cases, focused tests, full regression, installed skill parity, and local Git/shadow synchronization.

**Non-Goals:**

- No admin/operator/developer/auditor role taxonomy.
- No fixed text-count, small-print, font-size, or geometry quotas.
- No final product copywriting or visual redesign.
- No requirement to classify every backend field; only content that has reached the UI candidate boundary is in scope.
- No duplicate ledger rows for ordinary task-owned controls and their normal labels.

## Decisions

### 1. Three executable values represent two conceptual groups

`UI_CONTENT_VISIBILITY_CLASSES` contains `user_visible`, `user_on_demand`, and `internal`. `user_visible` and `user_on_demand` are both ordinary user-facing content. This is preferred over a role/audience matrix because the reported defect is admission and progressive disclosure, not authorization.

### 2. Add a typed visibility plan inside the existing UI owner

`UIContentVisibilityItem` records `content_id`, grouped `source_field_ids`, `visibility_class`, typed `user_need_refs`, reveal/keyboard/dismiss events, and rationale. Need references use `task:`, `state:`, `recovery:`, or `safety:` and resolve against supplied task/state models. `UIContentVisibilityPlan` records its model/revision boundary, candidate ids, items, validation boundaries, and rationale. `review_ui_content_visibility(...)` is the sole admission reviewer.

The modeled block is:

`candidate content x UI state -> Set(admission decision x UI state)`

This plan is an internal stage of `ui_flow_structure`, not a new public route.

### 3. Bind admission ids to existing UI rows

`UIDisplayElement`, `UITextElement`, and `UIVisibleSurfaceItem` gain an optional `content_visibility_id`. `UIStateNode` gains `hidden_displays`. Visible-surface, text-hierarchy, observed-surface, human-operability, and implementation reviews consume the plan when supplied.

Non-action observed content cannot use a direct display mapping to bypass admission. Mapping proves ownership and placement; it does not grant permission to display.

### 4. Use fail-closed admission without breaking constructors

New fields default to empty values so existing Python constructors and serialized models can still load. Empty does not default to `user_visible`: unclassified in-scope candidate content cannot render and cannot support a broad/complete UI claim. Bounded legacy reviews that do not opt into a visibility plan preserve their previous behavior, but new/updated public templates always include the plan.

### 5. User need is typed; keyword lint remains secondary

`user_visible` and `user_on_demand` need at least one user-need reference tied to a task, current state, recovery, or safety need. A free-text purpose alone is insufficient. The existing internal-term lint remains a secondary design smell; it is not the security boundary and is not expanded into a language-specific blacklist.

### 6. On-demand content is a real state transition

`user_on_demand` must be hidden in the default/closed state across display, text, visible-surface, and observed mappings, become visible only after a declared reveal event whose control is visible/enabled/labeled, and have an operable close/collapse/blur/Escape path. Hover requires a distinct focus/keyboard event. Human review binds each item to a task-owned affordance and content-specific feedback; implementation review uses structured default/reveal/revealed/return/internal-absence evidence rows plus an observed inventory, and positive rows must resolve to the same content item in the declared state.

### 7. FieldLifecycleMesh supplies candidates, not UI policy

Field lifecycle rows remain the owner/readers/writers inventory. Every field whose reader reaches the ordinary-UI boundary is handed to UI Flow Structure as a candidate, regardless of its source role; fields without an ordinary-UI reader stay internally accounted. The UI layer decides admission. No new generic field schema or role taxonomy is added in this change.

### 8. Finite contract coverage is model-local

The finite axes are visibility class (`user_visible`, `user_on_demand`, `internal`, unknown), mapping target (none/display/text/visible/observed), UI state (closed/revealed), and user-need reference (present/absent). ContractExhaustionMesh deterministically produces 80 cases, one shard, and one receipt; the real reviewer executes every tuple with a case-specific pass/block oracle. The Behavior Commitment Ledger, Model-Test Alignment, TestMesh, Risk Evidence Ledger, and the matrix test share the same obligation, code-contract, test, case, shard, and receipt ids.

### 9. Closure owns current evidence production and child receipts

The final closure runner regenerates focused core/template/matrix JUnit artifacts, reruns the UI owner, real-surface, Behavior Ledger, and FieldLifecycle child models, verifies each child `result.json`, and fingerprints those current artifacts before reviewing MTA, TestMesh, and Risk Evidence Ledger. A pre-existing result file or non-empty evidence id cannot make the closure green.

### 10. Repository and installation sync is evidence-gated

The no-`.git` shadow workspace is the implementation workspace. After OpenSpec verification and regressions pass, only the owned changed paths are merged into the repository checkout, preserving unrelated dirty files. The repository-managed `.agents/skills` tree remains canonical for skill installation; installation and formal/shadow/installed parity are checked after the Git merge. No remote push or tag is part of this change.

## Risks / Trade-offs

- **Risk: optional defaults let legacy callers omit the plan** → New public templates and complete-claim reviews require the plan; compatibility is limited to loading and bounded legacy behavior.
- **Risk: authors classify everything as `user_visible`** → Require typed user-need references and known-bad tests; free-text rationale alone does not pass.
- **Risk: every control label creates duplicate paperwork** → Exempt ordinary task-owned controls and normal labels; apply the plan to content that can expose state or metadata.
- **Risk: a control owner id is used to disguise state/metadata text** → Require registered exact-label shape and, when task evidence is available, in-scope task ownership.
- **Risk: hover-only details are inaccessible** → Require keyboard/focus equivalence and close/collapse behavior.
- **Risk: all checks are green but their evidence ids do not connect** → Use one canonical chain and a regression that resolves the exact owner, cases, shard, receipt, and tests.
- **Risk: keyword rules miss Chinese or novel internal fields** → Make typed admission and mapping prohibition primary; keep keyword lint secondary.
- **Risk: peer changes are overwritten during sync** → Compare fingerprints before merge, patch only owned files, and verify unrelated Git diffs remain present.
- **Risk: background regression is mistaken for completion** → Treat running output as liveness only and require final exit/result artifacts before verification or sync.

## Migration Plan

1. Add OpenSpec and model commitments first.
2. Add compatible core dataclasses/reviewer and public exports.
3. Integrate admission into existing UI reviewers and state modeling.
4. Update compact/full templates, skill prompt/protocols, generated contracts, and documentation.
5. Add focused positive/negative tests and finite-case coverage.
6. Run model checks, focused tests, full regression, project audit, and OpenSpec verification.
7. Merge owned paths into the local Git checkout, install repository-managed skills, and verify formal/shadow/installed parity plus import path/capability markers.

Rollback is path-scoped: revert only this change's owned files and re-run the same focused/model checks. Do not reset the shared Git worktree or discard unrelated peer changes.

## Open Questions

None. Future operator/developer diagnostic surfaces require a separate explicitly scoped product change.
