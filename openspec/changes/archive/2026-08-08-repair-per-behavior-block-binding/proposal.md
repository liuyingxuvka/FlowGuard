## Why

FlowGuard's expanded independent behavior denominator exposed a structural mismatch: one model owner may govern several real behavior surfaces, while portable field mappings and behavior cases were still represented as one owner-wide primary-surface declaration. That mismatch can either reject valid sibling blocks or, if merely filtered away, leave non-primary blocks without their own reconstructible contract.

## What Changes

- Require each observed behavior block under a model owner to carry its own exact portable binding for implementation fingerprint, input, output, state, effects, and only the model members and protected failures it actually realizes.
- Preserve one explicit composite behavior surface for parent-model semantics, so owner-wide good/bad transitions bind to that exact parent rather than being copied to every child function.
- Partition good, boundary, and bad cases by behavior block while preserving their model-level source-case lineage.
- Reject cases that target a block outside the declaring owner's independently observed behavior surface set.
- Require coverage edges to consume the case, checker, oracle, and implementation surface belonging to the same behavior block; sibling blocks cannot lend coverage to one another.
- Keep one model owner as the parent of several behavior blocks without collapsing those child blocks into a lexically selected primary surface.
- Keep every discovered implementation surface in the code map while classifying only callable or observed state/effect/entry surfaces as behavior blocks; modules, classes, nested functions, and pure private helpers remain explicitly owned supporting surfaces instead of receiving fabricated behavior cases.
- Treat a module or class aggregate as an independent composite behavior only when the active observation provider supplies an exact current composite behavior contract; a matching path, owner name, or containment relation alone never promotes the aggregate.
- Keep block-local dimension applicability, parameter-case identity, and source-case lineage separate so whole-target materialization grows with the declared objects rather than repeating each owner or checker neighborhood quadratically.
- Require bad-case and coverage growth to follow explicit surface-to-failure edges; a missing or ambiguous edge remains a visible depth gap and never expands to every sibling surface.
- Bind the project intent inventory to the current observed model-snapshot fingerprint while retaining source-inventory revision as a separate build-input identity that cannot substitute for the snapshot.
- Project every actually accepted `relation:model-realizes-purpose:<owner>` relation to that exact current owner and reject an omitted, foreign, or merely declared-but-unrealized owner.
- Require every owner semantic specification used by an intent-consuming behavior to bind the exact accepted intent source id and source fingerprint.
- Keep planned checker design, terminal execution disposition, and coverage-contract ownership separate: a parent result or suite label cannot become sibling coverage, and absent exact terminal evidence remains `not_run`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `target-system-blueprint`: Clarify that one model owner may contain several behavior blocks, each with an independent block-local portable contract and case inventory.
- `software-blueprint-readiness`: Require block-local portable member coverage, exact current intent identity and lineage, and prevent owner-wide summaries from satisfying sibling behavior blocks.
- `model-test-alignment`: Require coverage case, checker, oracle, implementation, execution, and coverage-owner identities to remain inside one exact behavior block.

## Impact

The current project-blueprint document schema and behavior-blueprint report schema advance to direct-current versions. The project and self-blueprint compilers, strict document loader, portable-member review, FlowGuard self-model projection, architecture-reduction indexes, intent-to-owner projection, semantic provenance, and focused regression tests are affected. Existing archived OpenSpec changes remain immutable; this corrective change supplies a new intent contribution for the next model-authority revision. Any earlier validation or intent fingerprint predating these clarified requirements remains historical rather than current release evidence.
