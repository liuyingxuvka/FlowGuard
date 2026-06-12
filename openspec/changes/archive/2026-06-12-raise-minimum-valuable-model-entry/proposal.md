## Why

FlowGuard's AI entry path became too thin: agents can produce a tiny happy-path
model that technically runs but does not prevent a meaningful defect. The entry
needs a minimum valuable model standard and a lightweight reusable template
memory so similar risks get deeper over time on every installed machine.

## What Changes

- Replace the "thin default path" for model-first AI work with a "minimum
  valuable model" entry: the first useful model must name the real error class,
  model the state/side effects/evidence that make the error visible, and include
  at least one representative known-bad case.
- Add a route for reusable risk templates with two default layers:
  packaged public templates shipped with FlowGuard, and a per-machine local
  template library discovered through a portable default path or environment
  override.
- Require model creation/deepening entrances to search public and local
  templates before generating a model, then record used templates or an explicit
  no-match reason.
- Add post-run template harvesting so a successful model with a reusable error
  class, modeled state/side effects/evidence, and a known-bad case can be saved
  as a local candidate template.
- Extend Risk Intent and CheckPlan helper surfaces so template reuse, protected
  error classes, completion evidence, side effects, and known-bad cases are
  structured fields instead of prose-only guidance.
- Strengthen audits, summary sections, public starter templates, skills, docs,
  and tests so success-path-only models remain visible as gaps.
- No project-level template library is introduced as a default layer in this
  change. Project/team template sharing can be added later as an explicit
  capability if needed.

## Capabilities

### New Capabilities
- `risk-template-library`: Public packaged risk templates, portable per-machine
  local risk template storage, search, merge, and harvest candidate behavior.
- `minimum-valuable-model-entry`: The default AI model-first entry standard
  requiring a protected error class, modeled state/side effects/evidence, and a
  known-bad case.

### Modified Capabilities
- `model-first-function-flow`: Replace thin default entry requirements with the
  minimum valuable model entry and risk-template pre/post hooks.
- `flowguard-template-structure`: Upgrade starter templates so the basic public
  template demonstrates a real completion-evidence and known-bad-case gate.
- `flowguard-skill-kernel`: Keep the kernel compact while routing template
  search/harvest as a normal model creation/deepening gate.
- `flowguard-api-registry`: Expose the risk template library helpers through
  route-scoped public API groups without making them core model primitives.
- `model-similarity-consolidation`: Let model signatures carry reusable risk
  template, evidence-gate, and known-bad-case ids so similar models can reveal
  missing depth.

## Impact

Affected surfaces include `RiskIntent`, `FlowGuardCheckPlan`, model-quality
audit, `run_model_first_checks`, summary sections, public templates and CLI,
template text modules, model similarity signatures, docs, installed Codex skill
guidance, OpenSpec specs, tests, local install sync, shadow workspace sync, and
adoption logs. The implementation remains standard-library-only and stores
local templates as ordinary files under a portable per-user FlowGuard data root.
