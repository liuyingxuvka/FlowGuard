## 1. OpenSpec And FlowGuard Boundary

- [x] 1.1 Validate the OpenSpec proposal, design, specs, and tasks.
- [x] 1.2 Add or update an executable FlowGuard self-model for compatibility
  cleanup classification and installed-skill parity gates.
- [x] 1.3 Run the self-model before production edits and inspect any blocked
  cleanup counterexamples.

## 2. Compatibility Cleanup Audit

- [x] 2.1 Search code, docs, templates, tests, OpenSpec artifacts, and skill
  prompts for old compatibility fields, aliases, wrappers, stale similarity
  wording, and installed-skill drift.
- [x] 2.2 Classify findings as current contract, safety classifier, removable
  legacy, or unknown-needs-evidence.
- [x] 2.3 Select only evidence-backed removable legacy candidates for edits.

## 3. Implementation

- [x] 3.1 Remove obsolete compatibility-only fields, aliases, wrappers, or
  prompt guidance discovered by the audit.
- [x] 3.2 Replace stale similarity or route guidance with `SimilarityHandoff`
  and route-first wording.
- [x] 3.3 Preserve and document compatibility-surface safety classifiers that
  still protect current contracts, public facades, negative legacy tests, or
  unknown surfaces.
- [x] 3.4 Add tests or assertions that prevent removed legacy fields or stale
  installed-skill sync assumptions from returning.

## 4. Validation

- [x] 4.1 Run OpenSpec validation for `clean-legacy-compatibility-fields`.
- [x] 4.2 Run FlowGuard model checks for the cleanup and sync gates.
- [x] 4.3 Run focused tests covering API surface, model similarity integration,
  architecture reduction, skill docs, and public templates.
- [x] 4.4 Run the strongest practical full regression.

## 5. Sync And Git

- [x] 5.1 Refresh editable local install and verify package path, version,
  schema, and current API availability.
- [x] 5.2 Sync repository-managed skills into installed Codex skills and verify
  content parity for all affected FlowGuard skills.
- [x] 5.3 Sync the repository source to
  the local local shadow workspace and verify shadow imports and
  focused checks.
- [x] 5.4 Record FlowGuard adoption evidence and KB postflight.
- [x] 5.5 Commit local git changes and create a local version tag if validation
  and sync evidence pass.
