# Changelog

## v0.3.0 - 2026-04-30

- Expanded the `model-first-function-flow` Skill from coding/repository-only
  framing to coding, repository, and process-design work.
- Added `process_preflight` mode for non-code or mixed workflows that need
  validation, adjustment, observation, or loss-prevention review before action.
- Clarified that booking, purchase, publication handoff, operational runbook,
  data migration, support escalation, and multi-agent coordination flows can be
  modeled when they have meaningful state, side effects, external dependencies,
  rollback concerns, or irreversible cost.
- Preserved the skip boundary for trivial reversible tasks and clarified that
  non-code process models are risk-discovery preflights, not proof of real-world
  prices, availability, policies, or vendor behavior.
- Updated the README, AGENTS snippet, Skill documentation, and Skill doc tests
  for the broader process-preflight scope.

## v0.2.1 - 2026-04-30

- Simplified the `model-first-function-flow` Skill adoption-note wording so
  agents leave a short plain-language record instead of treating adoption
  logging as a heavy field checklist.
- Clarified that the adoption CLI can help create the log entry, but it is not
  a substitute for a short human-readable note when the model found something
  important.
- Updated the reusable AGENTS snippet with the same lighter note guidance.
- Clarified that `SCHEMA_VERSION` / `python -m flowguard schema-version`
  reports the artifact schema version, not the GitHub/package release version.

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
