## Context

ContractExhaustionMesh is already the canonical route for generated finite
bad-case ids. The existing implementation can generate mutation cases,
Cartesian combination cases, shards, receipts, route handoffs, and broad-claim
gates after dimensions and axes are declared.

The remaining gap is declaration completeness. A matrix can be internally
correct while still missing a whole class of in-scope dimensions, payload
contracts, file/attachment contracts, code boundaries, or observed same-class
misses. FlowGuard needs a generic way to say "this is the universe this matrix
claims to cover" and then prove the matrix matches that universe.

## Goals / Non-Goals

**Goals:**

- Add coverage-universe declarations to the existing ContractExhaustionMesh
  route.
- Keep the API generic and reusable for any submitter, worker, runtime,
  package, file, transition, or payload contract.
- Generate domain-neutral synthetic contract-fault profiles from existing
  cases so downstream systems can rehearse bad submissions without FlowGuard
  knowing about FlowPilot or AI agents.
- Require actionable feedback for reject/block/reissue cases when a broad
  coverage claim is made.
- Add observed-problem backfeed so real misses must map to generated cases and
  same-class coverage, or become explicit model gaps.

**Non-Goals:**

- Do not add a FlowPilot-specific fake-AI route, skill, or public API.
- Do not make ContractExhaustionMesh a global repository-wide bug oracle.
- Do not add compatibility aliases or fallback case-generation paths.
- Do not replace Model-Test Alignment, TestMesh, ModelMesh, or Risk Evidence
  Ledger as downstream evidence owners.

## Decisions

### Decision: Coverage universe belongs inside ContractExhaustionMesh

The universe will be a dataclass referenced by `ContractExhaustionPlan`.
It names required dimensions, axes, interaction groups, payload contracts,
boundaries, generated case ids, and receipts, plus explicit scoped exclusions.
This keeps the current public route and avoids a competing coverage checker.

Alternative considered: add a new route for "coverage universe review". That
would duplicate ContractExhaustionMesh ownership and make agents choose between
two case-generation authorities.

### Decision: Synthetic faults are contract-level profiles

The new helper will emit `ContractFaultProfile` rows from generated cases. A
profile describes mutation path, expected status, expected feedback fields,
repair fields, retry class, and whether it is synthetic-only. It deliberately
does not mention AI, FlowPilot, or a specific runtime.

Alternative considered: add FlowPilot fake-AI behavior classes directly to
FlowGuard. That would make the generic library depend on one consumer's actor
model.

### Decision: Actionable feedback is checked through oracles

Cases that expect reject, block, reissue, retry, or repair require their
oracle to provide expected message fields and repair fields when a broad or
explicit actionable-feedback claim is made. The generated matrix then proves
not only "this bad case is detected", but also "the recipient gets enough
structured information to fix it".

Alternative considered: put all feedback checks into tests only. That would
leave the model unable to detect missing repair instructions before downstream
test code exists.

### Decision: Observed misses backfeed into the same route

`ObservedProblemBackfeed` rows map real misses to generated mutation cases,
combination cases, coverage receipts, and same-class cases. Missing mappings
produce findings instead of silently expanding the claim.

Alternative considered: record observed misses only in ModelMissReview. That
preserves bug provenance, but does not prove the canonical matrix learned the
same-class family.

## Risks / Trade-offs

- Universe declarations can become too large -> allow scoped exclusions, but
  require explicit reason and owner route for each exclusion.
- Payload contracts and code boundaries may not have first-class objects in a
  contract-exhaustion plan -> match them through declared universe ids, case
  metadata, and explicit exclusions until their owning routes project them.
- Synthetic fault profiles could be mistaken for live evidence -> mark them
  synthetic-only and not live-completion evidence.
- Broad claims become stricter -> routine narrow claims remain allowed, while
  broad/full claims must carry the universe proof.

## Migration Plan

1. Add the new dataclasses and review checks to `contract_exhaustion.py`.
2. Export the new symbols through the existing ContractExhaustionMesh API.
3. Add focused tests for missing universe, missing ids, exclusions, actionable
   feedback, synthetic profiles, and observed-problem backfeed.
4. Update docs/templates to describe the generic actor/submitter layer without
   FlowPilot-specific names.
5. Validate OpenSpec, targeted tests, project audit, install sync, and local
   version metadata before committing.
