## 1. Seed contract and exact selection

- [x] 1.1 Add the route-scoped seed data model with the four layers, stable IDs, exact applicability predicates, branch fields, privacy disposition, and promotion status.
- [x] 1.2 Add deterministic serialization and schema validation for packaged seeds; reject missing fields, duplicate IDs, private paths, self-owner IDs, and stale/incompatible records without a compatibility reader.
- [x] 1.3 Add exact `TaskFacts` selection and pending-branch projection; unknown, ambiguous, fuzzy-only, or unpromoted matches must return a blocker and zero applied seeds.
- [x] 1.4 Add target-owned branch closure validation for `modeled` and proved `not_applicable`; pending or unproved branches must block and seed receipts must not satisfy target receipts.
- [x] 1.5 Add focused positive, known-bad, false-friend, privacy, unknown-route, multi-match, stale-receipt, and pending-branch tests.

## 2. Public ModelMesh template

- [x] 2.1 Add `flowguard/template_text/model_mesh.py` with target-owned parent partition, unique child/parent ownership, shared-kernel relations, changed-boundary reattachment, and stale/not-run evidence fields.
- [x] 2.2 Add the ModelMesh template factory, explicit CLI route, current role-root model/runner paths, and public adapter wiring without copying the mesh engine.
- [x] 2.3 Add executable positive and negative template tests for missing partition, overlapping siblings, two parents, changed child, stale child receipt, parent-as-child receipt, partial activation, and count-only false friend.

## 3. Public ContractExhaustion template

- [x] 3.1 Add `flowguard/template_text/contract_exhaustion.py` requiring finite dimensions, member universes, allowed/rejected combinations, normalization, oracle, stable case IDs, exclusions, shard owners, receipts, and handoffs.
- [x] 3.2 Add the template factory, explicit CLI route, current role-root paths, and public adapter wiring using existing ContractExhaustion/mesh checks.
- [x] 3.3 Add executable tests for missing denominator/oracle, unbounded Cartesian, missing member, duplicate case ID, stale universe, hidden fallback reject case, and unbounded UI exception.

## 4. Public reverse-surface closure template

- [x] 4.1 Add `flowguard/template_text/reverse_surface_closure.py` as a thin authoring guide that reuses discovery, shard, merge, semantic-map, owner-authority, and audit helpers.
- [x] 4.2 Add the template factory, explicit CLI route, current role-root paths, and BCL/MTA/UI adapter handoffs.
- [x] 4.3 Add tests for independent denominator, component expansion, both exact join directions, owner/test/receipt/authority joins, UI-like action joins, finite dynamic dispatch, and typed discovery-vs-graduation unresolved boundaries.

## 5. Storage and layout performance boundary

- [x] 5.1 Add a one-walk read-light storage audit that reports counts, bytes, bounded largest-item samples, current/pinned/lease/collectible/unknown classes, and reparse/outside-root blockers without content reads or hashes.
- [x] 5.2 Add the CLI route and lifecycle integration for explicit storage-audit → evidence-audit → exact-plan → quarantine → replay/restore/purge, keeping ordinary validation free of persistent cleanup.
- [x] 5.3 Add tests for one walk, zero content reads/hashes, optional roots, current/pinned/lease protection, stale-plan refusal, quarantine restore, and bounded output.

## 6. Harvest, promotion, and documentation

- [x] 6.1 Extend the existing risk-template harvest/review path to emit candidate-only seed records and to promote only reviewed, privacy-neutral, proof-complete seeds; do not add a second harvest engine.
- [x] 6.2 Add the first neutral branch candidates from existing proven tests, retaining `not_harvestable` when any protected error, positive, known-bad, false-friend, or exact predicate is missing.
- [x] 6.3 Update current public docs, generated rules, and CLI help to explain exact selection, pending closure, compact layout, three validation profiles, and direct-current replacement; do not rewrite archive/history.
- [x] 6.4 Add tests proving fuzzy search is recommendation-only, local candidates cannot apply, private provenance is omitted, and template receipts cannot impersonate target receipts.

## 7. Integration and current authority

- [x] 7.1 Run strict OpenSpec validation for this change and the existing currentness change; resolve every current-code/spec/template contradiction before implementation is marked complete.
- [x] 7.2 Run focused template, seed, storage, layout, reverse-closure, and existing route tests with `python -B`; inspect counterexamples and fix failures at the owning route.
- [x] 7.3 Freeze source/toolchain/owner identities, run one affected owner plan and execution, rebuild current authority and reverse denominator, and require all unresolved completion counters to be zero.
- [x] 7.4 Run the final full owner only after all prior gates pass; record external CI/release as not_run unless separately authorized, and run `git diff --check` plus owned-path status review.

Current disposition for 7.4: the final local full owner completed successfully under
one frozen owner plan. The parent result is `pass` with 10/10 required children passed,
zero failed/blocked/not-run children, exit code 0, and a verified parent result at
`.flowguard/evidence/full-validation/v0.68.15-final11/result.json`. Model regressions
were 51/51, the self-maintenance cleanup gate passed, strict OpenSpec passed, and the
formal/shadow/installed consumer projections passed exact parity. External CI,
consumer publication, and release remain `not_run` without separate authorization.
