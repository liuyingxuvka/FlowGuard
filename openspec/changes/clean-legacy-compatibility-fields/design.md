## Context

The prior AI-surface work established a route-first shape and introduced
`SimilarityHandoff` so downstream routes no longer need repeated scalar
similarity fields. A follow-up audit found that the repository and shadow
workspace skills were aligned, but the installed Codex skill root still lagged
behind several similarity handoff lines. The user also explicitly approved
removing compatibility-only structures rather than preserving old fields for
backward compatibility.

## Goals

- Remove obsolete compatibility-only fields, aliases, wrappers, and AI guidance
  that are no longer part of the intended FlowGuard surface.
- Preserve compatibility-surface classification as a safety mechanism for
  public entrypoints, negative legacy tests, archive-only evidence, and unknown
  surfaces.
- Make installed Codex skills match repository-managed skills with
  content-level verification.
- Keep Model Similarity Consolidation as the existing owner for A/B/C workflow
  similarity and downstream handoffs.

## Non-Goals

- Do not add a new Codex skill or a separate compatibility-cleanup capability.
- Do not remove safety classifiers that prevent deleting current contracts,
  public facades, or negative legacy tests without replacement evidence.
- Do not perform broad unrelated API cleanup outside the audited compatibility
  and installed-skill drift surfaces.

## Design

1. **Audit before deleting.** Search code, docs, templates, tests, OpenSpec
   artifacts, and skill prompts for legacy compatibility markers such as old
   repeated similarity ids, aliases, wrapper constructors, stale route wording,
   and installed-skill drift.

2. **Classify every candidate.** Treat candidates as:
   - `current_contract`: keep and test.
   - `safety_classifier`: keep because it protects deletion decisions.
   - `removable_legacy`: delete or replace with the current route/handoff.
   - `unknown`: block removal until evidence exists.

3. **Prefer route-first replacement.** If a stale compatibility field points to
   similarity provenance, replace it with `SimilarityHandoff` or route-scoped
   API groups instead of preserving both forms.

4. **Verify active AI behavior.** After skill prompt edits, compare repository
   `.agents/skills`, shadow workspace `.agents/skills`, and installed
   `~/.codex/skills` content for affected skills. Package version checks alone
   are not enough.

5. **Revalidate after writes.** Later code, docs, tests, skill sync, install,
   or shadow copy actions stale earlier evidence. Rerun focused checks after
   the last write and use DevelopmentProcessFlow to keep the claim boundary
   explicit.

## Risks

- **Risk: removing safety classification instead of stale compatibility.**
  Mitigation: compatibility-surface classifiers are protected unless the audit
  proves the classifier itself is obsolete and covered by another current
  guard.

- **Risk: public API break surprises users.** Mitigation: this is a local
  cleanup explicitly approved by the user; tests should still prove current
  route-first APIs and `SimilarityHandoff` remain available.

- **Risk: repository changes do not affect active Codex behavior.** Mitigation:
  installed skill content parity is a required validation artifact before
  claiming completion.

## Validation

- OpenSpec validation for this change.
- Executable FlowGuard model/check for cleanup classification and sync gates.
- Focused tests for API surface, model similarity integration, architecture
  reduction, skill docs, and public templates.
- Full regression if practical.
- Editable install verification, installed skill parity check, shadow workspace
  import and focused test verification.
