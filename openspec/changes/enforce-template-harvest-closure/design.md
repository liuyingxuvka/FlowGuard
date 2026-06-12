# Design

## Product Behavior

The model lifecycle becomes:

```text
search public/local templates
-> build or deepen the minimum valuable model
-> run checks and inspect bad paths
-> perform template harvest closure
-> only then claim complete FlowGuard evidence
```

Harvest closure has four successful dispositions:

- `written`: a new local candidate template was written.
- `merged`: the model strengthened an existing local candidate/template.
- `duplicate_linked`: an existing template already covers the pattern, and the
  model records the template id.
- `not_harvestable`: the model cannot become a reusable template and records an
  accepted reason.

Missing harvest closure is a model-quality gap. It should block broad
completion claims in the same way missing completion evidence or missing
known-bad cases does.

## Data Model

Add `TemplateHarvestReview` in `flowguard.risk_templates` with:

- `disposition`
- `written_template_ids`
- `merged_template_ids`
- `linked_template_ids`
- `not_harvestable_reason`
- `local_root`
- `findings`

Accepted not-harvestable reasons:

- `not_reusable_project_specific`
- `no_new_pattern`
- `missing_known_bad_case`
- `missing_completion_evidence`
- `write_blocked`
- `human_deferred`

Add `review_template_harvest_closure(...)` so checks can report:

- `missing_template_harvest_review`
- `invalid_template_harvest_disposition`
- `missing_harvest_template_id`
- `missing_not_harvestable_reason`
- `unsupported_not_harvestable_reason`

`FlowGuardCheckPlan` gains `template_harvest_review`, and the runner adds a
`template_harvest_review` section whenever a plan has model-creation/deepening
evidence.

## CLI/API

Keep `risk-template-harvest` for direct writes. Add a companion review command:

```text
risk-template-harvest-review
```

The command validates a closure disposition without necessarily writing a
template. This gives AI agents an easy final gate for written, merged,
duplicate-linked, or not-harvestable cases.

Public API additions are route-scoped under `RISK_TEMPLATE_LIBRARY_API` and
`ROUTE_STARTER_API["risk_template_library"]`.

## Prompt And Skill Strategy

Do not make the hot path thick. Replace soft wording such as "when useful" with
one compact rule:

```text
After any new/deepened model, record harvest closure: written, merged,
duplicate-linked, or not-harvestable with an accepted reason.
```

Mirror that rule in direct satellite skills that can create or deepen models,
so direct routing cannot bypass the kernel.

## Validation

Validation must include:

- OpenSpec strict validation.
- FlowGuard self-model showing missing harvest closure is rejected.
- Unit tests for review statuses and CLI command.
- Plan/runner/audit tests proving missing harvest review is visible.
- Skill-doc tests proving the hot path is hard but still within prompt budgets.
- Full pytest as practical.
- Install, installed-skill, shadow workspace, adoption log, and local git
  synchronization checks.
