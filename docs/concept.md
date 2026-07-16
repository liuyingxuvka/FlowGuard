# FlowGuard Concept

FlowGuard is an AI-agent skill suite powered by an executable check engine. The skills tell an agent when to model a risky workflow, which route owns the problem, what evidence is required, and where a safe claim must stop. The Python engine makes those selected obligations executable before or after production code changes.

It is not a normal test framework, not a prompt-engineering trick, and not an LLM wrapper. It does not call model APIs. Its purpose is to make function-flow behavior, process order, evidence freshness, and claim boundaries explicit, finite, repeatable, and checkable. The installable product surface is the complete 17-member tree under `.agents/skills/`; the `flowguard` package and scripts are its executable support layer.

## Three Different Meanings Of Green

FlowGuard keeps three governance layers separate because each answers a different question:

1. **Prompt and contract structure:** Does a skill say the right things, reference resolvable material, and satisfy its static/depth contract?
2. **Native evidence receipt:** Did that route's real executable command run against the declared current inputs and end with an independently verifiable exact-pass receipt?
3. **Self-governance parent closure:** Did the parent consume every required current child receipt and check inventory, freshness, and distribution boundaries before making a suite-level claim?

A layer-one pass is not a layer-two run. One layer-two receipt is not layer-three closure. Any changed prompt, contract, native checker, model, test, or covered input may make older evidence stale. This separation is the practical defense against a local green result being promoted into an unsupported full or release claim.

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

## Validation And Distribution Surface

Repository model checks are owned by an explicit manifest rather than implicit file discovery. `fast` gives scoped development feedback, `focused` covers a wider selected surface, and only a current terminal `full` run can contribute to release evidence. Default output is concise; JSON and full human projections preserve the same status semantics and point to complete artifacts.

The skill distribution lifecycle is also explicit: install, check, parity, and uninstall operate on the complete 17-member tree, use ownership metadata, preserve modified user files, and report missing, extra, raw-hash, semantic-hash, and explicit exclusion results separately. See [Validation and Skill Distribution](./validation_and_distribution.md) for safe commands, evidence locations, background progress, and claim boundaries.

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
