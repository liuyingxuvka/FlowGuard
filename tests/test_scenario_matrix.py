import unittest
from dataclasses import dataclass

from flowguard.scenario import ScenarioExpectation
from flowguard.scenario_matrix import ScenarioMatrixBuilder


@dataclass(frozen=True)
class State:
    status: str = "empty"


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


if __name__ == "__main__":
    unittest.main()
