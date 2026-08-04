## Context

See `proposal.md` for motivation and the delta specs for observable behavior. FlowGuard v0.68.5 already owns an independent repository inventory, a Python AST implementation adapter, model-implementation binding review, deterministic blueprint projection, separate static and empirical statuses, WorkContext adapters, ModelRevisionSet activation, Model-Test Alignment, TestMesh, ArchitectureReduction, and a FlowGuard self-blueprint command.

The remaining defect is compositional. `self_blueprint.py` currently discovers code, creates one synthetic model element per discovered surface, derives the semantic payload from that same surface, chooses an owner with a broad fallback, and attaches one owner-level native oracle to many unrelated surfaces. This can make a self-generated graph look closed without proving that its semantics and tests were independently declared. The same composition is also FlowGuard-specific, so another Python project cannot obtain the same honest depth report through one supported builder.

The design must preserve the single observed model authority, strict current schemas, project-bounded read-only WorkContext, affected-only ordinary work, exact evidence identity, SkillGuard's author/consumer separation, and the rule that no blueprint operation launches reconstruction automatically.

## Goals / Non-Goals

**Goals:**

- Make one project-neutral Python blueprint composition path usable by FlowGuard and another bounded project.
- Turn code-derived facts into observation evidence, never self-authenticating intended semantics.
- Report independently useful qualification layers instead of one opaque green status.
- Connect model intent, implementation surfaces, exact tests, resources, oracles, and current evidence without creating another authority registry.
- Make FlowGuard self-host the generic path and safely contract only proof-ready duplicate architecture.

**Non-Goals:**

- Clean-room reconstruction, byte-identical source reproduction, source-text packaging, or an automatic reconstruction runner.
- Supporting non-Python deep discovery in this patch.
- Inventing target-product people, roles, permissions, or workflows inside FlowGuard's BehaviorCommitmentLedger.
- Adding a `flowguard-dna` skill, depth-selection mode, compatibility reader, second model head, or alternate success path.
- Requiring a whole-repository blueprint scan for ordinary bounded maintenance.

## Decisions

### 1. Add one generic composition module and keep self-blueprint as a preset

Add `flowguard/project_blueprint.py` with strict project-definition, evidence-input, layer-status, bundle, load, build, and audit types. The builder will reuse `SoftwareBoundary`, implementation inventory/adapters, binding review, blueprint manifest, qualification, and projection owners. It will not duplicate their validation logic.

`flowguard/self_blueprint.py` will retain only FlowGuard-specific declaration loading, file categories, model-owner mappings, current snapshot/semantic-mesh identities, resource groups, and native evidence lookup. It will translate those inputs into the project-neutral builder. No generic code will import the self preset.

Alternative rejected: generalize the self function in place. That would leave FlowGuard-specific manifest assumptions inside the generic path and make external use dependent on the repository's 65 model-regression owners.

### 2. Qualify a finite ladder of independent layers

Extend blueprint qualification with these ordered static layers:

1. `inventory`: every admitted file/surface has a current terminal disposition and a supported adapter;
2. `traceability`: required models and behavior-bearing code are bidirectionally bound;
3. `independent_semantics`: every required dimension is supplied by a declared/imported model artifact, not by the production-source observation that it explains;
4. `model_code_test`: every required model/contract surface has exact test source/node/assertion bindings and current structural identities;
5. `resource_oracle`: every required build/runtime/data/config/schema/asset/migration/service/oracle reference is current;
6. `static_blueprint`: the join of the five layers;
7. `empirical_reconstruction`: an orthogonal optional receipt state.

The result records each layer's status, finding ids, owners, evidence subjects, and deepest proven layer. `static_status` remains for compatibility with existing internal consumers but is derived from the layer table and cannot hide a failed layer.

Alternative rejected: a single `deep=true` flag. A flag would hide why the system is incomplete and would recreate the self-rated depth problem.

### 3. Give semantic references explicit provenance authority

Extend `SemanticSpecReference` with an exact source class (`declared_behavior`, `imported_model`, or `observed_candidate`), provenance ids/fingerprints, and source-independence decision. Existing FlowGuard model-purpose closures, semantic mesh nodes, portable models, and declared CodeContracts can supply declared/imported semantics. AST-derived parameter, call, write, effect, return, and error facts are `observed_candidate` only.

