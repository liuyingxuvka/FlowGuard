## Context

See `proposal.md` for motivation. The current composed review already intends to build one self blueprint, but source discovery and authority capture are repeated, the final currentness requirement contradicts that intent, ambiguous aliases expand caller-by-candidate rows, and full result serialization is still the release default.

## Goals / Non-Goals

**Goals:**

- Keep every current semantic, denominator, candidate, proof, retain, freshness, and readiness check.
- Make each expensive observation and complete identity object single-owned inside one invocation.
- Keep a final independent currentness boundary without creating a second result authority.
- Make complexity regressions structural and deterministic instead of relying mainly on wall-clock thresholds.

**Non-Goals:**

- Reduce the number of modeled behavior blocks or test obligations.
- Introduce persistent caches, stale receipts, compatibility readers, or fallback identities.
- Contract code merely because the audit becomes faster.

## Decisions

### Reuse immutable observations, not validation results

The implementation provider will create one typed invocation-local observation bundle containing the exact discovered surfaces and provider identity. Declaration classification and the implementation inventory will consume the same facts but independently enforce disposition, ownership, completeness, duplicate, parse-failure, and boundary rules. This preserves independent judgment without parsing identical source twice.

### Builder identity is the before-side of the currentness comparator

The self-blueprint bundle will carry the exact build-input identity associated with the authority, definition, boundary, file inventory, semantic mesh, and provider contracts it consumed. A composed review will not perform a separate pre-capture. Immediately before publication it will perform one fresh capture and compare exact identities. This leaves one build plus one time-of-check/time-of-use comparison.

### Full review identity is component-based and stored

The complete review fingerprint will be computed once from stable component identities and terminal status fields and stored on the frozen review. Complete `to_dict()` output may still exist for an explicit diagnostic caller, but it will not reconstruct the identity payload twice. Compact publication must read the stored review fingerprint and compute a separate projection fingerprint.

### Immutable identities and lookup evidence are invocation-local singletons

Large frozen inventories, binding reports, manifests, alignment reports, topology reports, intent inventories, and target reports will compute their canonical fingerprint once per object. Model-test blocker findings will be indexed once by obligation, code contract, and test evidence before binding rows are produced. Affected-blueprint materialization will still independently fingerprint every supplied base object and compare it with the declared projection, but it will reuse that computed value for the final index and compute each newly materialized object identity once. None of these values persists across invocations or replaces a freshness check.

### Candidate review uses exact indexes, not repeated full scans

Candidate construction will freeze the current manifest, behavior, implementation, and test identities before iteration. Contract-member membership, ready-candidate membership, and conflicting target actions will use exact sets or maps constructed once. The candidate inventory, blocker set, action disposition, and release decision remain byte-for-byte governed by the same facts.

### Statically finite dynamic selectors materialize from the current observation

The Python provider already records an exact selector domain when an operation such as `getattr`, `setattr`, or a mapping lookup is driven by a statically finite value set. The self-blueprint provider will turn that observed finite domain into one exact-current `DynamicSelectorContract` bound to the surface, effective owner, structure fingerprint, selector-source fingerprint, values, and operation. It will not require a second hand-maintained copy in the authored definition and it will replace a mechanically stale generated projection with the current observation. Truly open selectors remain blocking unless the implementation is made finite or an explicit exact allowance states the bounded reason; an allowance is not a fallback for a selector whose finite domain can be proved.

### Behavior ownership, check ownership, and receipts stay separate

`ProjectTestNodeDisposition.owner_ids` describes exact behavior-coverage ownership. `CoverageExecutionEvidence.execution_owner_id` describes the native process that would execute one or more planned checks. A non-empty passing receipt proves a completed execution; it does not create the owner itself. Required ordinary tests may correctly remain `supporting` with no exact behavior owner while their own source identity remains in the independent test denominator.

