## Context

See `proposal.md` for motivation. FlowGuard already owns finite behavior models, model hierarchy, external behavior commitments, model-code-test alignment, code-structure recommendations, existing-code partitions, portable finite models, bounded system composition, and one observed model-system authority. The missing denominator is the implementation itself: current source audits inspect caller-declared contracts, StructureMesh consumes caller-supplied partitions, portable schemas intentionally do not serialize Python callables, and the observed model-system coverage is exhaustive only inside its declared manifest and contract universe.

The implementation must preserve the current route topology, the canonical `OwnerCoverageResolution`, the thin Closure consumer, PortableModel/PortableSystem v1 strict wire formats, affected-only ordinary use, and concurrent peer work. The blueprint is derived from the sole observed model-system head and cannot become another authority pointer.

## Goals / Non-Goals

**Goals:**

- Establish an independent, fingerprinted denominator for production code and reconstruction-relevant non-code material.
- Prove bidirectional model-to-implementation and implementation-to-model closure with explicit dispositions.
- Record enough source-independent semantics and oracles for equivalent reconstruction inside a declared boundary.
- Export a deterministic, content-addressed blueprint projection whose authority can always be traced back to current owners.
- Keep static blueprint closure and optional empirical reconstruction evidence as two independent results.
- Make FlowGuard itself the first complete consumer without making whole-repository work the default for ordinary tasks.

**Non-Goals:**

- Reproducing byte-identical source, original file layout, or private helper names.
- Turning every helper into an external CodeContract.
- Storing internal code inventory in the BehaviorCommitmentLedger.
- Adding a `DNA` route, a reconstruction depth mode, a second model-system head, a compatibility reader, or an automatic rebuild command.
- Changing PortableModel or PortableSystem v1 wire semantics in this patch.

## Decisions

### 1. Give independent discovery and blueprint qualification separate internal owners

Add a language-neutral implementation inventory module, a Python AST discovery adapter, and a blueprint qualification/projection module. The inventory owner discovers the denominator and fingerprints it; the blueprint owner consumes that denominator together with exact existing model, contract, portable, resource, and oracle identities. Model-Test Alignment, StructureMesh, and CodeStructureRecommendation consume these reports rather than becoming repository scanners.

This is chosen over expanding `model_test_alignment.py` because CodeContract describes externally meaningful behavior and should not be forced onto every pure helper. It is chosen over expanding StructureMesh because that route intentionally reviews supplied partitions and does not parse source.

### 2. Reuse the project file-manifest authority

Implementation discovery starts from the same exact tracked plus admitted non-ignored file manifest used by current validation ownership. A boundary declares production, build, config, schema, asset, migration, test-oracle, generated, external, and excluded patterns. Every admitted file receives one discovery disposition; unsupported syntax, parse errors, path escapes, dynamic ambiguity, and unmatched files remain blockers.

The Python adapter emits modules, classes, functions, methods, entrypoints, helpers, observed calls, reads, writes, and effect candidates through `ast`. Additional languages may register adapters later, but absence of an adapter is a visible boundary gap rather than permission to ignore files.

### 3. Keep discovery separate from interpretation

Inventory items contain observed path/symbol/structure/fingerprint facts and one explicit implementation disposition: `model_implementation`, `supporting`, `generated`, `external`, `scoped_out`, `dead_retire`, or `unresolved`. Model bindings are separate immutable rows with relation kinds such as implements, supports, calls, adapts, exposes, reads, writes, serializes, migrates, validates, builds, or loads.

Every behavior-bearing entrypoint, state/effect writer, and externally meaningful implementation requires a direct model obligation and owner-contract binding. Pure helpers may use supports/calls edges to a unique owner. This avoids making helpers public contracts while still preventing silent omission.

### 4. Require source-independent semantics in addition to source traceability

A binding that only names a path and symbol is traceability evidence, not reconstruction evidence. Blueprint-required bindings also name semantic specifications and oracles covering input/output shapes, state/effect changes, errors, ordering, retry/timeout behavior when relevant, and algorithmic or decision rules. Complex behavior may point to a current portable model or another source-independent executable specification; otherwise the blueprint remains incomplete.

### 5. Compose existing owners through references, not copied payloads

The blueprint manifest references the exact observed ModelSystemSnapshot, implementation inventory, binding report, portable models/systems, schemas, config, data, assets, migrations, build/runtime definitions, external-service contracts, and test oracles by owner, identity, path, and fingerprint. BCL continues to own external commitments; FieldLifecycleMesh owns field/data lifecycle; UI Flow Structure owns UI semantics and visible assets; TestMesh owns layered evidence. The blueprint only proves their cross-layer closure.

The initial patch does not add a new model-authority coverage dimension because that would invalidate every existing snapshot fixture. Instead, the blueprint is a content-addressed qualification derived from the current observed snapshot. A later schema change may add a typed endpoint only through a separate direct-current revision.

### 6. Keep static and empirical results orthogonal

Blueprint qualification returns:

- static status: `complete`, `incomplete`, `stale`, or `blocked`;
- empirical reconstruction status: `not_run`, `pass`, `fail`, or `blocked`.

