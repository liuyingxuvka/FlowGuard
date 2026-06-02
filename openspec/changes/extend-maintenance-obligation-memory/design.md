## Context

FlowGuard already has the right owner routes for structural and evidence risk:
finding ledger summarizes gaps, maintenance scan routes changed artifacts and
signals, model maturation upgrades coarse models, StructureMesh and
Architecture Reduction own code-shape risks, and Risk Evidence Ledger owns broad
confidence claims.

The missing behavior is continuity. A current run can expose a risk, but a
later run has no first-class object that says "this anchored obligation is
still open and must be reconsidered if the same surface is touched." The design
therefore extends the existing maintenance chain rather than adding a new
technical-debt scanner.

## Goals / Non-Goals

**Goals:**
- Represent unresolved FlowGuard maintenance work as small, anchored obligation
  rows.
- Let existing reports produce obligation rows from already-known gaps.
- Let maintenance scan reopen obligations when current work touches their
  anchored model/code/test/public surface.
- Let model maturation and risk evidence ledger consume relevant obligations
  before broad confidence.
- Keep agent guidance compact and route-owned.

**Non-Goals:**
- No repository-wide static scanner.
- No standalone `technical_debt` route.
- No automatic refactor, model split, or test execution from obligation memory.
- No hard blocking from vague or unanchored observations.

## Decisions

1. Extend the reporting/helper layer with obligation rows.

   Add a small immutable row type such as `MaintenanceObligation` with stable
   ids, source route, reason code, required owner route, strength, status,
   anchored artifact ids, anchor kind/path/symbol/model ids, evidence ids, and
   scope notes. This belongs beside maintenance/reporting helpers because it is
   a coordination object over existing routes.

   Alternative considered: create a new DebtGuard route. Rejected because the
   user goal is natural prevention through normal FlowGuard use, and current
   FlowGuard routes already own the concrete work.

2. Generate obligations from existing findings and reports.

   Add helper functions that convert known non-pass sections, maintenance
   actions, and maturation findings into obligation rows. The conversion must
   preserve source route and reason code so the owning route remains explicit.

   Alternative considered: require agents to hand-write obligations. Rejected
   because the protection should happen as a normal consequence of FlowGuard
   use.

3. Make maintenance scan consume prior obligations.

   Extend `MaintenanceScanPlan` with `prior_obligations`. During review, reopen
   active obligations whose artifact ids or anchors intersect current changed
   artifacts. The scan returns ordinary `MaintenanceAction` rows for the owner
   route. The scan still does not prove the owner route passed.

   Alternative considered: persist and load a project JSONL file inside the
   helper. Rejected for the first implementation because adapters differ by
   project. JSONL templates/docs can show how a project keeps rows, but the
   package helper should remain deterministic.

4. Connect broad confidence through Risk Evidence Ledger.

   Add optional open-obligation references to risk rows or ledger plan inputs.
   Relevant unresolved obligations block or scope full confidence, matching the
   existing ledger pattern for topology, family, split, stale, and proof gaps.

5. Keep prompt changes minimal.

   Add one compact rule to the kernel and route snippets: anchored unresolved
   route work becomes an inherited maintenance obligation; unanchored concerns
   remain observations. Avoid long checklist prompts.

## Risks / Trade-offs

- [Risk] Agents treat obligation rows as validation evidence. -> Mitigation:
  report wording and tests say obligations are routing/freshness memory only;
  owner-route evidence is still required.
- [Risk] Vague AI warnings become permanent blockers. -> Mitigation:
  require concrete anchors and owner routes for active obligations; unanchored
  entries are observation-only.
- [Risk] Obligation memory becomes another oversized API surface. ->
  Mitigation: small row type, helper converters, no new route, no scanner.
- [Risk] Active topology-hazard work overlaps this change. -> Mitigation:
  consume topology hazard outputs through existing fields and avoid editing the
  active topology change artifacts except for compatible docs after that work
  lands.

## Migration Plan

1. Add the row/report helpers and focused tests.
2. Extend maintenance scan plan/report behavior while preserving existing clear,
   required, suggested, scoped, and blocked decisions.
3. Extend model maturation and risk evidence ledger with optional obligation
   inputs.
4. Update route docs, templates, AGENTS snippet, and skill guidance.
5. Add a FlowGuard self-model for the existing-chain upgrade.
6. Run OpenSpec validation, focused tests, self-model checks, full practical
   regression, editable install sync, project audit/upgrade as needed, and local
   repository sync.
