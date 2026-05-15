## Context

The existing `model-first-function-flow` Skill already has a post-runtime
model-miss review step. It says to reopen FlowGuard work, classify the miss,
represent it in executable evidence, rerun checks, validate the repair, and
record the result. The problem is not missing process; the problem is that the
current wording leaves too much room for point fixes and over-detailed
classification.

This change keeps the existing flow and tightens only the model-miss review
node.

## Goals / Non-Goals

**Goals:**

- Preserve FlowGuard's lightweight and fit-for-risk style.
- Replace the daily model-miss classification list with five practical types.
- Require one same-class generalized bad case for in-scope misses when
  practical.
- Keep adoption notes short: miss type plus generalized case or reason omitted.
- Pin the behavior with focused docs tests and a small rollout model.

**Non-Goals:**

- Do not introduce a new default evidence-level field.
- Do not introduce a hazard registry or model-upgrade reviewer.
- Do not make model mesh, full coverage matrices, or state writer inventories
  default requirements for ordinary model misses.
- Do not change FlowGuard's public Python API or runtime dependencies.

## Decisions

1. Update the existing post-runtime model-miss review section instead of adding
   a new process.

   Rationale: the existing hook is already in the Skill and workflow. A new
   process would duplicate it and make ordinary use heavier.

2. Use five miss types as the normative daily categories.

   Rationale: the old longer list contained valid details, but too many options
   make agents write explanations instead of improving the model. The five
   categories are broad enough to guide action without taxonomy overhead.

3. Require one same-class generalized bad case when practical.

   Rationale: one extra variant is the smallest useful guard against patching
   only the observed bug. Requiring many variants or a full matrix would be
   disproportionate for ordinary model misses.

4. Keep adoption logging compact.

   Rationale: FlowGuard users already understand that a model is a simulator.
   The useful added evidence is the miss type and the generalized case, not an
   extra confidence taxonomy.

## Risks / Trade-offs

- Five categories may hide rare details -> allow a short free-form note without
  making it a formal category.
- One generalized case may still miss future variants -> this is acceptable for
  the lightweight default; repeated misses can still trigger stronger modeling.
- Documentation-only behavior can drift -> focused tests and a rollout model
  pin the expected wording and hazards.
