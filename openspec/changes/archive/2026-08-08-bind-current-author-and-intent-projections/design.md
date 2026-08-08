## Context

The existing suite tooling has one transactional consumer installer and a parity checker with explicit `author_source` and `consumer_distribution` roles. It has no write path for an author shadow, while the release parent requires the shadow tree to be an author source. The current shadow is an installer-owned clean consumer projection inside a dirty, independently developed FlowPilot repository, so whole-repository copying is both unsafe and semantically wrong.

Model intent inventories already carry strict internal fingerprints and source references. Revision construction reviews those internal identities but does not recompute the referenced source-file identities, so a stale inventory can remain internally self-consistent.

The current accepted revision records the delta that produced its candidate, while the self-blueprint currently reads that delta as if it were the whole system's current intent. The current ancestry contains repeated contribution ids and reaches only a subset of the current model-owner denominator, so concatenating history or choosing the last repeated id would create an implicit fallback and last-write-wins authority rather than a trustworthy cumulative view.

## Goals / Non-Goals

**Goals:**

- Make the complete FlowGuard author tree safely reproducible in one shadow skill root without touching its surrounding repository.
- Preserve modified, foreign, and co-located work through exact ownership checks and fail-closed conflicts.
- Make current intent source files a direct build input of model-revision construction.
- Bind each active local intent source to the exact logical model input inventory that consumes it, while preserving external WorkContext identity as a separate provider-neutral authority.
- Make the accepted revision the sole direct-current owner of a cumulative intent view while preserving the existing delta semantics.
- Prove current intent coverage separately for the complete model-owner and behavior-block denominators without copying full intent bodies per owner or behavior.
- Perform one explicit direct migration from the existing accepted ancestry and reject legacy current authority afterward.
- Keep the release workflow on one author projection, one consumer projection, and one current intent authority path.

**Non-Goals:**

- Synchronizing the FlowPilot repository outside `.agents/skills/<managed-flowguard-member>` and the suite ownership record.
- Adding compatibility readers, path guessing, partial-suite role transitions, or a second intent-inventory format.
- Refreshing or rewriting intent wording automatically when a source changes; the existing contribution must instead be deliberately renewed.
- Creating a second current-intent file, pointer, compatibility reader, automatic historical fallback, or generic root intent that can hide missing owner coverage.
- Treating model-owner coverage as proof that every implementation behavior consumes the right intent, or vice versa.

## Decisions

### Add one full-suite `author-sync` action

The installer command surface will gain a distinct `author-sync` action. It will use the existing canonical suite map and an author inventory compiler, never the consumer projection compiler. Keeping it distinct from `install` makes the projection role visible and prevents an option combination from silently changing an installed consumer into author source.

The transition is intentionally full-suite. A first consumer-to-author transition cannot safely update only the six currently affected skills because the target role and author-only inventory are defined for the complete 15-member suite. Full-suite synchronization is inexpensive compared with release validation and removes a partial-role branch.

Alternative rejected: use the existing consumer installer with the shadow path. That necessarily strips author controls and emits consumer release files, so parity can never prove an author shadow.

Alternative rejected: copy the whole FlowGuard checkout into FlowPilot. That overwrites unrelated project state, retains consumer-only extras, and violates the peer-work boundary.

### Use exact ownership to authorize replacement and deletion

The operation will accept either an exact installer-owned consumer tree for an explicit role transition or an exact previously synchronized author tree. It will stage the new managed tree, validate paths and the complete expected inventory, and atomically activate only after every planned target mutation is authorized. Modified owned files, unowned files inside a managed member, unsafe links, or role ambiguity block the complete operation. Co-located directories and all paths outside the managed member set are out of scope and remain untouched.

The ownership record will state the projection role and hashes of the exact managed files, enabling idempotence and future conflict detection. Consumer-only release manifests are removed only when their current hashes match the consumer ownership record.

### Verify intent source identity inside revision construction

Current-source validation will live with the existing model-intent loader/reviewer and be invoked by the revision builder before candidate output creation. Each direct relative source reference is resolved under the declared project root, rejected if unsafe or non-regular, and fingerprinted with FlowGuard's canonical source-file identity function so newline normalization matches the contribution producer. Contributions carrying complete WorkContext provenance are instead re-resolved through the current project WorkContext declarations and must match the exact context id, context fingerprint, native owner, source reference, and artifact fingerprint; this preserves provider-neutral Spark, OpenSpec, ChangeLog, and other external inputs without treating provider status as model evidence.

