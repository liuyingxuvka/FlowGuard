## Context

See `proposal.md` for motivation. The current implementation already has provider-like implementation and test adapters, a rich model-intent review, model authority, and model-test alignment. The gap is in composition: the project blueprint rejects non-Python targets, owner-level text is projected onto many behaviors, helper ownership can be guessed, placeholder test identifiers can close static coverage, and several readiness booleans do not form one ordered claim chain.

The repository and installed skill suite are shared with other agents. Changes must therefore be direct-current, narrowly staged, affected-first, and release-frozen only after peer writes settle.

## Goals / Non-Goals

**Goals:**

- Put a thin, provider-neutral target-system layer above existing code, test, resource, model, intent, and workflow adapters.
- Make one canonical static blueprint result answer whether a declared target boundary is fully described by current evidence.
- Preserve evidence qualification, static blueprint readiness, and task admission as separate ordered claims.
- Require block-local semantics, exact portable behavior bindings, evidence-bound helper ownership, and real test/case/oracle referential integrity.
- Let ordinary AI work load an affected compact summary while whole-target claims consume whole-target evidence.
- Reuse existing FlowGuard satellite owners and the existing SkillGuard maintenance unit; do not create another public DNA route.
- Let one self-maintenance invocation build the current self-blueprint once and reuse it for architecture-reduction review without weakening freshness or evidence identity.

**Non-Goals:**

- Automatically parse every programming language inside the FlowGuard core.
- Automatically translate a system between languages.
- Rebuild FlowGuard or every consumer project merely to prove static readiness.
- Treat documentation, provider completion, source inspection, or AI confidence as independent semantic or test authority.
- Delete duplicate-looking code without the existing observable-contract and equivalence/delegation gates.

## Decisions

### 1. Add one thin target-system composition layer

Add a core module that owns `TargetSystemDescriptor`, provider result records, `TargetSystemSnapshot`, canonical target-system blueprint compilation, and `BlueprintUnderstandingSummary`.

Providers have only two semantic roles:

- observation providers report what currently exists, such as implementation surfaces, calls, state/effects, tests, resources, traces, and runtime facts;
- authority providers report independently governed intent, model semantics, oracles, portable transitions/properties, and explicit ownership.

Every result is content-addressed and revision-bound. Providers never emit `ready`; the compiler cross-checks their results and produces readiness. Existing Python AST and pytest discovery become software observation providers. Declared workflow fixtures exercise the same core without a source-language field.

Alternative considered: add more language branches to the existing project builder. Rejected because it would keep programming language as the core ontology and would not support workflows or mixed systems cleanly.

### 2. Keep one ordered readiness chain and one side claim

The canonical dependency is:

```text
EvidenceQualification -> StaticBlueprintReadiness -> TaskAdmission
```

Lower-layer success remains visible when a higher layer fails. Project and self-blueprint `ok` results consume static readiness rather than inventory qualification alone. Task admission may accept a fully evidenced affected scope while forbidding a whole-target claim.

Independent reproduction, clean-room implementation, or language migration is outside the ordinary blueprint lifecycle. Such work is admitted only by a separate explicit request and uses its own specialist evidence surface; it is not a default blueprint layer, summary field, readiness state, release gate, or routine status line.

Alternative considered: collapse all statuses into one boolean. Rejected because it would either block legitimate lightweight work or falsely license broad DNA claims.

### 3. Compile behavior only from exact declarations and current relations

The compiler consumes a declared behavior contract per behavior block. A block identifies exact implementation surfaces; source-independent semantic rules with per-surface applicability; portable model, transition, property, field, assumption, and guarantee bindings; protected failures; and applicable or typed-not-applicable dimensions.

Shared semantic rules are normalized once but carry explicit applicability rows. Identical generic owner prose copied across blocks without such rows is rejected. Candidate discovery may propose rows but cannot mark them accepted.

Supporting ownership edges carry relation kind, observed or declared evidence identity, and fingerprint. The lexical `min(...)` fallback is removed. No edge or ambiguous edges remain gaps.

Alternative considered: keep owner-wide templates for convenience. Rejected for readiness because they cannot distinguish functions with different input, state, error, and completion behavior.

### 4. Split formal coverage from execution evidence

Replace placeholder-capable mixed coverage with:

