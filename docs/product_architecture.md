# FlowGuard Product Architecture

FlowGuard now has two connected systems:

1. a public minimal system for users and project agents;
2. an internal maintenance system for improving FlowGuard itself.

The public system should stay small. The internal system can stay rich because
it is a maintainer feedback loop, not the product surface.

## Public Minimal System

This is the surface that belongs in a future public GitHub release:

- `flowguard` Python package;
- minimal model template;
- modeling protocol;
- invariant cookbook;
- scenario, loop, progress, contract, and conformance examples;
- `model-first-function-flow` Skill;
- `AGENTS.md` snippet;
- lightweight adoption log support;
- small examples such as `job_matching` and `looping_workflow`;
- thin wrappers that preserve the Python API reports.

The user-facing workflow should remain:

```text
define a small function-flow model
-> run executable checks
-> inspect counterexamples
-> revise the design
-> implement production code
-> replay representative traces when production code exists
```

Users should not need to understand FlowGuard's internal KB, private pilots,
daily review process, or full benchmark-maintenance machinery before they can
use the tool.

## Internal Maintenance System

This repository also contains maintainer-only feedback loops:

- 2100-case real-model corpus;
- benchmark hardening and scorecards;
- adoption review documents;
- predictive KB feedback;
- private real-project pilot evidence;
- daily or phase-level review notes;
- self-review models for FlowGuard's own workflow.

These assets prove and improve the method. They should not be presented as the
basic user path, and private pilot evidence must not leak into a public release.

## Boundary Self-Review

The boundary is modeled in:

- `examples/flowguard_product_boundary/model.py`
- `examples/flowguard_product_boundary/run_review.py`

The model checks:

- required public artifacts are included;
- internal/private maintenance evidence stays internal;
- adoption logging remains default and low-burden;
- optional wrappers such as a future CLI can wait until product value is proven.

Current review:

```text
total: 5
passed: 2
expected violations observed: 3
unexpected violations: 0
missing expected violations: 0
```

Broken variants caught:

- internal KB/private pilot evidence exposed publicly;
- public release omits the Codex Skill trigger;
- public adoption log becomes manual user burden.

## Skill Trigger Self-Review

The trigger policy is modeled in:

- `examples/flowguard_skill_trigger/model.py`
- `examples/flowguard_skill_trigger/run_review.py`

The model checks:

- risky architecture/state/workflow tasks trigger the Skill;
- trivial or read-only tasks can skip with a reason;
- ambiguous scope becomes `needs_human_review`;
- production-facing tasks include conformance when required;
- skips must have reasons;
- final evidence cannot remain `in_progress`;
- over-triggering trivial work is treated as a workflow-quality problem.

Current review:

```text
total: 11
passed: 4
expected violations observed: 6
needs human review: 1
unexpected violations: 0
missing expected violations: 0
```

Broken variants caught:

- risky architecture work skips FlowGuard;
- trivial docs work over-triggers FlowGuard;
- conformance is omitted for production-facing work;
- skip is recorded without reason;
- final evidence stays `in_progress`;
- ambiguous redesign scope is silently skipped.

## Product Decision

The product architecture should not collect external project models as reusable
templates. Real projects should build situational models for their current
behavior boundary.

FlowGuard should collect:

- small skeleton templates;
- invariant and modeling patterns;
- adoption evidence;
- friction points;
- counterexamples;
- known limitations.

FlowGuard should not collect:

- private external project code as public templates;
- internal KB history as user-facing material;
- private pilot logs in a public release;
- heavyweight maintenance scorecards as the default user path.

## Next Architecture Work

Before a public GitHub release, run the product-boundary review and the Skill
trigger review again. If either report changes from expected outcomes, fix the
architecture or update the model with an explicit reason before publishing.

