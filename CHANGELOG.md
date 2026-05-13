# Changelog

## v0.5.5 - 2026-05-13

- Added default ten-step progress output for `Explorer.explore()` so long
  serial model runs emit start and progress lines on `stderr` while preserving
  `stdout` for reports and JSON pipelines.
- Counted progress by top-level `initial_state x input_sequence` work units and
  kept the run serial and deterministic.
- Added `progress_steps=0` and `FLOWGUARD_PROGRESS=0` opt-outs for strict CI or
  callers that need silent runs.
- Added a FlowGuard rollout model plus focused tests for stderr routing,
  bounded output, small totals, opt-outs, runner inheritance, and report
  stability.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.5.4 - 2026-05-12

- Added Risk Purpose Headers to generated FlowGuard model templates so future
  agents can see the FlowGuard source repository, modeled workflow, guarded
  failure modes, use-before-editing guidance, and companion run command.
- Updated the `model-first-function-flow` Skill and reusable AGENTS snippet so
  AI-created or AI-updated FlowGuard model files carry the same lightweight
  header instead of only saying that they are FlowGuard artifacts.
- Used a local FlowGuard rollout model for this release that catches generic
  link-only headers, partial template coverage, missing Skill/AGENTS guidance,
  missing tests, manifest-style scope creep, and premature publication.
- Added focused tests for generated model template headers and Skill/AGENTS
  header guidance.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.5.3 - 2026-05-12

- Added a local model mesh protocol for projects with three or more FlowGuard
  models, including inventory fields, evidence tiers, required hazards, a prompt
  template, and a completion standard.
- Updated the `model-first-function-flow` Skill so multi-model FlowGuard
  projects must inventory and connect existing models before broad continue,
  release, completion, or production-confidence claims.
- Extended the FlowGuard Skill trigger self-review with a multi-model
  maintenance scenario and a broken variant that catches omitted model-mesh
  checks.
- Updated the reusable AGENTS snippet and modeling protocol docs with the
  model-of-models trigger.
- Schema remains `1.0`; runtime dependencies and CLI templates are unchanged.

## v0.5.2 - 2026-05-10

- Clarified the `model-first-function-flow` Skill around three broad FlowGuard
  scopes: Behavior Flow, Argument Flow, and Decision Flow.
- Added concise modeling hints for behavior state, reader/argument state, and
  decision/commitment state without adding new template families or changing
  the core API.
- Updated the README and reusable AGENTS snippet so users see that the existing
  model templates remain the execution scaffolds for all three flow types.
- Extended the Skill trigger self-review with structured argument and decision
  planning scenarios.
- Schema remains `1.0`; runtime dependencies and CLI templates are unchanged.

## v0.5.1 - 2026-05-09

- Refreshed the public project template so package-generated starter files
  match the richer model-first Skill template with validation, rejection,
  repeated-input handling, and traceability checks.
- Added public-safe Risk Intent + CheckPlan and post-runtime model-miss review
  template scaffolds, including CLI writers for `project-template`,
  `risk-intent-template`, and `model-miss-template`.
- Added template execution tests and privacy-marker checks to keep public
  scaffolds neutral and free of local project details.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.5.0 - 2026-05-08

- Added `FlowGuardFindingLedger`, `FlowGuardFindingLedgerEntry`, and
  `build_finding_ledger` to flatten summary findings and skipped/not-run gaps
  into one coverage-first repair ledger.
- `FlowGuardSummaryReport.finding_ledger` now exposes the ledger, and
  `to_dict()` includes it as machine-readable output for agents.
- Updated the helper-runner self-review with a broken variant that catches
  point-rule patches made before a full finding ledger is built.
- Updated the model-first Skill, AGENTS snippet, check-plan docs, framework
  upgrade guidance, modeling protocol, and README to route FlowGuard or
  LiveFlowGuard self-upgrades through coverage-first triage.
- Schema remains `1.0`; runtime dependencies remain Python standard library
  only.

## v0.4.2 - 2026-05-07

- Added Post-Runtime Model-Miss Review guidance to the model-first Skill:
  runtime, test, replay, or manual-validation failures after a FlowGuard pass
  must reopen the model-first loop instead of becoming direct patch-and-finish
  work.
- Clarified that agents should classify why the prior model missed the issue,
  represent in-scope misses as scenarios, invariants, replays, representative
  traces, or explicit out-of-scope boundaries, then rerun checks before
  validating the repair.
- Updated the reusable AGENTS snippet, modeling protocol, project integration
  notes, README, and Skill doc tests for the new completion gate.
- No core API, schema, runtime dependency, or CLI behavior changed.

## v0.4.1 - 2026-05-07

- Clarified that when no FlowGuard model exists yet, the AI agent should create
  one from the current plan or adapt the included model template instead of
  refusing the task.
- Reframed the model as a fit-for-risk, customer-purpose artifact rather than
  always a minimal script: it should capture the failure modes the customer
  wants to expose and grow as new risks appear.
- Updated the README, AGENTS snippet, modeling protocol, project integration
  notes, and Skill wording to make evolving model scripts part of the public
  onboarding path.
- No core API, schema, runtime dependency, or CLI behavior changed.

## v0.4.0 - 2026-05-02

- Added `RiskIntent` for explicit pre-modeling briefs that name failure modes,
  protected harms, model-critical state, adversarial inputs, hard invariants,
  and blindspots.
- Extended `RiskProfile` with an optional `risk_intent` field and audit
  suggestions for missing or thin Risk Intent Briefs.
- Updated the model-first Skill, modeling protocol, check plan docs, API
  surface docs, and README to make Risk Intent Briefs part of the public
  FlowGuard workflow.
- Fixed README version-section ordering so release notes read newest to oldest:
  `v0.4.0`, `v0.3.1`, `v0.3.0`, then `v0.2.0`.

## v0.3.1 - 2026-05-02

- Added opt-in Mermaid source exporters for representative traces, generic
  state graphs, and loop review graphs.
- Exposed `trace_to_mermaid_text`, `graph_to_mermaid_text`,
  `loop_report_to_mermaid_text`, and `mermaid_code_block` through the public
  FlowGuard reporting helper API.
- Updated the README with English and Chinese Mermaid examples showing how
  FlowGuard turns a risky request into a finite model, reachable traces,
  findings, and optional conformance replay.
- Added a runnable `examples/mermaid_export_example.py` script that prints a
  Markdown Mermaid code block.
- Documented that Mermaid output is copyable text source and remains off by
  default so routine reports stay concise.

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
