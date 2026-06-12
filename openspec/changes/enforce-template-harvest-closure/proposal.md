# Enforce Template Harvest Closure

## Summary

Make template harvest closure mandatory after new or materially deepened
FlowGuard models. A model can no longer finish with only template search and a
minimum valuable contract; it must also record whether reusable local template
experience was written, merged, linked to an existing template, or explicitly
not harvestable with an accepted reason.

## Motivation

FlowGuard 0.44.0 added public/local risk-template search and local candidate
harvest. The remaining gap is behavioral: the hot path still says to harvest a
candidate "when useful", which lets agents skip the learning loop after model
creation or deepening. That weakens the local machine's accumulated template
library and makes later similar work start from scratch.

## Scope

- Add a structured template-harvest closure review.
- Require harvest closure for new or deepened model work before broad
  FlowGuard completion confidence.
- Keep the default storage model portable: packaged public templates plus a
  per-machine local library, with no project-only or developer-path default.
- Update AI-facing skills, snippets, templates, audit/runner output, CLI/API,
  docs, and tests so agents cannot miss the closure step.
- Sync installed skills, editable install, shadow workspace, adoption records,
  and local git version after validation.

## Non-Goals

- Do not force every model to write a new template card. Duplicate or
  project-specific models may be linked or marked not harvestable with a
  concrete reason.
- Do not create a separate Codex satellite skill for template harvest. The
  guard must be embedded into every model-creation/deepening route.
- Do not push to remote GitHub or publish a release unless separately
  requested.
