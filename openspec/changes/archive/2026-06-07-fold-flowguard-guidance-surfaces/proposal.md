## Why

The first guidance-compression pass shortened FlowGuard's hot-path skill
prompts, but large reference files still duplicate route explanations, long
prompt templates, and exact copies of satellite protocol docs. Agents can still
end up loading too much text before acting, and duplicate copies increase drift
risk during later skill updates.

## What Changes

- Fold repeated route-trigger prose out of the core modeling protocol into a
  compact satellite handoff table.
- Replace duplicate kernel-owned reference protocol copies with short handoff
  stubs where the satellite owns the detailed protocol.
- Move long agent prompt templates out of primary protocol files into
  separately loaded template references.
- Add tests that detect duplicate protocol copies and keep long templates out of
  first-read reference protocols.
- Preserve hard gates, satellite discoverability, reference handoffs, installed
  skill sync, shadow workspace validation, and local git evidence.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `flowguard-ai-entry-simplification`: Extend prompt-budget enforcement beyond
  `SKILL.md` hot paths to heavy reference surfaces and local sync evidence.
- `flowguard-codex-skill-satellites`: Clarify that satellite reference
  protocols are the canonical owner for satellite detail.
- `flowguard-global-routing`: Keep route discovery compact and route detailed
  protocol content through references instead of duplicate inventories.
- `flowguard-skill-kernel`: Require kernel references to hand off to satellite
  protocols instead of carrying duplicate copies of satellite detail.

## Impact

- Affected guidance/docs: `.agents/skills/model-first-function-flow/references/*`,
  selected satellite `references/*`, and this OpenSpec change.
- Affected tests: `tests/test_skill_docs.py` gains checks for duplicate
  reference copies, long inline prompt templates, and compact kernel handoffs.
- Affected validation/sync: OpenSpec strict validation, FlowGuard
  guidance-compression checks, focused skill docs tests, broader regression,
  editable install refresh, installed skill parity checks, shadow workspace
  sync, and local commit/tag evidence.
