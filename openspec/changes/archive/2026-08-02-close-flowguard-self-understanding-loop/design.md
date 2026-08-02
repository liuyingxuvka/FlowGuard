## Context

See `proposal.md` for motivation. The current implementation already has task-coverage demand, model maturation, canonical maturation receipts, process admission, risk, closure, route topology, and a 64-member observed model system. The missing architectural link is not another workflow: it is a single identity-preserving path through those existing owners. Current code also maintains route ownership in more than one registry, represents one owner's evidence twice, uses raw model count as one mesh trigger, and has no read-only combined status projection.

The patch candidate must preserve lightweight consumer use, direct-current identities, existing public-owner boundaries, parallel work in other worktrees, and the distinction between source, observed model authority, installed projection, local Git commit, remote commit, tag, and GitHub release. The user has now authorized the complete patch-release batch, so remote publication follows only after every local domain and the companion blueprint change are current.

## Goals / Non-Goals

**Goals:**

- Make the depth of understanding independently measurable for one exact task and current model-system revision.
- Make whole-FlowGuard self-understanding a finite semantic claim over the current model universe.
- Give AI and humans one read-only answer that separates knowledge, permission, and workflow admission.
- Contract duplicate ownership and evidence representations without creating a new skill or universal hard gate.

**Non-Goals:**

- Modeling target-software domain roles inside FlowGuard itself.
- Requiring full modeling before every user-authorized code change.
- Treating behavior-commitment records as user activity logging.
- Adding compatibility aliases, dual readers, automatic fallback, a UI, or a parallel validation framework.
- Replacing the existing specialist FlowGuard routes.

## Decisions

### 1. Compile task facts independently before asking owners for evidence

Task facts are compiled from four observation planes: the user request, the current authoritative model, externally visible surfaces, and lifecycle/process changes. A caller may add facts or narrow an authorized claim, but cannot silently remove independently observed facts. Each fact carries provenance and an explicit disposition. This is chosen over trusting a caller-populated list because sufficiency cannot be established using a denominator selected by the claimant.

### 2. Generate projections from one canonical public-owner declaration

The existing route-topology module will own the canonical public-owner descriptors. Task-coverage rules, self-maintenance admission profiles, skill identities, documentation checks, and contract checks will be derived projections. A small neutral descriptor type avoids importing the heavier self-maintenance runner into task coverage. This is chosen over runtime reconciliation because drift must fail at build or validation time, not be silently repaired.

### 3. Introduce one immutable owner-resolution value

Each demanded owner returns one identity-bearing resolution containing the task, demand, owner, disposition, obligations, evidence references, and fingerprint. Task-coverage rows and maturation contributions become deterministic views of that value. During the additive phase, old constructors can still be accepted only where existing compatibility is already specified, but the new self-understanding path uses the canonical value exclusively; a separate contraction phase removes redundant fields after parity proof.

### 4. Add a pure status composer, not another validation owner

A small kernel-owned module will compose already-produced task facts, demand, owner resolutions, maturation report/receipt verification, user choice, and process admission. Its Python API accepts values; its CLI accepts explicit JSON artifact paths. It performs no owner execution and writes no receipt. Missing inputs are first-class `not_run` or `unresolved` results. This is chosen over a convenience command that invokes missing checks because a status reader must never create the evidence it is judging.

The public result has three independent axes:

- understanding sufficiency: `not_run`, `unresolved`, `scoped_verified`, `verified`, `stale`, or `blocked`;
- user execution choice: `model_first`, `direct_user_choice`, or `no_code`;
- FlowGuard implementation admission: `not_requested`, `ready`, `ready_scoped`, `no_code_requested`, `stale`, or `blocked`.

### 5. Represent whole-system understanding as a semantic parent mesh

The observed model-system inventory remains the finite universe, but each of its 64 current models receives a semantic disposition, rationale, and required parent/consumer edges. The result is a compact parent mesh and coverage table, not a sixty-fifth monolithic state machine. Raw model count is removed as an activation signal; topology and claim scope determine ModelMesh use.

