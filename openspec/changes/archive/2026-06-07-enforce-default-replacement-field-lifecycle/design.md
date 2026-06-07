## Context

FlowGuard already has route-specific tools for existing model lookup, model
first checks, transition coverage, model-code-test alignment, legacy path
disposition, model-miss repair, development freshness, and final closure.
Those pieces are correct, but they do not yet share one default rule for
replacement work: if the user did not ask to keep compatibility, old behavior
and old fields need disposition instead of accidental survival. Field-heavy
systems also need complete field accounting without forcing every field into a
single large behavior model.

## Goals / Non-Goals

**Goals:**

- Keep the current route-handoff entry shape and add the missing field and
  replacement closure layer behind it.
- Add a field lifecycle mesh that covers every discovered field at leaf level
  and projects important fields into existing behavior models.
- Bind field projections to model obligations, owner code contracts, tests,
  transition cells, legacy path/field disposition, and closure evidence.
- Make bug repairs close the full loop: observed failure, same-class case, root
  cause, field/model update, code owner, tests, old-path/field disposition,
  freshness, and final closure.
- Keep high-level models readable by projecting only behavior-bearing fields
  while leaf field models account for all fields.

**Non-Goals:**

- Do not replace Model-Test Alignment, DevelopmentProcessFlow,
  Architecture Reduction, Model-Miss Review, TestMesh, ModelMesh, or
  ClosureContract with a new all-in-one runner.
- Do not require every display-only or metadata field to become a high-level
  state-machine dimension.
- Do not preserve old compatibility paths by default for new replacement work.
  Compatibility is allowed only when declared and evidence-backed.
- Do not perform remote publishing as part of this change unless requested
  separately.

## Decisions

1. **Add a field lifecycle mesh, not a giant main model.**

   The field lifecycle mesh has parent groups such as entity, payload, schema,
   config, public entrypoint, or prompt/config surface. Child/leaf rows cover
   every field. Behavior-bearing fields project upward into the existing model
   and test routes. Non-behavioral fields stay accounted with scoped-out
   reasons. This gives complete field coverage without exploding the main
   state machine.

2. **Represent old-field disposition beside old-path disposition.**

   FlowGuard already has `LegacyPathDisposition`. Replacement work needs the
   same clarity for old fields: deleted, blocked, migrated, delegated to a new
   field/path, same-contract repaired, explicitly preserved, out of scope with
   reason, or unknown. Unknown blocks full confidence.

3. **Use projection rows as the bridge to existing routes.**

   The field lifecycle mesh should not run tests or refactor code by itself.
   It produces field projections and obligations consumed by:

   - Model-first / transition coverage for state and transition behavior.
   - Code Structure Recommendation for reader/writer/owner maps.
   - Model-Test Alignment for model obligation -> CodeContract -> TestEvidence.
   - Model-Miss Review for bug root cause and same-class field failure cases.
   - DevelopmentProcessFlow and ClosureContract for freshness and final claims.

4. **Default replacement policy is opt-out by explicit compatibility.**

   Agents should not ask whether to preserve old behavior on every ordinary
   replacement task. The default is cleanup. Public API, old persisted data,
   external compatibility, or migration support can be preserved only when the
   plan declares compatibility intent and supplies evidence.

5. **Prompt changes stay compact and point to structured evidence.**

   AI-facing text should not become another large checklist. Skills and
   templates should say: create/use field lifecycle mesh when fields matter,
   project behavior-bearing fields, dispose old paths/fields by default, and
   rerun the relevant owner route before done claims.

## Risks / Trade-offs

- [Risk] Field inventory could become noisy and slow.
  -> Mitigation: require all fields to be accounted at leaf level, but only
  behavior-bearing fields project into high-level behavior models.

- [Risk] Agents may treat field inventory as proof.
  -> Mitigation: field rows are obligations and routing evidence, not proof.
  Full confidence still needs model-code-test evidence and closure review.

- [Risk] Compatibility users could be surprised by default cleanup.
  -> Mitigation: public compatibility remains supported when declared as
  compatibility intent with public-entrypoint, migration, or negative legacy
  evidence.

- [Risk] The change touches many route surfaces.
  -> Mitigation: keep the new runtime surface small, use existing routes for
  route-specific validation, and add tests that prove no parallel runner was
  created.

## Migration Plan

1. Create OpenSpec artifacts and a FlowGuard self-model for the new lifecycle.
2. Add the `field_lifecycle` module and route-scoped exports.
3. Add field projection consumption to existing routes without changing their
   ownership boundaries.
4. Update prompts, templates, docs, and focused tests.
5. Run focused model checks and unit tests after implementation.
6. Run practical regression, project audit, editable install verification,
   installed skill parity checks, shadow workspace checks, and local git sync.

Rollback is straightforward: remove the new field lifecycle module, exports,
OpenSpec deltas, and prompt/template references. Existing route behavior should
remain otherwise unchanged.

## Open Questions

None blocking implementation. If implementation exposes an oversized field
mesh or test surface, use ModelMesh or TestMesh for parent/child evidence
rather than expanding FieldLifecycleMesh into an all-in-one checker.
