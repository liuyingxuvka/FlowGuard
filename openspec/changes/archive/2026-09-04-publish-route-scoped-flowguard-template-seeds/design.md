## Context

The current public facade is `flowguard/templates.py`; route text lives in
`flowguard/template_text/`. The risk-template library already owns portable
search and local harvest, while reverse-surface discovery and its audit already
exist as separate implementation routes. The design must preserve those
boundaries, keep consumer projections small, and never treat a local card,
historical artifact, or predictive-KB recommendation as current authority.

## Goals / Non-Goals

**Goals:**

- Add one deterministic seed contract and exact-facts selector.
- Add compact executable templates for ModelMesh, ContractExhaustion, and
  reverse-surface closure without duplicating their engines.
- Keep pending branches visible until target-owned closure evidence exists.
- Keep storage planning read-light and recoverable.
- Preserve direct-current replacement and privacy boundaries.

**Non-Goals:**

- No automatic migration, compatibility reader, alias, fallback, or silent
  inheritance of old seed records.
- No whole-Documents discovery, consumer-project edits, external CI/release,
  or Predictive-KB authority changes.
- No line-by-line intent inventory; component groups and route-owned
  obligations remain the semantic granularity.

## Decisions

### 1. Extend the existing template library, do not create a second harvest engine

The seed schema and selector will sit beside `RiskTemplate` and reuse its
review/harvest boundary. Existing risk cards remain risk cards; a seed adds
exact predicates, branch skeletons, and closure state. Search may return
recommendations, but only a promoted seed with a complete predicate may be
selected.

Alternative rejected: a second independent `branch_harvest` module would
duplicate local storage, privacy review, and promotion semantics.

### 2. Keep route templates as thin public adapters

Each new template file contains the target-facing model fields, required
positive/negative cases, and the command/owner handoff. It calls the existing
ModelMesh, ContractExhaustion, and reverse-surface helpers; it does not copy a
resolver, discovery walker, or receipt writer. `templates.py` remains the
only public factory and CLI dispatch remains explicit.

Alternative rejected: embedding implementation engines in template text would
make generated projects diverge from the current FlowGuard authority.

### 3. Use exact joins for branch closure

Selected branch IDs, target artifact IDs, owner IDs, proof references, and
receipts are joined by stable IDs and current fingerprints. A pending branch
blocks the target route. `not_applicable` is valid only with target-owned
proof; template receipts never satisfy target model/test/release claims.

### 4. Make storage audit a separate read-light preflight

The storage audit performs one guarded directory walk, records path counts and
bytes, and classifies reachability from existing evidence heads, pins, leases,
and current plans. Content reads and hashes remain in the evidence audit or
exact GC plan, never in ordinary validation. Quarantine and purge stay
separate explicit operations.

### 5. Keep layout compact and optional roots on demand

The current shape manifest stores role rules and identity, not ordinary
per-file fingerprints. Model/verification roots are created at adoption;
other roots appear when their first current artifact is written. A layout
audit reports bounded path samples and does not become a semantic or evidence
scanner.

## Risks / Trade-offs

- [Risk] A target may select a seed whose predicate is technically exact but
  semantically unsuitable. → Require target-owned branch closure and keep the
  selected disposition pending until proof exists.
- [Risk] Existing local cards may use an older shape. → Treat them as
  candidate-only; direct manual rewrite or retirement is required, with no
  compatibility reader.
- [Risk] Thin templates may omit a route-specific edge. → Require positive,
  known-bad, and false-friend cases in the seed contract and route-owned
  executable checks.
- [Risk] Storage classification can be stale while a run is active. → Bind
  the plan to current heads, pins, leases, and plan identity; stale plans
  refuse to move anything.
- [Risk] Public seed metadata can leak source provenance. → Promotion performs
  privacy checks and consumer projections contain only neutral IDs and proof
  references.

## Migration Plan

1. Validate and apply the OpenSpec change after the seed schema and route
   templates are implemented.
2. Run focused seed, template, storage, and existing route tests.
3. Harvest existing proven branches only with `--no-write` first; promote
   individually after positive/negative/false-friend and privacy checks.
4. Rebuild current FlowGuard authority and run affected validation.
5. Keep old local candidates in their existing history/working area; do not
   rewrite or read them as current. Any incompatible candidate becomes a
   manual rewrite/retirement work item.

## Open Questions

None. The target-owned semantic decision remains intentionally outside
automatic selection and is represented by the required closure record.
