# FlowGuard

FlowGuard is a lightweight Python framework for model-first function-flow
engineering. It helps AI coding agents and human engineers model a behavior
before editing production code.

FlowGuard is not an LLM wrapper. It does not call model APIs, estimate
probabilities, run Monte Carlo, or randomly sample behavior.

## Core Idea

Model each behavior boundary as:

```text
F: Input x State -> Set(Output x State)
```

If a function block can produce multiple possible outcomes, enumerate all of
them. Compose blocks into a workflow, explore the resulting execution tree, and
check whether any path violates an invariant or scenario expectation.

FlowGuard is especially useful for:

- duplicate side effects;
- missing deduplication;
- idempotency failures;
- repeated processing without refresh;
- cache/source mismatch;
- wrong state owner;
- downstream non-consumable output;
- missing or contradictory decisions;
- retry loops, stuck states, and unreachable success;
- production behavior that diverges from an abstract model.

## Install From Source

```powershell
python -m pip install -e . --no-deps --no-build-isolation
python -c "import flowguard; print(flowguard.SCHEMA_VERSION)"
```

FlowGuard uses only the Python standard library.

## Run Tests

```powershell
python -m unittest discover -s tests
```

## Run Examples

Job matching model:

```powershell
python examples/job_matching/run_checks.py
python examples/job_matching/run_conformance.py
python examples/job_matching/run_scenario_review.py
```

Loop and progress review:

```powershell
python examples/looping_workflow/run_loop_review.py
```

## Minimal Python Sketch

```python
from dataclasses import dataclass

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow, Explorer


@dataclass(frozen=True)
class State:
    records: tuple[str, ...] = ()


class RecordItem:
    name = "RecordItem"
    accepted_input_type = str
    reads = ("records",)
    writes = ("records",)
    input_description = "item id"
    output_description = "record status"
    idempotency = "same item is recorded once"

    def apply(self, input_obj, state):
        if input_obj in state.records:
            yield FunctionResult("already_exists", state, "record_already_exists")
            return
        yield FunctionResult(
            "added",
            State(records=state.records + (input_obj,)),
            "record_added",
        )


def no_duplicate_records():
    def check(state, trace):
        if len(state.records) != len(set(state.records)):
            return InvariantResult.fail("duplicate records")
        return InvariantResult.ok()

    return Invariant("no_duplicate_records", "records are unique", check)


workflow = Workflow((RecordItem(),))
report = Explorer(
    initial_states=(State(),),
    external_inputs=("item-1",),
    workflow=workflow,
    invariants=(no_duplicate_records(),),
    max_sequence_length=2,
).run()

print(report.format_text())
```

## Codex Skill

This repository includes a Codex Skill:

```text
.agents/skills/model-first-function-flow/
```

Use it before non-trivial work involving behavior, workflows, state,
deduplication, idempotency, caching, retries, side effects, or module
boundaries.

In Codex, ask:

```text
Use the model-first-function-flow skill before changing this workflow.
```

For another project, copy the rule from `docs/agents_snippet.md` into that
project's `AGENTS.md`, or install/copy the skill into your Codex skills
directory. The Skill includes a standard-library `toolchain_preflight.py`
helper for checking whether the active Python environment can import the real
`flowguard` package.

## Documentation

- `docs/concept.md`: worldview and math.
- `docs/modeling_protocol.md`: step-by-step modeling process.
- `docs/invariant_examples.md`: common invariant patterns.
- `docs/scenario_sandbox.md`: expected-vs-observed scenario review.
- `docs/conformance_testing.md`: replay abstract traces against real code.
- `docs/loop_detection.md`: stuck states and bottom SCCs.
- `docs/progress_properties.md`: progress and escape-edge cycles.
- `docs/contract_composition.md`: function contracts and ownership.
- `docs/refinement.md`: projection from real state to abstract state.
- `docs/project_integration.md`: connect FlowGuard in another repository.

## Current Limits

- Deterministic finite exploration only.
- No random generation.
- No Hypothesis dependency.
- No probability model.
- No Monte Carlo.
- No complete formal proof claim.
- Not a replacement for unit tests.
- Conformance replay needs a user-written adapter.

## License

MIT.

