# API Surface Layers

FlowGuard has one core model and several optional helper layers. The layers are
named so AI coding agents can choose the smallest useful path without treating
every helper as a required gate.

The executable core is still:

```text
FunctionBlock: Input x State -> Set(Output x State)
Workflow = composed FunctionBlocks
Explorer = deterministic finite exploration
```

The minimum useful path remains:

```text
State + FunctionBlock + Invariant + Explorer
```

## Core API

Core APIs are the stable objects needed to build and run a direct finite model:

- `FunctionBlock`, `FunctionResult`
- `Invariant`, `InvariantResult`
- `Workflow`, `WorkflowPath`, `WorkflowRun`
- `Explorer`, `ReachabilityCondition`, `enumerate_input_sequences`
- `CheckReport`, `InvariantViolation`, `DeadBranch`, `ExceptionBranch`,
  `ReachabilityFailure`
- `Trace`, `TraceStep`

These APIs should stay small and backward compatible. New helpers should not
change the meaning of `FunctionBlock`, `Workflow`, or `Explorer`.

## Modeling Helpers

Modeling helpers reduce boilerplate around common bug classes:

- property factories such as `no_duplicate_by`, `at_most_once_by`,
  `cache_matches_source`, `require_label_order`, and `forbid_label_after`;
- state write inventory guidance for fields named by invariants;
- maintenance workflow templates for recurring multi-role maintenance systems;
- scenario review and `ScenarioMatrixBuilder`;
- deterministic counterexample minimization;
- optional domain packs such as `DeduplicationPack`, `CachePack`, `RetryPack`,
  and `SideEffectPack`;
- optional loop, progress, contract, conformance, and replay helpers.

These helpers return or consume the same core model objects. They are useful
shortcuts, not a new modeling language and not mandatory for valid FlowGuard
use.

## Reporting Helpers

Reporting helpers help an AI agent explain what was checked and what was not:

- `RiskProfile` and `FlowGuardCheckPlan`
- `run_model_first_checks`
- `audit_model`
- `FlowGuardSummaryReport`
- adoption logging and `audit_flowguard_adoption`
- thin adoption logging commands such as `adoption-start` and
  `adoption-finish`
- schema and JSON artifact helpers

Warnings, gaps, skipped sections, and `not_run` sections are confidence
boundaries. They should not be hidden, but they also should not be treated as
hard failures unless the underlying section actually failed.

## Evidence And Internal Validation

Evidence APIs are used to keep FlowGuard itself honest:

- evidence baseline reports;
- benchmark scorecards and benchmark coverage audits;
- problem corpus and executable corpus reports;
- pytest/template helpers used by examples and framework validation.

These tools are valuable for FlowGuard maintenance. Ordinary project models do
not have to run the full evidence baseline, problem corpus, or benchmark suite
before using `Explorer` or `run_model_first_checks`.

## Introspection Constants

The package exports lightweight grouping constants:

- `CORE_API`
- `MODELING_HELPER_API`
- `REPORTING_HELPER_API`
- `EVIDENCE_API`
- `API_SURFACE`

They are descriptive lists of exported public names. They do not enforce a
runtime policy and they do not make helper layers mandatory.

## Agent Guidance

Start with the core path when it is enough. Add helpers only when they clarify a
real risk, reduce repetitive code, or improve reporting honesty. Keep skipped
checks visible. Do not claim production confidence from a model-only pass unless
conformance replay or equivalent real-code evidence exists.
