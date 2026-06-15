## ADDED Requirements

### Requirement: Human-operability artifacts stale UI completion evidence
DevelopmentProcessFlow SHALL treat changes to user task coverage, affordance,
action grammar, dialog/window, keyboard/focus, walkthrough, or related skill
guidance as stale for broad UI done/release claims until rerun.

#### Scenario: Action grammar changes after walkthrough
- **WHEN** a UI action grammar, task flow, or region map changes after
  walkthrough evidence was produced
- **THEN** development-process review requires revalidation before reusing the
  walkthrough for human-operable confidence
