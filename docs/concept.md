# FlowGuard Concept

FlowGuard is an AI-agent skill backed by an executable check engine. The skill tells an agent when to model a risky workflow, which of its capabilities applies to the problem, which models and tests have to run, and where a safe claim must stop. The Python engine makes those checks executable before or after production code changes.

It is not a normal test framework, not a prompt-engineering trick, and not an LLM wrapper. It does not call model APIs. Its purpose is to make function-flow behavior, process order, staleness, and claim boundaries explicit, finite, repeatable, and checkable. The installable product surface is the single `flowguard` tree under `.agents/skills/`; each capability's short guide lives below `references/domains/`, while the `flowguard` package and scripts remain the executable support layer.

## Three Different Meanings Of Green

FlowGuard keeps three kinds of "green" separate because each answers a different question:

1. **Written guidance:** Does the skill or a capability guide say the right things and point at material that exists? This is a static reading, not a run.
2. **Executed check:** Did the real model or test actually run against the current code and pass? Only running it shows that.
3. **Current map:** Does `.flowguard/map.json` still describe the code (`python -m flowguard map check`, which flags a confirmed component as stale when its owned files no longer match the stored fingerprint), and did `python -m flowguard change` or `release` run every model and test the change affects?

Good wording is not a passing run. One passing model is not the whole project. Any changed model, test, or covered source file may make an older result stale. This separation is the practical defense against a local green result being promoted into an unsupported full or release claim.

## Why Agents Need an Executable Model

AI coding agents are good at local edits. That strength also creates a risk: an agent may fix the symptom near the failing line while breaking the global workflow. Common failures include duplicate side effects, missing deduplication, inconsistent caches, retry paths that are not idempotent, and downstream functions receiving objects they cannot consume.

Natural-language reminders help, but they are weak. They do not enumerate branches, they do not replay repeated inputs, and they do not produce counterexample traces. FlowGuard makes those concerns executable.

## Mathematical Model

Each function block is modeled as:

```text
F: Input x State -> Set(Output x State)
```

This means:

- A block receives one abstract input and one immutable abstract state.
- It returns every possible `(output, new_state)` pair.
- One result means deterministic behavior.
- More than one result means explicit branching behavior.
- Zero results means a dead branch that must be reported.

A workflow composes blocks:

```text
Workflow = F_C o F_B o F_A
```

Because each block may produce multiple results, workflow execution forms a tree of traces. FlowGuard exhaustively explores that tree up to finite bounds and checks invariants on the reachable paths.

## Portable And Compositional Semantics

Python `FunctionBlock` models remain the authoring surface. When an exact
finite model must be consumed outside that Python model, the current
`flowguard.portable_model.v1` IR records states, input/output symbols,
transitions, initial and terminal states, invariants, temporal obligations,
assumptions, guarantees, and conflicts as canonical JSON.

The reference checker is deliberately narrower than a theorem prover. It
executes only the explicit finite relation, fails closed on unknown schemas or
truncated exploration, checks reachable safety violations and universal or
bounded eventuality, and preserves fairness assumptions and counterexamples.
Parent/child claims require explicit state and transition mappings; component
composition requires every assumption to have an environment or peer provider
and rejects declared conflicts. Descriptive mesh edges, prompt prose, or a
Python-only pass are not portable semantic evidence.

When several portable component models must be checked as one declared finite
subsystem, `flowguard.portable_system.v1` separates three identities:

- the system definition: components, typed dependencies, ports, bindings,
  resources, ordered or atomic steps, supported interaction patterns, and
  system properties;
- the request: selected roots, bounds, and explicit environment guarantees;
- the derived slice: the exact fixed-point closure over declared dependencies.

The composition checker validates each component, compiles that exact slice
into one joint portable model, invokes the canonical checker at most once for
the system result, and maps any counterexample back to component transitions
and optional code targets. Missing/stale closure and unresolved references are
`blocked`; malformed identities or schemas are `invalid`; a complete checked
counterexample is `fail`; unexecuted descendants are `not_run`. Clean or
temporal truncation never becomes a pass. Unknown components outside the
declared graph remain outside the proof boundary.

This is an intrinsic FlowGuard verification capability. It is not a storage
model or workflow engine for an unrelated application, and it makes no claim
about arbitrary Python, unbounded software, or domain truth outside the
declared finite artifact.

## No Probability

FlowGuard is non-probabilistic. It does not estimate probabilities, sample random paths, or run Monte Carlo. If a block can produce three possible outputs, the model returns all three. This is important because rare paths often contain the bug: repeated scoring, duplicate records, contradictory decisions, or a stale cache branch.

## Repeated Inputs

Many production bugs only appear when the same external input is processed again. Examples include retries, user double-submit, job re-ingestion, cache refresh mistakes, and repeated agent runs.

For `external_inputs = [job_001]` and `max_sequence_length = 2`, FlowGuard explores:

```text
[job_001]
[job_001, job_001]
```

That repeated sequence is what exposes non-idempotent blocks.

## Idempotency

Idempotency is a design rule, not only a test case. A block that writes state should say what happens when it receives the same input again. For example, `RecordScoredJob` should return `already_exists` instead of adding a second record.

FlowGuard makes that rule visible in three places:

- Function-block metadata such as `reads`, `writes`, and `idempotency`.
- State transitions in `FunctionResult`.
- Invariants such as `no_duplicate_application_records`.

## Invariants Beat Reminders

An invariant is executable. It checks every explored path and returns a structured violation with a counterexample trace. A reminder says "remember to deduplicate"; an invariant proves whether any explored path creates duplicates.

Good invariants are concrete:

- No duplicate application records.
- No repeated scoring without refresh.
- Every downstream object has source traceability.
- No contradictory final decisions.
- Cache and source of truth remain consistent.

## What FlowGuard Is Not

FlowGuard is not a complete formal proof system. The MVP explores finite abstract inputs up to finite sequence bounds. It can find counterexamples inside the model, but it cannot prove unbounded production correctness.

FlowGuard is also not a replacement for unit tests. Unit tests still verify production code. FlowGuard sits earlier: it models the intended functional flow before production code is written or changed.

## Map, Check And Release

FlowGuard keeps a map of the project in `.flowguard/map.json` (components, files, entrypoints,
dependencies, tests and models). `python -m flowguard change` checks the map against the code and
lists only the tests and models a change affects; `python -m flowguard release` runs the strict
check, the architecture review and every model. The skill is installed by copying
`.agents/skills/flowguard/` with `python scripts/install_skill.py --target <skills dir>`.

## MVP Limits

The first version is intentionally small:

- Python standard library only.
- No LLM API calls.
- No probability model.
- No random sampling or Monte Carlo.
- No GUI.
- No database.
- No real job-search product.
- No complex plugin system.
- No complete formal proof or unbounded model checking.

The target use is a small, executable model that makes production design safer before implementation starts.
