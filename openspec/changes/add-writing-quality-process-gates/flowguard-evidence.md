# FlowGuard DevelopmentProcessFlow Evidence

## Process Model

```text
proposal -> FlowGuard skill/protocol edits -> package metadata update
-> installed skill sync -> full pytest -> downstream LogicGuard semantic check
-> release packaging
```

## Changed Artifacts

- DevelopmentProcessFlow, PlanDetailing, AgentWorkflowRehearsal, kernel,
  UI Flow, and Model-Test Alignment skill guidance.
- DevelopmentProcessFlow protocol reference.
- README, CHANGELOG, pyproject metadata, OpenSpec change files, and FlowGuard
  adoption record.

## Evidence

- `openspec validate add-writing-quality-process-gates --strict`: pass.
- `python -m pytest`: 792 passed.
- `python -m flowguard project-audit --root . --json`: pass on FlowGuard 0.43.0.
- `python .../quick_validate.py` for modified FlowGuard skills: pass.
- Installed FlowGuard skill sync and parity check: pass.
- Downstream LogicGuard installed-FlowGuard diagram semantic check: pass.
- Editable install reports FlowGuard 0.43.0, schema 1.0.

## Freshness Boundary

Later edits to route skills, protocol guidance, installed skill copies,
package metadata, or release notes require rerunning FlowGuard skill docs tests,
full pytest when route semantics change, project audit, and installed parity
before release confidence.
