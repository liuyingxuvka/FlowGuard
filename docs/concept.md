# FlowGuard Concept

FlowGuard maintains one executable model tree of a software project. Its map
names the components that own files, entrypoints, state and side effects.
Models sit under those owners and describe behaviour that matters across paths.
Real code and test bindings connect those models to the implementation.
`examples/shelf/` shows a small tree with a current model, a target and the code after the change.

## Function Blocks And Finite Exploration

A function block has the form:

```text
F: Input x State -> Set(Output x State)
```

The block receives an abstract input and state and returns every possible
output/new-state pair. Zero results expose a dead branch; one is deterministic;
several express branching. A workflow composes blocks:

```text
Workflow = F_C o F_B o F_A
```

FlowGuard exhaustively explores the resulting paths inside declared finite
bounds. It enumerates choices without probabilities or random sampling.
Repeated inputs expose retry, deduplication, idempotency and cache mistakes.
Invariants can reject duplicate side effects, contradictory decisions, stuck
states or outputs a downstream block cannot consume. A failure reports the
counterexample trace so the broken sequence can be replayed.

Finite exploration establishes behaviour only within the model and its bounds.
Conformance replay checks representative model traces against real code through
an adapter. The adapter projects state and output while preserving the facts
needed by the rule; deduplicating a real duplicate in that projection would hide
a bug. Unit tests also remain necessary.

## One Tree, Five Facets

The root is `system`. Components may form sub-systems with an optional `parent`;
models can nest below components or other models. The read view shows five
facets at each node: purpose, rules, known-bad variants, code and tests.

`IMPLEMENTED_BY` names real code anchors exercised by model exploration or
`conformance()`.
`TESTED_BY` names tests for each rule. Every model supplies known-bad variants
that must fail, and each rule must be broken by at least one of those variants.
These checks make omitted cases visible; they do not establish unbounded
production correctness.

## Current And Target Models

The current model is `.flowguard/map.json` plus `.flowguard/models/`.
Confirmed components store file fingerprints; changed owned code becomes stale
until its description is reviewed and confirmed.

For a behaviour or structure change, start one target:

```sh
python -m flowguard read
python -m flowguard target start "Describe the intended change"
python -m flowguard target add <node-id>
python -m flowguard target check
```

Edit `.flowguard/target/` until the design has no errors. Implement the code and
tests until no to-do remains, then use `target promote`, confirm the components
it lists and run `change`. The target becomes the current model; git keeps its
history. An edit that changes neither behaviour nor structure uses `change`
directly. Run the tests and models it selects, and resolve reported errors
before committing.

## Node Kinds And Tree Operations

Templates start ordinary `behaviour` models, finite-input `validator` nodes and
`ui-journey` nodes. `adoption` supplies repository rules. With a target present,
model templates write into its model directory.

Use [tree operations](../.agents/skills/flowguard/references/tree_operations.md)
to add, split, merge or remove owners, retire fields and preserve external
promises. [Model recipes](../.agents/skills/flowguard/references/model_recipes.md)
describe real bindings, child models and the node kinds.

## Computed Facets And Passing Checks

`read` reports how models, tests and explicit exclusions explain entrypoints
and state writers. `map models` computes `hazard:` observations and warns about
rules without test bindings through `invariant_untested`. These observations
come from the current tree and code.

A passing result means `map models` or `release` actually ran on that source.
Written guidance, a confirmed fingerprint and a historical pass do not establish
a new passing result. `change` selects affected checks. By default, `release`
runs strict checks, all models and their bound tests; `release --shards N` also
runs the whole collected test suite. Report the command, source revision and
actual result so its scope remains clear.
