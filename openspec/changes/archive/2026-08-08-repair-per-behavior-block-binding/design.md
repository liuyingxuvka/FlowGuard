## Context

See `proposal.md` for motivation. The project blueprint now derives its behavior denominator from independent implementation observation. The owner declaration still carries shared model semantics and evidence authority, but block-specific portable fields and cases must no longer be stored or consumed as if one primary surface represented every observed behavior surface.

## Goals / Non-Goals

**Goals:**

- Represent one model owner as the parent of one or more exact behavior-block bindings.
- Keep block-local fields, implementation fingerprints, cases, and checker designs separate while preserving their common model authority and source-case lineage.
- Fail closed on foreign or nonexistent block references.
- Preserve affected-only compact reads despite a deeper whole-target model.
- Preserve a complete code map without pretending that every module, class, nested function, or pure private helper is an independently testable behavior.
- Keep whole-target compilation proportional to the materialized surfaces, contracts, cases, and coverage edges by indexing exact joins once.
- Keep source-inventory revision and current observed model-snapshot identity as distinct typed identities.
- Preserve exact accepted intent lineage from its source through every actually realized model owner to the owner semantic specification used by behavior blocks.
- Keep checker design, terminal execution evidence, and coverage ownership as separate facts.

**Non-Goals:**

- Run a reconstruction exercise or add a reconstruction product branch.
- Treat planned checker design as current executed evidence.
- Reopen or rewrite prior archived OpenSpec changes.

## Decisions

### Store portable bindings at behavior-block level

Each owner carries an exact collection of portable behavior bindings, one per observed behavior block. A model member may appear in a child binding only when the authority provider declares that exact child scope. Explicitly cross-cutting invariants or guarantees may be referenced by several children, but owner transitions and protected failures do not become child-local merely because the children share an owner. Input, output, and state field mappings remain surface-specific.

This is preferred over copying the primary surface's mappings because different functions can have different contracts. It is also preferred over deriving model member identities in the readiness consumer because code observation must not create its own model authority.

### Bind parent semantics only to an explicitly observed composite behavior

The provider may declare an observed composite workflow surface as the parent behavior block for a model owner only when it supplies an exact current, implementation-independent composite behavior contract with its own inputs, state/effects, outputs, completion, and source identity. A module or class path that matches the model owner, contains child functions, or appears in a manifest remains a supporting aggregate unless that independent composite contract exists. No lexical, containment, path, or owner-name rule promotes an aggregate into the behavior denominator.

An admitted composite binding may carry only the owner-level transitions and protected failures explicitly scoped to that composite. Detailed function and method bindings carry their own fields and only explicitly scoped model members. Every detailed behavior still receives its own good and boundary contract, while bad cases exist only for explicit surface-to-failure edges. When no composite behavior is admitted, supporting modules and classes bind directly to the model owner and do not receive fabricated cases. Neither a parent failure nor a parent or aggregate test result is copied to sibling behavior blocks.

### Bind intent to the current snapshot and every realized purpose owner

The project intent inventory uses the current observed model-snapshot fingerprint as both its target subject and observed subject. The source-inventory revision remains an independent build-input identity used to say which source content was observed; it never substitutes for the snapshot identity even when both are current.

For each intent contribution with an accepted disposition, the producer intersects the contribution's declared `target_relation_ids` with that disposition's exact `changed_relation_ids`. Every surviving `relation:model-realizes-purpose:<owner>` relation projects to the corresponding current `model-obligation:<owner>`. The primary logical model remains an exact target when declared, but it cannot hide an omitted accepted sibling owner. A declared relation absent from the accepted disposition is not projected, and a surviving relation whose owner is absent, foreign, or ambiguous blocks publication instead of being dropped.

### Bind owner semantics to the exact accepted intent source

Every owner semantic specification used by a behavior that consumes an accepted contribution includes that contribution's exact `(source_id, source_fingerprint)` pair in its provenance. Model, runner, declaration, and closure fingerprints remain necessary model authority but cannot substitute for intent-source lineage. The pair is stored once on the shared owner semantic object; behavior blocks retain stable semantic and contribution references rather than copying intent bodies.

