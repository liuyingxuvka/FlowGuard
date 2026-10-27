# Node kinds

## UI journey

Start/add the owner's target first (SKILL.md). For a new model, use `python -m flowguard template ui-journey --write <scratch>` (`ui-flow` is an alias), then copy the starter model into `.flowguard/target/models/`.
Import `UIInteractionModel`, `UIStateNode`, `UIControl`, `UITransition`, `ui_journey_explorer` and `ui_flow_code_facts` from `flowguard.ui_flow`; declare the initial state, screens/form data, controls and submit/cancel/back/retry transitions.
Bind real handlers in `IMPLEMENTED_BY`, real UI source in `UI_FILES` and real tests in `TESTED_BY`; `conformance()` checks the source controls and handlers through code facts.
Keep the `show_opens_an_unknown_state` and `details_dialog_cannot_close` known-bad variants; model reachable success, stable cancel and failure recovery.
Automatic `ui_review_accepts` checks structure and four operability rules: `missing_failure_recovery`, `destructive_control_too_prominent`, `dialog_cannot_close`, `state_unreachable`.
Model a close transition to a different registered state using an available control. Finish target design before code; remove every ERROR and TO-DO before promote, then run the selected checks.
Review these questions against real UI code and click-through/component tests; the model and code facts do not render, click or prove the manual answers:

- **Visibility:** Are internal ids/fields absent, optional details hidden until reveal and closable, rendered items accounted for, and disabled reasons user-facing?
- **Hierarchy:** Does each screen have one clear main heading/action, stable global/context/local regions and task-owned labels/status/error text without unexplained duplication?
- **Responsive:** At phone width is there no horizontal overflow, with immediate action feedback, stable layout and protection from stale asynchronous results?
- **Operability:** Can users finish tasks with keyboard access, visible focus, correct affordances, cancel/Escape/close and focus return, including native dialogs and hover disclosure?
- **Consistency:** Does one intent use the same term, typography, action grammar, navigation, feedback and recovery across surfaces, with deliberate repeated controls?
- **Render/geometry:** In the running UI are controls rendered, unclipped and non-overlapping, with correct bounds/scroll/focus and current screenshot, DOM or geometry checks?
- **Capability:** Does every required user task have a working path from control through its real handler to a visible result, preserving old capabilities or an explicit intentional change?
- **Journey:** Does every entry route reach success with tested failure/recovery/cancel/exit branches, and do enabled controls and the current implementation match the declared states/transitions?

## Validator

Use when a function/interface has a finite input boundary and every declared bad value must be rejected; this is an ordinary contract model.
Start/add the owner's target first (SKILL.md); scaffold with `python -m flowguard template validator --write <scratch>` and copy the model into `.flowguard/target/models/`.
Import `ContractDimension`, `ContractExhaustionPlan`, `ContractOracle`, `contract_exhaustion_features` and `execute_contract_features` from `flowguard.validator`; bind real code and tests.
Declare finite dimensions, their values and default mutations. Input/payload defaults include `old_schema_version` and `conflicting_identity`; keep `omitted_family_member` for missing registry members.
Add `ContractAxis` / `ContractInteractionGroup` only for real interactions; cap the product and inspect the allowed single/pair combinations actually executed.
Use generated features with real conformance and `execute_contract_features`; preserve the clean-input check and name a rejection oracle for each case.
A dimension's mutation may have any name: built-in names keep their default reaction, other names must be rejected; a hand-written seed case still names its oracle or expected status, and invalid/unbounded dimensions or excessive products raise `ValueError`.
Only `ValueError`/`TypeError` (or `rejects=(...)`) count as a rejection; any other exception is reported as `adapter_exception` (a crash).
A reported accepted case id identifies a bad input the real function failed to reject: reproduce it, fix the code and retain a failing known-bad variant plus a real regression test.
A default label saying reject before side effect is not observed timing proof; test the actual function's effects when that ordering matters.
Finish target design before code and remove ERROR/TO-DO before promote; run the selected checks and report executed case counts and limits.

## Node kinds

`behaviour` starts an ordinary executable contract model.
`validator` checks a finite input boundary; see `## Validator`.
`ui-journey` explores interface states, controls and transitions; see `## UI journey`.
Use `python -m flowguard template <kind> --write .`; `adoption` writes the six project integration rules.
With a target, model files go into `.flowguard/target/models/`; otherwise they go into `.flowguard/models/`.
Other template files keep their paths; the CLI prints the next target check or model command. `--force` keeps its overwrite meaning.

Feature kits (`flowguard.kit`: `feature_explorer`; code facts or replay as conformance) reuse the same model contract.
A feature model lists `Feature(name, rejects, codes, apply)` rows:
each changes a clean input (a defect the code must reject and report, or a benign variation); the kit
explores each allowed feature set once (up to `max_features=2` by default), generates the known-bad variants (`feature_variants`) and, in
`feature_conformance(features, base, review)`, runs each combination on the real code and prints a
counterexample (features, expected and observed verdict) for each one that disagrees. `codes="all"` reports all defects;
use `codes="first"` for a validator that stops at the first defect in declaration order. `requires=("other",)`
requires another feature in the set; `conflicts=("other",)` forbids their combination, symmetrically.
`exclusive=True` still excludes every other feature. Impossible requirements and unknown names are errors. Invariants without a reachable nonempty witness
are omitted; conformance still checks the clean base against the design, including adapter errors.
`read` computes a kit model's rules, known-bad and defect/benign cases from a literal `FEATURES`
(`feature_model_names` gives the same names without `apply`); a non-literal name or constraint shows `?`.

`ui-journey` and `validator` contain `REPLACE_ME` anchors: fill them with real code and tests.
`behaviour` has sample `shop/orders.py:OrderService.place` and a commented `TESTED_BY` example; replace the sample and bind real tests. Components come from IMPLEMENTED_BY; add COMPONENTS or PARENT only for placement. Run
`python -m flowguard map models <MODEL_ID>`: exit code 0 means the intended plan passes and the
broken plans are rejected.
There is no review kind; `invariant_untested` is computed by `map models`.

