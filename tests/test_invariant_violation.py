import unittest
from dataclasses import dataclass

from flowguard import Explorer, FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.explorer import enumerate_input_sequences


@dataclass(frozen=True)
class State:
    records: tuple[str, ...] = ()


class AppendRecord:
    name = "AppendRecord"
    accepted_input_type = str

    def apply(self, input_obj, state):
        return (
            FunctionResult(
                output=input_obj,
                new_state=State(state.records + (input_obj,)),
                label="record_added",
            ),
        )


def no_duplicate_records(state, trace):
    del trace
    if len(state.records) != len(set(state.records)):
        return InvariantResult.fail("records contains duplicates")
    return InvariantResult.pass_()


class InvariantViolationTests(unittest.TestCase):
    def test_repeated_input_sequences_are_enumerated(self):
        self.assertEqual(
            (("job_001",), ("job_001", "job_001")),
            enumerate_input_sequences(("job_001",), 2),
        )

    def test_repeated_input_can_violate_invariant(self):
        explorer = Explorer(
            workflow=Workflow((AppendRecord(),)),
            initial_states=(State(),),
            external_inputs=("job_001",),
            invariants=(
                Invariant(
                    name="no_duplicate_records",
                    description="records must be unique",
                    predicate=no_duplicate_records,
                ),
            ),
            max_sequence_length=2,
        )

        report = explorer.explore()

        self.assertFalse(report.ok)
        self.assertEqual("no_duplicate_records", report.violations[0].invariant_name)
        self.assertIn("duplicates", report.violations[0].message)


if __name__ == "__main__":
    unittest.main()