The builder will retain the verified source identities as frozen inputs and recheck them before publication. A mismatch is a visible stale-input failure; there is no source-path remapping, fallback inventory, or automatic refresh. This avoids adding another public refresh CLI and keeps renewal an explicit OpenSpec/model-intent action.

### Store the cumulative view inside the accepted revision

The revision schema will carry one `CurrentEffectiveIntentView`. Its active contributions retain their verified source identities. Compact owner bindings map the independently derived model-owner denominator to active contribution ids and the exact `model-realizes-purpose` relation in the candidate snapshot. The view also carries explicit transitions for every contribution active in the prior view. Its fingerprint is part of the revision identity, and the canonical head reaches it through the existing accepted-revision pointer.

Keeping the view inside the revision avoids a third mutable artifact and an additional current pointer. The delta intent review remains unchanged in meaning: it answers what this revision admitted and changed. The effective view answers what the whole current system now means. Normal construction folds the prior complete view with the delta under the same revision lock, validates every active source at the start and immediately before publication, and publishes the candidate snapshot plus revision through the existing content-addressed pair operation.

Alternative rejected: concatenate all historical accepted deltas at read time. Current history contains repeated ids without explicit supersession and does not cover the complete current owner denominator. A reader-side fold would be ambiguous, expensive, and a hidden fallback.

Alternative rejected: synthesize one standing-purpose contribution from each implementation model only in the self-blueprint. That would make the self projection appear complete without making cumulative intent part of current model authority, and it would create a second interpretation instead of fixing the capability for every target system.

### Bind local intent sources to exact model inputs

The model-regression manifest will carry an exact `intent_source_inputs` list for each model owner. It is not a broad discovery glob and it does not replace the cumulative intent view: the contribution remains the meaning and lineage authority, while this list makes the local source file part of that model instance's resolved immutable input inventory and focused validation contract. Revision construction compares the complete active project-file contributions with these owner-local paths before candidate publication. Missing, extra, duplicate, foreign-owner, unsafe, or unresolved bindings block visibly.

This creates the missing causal edge: changing one OpenSpec or other local intent source changes the input fingerprint of the model that owns it, so affected-owner planning can select that model directly. Several models may intentionally bind the same source file, but each keeps its own owner-local edge. A new intent source must be declared on its model before the contribution can become active, and retirement must remove the path when no active contribution for that owner uses it; stale historical paths cannot accumulate as hidden inputs.

WorkContext contributions remain outside repository path resolution. Their exact context id, context fingerprint, native owner, artifact id, source reference, and artifact fingerprint stay in the cumulative current-intent view and are reverified there. Treating an external provider artifact as a repository file would collapse two identity schemes and would make FlowGuard language- or provider-specific.

Alternative rejected: let any broad `input_globs` match count as intent ownership. Incidental directory coverage cannot prove which model consumes which design source and allows ownership to disappear when glob layout changes.

Alternative rejected: automatically append changed source paths after accepting a revision. That would require a second model revision merely to record the first revision's inputs and would leave a window in which the new intent is current but its model identity is not.

### Derive model and behavior denominators independently

Revision construction derives the complete model-owner denominator only from current candidate model instances and their exact realization relations. Every owner gets one compact binding, and every active contribution names one exact primary model owner. The same source artifact or design goal may support several owner-specific contribution records, so the source body is not copied while ownership stays unambiguous. Missing, extra, duplicate, or root fallback bindings block the view.

Behavior readiness retains its own independent observed-surface denominator. Each behavior block already names an exact model element; readiness will require a non-empty effective intent reference licensed by that owner's binding. This separately proves that all models are explained and that all implemented behaviors actually consume those explanations.

The embedded project intent inventory advances to its next strict schema because the independent model-owner denominator is now required data, not a derived optional decoration. The enclosing project blueprint document advances with it. A former parent document carrying a former child intent inventory is rejected visibly; the loader does not reinterpret the old document under the new meaning or add a compatibility reader.

### Use one explicit direct migration

The existing current revision predates the cumulative view. A bounded migration will audit only the exact accepted current ancestry, classify each historical contribution through typed retain, supersede, or retire decisions, exclude orphan revisions outside that ancestry, verify all active sources, and bind the full current owner denominator. It produces one accepted current-schema migration revision carrying an immutable bootstrap receipt fingerprint. Once that revision becomes current, normal authority loading rejects legacy revisions and never invokes migration automatically.

