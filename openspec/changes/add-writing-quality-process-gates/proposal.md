## Why

FlowGuard governs process confidence across skills, but writing-heavy workflows
need explicit process gates for quality evidence that can otherwise be skipped:
literature progression, method depth, figure/table argument treatment,
AI-style density, and citation/footnote verification.

## What Changes

- Add process guidance so DevelopmentProcessFlow treats writing-quality ledgers
  as freshness-sensitive artifacts.
- Add FlowGuard satellite guidance for cross-skill academic-writing gates.
- Keep FlowGuard as the coordinator: it does not judge citations or prose truth,
  but it must prevent completion claims when owner-skill evidence is missing,
  stale, skipped, or disposition-only.

## Capabilities

### Modified Capabilities
- `development-process-flow`
- `plan-detailing-compiler`
- `flowguard-agent-workflow-rehearsal`
- `risk-evidence-ledger`
- `flowguard-codex-skill-satellites`

## Impact

Affected surfaces: FlowGuard skill prompts, docs/specs, tests or prompt-grep
checks, installed skill sync, version/changelog, and GitHub release.
