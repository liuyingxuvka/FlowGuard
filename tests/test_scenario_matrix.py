import unittest
from dataclasses import dataclass

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.explorer import Explorer
from flowguard.scenario import ScenarioExpectation
from flowguard.scenario_matrix import ScenarioMatrixBuilder, synthesize_challenge_scenarios_from_report


@dataclass(frozen=True)
class State:
    status: str = "empty"
    values: tuple[str, ...] = ()


class AppendValue:
    name = "AppendValue"

    def apply(self, input_obj, state):
        return (
            FunctionResult(
                output=input_obj,
                new_state=State(status="recorded", values=state.values + (input_obj,)),
                label="record_added",
                reason="append input to model state",
            ),
        )


def no_duplicate_model_values(state, trace):
    del trace
    if len(state.values) != len(set(state.values)):
        return InvariantResult.fail("duplicate values")
    return InvariantResult.pass_()


class ScenarioMatrixBuilderTests(unittest.TestCase):
    def test_builder_generates_small_deterministic_matrix(self):
        scenarios = (
            ScenarioMatrixBuilder(
                name_prefix="job_matching",
                initial_states=(State(),),
                inputs=("job_a", "job_b"),
            )
            .single_inputs()
            .repeat_same(max_repeats=2)
            .pairwise_orders()
            .aba()
            .build()
        )

        self.assertEqual(8, len(scenarios))
        self.assertEqual("job_matching_single_input1", scenarios[0].name)
        self.assertEqual(("job_a",), scenarios[0].external_input_sequence)
        self.assertEqual(("job_a", "job_a"), scenarios[2].external_input_sequence)
        self.assertEqual("needs_human_review", scenarios[0].expected.expected_status)
        self.assertIn("repeated_input", scenarios[-1].tags)

    def test_builder_respects_sequence_length_and_scenario_limit(self):
        scenarios = (
            ScenarioMatrixBuilder(
                name_prefix="bounded",
                initial_states=(State(),),
                inputs=("a", "b"),
                max_sequence_length=2,
                max_scenarios=3,
            )
            .single_inputs()
            .repeat_same()
            .pairwise_orders()
            .aba()
            .build()
        )

        self.assertEqual(3, len(scenarios))
        self.assertTrue(all(len(scenario.external_input_sequence) <= 2 for scenario in scenarios))
        self.assertFalse(any("aba" in scenario.tags for scenario in scenarios))

    def test_builder_supports_special_initial_states_and_custom_expectation(self):
        expectation = ScenarioExpectation(expected_status="ok", summary="expected ok")
        scenarios = (
            ScenarioMatrixBuilder(
                name_prefix="states",
                initial_states=(State("normal"),),
                inputs=("x",),
                expectation=expectation,
                tags=("dedup",),
            )
            .special_initial_states((State("invalid"),), tag="invalid_initial_state", notes="invalid seed")
            .single_inputs()
            .build()
        )

        self.assertEqual(2, len(scenarios))
        self.assertEqual("states_single_input1_state1", scenarios[0].name)
        self.assertEqual("states_single_input1_state2", scenarios[1].name)
        self.assertIn("invalid_initial_state", scenarios[1].tags)
        self.assertEqual("ok", scenarios[1].expected.expected_status)
        self.assertIn("invalid seed", scenarios[1].notes)

    def test_builder_generates_adversarial_challenge_patterns(self):
        scenarios = (
            ScenarioMatrixBuilder(
                name_prefix="risk",
                initial_states=(State(),),
                inputs=("a", "b"),
            )
            .challenge_patterns()
            .build()
        )

        names = {scenario.name for scenario in scenarios}
        self.assertIn("risk_partial_failure_retry_input1", names)
        self.assertIn("risk_duplicate_delivery_input1x3", names)
        self.assertIn("risk_stale_state_after_change_input1_then_input2", names)
        self.assertIn("risk_delayed_replay_input1_input2_input1", names)
        self.assertIn("risk_terminal_replay_input1_input2x2", names)
        self.assertTrue(all(scenario.expected.expected_status == "needs_human_review" for scenario in scenarios))
        self.assertTrue(all("challenge" in scenario.tags for scenario in scenarios))
        self.assertTrue(any("side effect may have succeeded" in scenario.notes for scenario in scenarios))
        self.assertTrue(any("must not reopen completed work" in scenario.notes for scenario in scenarios))

    def test_challenge_patterns_respect_existing_limits(self):
        scenarios = (
            ScenarioMatrixBuilder(
                name_prefix="bounded_challenge",
                initial_states=(State(),),
                inputs=("a", "b"),
                max_sequence_length=2,
                max_scenarios=3,
            )
            .challenge_patterns()
            .build()
        )

        self.assertEqual(3, len(scenarios))
        self.assertTrue(all(len(scenario.external_input_sequence) <= 2 for scenario in scenarios))
        self.assertFalse(any("duplicate_delivery" in scenario.tags for scenario in scenarios))
        self.assertTrue(any("partial_failure_retry" in scenario.tags for scenario in scenarios))

    def test_model_derived_challenges_use_explorer_evidence(self):
        workflow = Workflow((AppendValue(),), name="append")
        invariant = Invariant(
            "no_duplicate_values",
            "model values remain unique",
            no_duplicate_model_values,
        )
        report = Explorer(
            workflow=workflow,
            initial_states=(State(),),
            external_inputs=("a", "b"),
            invariants=(invariant,),
            max_sequence_length=2,
        ).explore()

        scenarios = synthesize_challenge_scenarios_from_report(
            name_prefix="derived",
            report=report,
            workflow=workflow,
            invariants=(invariant,),
            max_scenarios=5,
        )

        self.assertTrue(any("model_counterexample" in scenario.tags for scenario in scenarios))
        counterexample = next(scenario for scenario in scenarios if "model_counterexample" in scenario.tags)
        self.assertEqual(("a", "a"), counterexample.external_input_sequence)
        self.assertEqual("needs_human_review", counterexample.expected.expected_status)
        self.assertIn("Explorer found invariant", counterexample.notes)
        self.assertIn("model-derived", counterexample.description)


if __name__ == "__main__":
    unittest.main()
