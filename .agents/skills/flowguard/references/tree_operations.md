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
4. For a promise deliberately retired, list `entrypoint:<path:Symbol>`, `state:<original text>` or `side_effect:<original text>` in `remove`. Each must exist in the current map; these entries record intent without editing merged components.
5. Copy the recipient model with `python -m flowguard target add <model-id>`, then add each removed symbol as a real `CodeFacts(root).unreferenced("path:Symbol")` fact in that target model's `conformance()`; while callers remain, it is TO-DO.
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