### Use one exact current-authority state loader

The current head is not proven by the snapshot and revision alone. One internal loader will read and cross-check the manifest head, observed snapshot, accepted revision, current activation-or-rollback transition receipt, exact predecessor binding, cumulative effective-intent view, and optionally reverified current source identities. Audit, revision planning/building, activation, and rollback consume this same result instead of independently deciding which subset of artifacts is sufficient.

The transition lookup is typed, not fallback. The head fingerprint must resolve to exactly one supported activation or rollback record. The receipt's own schema, content-address, system, revision, previous/candidate snapshot, subject revision, generation, expected predecessor head, and rollback contract/evidence bindings must all agree with the current head. A missing, duplicated, malformed, foreign, or partly matching receipt makes current authority invalid.

Authority audit always enables current source verification after immutable revision validation. A source change is reported as current-intent source staleness or absence, not as corruption of the historical revision that was valid when written.

### Preserve concurrent manifest work through final CAS

Activation and rollback may perform long validation after initially freezing the authority section. Immediately before pointer replacement, the writer re-reads the manifest. If the authority section changed, the operation stops as stale. If only unrelated sections changed, the writer replaces the authority section in the newest text and preserves those peer edits. The storage primitive enforces the expected authority identity so callers cannot accidentally write from the early cached manifest.

Immutable candidate artifacts written before a failed CAS remain non-current orphans and never participate in current lookup or ancestry merely because they exist on disk.

### Make legacy ancestry a strict direct chain

The explicit v4 bootstrap accepts both activation and rollback transitions as typed historical edges. For each step it reconstructs candidate predecessor heads and selects only the one whose complete head fingerprint equals the current transition's expected predecessor. An unrelated transition with the same snapshot and generation cannot make the real chain ambiguous; two exact predecessor matches do.

Every allowed historical schema receives a strict one-way parser that rejects duplicate or unknown keys, wrong primitive types, non-finite values, stale fingerprints, and violated version-specific acceptance invariants. These parsers exist only inside explicit migration and emit current audit records; they never return old runtime authority objects.

Bootstrap relation closure is exact. Current contributions may supersede only audited legacy contribution ids whose dispositions name the same replacements. Conflicts may reference current active contributions or explicit typed external owners only; unresolved current conflicts keep the view incomplete. Arbitrary ghost ids are rejected.

### Keep authority wire strict and non-duplicative

`complete`, `evidence_complete`, and `intent_acceptance_ready` are derived from authoritative members and do not remain independent truth in the content-addressed wire. They are recomputed for audit and display. Every remaining JSON field is type-checked before `_id`, `_text`, `_sha`, or other normalizers run; numbers, booleans, null, and arrays cannot become strings implicitly. This both contracts payloads and makes the raw wire schema equal the object identity being fingerprinted.

## Risks / Trade-offs

- **A legitimate hand-edited shadow file blocks synchronization** → Preserve it, report its exact path, and require the owning task to reconcile it deliberately; never overwrite it as release cleanup.
- **Atomic directory replacement differs across Windows filesystems** → Stage under the target root, validate all mutations first, use same-volume replacements, and retain the previous exact managed tree until post-activation verification succeeds.
- **Source identity changes while revision construction runs** → Recheck all frozen source identities immediately before publication and leave incomplete candidate material non-authoritative.
- **Full author synchronization copies unchanged members** → Use content hashes to avoid physical rewrites; the simpler complete role boundary is preferred over partial-role state.

## Migration Plan

1. Add and point-test current-source validation in model revision construction.
2. Advance the direct-current model-regression manifest once, add exact per-owner local intent-source paths, and block revision or audit when the active contribution set and those paths differ.
3. Add the current revision schema, cumulative fold, independent model denominator, behavior binding gate, strict loaders, and one explicit migration path.
4. Build and activate the one-way migration revision only after the complete current ancestry and owner denominator pass; do not change current authority on failure.
5. Add and point-test the author inventory, ownership transition, dry-run, conflict, preservation, and idempotence behavior.
6. Convert the existing exact installer-owned shadow consumer tree to author source with the new command.
7. Recompile consumer release authority, install the clean consumer projection locally, and require full role-aware parity.
8. If migration or synchronization fails, leave the prior current authority or target tree unchanged and keep release blocked; rollback never invokes a legacy normal-runtime reader or touches the surrounding repository.
