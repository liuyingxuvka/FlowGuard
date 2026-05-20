## Context

The FlowGuard kernel already tells agents that ModelMesh owns oversized model
partitioning, TestMesh owns thick or layered validation evidence, and
Model-Test Alignment owns obligation-to-test comparison. The failure observed
in practice happened later: after implementation, validation exposed a thick
model/check, and the agent treated it as a normal failure to push through
instead of a triage signal.

## Goals / Non-Goals

**Goals:**

- Make DevelopmentProcessFlow stop after validation failure and classify the
  failure before further edits.
- Make the three owning satellite skills explicitly accept those classified
  handoffs.
- Preserve parent confidence rules: split child evidence must be consumed by
  the parent before the parent can be called green.
- Keep installed skills and the local shadow workspace in sync with source.

**Non-Goals:**

- Do not add a new global hard gate to `model-first-function-flow/SKILL.md`.
- Do not change package runtime APIs, schema version, release version, tags,
  or GitHub release state.
- Do not claim that every failure must be split; ordinary code failures remain
  ordinary code failures after triage.

## Decisions

- Put the mandatory stop in `flowguard-development-process-flow`.
  Rationale: the failure point is edit -> validate -> fail, which is a
  development lifecycle question rather than initial route selection.
- Put receiving obligations in ModelMesh, TestMesh, and Model-Test Alignment.
  Rationale: those skills own the actual split or alignment work and must make
  parent consumption visible before confidence is claimed.
- Update protocol reference files along with short `SKILL.md` surfaces.
  Rationale: agents that read deeper guidance need the same rule, while the
  kernel remains a compact router.

## Risks / Trade-offs

- More triage text could make simple failures feel heavier. Mitigation: the
  gate explicitly allows ordinary code failures to continue as ordinary fixes
  after classification.
- Source and installed skill copies could drift. Mitigation: copy the updated
  source skill directories to the installed skill root and shadow workspace,
  then verify matching file hashes for the touched files.