Static complete plus empirical not-run is a successful static result whose claim text must say “blueprint complete; reconstruction not verified.” Only an explicit qualification request may require empirical evidence. A user-supplied reconstruction receipt must bind the blueprint fingerprint, isolated environment, source-access policy, covered oracle set, and evidence fingerprint.

### 7. Export a deterministic manifest and content-addressed shards

The explicit export command writes one canonical manifest and canonical UTF-8 JSON shards. Shards contain normalized inventory, bindings, semantic references, resource references, oracles, exclusions, and gaps; source text is excluded unless a separate explicit source-archive requirement exists. Re-exporting the same current inputs produces the same identities. Missing shards, path escape, fingerprint mismatch, or tampering fail closed.

### 8. Preserve lightweight use and one existing kernel route

Task facts trigger the whole-software blueprint path only for an explicit blueprint/export/qualification claim or an owner-declared release obligation. Ordinary changes load the compact blueprint identity and affected neighborhood at most; they do not scan the full repository, materialize every shard, or run reconstruction.

The Python APIs form one cohort under `model_first_function_flow`. The CLI exposes a read-only inventory audit, a read-only blueprint check, and an explicitly writing export. None is a new route or skill, and none invokes an isolated builder.

### 9. Qualify FlowGuard before release

The repository stores one declarative FlowGuard blueprint definition under the authoritative model-system area. Its boundary and disposition rules must account for every current production and reconstruction-relevant file, and its bindings/resources/oracles must close against the current semantic mesh. The current self-understanding fixed-count shortcuts are removed before this qualification. After all related source changes are frozen, one current ModelRevisionSet and one final validation owner cover the combined self-understanding and blueprint release.

### 10. Use the completed self blueprint for a release-time contraction pass

After FlowGuard's own blueprint closes and before the final validation snapshot is frozen, run ExistingModelPreflight, ArchitectureReduction, CodeStructureRecommendation, and StructureMesh over the independently discovered implementation denominator. Declare the public entrypoints, outputs, state, side effects, and validation boundaries that must not change. Every repeated route, branch, adapter, wrapper, facade, helper, and validation path found in scope receives a typed merge, collapse, remove, keep-facade, manual-review, or scoped disposition.

Only candidates with current equivalence or delegating-public-facade proof may be edited. Public entrypoints require StructureMesh parity, and any affected tests or model bindings are refreshed before the final full validation. Property-only, uncertain, stale, or behavior-changing candidates remain visible maintenance obligations. This release pass prevents unbounded growth without turning ArchitectureReduction into an unsafe automatic cleanup command or a universal gate for ordinary work.

## Risks / Trade-offs

- **[Risk] Static classification marks a behavior-bearing helper as merely supporting** → Treat public entrypoints, hidden state/effect writers, unresolved dynamic calls, and unowned side effects as blockers; add known-bad fixtures for each class.
- **[Risk] Full repository discovery is expensive** → Persist content-addressed inventory shards and load only the changed paths plus graph neighborhood during ordinary work; reserve full closure for explicit qualification and release.
- **[Risk] A blueprint duplicates source and becomes stale immediately** → Store semantics and stable references rather than source text, bind every item to content fingerprints, and invalidate only affected shards.
- **[Risk] New types create another authority path** → Derive the manifest from the sole observed snapshot and existing owner receipts; expose no mutable blueprint head.
- **[Risk] Portable v1 metadata is overloaded** → Keep v1 unchanged and reference exact portable fingerprints from the blueprint manifest.
- **[Risk] Concurrent peer writes invalidate evidence** → Re-sample the worktree before each validation phase, preserve peer changes, and rerun only owners whose exact inputs changed.
- **[Risk] Empirical reconstruction becomes a routine cost** → Default to `not_run`; require explicit request and a separate isolated execution owner.
- **[Risk] Release cleanup removes behavior that merely looks duplicated** → Require an observable contract, exact candidate accounting, equivalence or delegating-facade proof, StructureMesh parity for public entrypoints, and affected revalidation; preserve uncertain candidates instead of deleting them.

## Migration Plan

1. Remove fixed-count and caller-summary shortcuts from current self-understanding models while preserving their semantic contracts.
2. Add known-bad models/tests for omitted files, helpers, writers, bindings, semantics, resources, fingerprints, and projection shards.
3. Implement independent inventory and the Python adapter, then freeze FlowGuard's declared boundary.
4. Implement bidirectional bindings, semantic/oracle closure, cross-layer resource references, qualification, and deterministic projection.
5. Extend existing consumers and the kernel-owned API/CLI without changing route topology or Portable v1.
6. Update FlowGuard skills and SkillGuard contracts once, after the final prompt shape is stable.
7. Complete FlowGuard's self blueprint, then run the exact whole-system self-understanding chain and accept one new ModelRevisionSet.
8. Use the completed FlowGuard self blueprint to audit repeated paths, branches, adapters, wrappers, helpers, facades, and validations; safely contract only proof-ready candidates through StructureMesh and revalidate affected owners.
9. Freeze source and tool identities, run the unique full validation owner, rebuild/install the consumer projection and package, sync/archive all verified OpenSpec changes, and publish patch release `0.68.5`.

Rollback before publication restores the prior branch and observed pointer through the existing revision transaction. After publication, any repair uses a later patch release; no released blueprint, receipt, tag, or model authority is rewritten.
