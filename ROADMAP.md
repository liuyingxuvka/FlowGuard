# FlowGuard Roadmap

FlowGuard is a model-first function-flow engineering layer for AI coding
agents and human engineers. It is not a normal unit test framework, not a prompt
engineering wrapper, and not an LLM API client.

## Core Worldview

The core mathematical model is:

```text
FunctionBlock:
    F: Input x State -> Set(Output x State)
```

A workflow is a composition of function blocks:

```text
Workflow = F_C o F_B o F_A
```

Because each block may produce multiple possible outputs, a workflow forms an
execution tree or graph. FlowGuard deterministically enumerates those paths
within finite bounds and checks invariants, scenario expectations, conformance
replay, loop/stuck states, progress properties, and function contracts.

## Current Public Capabilities

- Core function-flow abstractions.
- Workflow execution and branching.
- Deterministic exploration.
- Trace and report export.
- Invariant checking.
- Scenario sandbox and oracle review.
- Conformance replay through adapters.
- Loop, stuck-state, and unreachable-success detection.
- Progress checks for escape-edge cycles without forced progress.
- Function contract and refinement helpers.
- Lightweight adoption logging.
- Codex Skill template and AGENTS snippet.
- Public examples for job matching and looping workflows.

## Near-Term Public Goals

1. Keep the public surface small and understandable.
2. Improve examples and docs from real adoption feedback.
3. Add clearer release and integration guidance.
4. Keep CLI wrappers thin and optional.
5. Preserve deterministic checks as the primary safety mechanism.

## Internal Maintenance Goals

The project may also keep private or internal benchmark systems, adoption
reviews, and predictive knowledge records. Those are useful for maintaining
FlowGuard, but they should not be confused with the minimal public product.

## Non-Goals

- No LLM API calls.
- No Monte Carlo.
- No probabilistic modeling.
- No random testing as a replacement for deterministic enumeration.
- No GUI.
- No database.
- No hidden production side effects.
- No claim of complete formal proof.

