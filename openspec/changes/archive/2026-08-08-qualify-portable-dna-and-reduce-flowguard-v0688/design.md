## Context

The v0.68.7 self-audit has a current static blueprint with 51 models, 3,030 behavior blocks, 7,532 implementation surfaces, 37,860 coverage edges, and zero static blueprint gaps. The release result is strong, but the self-maintenance command currently publishes a compact qualification result rather than a complete portable self-blueprint bundle. Model-Test Alignment also reports leaf execution gaps even when parent suites are green, and Architecture Reduction has proofless candidates that must remain retained. The repository has exact currentness and SkillGuard projection rules, so source, model authority, installation, validation, Git, and GitHub release identities must be closed separately.

This change is intentionally not an independent reconstruction project. It makes the DNA exportable and verifiable, improves ordinary read cost, closes evidence ownership, and applies only proof-backed contraction.

## Goals / Non-Goals

**Goals:**

- Materialize one canonical current self-blueprint using the existing content-addressed export/projection authority.
- Separate static readiness, portable export, and execution status without changing the model denominator.
- Let ordinary AI reads consume compact summaries and exact candidate details while preserving explicit full-audit output.
- Bind existing terminal receipts to behavior blocks and coverage edges through explicit coverage sets.
- Keep target modeling provider-neutral and add adapter/conformance checks without Python-only product branches.
- Use ArchitectureReduction and StructureMesh to prove a small, reviewable contraction batch; prioritize the six identical runner wrappers and the repeated strict JSON reader only after rebinding/parity proof.
- Update only the affected FlowGuard skill sources and maintain clean author/shadow/consumer projections.
- Use affected-only development checks, one late identity freeze, one final plan-only, and one final release parent.

**Non-Goals:**

- Do not run, implement, or require an independent software reconstruction experiment.
- Do not add a reconstruction status or alternate reconstruction route to ordinary runtime.
- Do not copy source code into the DNA or create a second DNA/package authority.
- Do not remove candidates solely because they are old, large, similar, expensive, or statically unreferenced.
- Do not introduce compatibility readers, fallback readers, aliases, alternate success paths, or a second model registry.
- Do not require every coverage edge to start its own test process.
- Do not split large modules by byte size alone or break the public flat API in a patch release.

## Decisions

### 1. Reuse the canonical blueprint authority

The existing `implementation_blueprint`, `canonical_blueprint_projection`, `blueprint_compact_projection`, `target_system_blueprint`, and `affected_blueprint_reader` surfaces remain the only blueprint authority. A portable export is a materialized projection of the current observed head, accepted ModelRevisionSet, complete effective intent, provider evidence, and canonical layers. It is not a new model type and it does not become current merely because its manifest exists.

Alternatives considered:

- A new `DNA Package` abstraction: rejected because it would create a second authority and duplicate fingerprints.
- A source-code archive: rejected because DNA describes observable contracts, state, resources, and bindings rather than source text.
- Reconstructing the full behavior graph twice: rejected because it wastes memory and token budget; one immutable observation and content-addressed references are sufficient.

### 2. Use three explicit readiness claims

The existing static result remains the static claim. The new portable claim is based on manifest/shard materialization and isolated verification. Execution remains its own receipt-backed claim. There is deliberately no reconstruction claim in this release.

This prevents `static_readiness_status=ready` from being misread as “the bundle was exported” or “all leaf checks executed.”

### 3. Make compact reads projection-only

Routine self-maintenance and ordinary AI use receive summary counts, fingerprints, blockers, candidate ids, and exact next routes. Candidate detail is loaded by id. Full evidence is explicit. All projections share the same frozen denominator and fingerprints; reducing output bytes must never remove unresolved or `not_run` members.

### 4. Close evidence by coverage ownership, not by test multiplication

One current terminal receipt may cover many behavior blocks when a typed coverage set names every block, case, oracle, and edge. Parent receipts do not become leaf evidence by copying. TestMesh owns execution/freshness and Model-Test Alignment owns the row semantics; neither route chooses architecture reduction or path quality.

