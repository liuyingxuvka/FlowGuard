## Why

The current post-runtime model-miss review is correct but too broad for daily
use. Agents can still respond to a missed bug by adding only the observed case,
then rerunning the model, instead of making one small same-class improvement.

## What Changes

- Simplify the model-miss classification used in the `model-first-function-flow`
  Skill to five everyday categories.
- Require in-scope model misses to add the observed issue plus one generalized
  same-class bad case when practical.
- Keep adoption notes lightweight by recording only the miss type and the
  generalized case or the reason it was not added.
- Avoid adding a new default registry, reviewer, model mesh requirement,
  coverage-matrix requirement, or evidence-level reporting field.
- Update the reusable AGENTS snippet, modeling protocol, focused docs tests, and
  a lightweight FlowGuard rollout model for the revised behavior.

## Capabilities

### New Capabilities
- `post-runtime-model-miss-review`: Covers the existing post-runtime model-miss
  review behavior: five miss types, same-class bad case representation, and
  lightweight adoption-note evidence.

### Modified Capabilities

## Impact

- `.agents/skills/model-first-function-flow/SKILL.md`
- `docs/agents_snippet.md`
- `docs/modeling_protocol.md`
- `examples/lightweight_model_miss_review/`
- Focused tests that pin the revised lightweight workflow
- Local FlowGuard rollout model for the workflow change
- Changelog, package version, installed Skill copy, shadow workspace, git tag,
  and GitHub Release for the patch release