### 6. Separate design-time tests from execution-time evidence

Model-test alignment records pre-code obligations, oracle definitions, canonical bad cases, and planned evidence before implementation. Execution records are attached only after the corresponding implementation exists and runs against the exact model/maturation identity. This preserves the user's model-first intent without pretending that a planned test has passed.

### 7. Make complete self-understanding strict only where the claim requires it

Ordinary consumers may take a lightweight or explicitly direct path and receive an honest bounded result. FlowGuard's own release self-maintenance task requests the whole-system claim and therefore requires every demanded owner, the semantic mesh, current maturation receipt, independent receipt verification, process admission, risk, and closure. User permission cannot waive identity, safety, or claimed-evidence requirements.

### 8. Use model-derived code boundaries and then contract duplicates

The implementation is split into neutral facts/resolution values, canonical route descriptors, a pure status composer, and thin adapters in existing owners. After conformance is green, ArchitectureReduction and StructureMesh evidence govern removal of duplicated coverage/contribution entry and route-specific Closure scoring, plus the public raw-count activation residue. Observable JSON and supported imports are reviewed explicitly before any removal.

### 9. Treat distribution and repository identities as separate gates

Development occurs in the dedicated branch. Integration happens only after rechecking the formal main worktree and peer changes. SkillGuard freezes affected maintained members and runs their target-owned checks; consumer projection and local package installation are rebuilt from source. Version metadata, documentation, OpenSpec archive state, source tree, observed model revision, installed version, local Git commit, remote commit, tag, and GitHub Release are compared explicitly. No later identity is inferred from an earlier local success.

## Risks / Trade-offs

- **[Risk] Existing callers construct duplicate coverage and maturation values independently** → Add canonical adapters and parity tests first, then remove only proven redundant public fields in the governed contraction phase.
- **[Risk] Central route descriptors create import cycles** → Keep descriptors dependency-light and generate projections into heavier modules; add import and registry parity tests.
- **[Risk] A whole-system semantic table becomes ceremonial** → Require typed relations, rationales, current consumer edges, known-bad gaps, and a receipt bound to the observed model revision.
- **[Risk] Read-only status accidentally launches work or writes evidence** → Make the composer pure, keep CLI file loading separate, and test filesystem and process-owner non-effects.
- **[Risk] Parallel agents change formal main during development** → Re-read identity and dirty state before integration, stage only owned paths, and invalidate affected evidence instead of rolling back peers.
- **[Risk] A deep Windows worktree lets child models pass but prevents the parent evidence object from being stored** → Use the operating system's extended path form for evidence reads and atomic writes and exercise a path longer than the legacy limit.
- **[Risk] Full validation cost causes repeated stale runs** → Use focused and affected checks during implementation, then one frozen final full execution owner after all source and tool identities are fixed.

## Migration Plan

1. Add known-bad tests, task-fact and canonical-resolution models, and the semantic parent-mesh shape before production behavior changes.
2. Move public-owner declarations to one canonical source and make existing registries projections with drift checks.
3. Add the pure status API/CLI and bind it to exact existing artifacts.
4. Materialize the 64-model semantic dispositions, behavior-commitment coverage, model-test alignment, and exact self-understanding receipt chain.
5. Update only affected skill prompts and SkillGuard contracts; rebuild the clean consumer projection.
6. Run behavior-preserving contraction with facade/parity evidence, then update API and documentation inventories.
7. Complete `close-model-implementation-blueprint-loop`, remove fixed-count and caller-summary shortcuts, qualify FlowGuard's own blueprint, and include the new models and consumers in the exact whole-system self-understanding chain.
8. Integrate into the formal main worktree after peer-state recheck, perform affected validation and installation synchronization, freeze all identities, run one final full release gate, archive all verified OpenSpec changes, commit intentionally, push the verified commit, create tag and GitHub Release `0.68.5`, and verify source, observed-model, installation, formal-main, remote, tag, and release identities separately.

Rollback before publication is branch deletion or reverting the isolated commits. After publication, released tags and immutable evidence are never rewritten; a repair uses a new patch release.