- concrete behavior case contracts containing good, bad, and boundary inputs/states, expected outputs/states/effects/errors, oracle identity, and protected-failure references;
- formal static-design edges referencing owner-declared accepted checker members, their current test-node or native-check owner, real cases, behavior blocks, surfaces, semantic rules, oracles, and exactly one covered dimension;
- execution evidence referencing the formal edge and an immutable current receipt, or an explicit `not_run`, `blocked`, `pass`, or `fail` disposition.

The reviewer receives the current test/oracle/case/checker inventories and verifies referential integrity. Generated cases, generated checker identities, unaccepted checker designs, or designs with no current test/native owner remain gaps. An accepted static checker design may remain `not_run`; that closes only design, never receipt-backed execution. Registered delegated assertion helpers are allowed only when their current call path reaches terminal assertion/native members and has no cycle.

Alternative considered: retain generated `contract-test-design` ids as formal coverage. Rejected because those ids can make a graph look complete without any test implementation.

### 5. Reuse canonical intent and resource authorities

The blueprint consumes the existing rich `ModelIntentReview` and its exact contributions/dispositions. A small projection binds each admitted contribution to exact current-realization or future-target behaviors; blanket binding to every target is rejected. Simplified project intent types no longer own readiness.

Resource readiness preserves the existing complete resource reference, including owner, artifact, fingerprint, source-independent semantics, purpose, and lifecycle role. Category disposition is added beside that object rather than copying it into a weaker type.

Alternative considered: synchronize two intent and two resource schemas. Rejected because freshness and semantic fields are already being lost during conversion.

### 6. Make compact understanding a projection, not another authority

`BlueprintUnderstandingSummary` contains the target/revision/blueprint fingerprints, affected or whole scope, layer statuses, deepest proven layer, first gap, total gap count, affected surfaces, and provider identities. It is deterministically projected from the canonical blueprint result and never scans, runs providers, or recalculates readiness.

The existing understanding-status route consumes this summary. It preserves user execution choice, verified sufficiency, and implementation admission as separate fields. Whole-target claims require a whole summary; lightweight work consumes an affected summary.

Alternative considered: add a standalone DNA skill or readiness route. Rejected because it would duplicate the existing FlowGuard entry and create another owner.

### 7. Broaden reduction discovery while retaining the proof gate

Self-reduction candidate discovery adds command routes, branches, adapters, wrappers, facades, helpers, validation paths, and repeated structural intent to the existing oversized/repeated-structure signals. Every candidate records observable contract, proof state, target action, primary owner, callers, and required next route. Only evidence-ready candidates may contract; all others remain visible.

Alternative considered: automatically consolidate by similarity score. Rejected because similar paths can have different public contracts, lifecycles, or evidence owners.

### 8. Reuse one exact self-blueprint and one caller index when composed review is selected

The explicitly selected composed self-maintenance invocation builds one immutable `FlowGuardSelfBlueprintBundle` and passes that exact object to architecture-reduction review. The reduction reviewer records the consumed blueprint, implementation-inventory, and behavior-report fingerprints. A source, test, resource, model, or intent change produces a different bundle and therefore cannot silently reuse an older result.

Candidate caller discovery builds one reverse call-alias index from the current required surfaces. Each required surface contributes its exact call names once; each candidate member then resolves callers from that index. This replaces the previous member-by-all-surfaces nested scan while preserving the same caller identity set and candidate fingerprints.

Nested shard-safety proof directories use a short deterministic hash instead of repeating the full model id below a user-selected evidence directory. The immutable receipt remains the readable identity authority: it stores the complete model id, input fingerprints, run ids, paths, results, and proof fingerprint. This prevents Windows path overflow without weakening traceability or introducing an alias authority.

The existing standalone commands remain available for lightweight independent use. The self-blueprint command gains an explicit composed-review option for workflows that require both results; it builds once and returns both bounded reports. No global cache, fallback reader, or serialized stale bundle is introduced.

Alternative considered: persist a transparent long-lived blueprint cache. Rejected because cache currentness would become a second authority and a stale cache could license a false cleanup claim.

Compact output is a direct projection, not post-processing over a fully expanded payload. The composed command reads only the bounded fields it emits; it never calls complete blueprint or reduction serialization before discarding most of the result. Full-detail serialization remains an explicit non-compact choice.

The immutable behavior report also memoizes its canonical fingerprint after the first calculation. This is invocation-local object state only: the fingerprint payload is unchanged, no serialized cache is written, and every downstream consumer receives the same exact value.

