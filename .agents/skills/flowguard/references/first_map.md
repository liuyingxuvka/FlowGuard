# First map of an existing project (reverse wrapping)

Goal: a confirmed map with 5-30 components, 0 check errors, and a written list of the main
architecture findings. Measured on FlowGuard's own map during the 0.70.2 work: about 112k nonblank,
noncomment source lines (5.2 MB) produced a 158k-character digest with a
40-line-per-file limit, about 3.1% of source bytes. These are character/byte counts,
not token estimates. API density and the line limit change this ratio; measure your
project and read components in batches. Default `read` targets 8,000 characters.

## Steps

0. If the project is not a git repository, run `git init` first (the inventory and `impact`
   use git). Never commit `.flowguard/cache/`.
1. `python -m flowguard map scan`
   Creates `.flowguard/map.json` with draft components, guessed tests and dependencies.
   `--max-components` defaults to 40; deepest complete directory groups are merged upward.
   A draft hint contains file count, line count and at most eight public names.
2. `python -m flowguard map discover` lets you inspect discovery directly.
   `python -m flowguard map digest all > .flowguard/cache/digest.txt`
   Read the digest (signatures, short assignments and docstrings, no function bodies). For a big project read it in
   batches: `python -m flowguard map digest <id> <id> ...`. Open a source file only when a
   name in the digest is not enough to say what the code does.
3. Rewrite `.flowguard/map.json` (writing the whole components list at once is fine; field
   format and a full example: `map_format.md`):
   - Merge drafts that serve one purpose into one component; split a draft that mixes purposes.
     Aim for components a newcomer can name in two words. Delete every `_hint`.
   - Each responsibility must have exactly one owner in the whole map.
   - Use `map discover` output: real entrypoints go to `entrypoints`, effects go to
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
     `python -m flowguard read` stays near 300 characters per component (about 8,000 for 25 components).
4. `python -m flowguard map deps --write` writes dependencies supported by imports, literal module references or justified accepted debts; unsupported declarations are removed.
5. `python -m flowguard map check` and fix until it reports 0 errors (`draft` warnings are expected now).
6. `python -m flowguard map confirm all`, then `python -m flowguard map check` must show 0 errors; review test/model bindings and scoped warnings.
7. `python -m flowguard map lint` and write the top ERROR and WARN lines into your report.
   On a first map, lint errors (for example `layer_violation`, `dependency_cycle`) and warnings (for example
   `entrypoint_unlisted`, `entrypoint_unmodeled`) are findings about the existing code: record
   them, do not refactor now, and do not let them block step 8. If a `layer_violation` comes
   only from a wrong layer choice, fix the layer. Otherwise fix it later or list it in
   `accepted_debts` with a reason (`architecture_review.md`).
8. `python -m flowguard template adoption --write .` generates `docs/flowguard_agents_rules.md`.
   Copy its six rules into the project's AGENTS.md or CLAUDE.md; the template never edits either.
   Routine changes run selected tests/models; final frozen-source release runs the full
   suite and all registered models once, locally or in CI for that exact source SHA.
   Commit the map and those project rules: `git add .flowguard/map.json` (plus `.flowguard/models/` if you wrote
   models), then commit. `.flowguard/cache/` ignores itself in git via its own `.gitignore`.
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
