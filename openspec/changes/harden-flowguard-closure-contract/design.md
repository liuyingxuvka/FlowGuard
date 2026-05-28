## Context

FlowGuard already has separate helpers for conformance replay, runtime gateway
adoption, model-impact freshness, model maturation, recurring model-miss
families, and risk evidence ledgers. The gap is at the final claim boundary:
agents can run individual helpers and still overstate a full-confidence claim
when one helper is missing, stale, scoped, or disconnected from the user-facing
risk.

This change codifies the existing `docs/flowguard_closure_contract.md` guidance
as an executable review helper. The helper is a coordinator over current
FlowGuard evidence. It does not replace the owning satellite routes and does
not invent a second workflow.

## Goals / Non-Goals

**Goals:**

- Make broad FlowGuard completion/release confidence depend on current evidence
  from the existing closure gates.
- Treat runtime traces that cannot be mapped to a model obligation as
  model-miss evidence.
- Treat changed artifacts as invalidation signals for dependent proof.
- Surface model-quality gaps before they become overconfident claims.
- Require same-class evidence for in-scope runtime/model misses.
- Consume runtime gateway adoption and risk evidence ledger reports at the same
  final confidence boundary.

**Non-Goals:**

- Do not replace `review_runtime_gateway_adoption`,
  `review_model_impact_freshness`, `review_model_maturation_loop`,
  `review_defect_family_gates`, or `review_risk_evidence_ledger`.
- Do not scan arbitrary source trees inside the closure helper; projects still
  provide inventory and observation evidence.
- Do not claim that unmodeled behavior is bug-free.

## Decisions

1. **Add a closure contract coordinator.**

   Add `flowguard.closure_contract` with dataclasses for:

   - runtime trace mapping rows;
   - artifact invalidation rows;
   - model-quality signals;
   - same-class model-miss closure rows;
   - child report summaries for gateway/freshness/maturation/ledger support;
   - final closure findings and decisions.

   Rationale: this keeps the upgrade inside FlowGuard's existing closure
   contract instead of asking each project to hand-compose final confidence.

2. **Use evidence summaries instead of direct coupling to every report type.**

   The closure helper will consume simple `ClosureEvidenceReport` rows with
   `report_kind`, `decision`, `ok`, `current`, and `confidence`. Dedicated
   helper constructors may be added later, but the first version stays small and
   decoupled.

   Rationale: FlowGuard already has many report objects. A common evidence row
   lets projects record the relevant result without circular imports or a large
   inheritance hierarchy.

3. **Block full confidence, allow explicit scoped confidence.**

   Missing/stale required evidence blocks full confidence. Optional or
   deliberately out-of-scope rows may produce scoped confidence only when the
   plan permits scoped claims.

   Rationale: this matches current FlowGuard reporting language and avoids
   falsely upgrading partial evidence into production confidence.

4. **Keep runtime gateway inventory strengthening at the closure boundary.**

   Projects must still provide runtime gateway plans. The closure review adds
   checks that inventory source evidence exists, that runtime observations cover
   the claimed surface, and that path-owner conflict rows are resolved before a
   runtime-protected claim is accepted.

   Rationale: FlowGuard should not pretend to be a universal source scanner, but
   it can require that the inventory source and conflicts are visible.

## Risks / Trade-offs

- **Risk: Another wrapper could look like a parallel process.**
  Mitigation: name and document it as the executable closure contract and make
  it consume existing report evidence, not replace existing helpers.

- **Risk: The first version may not auto-discover every project artifact.**
  Mitigation: require explicit inventory and invalidation rows, then let target
  projects build scanners on top.

- **Risk: Full confidence becomes harder to claim.**
  Mitigation: this is intended. Scoped confidence remains available when the
  plan records what is out of scope and why.
