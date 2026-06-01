## Why

FlowGuard has gone through many rapid changes, and keeping old fields, aliases,
wrappers, and prompt guidance alive as long-term compatibility paths increases
maintenance burden and lets stale model evidence look current. New FlowGuard
versions should bring an older adopted repository forward into the current
shape instead of teaching the runtime to keep accepting historical shapes.

## What Changes

- **BREAKING** Establish a latest-schema-first policy: normal FlowGuard runtime
  APIs, route reviews, reports, and AI guidance only support the current schema
  and route-first public surface.
- Add a deterministic upgrade capability for old FlowGuard artifacts, project
  records, model evidence, and known old API shapes. Old inputs may be detected
  and upgraded at tool/project boundaries, but they must not remain as parallel
  runtime compatibility paths.
- Extend project upgrade behavior so entering an older FlowGuard-adopted
  repository does more than refresh version records: it scans known FlowGuard
  artifacts, model records, tests, docs, and guidance for old shapes, upgrades
  deterministic cases, and reports blocked cases that need human or route-owner
  review.
- Preserve safety classifiers that protect current contracts, public facades,
  negative legacy tests, runtime-authoritative archives, and unknown surfaces
  from accidental deletion.
- Update docs, templates, and Codex skill guidance so agents default to
  upgrade-or-block behavior rather than preserving legacy fields or silently
  trusting old evidence.

## Capabilities

### New Capabilities

- `artifact-schema-upgrade`: Detects older FlowGuard artifact or project shapes,
  applies deterministic one-way upgrades to the current schema, and reports
  blocked or manual-review cases without enabling long-lived runtime
  compatibility.

### Modified Capabilities

- `project-adoption-version-gate`: Project upgrade SHALL scan and upgrade
  existing FlowGuard models, tests, reports, evidence, and guidance when the
  installed FlowGuard version is newer than the project-recorded version.
- `architecture-reduction`: Compatibility-only runtime shims, old fields,
  aliases, wrappers, and prompt guidance are default cleanup candidates after
  safety classification proves they are not current contracts or required
  evidence.
- `flowguard-ai-entry-simplification`: AI-facing guidance SHALL tell agents to
  use current route-first APIs and upgrade old artifacts instead of preserving
  obsolete fields for backward compatibility.

## Impact

- Affected code: project adoption/version helpers, schema/artifact helpers,
  CLI command dispatch, API exports, and upgrade report types.
- Affected docs and prompts: AGENTS snippets, API surface docs, modeling
  protocol, project adoption docs, and FlowGuard Codex skill guidance.
- Affected tests: project adoption/version gate tests, API surface tests,
  artifact upgrade tests, architecture-reduction cleanup tests, skill docs
  tests, public template tests, and focused CLI tests.
- Affected sync: editable install, installed Codex skill content, shadow
  workspace copy, project audit, FlowGuard adoption log, changelog, and local
  git version/tag records.
