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
   effects, files, entrypoints, dependencies, tests and models. Start or resume with
   `python -m flowguard status`, and find code, owners and callers with `python -m flowguard where NAME`.
2. **Models** - small executable `Input x State -> Set(Output x State)` models of risky flows
   (retries, idempotency, caching, ordering, money, permissions, multi-step workflows). FlowGuard
   explores every input sequence within a bound, reports counterexamples, checks that known-bad
   variants fail, and replays model traces against the real code (conformance).
3. **The target** (legacy route, kept until v1.0.0) - the intended map and models for one planned
   change of the legacy models; a normal change needs no target.

The map and models form one tree. Root and component nodes come from the code and stay active;
behavior models are added beneath components when a task needs them, with tests on the same nodes.
`python -m flowguard read --mermaid` draws this tree.

The current tree lives in `.flowguard/map.json` and `.flowguard/models/`. A normal change is code and tests
changed together, the project's tests run, and one commit with a message in your own words; add a line
`Request: R<n>` when the change answers a stored owner request.

Map and code are compared on every check. Real problems such as import cycles, layer violations and
missing model anchors are errors. Gaps that only mean the hand-written map is behind the code (a file
without an owner, a stale description, an undeclared or unproven dependency) are information and never
fail a check. History lives in git.

## Five-minute start

```bash
pip install -e .                                          # engine, standard library only
# or from GitHub: python -m pip install "flowguard @ git+https://github.com/liuyingxuvka/FlowGuard.git@v0.72.0"; the PyPI package named flowguard is a different project
python scripts/install_skill.py --target ~/.claude/skills # skill for your agent (or $CODEX_HOME/skills)

cd your-project
python -m flowguard status                              # 1. start or resume: the owner's newest words and open work
python -m flowguard req add owner-message.txt --id R1   # 2. store the owner's own words once, byte for byte
python -m flowguard where place_order                   # 3. find the code, its owner and its callers
python -m pytest -q tests/test_orders.py                # 4. change code and tests together; run the project's tests
git add -A && git commit -m "Charge each order once" -m "Request: R1"   # 5. one commit in your own words
```

That is the whole loop; the project needs no map, model or target for it. The legacy map (`map scan`, `map check`,
`map confirm`), the legacy models and the target commands are optional and kept until v1.0.0; the
[concept guide](docs/concept.md) describes them.

```powershell
python scripts/install_skill.py --target "$env:USERPROFILE\.claude\skills"
# Codex: set CODEX_HOME first; do not substitute an unset variable.
python scripts/install_skill.py --target "$env:CODEX_HOME\skills"
```

## Daily verbs

| when | command | what it does |
| --- | --- | --- |
| session start or resume | `python -m flowguard status` | the project's static facts and what fails release and CI |
| the owner asks for something | `python -m flowguard req add <file\|-> --id <id>` | store the owner's own words once, byte for byte |
| legacy target route (until v1.0.0) | `python -m flowguard target` (`start "<goal>"` \| `add <id>` \| `check` \| `promote` \| `drop`) | plan a change of the legacy models; a normal change needs no target |
| legacy check (until v1.0.0) | `python -m flowguard change` | verify map vs code; list only the affected tests and models |
| before release | `python -m flowguard release` | strict check, lint errors, every model re-run, the flow models' full check |
| start a model or adopt the workflow | `python -m flowguard template --list` | choose `behaviour`, `validator`, `ui-journey` or repository rules with `adoption` |

## Flow models

A flow model is the part of the design a change touches, written as a small machine in
`.flowguard/flow/<name>.py`: a few fields, the actions that change them and the promises the owner's
requests make (`from flowguard.flow import Model, need`, one model per file, ending with `MODEL = m`).
`check` tries every action in every reachable state and reports what gets stuck, what never happens and
which promise some order breaks, each with its shortest path and the requests behind it. The short
guide to writing them is [flowguard/flow/HOWTO.md](./flowguard/flow/HOWTO.md), also in the installed package.

| command | what it does |
| --- | --- |
| `python -m flowguard check` | explore every flow model; line 1 is the verdict; exit 0 clean, 1 conflict, 2 model error, 3 UNKNOWN (search capped), 4 RUNNING |
| `python -m flowguard check --full` | also break each model on purpose to see that its checks catch it, and explore a model with interchangeable ids once more without renaming them |
| `python -m flowguard show` | draw the conflicts, else the change against HEAD, as a flowchart (`show MODEL`, `show C-...`, `--before REV`) |

