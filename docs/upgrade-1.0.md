# Upgrade to FlowGuard 1.0

The current engine owns `check`, `show`, `decide` and `release`. Static `where`, owner request storage and the ordinary pytest shard runner remain. There is no compatibility interpreter for the old formats.

1. List every old model's rules, deliberate breakages, code anchors and test bindings before deleting it. Keep existing real tests. Move useful behavioral obligations to independent `.flowguard/flow/*.py` models with `MODEL = m`; preserve the source request. Bind real code through `Model.bind_adapter` and use the shared native recorder. Keep an explicit disposition for an obligation whose owner was deleted, whose old abstraction was invalid, or which is already enforced by a retained test. A model rewrite alone is not proof of the implementation.
2. Move static model coverage to `Model(..., covers=["path.py:Class.method"])`. Paths use the project root, including when the adapter executes from a nested source root. Replace old `IMPLEMENTED_BY`/`TESTED_BY` bookkeeping with actual native observation and ordinary executed tests. Keep code owners in the source inventory; no hand-written map is required.
3. Delete `.flowguard/map.json`, `.flowguard/models/` and `.flowguard/target/` after their useful content is accounted for. Keep immutable requests and existing conflict records. Executing an old format stops with upgrade advice; static queries remain available. There is no `map`, `target`, `read` or `change` command, and no experimental `flowguard.behave` executor.
4. Run relevant real tests, `check --full` and the project's release command. Use `release --shards N` when requesting the entire pytest suite. Without it, release states that tests were not run. If a scope is capped or unsupported, retain UNKNOWN; do not call it complete.

## Conflict identities

The conflict kind participates in its identity. When an upgrade changes a finding's kind, the former conflict may close and a new ID may open for the new kind. This is an identity change, not evidence of a code repair. Review both scopes and the new witness. Removing an action, field or promise does not settle the corresponding retained conflict. Owner choices and replacement requirements must quote stored actual owner words; model/code drift, STUCK and NEVER REACHED need repair.

## Removed pilot pieces

The old pilot skeleton and `why` executors are not carried forward. Static `where`/inventory owns source discovery; future drafting will write an explicit one-time TODO, not copy implementation guards or effects into its oracle. Existing `status` and `show` own explanation and retained witnesses. File-input observations and failures use the current native adapter and recorder; there is no second crash runner or swallowed-error path. These are implementation choices, not claims that later drafting or file-input features are already released.

## Limits kept visible

The native record covers actual in-process execution; subprocess interiors and unsupported observations remain explicit gaps. Source matches are candidates, not causal proof. Pure model results do not stand in for native execution. Finished UNKNOWN permits an ordinary commit and stays visible. No automatic commit hook or unconditional whole-project pytest run is added.

In the 1.0 consumer migration, PhysicsGuard's three production native checks and recorded walk were conformant. Its shared footprint remained nonreusable with `application-consumed arena directory enumeration order`; metadata directory discovery remains an unsupported observation boundary. The overall native result is visibly finished UNKNOWN, accepted under the existing release policy. This is partial native coverage, not an all-native-clean result.
