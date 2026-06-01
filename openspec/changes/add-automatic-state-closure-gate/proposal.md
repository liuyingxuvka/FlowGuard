# Add Automatic State Closure Gate

## Why

FlowGuard models intentionally explore finite `Input x State -> Set(Output x State)`
spaces, but real systems often receive values outside the author's enumeration:
new enum values, malformed inputs, missing required fields, old schema versions,
invalid terminal replays, and similar "other" cases. When those cases are not
modeled or safely rejected, FlowGuard can produce confidence that is too broad.

This change makes unknown/other handling a default model-first gate instead of
an optional AI reminder or a human-review-only prompt.

## What Changes

- Add a public state/input closure helper that can infer visible finite
  dimensions, generate representative outside-enumeration cases, and review
  whether handling is safe.
- Run the closure gate automatically inside `run_model_first_checks(...)`.
- Keep direct `Explorer` finite and minimal; the new gate is a confidence and
  coverage layer around model-first helper runs.
- Route state closure gaps through the maintenance scan to
  `model_maturation_loop` before broad completion confidence.
- Update docs, templates, and skill guidance so agents treat this as a default
  gate, not an optional pack.

## Impact

- New API: `StateClosurePlan`, `StateClosureDimension`,
  `StateClosureCase`, `StateClosureReport`, `infer_state_closure_plan(...)`,
  and `review_state_closure(...)`.
- Runner reports gain a `state_closure` section.
- Maintenance scan gains `MAINTENANCE_SIGNAL_STATE_CLOSURE_GAP` and
  `MAINTENANCE_ROUTE_MODEL_MATURATION`.
- Version, local editable install, shadow workspace, adoption records, and git
  tag are synchronized after validation.
