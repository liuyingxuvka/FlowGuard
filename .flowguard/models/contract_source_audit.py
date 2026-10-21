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

from dataclasses import dataclass

from flowguard import (
    CodeContract,
    TEST_ASSERTION_SCOPE_EXTERNAL_CONTRACT,
    TestEvidence,
    audit_python_code_contracts,
    audit_python_test_assertions,
    review_python_contract_source_audit,
)


@dataclass(frozen=True)
class SourceAuditCase:
    name: str
    code_source: str
    test_source: str
    expected_ok: bool
    expected_codes: tuple[str, ...] = ()


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


def cases() -> tuple[SourceAuditCase, ...]:
    return (
        SourceAuditCase("good_external_contract_source", GOOD_CODE, GOOD_TEST, True),
        SourceAuditCase(
            "missing_code_symbol_blocks",
            "def other(order_id): return 'Accepted'",
            GOOD_TEST,
            False,
            ("source_contract_missing_symbol",),
        ),
        SourceAuditCase(
            "missing_input_blocks",
            "def submit_order(): return 'Accepted'",
            GOOD_TEST,
            False,
            ("source_contract_missing_input",),
        ),
        SourceAuditCase(
            "missing_return_blocks",
            "def submit_order(order_id): state = {}; state['order_status'] = 'Accepted'",
            GOOD_TEST,
            False,
            ("source_contract_missing_output",),
        ),
        SourceAuditCase(
            "missing_state_write_blocks",
            "def submit_order(order_id): return 'Accepted'",
            GOOD_TEST,
            False,
            ("source_contract_missing_state_write",),
        ),
        SourceAuditCase(
            "extra_side_effect_blocks",
            "def submit_order(order_id): publish_metric(order_id); return 'Accepted'",
            GOOD_TEST,
            False,
            ("source_contract_missing_state_write", "source_contract_extra_side_effect"),
        ),
        SourceAuditCase(
            "test_calls_helper_blocks",
            GOOD_CODE,
            "def test_submit_order(): result = helper_submit_order('order-1'); assert result == 'Accepted'",
            False,
            ("source_test_missing_code_contract_call", "source_test_internal_path_only"),
        ),
        SourceAuditCase(
            "test_without_assertion_blocks",
            GOOD_CODE,
            "def test_submit_order(): submit_order('order-1')",
            False,
            ("source_test_missing_external_assertion", "source_test_internal_path_only"),
        ),
    )


__all__ = ["cases"]


# FlowGuard contract: the source-audit cases above form a case table; conformance audits each
# case's sources with the real audit and compares.
from flowguard.kit import Case, case_table_conformance, case_table_explorer, case_table_variants  # noqa: E402

MODEL_ID = "contract_source_audit"
COMPONENTS = ["model-test"]
IMPLEMENTED_BY = {"AuditCode": "flowguard/model_test_alignment_source.py:audit_python_code_contracts",
                  "AuditTests": "flowguard/model_test_alignment_source.py:audit_python_test_assertions",
                  "Review": "flowguard/model_test_alignment_source.py:review_python_contract_source_audit"}
TESTED_BY = {"verdict_matches_case": [
    "tests/test_model_test_alignment.py:test_python_source_audit_accepts_external_contract_test"]}
SOURCES = {case.name: case for case in cases()}
CASES = tuple(Case(case.name, case.expected_ok, case.expected_codes) for case in cases())


def build_explorer():
    return case_table_explorer(CASES)


def broken_variants():
    return case_table_variants(CASES)


def _observe(case):
    item = SOURCES[case.name]
    sources = {"checkout.py": item.code_source, "test_checkout.py": item.test_source}
    code_evidence = audit_python_code_contracts((CONTRACT,), sources)
    test_evidence = audit_python_test_assertions((EVIDENCE,), (CONTRACT,), sources)
    report = review_python_contract_source_audit((CONTRACT,), (EVIDENCE,), code_evidence, test_evidence)
    return report.ok, tuple(finding.code for finding in report.findings)


def conformance():
    return case_table_conformance(CASES, _observe)
