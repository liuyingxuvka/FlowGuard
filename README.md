# FlowGuard

<p align="center">
  <img src="./assets/readme-hero/flowguard-icon.png" alt="FlowGuard icon" width="104" />
</p>

<p align="center"><strong>A "software DNA" for AI-assisted development: a living map of the software that evolves with the code and is verified against it, executable models of the risky flows, and 11 focused reviews for architecture and behavior defects.</strong></p>

[中文说明](./README.zh-CN.md)

FlowGuard maps and checks its own repository (`.flowguard/map.json`, `.flowguard/models/`). Measured results and known limits: [repair and validation report](docs/flowguard_0_70_2_fix_report.md).


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
3. **Capability reviews** - 11 focused checks an agent picks when the task needs one (table below).

Map and code verify each other: every source file belongs to exactly one component; entrypoints,
flow steps and model files must exist; every real import must be declared;
confirming a component records a fingerprint of its files, so any code change marks it STALE until
someone re-reads and re-confirms it. History lives in git.

## Five-minute start

```bash
pip install -e .                                          # engine, standard library only
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
| after editing | `python -m flowguard change` | verify map vs code; list only the affected tests and models |
| before release | `python -m flowguard release` | strict check, lint errors, every model re-run |
| new capability model | `python -m flowguard template --list` | starter model and runner files for each capability |

## The 11 capabilities

| capability | catches |
| --- | --- |
| behavior-commitment | external promises without one owner and tests; silent fallback paths |
| architecture-reduction | unsafe merges or deletions of duplicate code |
| code-structure | a module layout or split where state, effects or a public entrypoint lose their single owner |
| contract-exhaustion | bad cases and combinations of a finite boundary nobody tested |
| field-lifecycle | renamed or replaced fields left without owner, reader or migration |
| model-mesh | models that do not fit together (owners, reattachment, unconsumed outputs) |
| model-miss | the same class of bug escaping a green model again |
| model-test | rules, code contracts and tests that do not line up |
| topology-hazard | future-use hazards in a green model (shared writers, repeatable effects) |
| test-mesh | large test runs whose results cannot be trusted |
| ui-flow | controls without events, journeys without an end, hidden or leaking content |

Each capability has a short protocol in `.agents/skills/flowguard/references/domains/<name>/protocol.md`.

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

- `flowguard/` engine and capabilities; `flowguard/map/` map, discovery and proof layer
- `.agents/skills/flowguard/` the agent skill
- `.flowguard/` FlowGuard's own map and models (it maintains itself with itself)
- `examples/` runnable teaching models; `docs/` long-form notes

License: MIT
