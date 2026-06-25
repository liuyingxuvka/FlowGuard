## Context

FlowGuard currently has two overlapping visibility rules:

- `flowguard-model-visibility` requires user-visible model snapshots for
  non-trivial FlowGuard work.
- `user-facing-model-diagrams` allows Mermaid diagrams when an abstract model
  would otherwise be hard to understand.

Those rules help users see the model shape, but they do not explicitly require
the agent to state the immediate work status in plain language. The user impact
is that a diagram can appear useful to an expert while still leaving a
non-technical user unsure what FlowGuard is doing.

## Goals / Non-Goals

**Goals:**

- Add a short current-situation explanation to existing FlowGuard visibility
  guidance.
- Keep the explanation lightweight enough for normal chat use.
- Apply the rule through existing shared and satellite skill prompts.
- Preserve optional diagrams for cases where they clarify a non-trivial model.
- Verify the prompt/spec change with existing model visibility and diagram
  checks.

**Non-Goals:**

- No new FlowGuard runtime event system.
- No new public Python API, dependency, schema version, or report format.
- No requirement that tiny or direct-command tasks show a diagram.
- No claim that a diagram or status note is validation evidence.

## Decisions

1. Use a plain-language note instead of a new workflow.

   The note has four parts: what is being checked, why it matters, current
   evidence or gaps, and next step. This matches the user's request for more
   visible progress without making FlowGuard heavier.

2. Update existing prompt surfaces instead of adding a new capability.

   The change touches the shared agent snippet, the model-first kernel, and the
   FlowGuard satellite skills that already own the relevant routes. This avoids
   parallel ownership and keeps existing route selection intact.

3. Keep diagrams optional but better grounded.

   When a diagram is useful, it should sit beside the current-situation note
   and show major states, branches, evidence, gaps, and claim boundaries. The
   note can stand alone when text is clearer than a diagram.

4. Treat installation and shadow workspace sync as part of completion.

   The editable install points to the Git checkout while the current work
   directory can shadow imports. Completion therefore requires checking the Git
   checkout, editable install, installed skill copies, and the shadow workspace.

## Risks / Trade-offs

- Extra chatter in trivial tasks -> Keep the rule limited to non-trivial
  FlowGuard work and user-suppressed cases.
- Agents mistake the note for validation -> Repeat that notes and diagrams
  explain; executable checks and explicit evidence still validate.
- Prompt drift across installed and repository skills -> Sync repository
  `.agents/skills`, installed `$CODEX_HOME/skills`, and the shadow workspace
  before final confidence.
- Parallel agents mutate files during validation -> Inspect final file status
  and avoid reverting unknown changes.
