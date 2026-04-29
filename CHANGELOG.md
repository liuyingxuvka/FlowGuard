# Changelog

## v0.2.0 - 2026-04-30

- Added optional standard property factories, model quality audit,
  `RiskProfile`, `FlowGuardCheckPlan`, and `run_model_first_checks()` to make
  model-first checks easier for AI coding agents without changing the core
  `Input x State -> Set(Output x State)` model.
- Added deterministic counterexample minimization, scenario matrix generation,
  unified summary reporting, and lightweight domain packs for deduplication,
  cache, retry, and side-effect risks.
- Added helper surfaces for adoption evidence review, state-write inventory,
  low-friction adoption logging, and optional maintenance workflow scaffolding.
- Expanded public examples, benchmark/evidence documentation, self-review
  models, and tests while keeping runtime dependencies at Python standard
  library only.
- Clarified that warnings, skipped checks, and `pass_with_gaps` are confidence
  boundaries, not hard failures and not production conformance claims.

## v0.1.3 - 2026-04-29

- Added model-fidelity calibration guidance to the `model-first-function-flow`
  Skill.
- Added a modeling protocol step that treats FlowGuard models as falsifiable
  simulators of real workflows, not ground truth.
- Clarified that conformance replay and replay adapters must not hide relevant
  production behavior.
- Updated the reusable AGENTS.md snippet to record model-fidelity gaps and
  calibration changes.
- Refreshed the README positioning around FlowGuard as an architecture
  simulator / finite-state workflow simulator, including the hero tagline and
  AI-agent install path.
