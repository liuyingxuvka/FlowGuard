## Context

The previous guidance-compression work made `model-first-function-flow` a
compact router and made satellite `SKILL.md` files concise route shells. Current
measurements show the remaining growth pressure is mainly in implementation
surfaces: `templates.py` is a large mixed template body file, `MODELING_HELPER_API`
is a flat list of hundreds of helper names, and some evidence dataclasses carry
many independent gate concepts as direct fields.

The change is behavior-preserving. Public functions, CLI commands, template
contents, and existing constructors remain compatible unless a later OpenSpec
change explicitly removes a deprecated surface.

## Goals / Non-Goals

**Goals:**

- Reduce large-file and repeated-test maintenance pressure without removing
  current public entrypoints.
- Make internal template ownership route-scoped so future route additions do
  not grow a monolithic file.
- Add grouped helper discovery for API users while keeping existing flat exports
  stable.
- Provide small evidence gate/detail objects that can be adopted gradually.
- Preserve current prompt budgets and satellite route discovery.

**Non-Goals:**

- Do not remove FlowGuard satellite skills.
- Do not break `flowguard.templates` imports, `flowguard.__all__`, or
  `python -m flowguard *-template` commands.
- Do not rewrite all wide evidence dataclasses in one pass.
- Do not publish a remote release unless explicitly requested.

## Decisions

1. **Split template bodies behind the facade.**
   `flowguard.templates` remains the public module. Large route template strings
   move to internal route-scoped modules and are re-imported by the facade.
   This gives a smaller public facade without changing callers or CLI behavior.

2. **Add grouped API registry instead of deleting flat exports.**
   Removing names from `MODELING_HELPER_API` would be breaking. The safer
   contraction is to add route-level groups first, then let future work migrate
   docs and callers to grouped discovery.

3. **Use additive lightweight evidence structures.**
   `RiskEvidenceRow` and `ProcessEvidence` are public constructors. This change
   adds small `EvidenceGate`, `CommandEvidence`, `BackgroundEvidence`, and
   `MeshSplitEvidence`-style objects with conversion helpers before any field
   removal is considered.

4. **Keep prompt compression separate from package structure compression.**
   Prompt hot paths already have budget tests. More wins come from package
   structure, API discovery, and repeated test fixtures.

5. **Use FlowGuard structure and development evidence for public surfaces.**
   Template facade, CLI commands, and flat exports are public entrypoints. The
   implementation must keep parity evidence visible through tests and adoption
   logs.

## Risks / Trade-offs

- **Risk: template split changes generated text.** -> Mitigation: run public
  template tests, CLI smoke tests, and template privacy scans.
- **Risk: grouped API registry drifts from flat exports.** -> Mitigation: add
  tests that registry names are exported and grouped.
- **Risk: lightweight evidence objects become another parallel model.** ->
  Mitigation: make them compatibility helpers and conversion inputs, not a
  replacement claim.
- **Risk: background regression becomes stale after later edits.** ->
  Mitigation: rerun focused tests after final edits and inspect background exit
  artifacts before claiming done.

## Migration Plan

1. Add OpenSpec specs/tasks and FlowGuard self-model for the contraction.
2. Split template text into internal route modules and preserve facade imports.
3. Add grouped API registry constants and tests.
4. Add lightweight evidence structures and focused compatibility tests.
5. Run OpenSpec validation, FlowGuard self-model, focused tests, and background
   full regression.
6. Refresh editable install, sync the shadow workspace, verify imports/tests in
   both locations, record adoption evidence, and commit locally.
