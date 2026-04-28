import json
import unittest
from dataclasses import dataclass

from flowguard.contract import (
    FunctionContract,
    check_refinement_projection,
    check_trace_contracts,
)
from flowguard.trace import Trace, TraceStep


@dataclass(frozen=True)
class State:
    source: tuple[str, ...] = ()
    records: tuple[str, ...] = ()
    cache: tuple[str, ...] = ()


@dataclass(frozen=True)
class Input:
    value: str


@dataclass(frozen=True)
class Output:
    value: str


class ContractCoreTests(unittest.TestCase):
    def test_trace_contract_accepts_declared_transition(self):
        old = State()
        new = State(records=("A",))
        step = TraceStep(
            external_input=Input("A"),
            function_name="Record",
            function_input=Input("A"),
            function_output=Output("A"),
            old_state=old,
            new_state=new,
            label="record",
            reason="recorded",
        )
        trace = Trace(initial_state=old, steps=(step,))
        report = check_trace_contracts(
            trace,
            (
                FunctionContract(
                    function_name="Record",
                    accepted_input_type=Input,
                    output_type=Output,
                    writes=("records",),
                ),
            ),
        )

        self.assertTrue(report.ok, report.format_text())

    def test_trace_contract_reports_forbidden_and_undeclared_writes(self):
        old = State()
        new = State(records=("A",), cache=("A",))
        step = TraceStep(
            external_input=Input("A"),
            function_name="Record",
            function_input=Input("A"),
            function_output=Output("A"),
            old_state=old,
            new_state=new,
            label="record",
            reason="recorded",
        )
        trace = Trace(initial_state=old, steps=(step,))
        report = check_trace_contracts(
            trace,
            (
                FunctionContract(
                    function_name="Record",
                    accepted_input_type=Input,
                    output_type=Output,
                    writes=("records",),
                    forbidden_writes=("cache",),
                ),
            ),
        )

        self.assertFalse(report.ok)
        self.assertIn("forbidden_write", report.violation_names())
        self.assertIn("undeclared_write", report.violation_names())
        loaded = json.loads(report.to_json_text())
        self.assertEqual(2, len(loaded["violations"]))

    def test_refinement_projection_compares_projected_state(self):
        report = check_refinement_projection(
            expected_abstract_state=State(records=("A",)),
            real_state={"records": ["A"], "private_log": ["raw"]},
            projection=lambda raw: State(records=tuple(raw["records"])),
            function_name="Record",
        )

        self.assertTrue(report.ok)

        mismatch = check_refinement_projection(
            expected_abstract_state=State(records=("A",)),
            real_state={"records": ["B"]},
            projection=lambda raw: State(records=tuple(raw["records"])),
            function_name="Record",
        )
        self.assertFalse(mismatch.ok)
        self.assertIn("refinement_projection_mismatch", mismatch.violation_names())


if __name__ == "__main__":
    unittest.main()
