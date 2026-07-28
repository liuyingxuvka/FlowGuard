## Why

FlowGuard is the reference model-first guard, so its installed skill guidance must not drift from downstream tests or satellite skills. Route-specific diagram language and SkillGuard anti-bypass contracts are currently the most visible drift points.

## What Changes

- Restore explicit model-first diagram intent guidance in the kernel skill.
- Update FlowGuard skill contracts so SkillGuard route checks recognize the duplicate-path boundary.
- Keep source skill copies and installed `.codex/skills` copies synchronized.

## Impact

Affected surfaces: `.agents/skills`, installed FlowGuard skills, downstream LogicGuard semantic guidance tests, package version, release notes.
