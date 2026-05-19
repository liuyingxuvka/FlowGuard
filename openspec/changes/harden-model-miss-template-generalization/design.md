## Context

The existing model-miss workflow already asks for the observed failure and a
same-class generalized bad case. The public template should make that behavior
hard to bypass by generating a small executable model and checks where the
known bug is treated as holdout validation evidence, while the target model
captures the broader bad-case class.

## Goals / Non-Goals

**Goals:**

- Harden the public template against point-fix-only modeling.
- Keep the template lightweight and understandable for ordinary model misses.
- Pin the behavior with a deliberately broken point-fix-only scenario.
- Make release completion include version/changelog, installed Skill sync, and
  shadow workspace sync.

**Non-Goals:**

- Do not add a heavyweight model-miss registry, coverage matrix, or ModelMesh
  requirement.
- Do not change FlowGuard's public Python APIs beyond the generated template
  content and checks.
- Do not use the known bug itself as the only modeled target.

## Decisions

1. Model the generalized failure class first, then use the known bug as
   validation/holdout evidence.

   Rationale: this forces the generated model to represent the class of bad
   behavior rather than memorizing one observed input. Alternative considered:
   keep only an observed-case field and improve prose. That would not prevent a
   green point fix.

2. Add an explicit broken point-fix-only check.

   Rationale: a negative check makes the template contract executable. The
   check should fail when the workflow accepts only the known issue and omits
   the same-class generalized case.

3. Keep generated notes operational and short.

   Rationale: users need to understand which case trained the model and which
   case validated it. The notes should name the observed issue, the generalized
   class, and the holdout role without adding new process weight.

4. Treat release sync as part of implementation completion.

   Rationale: this repository has a local installed Skill and a shadow
   workspace that can drift from source. The change is not release-ready until
   version, changelog, installed Skill, and shadow workspace evidence agree.

## Risks / Trade-offs

- Template complexity increases slightly -> keep the model fields minimal:
  observed issue, generalized class, holdout role, and completion status.
- A single generalized case may still miss another variant -> repeated misses
  can still escalate to stronger modeling; the default stays lightweight.
- Sync steps can be skipped accidentally -> include them as explicit release
  tasks with verification evidence.
