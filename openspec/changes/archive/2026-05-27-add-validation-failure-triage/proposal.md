## Why

Agents can finish an edit, run validation, see a failed or oversized check,
and keep patching toward green without first asking whether the failure is a
signal to split a model, split validation evidence, or realign model
obligations with tests. FlowGuard already has the satellite skills for those
jobs, but DevelopmentProcessFlow needs a stronger post-validation triage gate
so the right satellite is invoked at the failure point.

## What Changes

- Add a DevelopmentProcessFlow validation-failure triage gate for failed,
  stale, oversized, or parent/child evidence-sensitive validation.
- Keep the FlowGuard kernel route map unchanged; this change does not add a
  new global routing gate.
- Add handoff rules for ModelMesh, TestMesh, and Model-Test Alignment when
  DevelopmentProcessFlow classifies a failure as model-too-thick,
  test-too-thick, model-test mismatch, stale evidence, or parent/child
  evidence not reattached.
- Add focused skill-doc tests so this behavior cannot silently regress.
- Sync repository skill guidance into the installed Codex skill directory and
  the local shadow workspace after validation.

## Capabilities

### New Capabilities

- `validation-failure-triage`: FlowGuard staged validation work must classify
  failed or oversized validation before continuing and route mesh/alignment
  cases to the owning satellite skill.

### Modified Capabilities

None.

## Impact

- Codex skills under `.agents/skills/flowguard-development-process-flow`,
  `.agents/skills/flowguard-model-mesh`,
  `.agents/skills/flowguard-test-mesh`, and
  `.agents/skills/flowguard-model-test-alignment`.
- Matching protocol references used by the installed satellite skills.
- Focused skill-doc tests.
- Installed skill mirrors under the configured Codex skills directory.
- Local shadow workspace configured for this FlowGuard checkout.
