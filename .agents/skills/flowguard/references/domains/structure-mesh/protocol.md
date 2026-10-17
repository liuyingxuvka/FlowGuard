# Structure Mesh
Reuse the current owner model and tests. Create a persistent scaffold only for a new
reusable boundary; apply the regression examples relevant to this change.
Use this when you split an existing large file or module into smaller modules. The review
catches splits that lose something. Examples: a function that no child module owns, two
children that both write the same cache, an old `python -m tool` command or import path that
no longer works, a new import cycle between children, a changed default, or tests that were
green before the move but were not re-run after it. Each child module becomes one component
in `.flowguard/map.json` after the split.
## Use when

- A large script, module or package is split into two or more child modules.
- A public import path, CLI command, API route, data shape or plugin entry point moves.
- State, caches, config keys or side effects (writes, publishes, external calls) are divided.
- Children start importing each other, or routine and release safety must be judged apart.

## Do not use when

- The feature is new and no code exists yet. Use code-structure.
- You want to merge or delete duplicate code paths. Use architecture-reduction.
- You rename or retire a field. Use field-lifecycle.
- You only need to know which tests cover the split modules. Use test-mesh.

## Inputs

- `python -m flowguard read --component PARENT`: `files`, `entrypoints`, `state`,
  `side_effects`, `depends_on`, `tests`, `models` of the module you split.
- `python -m flowguard map digest PARENT`: top-level functions and classes (partition rows).
- The parent's functional model (function blocks, state, effects, config).
- Every old public path: import names, CLI commands, routes. Each needs a facade or a new path.
- The tests that cover the parent: `python -m flowguard map impact <parent files>`.

## Steps

1. Write the starter files: `python -m flowguard template structure-mesh --write .`
   It writes `.flowguard/models/owners/structure_mesh/model.py`, a runner in
   `.flowguard/verification/owners/structure_mesh/run_checks.py` and a notes file.
2. In `model.py`, build the target structure as a `CodeStructureRecommendation` with
   `parent_module_id` equal to the plan's parent, one `TargetModuleRecommendation` per child,
   owner maps and `facade_module_id` (see the code-structure protocol).
3. Build the plan and review it:
   ```python
   from flowguard import (StructureMeshPlan, StructurePartitionItem, ModuleStructureEvidence,
                          PublicEntrypointEvidence, review_structure_mesh, EVIDENCE_ABSTRACT_GREEN)
   plan = StructureMeshPlan(
       parent_module_id="reporter", target_structure=target, decision_scope="routine",
       partition_items=(StructurePartitionItem("render_report", owner_module_id="renderer"),),
       child_modules=(ModuleStructureEvidence("renderer", path="reporter/renderer.py",
           owns_state=("render_cache",), owns_side_effects=("write_report",),
           dependency_cycles=(), behavior_parity_current=True,
           behavior_parity_tier=EVIDENCE_ABSTRACT_GREEN),),
       public_entrypoints=(PublicEntrypointEvidence("python -m reporter", entrypoint_type="cli",
           compatibility_preserved=True, facade_available=True, parity_evidence_current=True),))
   report = review_structure_mesh(plan)  # report.ok, report.decision, report.findings
   ```
   `StructurePartitionItem` fields: `item_id`, `item_type` (`function`, `state`,
   `side_effect`, `config`, `entrypoint`), `owner_module_id`, `ownership` (`child`, `parent`,
   `read_only`, `shared_kernel`). Intentional sharing goes in `allowed_shared_state`,
   `allowed_shared_side_effects`, `allowed_shared_config`, `allowed_dependency_cycles`.
4. Fill the facts from real data, not from memory. The review trusts what you pass:
   - Partition rows: one per top-level symbol from `map digest PARENT`, plus each item in
     the parent's `state` and `side_effects`. Functions are checked for double owners only
     through partition rows; `owns_functions` and `dependencies` are stored but not checked.
   - Cycles: add the children as map components, run `python -m flowguard map deps` (real
     imports) and `python -m flowguard map lint`. Copy every `dependency_cycle` finding
     (for example `cli <-> renderer`) into that child's `dependency_cycles`.
   - Entrypoints: keep the old anchors (`path:Symbol`) in the facade component's
     `entrypoints`. If `python -m flowguard map check` reports `anchor_broken` for one,
     set `compatibility_preserved=False`. Set `facade_available` from whether the old path
     still re-exports the symbol.
   - Parity: run `python -m flowguard change` after the last code edit and run the tests it
     selects. Set `behavior_parity_current=True` only if they passed after that edit.
   - `config_defaults_changed=True` if any default, environment variable or path changed.
