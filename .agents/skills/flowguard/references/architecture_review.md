# Architecture review with `python -m flowguard map lint`

| code | level | meaning | usual fix |
| --- | --- | --- | --- |
| `layer_violation` | error | a lower layer imports a higher one | move the code down, invert the dependency (callback/interface), or fix the layer assignment |
| `duplicate_owner` | error | two components claim the same responsibility | pick one owner; the other delegates to it |
| `possible_duplicate` | warn | two responsibilities are worded very similarly | check whether they are the same job; merge or reword |
| `duplicate_code` | warn | identical function bodies in different components (info when all copies are in one component) | keep one implementation in the owner, call it from the other |
| `dependency_cycle` | error | components import each other in a cycle | extract the shared part into a lower component, or merge |
| `large_file` / `large_component` | warn | above size limits (800 LOC per file, 3000 per component) | split along responsibilities |
| `too_many_responsibilities` | warn | more than 7 responsibilities | split the component |
| `high_fan_out` | warn | depends on more than 8 components | introduce a facade or split |
| `untested_component` | warn | no tests mapped | add tests or map existing ones |
| `entrypoint_unlisted` | warn | discovery found a route, CLI command or handler that no component lists in `entrypoints` | add it to the owning component's `entrypoints` (or remove the dead route) |
| `entrypoint_unlisted` | info | the same for weaker signals (argparse registration, `__main__` calls) | list the real entrypoint if it is one |
| `effects_undeclared` | info | the code writes files, runs subprocesses, calls the network or a database, but `side_effects` is empty | describe the effects in `side_effects` |
| `never_imported` | info | a module nobody imports and that has no discovered entrypoint | delete dead code, or list it as an entrypoint |
| `foreign_state_write` | warn | code writes a state attribute that another component declares in `state` | move the write into the owner, or call the owner |
| `entrypoint_unmodeled` | warn | a listed entrypoint reaches a risky effect (file, subprocess, network, database) and no model anchors it; `check` and `change` print it too | model it, declare it in a model's `NOT_MODELED` with a reason, or accept it as a debt |
| `debt_stale` | warn | an `accepted_debts` entry matches no current finding | delete the debt |

Limits can be changed per run: `--max-file-loc 1200` etc.

The `entrypoint_*`, `effects_undeclared`, `never_imported` and `foreign_state_write` rows come from discovery (`python -m flowguard map discover` shows the raw
facts per component: entrypoints, side-effect counts, which effects each entrypoint can
reach, and which functions write each state attribute). Discovery is a heuristic: treat a
finding as a question to answer, not as proof.

Accepting a debt on purpose (it becomes `info` with your reason):

```json
"accepted_debts": [
  {"code": "dependency_cycle", "members": ["app", "cli"], "reason": "Flask-style app object; planned split in v2"}
]
```

`code` and `reason` are required; `component` and `contains` narrow the match.
Review accepted debts at every release; delete the ones that are fixed.

`flow_step_unreached` is an INFO hint from the static call graph. Higher-order calls and dynamic receivers can be unresolved; verify or reorder the declared journey. It does not block release.

A cycle debt covers only its members; a grown cycle stays an ERROR and names the new members.
