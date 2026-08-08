## Context

See `proposal.md` for motivation. FlowGuard already records topology relations, child model evidence, model-test coverage, and a full model parent result, but the current self-audit showed that these objects can be joined with the wrong edge kind or evidence owner. The design must keep structural topology, semantic cross-boundary relations, feedback progress, evidence production, evidence registration, and readiness consumption independently checkable while preserving affected-only operation.

## Goals / Non-Goals

**Goals:**

- Represent exactly one structural parent separately from any number of typed cross-boundary parents.
- Validate structural acyclicity independently from real feedback SCC progress closure.
- Make the full parent consume exact-current child and progress receipts without becoming their producer.
- Recursively resolve lexically qualified delegated assertion helpers to real leaves.
- Preserve coverage-contract ownership and planned-versus-executed status across every join.
- Keep the whole-self result fail-closed without copying complete child state graphs or evidence payloads.

**Non-Goals:**

- Change Python, tests, executable FlowGuard models, manifests, installation, or release identity in this planning step.
- Convert every cross-boundary relation into hierarchy or forbid legitimate feedback.
- Let the full model parent rerun missing children, manufacture receipts, or use a whole-suite pass as child evidence.
- Treat a helper name, source path, or planned checker as executed proof.

## Decisions

### Store structural and cross-boundary parent identities separately

The topology node projection carries one `structural_parent_id` plus a sorted deduplicated `cross_boundary_parent_ids` collection. The declared root uses one explicit root sentinel; every other in-scope node must resolve to exactly one structural parent. Structural validation considers only structural edges and requires reachability plus acyclicity. Consumer, producer, feedback, retry, repair, shared-resource, affected-sibling, and similar semantic edges remain typed cross-boundary relations and never modify the structural parent.

This is preferred over a generic `parent_ids` set because a multi-parent semantic graph cannot answer which owner establishes hierarchy, and treating every relation as structure creates false cycles. It is also preferred over choosing the first parent because ordering is not authority.

### Evaluate feedback SCCs over a separate semantic graph

After structural closure, the mesh builds a bounded feedback graph only from relation kinds that can return control, work, tokens, errors, retries, or repair results. A component with multiple nodes, or a self-loop, is a real feedback SCC. Each component binds one progress contract identifying its input/repeated-token boundary and a blocker, repair-token mutation, ranking decrease, monotone progress rule, or finite bound.

Progress evidence must be current for the exact snapshot and independently produced. A descriptive relation label, child-local pass, structural acyclicity, or contract text alone is insufficient. The closure result records the exact SCC members, relation ids, progress contract id, evidence receipt, and any unresolved branch without expanding child state graphs.

### Make the full model parent a receipt consumer only

Each child validation owner produces one supervised terminal receipt before full-parent aggregation. The authority registry verifies and admits the immutable receipt without launching the producer. The full model parent consumes a frozen map from child id to exact receipt id and fingerprint, plus current reattachment, interface, and feedback-progress receipts. Its terminal result proves only that aggregation.

The blueprint builder, full parent, mesh reviewer, and readiness qualifier may not create or register a passing child/progress receipt during the same qualification. This direct-current boundary avoids circular evidence while keeping child execution and parent aggregation independently rerunnable by their own owners.

### Resolve delegated assertion helpers as a recursive lexical graph

Delegated helper discovery starts from each coverage contract's declared checker member and recursively follows only current statically resolved helper calls within the admitted test boundary. An identity combines source owner, module or file identity, lexical qualified name, and current content fingerprint. This keeps nested same-named helpers distinct. Every reachable branch must terminate at a registered assertion or native-check leaf; cycles, unresolved dynamic calls, stale helpers, or assertion-free leaves remain exact gaps.

Helpers and leaves are implementation members, not new coverage owners. The original coverage contract owner remains stable throughout the graph. The graph can complete planned checker design while execution stays `not_run` until a terminal receipt covers the exact leaf and contract subject.

### Compose readiness without collapsing evidence layers

Target qualification supplies the separated topology projection. ModelMesh supplies structural, feedback, and reattachment reports. Model authority supplies independently registered receipts and the full-parent aggregation identity. Model-Test Alignment supplies the helper graph, coverage owner, checker design, and execution status. Software Blueprint Readiness consumes these reports and advances only through their complete current prefix; it does not recalculate or overwrite their native findings.

## Risks / Trade-offs

- [Risk] Existing nodes may carry several undifferentiated parent-like relations. → Mitigation: require an explicit direct-current structural disposition for each relation and keep unresolved nodes blocked; do not select by order or name.
- [Risk] Treating all semantic cycles as feedback creates false SCC obligations. → Mitigation: restrict SCC construction to declared return/control/retry/repair relation kinds and preserve other cross-boundary edges outside the feedback graph.
- [Risk] A progress contract can become self-certifying. → Mitigation: require a separately supervised terminal receipt whose producer and registration episode predate the consuming qualification.
- [Risk] Recursive helper discovery can grow or cycle. → Mitigation: key by lexical identity plus fingerprint, memoize visited nodes, preserve exact cycles, and stay inside the frozen test boundary.
- [Risk] Parent aggregation becomes slower when it must verify every child receipt. → Mitigation: verify immutable fingerprints and ownership references, reuse only exact-current terminal receipts, and never rerun children inside the parent.
- [Risk] Main specs are already changing in parallel. → Mitigation: append narrowly owned requirements, preserve existing content, validate each affected spec, and stage only this change's paths during later integration.

## Migration Plan

1. Add the five delta requirements and synchronize them to their existing main capability specs.
2. Update the provider-neutral topology shape and strict loaders directly to the new structural/cross-boundary identities without a compatibility reader.
3. Add structural classification, feedback SCC progress, child receipt, self-evidence, helper recursion, ownership, and execution model counterexamples before production edits.
4. Implement the topology, authority, helper, and readiness joins under their existing owners.
5. Run focused native and point regressions, then renew exact affected model evidence and the full model parent.
6. Create and activate one fresh accepted model revision and rerun the live compact self-audit.
7. Continue archive, installation, full validation, and release only after the new current authority passes.
