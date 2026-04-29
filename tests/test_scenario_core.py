import json
import unittest
from dataclasses import dataclass

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.review import review_scenarios, scenario_status_ok
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

    def test_review_report_distinguishes_statuses(self):
        workflow = Workflow((AddValue(),))
        invariant = Invariant("no_duplicates", "no duplicates", no_duplicate_values)
        scenarios = (
            Scenario(
                "ok_case",
                "ok",
                State(),
                ("a",),
                ScenarioExpectation(expected_status="ok", required_trace_labels=("added",)),
                workflow=workflow,
                invariants=(invariant,),
            ),
            Scenario(
                "expected_violation",
                "duplicate expected",
                State(),
                ("a", "a"),
                ScenarioExpectation(
                    expected_status="violation",
                    expected_violation_names=("no_duplicates",),
                ),
                workflow=workflow,
                invariants=(invariant,),
            ),
            Scenario(
                "unexpected_violation",
                "duplicate unexpected",
                State(),
                ("a", "a"),
                ScenarioExpectation(expected_status="ok"),
                workflow=workflow,
                invariants=(invariant,),
            ),
            Scenario(
                "missing_expected_violation",
                "expected but absent",
                State(),
                ("a",),
                ScenarioExpectation(
                    expected_status="violation",
                    expected_violation_names=("no_duplicates",),
                ),
                workflow=workflow,
                invariants=(invariant,),
            ),
            Scenario(
                "needs_review",
                "manual",
                State(),
                ("a",),
                ScenarioExpectation(expected_status="needs_human_review"),
                workflow=workflow,
                invariants=(invariant,),
            ),
            Scenario(
                "oracle_mismatch",
                "custom failure",
                State(),
                ("a",),
                ScenarioExpectation(
                    expected_status="ok",
                    custom_checks=(
                        lambda run: OracleCheckResult(False, "custom failed", violation_name="custom"),
                    ),
                ),
                workflow=workflow,
                invariants=(invariant,),
            ),
        )

        report = review_scenarios(scenarios)
        statuses = {result.scenario_name: result.status for result in report.results}
        ok_values = {result.scenario_name: result.ok for result in report.results}

        self.assertEqual("pass", statuses["ok_case"])
        self.assertEqual("expected_violation_observed", statuses["expected_violation"])
        self.assertEqual("unexpected_violation", statuses["unexpected_violation"])
        self.assertEqual("missing_expected_violation", statuses["missing_expected_violation"])
        self.assertEqual("needs_human_review", statuses["needs_review"])
        self.assertEqual("oracle_mismatch", statuses["oracle_mismatch"])
        self.assertIs(True, ok_values["ok_case"])
        self.assertIs(True, ok_values["expected_violation"])
        self.assertIs(False, ok_values["unexpected_violation"])
        self.assertIs(False, ok_values["missing_expected_violation"])
        self.assertIs(None, ok_values["needs_review"])
        self.assertIs(False, ok_values["oracle_mismatch"])
        self.assertFalse(report.ok)
        formatted = report.format_text()
        self.assertIn("Scenario: ok_case", formatted)
        self.assertIn("Outcome:", formatted)
        data = json.loads(report.to_json_text())
        self.assertEqual(report.total_scenarios, data["total_scenarios"])
        first_result = data["results"][0]
        self.assertIs(True, first_result["ok"])
        self.assertIn("status_explanation", first_result)

    def test_scenario_status_ok_explains_unknown_as_review_needed(self):
        self.assertIsNone(scenario_status_ok("unrecognized_status"))


if __name__ == "__main__":
    unittest.main()
