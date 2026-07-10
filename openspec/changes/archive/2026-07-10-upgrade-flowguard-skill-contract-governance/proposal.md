## Why

FlowGuard's seventeen skills are concise and useful, but current SkillGuard governance either uses one generic shallow contract for unrelated skills or has no control root at all. The prompts and contracts must express each skill's real activation boundary, native owner, evidence gates, blockers, and claim boundary without creating a second execution framework.

## What Changes

- Give the kernel and all sixteen satellites one consistent entrypoint structure: Purpose, Entrypoint Scope, Local Material Routing, Entrypoint Acceptance Map, Use When, Do Not Use When, Required Workflow, Hard Gates, Output Requirements, and SkillGuard Maintenance.
- Rewrite each skill's content to remain route-specific; shared headings do not permit copied generic routes or identical acceptance contracts.
- Add or align `agents/openai.yaml` default prompts so trigger, route role, main gate, non-owned work, output fields, and claim boundary agree with the route registry and `SKILL.md`.
- Add target-specific semantic contract sources and deterministically generated `work-contract.json`/`check_manifest.json` artifacts for all seventeen skills, including Behavior Commitment Ledger.
- Keep the integration mode `native-integrated`; SkillGuard validates the native FlowGuard route and MUST NOT become a parallel FlowGuard controller.
- Replace cloned field-presence checks with shared evidence-aware contract checks plus per-skill manifests and negative fixtures.
- Preserve prompt-size budgets by moving detailed protocols to directly routed references and generating route indexes rather than adding more text to the kernel.
- **BREAKING**: legacy schema contracts, generic four-route contracts, missing control roots, stale generated contracts, and contracts without native-owner proof will fail SkillGuard certification.

## Capabilities

### New Capabilities

- `flowguard-skill-contract-governance`: Defines the seventeen-skill prompt schema, route-specific contract source, deterministic contract generation, deep SkillGuard certification, and native-integration boundary.

### Modified Capabilities

- `flowguard-skill-kernel`: Tightens kernel entrypoint wording, route-index ownership, size budget, and broad-claim boundaries.
- `flowguard-codex-skill-satellites`: Requires every satellite prompt and `openai.yaml` to declare precise activation, non-use, workflow, evidence, blocker, and handoff semantics.

## Impact

Affected surfaces include all `.agents/skills/*/SKILL.md`, satellite and kernel `agents/openai.yaml`, `.skillguard` control roots, generated contracts/manifests, shared SkillGuard checks, prompt-size tests, route-parity tests, and selected reference protocols. This change depends on canonical membership and route ownership from the first two changes; it does not implement runtime evidence receipts, parent self-governance aggregation, model-runner orchestration, installer behavior, or release publication.
