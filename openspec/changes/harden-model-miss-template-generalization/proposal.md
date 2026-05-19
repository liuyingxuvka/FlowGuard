## Why

The public `model-miss-template` can still be completed in a bug-shaped way:
the observed issue is represented, but the generated model does not prove that
a same-class variant would also be rejected. This leaves agents able to claim a
model-miss repair while only encoding the known bug.

## What Changes

- Require the public template to encode both the observed issue and one
  same-class generalized bad case.
- Add template checks that fail a broken point-fix-only implementation.
- Make generated notes explain that the known bug is validation or holdout
  evidence, not the model target.
- Keep the change scoped to the public template, focused tests, release notes,
  version metadata, installed Skill sync, and shadow workspace sync.

## Capabilities

### New Capabilities
- `public-model-miss-template`: Covers the public `model-miss-template`
  artifact contract, generated checks, generated notes, and release sync gates.

### Modified Capabilities

## Impact

- `flowguard/templates.py` public template content and generated files
- `tests/test_public_templates.py` and any focused docs/template tests
- `CHANGELOG.md` and package version metadata
- Installed local FlowGuard Skill copy and configured shadow workspace sync
  after release preparation
