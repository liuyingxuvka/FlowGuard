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
- `model-first-function-flow` Skill Kernel;
- `flowguard-*` satellite skills for mature public owner routes, including UI
  flow structure, code structure, model-test alignment, process flow, model
  misses, ModelMesh, TestMesh, and StructureMesh, plus delegated
  DevelopmentProcessFlow mode skills;
- UI Text Hierarchy Blueprint helpers for the `v0.16.0` public UI text route;
- `AGENTS.md` snippet;
- lightweight adoption log support;
- packaged public risk templates and a portable per-machine local risk template
  library;
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
-> consume the closure contract before broad completion claims
```

For AI agents, the first screen of the method should be a minimum valuable
model:

```text
risky boundary -> protected error class -> public/local template search
-> Input x State -> Set(Output x State)
-> state + side effects + completion evidence + known-bad case
-> run checks -> inspect counterexample
```

That entry remains compact, but it must have teeth. The model should prevent or
expose one real error, record used public/local template ids or a no-match
reason, and include completion evidence plus a known-bad case. Public templates
ship with FlowGuard for every installed computer. Local templates are
per-machine reusable risk cards under a portable user data root, not a required
project-level template library. Complete FlowGuard use requires the closure
contract for the claim being made. Users should not need to understand
FlowGuard's internal KB, private pilots, daily review process, or full
benchmark-maintenance machinery before they can use the tool, but broad
done/release/publish/production-confidence claims still need the current intake,
model, alignment, model maturation, freshness, ledger, and claim-chain support
that their boundary requires.

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
- public release omits the Codex Skill Kernel or satellite triggers;
- public adoption log becomes manual user burden.

## UI Text Hierarchy Blueprint

UI Text Hierarchy Blueprint is the text-facing sibling of UI Flow Structure.
It does not write final marketing copy or localize strings. It inventories the
approved text a UI exposes in each state and region, then assigns roles, owners,
semantic keys, hierarchy priority, duplication rationale, and warning/error
escalation rules.

Text ownership cannot grant display admission. The blueprint consumes
`user_visible` content and revealed-state `user_on_demand` content from the UI
content-visibility plan; `internal` and unclassified content remain outside the
ordinary hierarchy. On-demand text is absent from the default hierarchy until
its explicit reveal event.

This closes a gap that remains after interaction structure is correct: a UI can
have the right controls and still bury the primary state message under helper
text, repeat the same result in three places, leave loading text visible after
success, or hide a blocking warning at a local hierarchy level. The blueprint
keeps headings, labels, CTA text, helper text, status text, empty/loading/
success/failure text, warnings, errors, and assistive text aligned with the UI
state where each message is true.

The package exposes `UITypographyToken`, `UITextElement`,
`UITextHierarchyBlueprint`, `UITextHierarchyReport`, and
`review_ui_text_hierarchy(...)` so this handoff can be checked before
copywriting, visual design, frontend implementation, and accessibility review.
It is not itself a browser or accessibility validation pass, and it does not
mean every semantic hierarchy level should become a separate visual font size.
The handoff should encourage reusable visual text treatments, clear reasons for
visible differences, and soft review of typography noise before implementation
claims.

## UI Flow Structure

UI Flow Structure is the UI-facing sibling of Code Structure Recommendation.
It does not start by arranging buttons on a screen. For an existing UI it first
records the observed surface, but observation does not authorize content. It
then admits state-exposing candidate content before display modeling using
exactly `user_visible`, `user_on_demand`, or `internal`. The first two form one
ordinary user-content group; this is not a user-role taxonomy. Unclassified and
internal content cannot render on ordinary UI, while on-demand content is
default hidden on every mapping target and requires visible/enabled reveal and
return controls, content-bound feedback, and a distinct keyboard/focus event
for hover. User needs are typed and resolvable. Only exact normal labels for
registered, in-scope task-owned controls with no extra state or metadata need
no duplicate content row.

After content admission, it builds or reviews
a UI interaction model: initial UI state, controls, information displays,
events, state transitions, failure/recovery paths, terminal states, state
availability, and intentional redundancy. For complete app-level UI claims, it
also reviews launch-to-terminal journey coverage. For implemented or runnable
UI completion claims, it aligns user-visible feature contracts, reviewed UI
journeys, and browser/desktop/manual click-through evidence. It then derives parent/child
UI topology, first-level persistent menus, second-level contextual regions,
third-level local controls, information-display ownership, overlay hierarchy,
and stable placement rules from that model.

This keeps workflow-heavy UI design from drifting into arbitrary placement. The
visual design and frontend implementation can still be creative, but they
receive a stable structure contract first.

For a complete-product claim, UI Flow Structure also compares the declared
surfaces as one product language. Equal semantic roles reuse the same
typography treatment, component role, navigation pattern, interaction,
feedback, recovery, and transition grammar. A platform, accessibility,
native-control, or safety exception may change presentation with current
evidence, but it cannot change the user's exact intent, active behavior
commitment, selected primary path, visibility class, or external result.

The UI route does not own the runtime path. Business-bearing features,
actions, functional chains, and transitions carry internal
`business_intent_id`, `behavior_commitment_id`, and `primary_path_id` bindings
so several pages or controls can reuse the same proven behavior. Those ids are
model/evidence fields and are not ordinary UI content.

FieldLifecycleMesh supplies every field candidate whose reader reaches the
ordinary UI boundary, regardless of source role. UI Flow Structure owns final
admission; fields with no ordinary-UI reader remain internally accounted.

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

## Skill Orchestrator Collaboration Self-Review

Optional cooperation with spec/SPAC-style planning skills is modeled in:

- `examples/flowguard_skill_collaboration/model.py`
- `examples/flowguard_skill_collaboration/run_review.py`

The model checks:

- FlowGuard still works when no upstream planner is installed;
- a complete upstream handoff can pass after FlowGuard review;
- missing upstream tools fall back to standalone FlowGuard;
- incomplete handoffs block collaboration before execution;
- side effects must be mapped before execution;
- parallel agent work needs explicit ownership;
- skipped checks need reasons;
- counterexamples block execution;
- trivial read-only work does not over-trigger;
- risky work cannot be recorded complete without evidence.

Current review:

```text
total: 12
passed: 5
expected violations observed: 7
unexpected violations: 0
missing expected violations: 0
```

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

Before a public GitHub release, run the product-boundary review, the Skill
trigger review, and the skill-orchestrator collaboration review again. If any
report changes from expected outcomes, fix the architecture or update the model
with an explicit reason before publishing.
