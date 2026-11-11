# Tests retired with the 4.3 sealed comparison

FlowGuard 4.3 records each real call's JSON arguments and result and compares the recorded calls
after the session in a sealed, source-only environment (design section 4.5). The mechanisms below
were removed with that change. A test whose whole subject was one of them is listed here: its name,
the removed mechanism and the design section. Every assertion of such a test that still holds under
4.3 lives on in a migrated test of the same file or in the test named in the last column.

| Test | Removed mechanism | Design | Still covered by |
|---|---|---|---|
| `tests/intent_engine/test_runtime_candidate.py::test_default_grid_includes_old_new_constants_actual_and_neighbours` | the default replay grid of a changed function (old/new constants, actual value and neighbours) | 4.5: `changed` uses only the recorded inputs | `test_default_runtime_signals.py::test_fixed_6_same_name_copies_disagree_on_a_real_shared_input` (±1 and constants for copies) |
| `tests/intent_engine/test_runtime_candidate.py::test_historical_code_keeps_current_anchor_identity_and_separate_old_line` | old code installed into the live function (`old_code` swap) and its event path | 4.5 (sealed environment, no module loaded), 6.5 (no old-code rerun) | `test_runtime_candidate.py::test_prior_code_scope_never_swaps_the_live_module_even_after_exception` |
| `tests/intent_engine/test_runtime_candidate.py::test_axis_provider_cannot_recursively_reenter_instrumented_tool_helpers` | axis providers called before each real call | 4.5: record only, no in-test replay | `test_runtime_candidate.py::test_each_real_context_is_recorded_and_private_calls_are_not` |
| `tests/intent_engine/test_runtime_candidate.py::test_explicit_partition_keeps_every_representative_and_actual_without_cross_field_constants` | explicit replay partition (axes and representatives) before each real call | 4.5: `changed` uses only the recorded inputs | `test_anchor_differences.py::test_real_calls_at_the_union_representatives_give_the_class_report` |
