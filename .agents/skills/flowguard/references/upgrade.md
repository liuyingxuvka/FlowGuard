# Upgrade FlowGuard projects

## From 0.69

### Upgrade a project from FlowGuard 0.69

The current map, `.flowguard/map.json`, replaces `.flowguard/project.toml` and the
old ledger/receipt gates. Preserve old material in git history; do not turn old
results into current proof.

1. Save or commit the old project state before changing its integration.
2. Remove `.flowguard/project.toml` from the active tree (keep its git history).
3. Replace old FlowGuard/SkillGuard sections in AGENTS.md or CLAUDE.md with the six
   rules from `python -m flowguard template adoption --write .`.
4. Run `python -m flowguard map scan`, inspect `map discover` and `map digest all`,
   then describe components, owners, entrypoints, state, effects, tests and models.
5. `python -m flowguard map deps --write` keeps edges supported by actual imports, literal module
   references or explicitly justified accepted debts; unsupported declarations are removed. Follow
   `first_map.md`, fix `map check` errors, review dependencies and confirm the map.
6. Keep existing models whose declared boundary still matters. Register top-level
   contract models; do not register nested model.py.
7. During migration run `python -m flowguard change` and its selected checks. At the
   final frozen revision run the full project suite and `python -m flowguard release`
   once, or use successful CI for that exact source SHA, before claiming completion.
8. Do not retain SkillGuard compile/owner-receipt/selfproof or authority-closure gates.
   Move any necessary business assertion to the existing native test or contract model;
   remove unconsumed projection envelopes. Code/model/test bindings remain native.

Daily commands are read, change and release. Old self-review, self-conformance,
model-impact freshness and authority snapshot APIs are retired in 0.70.0.
Component IDs select `read --component`; executable model IDs select `map models`.
`read` may update disposable caches but does not change project behavior/data.

## From 0.70.10 to 0.70.11

The ten capability engines are folded into the model tree; each line below says what replaces one of them.

- `FlowGuardCheckPlan` / `run_model_first_checks` / `audit_model` / risk templates are removed; put the checks into a model file and run `python -m flowguard map models` (loops: call `flowguard.loop.check_loops` from the model's conformance or a test).

- The old architecture-reduction engine and template are removed; use `references/tree_operations.md#Remove or merge a node` with target `remove` and `CodeFacts.unreferenced` instead.

- The old `.flowguard/models/code_structure.py` starter no longer imports; plan the split as a target using `references/tree_operations.md#Add or split a component`. A state or side-effect claim shared by multiple components now raises `duplicate_owner` and makes `release` fail; describe each owner's state and effects specifically. ResearchGuard's FlowGuard reference upgrade must give `logicguard`, `sourceguard`, `traceguard` and `experimentguard` specific state/effect descriptions in the same change.

- The old `.flowguard/models/field_lifecycle.py` starter no longer imports; use the target-model field operation in `references/tree_operations.md#Rename or retire a field`, with `CodeFacts.absent` / `CodeFacts.present` in real `conformance()`.

- `.flowguard/behavior/inventory/ledger.json` is no longer read: move each promise into its file-owning component's `entrypoints` and a model's `IMPLEMENTED_BY` / `TESTED_BY` or a reasoned `NOT_MODELED`, then delete the old file. Duplicate or wrong-owner declarations are `entrypoint_owner` errors. `entrypoint_unmodeled` stays WARN for uncovered declared precise entrypoints (excluding argparse-derived ones) and the existing dangerous-effect cases; the old file produces a `retired_file` WARN. Existing ResearchGuard adopters should record the expected additional warning on FlowGuard reference upgrade and resolve it through native model bindings or a reasoned exclusion.

- Partition maps and `review_hierarchical_mesh` are gone; nesting is checked by `python -m flowguard map check`. For handoffs between children, import `MeshClosureModel` and `closure_invariant` from `flowguard.closure`, then place `closure_invariant(MESH)` in the parent model's invariants.

- The model-test alignment plan is gone; bind each rule to real tests in `TESTED_BY`, inspect the component's tests facet and run `python -m flowguard map models --tests`. `invariant_untested` warns about rule names with no binding key; it does not gate release or prove assertion strength. Failed bound tests, missing anchor reach and uncovered required known-bad invariants still block release.

- Any `DESIGN_ONLY` declaration in `.flowguard/models/` is now a `design_only_model` ERROR, even when its value is `False`, `None` or an empty string. Run `python -m flowguard target start "<goal>"`, move the file to `.flowguard/target/models/` and delete the declaration; target models also reject it (`target_design_only`). `planned=` and planned-code-fact exemptions are retired; code facts check real code without a planning flag.

- Runner models (`run_checks.py`) are retired: since 0.70.11 a leftover runner file is a `runner_model` error and is no longer executed. Rewrite it as a contract model in `.flowguard/models/` and delete the old file.

- Topology-hazard review models are gone; `python -m flowguard map models` now computes `hazard:` hints from each model's structure when landmarks exist, without changing verdicts.

- The `ui-flow-structure` template is retired; use `ui-journey` (`ui-flow` remains an alias) and import from `flowguard.ui_flow`. The remaining UI review questions are in `references/model_recipes.md#UI journey`.

- The `contract-exhaustion` template is now `validator`; import from `flowguard.validator`. Routes, cross-engine handoffs/adapters, coverage universes and confidence are gone; finite bad-case generation and execution against the real function remain.

- Capability and benchmark names left `import flowguard`; import node kinds from `flowguard.validator` / `flowguard.ui_flow`, closure from `flowguard.closure`, and benchmark helpers from their modules.