The self-reduction universe will therefore keep each required test node once, keep each unique native execution owner once with an exact aggregate design fingerprint, and preserve terminal receipt evidence separately when it exists. It will not turn a legal supporting test into a missing-execution-owner gap, infer behavior ownership from broad model test-file globs, or replicate every behavior coverage edge as a second `check-design-owner` member.

### Shared evidence neighborhoods are normalized, not repeated per candidate

Coverage-derived observable-contract fields can be identical across many candidates that belong to the same behavior neighborhood. The current representation copies test ids, coverage ids, covered dimensions, and current receipt ids into every candidate, so canonical inventory and review identities scale with candidates multiplied by shared evidence. The direct-current self-reduction schema will instead publish one content-addressed evidence-neighborhood catalog. Each candidate carries exactly one neighborhood id and fingerprint; the full observable contract is resolved by combining that catalog row with the candidate-local caller, behavior, model, owner, state, effect, and error fields. The canonical observable-contract identity becomes a typed composite of the inline semantic fields plus the content-addressed neighborhood fingerprint, so hashing is linear in the physical normalized representation. Proof execution still resolves and validates the complete tests, coverage, dimensions, and receipts before it can publish evidence.

No inline copy, compatibility reader, missing-reference fallback, or second catalog authority is allowed. Unknown ids, duplicate ids, stale fingerprints, catalog rows outside the exact candidate inventory, and any resolved-contract fingerprint mismatch block review or proof consumption. This changes the physical review schema and its fingerprints while preserving the logical candidate, test, coverage, proof, and denominator facts.

### Aggregate shared ambiguity, retain exact sets

Caller ambiguity will be keyed by raw alias. Each record carries sorted exact caller and candidate surface sets; affected members reference the shared record. The blocker stays unchanged. Retain dispositions may likewise group members only when every authority, evidence, rationale, and currentness field is identical, with exact-cover validation after grouping.

### Current necessity is semantic evidence, not a structural identity

Every implementation surface that is retained will carry one direct-current necessity witness. The witness binds the exact current intent authority, one behavior/model/code owner, source-independent semantic specifications, current callers or external behavior commitment, and model-code-test evidence. The audit loads and reviews the BCL once, and an external commitment enters a witness only when that one current review binds the exact primary model, the same current blueprint owner contract, and current test evidence. Candidate ids, paths, symbols, owner ids, model ids, semantic-spec ids, oracle ids, test ids, and receipt ids remain provenance and currentness evidence; they do not enter the semantic-obligation fingerprint and therefore cannot manufacture a false semantic difference.

A public role is discovery metadata, not proof that a public promise remains current. A public surface with neither a current consumer nor an active reviewed Behavior Commitment Ledger promise remains unresolved. A multi-member candidate is retained as independently necessary only when every member has a complete witness and every normalized current semantic obligation is pairwise different. If any obligations repeat, including a partially repeated three-member group, the whole group remains unresolved for splitting or contraction proof.

Historical-looking words such as `legacy`, `compat`, `fallback`, or `alias` remain useful discovery signals, but one isolated name is not a reduction candidate. A candidate is materialized only when two or more current surfaces have an exact shared call or structure relation. This prevents a naming convention from creating a fake cleanup workload while preserving real related historical paths for review.

### Persistent proof authority reuses the canonical receipt store

The read-only audit will discover exact-current self-reduction proof records from the canonical aggregate validation-owner receipt store. It will reconstruct the strict typed proof record from the receipt's evidence context, ignore stale historical receipts as history, and block duplicate exact-current authorities. It will not accept caller-supplied proof records or create a second proof registry.

The proof producer will freeze the current bundle and candidate inventory once, select a finite candidate subset by exact id and fingerprint, reuse an exact-current aggregate receipt before execution, and otherwise execute the selected proofs under one batch owner. Each proof keeps a deterministic candidate-bound identity and the batch writes one aggregate authority. Audit remains read-only; proof execution remains an explicit separate action.

### Release uses complete compute and compact publication

The release-suite child command will add compact output after the stored full-review identity contract is implemented and tested. The validation receipt remains about the complete review; compact JSON is only its bounded terminal projection.

