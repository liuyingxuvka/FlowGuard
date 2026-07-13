## Why

FlowGuard's official installer already preserves unrelated skills in a shared
`.agents/skills/` root, but project suite validation currently treats every
co-located `SKILL.md` directory as a FlowGuard member. This blocks
`project-audit` and `project-upgrade` in valid mixed roots such as a
SkillGuard repository after the canonical seventeen-member FlowGuard suite is
installed.

## What Changes

- Use the official FlowGuard distribution ownership manifest to establish a
  strict FlowGuard membership boundary inside a mixed skill root.
- Continue requiring all seventeen canonical FlowGuard members and all required
  member files.
- Continue rejecting undeclared skills in FlowGuard-reserved namespaces, even
  when a valid ownership manifest exists.
- Report unrelated co-located skills separately instead of counting them as
  FlowGuard suite members.
- Add regression coverage for pure roots, valid mixed roots, missing canonical
  members, invalid ownership evidence, and undeclared FlowGuard-like members.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `flowguard-skill-suite-distribution`: Define strict, ownership-backed suite
  reconciliation for roots that also contain unrelated skills.
- `project-adoption-version-gate`: Allow audit and explicit upgrade to consume
  a passing ownership-backed mixed-root suite result without weakening suite
  blockers.

## Impact

- Affected code: `flowguard/skill_suite.py`.
- Affected tests: suite inventory and project adoption focused tests.
- Public JSON reports gain additive co-located-skill metadata.
- No target SkillGuard repository change, new dependency, or breaking CLI
  option is required.
