# AgentWorkflowRehearsal Protocol

Use `agent_workflow_rehearsal` when the agent's main risk is capability
selection and sequencing across installed Codex skills, tools, plugins, or
external actions. The model answers: "Given the current machine/session, is the
planned skill workflow coherent enough to start?"

This is a sibling FlowGuard route. It can reference OpenSpec, LogicGuard,
FlowGuard satellites, browser tools, GitHub, document plugins, or local custom
skills as inventory entries, but it does not execute or supervise those skills.
Owning skills still perform their own work and validation.

## Trigger

Use this route when:

- the task may require several installed skills, plugins, tools, or external
  actions;
- skill selection or order is unclear;
- skipping a candidate skill could change the safety or evidence boundary;
- staged validation, background checks, install sync, release/publish actions,
  or other side effects need continue and rework gates;
- UI click-through, file/artifact payload validation, AI work-package
  validation, manual review, or installed-skill sync can change the final
  evidence claim;
- a final done/release/publish/full-confidence claim depends on evidence from
  multiple routes.

Skip with a reason for tiny read-only answers, formatting-only edits, direct
command answers, or obvious low-risk single-skill tasks.

## Fresh Inventory

Every invocation starts with a fresh current-machine `SkillInventorySnapshot`.
Cached snapshots may be kept for history or comparison, but never as current
evidence. A valid snapshot should record:

- skill name, description, source, and trigger clues;
- whether the skill is a task candidate or required for the task;
- known capabilities and limitations;
- likely side effects such as publish, push, email, delete, install, migration,
  booking, external browsing, or irreversible account actions;
- validation guidance status: `strong`, `weak`, `missing`, `manual_only`, or
  `external_only`;
- whether the full `SKILL.md` body needs deeper reading before the plan can be
  trusted.

Do not deep-read every skill body by default. Deep-read candidate skills that
affect route choice, side effects, validation obligations, or final evidence
claims.

## Plan Shape

Build an `AgentWorkflowPlan` with:

- selected skills and why they are selected;
- skipped candidate skills with reason, consequence, accepted/not accepted, and
  scope boundary;
- ordered `AgentWorkflowStep` rows;
- required completed step ids and required evidence ids;
- produced evidence ids and continue evidence ids;
- rework gates for failed validation, stale evidence, weak validation, or side
  effect failures;
- compensating checks for weak, missing, manual-only, or external-only
  validation guidance;
- explicit evidence surfaces for UI action coverage, synthetic payload cases
  that exercise real file/artifact/AI work-package surfaces, manual checks,
  installed-skill sync, and long checks when the task touches them;
- for UI full claims, `ui_evidence_roles` must include separate evidence for
  `ui_inventory`, `ui_baseline_semantics`, and
  `ui_implementation_validation`;
- final evidence claim: none, scoped, full, or blocked.

If the work starts from a rough idea or short plan, build `PlanDetail` rows
first and run `review_plan_detail(...)`. Use
`plan_detail_to_agent_workflow_plan(...)` to carry selected skills, ordered
steps, side effects, evidence gates, rework gates, risk flags, and final claim
scope into AgentWorkflowRehearsal.

Use `review_agent_workflow_rehearsal(...)` when the FlowGuard package helper is
available. If only manual review is possible, preserve the same statuses:
`pass`, `needs_revision`, `scoped`, or `blocked`.

## Required Findings

Keep these hazards visible:

- `stale_or_cached_skill_inventory`;
- `empty_skill_inventory`;
- `unknown_selected_skill`;
- `required_candidate_skill_skipped`;
- `candidate_skill_not_accounted_for`;
- `selected_candidate_skill_has_no_step`;
- `skipped_skill_missing_reason`;
- `skipped_skill_missing_consequence`;
- `unaccepted_skip_scope_missing`;
- `workflow_step_missing_order_dependency`;
- `workflow_step_missing_required_evidence`;
- `side_effect_without_prior_evidence_gate`;
- `rework_gate_missing`;
- `selected_skill_has_weak_validation_guidance`;
- `full_claim_missing_final_evidence`;
- `ui_agent_role_evidence_missing`;
- `ui_action_coverage_skill_skipped`;
- `artifact_payload_validation_skill_skipped`;
- `manual_review_boundary_missing`;
- `installed_skill_sync_missing`;
- `trivial_task_overtriggers_skills`.

## Completion Standard

A rehearsal can return `pass` only when:

- the inventory is fresh for the current machine/session;
- required candidate skills are selected, or their skips are explicitly scoped;
- selected candidate skills appear in the ordered plan;
- side-effect or irreversible steps have prior evidence gates;
- meaningful validation steps have rework gates;
- weak validation guidance has compensating checks or a scoped claim;
- the final evidence claim does not exceed planned downstream validation.
- UI full claims include separate real-surface inventory, baseline semantics,
  and implementation-validation evidence roles. These may be produced by
  separate agents, but each role needs an evidence id or boundary before the
  main agent can claim full confidence.

Return `needs_revision` when the plan can likely be fixed by adding route
coverage, order dependencies, skip consequences, or gates. Return `scoped` when
execution can proceed but the claim boundary must stay limited. Return
`blocked` when the plan relies on stale inventory, skips a required skill
without a supported boundary, performs unsafe side effects, or claims full
confidence without final evidence or without the required UI evidence roles.

For final done/release/publish/full-confidence claims, the Risk Evidence Ledger
or owning FlowGuard route must still consume current downstream evidence.
AgentWorkflowRehearsal only checks the planned path to that evidence; it does
not replace that evidence.
