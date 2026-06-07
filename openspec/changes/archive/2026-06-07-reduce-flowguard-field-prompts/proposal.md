# Reduce FlowGuard Field Prompts

## Why

The previous guidance fold-down removed duplicated long prompt bodies, but
several FlowGuard skill references still ask agents to fill long lists of
overlapping text fields. Those field lists make ordinary route use slower and
encourage repeated prose without adding proportional evidence quality.

The next contraction should reduce AI-facing field-writing burden while keeping
the fields that protect FlowGuard quality: identity, status, freshness,
evidence ids, external boundaries, skipped/not-run visibility, and scoped gaps.

## What Changes

- Collapse verbose checklist fields into grouped field families in
  Model-Test Alignment, DevelopmentProcessFlow, TestMesh, ModelMesh, and the
  adoption log template.
- Keep uncommon deep-detail fields behind "expand only when applicable"
  guidance instead of making them part of every hot-path prompt.
- Add documentation tests that prevent long prompt field lists from returning
  to the hot path and preserve required quality-critical field families.
- Add a FlowGuard model for the field-prompt reduction lifecycle so done claims
  require field grouping, required evidence preservation, validation, install
  sync, shadow sync, and git evidence.

## Scope

In scope:

- AI-facing skill references and prompt templates under `.agents/skills`.
- `tests/test_skill_docs.py` guardrails.
- OpenSpec artifacts and FlowGuard self-model for this guidance change.
- Installed Codex skill sync and shadow workspace sync for the changed skill
  files.

Out of scope:

- Runtime dataclass/API field removal.
- Behavior changes to FlowGuard helper functions.
- Rewriting peer-agent work in the active `add-maintenance-scan-router`
  change.

## Expected Outcome

Agents should see fewer form-like fields on routine reads, but still preserve
the evidence boundaries that prevent overclaims, stale evidence reuse, hidden
skips, and external-boundary drift.
