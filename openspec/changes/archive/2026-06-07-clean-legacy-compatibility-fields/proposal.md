## Why

FlowGuard's AI-facing surface was recently shortened, but old compatibility
wording and installed-skill drift can still make agents preserve obsolete
fields or miss the current similarity handoff route. This change removes
provably obsolete compatibility surfaces while preserving the safety checks that
protect current public contracts.

## What Changes

- **BREAKING** Remove old compatibility-only fields, aliases, or guidance that
  have been replaced by `SimilarityHandoff` or route-scoped API discovery.
- Add evidence-based cleanup checks that distinguish removable legacy surfaces
  from current public contracts, negative legacy tests, and unknown surfaces.
- Synchronize repository-managed FlowGuard skills into installed Codex skills
  and verify content-level parity, not just package version parity.
- Update docs and tests so AI agents use the current route-first flow and do
  not rely on stale compatibility wording.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `architecture-reduction`: clarify that compatibility cleanup may remove
  obsolete fields or guidance only after classification proves they are not a
  current contract or required safety evidence.
- `flowguard-ai-entry-simplification`: require installed-skill content parity
  checks after skill or routing changes so active AI behavior matches the
  repository-managed guidance.

## Impact

- Affected code: FlowGuard compatibility/similarity handoff models, public API
  exports, tests, and any obsolete alias or wrapper paths discovered by audit.
- Affected prompts/docs: `.agents/skills/*/SKILL.md`, `docs/agents_snippet.md`,
  `docs/api_surface.md`, and route reference docs that mention stale fields.
- Affected validation/sync: OpenSpec validation, FlowGuard model checks,
  focused unit tests, full regression when practical, editable install refresh,
  installed Codex skill sync, shadow workspace sync, adoption logs, and local
  git commit/tag evidence.
