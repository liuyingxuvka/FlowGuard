## Context

FlowGuard already has distinct native owners for external behavior commitments, existing-model discovery, model similarity, model-miss repair, AI workflow rehearsal, development-process freshness, finite bad-case generation, model-test alignment, and large-test evidence. The missing link is a stable identity for *whose promise* a commitment represents. Today `commitment_kind` describes form (`ui`, `cli`, `workflow`, `process`, and similar), `actor` is free text, dependencies are untyped ids, the project ledger is Python-authored, and Existing Model Preflight does not use the task summary to discover commitments.

The repository is also being edited by peer agents. This change therefore needs one new isolated module and narrow additive edits to shared owners, with every shared-file patch based on freshly read content. It must not revert peer work or make stale validation look current.

## Goals / Non-Goals

**Goals:**

- Keep one Behavior Commitment Ledger and partition it by explicit responsibility plane.
- Make same-plane commitment/model recall cheap, deterministic, explainable, and available to Existing Model Preflight.
- Preserve typed cross-plane context without allowing related product/process rows to become AI instructions.
- Make Model Miss backfeed update the same-plane commitment and owner model before creating a gap-backfill row.
- Replace the Python-authored project ledger with one canonical data artifact and reject former ledger shapes at the current boundary.
- Reuse existing AgentWorkflowRehearsal and DevelopmentProcessFlow execution/evidence structures.
- Preserve source, generated SkillGuard contract, shadow install, and installed-skill parity.
- Produce current focused, model-regression, frozen full-suite, former-shape rejection, and OpenSpec receipt-consumption evidence.

**Non-Goals:**

- No new public FlowGuard route, generic AI-operation registry, vector database, runtime action gateway, or second execution engine.
- No universal rule that every trivial AI action must query or execute a FlowGuard model.
- No automatic execution of retrieved commitments; route-native policy and current AI judgment remain authoritative.
- No external publication, Git push/tag, or GitHub release.
- No compatibility reader, converter, upgrade command, alias, or second ledger authority.

## Decisions

### 1. Behavior plane is an orthogonal required field

`BehaviorCommitment` gains `behavior_plane` with production values `product_runtime`, `agent_operation`, and `development_process`. `commitment_kind` remains unchanged and continues to describe the external form. `actor_kind` adds the structured values `end_user`, `external_system`, `application`, `ai_agent`, `developer`, and `automation`; the existing `actor` string remains the display label.

An AI feature implemented inside the product is `product_runtime`; `agent_operation` means the development/maintenance agent acting to complete the current task. `unclassified` is not a current production value and is rejected at the canonical boundary.

Alternative considered: infer ownership from `commitment_kind` or actor text. Rejected because UI, workflow, CLI, process, and AI words occur in more than one responsibility plane.

### 2. Typed relations replace untyped runtime dependencies

Add `BehaviorCommitmentRelation(target_commitment_id, relation_type, rationale)` with `depends_on`, `invokes`, `validates`, `governs`, and `requires_evidence_from`.

- Same-plane: `depends_on`, `invokes`, and `validates`.
- `agent_operation -> product_runtime`: `invokes` and `validates`.
- `development_process -> agent_operation|product_runtime`: `governs`, `validates`, and `requires_evidence_from`.
- Other cross-plane directions are rejected unless a later spec explicitly adds them.

Reverse context is derived by the lookup helper; duplicate inverse rows are not required. Cross-plane rows require a non-empty rationale. Former `dependency_commitment_ids` input is rejected; the source author must write the current typed relation explicitly.

Alternative considered: keep both fields indefinitely. Rejected because two successful relationship authorities would drift.

### 3. One canonical ledger artifact

Add `.flowguard/behavior_commitment_ledger/ledger.json` as the project source of truth. It contains an artifact type, schema/format identity, ledger metadata, source surfaces, commitments, and expected ids. Each commitment carries its plane explicitly. Canonical serialization orders commitments by plane and id for reviewability without creating three independent ledgers.

The existing project `model.py` becomes a thin loader/adaptor, and `run_checks.py` writes only result evidence. The runtime does not execute arbitrary Python to discover ledger data and exposes no converter for former Python or JSON ledger shapes. A project adopts the current template by directly writing current source data.

Alternative considered: three files plus a fourth relation file. Rejected because multi-file authority and partial edits create more freshness states without improving the small-project lookup path.

### 4. Lookup is a small internal module, not a route

Create `flowguard/behavior_commitment_lookup.py` with:

- `BehaviorLookupQuery`: task summary, optional primary plane, canonical terms, changed paths, tool ids, error signatures, and `top_k`.
- `BehaviorCommitmentHit`: commitment id, plane, owner model id, score, match reasons, hit role, and optional relation path.
- `BehaviorLookupReport`: status, selected/ambiguous plane, primary hits, related hits, ledger fingerprint, and blocked reason.

Matching priority is exact id/tool/error/path, then structured lookup bindings, then normalized commitment text. Plane filtering happens before text scoring. Optional AI semantic normalization may provide canonical terms, but the library and CLI remain deterministic and language-neutral. No persisted secondary index is introduced; the ledger is parsed into an in-memory index.

### 5. Existing Model Preflight owns task-time recall

`existing_model_preflight_from_project()` loads and queries the ledger before its current path scan. Exact owner models from primary hits are added first; path discovery supplements them. Preflight records `behavior_lookup_status`, `primary_behavior_plane`, `primary_commitment_hits`, `related_commitment_hits`, `plane_ambiguity`, and `ledger_fingerprint`.

