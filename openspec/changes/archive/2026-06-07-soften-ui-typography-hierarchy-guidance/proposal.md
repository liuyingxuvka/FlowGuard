## Why

UI text hierarchy can pass the current semantic checks while the final UI still
looks noisy because every text role turns into a separate visual treatment.
The route needs soft typography hygiene guidance so agents consider calm
hierarchy, reuse, and intentional exceptions without imposing fixed font-size
limits.

## What Changes

- Clarify that UI text hierarchy tokens are semantic handoff artifacts, not a
  command to create one visual font size per hierarchy level.
- Add soft visual handoff guidance for typography: similar text jobs should
  usually reuse visual treatment, and visible differences should have a clear
  attention or meaning role.
- Update UI design, review, iteration, and FlowGuard UI skill prompts so agents
  treat excessive one-off text styling as a design smell instead of a hard
  numeric failure.
- Update template examples so typography scale names describe visual jobs
  rather than mirroring hierarchy numbers.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `ui-text-hierarchy-blueprint`: add soft visual handoff requirements for
  typography style reuse, intentional visual differences, and design-smell
  reporting without hard font-size caps.
- `flowguard-ui-flow-structure`: clarify that UI structure and text hierarchy
  handoff should guide frontend, Figma, and design-review workflows toward
  calm, reusable text treatments.

## Impact

- Affected Codex skills: frontend design, FlowGuard UI Flow Structure, design
  implementation review, and design iteration.
- Affected project guidance: UI Flow Structure docs and protocol reference.
- Affected templates/tests: UI Flow Structure template examples and focused
  skill/template tests.
- No runtime dependency changes and no hard API requirement to count font sizes.