Compact publication must still be actionable. It will count blocker findings by exact child report, code, and severity and include one bounded example for each emitted blocker kind. This prevents an aggregate five-layer gap from hiding hundreds of same-root-cause findings and avoids a second complete blueprint build merely to learn the child finding code.

### Supporting oracle code is traceability, not self-certifying behavior

A test runner or oracle implementation remains in the implementation denominator and delegates to its exact behavior owner as a supporting surface. When that supporting surface is also the physical source of the owner's oracle, the inherited oracle reference records the delegation but does not claim that the runner independently certifies its own behavior. Independent semantic and oracle source checks remain mandatory for every direct `implements` binding; the exception is restricted to typed `supports` bindings and cannot promote the runner into an independent behavior block.

### Separate audit completion from cleanup authority

The self-reduction result will expose three different conclusions instead of deriving all of them from one boolean. `audit_complete` means that the current source, qualified blueprint, independent candidate denominator, and every disposition were completely reviewed. Candidate action authorization remains candidate-local and requires current independent proof. `cleanup_release_ready` is the stronger closure claim and requires a complete audit with no unresolved candidate and no authorized-but-unapplied action. A proofless candidate therefore remains visible as unresolved risky keep without making a complete read-only audit fail; a proof-authorized action that is still pending continues to block release self-maintenance.

## Risks / Trade-offs

- [Risk] Observation reuse could accidentally make one consumer trust another consumer's classification. → Mitigation: share only raw immutable provider facts; keep separate rule execution, findings, and result fingerprints.
- [Risk] Component identity could omit a complete-review fact. → Mitigation: enumerate every governed component identity in the review schema and add mutation tests for each component.
- [Risk] Ambiguity aggregation could hide one caller. → Mitigation: exact caller/candidate set assertions and affected-member reverse references are required before publication.
- [Risk] Compact output could be mistaken for a shallow audit. → Mitigation: receipts bind the stored full-review fingerprint and tests assert that all full review producers execute.
- [Risk] Fingerprint caching could hide mutation. → Mitigation: only frozen invocation-local objects are cached; affected supplied payloads are independently hashed before their actual result is reused, and final governed-input currentness remains a fresh observation.
- [Risk] A candidate reference could detach evidence from its observable contract. → Mitigation: content-address every catalog row, require exact one-time catalog membership, resolve the complete contract before proof use, and compare the resolved semantic fingerprint with the candidate binding.
- [Risk] A passing audit could be mistaken for permission to delete or merge code. → Mitigation: publish audit completion, per-candidate action authorization, and cleanup readiness as separate fields and test every cross-product boundary.
- [Risk] Different structure ids could be mistaken for different product behavior. → Mitigation: compare only normalized source-independent semantic content and require one complete current necessity witness per retained implementation member.
- [Risk] Proof receipts could become a hidden second registry or stale authority. → Mitigation: use only the canonical aggregate owner store, reconstruct strict records from exact evidence context, reuse only exact-current inputs, and block duplicate current producers.

## Migration Plan

1. Add structural counter regressions for discovery count, identity construction, ambiguity size, and compact command composition.
2. Introduce invocation-local observation reuse and remove the duplicate pre-build capture.
3. Store complete review identity, separate compact projection identity, and switch release publication to compact.
4. Aggregate ambiguity and other exact same-authority physical rows without changing logical denominators.
5. Replace repeated coverage-derived candidate arrays with one direct-current content-addressed neighborhood catalog and add shared-behavior scale plus corrupt-reference regressions.
6. Close finite-selector and test/check-owner semantic regressions, then run the complete live self-maintenance review until all real candidates and gaps are resolved.
7. Replace structural-id retain decisions with current necessity witnesses, contract lexical singleton false candidates, and make canonical proof receipts discoverable by the read-only audit.
8. Archive the coordinated OpenSpec changes, freeze the resulting governed source, renew final model authority once, synchronize maintained installations, and run the unique foreground release validation only from that frozen final snapshot.
