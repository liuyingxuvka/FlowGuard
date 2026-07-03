## Context

FlowGuard currently has two different surfaces:

- the agent-facing skill suite in `.agents/skills/`;
- the executable Python modules and CLI used to run checks, templates, project
  records, and adoption helpers.

Public onboarding still leads with `python -m pip install -e .`, so an agent on
another machine can reasonably conclude that package installation is the main
FlowGuard setup. That conflicts with the local skill ecosystem: installed
Codex skills are normally `SKILL.md` plus scripts, assets, and references, and
do not carry package project files.

The change must preserve executable checks while removing package-first
identity from the public and AI-facing path.

## Goals / Non-Goals

**Goals:**

- Present FlowGuard as an AI-agent skill suite first.
- Make `.agents/skills/` the primary install/read surface.
- Make `model-first-function-flow` the explicit default entrypoint.
- Describe executable FlowGuard code as check scripts/check engine support for
  the skills.
- Keep existing CLI/import checks available for compatibility and local project
  records.
- Synchronize repository skill guidance to the local installed Codex skill
  surface before claiming local active behavior.

**Non-Goals:**

- Do not delete FlowGuard's executable check logic in this change.
- Do not move every `flowguard/` module into skill assets in this pass.
- Do not remove project adoption, audit, upgrade, or template commands while
  current docs/tests still rely on them for check execution.
- Do not claim GitHub publication unless a later release task explicitly
  pushes and verifies the remote state.

## Decisions

### Decision: Skill suite is the public identity

README, AGENTS guidance, and project integration docs will describe FlowGuard
as an AI-agent skill suite with executable check scripts. The first setup path
will be "load `.agents/skills/` and start with `model-first-function-flow`."

Alternative considered: keep Python editable install as the first step but add
a warning. Rejected because it still teaches agents to stop at package setup.

### Decision: Check code remains available through compatibility wrappers

The existing `flowguard/` modules and `python -m flowguard` commands remain
available as compatibility wrappers for executable checks and project records.
Docs will avoid calling that the skill installation.

Alternative considered: delete `pyproject.toml` immediately. Rejected for this
change because version audit, project adoption, template commands, CI, and
existing tests still depend on the CLI/module wrapper. Removing it safely needs
a separate script-entry migration.

### Decision: Local active behavior requires skill-content sync

After repository skill files change, local installed Codex skill copies must be
refreshed or reported as unsynced. Content parity is required before claiming
that this machine's active AI behavior uses the new guidance.

Alternative considered: trust repository changes. Rejected because local
installed skill copies can drift from repository skill files.

## Risks / Trade-offs

- Existing docs and tests mention package installation heavily -> update the
  focused tests so they enforce skill-suite language instead of package-first
  language.
- Keeping `pyproject.toml` may look inconsistent -> explicitly label it a
  compatibility/check wrapper, not the skill install surface.
- Installed skills include generated SkillGuard layers -> verify content by
  key guidance markers rather than byte-for-byte equality when generated layers
  are expected.

## Migration Plan

1. Add OpenSpec specs for skill-suite distribution and affected guidance.
2. Update README English and Chinese quick starts.
3. Update AGENTS and reusable project integration guidance.
4. Update `model-first-function-flow` to identify itself as the skill-suite
   entrypoint and point to sibling FlowGuard skills.
5. Update focused documentation tests.
6. Run OpenSpec validation, focused tests, and practical check-script smoke
   commands.
7. Synchronize affected repository-managed skills to the local installed Codex
   skills directory and verify marker parity.
8. Sync the same changes to the formal Git repository and verify its status.

Rollback strategy: revert this change's docs/spec/tests and restore prior
README/project-integration wording. Do not remove executable check modules as
part of rollback.
