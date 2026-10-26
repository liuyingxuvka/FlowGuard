# Tree operations

An operation is one target edit: `python -m flowguard target start "<goal>"`, then `python -m flowguard target add <id>` for every node to change.
Edit `.flowguard/target/` until `python -m flowguard target check` reports no ERROR and only TO-DO remains.
Write the code and tests until the same check reports no TO-DO.
Run `python -m flowguard target promote`, then `python -m flowguard map confirm <listed components>` and `python -m flowguard change`; run its selected checks.

## Remove or merge a node

Use when `map lint` reports `duplicate_code`, `never_imported` or `possible_duplicate`, when responsibilities overlap, or when a model or branch is no longer needed.

1. Start `python -m flowguard target start "<goal>"`, then `python -m flowguard target add <recipient>` for the component that takes over.
2. In target `map.json`, list `component:<id>` or `model:<id>` in `remove` for each retired node.
3. Move its `files`, `entrypoints`, `state`, `side_effects` and `responsibilities` into the recipient's target entry; update real dependencies and flow steps.
4. For a promise deliberately retired, list `entrypoint:<path:Symbol>`, `state:<original text>`, `side_effect:<original text>` or `responsibility:<original text>` in `remove`. Each must exist in the current map; these entries record intent without editing merged components.
5. Copy the recipient model with `python -m flowguard target add <model-id>`, then add each removed symbol as a real `CodeFacts(root).unreferenced("path:Symbol")` fact in that target model's `conformance()`; while callers remain, it is TO-DO.
   `unreferenced` returns a bool and records the fact; combine it with the replay (`replay_trace` as in `## Conformance` of `references/model_recipes.md`):
   ```python
   facts = CodeFacts(root)
   facts.unreferenced("shelf/members.py:Members.may_borrow")
   replay = replay_trace(trace=trace, adapter=Adapter(), invariants=INVARIANTS)
   facts.check("the replay still conforms", replay.ok, replay.format_text())
   return facts.report()                                  # ok only when every recorded fact holds
   ```
6. Run `python -m flowguard target check` until the design has no ERROR and only code/test TO-DO remains, then remove the code and its callers.
7. Use `python -m flowguard change` to inspect affected current checks and static target work. It does not execute target models.
8. Run `python -m flowguard target check` again: it executes changed target models and related models with bound tests in the merged tree. All ERROR and TO-DO must be gone.
9. Run `python -m flowguard target promote`, confirm the listed components, then `python -m flowguard change` and any remaining selected checks.

- Sole state writer disappears: transfer its state promise or retire it explicitly; `owner_dropped` blocks silent loss.
- Sole side-effect emitter disappears: transfer its effect promise or retire it explicitly; `owner_dropped` blocks silent loss.
- Public command or entrypoint disappears: keep it on a remaining owner or retire it explicitly; `owner_dropped` blocks silent loss.
- A rule's only counterexample test disappears: before promotion, inspect `python -m flowguard read --component <recipient> --target` and ensure every remaining rule still has a real test.

Do not delete on a guess: removed symbols must be `unreferenced`.

## Add or split a component

1. Run `python -m flowguard read --find <words>` first; extend the existing owner when it covers the change. Create a component only for a new responsibility.
2. Start `python -m flowguard target start "<goal>"`. For a new responsibility, write a complete target component: `id`, `layer`, `summary`, `responsibilities`, `files`, `entrypoints`, `state`, `side_effects`, `depends_on` and `tests`.
3. For a split, copy the original with `python -m flowguard target add <component-id>`, then divide its entry among the target components.
4. Put each state, side effect and public entrypoint on one responsible component: `duplicate_owner` checks responsibility/state/effect claims, and `owner_dropped` catches a lost promise. Keep required old entrypoints through a thin forwarding facade in the original file.
5. Share a kernel only when the code carries the same intent. Similar code with different intent (false friends) stays with its separate owners.
6. If a model must change, copy it explicitly with `python -m flowguard target add <model-id>` and edit that target copy; copying a component does not copy its models or helpers.
7. Run `python -m flowguard target check` until there is no ERROR and only code/test TO-DO remains. `component_empty`, `anchor_broken`, `file_unmapped` and `dep_unused` can identify code still to write.
8. Write the code and tests, then run the same target check until ERROR and TO-DO are both zero; it checks changed target models and related models with bound tests in the merged tree.
9. Run `python -m flowguard target promote`, confirm the listed components, then `python -m flowguard change` and any remaining selected checks.

