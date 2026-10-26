import json
import unittest
from dataclasses import dataclass

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.scenario import OracleCheckResult, Scenario, ScenarioExpectation, run_exact_sequence


@dataclass(frozen=True)
class State:
    values: tuple[str, ...] = ()


class AddValue:
    name = "AddValue"
    accepted_input_type = str

    def apply(self, input_obj, state):
        return (
            FunctionResult(
                output=input_obj,
                new_state=State(state.values + (input_obj,)),
                label="added",
            ),
        )


def no_duplicate_values(state, trace):
    del trace
    if len(state.values) != len(set(state.values)):
        return InvariantResult.fail("duplicate values")
    return InvariantResult.pass_()


class ScenarioCoreTests(unittest.TestCase):
    def test_run_exact_sequence_returns_structured_run(self):
        scenario = Scenario(
            name="single",
            description="single add",
            initial_state=State(),
            external_input_sequence=("a",),
            expected=ScenarioExpectation(required_trace_labels=("added",)),
            workflow=Workflow((AddValue(),)),
            invariants=(
                Invariant("no_duplicates", "no duplicates", no_duplicate_values),
            ),
        )

        run = run_exact_sequence(
            scenario.workflow,
            scenario.initial_state,
            scenario.external_input_sequence,
            scenario.invariants,
            scenario,
        )

        self.assertEqual("ok", run.observed_status)
        self.assertEqual((State(("a",)),), run.final_states)
        self.assertEqual(1, len(run.traces))
        self.assertEqual("single", run.to_dict()["scenario"]["name"])




if __name__ == "__main__":
    unittest.main()
