"""FlowGuard rollout model for Python contract source audit.

Purpose: review the source-audit layer that checks whether real Python code
and real Python tests support declared model/test/code external contracts.
Guards against: trusting declared CodeContract/TestEvidence rows when the code
symbol is missing, inputs/outputs/state writes/side effects disagree, tests do
not call the target code surface, or tests have no external assertion.

Run:
python -m flowguard map models contract_source_audit
"""

from __future__ import annotations

from flowguard import (
    CodeContract,
    TEST_ASSERTION_SCOPE_EXTERNAL_CONTRACT,
    TestEvidence,
    audit_python_code_contracts,
    audit_python_test_assertions,
    review_python_contract_source_audit,
)


CONTRACT = CodeContract(
    "checkout_submit",
    path="checkout.py",
    symbol="submit_order",
    implements_obligations=("accept_valid_order",),
    external_inputs=("order_id",),
    external_outputs=("Accepted",),
    state_writes=("order_status",),
)

EVIDENCE = TestEvidence(
    "test_submit_order",
    test_name="test_submit_order",
    path="test_checkout.py",
    result_status="passed",
    covered_obligations=("accept_valid_order",),
    covered_code_contracts=("checkout_submit",),
    assertion_scope=TEST_ASSERTION_SCOPE_EXTERNAL_CONTRACT,
)


GOOD_CODE = """
def submit_order(order_id):
    state = {}
    state["order_status"] = "Accepted"
    return "Accepted"
"""

GOOD_TEST = """
def test_submit_order():
    result = submit_order("order-1")
    assert result == "Accepted"
"""


# FlowGuard contract (feature kit): each broken source is a feature that changes the good code or test
# above; the kit explores every feature alone and every pair, and conformance audits each combination with
# the real source audit.
from flowguard.kit import Feature, feature_conformance, feature_explorer, feature_variants  # noqa: E402

MODEL_ID = "contract_source_audit"
COMPONENTS = ["model-test"]
IMPLEMENTED_BY = {"AuditCode": "flowguard/model_test_alignment_source.py:audit_python_code_contracts",
                  "AuditTests": "flowguard/model_test_alignment_source.py:audit_python_test_assertions",
                  "Review": "flowguard/model_test_alignment_source.py:review_python_contract_source_audit"}
TESTED_BY = {"clean_input_accepted": [
    "tests/test_model_test_alignment.py:test_python_source_audit_accepts_external_contract_test"]}


def _edit(path: str, old: str, new: str):
    def apply(sources: dict) -> dict:
        assert old in sources[path], (path, old)
        return {**sources, path: sources[path].replace(old, new, 1)}
    return apply


CODE, TEST = "checkout.py", "test_checkout.py"
FEATURES = (
    Feature("missing_code_symbol", True, ("source_contract_missing_symbol",),
            _edit(CODE, "def submit_order(", "def other("), exclusive=True),   # removes what the code features edit
    Feature("missing_input", True, ("source_contract_missing_input",),
            _edit(CODE, "def submit_order(order_id):", "def submit_order():")),
    Feature("missing_return", True, ("source_contract_missing_output",), _edit(CODE, '    return "Accepted"\n', "")),
    Feature("missing_state_write", True, ("source_contract_missing_state_write",),
            _edit(CODE, '    state["order_status"] = "Accepted"\n', "")),
    Feature("extra_side_effect", True, ("source_contract_extra_side_effect",),
            _edit(CODE, "    state = {}\n", "    state = {}\n    publish_metric(order_id)\n")),
    Feature("test_calls_helper", True, ("source_test_missing_code_contract_call", "source_test_internal_path_only"),
            _edit(TEST, "result = submit_order(", "result = helper_submit_order(")),
    Feature("test_without_assertion", True, ("source_test_missing_external_assertion", "source_test_internal_path_only"),
            _edit(TEST, '    assert result == "Accepted"\n', "")),
    Feature("unrelated_helper_in_module", False, (),
            _edit(CODE, "def submit_order(", "def format_order(order_id):\n    return str(order_id)\n\n\ndef submit_order(")),
)


def build_explorer():
    return feature_explorer(FEATURES)


def broken_variants():
    return feature_variants(FEATURES)


def _audit(sources: dict):
    code_evidence = audit_python_code_contracts((CONTRACT,), sources)
    test_evidence = audit_python_test_assertions((EVIDENCE,), (CONTRACT,), sources)
    report = review_python_contract_source_audit((CONTRACT,), (EVIDENCE,), code_evidence, test_evidence)
    return report.ok, tuple(finding.code for finding in report.findings)


def conformance():
    return feature_conformance(FEATURES, lambda: {CODE: GOOD_CODE, TEST: GOOD_TEST}, _audit)