5. For release, use `decision_scope="release"` and a higher `required_evidence_tier`
   (order: `candidate_only` < `abstract_green` < `hazard_green` < `live_current_green` <
   `conformance_green` < `mesh_green`, all exported as `EVIDENCE_*`). In routine scope (with the
   default `release_deferred_allowed=True`) a module or entrypoint with `release_required=True`
   and stale parity is only a warning, listed in `report.release_obligations`.
6. Add broken plans (see below). `run_checks.py` must return 0 only when the good plan passes
   and every broken plan fails. Run it with `python <that run_checks.py>`.
7. List the runner in the parent component's `models` in `map.json`
   (`".flowguard/verification/owners/structure_mesh/run_checks.py"`), then run
   `python -m flowguard map models structure_mesh` (exit 0 = pass).
8. After the split, each child is a map component: `files` = its path, `entrypoints` = its
   public symbols, `state` and `side_effects` = what it owns, `tests` = its parity tests.
   Run `map deps --write`, `map check`, `map lint`, then `map confirm ID`.

## What blocks

| Code | Meaning |
|---|---|
| `missing_target_structure` | No `target_structure`; the split is not derived from a model. |
| `coverage_gap` | A partition item has no owner, or its owner is not in `child_modules`. |
| `duplicate_partition_owner` | One partition item is owned by two modules. |
| `duplicate_state_owner` | Two children own the same state (also `duplicate_side_effect_owner`, `duplicate_config_owner`). |
| `target_function_owner_mismatch` | Partition owner differs from the target structure (also `target_state_`, `target_side_effect_`, `target_config_`, `target_entrypoint_owner_mismatch`). |
| `target_facade_missing` | Public entrypoints exist but the target structure has no `facade_module_id`. |
| `entrypoint_removed` | An old public entrypoint is not compatibility-preserved. |
| `facade_missing` | A module dropped the facade, or an entrypoint has no facade. |
| `dependency_cycle` | A child lists a cycle that is not in `allowed_dependency_cycles`. |
| `config_drift` | A child changed config, environment, path or default behavior. |
| `stale_behavior_parity` | Parity evidence exists but is not current. |
| `insufficient_evidence_tier` | Parity tier is below `required_evidence_tier`. |
| `release_parity_not_current` | Release scope: a release-required item has stale parity. |

## Risk-specific regression examples

- Double writer: `cli` and `renderer` both have `owns_state=("render_cache",)`.
- Removed command: `PublicEntrypointEvidence("python -m reporter", compatibility_preserved=False)`.
- Real cycle: `map lint` shows `cli <-> renderer`; set `dependency_cycles=("cli <-> renderer",)`.
- Orphan: `StructurePartitionItem("write_cache_file")` with no `owner_module_id`.
- Stale parity: the renderer changed after the last test run, `behavior_parity_current=False`.

## Done when

- [ ] `run_checks.py` exits 0: the good plan passes and every broken plan fails.
- [ ] The runner is listed in `models`; `python -m flowguard map models structure_mesh` passes.
- [ ] Each child is a map component with its tests listed; `map check` has no errors and
      `map lint` shows no `dependency_cycle` between children.
- [ ] `python -m flowguard change` is clean and its selected tests pass after the last edit.
- [ ] Your report names what ran, what was skipped (for example release obligations) and why.

## Limits

- The review checks only the facts you pass. A real a<->b import cycle or a function listed
  in two `owns_functions` passes unless you copy it into `dependency_cycles` or partition rows.
- It does not read code or run tests. `map check`, `map lint` and the real tests prove the code.
- A routine-scope pass can still carry `report.release_obligations`. They are not proven
  until a `decision_scope="release"` review passes.
- An `abstract_green` tier is a label you choose; it is not proof that behavior is unchanged.