## Rename or retire a field

Fields belong to model state or a component's `state`. Routing, permissions, feature flags, mode/version switches, persistence and prompt configuration carry behavior and use a target.
Pure display or metadata changes that leave behavior unchanged may follow **Change code only** in the skill.

1. Run `python -m flowguard read --field <name>` to see its writers, readers, model rules and bound tests.
2. Copy the component too if its `state` description changes. Keep retained promises on an owner; list `state:<original text>` in target `remove` only for an intentionally retired old promise.
3. Change the target model's state names and values. Add a known-bad variant for an old field still being read or a missing new field silently falling back to the old one.
4. Read the `consumes`, `produces`, `mentions`, and `promises:` lines from `change` or `target check`; open each named position and update its consumer or explain an intentional retirement. Record the applicable `CodeFacts(root).absent("old_mode", OWNED_FILES)` / `CodeFacts(root).present("mode", OWNED_FILES)` facts in that target model's real `conformance()`; before the code changes, unmet facts are TO-DO.
5. Run `python -m flowguard target check` until there is no ERROR and only code/test TO-DO remains, then implement the code and tests.
6. Run the same target check until ERROR and TO-DO are both zero; it checks changed target models and related models with bound tests in the merged tree.
7. Run `python -m flowguard target promote`, confirm the listed components, then `python -m flowguard change` and any remaining selected checks.

Choose an explicit outcome for the old field:
- Delete: require `absent` across its active producers and readers.
- Migrate: require the new name to be `present`; confine old-name reads to explicit, tested migration code and scope absence checks to the remaining active code.
- Reject: make legacy input fail a real check, and cover it with a known-bad variant or test.
- Reassign: put the field in the recipient component's target `state` and preserve its behavior and bindings there.

Check the default for a missing field and the behavior for null; who reads already persisted old data; and whether private content can be displayed to users.

## External promise (no silent fallback)

An external promise is a route, command, console script, handler or public API function recorded in a component's `entrypoints`.

1. Start `python -m flowguard target start "<goal>"`; copy the file-owning component and any existing model you change with `python -m flowguard target add <id>`. Write a new model under `.flowguard/target/models/` when needed.
2. List the entrypoint only on the component that owns its file; one promise has one owner (`entrypoint_owner`).
3. Use a model in that component's subtree: name the entrypoint in `IMPLEMENTED_BY` and bind real tests in `TESTED_BY`, or state a concrete `NOT_MODELED` reason for an intentionally unmodeled promise (`entrypoint_unmodeled`).
4. To retire a promise, remove it from the target component entry and list `entrypoint:<path:Symbol>` in target `remove`; `owner_dropped` blocks an undeclared loss.
5. A legacy facade only delegates to the primary path; model and test that its result equals the primary path's result.

For a model with primary and fallback paths, give each failure below its own `broken_variants()` entry that the rules must reject:
- Primary failure is followed by a fallback that reports success.
- A new field or data source fails, then code reads an old field or backup cache.
- Two paths claim authoritative success for the same intent.
- Required manual recovery is performed automatically.
- A legacy facade performs business logic instead of delegating to the primary path.

6. Run `python -m flowguard target check` until the design has no ERROR and only code/test TO-DO remains, then implement the code and tests.
7. Run the same target check until ERROR and TO-DO are both zero, then `python -m flowguard target promote`, confirm the listed components and run `python -m flowguard change` with any remaining selected checks.
