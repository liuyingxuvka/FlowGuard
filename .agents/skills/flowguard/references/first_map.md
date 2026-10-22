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
   - Write `layers` (top to bottom) and give every component a layer; without layers the root
     model `system` warns `no layers in the map` and the layer rule never runs. Pick layers by
     responsibility, not current imports; function-local imports count, `TYPE_CHECKING` imports do not.
   - Add 1-5 `flows` for the most important journeys. Each flow needs `"id"` (not `"name"`),
     `"summary"` and `"steps"`.
   - Keep `summary` to one sentence and each responsibility under about 8 words, so that
     `python -m flowguard read` stays within its 8,000-character default budget, including structure problems and model subtrees.
4. `python -m flowguard map deps --write` writes dependencies supported by imports, lazy exports, literal import calls, entrypoint or defined-symbol literals, or justified accepted debts; ordinary string values are not dependency evidence; unsupported declarations are removed.
5. `python -m flowguard map check` and fix until it reports 0 errors (`draft` warnings are expected now).
   For real existing `dependency_cycle` / `layer_violation` problems not being refactored now, record
   a reason in `accepted_debts` (cycle debts name `members`); fix incorrect layer choices instead.
6. `python -m flowguard map confirm all`, then `python -m flowguard map check` must show 0 errors; review test/model bindings and scoped warnings.
7. `python -m flowguard map lint` and write the top ERROR and WARN lines into your report.
   Review warnings such as `entrypoint_unlisted` and `entrypoint_unmodeled` as findings about existing code.
   Keep structural errors at zero by fixing wrong declarations or explicitly accepting existing debt
   with its reason as in step 5 (`architecture_review.md`); do not silently bypass those errors.
8. `python -m flowguard template adoption --write .` generates `docs/flowguard_agents_rules.md`.
   Copy its six rules into the project's AGENTS.md or CLAUDE.md; the template never edits either.
   Routine changes run selected tests/models; final frozen-source release runs the full
   suite and all registered models once, locally or in CI for that exact source SHA.
   Commit the map and those project rules: `git add .flowguard/map.json` (plus `.flowguard/models/` if you wrote
   models), then commit. `.flowguard/cache/` ignores itself in git via its own `.gitignore`.
9. Optional: write models for the 1-3 riskiest flows (`model_recipes.md`); entrypoints whose
   discovered reach includes `db`, `network` or `fs_write` are good candidates.
   The result is a root plus N components; add behavior models for those 1-3 dangerous flows.

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

- `layers` is set and every component has one.

- Every source file belongs to exactly one component (check enforces this).
- A newcomer reading `python -m flowguard read` can say where a new feature belongs.
- No responsibility appears twice; no vague summaries like "utils", "misc", "helpers".
- Descriptions say what the code does today, based on the digest, discovery or the source,
  not on guesses from names alone.
