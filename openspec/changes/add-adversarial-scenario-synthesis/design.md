## Context

FlowGuard already has the pieces needed for proactive bug discovery:
`ScenarioMatrixBuilder` creates deterministic generated scenarios, helper packs
attach common invariants and generated scenarios, Scenario Sandbox preserves
expected-vs-observed status, conformance replay checks real implementations, and
Model-Test Alignment plus Risk Evidence Ledger prevent evidence overclaims.

The current matrix builder is intentionally small: single input, repeated same
input, pairwise order, and ABA. That is useful but does not directly name the
risk behind generated routes, and packs cannot currently ask for richer
challenge patterns such as stale-source replay, terminal replay, or partial
failure retry shapes.

The first implementation must not stop at static input shapes. Static challenge
patterns are a fallback; the model-derived layer must also inspect Explorer
reports and turn real model evidence into challenge scenarios.

## Goals / Non-Goals

**Goals:**

- Add bounded adversarial scenario synthesis to the existing
  `ScenarioMatrixBuilder` API.
- Add model-derived synthesis from actual `CheckReport` traces, violations,
  dead branches, and exception branches.
- Preserve generated scenarios as ordinary `Scenario` objects with the existing
  default `needs_human_review` expectation.
- Add risk tags and notes to explain why each generated route is high-risk.
- Let existing packs opt into richer challenge routes without adding a new
  testing workflow.
- Keep sequence limits and scenario limits authoritative.
- Add tests and docs that make the no-overclaim rule explicit.

**Non-Goals:**

- Do not introduce random, probabilistic, or LLM-generated scenario generation.
- Do not replace Scenario Sandbox, conformance replay, Model-Test Alignment, or
  Risk Evidence Ledger.
- Do not claim generated routes are test evidence until they have explicit
  expectations and current validation.
- Do not require users to adopt helper packs; direct `ScenarioMatrixBuilder`
  usage remains valid.

## Decisions

1. **Extend `ScenarioMatrixBuilder` instead of adding a new subsystem.**

   Rationale: The existing builder is already consumed by packs and already
   returns normal `Scenario` objects. Extending it keeps downstream review,
   replay, alignment, and ledger behavior unchanged.

   Alternative considered: a separate adversarial testing runner. Rejected
   because it would duplicate status semantics and make evidence accounting
   harder.

2. **Use deterministic named challenge patterns only as a fallback layer.**

   Rationale: FlowGuard models must stay finite and inspectable. Named patterns
   let users understand why a route exists and let tests assert exact output.

   Alternative considered: state-space search over every possible sequence.
   Rejected for the first version because it can explode quickly and would need
   a separate minimizer/evidence story.

3. **Synthesize model-derived challenges from Explorer reports.**

   Rationale: A route is useful when FlowGuard evidence explains why it is
   dangerous. `synthesize_challenge_scenarios_from_report(...)` consumes actual
   `CheckReport` evidence: invariant counterexamples, dead branches,
   exceptions, repeated labels, repeated blocks, interleaved replay, state
   revisits, and risk-signaling trace text. The output is still ordinary
   `Scenario` objects.

4. **Represent risk explanation in scenario tags and notes.**

   Rationale: `Scenario` already supports tags and notes. Using those fields
   avoids changing Scenario Sandbox data structures while still surfacing the
   reason a route is dangerous.

   Alternative considered: adding a new scenario metadata object. Deferred until
   a real consumer needs structured fields beyond tags and notes.

5. **Make packs opt into the richer matrix through one builder call.**

   Rationale: Packs should remain recipes over existing primitives, not hidden
   workflows. Calling `challenge_patterns(...)` keeps their behavior readable.

6. **Keep generated routes candidate-only by default.**

   Rationale: FlowGuard already has the invariant that generated scenarios must
   not become passing evidence without a human/domain oracle. This feature must
   strengthen that rule rather than weaken it.

## Risks / Trade-offs

- **Risk: Too many generated routes.** -> Keep `max_sequence_length` and
  `max_scenarios` as hard caps, and use a small deterministic default pattern
  set.
- **Risk: Users mistake generated routes for proof.** -> Default expectation
  stays `needs_human_review`; tests and docs cover this explicitly.
- **Risk: Static patterns get mistaken for model intelligence.** -> The
  first-class model-derived helper must consume Explorer evidence and reports
  should distinguish input-shape scaffolding from model-derived challenges.
- **Risk: Pack behavior changes by producing more scenarios.** -> Existing
  scenario limits bound output; tests check expected shapes rather than
  unbounded counts.

## Migration Plan

1. Add the builder method and tests.
2. Update packs to call the method after their existing patterns.
3. Update docs to describe the proactive bug-discovery workflow.
4. Run focused tests, OpenSpec validation, FlowGuard examples, and broader
   regression as practical.
5. Sync editable install and the shadow workspace after source validation.

Rollback is straightforward: remove the added builder method usage from packs,
then remove the method and tests. No persisted data format changes are involved.

## Open Questions

- Whether future reports need a structured `risk_reason` field on `Scenario`.
  This version intentionally avoids that data-model change.
- Whether a later model-search layer should generate routes from actual graph
  counterexample candidates. This version starts with deterministic patterns on
  the existing matrix path.