The accepted intent review is loaded and frozen once for one blueprint build. Target projection, source authority, owner semantic provenance, behavior contribution references, and the build-input identity all consume that same frozen review so one stage cannot silently use another revision.

### Validate owner boundaries before partitioning cases

The owner declaration validates that every materialized case points to a block for which that owner supplies an exact portable binding. The readiness compiler then selects only the cases for the block currently being compiled. This prevents both false rejection of legitimate siblings and silent loss of foreign cases.

### Compare portable member catalogs by exact union

Each behavior block is compared with its own implementation surface. The independently supplied portable model catalog is then compared with the union of all bindings for that model. Requiring every block to bind every sibling field would recreate the owner/block level error; accepting only a subset union would hide missing model members.

The same exact-union rule applies to transitions, properties, invariants, assumptions, guarantees, and protected failures. For `S` behavior surfaces and `E` explicit surface-to-failure edges, case materialization is `2S + E` and six-dimension coverage is `6 * (2S + E)`. A dense result is permitted only when the provider explicitly supplies a dense edge set; the compiler never manufactures `S * F` edges from an owner with `F` failures.

### Preserve model-level source-case lineage

Generated block-local case ids include the stable implementation surface identity. `parameter_case_id` names the exact executable or planned checker case, while a separate `source_case_id` preserves the owner-level known-good, boundary, or known-bad origin. Several block-local cases can therefore share one model-level origin without colliding or producing false parameter-case gaps.

### Keep checker design, execution, and coverage ownership separate

A planned checker design records how one exact block-local case and dimension would be checked. It does not claim that the checker ran. Execution remains `not_run` until a current terminal receipt binds the exact coverage contract, behavior block, case, checker member, implementation subject, and execution owner; a parent suite or owner-level result cannot be copied to children.

Coverage ownership comes only from the exact owner declared by the coverage contract. Test-node location, suite membership, shared oracle lineage, model parentage, or a passing aggregate command cannot reassign that owner or lend the edge to a sibling. A coverage edge whose declared owner, case, implementation surface, or behavior block disagrees is rejected in both directions.

### Separate behavior blocks from supporting implementation surfaces

The independent implementation inventory remains the complete denominator: no discovered current surface disappears. The provider-specific self-adoption classifier marks entrypoints, public callables, and observed state/effect/dynamic writers as behavior surfaces. Modules, classes, nested functions, and pure private helpers remain current supporting surfaces and receive one exact owner relation instead of copied good/boundary/bad cases.

This keeps the generic blueprint provider-neutral. Other languages and non-code workflows supply equivalent dispositions through their own observation providers; Python syntax is not promoted into the generic model schema.

### Keep block contracts and whole-audit joins linear

Each behavior dimension applies to its one exact implementation surface. Shared owner rules remain referenced by stable semantic-rule ids and are not copied as an applicability list containing every sibling surface. Per-owner binding/case lookup, reduction-signal lookup, and candidate-to-contract/coverage lookup are indexed once and consumed by identity. No index changes authority or drops a denominator member; it only removes repeated full scans and repeated identity lists.

### Give normalized coverage payload one physical owner

The native typed behavior report retains its `BehaviorCoverageEdge` rows because readiness review must remain a pure, self-contained result. Once that report enters normalized, affected-read, or canonical physical projection, each complete coverage payload is stored only at `shared_objects[coverage_id]`. The normalized behavior view binds the report fingerprint plus exact coverage fingerprints, and coverage shards contain only a strict current-schema envelope of ordered coverage object references.

The producer validates the report and object store in both directions before creating shards. The normalizer accepts the already-created reference shards and rejects any missing, extra, reordered, duplicated, legacy full-payload, or otherwise inconsistent shard. The affected reader accepts only the strict reference envelope and loads the full row from the fingerprint-checked object store. The canonical `behavior_model` and `behavior_shards` exports remain reference-only; `shared_objects` is the sole complete normalized/canonical owner. No old full-shard reader or conversion fallback is retained.

