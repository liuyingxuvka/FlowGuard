## Why

FlowGuard's public onboarding still presents editable Python installation as
the first path, which makes AI agents treat package setup as completion and can
hide the actual `.agents/skills/` skill suite. Local evidence from installed
Codex skills shows the normal skill shape is `SKILL.md` plus scripts, assets,
and references, not a standalone package-first install flow.

## What Changes

- Reframe FlowGuard publicly as an AI-agent skill suite with executable check
  scripts.
- Move README and integration guidance so agents load `.agents/skills/` first,
  start at `model-first-function-flow`, and treat sibling FlowGuard skills as
  the complete agent surface.
- Replace package-first onboarding language with check-script language.
- Keep the existing Python CLI/module surface as compatibility for check
  execution and project records, but stop presenting it as the skill install.
- Add tests that prevent README and project integration docs from reintroducing
  `pip install` as the primary FlowGuard setup path.
- Sync repository-managed skill wording to the local installed Codex skill
  copies after validation.

## Capabilities

### New Capabilities
- `flowguard-skill-suite-distribution`: Defines the public skill-suite
  distribution shape, AI-agent install meaning, check-script role, and local
  sync evidence required for active installed behavior.

### Modified Capabilities
- `flowguard-ai-entry-simplification`: AI entry guidance must lead with the
  skill suite and keep package/CLI details behind check-script execution.
- `flowguard-skill-kernel`: The kernel must identify itself as the default
  entrypoint for the FlowGuard skill suite and point agents to sibling skills.
- `flowguard-codex-skill-satellites`: Installed and repository skill sync must
  prove the complete FlowGuard skill suite is visible, not merely that a Python
  package imports.
- `project-adoption-version-gate`: Project integration guidance must separate
  skill-suite availability from check-script/project-record commands.

## Impact

- README English and Chinese onboarding.
- AGENTS managed FlowGuard project rules and reusable agent guidance.
- `.agents/skills/model-first-function-flow/SKILL.md` and its project
  integration reference.
- `docs/project_integration.md` and focused documentation tests.
- Local installed Codex skills under the active user's Codex skills root.
- Shadow workspace and formal Git repository sync checks after implementation.
