# First map of an existing project (reverse wrapping)

Goal: a confirmed map with 5-30 components, 0 check errors, and a written list of the main
architecture findings. Typical cost: a 10k-line project needs about 5k tokens of digest
reading; a 200k-line project about 90k tokens, done in batches of components.

## Steps

0. If the project is not a git repository, run `git init` first (the inventory and `impact`
   use git). Never commit `.flowguard/cache/`.
1. `python -m flowguard map scan`
   Creates `.flowguard/map.json` with draft components (one per directory, large directories
   split by file-name prefix), guessed tests and dependencies. Each draft has a `_hint` with
   its size, public symbols and, under `_hint.discovered`, what discovery found in the code:
   entrypoints (HTTP routes with method and path, CLI commands, `__main__`), side-effect
   counts (file writes, subprocess, network, database, environment, exit), which effects each
   entrypoint can reach, and which functions write each state attribute.
2. `python -m flowguard map digest all > .flowguard/cache/digest.txt`
   Read the digest (signatures and docstrings, no bodies). For a big project read it in
   batches: `python -m flowguard map digest <id> <id> ...`. Open a source file only when a
   name in the digest is not enough to say what the code does.
3. Rewrite `.flowguard/map.json` (writing the whole components list at once is fine; field
   format and a full example: `map_format.md`):
   - Merge drafts that serve one purpose into one component; split a draft that mixes purposes.
     Aim for components a newcomer can name in two words. Delete every `_hint`.
   - Each responsibility must have exactly one owner in the whole map.
   - Use `_hint.discovered`: real entrypoints go to `entrypoints`, effects go to
     `side_effects` in plain words ("writes notes to sqlite"), written state to `state`.
   - `entrypoints` and flow steps must name a symbol **defined** in that file (`def`, `class`
     or a top-level assignment), as `path:Name` or `path:Class.method`. A name the file only
     imports (a re-export in `__init__.py`) fails with `anchor_broken`; point at the defining file.
   - `tests`: test files or globs (`tests/test_sessions*.py`). A component without tests is
     allowed; lint will warn `untested_component`.
   - `layers`: top to bottom (e.g. `["entry", "app", "core", "support"]`). Pick each
     component's layer by what it is, not by its current imports. Every import counts,
     including imports inside functions; imports under `if TYPE_CHECKING:` do not.
   - Add 1-5 `flows` for the most important journeys. Each flow needs `"id"` (not `"name"`),
     `"summary"` and `"steps"`.
   - Keep `summary` to one sentence and each responsibility under about 8 words, so that
     `python -m flowguard read` stays under about 8,000 characters.
4. `python -m flowguard map deps --write` merges parsed imports into `depends_on`, preserving valid declarations for lazy/alias paths. Unparsed declarations remain unverified.
5. `python -m flowguard map check` and fix until it reports 0 errors (`draft` warnings are expected now).
6. `python -m flowguard map confirm all`, then `python -m flowguard map check` must show 0 errors, 0 warnings.
7. `python -m flowguard map lint` and write the top ERROR and WARN lines into your report.
   On a first map, lint errors (for example `layer_violation`) and warnings (for example
   `dependency_cycle`, `entrypoint_unlisted`) are findings about the existing code: record
   them, do not refactor now, and do not let them block step 8. If a `layer_violation` comes
   only from a wrong layer choice, fix the layer. Otherwise fix it later or list it in
   `accepted_debts` with a reason (`architecture_review.md`).
8. Commit only the map: `git add .flowguard/map.json` (plus `.flowguard/models/` if you wrote
   models), then commit. Do not use `git add -A`: `scan` does not add `.flowguard/cache/` to
   `.gitignore`.
9. Optional: write models for the 1-3 riskiest flows (`model_recipes.md`); entrypoints whose
   discovered reach includes `db`, `network` or `fs_write` are good candidates.

## Example (one component and one flow, valid as written)

```json
{
  "schema": "flowguard.map.v1",
  "project": "shop",
  "layers": ["api", "domain", "infra"],
  "ignore": [],
  "test_command": "python -m pytest -q",
  "components": [
    {
      "id": "orders",
      "layer": "domain",
      "summary": "Places orders and charges the customer once per order id.",
      "responsibilities": ["place an order", "charge the customer once per order id"],
      "files": ["shop/orders.py"],
      "entrypoints": ["shop/orders.py:OrderService.place"],
      "state": ["orders by id"],
      "side_effects": ["charges the card"],
      "depends_on": [],
      "tests": ["tests/test_orders.py"],
      "models": [],
      "status": "draft",
      "fingerprint": ""
    }
  ],
  "flows": [
    {"id": "checkout", "summary": "request to paid order", "steps": ["orders:OrderService.place"]}
  ],
  "accepted_debts": []
}
```

## Quality bar

- Every source file belongs to exactly one component (check enforces this).
- A newcomer reading `python -m flowguard read` can say where a new feature belongs.
- No responsibility appears twice; no vague summaries like "utils", "misc", "helpers".
- Descriptions say what the code does today, based on the digest, discovery or the source,
  not on guesses from names alone.
