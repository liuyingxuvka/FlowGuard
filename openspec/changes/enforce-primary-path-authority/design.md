## Context

FlowGuard already has several anti-debt controls:

- project guidance says old paths, old fields, aliases, wrappers, and fallback
  surfaces default to disposal unless compatibility is explicit;
- `ArchitectureReduction` classifies compatibility surfaces;
- `FieldLifecycleMesh` records old/replaced/compatibility field disposition;
- `LegacyPathDisposition` records old or alternate path disposition;
- topology hazard review detects duplicated or conflicting business paths;
- runtime path evidence binds observations to business path ids;
- ContractExhaustionMesh and TestMesh support finite Cartesian coverage and
  child evidence freshness;
- RiskEvidenceLedger owns final broad confidence.

The missing piece is a route that makes these pieces one default rule for AI
coding workflows: identify the primary runtime authority, fail closed on
primary failure, and reject automatic alternate success paths.

## Goals / Non-Goals

**Goals:**

- Add a first-class `primary_path_authority` route with structured plan,
  candidate, report, and finding objects.
- Reject "A failed -> B automatically returned success" paths by default.
- Require every non-primary surface to choose a disposition: delete, block,
  migrate, delegate to primary, preserve thin facade, manual-only, or scoped
  out.
- Represent primary-path authority as a finite coverage universe with
  Cartesian axes, generated case ids, shards, receipts, and downstream route
  handoff ids.
- Connect route evidence to runtime path evidence, topology hazard review,
  RiskEvidenceLedger, API registry, templates, skills, docs, and install sync.

**Non-Goals:**

- Do not remove explicit external compatibility facades that are current,
  bounded, non-authoritative, and tested.
- Do not ban bounded retries inside the same primary owner path.
- Do not make ContractExhaustionMesh or TestMesh duplicate this route's
  semantic policy. They generate and own coverage evidence; the new route owns
  the no-silent-fallback policy.
- Do not introduce a fake checker outside the real `flowguard` package.

## Decisions

### Decision 1: Add a route-specific module

Create `flowguard/primary_path_authority.py` instead of folding all checks into
runtime path or topology hazard modules.

Rationale: runtime path evidence can observe "B was invoked", and topology
hazard review can detect duplicated business paths, but neither owns the full
policy: business intent, primary authority, failure policy, fallback
classification, disposition, coverage, and final risk handoff. A route-specific
module keeps the public model clear and lets the sibling routes consume stable
ids.

Alternative considered: only add fields to existing routes. Rejected because
the policy would stay distributed and agents would continue missing one piece.

### Decision 2: Treat primary failure masking as a hard blocker

Any candidate that is invoked because the primary path failed and returns
success for the same business intent is a blocker unless it is explicitly
modeled as same-owner retry and does not change authority.

Rationale: this is the core maintenance-debt failure the change prevents.

Alternative considered: downgrade it to a warning. Rejected because warnings
are easy for agents to ignore during pressure to get tests green.

### Decision 3: Make `unknown` disposition fail

Fallback candidates with `unknown` classification or `unknown` disposition
block routine and release claims.

Rationale: unknown old paths are exactly where hidden compatibility debt lives.

Alternative considered: allow unknown under routine scope. Rejected because the
route is intended to change agent defaults before implementation starts.

### Decision 4: Model Cartesian coverage as finite, scoped, and downstream-owned

The route will expose default axes and interaction groups, but broad claims
must use ContractExhaustionMesh-style coverage receipts and TestMesh child
shard evidence.

Rationale: full repository Cartesian coverage is unbounded. The safe version is
model-scoped: declare finite axes, combine known interaction groups, and keep
exclusions explicit.

Alternative considered: hand-written bad cases only. Rejected because it misses
field/path/failure/compatibility combinations.

### Decision 5: Keep compatibility facades thin

An external compatibility facade may be preserved only when it delegates to the
primary path, has no business state writes or side effects of its own, and has
current evidence.

Rationale: this preserves real external contracts without making the facade a
parallel implementation.

Alternative considered: remove all compatibility. Rejected because public API
compatibility can be a valid product requirement.

## Risks / Trade-offs

- Broad matrices can become large -> mitigate with named interaction groups,
  shards, and TestMesh ownership instead of one monolithic test.
- Existing callers may need new required fields for strict claims -> keep
  fields optional where they are not in scope, but block broad
  primary-path-sensitive claims when evidence is missing.
- Route registry/API changes can desync installed skills -> verify repo-local
  package import path, editable install, shadow workspace import path, and
  installed skill hash/content after implementation.
- Parallel AI work can stale validation -> preserve unrelated changes and rerun
  project audit plus focused/full regression after final sync.

## Migration Plan

1. Add the new route module, public API exports, template, and route registry.
2. Add focused unit tests and self-model checks for primary-path authority.
3. Extend runtime path, topology hazard, risk ledger, docs, and skills to
   consume the new evidence fields and gate ids.
4. Add ContractExhaustionMesh/TestMesh coverage universe and shard tests.
5. Validate with OpenSpec, FlowGuard self checks, focused tests, and full
   regression.
6. Sync the implementation to the local git checkout and editable install,
   then verify metadata version, `flowguard.__file__`, and the new public API
   from both local workspaces.

## Open Questions

- The local working directory is not itself a git checkout. Final git sync
  should target the formal local FlowGuard git checkout, preserving unrelated
  work already present there.