`check` returns within `--wait` seconds (default 90). Work left RUNNING continues for `--keep` seconds, and the
same command resumes it. `--json` prints one line. Conflicts are kept in `.flowguard/conflicts.json` (commit it):
`status` shows the open ones, and `release` runs `check --full`. Pictures need node with Playwright; without them
`show` writes the Mermaid text.

The v0.73 flow engine supports Linux only. Windows keeps the legacy commands; flow `check`,
`show` and the flow part of `release` exit 2 with an explanation. `status` still shows stored
conflicts and the limitation. Full Windows flow support is planned for the next stage.

## Find source and original text

When finding source or its owner needs more than one grep hop, use these static queries (FlowGuard 0.71.1+):

| Command | Shows |
| --- | --- |
| `python -m flowguard where NAME` | source, owners and callers |
| `python -m flowguard where` | compact module overview |
| `python -m flowguard where --flow` | static calls; add NAME to focus |
| `python -m flowguard where --arch` | architecture and source-backed suggestions |
| `python -m flowguard where --text` | text and reference summary |
| `python -m flowguard where --keyflows` | shared state and file destinations |

Add `--root DIR` or `--json` as needed. With `--text`, select FILE, `source:<id>`, `group:<id>` or `"text:<literal phrase>"` to read original passages and available Git provenance. The default shows the most relevant rows of each list, says how many it left out and prints commands for the next query; `--all` prints every row. Literal searches use case-insensitive substrings. `--at REF` reads both text and code at that Git revision.

These queries run no application, model or test. Missing execution records stay unknown. Literal matches are candidates, without an automatic semantic verdict or change gate; models and independent rule tests still validate behavior. Existing commands, 64 public exports and the map format remain compatible.

## What you can do

These use the legacy map, models and target commands: optional, kept until v1.0.0 and not needed for a normal change.

| former capability | how to do it now |
| --- | --- |
| behavior-commitment | Give each external promise one owner, a real code anchor and tests; model alternate paths. |
| architecture-reduction | Remove or merge a node through the target; preserve every public promise and check unreferenced code. |
| code-structure | Add or split an owner through the target; keep files, state, effects and entrypoints single owned. |
| contract-exhaustion | Use a `validator` node for finite accepted and rejected cases. |
| field-lifecycle | Describe renamed or retired fields in the target and check the old and new readers. |
| model-mesh | Nest models with `PARENT`; use state projection, finite `OUTPUTS` and `HANDOFF` where children exchange results. |
| model-test | Bind rules through `IMPLEMENTED_BY` and `TESTED_BY`; run `map models --tests`. |
| test-mesh | Use `release --shards N`; each shard runs whole test subtrees and every collected test runs exactly once. |
| ui-flow | Use a `ui-journey` node for states and journeys, plus the manual UI checklist. |

See [routes](.agents/skills/flowguard/references/routes.md) and
[model recipes](.agents/skills/flowguard/references/model_recipes.md).

## What a model catches (real example)

`tests/fixtures/flowguard_map/order_placement.py`: a client retry with the same order id charges
the card twice. The unit test is green; the model's conformance replay fails with the two-step
counterexample `Place(o1), Place(o1) -> charges=('o1','o1')`. Deleting the invariant to get a pass
fails too: "known-bad variant passed: the invariants do not catch it".

`examples/shelf/` is a whole model tree to copy: a current map and model, a target that adds a
rule, and the code after the change (its README lists the commands).

## What it does not prove

A model proves only its declared finite boundary; the map describes the current commit; discovery
is a heuristic. FlowGuard does not replace tests, review or production monitoring, and does not
find the globally best architecture. It keeps one model tree bound to the code and tests.

## Repository layout

- `flowguard/` engine, node kinds and computed facets; `flowguard/map/` map, target, discovery and proof layer;
  `flowguard/flow/` the flow-model engine behind `check` and `show`
- `.agents/skills/flowguard/` the agent skill
- `.flowguard/` FlowGuard's own map and models (it maintains itself with itself)
- `examples/` runnable teaching models; `docs/` long-form notes

License: MIT
