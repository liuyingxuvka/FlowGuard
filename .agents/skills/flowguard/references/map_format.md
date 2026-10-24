# `.flowguard/map.json` format (schema `flowguard.map.v1`)

```json
{
  "schema": "flowguard.map.v1",
  "project": "shop",
  "layers": ["ui", "api", "domain", "infra"],
  "ignore": ["docs/**", "scripts/**"],
  "test_command": "python -m pytest -q",
  "components": [
    {
      "id": "orders",
      "layer": "domain",
      "summary": "Places orders and charges the customer.",
      "responsibilities": ["place an order", "charge the customer once per order id"],
      "files": ["shop/orders/*.py"],
      "entrypoints": ["shop/orders/service.py:OrderService.place"],
      "state": ["orders table"],
      "side_effects": ["charges the card through the payment gateway"],
      "depends_on": ["storage", "payments"],
      "tests": ["tests/test_orders*.py"],
      "models": [],
      "status": "confirmed",
      "fingerprint": "sha256:..."
    }
  ],
  "flows": [
    {"id": "checkout", "summary": "cart to paid order", "steps": ["api:checkout", "orders:place", "payments:charge"],
     "model": ".flowguard/models/order_placement.py"}
  ],
  "accepted_debts": [
    {"code": "dependency_cycle", "members": ["orders", "payments"], "reason": "split planned"}
  ]
}
```

A flow of separate commands that hand over a file writes the later steps as `reads` steps:
`"steps": ["plan:main", "check:main reads plan.json"]`.

| field | meaning | who writes it |
| --- | --- | --- |
| `layers` | allowed dependency direction, top to bottom; a component may import its own or lower layers | human/AI |
| `ignore` | globs excluded from the inventory (in addition to `.flowguard/**`, `.git/**`, build dirs) | human/AI |
| `test_command` | how to run tests; `impact` appends the selected test files | human/AI |
| `id` | lowercase `[a-z0-9][a-z0-9_.-]*`, unique | human/AI |
| `parent` | optional id of a parent component (a sub-system); it must be in the same layer; file ownership stays direct | human/AI |
| `files` | globs (`*` = one directory level, `**` = any depth); every non-test source file must match exactly one component | human/AI |
| `entrypoints` | `path:Symbol` or `path:Class.method`; must exist (`check`) | human/AI |
| `depends_on` | edges supported by parsed imports, lazy exports, literal import_module/__import__ calls, entrypoint literals or defined symbol literals or an accepted `dep_unused` debt; undeclared imports and unsupported declarations are errors; `deps --write` replaces `depends_on` with the supported edges | tool, then reviewed |
| `tests` | test files/globs that exercise the component; must match something (`check`) | human/AI |
| `models` | optional: list contract models that this component's tree should show here; usually derived from COMPONENTS / IMPLEMENTED_BY / PARENT; unrelated listings warn; files must exist (`check`) | human/AI |
| `status` | `draft` or `confirmed` | `confirm` |
| `_hint` | facts written by `scan` to help describe a draft (file count, lines of code, a sample of public symbols); `confirm` deletes it | `scan` |
| `fingerprint` | hash of the component's files at the last `confirm`; mismatch = STALE | `confirm` only |
| `flows[].steps` | `component`, `component:Symbol`, or `component:Symbol reads <file>` for a separate command that reads a file an earlier step wrote; symbols must exist in that component (`check`); a `reads` step must name a symbol and cannot be the first step (`flow_handoff_invalid`) | human/AI |
| `flows[].model` | optional model protecting the whole flow; it is selected whenever a step's file changes, and `read --component` shows it on every component of the flow | human/AI |

Component containment is separate from a model's `PARENT`. Unknown parents, parent cycles and
cross-layer parents are ERRORs: `component_parent_unknown`, `component_parent_cycle`, `component_parent_layer`.
A parent with children may have no direct files; its `depends_on` must then be empty (`dep_unused`).
Displayed files, tests, dependencies and facets roll up the subtree; direct ownership and fingerprints do not change.
Before removing a parent in a target, remove or reparent its children; otherwise the target is invalid.

