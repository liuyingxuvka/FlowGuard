# FlowGuard

<p align="center">
  <img src="./assets/readme-hero/flowguard-icon.png" alt="FlowGuard icon" width="104" />
</p>

<p align="center"><strong>A "software DNA" for AI-assisted development: one living model tree with code owners, executable models of risky flows, tests and a target for planned changes.</strong></p>

[中文说明](./README.zh-CN.md)

FlowGuard maps and checks its own repository (`.flowguard/map.json`, `.flowguard/models/`). Its model and boundaries are described in [the concept guide](docs/concept.md).


## What it does

AI agents are good at local edits, but every new session has to rediscover: what parts does the
software have, who owns this behavior, what else does a change affect? FlowGuard keeps three
things in the project:

1. **The map** `.flowguard/map.json` - components, their responsibilities, owned state, side
   effects, files, entrypoints, dependencies, tests and models. A new session reads the whole map
   in a few thousand tokens and knows where to look.
2. **Models** - small executable `Input x State -> Set(Output x State)` models of risky flows
   (retries, idempotency, caching, ordering, money, permissions, multi-step workflows). FlowGuard
   explores every input sequence within a bound, reports counterexamples, checks that known-bad
   variants fail, and replays model traces against the real code (conformance).
3. **The target** - the intended map and models for one planned behaviour or structure change;
   implement and check that plan before promoting it to the current model.

The map and models form one tree. Root and component nodes come from the code and stay active;
behavior models are added beneath components when a task needs them, with tests on the same nodes.
`python -m flowguard read --mermaid` draws this tree.

The current tree lives in `.flowguard/map.json` and `.flowguard/models/`; planned changes live in one target under `.flowguard/target/` at a time.
For behaviour or structure changes, write the target first, then make the code and tests match it.
Once `target check` has no ERROR or TO-DO, `target promote` replaces the current tree and removes the target.

Map and code verify each other: every source file belongs to exactly one component; entrypoints,
flow steps and model files must exist; every real import must be declared;
confirming a component records a fingerprint of its files, so any code change marks it STALE until
someone re-reads and re-confirms it. History lives in git.

## Five-minute start

```bash
pip install -e .                                          # engine, standard library only
# or from GitHub: python -m pip install "flowguard @ git+https://github.com/liuyingxuvka/FlowGuard.git@<tag>"; the PyPI package named flowguard is a different project
python scripts/install_skill.py --target ~/.claude/skills # skill for your agent (or $CODEX_HOME/skills)

cd your-project
python -m flowguard map scan              # 1. draft components; guess tests from imports (default max 40)
python -m flowguard map discover          # inspect routes, commands, effects and state writers
python -m flowguard map digest all        # 2. API outline, signatures, assignments and docstrings; size varies
#   edit .flowguard/map.json: merge/split components, write summary, responsibilities, layer ...
python -m flowguard map deps --write      # 3. dependencies from real imports
python -m flowguard map check             # 4. fix until 0 errors
python -m flowguard map confirm all       # 5. the map is current
python -m flowguard map lint              # 6. architecture review
```

```powershell
python scripts/install_skill.py --target "$env:USERPROFILE\.claude\skills"
# Codex: set CODEX_HOME first; do not substitute an unset variable.
python scripts/install_skill.py --target "$env:CODEX_HOME\skills"
```

## Daily verbs

| when | command | what it does |
| --- | --- | --- |
| session start | `python -m flowguard read` / `read --find WORDS` | read the map; find the existing owner before adding code |
| behaviour or structure change | `python -m flowguard target` (`start "<goal>"` \| `add <id>` \| `check` \| `promote` \| `drop`) | write the target model first, make the code match it, then replace the current model |
| after editing | `python -m flowguard change` | verify map vs code; list only the affected tests and models |
| before release | `python -m flowguard release` | strict check, lint errors, every model re-run |
| start a model or adopt the workflow | `python -m flowguard template --list` | choose `behaviour`, `validator`, `ui-journey` or repository rules with `adoption` |

## What you can do

| former capability | how to do it now |
| --- | --- |
| behavior-commitment | Give each external promise one owner, a real code anchor and tests; model alternate paths. |
| architecture-reduction | Remove or merge a node through the target; preserve every public promise and check unreferenced code. |
| code-structure | Add or split an owner through the target; keep files, state, effects and entrypoints single owned. |
| contract-exhaustion | Use a `validator` node for finite accepted and rejected cases. |
| field-lifecycle | Describe renamed or retired fields in the target and check the old and new readers. |
| model-mesh | Nest models with `PARENT`; use state projection or `flowguard.closure` where children exchange results. |
| model-test | Bind rules through `IMPLEMENTED_BY` and `TESTED_BY`; run `map models --tests`. |
| topology-hazard | Read the computed `hazard:` observations from `map models`. |
| test-mesh | Use `release --shards 4`; each collected test runs once within the whole-suite phase. |
| ui-flow | Use a `ui-journey` node for states and journeys, plus the manual UI checklist. |

See [tree operations](.agents/skills/flowguard/references/tree_operations.md) and
[model recipes](.agents/skills/flowguard/references/model_recipes.md).

## What a model catches (real example)

`tests/fixtures/flowguard_map/order_placement.py`: a client retry with the same order id charges
the card twice. The unit test is green; the model's conformance replay fails with the two-step
counterexample `Place(o1), Place(o1) -> charges=('o1','o1')`. Deleting the invariant to get a pass
fails too: "known-bad variant passed: the invariants do not catch it".

## What it does not prove

A model proves only its declared finite boundary; the map describes the current commit; discovery
is a heuristic. FlowGuard does not replace tests, review or production monitoring, and does not
find the globally best architecture. It keeps its claims fresh, reviewable and bound to the code.

## Repository layout

- `flowguard/` engine, node kinds and computed facets; `flowguard/map/` map, target, discovery and proof layer
- `.agents/skills/flowguard/` the agent skill
- `.flowguard/` FlowGuard's own map and models (it maintains itself with itself)
- `examples/` runnable teaching models; `docs/` long-form notes

License: MIT
