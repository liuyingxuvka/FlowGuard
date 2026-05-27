## Context

FlowGuard already has separate routes for post-runtime model misses,
Model-Test Alignment, DevelopmentProcessFlow, TestMesh, and Risk Evidence
Ledger. The current miss workflow blocks point-fix-only modeling by requiring
the observed issue and one same-class generalized bad case, but it does not
force the test side to prove the same generalized class before the miss is
closed.

The design must strengthen the existing route handoff rather than introduce a
new sibling skill or a heavyweight registry.

The follow-up design must also distinguish an ordinary single miss from a
defect family that is recurring or high-risk. A single miss can stay on the
lightweight closure path. A recurring family needs a small, reusable gate that
the Risk Evidence Ledger can consume before any broad "fully fixed" claim.

## Goals / Non-Goals

**Goals:**
- Make model-miss closure require same-class test evidence when the miss is in
  modeled scope.
- Promote recurring or high-risk same-class misses into a defect-family gate at
  the FlowGuard layer.
- Keep observed-bug regression tests visible as necessary but insufficient for
  full closure.
- Require Model-Test Alignment after model-miss repair when new model
  obligations need test proof.
- Require the Risk Evidence Ledger to consume defect-family gate freshness
  before full confidence is claimed for the affected user-facing risk.
- Use DevelopmentProcessFlow to mark old test evidence stale or overclaimed
  after model or test obligation changes.
- Escalate large, slow, layered, or release-only same-class coverage to
  TestMesh.

**Non-Goals:**
- Do not make every model miss require exhaustive testing of infinite input
  space.
- Do not turn Model-Test Alignment into TestMesh.
- Do not add a separate model-miss test skill.
- Do not add a product-specific FlowPilot closure skill for a framework-level
  recurrence problem.
- Do not weaken the existing same-class generalized bad-case requirement.

## Decisions

1. **Closure is a cross-route gate, not a new route.**
   Model-Miss Review still owns the miss classification, observed failure, and
   same-class generalized bad case. Model-Test Alignment owns whether ordinary
   tests prove the repaired model obligations. DevelopmentProcessFlow owns
   whether those rows are still current when closure or release is claimed.

2. **Same-class evidence is explicit.**
   Model obligations can mark themselves as originating from a model miss and
   can require same-class test evidence. Test evidence can name its
   same-class coverage role, so reports can distinguish exact observed
   regression evidence from generalized family coverage.

3. **Point-fix-only tests block full confidence.**
   A current passing test that covers only the observed bug is allowed to
   remain useful, but it cannot satisfy a model-miss obligation that requires
   same-class evidence.

4. **Overclaimed old evidence is not silently reused.**
   If old evidence previously claimed a broad model confidence boundary, the
   alignment report keeps that overclaim visible until new same-class evidence
   replaces it.

5. **Big validation goes to TestMesh.**
   If same-class coverage needs a parent/child suite, slow release-only run,
   background completion artifact, or leaf matrix ownership, the docs and
   skills must route to TestMesh rather than inflating the alignment helper.

6. **Recurrence promotes the claim boundary.**
   When the same class appears again, or when the first miss is high-risk enough
   to threaten a broad user-facing claim, Model-Miss Review records the family
   and `review_defect_family_gates(...)` checks whether the family has been
   promoted, modeled, bounded, and proven.

7. **The ledger decides final confidence.**
   A defect-family gate is not just a note. `RiskEvidenceRow` can require a
   current defect-family gate. Missing, stale, or scoped gate evidence blocks or
   downgrades final confidence just like stale proof evidence does.

## Risks / Trade-offs

- **Risk: Agents over-test every miss** -> Mitigate by allowing representative
  same-class, boundary matrix, property, seeded fuzz, or explicit scoped
  confidence depending on the size of the input/state space.
- **Risk: Agents claim closure from background progress** -> Mitigate through
  DevelopmentProcessFlow and TestMesh rules that distinguish progress from
  final exit/result artifacts.
- **Risk: Duplicate primary tests make obligations look stronger** -> Preserve
  the existing duplicate primary evidence rule and attach variants to child
  obligations, code contracts, or leaf matrix cells when needed.
- **Risk: Existing users only read template notes** -> Update generated
  template notes, README, docs, and skill guidance in addition to helper code.
- **Risk: Defect-family gates become a heavy default** -> Gate promotion only
  when recurrence or high-risk authority/evidence gaps are present; the first
  ordinary miss still uses the lightweight same-class closure path.