### 5. Apply contraction in small proof-backed batches

ArchitectureReduction will first repair caller/consumer classification and then evaluate route/branch/validation candidates, the six identical runner wrappers, the three strict JSON readers, and small pure-helper families. Each batch has one current owner, complete callers and consumers, observable input/output/state/error/side-effect proof, model and test rebinding, and a post-action owner. Public facades, adapters, serialization paths, dynamic entries, and the flat package API remain retained or unresolved unless their proof closes.

### 6. Keep provider neutrality in the core

The export schema carries target-neutral provider payloads. Python/pytest discovery remains one adapter; TypeScript and non-code workflow adapters use the same contract. A missing adapter is a visible provider gap, never a silent Python fallback or synthetic success.

### 7. Edit author sources, then synchronize projections once

The affected `.agents/skills/flowguard*` sources and references are edited under the `unit:flowguard-suite` SkillGuard author boundary. During development, only affected member checks run. After all skill edits are stable, the complete author unit is compiled once, then shadow, consumer, editable package, and parity projections are synchronized.

### 8. Freeze version and release identities late

Implementation, affected validation, and one cleanup pass occur before the 0.68.8 version bump. OpenSpec is verified and archived, final model authority is activated, and installation projections are synchronized before the final plan-only. Because release owners bind the version as toolchain identity, v0.68.7 receipts are not claimed for 0.68.8. One final parent executes the minimum stale owner set.

## Risks / Trade-offs

- [Portable bundle exposes stale or duplicated content] → Build from one frozen current observation, content-address every shard, recompute the bundle identity independently, and verify in an isolated directory.
- [Compact output hides a gap] → Keep the full denominator, unresolved ids, not-run statuses, and claim boundary in the summary envelope; add by-id expansion tests.
- [A parent receipt is incorrectly treated as leaf evidence] → Require explicit coverage sets and current leaf execution owner identities; retain `not_run` visibly.
- [A seemingly unused helper is invoked dynamically] → Classify methods, properties, dunders, runners, registries, manifest references, and string/reflective calls separately; unresolved remains retained.
- [Runner or JSON-reader contraction changes error/output behavior] → Freeze success, malformed, duplicate-key, non-finite, state, side-effect, and exit-code cases before rebinding; delete only after parity evidence.
- [Skill prompt reduction drops a hard gate] → Keep gates and claim boundaries in the author source, run prompt-budget and affected native checks, and compare source/shadow/consumer projections.
- [Parallel AI changes are overwritten] → Inspect status before every write, edit only owned paths, stage explicit paths, and never reset or checkout the worktree.
- [Full validation repeats or leaves descendants] → Use one plan-only, one foreground parent, exact receipt reuse, supervised execution, and process-tree cleanup confirmation.
- [The stale v0.68.7 release pointer is mistaken for a product failure] → Add a lightweight published-identity receipt before v0.68.8; do not rerun product tests for that bookkeeping correction.

## Migration Plan

1. Capture the v0.68.7 source/model/install/release baseline and reconcile the stale local published pointer.
2. Implement the new portable/compact/evidence contracts and affected skill updates under the active change.
3. Run only affected checks while code and models are changing.
4. Run one architecture-reduction cleanup pass and revalidate only its affected closure.
5. Freeze source behavior, update the current version to 0.68.8, verify/sync/archive OpenSpec, activate the final model revision, and synchronize SkillGuard projections and editable installation.
6. Materialize and isolate-verify the final portable self-blueprint.
7. Run the one final full plan-only and parent validation.
8. Bind the candidate, commit, tag, push, publish GitHub v0.68.8, and record tag/published identity receipts.

Rollback is identity-bounded: before the final commit, revert only the owned active change through normal version-control review if focused checks cannot be repaired. After tag/publication, do not move the tag; publish a corrective patch if necessary. Never restore a retired runtime route through a fallback reader or alternate authority.

## Open Questions

None that change the scope or architecture. The user explicitly removed independent reconstruction from this release; any future reconstruction qualification must be a separate change with its own authority and budget.
