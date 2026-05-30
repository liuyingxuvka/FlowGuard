# Optional Skill Orchestrator Collaboration

This plan describes how FlowGuard should cooperate with SPAC-style planning or
orchestration skills without depending on them.

The baseline rule is:

```text
FlowGuard must remain fully useful without any external spec, SPAC, or
orchestrator skill installed.
```

## Operating Modes

| Mode | When it applies | FlowGuard behavior | Dependency rule |
| --- | --- | --- | --- |
| Standalone mode | No upstream planner exists, or the task is clear enough to model directly. | FlowGuard reads the task, decides applicability, builds or updates a model, runs checks, and reports evidence. | No external skill required. |
| Collaboration mode | A spec/SPAC-style skill has decomposed the task into a plan before execution. | FlowGuard checks the handoff plan for state, side effects, retries, parallel ownership, skipped checks, counterexamples, and completion evidence. | The upstream planner is optional input, not a runtime dependency. |
| Fallback mode | The upstream planner is missing, unavailable, or produced an incomplete handoff. | FlowGuard falls back to standalone mode or blocks only the incomplete collaboration handoff, not FlowGuard itself. | Missing planner must not make FlowGuard unusable. |

## Upgrade Sequence

| Step | Optimization point | Concrete work | Completion signal |
| --- | --- | --- | --- |
| 1 | Preserve standalone FlowGuard | Keep the direct model-first path as the default baseline. | A task with no spec/SPAC skill still runs through FlowGuard checks. |
| 2 | Add a handoff contract | Document the fields an upstream planner should provide: task, steps, state, side effects, parallel ownership, skipped checks, and completion evidence. | A planner-neutral handoff can be written without naming any specific tool. |
| 3 | Teach trigger rules about upstream plans | Extend Skill guidance so FlowGuard recognizes "already decomposed by another skill" as useful context. | Risky upstream plans trigger FlowGuard review; trivial plans can still skip with reason. |
| 4 | Add collaboration self-review scenarios | Add executable scenarios for good collaboration, fallback, missing handoff data, ignored counterexamples, missing ownership, and over-triggering. | The model catches known-bad collaboration hazards before docs or Skill wording are trusted. |
| 5 | Update docs and user-facing guidance | Explain the three modes, the handoff, and the non-dependency rule in project docs and Skill docs. | Users can see that SPAC-style tools are optional accelerators, not prerequisites. |
| 6 | Update tests | Add tests for the collaboration model and docs wording. | Focused tests pass before broader repository checks. |
| 7 | Sync installed and release surfaces | Sync current workspace, editable install checkout, global Skill copy, changelog, version, git, tag, and GitHub release. | Installed package, local checkout, tag, and GitHub release agree on the same version. |

## Handoff Contract

An upstream spec/SPAC-style planner should hand FlowGuard a small plan summary.
The exact file format can stay flexible; these fields are the contract:

| Field | Meaning | Why FlowGuard needs it |
| --- | --- | --- |
| `task_summary` | What the user wants done. | Keeps the modeled boundary clear. |
| `planned_steps` | The ordered or parallel work items. | Lets FlowGuard inspect prerequisites and execution order. |
| `state_fields` | Durable state or project facts the plan changes or relies on. | Prevents hidden source-of-truth drift. |
| `side_effects` | File writes, network calls, publishing, commits, tags, releases, installs, or external actions. | Prevents unchecked irreversible or duplicate effects. |
| `parallel_ownership` | Which agent or skill owns which path, module, or artifact. | Prevents overlapping edits and lost peer-agent work. |
| `existing_model_context` | Relevant FlowGuard models, ownership boundaries, and reuse/extend/new-boundary decision when the task touches an existing modeled system. | Prevents a planner or agent from inventing a parallel subsystem before checking the current model map. |
| `repeat_or_retry_points` | Steps that may run more than once. | Lets FlowGuard check idempotency. |
| `skipped_checks` | Checks the planner proposes to skip, with reasons. | Keeps skipped work visible; skipped is not pass. |
| `completion_evidence` | What evidence proves the plan is done. | Prevents "completed" status without proof. |

In current FlowGuard terms, this neutral handoff can be represented as
`PlanDetail` rows. A rough planner output should be compiled with
`review_plan_detail(...)`; then the same rows can be projected to PlanIntake,
WorkflowStepContracts, DevelopmentProcessFlow, and AgentWorkflowRehearsal. This
keeps collaboration optional while still forcing vague plans to declare state,
side effects, receipts, validation, rework, and claim evidence.

## Collaboration Hazards To Catch

| Hazard id | Possible bug introduced by this upgrade | Required model coverage |
| --- | --- | --- |
| H01 | FlowGuard becomes unusable when no spec/SPAC skill is installed. | Fallback and standalone scenarios must pass without an upstream tool. |
| H02 | A risky upstream plan executes without FlowGuard review. | Risky collaboration scenarios must require model/review evidence before execution. |
| H03 | Side effects are hidden or unmapped, then executed. | Side-effect scenarios must fail unless the handoff maps those effects. |
| H04 | Parallel agents edit overlapping scope without ownership boundaries. | Parallel scenarios must fail unless ownership is explicit. |
| H05 | The planner skips checks without a reason. | Skip scenarios must fail when a skip reason is empty. |
| H06 | FlowGuard finds a counterexample, but the upstream plan continues unchanged. | Counterexample scenarios must block execution. |
| H07 | Trivial read-only work over-triggers FlowGuard and slows normal use. | Trivial scenarios must skip with a reason and no model run. |
| H08 | Completion is recorded without evidence. | Completion scenarios must fail without evidence for risky work. |
| H09 | Collaboration docs imply a hard dependency on a specific external tool. | Documentation tests must require optional/non-dependency wording. |
| H10 | A planner proposes a new subsystem even though an existing FlowGuard model owns the responsibility. | Existing model preflight must record the consulted model boundary, reuse decision, duplicate-boundary risk, and downstream route. |

## Validation Order

1. Run the collaboration model and confirm good plans pass.
2. Confirm every known-bad hazard is caught as an expected violation.
3. Confirm a no-orchestrator fallback scenario still passes.
4. Update Skill/docs only after the model catches the hazards.
5. Run focused docs and model tests.
6. Run the broad repository test suite before release.
7. Test the editable installed checkout after syncing.
8. Only then commit, tag, push, and publish the release.

## Non-Goals

- Do not make FlowGuard an orchestrator.
- Do not manage agent personas or task assignment inside FlowGuard.
- Do not require OpenSpec, SPAC, SPACKit, or OpenSPAC to be installed.
- Do not add per-tool adapters before the planner-neutral handoff is useful.
- Do not treat skipped checks as passed checks.
