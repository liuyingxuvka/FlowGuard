# Routes

Locate the deepest owner with `python -m flowguard read --find <words | path:function | path::test>`. Code-only work uses `change --run`; model or structure work uses one target. Write no current model file in place. The loop and its EXPECTED GAP / moved rules only / NO GAP checkpoints are in SKILL.md.

## Code only

Use when no model file or map structure changes.
1. Edit code. `python -m flowguard change --run` selects its checks; run every selected check.
2. Fix `file_unmapped` by assigning one owner; fix intended `dep_undeclared` by declaring the layer-respecting dependency; remove `dep_unused`. Repair `anchor_broken`; move `duplicate_owner` promises to their sole owner.
3. For `UNEXPLAINED`, anchor the behavior, bind a test that exercises it, or give `NOT_MODELED` a concrete reason.
4. Re-read every REVIEW component; update descriptions when behavior changes, then `python -m flowguard map confirm <ids>`. Commit.

## New function

1. `read --find <words>` names the responsible component and model. No owner: [add a component](#add-or-split-a-component).
2. Take the first fit: **reuse** a rule that already judges this behavior (bind the new test; `no rule change`); **extend** the same function, entry and fields (`target add <model>`, add its input/field/rule and a known-bad); **sibling** for a separate command/check/entry or code used by other commands, branches or models (new target file, `PARENT = "<component>"`, `template behaviour`). If a model consumes another's result, the user writes HANDOFF and producer OUTPUTS: [Ports](model_recipes.md#ports).
3. An extra exclusive stage of a staged function gets `PARENT = "<parent>"`, OUTPUTS, READS_PARENT and a receiving step/HANDOFF in the parent's target. A new mode of one dispatch gets a branch child, OUTPUTS and the parent's DISPATCH/HANDOFF entry. Shared code is a sibling; never create a parent just to group models.
4. IMPLEMENTED_BY owns each function once; USES reads other owners. Put tests in `tests/test_<model>.py`, bind TESTED_BY, feed entry seeds to the real entry and assert its exits.
5. `target check`: EXPECTED GAP before code; promptly follow [Split a model](#split-a-model) for soft size warnings.
6. Write code, `target promote`, run its `map confirm`, commit. Existing behavior uses NO GAP and `records existing behaviour: <rule>` instead of new code.

## Split a model

A child belongs exclusively to its parent's function, as a stage or as a branch; a function that several models use is an independent model that each user consumes through HANDOFF.
List the candidate entry's discover callers and result users. Only callers/users within this one function permit a stage or branch.
1. Split when warned (>8 rules or >2,000 sequences); >12 rules or >10,000 sequences must split before promote/release. Keep smaller models, even with several aspects, until a rule exceeds the limit. Time is advice.
2. List rules, their fields (`read --field`) and real replay entries; group by the function judged.
3. Move independent aspects and shared code first: rules, bad variants, fields, anchors and fixtures move once into component siblings. A helper serving branches of one dispatch belongs to the branch whose function it is; others USES it. Actual result users consume OUTPUTS through HANDOFF, optionally mapping unused values to None.
4. If one exclusive function still needs splitting, use coarse stages (ordered/conditional) or branches (one choice per call). Set child PARENT/OUTPUTS/READS_PARENT; parent receives results as events into fields. DISPATCH maps every choice to its branch; each call receives that branch only. Parent rules judge order, conditions, choice and aggregation; KEEPS only inputs, markers and aggregates. Case tables contain child OUTPUTS only; see [Ports](model_recipes.md#ports).
5. Repeat only for an oversized stage/branch. No empty grouping layer or model existing only to feed/run another model.
6. A single-entry decision table may waive a soft limit with reason: `one decision table judged through one entry function: there is no composing function to split into steps, and halving the table makes two models replay the same function with no new information`. Hard limits cannot be waived: split >12 rules by entry cases into sibling tables.
7. One target contains the entire split. Moved rules print `moved rules only`; new rules print gap lines. Real `map check`/`map models` must have no S0–S8/C1–C8 findings. Examples: change_selection stages; read_command's six DISPATCH branches; shared map_check consumed by change_command/release_gate, and relation_graph shared by views.
8. One test file containing all and only this model's bound tests splits in that target into `test_<model>.py` per recipient; update TESTED_BY. Shared test functions stay. `test_file_not_split` remains TO-DO until both halves move. Otherwise use the test-file route.
9. Suggested: if new anchors share an oversized source file or one component now houses several independent models, split that file/component in this target. Otherwise leave code where it is.

## Split a test file

Use canonical test positions from `read --find <test path>`. Bound tests follow their top model, descending into its children if a group exceeds 40 functions. Multi-model tests stay at their lowest common ancestor. Unbound tests follow the literal command/module they exercise. A file mixing models splits at 3 functions per model (hard at 6); size warns above 40 and gates above 60.
Keep parametrizations and assertions; move TESTED_BY paths in the same target (`no rule change`). One-to-one files split with their model (`test_file_not_split`). Put shared fixtures in `tests/conftest.py`, shared functions in underscore helpers. Update component test patterns and list actual descendant files individually in smoke CI. A subtree shard then runs those nodes once.

## Interface change

For `port changed ... -> verify X`, add X to the same target. `(parent)` means a composing parent, `(HANDOFF)` another consumer, `(child input)` a child reading your field. A receiving step's input, label or output carries the new value and stores it in the named field; full HANDOFF can rename values. Consumers may map unused values to None; parents never may. `reads +f` requires the parent to supply f. `port_changed_parent_missing` prints the needed add command.
`dispatch +<a>` does not escalate upward, but requires that branch child and a DISPATCH entry (`dispatch_without_child`). Before changing a hub from `read --review`, inspect its ripple and include those models. Done: no ERROR and every affected receiver passes.

## Rename or retire a field

1. `read --field <name>` lists model State, rule, code writer/reader and literal sites. Read every named place.
2. In one target, rename State fields, READS_PARENT, OUTPUTS/HANDOFF and every owner anchor affected. Follow `port changed` to parent/consumer targets.
3. Inspect `consumes`, `produces`, `mentions` and `nothing produces`; a rename changes both interface production and consumption. Removed rules, known-bad and tests are promises, not disposable strings.
4. `target check` must show the intended gap or an honest move/NO GAP. Fix code/tests and all dangling readers. Retiring a field means removing its readers or documenting the deliberate lost promise, not supplying a silent default. Promote and confirm.

## Add or split a component

Use discover's actual call/import graph. Assign each file, entrypoint, responsibility, state and side effect once; preserve layer-respecting dependencies and test commands. Start a target and add every affected component/model. Move the owned promises and update dependency evidence/flow steps; don't add an undeclared shortcut to another layer.
Anchors follow code in the same target: update IMPLEMENTED_BY paths and keep `anchor_outside_home` clean. Scope broadening is not ownership. If nothing owns a new function, give it the smallest honest component. Inspect target read, check, implement, promote and confirm the listed components.

## Remove or merge a node

Use for duplicate or unused code, overlapping duties or a retired model/branch. One target names every recipient and every retired `component:<id>` / `model:<id>` in remove. Move files, entries, state, effects, responsibilities, dependencies and flows to the recipient. Deliberately lost promises use explicit `entrypoint:<path:Symbol>`, `state:<text>`, `side_effect:<text>` or `responsibility:<text>` removals; each must exist.
Move rules/bads/tests once, or give the reason for every printed `promises: -...` in the commit. The recipient's conformance calls real `CodeFacts(root).unreferenced("path:Symbol")` for removed code and combines those facts with its native replay; remaining callers are TO-DO. `change` selects affected current checks and lists static target work; `target check` executes merged models without bound tests. Delete the code only after design/gap evidence; finish with no ERROR/TO-DO, promote once, confirm and run remaining selected checks.

## When a green model missed a bug

1. Reproduce; retain failing node/log/steps.
2. `read --find <path:function>` locates the deepest owning model; absent owner: [New function](#new-function).
3. Identify missing input, coarse state, weak rule or wrong native conformance mapping.
4. Target-add the owner; add the missing input/field or strengthen its rule. The escaped case becomes a known-bad that must fail; recurring misses get another same-class case.
5. `target check`: changed rules show EXPECTED GAP; follow [Interface change](#interface-change) for port deltas.
6. Bind one real regression test in TESTED_BY; fix code until no TO-DO, promote, confirm.

## External promise (no silent fallback)

Own each public API/CLI/UI contract once, with a source, real entry seeds and asserted exits. Model fallback explicitly: its cause, chosen route, preserved result and visible failure; it cannot silently bypass a rule. Include timeout, unavailable dependency, incompatible input and cancellation where relevant. Bind tests to real calls. A removed branch's promises must move or have a recorded retirement reason. Target/check the intended change before code; promote only a clean implementation.

## Model before code

Write rules and caught known-bad variants without IMPLEMENTED_BY. Directly add an accepted debt `{"code":"model_anchor_missing","component":"<model id>","reason":"<what it models; which code will implement it>"}`; run map check before/after the setting change. Output names it `(process model: no code yet)`; this is not code proof. When code exists, add its anchors and native conformance in the same target as that code. `debt_stale` tells you when to remove the debt. Give a model without tests a reasoned unbound_models debt until real tests exercise it.
