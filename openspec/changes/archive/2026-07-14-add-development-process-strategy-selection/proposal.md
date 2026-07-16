## Why

DevelopmentProcessFlow can currently prove ordering, ownership, freshness, and completion, but it does not compare multiple outcome-equivalent ways to perform the work. That gap lets a valid plan still be wasteful—for example, repeatedly stopping at the first diagnostic failure and repairing locally when a bounded diagnostic campaign and one root-cause repair batch would produce the same safe outcome with less rework.

## What Changes

- Add a DevelopmentProcessFlow-owned strategy-selection capability that first proves hard outcome, evidence, safety, and authority equivalence, then compares only the eligible candidates.
- Represent multi-objective process cost explicitly (effort, elapsed time, repeated work, coordination, risk, and information value) and return a deterministic non-dominated recommendation with an honest optimality boundary.
- Support `fail_fast`, `collect_all`, `focused_first`, `bounded_collect`, `parallel_shards`, and `adaptive` strategies without making any one strategy universally mandatory.
- Add diagnostic campaigns, failure observations, clusters, root-cause hypotheses, repair batches, and dynamic re-evaluation so related findings can be repaired together while urgent or unsafe failures can still stop immediately.
- Extend DevelopmentProcessFlow and its simulator with an internal `strategy_selection` mode while retaining `flowguard-development-process-flow` as the single public process entry.
- Project campaign completeness and early-stop evidence into TestMesh, selected strategy and re-evaluation gates into PlanDetailing, and obligation/cluster bindings into Model-Test Alignment without transferring native ownership.
- Register one new `development_process` Behavior Commitment and expose current Python API/report types; no second public skill, provider task engine, fallback success path, or product-UI projection is added.
- Roll out recommendation enforcement in stages: shadow/advisory, opt-in, then conditional default only when current evidence satisfies the declared policy.

## Capabilities

### New Capabilities

- `development-process-strategy-selection`: Outcome-equivalence gates, strategy candidates, cost/Pareto comparison, diagnostic campaigns, repair batching, re-evaluation, and bounded optimality claims.

### Modified Capabilities

- `development-process-flow`: Consume one selected strategy and its current decision evidence before execution/revalidation claims.
- `development-process-simulator`: Add the internal strategy-selection phase and preserve blocked/not-run paths.
- `test-evidence-mesh`: Record planned/executed diagnostic coverage, enumeration completeness, early-stop reason, and campaign/cluster identities without executing tests.
- `plan-detailing-compiler`: Project strategy, campaign, repair-batch, and re-evaluation gates into detailed process steps.
- `model-test-alignment`: Bind failure clusters and repair batches to the obligations and code contracts they can actually satisfy.
- `behavior-commitment-ledger`: Register and validate the new development-process behavior promise and typed cross-owner relations.
- `flowguard-api-registry`: Export canonical strategy-selection inputs, reports, and review functions from the existing FlowGuard package facade.
- `flowguard-codex-skill-satellites`: Teach the existing DevelopmentProcessFlow skill to use strategy selection without adding a new public route.
- `flowguard-skill-suite-distribution`: Keep source, formal/shadow, and installed DevelopmentProcessFlow guidance current under SkillGuard supervision.

## Impact

The change affects the executable FlowGuard model inventory, `flowguard` process/simulator/TestMesh/PlanDetailing/alignment APIs, package exports, templates and documentation, Behavior Commitment and field-lifecycle records, focused and known-bad tests, benchmark evidence, and the DevelopmentProcessFlow managed skill contract. OpenSpec remains the requirement/task/archive authority, SpecWorkPackage remains the receipt/session authority, and remote publication is outside this change.