Only primary-plane hits can guide same-plane operation. Related hits are labelled as invoked targets, governing process, validation target, or evidence source. A missing/stale ledger blocks canonical behavior lookup; path inventory may remain visible as a separate diagnostic but cannot become an alternate success path.

Trivial work continues to use the existing preflight skip rule. This is not a new mandatory model run for every action.

### 6. Plane identity constrains similarity and miss backfeed

`ModelSignature` and similarity handoffs gain behavior-plane identity. Same words across different planes are false-friend/manual-review evidence unless a typed BCL relation explains the connection; they cannot create a same-workflow merge recommendation.

Concrete Model Miss records gain affected plane, commitment id, owner model id, and related relation ids. Repair searches the same plane first. An existing row is extended with the observed/same-class case, error signature, owner-model update, and evidence; only an uncovered promise becomes a `coverage_gap_backfill` commitment. Multi-plane incidents have one primary failed promise plus typed related rows.

### 7. Existing process owners remain authoritative

BCL says what is promised and who owns it. Existing Model Preflight recalls it. AgentWorkflowRehearsal continues to own planned AI steps, evidence ids, continue gates, and rework targets. DevelopmentProcessFlow continues to own lifecycle ordering, peer-write invalidation, process-tree safety, installation, and final evidence freshness. No BCL field is copied into every action row; the selected commitment/owner model is the plan-level source, while existing step receipts remain the execution detail.

### 8. Module and public-surface ownership

- `behavior_commitment.py`: plane/actor/relation/lookup-binding schema, ledger loading/serialization, review, and coverage axes.
- `behavior_commitment_lookup.py`: normalization, index construction, scoring, relation traversal, and report types.
- `existing_model_preflight.py`: project/query orchestration and model-hit projection.
- `model_similarity.py`: plane-aware signatures and cross-plane quarantine.
- `recurring_model_miss.py`: concrete miss identity and backfeed inputs.
- `templates.py` and template text: canonical project artifact shape.
- `__init__.py`: public exports inside existing BCL/preflight API groups.
- `__main__.py`: read-only `behavior-commitment-query` command; no new route id.

### 9. Field lifecycle and test boundary

FieldLifecycleMesh accounts every added field and the removed former dependency field. ContractExhaustionMesh declares finite axes for plane, actor kind, relation type/direction, lookup state, and former-shape rejection. Model-Test Alignment binds each required obligation to the public owner contract and its existing native tests. TestMesh stores owner receipts and a read-only parent aggregation; it never copies native test commands. Focused, affected-model, install-parity, and the one frozen full gate remain distinct, and progress is never pass evidence.

### 10. Version and concurrent release ownership

The implementation is designed for the next minor release and global schema review (`0.55.0` / `1.1` were the planning baseline), but the final version edit is single-owner integration work after concurrent changes settle. The change must not overwrite a newer peer version. If the active repository has already advanced, the implementation preserves the newer version and records the feature in that release instead of downgrading it.

## Risks / Trade-offs

- **Risk: plane inference is ambiguous** → Return separated candidates and no primary commitment; allow ordinary scoped work but block broad lookup confidence until the caller selects/reruns.
- **Risk: typed relations reject legitimate future directions** → Keep the first matrix deliberately small and add new semantics through a later spec rather than a generic escape hatch.
- **Risk: a former ledger cannot be read automatically** → Reject it without execution and require direct source rewrite to the one current schema.
- **Risk: canonical JSON and Python adapter become dual authorities** → The adapter only loads JSON; tests reject embedded commitment construction in the canonical template.
- **Risk: peer edits stale validation or conflict with shared modules** → Re-read each shared file immediately before patching, preserve additive peer changes, fingerprint watched artifacts, and rerun affected evidence after the last write.
- **Risk: keyword scoring still produces noisy hits** → Plane-first filtering, exact match priority, explicit match reasons, bounded `top_k`, and typed related traversal keep noise observable.
- **Risk: prompt source and installed copy drift** → Compile from `.skillguard/contract-source.json`, use shadow install/check/parity, then run formal installed-layout parity.
- **Risk: concurrent or timed-out regressions are mistaken for completion** → one explicit owner runs only missing affected checks; timeout cleanup must confirm the whole descendant tree is zero before a receipt can exist.

## Direct Replacement Plan

1. Run project and installed-tool preflight; freeze current ledger and skill fingerprints.
2. Add current schema/review types and explicit former-shape rejection.
3. Add canonical serializer/loader with no former-shape reader.
4. Rewrite the official project ledger directly as `ledger.json`; change `model.py` into a loader; verify current semantic coverage.
5. Add lookup and preflight integration, then similarity and Model Miss identity.
6. Update templates, project models, rules, docs, skills, prompt metadata, and SkillGuard contract sources; regenerate derived contracts.
7. Run focused tests and affected model regressions; repair all failures.
8. Verify component-scoped source/compiled/install projections, then update the formal installed suite transactionally.
9. After source and tool identities freeze, let one owner execute the single final parent TestMesh; OpenSpec only consumes that receipt, then perform a requirement-by-requirement completion audit.

Failure is fail-closed: the current authority remains inactive until direct replacement is complete. There is no automatic rollback that reactivates a former skill/runtime authority.

## Open Questions

None block implementation. Release version ownership is resolved from the repository's newest concurrent state at final integration; it is not guessed up front.
