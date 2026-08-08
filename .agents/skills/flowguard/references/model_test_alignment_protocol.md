# Model-Test Alignment Handoff

This kernel-side file is a compact handoff stub. The detailed protocol is
owned by the direct satellite skill `flowguard-model-test-alignment`.

Load:
`.agents/skills/flowguard-model-test-alignment/references/model_test_alignment_protocol.md`

Use this route when model obligations, owner external code contracts, and ordinary test evidence need current parity before a done, release, publish, or full-confidence claim, or when file/artifact/AI work-package payload cases need external evidence.

Keep the hard gates: use the real FlowGuard package, preserve `Input x State -> Set(Output x State)` boundaries, keep stale/skipped evidence visible, require structured payload case evidence, and feed missing obligations or duplicate primary evidence to `review_model_maturation_loop(...)` before broad confidence. Supply task/coverage identity plus prediction/falsifier fields; rerun after each candidate model or evidence edit until the receipt is `model_maturation_closed_for_task` or names an explicit canonical `model_maturation_external_input_required`, `model_maturation_scope_excluded`, `model_maturation_progress_stalled`, or `model_maturation_iteration_limit` terminal reason. Never replace this evidence with an AI self-report.
