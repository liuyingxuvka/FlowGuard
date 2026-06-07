## Context

The current UI Text Hierarchy Blueprint reviews text ownership, role priority,
state scope, duplication, and parent/child prominence. That protects semantic
hierarchy, but the downstream visual implementation can still become noisy when
each semantic role is expressed as a separate visual font size or one-off text
treatment.

The user explicitly does not want a rigid maximum number of font sizes. The
upgrade should make typography complexity a design consideration and review
smell, not a universal numeric gate.

## Goals / Non-Goals

**Goals:**

- Add soft typography hierarchy hygiene to UI generation, FlowGuard UI
  handoff, design review, and design iteration prompts.
- Clarify that semantic text hierarchy can be richer than the final visual
  type treatment set.
- Teach agents to ask whether text differences have a job: primary focus,
  region scan, local control, status, helper, warning, or quiet metadata.
- Adjust examples so typography scale names describe visual jobs instead of
  mirroring hierarchy numbers.
- Keep the change compatible with expressive UI design and intentional
  exceptions.

**Non-Goals:**

- Do not impose a fixed maximum number of font sizes.
- Do not reject expressive editorial, hero, marketing, or brand-heavy pages
  solely because they use a broader visual type scale.
- Do not replace accessibility testing, browser QA, or Figma/design-system
  review.
- Do not change core runtime behavior outside UI guidance, templates, docs, and
  focused tests.

## Decisions

### Use soft hygiene language instead of numeric caps

The prompts should name chaotic text treatments as a design smell: nearby text
with the same job should usually share treatment, differences should be
explainable, and agents should prefer grouping, spacing, weight, color role, or
placement before inventing a new text size.

Alternative considered: enforce a font-size count budget. This is too rigid for
design work and conflicts with the user's intent.

### Update the first-pass generator and the later reviewers

The frontend generator needs the guidance because the first draft is where
typography noise is introduced. The reviewer and iterator also need the same
language because many UI tasks converge through screenshot-analysis loops after
the first pass.

Alternative considered: only update FlowGuard UI Flow Structure. That would
help model-first UI work but would not affect ordinary frontend generation or
post-implementation review.

### Keep FlowGuard's semantic boundary intact

UI Text Hierarchy Blueprint remains a semantic contract. The new guidance adds
handoff hygiene so agents do not treat hierarchy levels as one-to-one visual
font sizes. Runtime checks can still focus on role, ownership, prominence, and
duplication; visual implementation checks can report excessive one-off
treatments as actionable review findings.

Alternative considered: add new model fields for visual font-size counts. That
would overfit a visual-design concern into the semantic model.

## Risks / Trade-offs

- Soft guidance may be missed by agents that only read short skill entries →
  place concise wording in short entries and fuller examples in protocol docs.
- Too much restraint can flatten expressive designs → state that intentional
  exceptions are allowed when they have a clear attention or brand role.
- Tests may become brittle if they assert exact prose → use focused text
  presence checks for key concepts rather than entire paragraphs.