Binding review may use observed candidates for inventory and traceability, but independent-semantic closure requires every necessary dimension to be covered by at least one current declared/imported reference. Order, retry, timeout, idempotency, and recovery are explicit dimensions or explicit `not_applicable` decisions; silence is not closure.

Alternative rejected: compare semantic text against code text. Textual difference does not establish independent origin or correctness.

### 4. Use stable owner obligations instead of one synthetic model per function

The FlowGuard preset will derive real owner obligations from the current model-regression manifest and semantic model mesh. Implementation surfaces will bind to those stable owner obligations. Behavior-bearing surfaces may be primary implementations only when the owner mapping is exact; ordinary internal helpers use `supports`/`calls` with `primary=false` and one unique owner.

Owner selection will prefer exact declared model inputs and explicit overrides. Unknown or multiply owned behavior-bearing surfaces become unresolved. There is no fallback to `authoritative_model_system`. Owner semantics and oracle payloads are stored once per owner; surface bindings reference them, reducing repeated projection content and token cost.

Alternative rejected: keep per-surface model elements and only rename them. That would retain circular authority and projection bloat.

### 5. Add a project test inventory and bind tests without promoting a parent suite

Add `flowguard/test_inventory.py` and `flowguard/test_inventory_python.py`. Python discovery records test files, classes/functions, pytest node ids, parameterization markers, calls, assertion count/kinds/targets, source and structure fingerprints, and explicit disposition. Collection/execution identities and immutable receipts remain separate fields.

Project blueprint input maps stable model obligations and owner CodeContracts to exact test nodes or a bounded native model checker when that owner has no declared pytest node. Test nodes are re-discovered from the embedded inventory; native checkers are re-hashed from their exact project paths. Model-Test Alignment consumes those rows and reports source-audit, assertion-quality, and evidence freshness gaps. TestMesh continues to own large execution partitions and parent receipts. A broad full-suite pass is aggregate evidence and never fabricates missing child bindings.

For the self preset, test paths come from exact model-owner input manifests, then test-node discovery refines them. Ambiguous tests remain orphaned until explicitly mapped. The checked-in self definition may declare narrow overrides; it may not use one global fallback.

Alternative rejected: parse the final pytest log to infer test ownership. Execution order and filenames are not semantic obligation bindings.

### 6. Model intent contributions outside WorkContext authority and consume them in revisions

Add `flowguard/model_intent.py` with immutable `ModelIntentContribution`, conflict finding/report, and WorkContext projection helpers. Contributions preserve source kind/ref/fingerprint, subject lane/role, lifecycle state, supersession, model target ids, effective revision, and rationale. WorkContext only reads and fingerprints inputs; it never accepts a model change.

Extend `ModelRevisionSet` with a strict contribution-disposition inventory and conflict ids. Accepted contributions must connect to changed model ids or one explicit scoped gap; superseded/rejected/deferred rows remain traceable; conflicting/unresolved rows block acceptance. ModelRevisionSet remains the sole atomic candidate decision and the existing activation transaction remains the sole observed-head update.

Alternative rejected: introduce a permanent ideal-model registry. That would create a second authority and force current/future divergence to be reconciled outside ModelRevisionSet.

### 7. Expose generic API and read-only CLI surfaces

Register project blueprint/test inventory types and builders in the existing kernel API cohort and package exports. Add a read-only `project-blueprint-audit` command that consumes a project definition and returns layer/depth/gap output. Existing artifact-based check/export commands remain. `flowguard-self-blueprint-check` becomes a preset invocation of the same builder.

The generic audit may materialize data in memory only. It never changes the target project, writes a projection, installs anything, activates a model, starts missing validators, or launches reconstruction. Unsupported languages and missing declarations fail visibly.

Alternative rejected: a separate DNA CLI group or plugin, because it would duplicate route ownership and confuse capability with an execution mode.

### 8. Keep ordinary work compact and make full qualification explicit

The builder always supports an explicit full audit. Ordinary FlowGuard routing consumes only the current compact blueprint identity plus `AffectedBlueprintNeighborhood`; it does not re-enumerate the repository. Content-addressed owner, inventory, test, binding, resource, and projection identities allow exact affected invalidation.

