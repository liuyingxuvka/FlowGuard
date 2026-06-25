## 1. Prompt Guidance

- [x] 1.1 Update `docs/agents_snippet.md` so non-trivial FlowGuard work shows a short current-situation explanation before or with route-specific snapshots.
- [x] 1.2 Update `.agents/skills/model-first-function-flow/SKILL.md` with the shared current-situation rule.
- [x] 1.3 Update `.agents/skills/flowguard-existing-model-preflight/SKILL.md` with model-search, reuse-decision, duplicate-risk, and downstream-route status guidance.
- [x] 1.4 Update `.agents/skills/flowguard-ui-flow-structure/SKILL.md` with visible-surface, user task, evidence, blindspot, and next-step status guidance.
- [x] 1.5 Update `.agents/skills/flowguard-development-process-flow/SKILL.md` with mode, artifact freshness, invalidation, validation, unsupported-claim, and next-step status guidance.
- [x] 1.6 Add concise current-situation guidance to the medium-priority FlowGuard satellite skills without rewriting their workflows.

## 2. Model And Spec Evidence

- [x] 2.1 Update existing FlowGuard visibility model evidence only as needed to reflect the current-situation requirement.
- [x] 2.2 Validate the OpenSpec change and strict spec set.
- [x] 2.3 Run model visibility and user-facing diagram checks.

## 3. Sync And Install

- [x] 3.1 Reinstall or refresh the editable local FlowGuard install from the Git checkout.
- [x] 3.2 Sync changed repository skills/docs/specs into the `FlowGuard_20260427` shadow workspace without reverting unrelated peer work.
- [x] 3.3 Sync changed installed skill copies under `$CODEX_HOME/skills` where those installed copies exist.
- [x] 3.4 Verify imports, package version, and schema version from both the Git checkout context and the shadow workspace context.

## 4. Regression And Closure

- [x] 4.1 Run focused prompt, skill, OpenSpec, and API surface tests.
- [x] 4.2 Inspect final file status in the Git checkout and shadow workspace, preserving peer-agent changes.
- [x] 4.3 Record FlowGuard adoption/process evidence and KB postflight if the work exposes a reusable lesson.