### Prove publication currentness with an independent build-input identity

Architecture reduction materializes the complete self blueprint once. Before that build it captures a small, independently recomputable identity over the audited model-authority head, accepted revision, observed snapshot, self-blueprint definition, complete classified file-content inventory, semantic mesh, and provider contracts. Immediately before publication it recomputes that exact identity and fails if any field differs.

This comparator preserves the previous time-of-check/time-of-use boundary without rebuilding every behavior case, coverage edge, normalized object, and reduction candidate a second time. A matching input identity licenses reuse only of the deterministic in-memory build from the same review; it is not a validation receipt, does not license future runs, and cannot hide a changed denominator.

### Advance direct-current schemas

The strict project-blueprint definition and behavior-blueprint report schemas advance to new current versions. The loader accepts only the current per-block structure; no compatibility reader, alias, or fallback is introduced.

## Risks / Trade-offs

- [Risk] Whole-target self-blueprint materialization becomes larger because every observed behavior block has its own cases and field binding. → Mitigation: ordinary AI work consumes content-addressed affected-only and compact projections; whole expansion remains an explicit audit operation.
- [Risk] An over-broad self-adoption classifier fabricates thousands of cases for structural helpers, while an over-narrow classifier hides real behavior. → Mitigation: retain every surface in the implementation inventory, admit public callables and observed behavior-bearing surfaces, keep all remaining surfaces explicitly owner-bound as supporting, and test both directions.
- [Risk] Exact block-local objects create accidental quadratic joins during whole audit. → Mitigation: require singleton dimension applicability and pre-index all identity joins; add a real-repository scale regression that rejects repeated owner-wide or candidate-wide scans.
- [Risk] A composite parent could be mistaken for proof that every detailed child implements every parent failure. → Mitigation: parent and child bindings remain separate; only explicit child member edges propagate a failure below the composite.
- [Risk] A superficially green owner-level native checker may appear reusable for every block. → Mitigation: static checker identities remain block-local and execution stays `not_run` until exact terminal evidence covers the member.
- [Risk] A current source-inventory revision may be mistaken for the current model snapshot because both are fresh strings. → Mitigation: preserve typed fields, require the intent subject and observed subject to equal the model-snapshot fingerprint, and test the mixed-identity counterexample.
- [Risk] The primary logical model may make a partially projected intent look complete while an accepted realized-purpose sibling is omitted. → Mitigation: compare the complete exact accepted relation set with the projected owner set and fail on any missing or foreign owner.
- [Risk] Repeating intent source provenance or coverage payloads on every behavior increases token and storage cost. → Mitigation: store each exact intent pair on the shared owner semantic object and each complete coverage row under its sole shared-object owner; children carry references only.
- [Risk] Existing test fixtures or strict documents use the previous schema. → Mitigation: update all maintained producers and consumers directly and reject residual old documents in current runtime.
- [Risk] New source changes stale the active model authority. → Mitigation: create one new corrective intent contribution, rerun affected model evidence, and atomically activate a fresh revision before installation or release.

## Migration Plan

1. Update the current owner schema, strict loader, self-blueprint producer, readiness compiler, and portable catalog review together.
2. Add point and same-class regressions for valid siblings, different signatures, foreign blocks, missing sibling cases, and duplicate case ids.
3. Calibrate FlowGuard's provider-specific self-adoption behavior/supporting dispositions without shrinking the complete implementation inventory.
4. Remove repeated owner-wide applicability and whole-audit scans, then validate the complete FlowGuard self-blueprint and architecture-reduction review under bounded scale measurements.
5. Correct snapshot identity, accepted realized-purpose projection, and exact intent-source provenance before rebuilding behavior readiness.
6. Recalibrate module/class aggregates, checker execution, and coverage ownership against the clarified block-local rules.
7. Create a new exact intent contribution for the frozen corrective diff, rebuild owner evidence, and activate a new observed model revision.
8. Synchronize maintained distributions only after the new authority and a fresh live self-audit pass.