Skills will tell AI to report layer status and gaps, but prompts will not claim the capability until APIs and executable tests pass. User permission, verified model sufficiency, and DevelopmentProcessFlow implementation admission remain three separate values.

### 9. Self-audit contraction is evidence gated, not automatic cleanup

After FlowGuard self-qualification is current, derive a finite reduction candidate inventory from exact same-intent/model/code/test relationships. ArchitectureReduction classifies each candidate. Only `safe_by_equivalence` and current `safe_by_public_facade` actions may be implemented. Public entrypoints and structural moves require StructureMesh parity. Other candidates become typed maintenance obligations.

The likely first contraction is removal of self-only assembly duplication after the generic builder owns it. Broader handler/helper deletions are allowed only when the current model and tests prove them; the release is not required to delete a quota of code.

### 10. Release only after all authority domains are frozen separately

The release order is: strict OpenSpec planning; code/models/tests; affected checks; self-blueprint qualification; architecture-reduction review and any safe contractions; affected revalidation; skill-source validation under SkillGuard; consumer-authority compilation; package and consumer installation parity; version/docs; archive verified OpenSpec changes; freeze source/toolchain/owner plan; one final full model/test gate; local release verification; commit/tag/push; zero-asset GitHub Release; published verification.

Focused checks may run concurrently only on frozen independent inputs. The final full gate has one owner and runs after the worktree is read-only. A timeout or interruption blocks reuse until the entire descendant process tree is confirmed gone.

## Risks / Trade-offs

- **[Risk] Honest independence makes the current self-blueprint incomplete initially** → Add explicit model-purpose/semantic-mesh/test-owner mappings and expose unresolved rows; never restore a broad fallback merely to regain green.
- **[Risk] Owner-level semantics become too coarse for a complex surface** → Allow a surface binding to reference a narrower declared/portable semantic artifact and keep missing dimensions blocked.
- **[Risk] Test discovery mistakes a call for an assertion** → Store calls and assertions separately; Model-Test Alignment accepts only oracle-bearing external/mixed assertions for the claimed contract.
- **[Risk] Strict new ModelRevisionSet fields stale stored revision artifacts** → Update the current producer, fixtures, executable model, serializers, and authority snapshot in one direct-current revision; do not add an old-schema reader.
- **[Risk] Full self-audit is slow or token-heavy** → Deduplicate owner semantic/oracle records, shard by owner/model neighborhood, and keep ordinary routing on compact identities.
- **[Risk] Parallel work changes a consumed input** → Re-sample Git and fingerprints before each phase, preserve the peer write, invalidate only mapped consumers, and never roll back to an older green state.
- **[Risk] Release cleanup expands scope** → Apply only exact proof-ready candidates; preserving a typed uncertain candidate is an acceptable release result.
- **[Risk] External users assume all languages are supported** → State Python-only deep discovery in API/CLI/docs and block every required unsupported source language.

## Migration Plan

1. Add failing tests for circular semantics, broad owner fallback, helper-primary ownership, missing exact tests, broad-parent substitution, intent conflict/supersession, unsupported language, and automatic reconstruction.
2. Add current intent-contribution and test-inventory schemas and their strict readers/reviewers.
3. Extend blueprint semantic provenance, binding test references, manifest identities, and layered qualification; update all current serializers and fixtures directly.
4. Add the generic project builder and external fixture; convert FlowGuard self-blueprint into a thin preset with stable owner-level semantics, exact code/test mappings, and no broad fallback.
5. Add API/CLI registration, executable FlowGuard models, regression ownership, documentation, and affected skill guidance.
6. Run current self-qualification, create the finite reduction review, apply only proof-ready contractions, and rerun affected checks.
7. Update the sole observed model-system revision through the existing revision transaction after all affected child evidence is current.
8. Synchronize clean consumer projections and package/install identities, freeze and run one final gate, then publish the next patch version.

Before publication, rollback is ordinary source/model reversal through the same current schemas and activation contract. After publication, any correction uses a later immutable patch tag and Release; the published tag, receipts, blueprint, and authority head are never rewritten.