Tests are files whose name starts with `test_`, ends with `_test.py`, contains `.test.`/`.spec.`,
or that live in a `tests/`, `test/` or `__tests__/` directory. Tests are not owned by components;
they are linked through `tests`.

`.flowguard/cache/` holds parse caches. It is never committed and can be deleted at any time.

Exact non-ignored schema/config/resource paths in `files` join the owner fingerprint
and normal change selection. Non-code globs do not broaden the default code inventory.
A changed resource makes the owner stale; deletion/rename leaves a dead path until
the map and its code/model/test bindings are updated. Ignore rules still apply.

A cycle debt covers only its members; a grown cycle stays an ERROR and names the new members.

## Target (.flowguard/target/)

One target at a time; git holds history. The directory contains `map.json` plus optional flat
`models/<name>.py` contract files and `models/_<name>.py` helpers. A same-named file replaces
`.flowguard/models/<name>.py`; a new filename adds a model or helper. An absent `models/`
directory is valid and means no target model files.

`map.json` contains only the changes, with these keys:

| key | meaning |
| --- | --- |
| `schema` | exactly `flowguard.target.v1` |
| `goal` | nonempty description of the planned change |
| `components` | complete new entries; replace by matching `id` or add a new id; omit `status`, `fingerprint` and `_hint` |
| `flows` | complete new entries; replace by matching `id` or add a new id |
| `remove` | current nodes to remove: `component:<id>`, `flow:<id>` or `model:<MODEL_ID>`; explicit promise retirement: `entrypoint:<path:Symbol>`, `state:<original text>`, `side_effect:<original text>` or `responsibility:<original text>` |
| `layers` | optional; if present, replaces the entire current list |
| `accepted_debts` | optional; if present, replaces the entire current list |

An explicit empty optional list replaces the current list with empty; absence retains it.
Every `remove` value must name an item in the current map (or a current model ID); otherwise it is `target_invalid`.
`entrypoint:`, `state:` and `side_effect:` record deliberate retirement only: they do not edit merged component entries.
The target check reports ERROR `owner_dropped` when a replaced or removed component's entrypoint, state, side effect or responsibility has no merged owner and no explicit retirement (responsibilities, like state, compare by their words: a reworded one needs its old text in `remove`).
All model references use their merged destination, `.flowguard/models/<filename>.py`,
never a `.flowguard/target/models/` path. Replaced/new components become draft and lose
fingerprints; unchanged nodes retain their current description and bindings. Merged model ids must be unique. Reusing a current id in a different filename requires
explicitly removing that old id (`target_model_id_clash`); a same-filename replacement may
change its id. Conflicting remove/replace entries and invalid target structure are design errors.
A target that changes nothing yet (same map apart from status/fingerprint, empty `remove`, model files with the same AST) is ERROR `target_noop`. `target check` and `read --target` print `goal rules:`, the rules and known-bad variants the target adds (+) or changes (~), read statically; a target that changes the project's entrypoints, state or side effects with no goal rule is ERROR `target_goal_untied`.

`python -m flowguard target start "<goal>"` starts the target; `python -m flowguard target add <id>`
copies a current node; for a model it copies that single file and only notes static helpers.
Copy a helper into target `models/` yourself if it needs changes. Edit that copy; `target check`
checks the merged tree with real code and bound tests, reporting ERROR / TO-DO / WARN.
`python -m flowguard read --target` and `python -m flowguard read --mermaid --target` show the delta.
A clean `python -m flowguard target promote` makes it current and removes the target directory;
confirm the components it lists. `python -m flowguard target drop --yes` discards only the target.
Promote prints `re-read:` lines (re-parented models, flows that cross changed components, tests no longer bound); `target check` warns `debt_stale` for accepted debts the target makes stale.
