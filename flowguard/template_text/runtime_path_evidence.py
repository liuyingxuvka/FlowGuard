"""Template text for FlowGuard runtime path evidence route."""

from __future__ import annotations

RUNTIME_PATH_EVIDENCE_MODEL_TEMPLATE = '''"""FlowGuard Risk Purpose Header.

Created with FlowGuard:
https://github.com/liuyingxuvka/FlowGuard

Purpose:
Models runtime path evidence for real code nodes that should line up with a
FlowGuard model.

Guards against:
- progress logs that do not name the FlowGuard model being compared;
- broad confidence claims without leaf runtime node observations;
- stale, non-passing, internal-only, or out-of-order runtime path evidence;
- runtime gateway or parent-model claims that cannot point to child path ids.

Use before editing:
real-code instrumentation, test adapters, model-test alignment rows, leaf
boundary matrices, parent/child reattachment, runtime gateway bindings, or
closure evidence.

Run:
python .flowguard/runtime_path_evidence/run_checks.py
"""

from __future__ import annotations

from flowguard import (
    RuntimeNodeContract,
    RuntimeNodeObservation,
    RuntimePathAlignmentPlan,
    RuntimePathRecorder,
    review_runtime_path_alignment,
)


MODEL_ID = "checkout.leaf"
MODEL_PATH = ".flowguard/checkout_leaf/model.py"
OBLIGATION_ID = "accept_valid_order"
CODE_CONTRACT_ID = "checkout.submit"


def node_contracts():
    return (
        RuntimeNodeContract(
            "validate_order",
            model_id=MODEL_ID,
            model_path=MODEL_PATH,
            leaf_model_id=MODEL_ID,
            model_obligation_id=OBLIGATION_ID,
            code_contract_id=CODE_CONTRACT_ID,
            boundary_id="checkout.submit.boundary",
            allowed_outputs=("accepted",),
            allowed_state_writes=("order_status",),
            sequence_index=0,
        ),
    )


def good_plan():
    recorder = RuntimePathRecorder("run:checkout:happy-path")
    recorder.record(
        "validate_order",
        model_id=MODEL_ID,
        model_path=MODEL_PATH,
        leaf_model_id=MODEL_ID,
        model_obligation_id=OBLIGATION_ID,
        code_contract_id=CODE_CONTRACT_ID,
        boundary_id="checkout.submit.boundary",
        observed_output="accepted",
        observed_state_writes=("order_status",),
        evidence_id="runtime-path:validate-order:v1",
        progress_message="accepted valid order at model-owned boundary",
    )
    return RuntimePathAlignmentPlan(
        "checkout-runtime-path",
        model_id=MODEL_ID,
        node_contracts=node_contracts(),
        runs=(recorder.to_run(),),
        require_exact_path=True,
    )


def broken_plan():
    return RuntimePathAlignmentPlan(
        "checkout-runtime-path-broken",
        model_id=MODEL_ID,
        node_contracts=node_contracts(),
        observations=(
            RuntimeNodeObservation(
                "obs:internal-helper",
                "internal_helper_only",
                run_id="run:checkout:broken",
                model_id=MODEL_ID,
                model_path=MODEL_PATH,
                assertion_scope="internal_path",
                result_status="skipped",
                progress_message="helper log did not prove the model node",
            ),
        ),
        require_exact_path=True,
    )


def review():
    return review_runtime_path_alignment(good_plan()), review_runtime_path_alignment(broken_plan())
'''

RUNTIME_PATH_EVIDENCE_RUN_CHECKS_TEMPLATE = '''"""Run the Runtime Path Evidence template checks."""

from __future__ import annotations

from model import good_plan, review


def main() -> int:
    good_report, broken_report = review()
    print("=== flowguard runtime path evidence ===")
    print(good_report.format_text())
    print()
    print("runtime progress:")
    print(good_plan().runs[0].format_progress_lines())
    print()
    print("broken evidence:")
    print(broken_report.format_text(max_findings=5))
    ok = good_report.ok and not broken_report.ok
    print(f"status: {'OK' if ok else 'FAILED'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''

RUNTIME_PATH_EVIDENCE_NOTES_TEMPLATE = """# FlowGuard Runtime Path Evidence

Runtime path evidence connects real code progress output back to a FlowGuard
model. Each emitted node should name the compared `model_id`, `model_path`,
`node_id`, run id, status, and the relevant obligation or code contract when
known.

Use it at leaf model boundaries, state writes, side effects, parent/child
handoffs, runtime gateway writes, and final confidence claims. Do not treat
anonymous progress logs as FlowGuard evidence.
"""

__all__ = [
    'RUNTIME_PATH_EVIDENCE_MODEL_TEMPLATE',
    'RUNTIME_PATH_EVIDENCE_RUN_CHECKS_TEMPLATE',
    'RUNTIME_PATH_EVIDENCE_NOTES_TEMPLATE',
]