### 9. Direct-current migration and release

The Python-only project definition field is replaced by `target_kind` and exact provider identities. No compatibility alias or fallback reader is retained. Public exports, CLI request schemas, fixtures, docs, FlowGuard models, and affected skill prompts move together.

Implementation proceeds affected-first. After source and model changes stabilize, the FlowGuard model revision set is accepted once, affected tests and model regressions run, the canonical self-blueprint and self-reduction audit are checked, SkillGuard refreshes only the current maintained unit and global router from the complete explicit registry, source/install/shadow parity is restored, and one frozen foreground full validation gates the patch commit, tag, push, and GitHub Release.

## Risks / Trade-offs

- **[Risk] Existing self-blueprint data is too coarse to become immediately static-ready** -> Make gaps honest, then supply current block-local declarations and real bindings for the release-owned boundary; do not restore synthetic closure.
- **[Risk] Exact per-behavior data increases model size and token cost** -> Normalize shared semantic/case/oracle objects, shard by owner and behavior, and expose affected compact summaries.
- **[Risk] Provider-neutral types become an abstract duplicate of existing inventories** -> Keep the new layer thin: it references canonical inventories and provider identities rather than copying their members.
- **[Risk] Direct-current field replacement breaks old fixtures or scripts** -> Update every repository caller, test, CLI fixture, model, and installed projection in the same release; reject old shapes visibly.
- **[Risk] Broader reduction discovery creates many false positives** -> Candidates remain non-authoritative and require current equivalence/delegation evidence before any contraction.
- **[Risk] Caller discovery becomes quadratic on a large self-blueprint** -> Build one deterministic reverse call index and compare its result with the prior exact caller semantics in focused fixtures.
- **[Risk] Reused self-blueprint evidence becomes stale** -> Reuse only the exact in-memory bundle inside one invocation and bind every reduction result to its current fingerprints; never fall back to a prior serialized result.
- **[Risk] Compact output expands a multi-gigabyte full graph before discarding it** -> Project compact fields directly and protect the path with tests that fail if complete blueprint or reduction serialization is invoked.
- **[Risk] Multiple consumers repeatedly fingerprint the same large immutable behavior report** -> Cache the canonical fingerprint on that immutable object and prove repeated reads call the payload hasher once.
- **[Risk] Normalization retains several complete canonical JSON copies while computing fingerprints and sizes** -> Stream exact canonical chunks into one digest and byte counter, release the logical payload before constructing the physical projection, and prove the streaming path never calls full JSON materialization.
- **[Risk] Readable release evidence roots overflow Windows paths when shard proofs add nested model and child names** -> Keep the user-visible evidence root and receipt identity, but derive bounded internal proof directories from the exact model id hash.
- **[Risk] Parallel agent changes stale evidence or overlap edits** -> Re-read before each patch, stage only reviewed paths, preserve peer writes, and freeze the unique final gate only after the consumed tree is stable.
- **[Risk] Final validation is expensive** -> Run narrow affected checks during implementation and exactly one foreground full parent after freeze; never use background resume as a shortcut.

## Migration Plan

1. Introduce current target-system/provider records and tests for declared workflow, non-Python, mixed-provider, missing-provider, and stale-provider cases.
2. Replace Python-only project definition and compose existing software inventories through the new layer.
3. Tighten behavior, portable, helper, case, oracle, and real-test referential integrity; remove synthetic closure and lexical ownership fallback.
4. Connect canonical intent/resources and compact understanding projection; update self-blueprint and CLI.
5. Broaden self-reduction candidate discovery and review results without automatically deleting unresolved candidates.
6. Replace repeated caller scans with one deterministic reverse index and add the explicit build-once composed self-maintenance invocation.
7. Update current model authority, prompts, protocols, public API/docs, and all affected tests and fixtures.
8. Run affected validation and self-audit; compare standalone and composed results and fix every current failure or report an exact blocker.
9. Refresh source/install/shadow/SkillGuard identities, freeze and run the unique full gate, archive the OpenSpec change, commit, tag, push, publish the patch release, and verify each identity independently.

Rollback before publication is file-scoped reversal of only this change's owned paths. After publication, correction uses a new patch release; published authority is never rewritten. Parallel peer changes are never rolled back as part of either strategy.
