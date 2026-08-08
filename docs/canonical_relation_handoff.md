# Canonical Relation Carrier

`flowguard.canonical_relation` is an internal data carrier, not an AI route,
search engine, comparison service, or completion checker. It is the sole
direct-current relation schema.

The carrier exists because several current owners need to pass the same exact
DNA relation without copying loosely related fields. A canonical owner first
selects the affected commitment, model, code boundary, test obligation, or
topology edge from current evidence. It may then construct:

- `CanonicalRelation`: one typed edge with exact source and target endpoint
  identities, the source identities that establish it, and any typed BCL
  relation references;
- `CanonicalRelationHandoff`: the immutable group of those relations together
  with affected model, code-obligation, test-obligation, and gap ids;
- `normalize_canonical_relation_handoff(...)`: direct-current normalization of
  that one schema. Old shapes are not accepted.

Supported relation types include owner-declared DNA relations such as
`same_intent`, `shared_owner`, `affected_sibling`, `shared_mechanism`,
`adapter_only`, `duplicate_boundary`, and `false_friend`, plus observed-model
edges such as `contains`, `refines`, `depends_on`, `delegates_to`, `consumes`,
`produces_for`, `realizes`, `supersedes`, `validates`,
`shares_kernel_with`, `implements`, `invokes`, and `affects`.

The relation type is not proof. Every relation requires an exact
`relation_id`, two distinct typed endpoints, and at least one current source
identity. `evidence_current=False` remains a visible gap. The consuming owner
decides what the relation means under its own contract.

## Current Use

The ordinary path is:

```text
current commitment / blueprint / topology owner
-> exact CanonicalRelation identities
-> CanonicalRelationHandoff
-> ContractExhaustionMesh materializes finite cases when coverage is required
-> owning route proves code, test, mesh, reduction, or risk obligations
```

ContractExhaustionMesh may use the handoff to materialize stable relation-based
case ids and to report a gap when a declared relation was not materialized.
Existing Model Preflight, Architecture Reduction, Code Structure
Recommendation, Model-Test Alignment, and other owners may consume the same
handoff, but each remains responsible for its own decision and evidence.

## Hard Boundary

This internal carrier does not:

- scan a repository for lookalikes;
- infer maintenance groups from names or source text;
- score or classify arbitrary pairs;
- select a primary owner or runtime authority;
- expand the affected scope beyond declared current identities;
- recommend a merge merely because two things look alike;
- run a standalone template, report, or route;
- prove that code or tests can be changed safely.

When the owner cannot name the exact relation and its source identities, the
correct result is an explicit gap or human review. It is never a reason to
restore a free-form discovery engine, fallback classifier, or parallel
completion path.
