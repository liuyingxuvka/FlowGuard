## Context

FlowGuard already has route-specific checks for model-test alignment,
DevelopmentProcessFlow freshness, TestMesh validation hierarchy, ModelMesh
parent/child boundaries, model-miss repair, and code-structure derivation.
Adoption records show that those routes work for their declared local
obligations, but final completion claims can still sound broader than the
evidence actually proves.

The gap is a final, user-readable and machine-readable ledger that answers:
which risk was modeled, which model obligation owns it, which public code
surface implements it, which test/replay/manual evidence proves it, whether
that evidence is current, and what remains out of scope.

## Goals / Non-Goals

**Goals:**

- Add a small public API for risk evidence ledger rows, plans, reports, and
  review findings.
- Make missing model, code, test, stale evidence, skipped evidence,
  internal-path-only tests, and out-of-scope rows visible before full
  confidence is claimed.
- Keep the ledger as the final confidence summary that consumes route-specific
  evidence from Model-Test Alignment, TestMesh, ModelMesh,
  DevelopmentProcessFlow, and Model-Miss Review.
- Update adoption records and skills so users see what was proven in plain
  terms.
- Add an executable FlowGuard rollout model with known-bad cases for overbroad
  green claims.

**Non-Goals:**

- Do not require one FlowGuard transition per code line.
- Do not replace Model-Test Alignment, TestMesh, ModelMesh, StructureMesh,
  DevelopmentProcessFlow, or Model-Miss Review internals.
- Do not make ordinary test commands run inside FlowGuard.
- Do not add third-party runtime dependencies.
- Do not change schema version `1.0`.

## Decisions

1. Add the ledger as a separate public helper route.

   Rationale: A separate helper lets existing routes remain focused while giving
   final adoption evidence one common confidence vocabulary. Alternative
   considered: extend Model-Test Alignment to own the whole concept. That would
   overload it with process freshness, TestMesh, ModelMesh, and model-miss
   responsibilities it explicitly does not own.

2. Model each row as one user-meaningful risk, not one code line.

   Rationale: The ledger should preserve FlowGuard's abstraction level while
   forcing each abstraction to connect to evidence. Alternative considered:
   line-level rows. That duplicates implementation code and does not solve
   stale or unbound evidence.

3. Use confidence decisions instead of a single green/red label.

   Rationale: Users need to distinguish full confidence from "model passed but
   tests are missing", "tests passed but model is missing", "evidence is
   stale", and "explicitly out of scope". Alternative considered: fail every
   partial row. That would make scoped adoption impossible and encourage hidden
   skipped checks.

4. Keep source audits and conformance replay as evidence sources, not proof
   substitutes.

   Rationale: Conservative source audit can find missing bindings, but it is
   not semantic proof. Conformance replay is still needed for production-facing
   behavior. Alternative considered: let AST audit close all code/test claims.
   That would recreate evidence overclaiming.

5. Extend adoption logging with optional ledger fields.

   Rationale: Older adoption records should remain readable and serializable.
   New records can include a ledger summary without breaking existing callers.

## Risks / Trade-offs

- [Risk] The ledger becomes another checklist that agents fill loosely. ->
  Mitigation: add known-bad rollout cases and review findings for unbound,
  stale, internal-only, skipped, and overclaimed rows.
- [Risk] Users interpret partial confidence as failure. -> Mitigation: report
  clear decision names and plain-language row dispositions.
- [Risk] Duplicate evidence exists in route reports and the ledger. ->
  Mitigation: ledger rows reference route evidence ids and summarize boundaries
  rather than copying full route internals.
- [Risk] Release sync misses the shadow workspace. -> Mitigation: treat shadow
  import and focused tests as release tasks.

## Migration Plan

1. Add the executable rollout model and run it before production code edits.
2. Implement public ledger data types and review logic.
3. Add CLI/template support and public exports.
4. Update skills, adoption protocol, docs, README, changelog, and API surface.
5. Add focused unit tests and template tests.
6. Run focused checks, full regression, OpenSpec validation, install sync, and
   shadow workspace validation.
7. Bump package version, commit, tag, push, and publish a source-only GitHub
   release.

Rollback is straightforward: callers can ignore the new ledger helper while
existing route-specific helpers continue to work.

## Open Questions

- None for this implementation. Exact helper names may follow existing
  FlowGuard naming conventions during implementation.
