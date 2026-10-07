"""Engine-owner oracles must detect real broken behavior, not just emit rows."""
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


PATH = Path(__file__).resolve().parents[1] / ".flowguard/models/owners/python_function_state_verification/model.py"
NAME = "_python_function_state_verification_owner_test"
SPEC = importlib.util.spec_from_file_location(NAME, PATH)
OWNER = importlib.util.module_from_spec(SPEC)
sys.modules[NAME] = OWNER
SPEC.loader.exec_module(OWNER)


class PythonEngineOwnerTests(unittest.TestCase):
    def test_actual_library_satisfies_each_declared_positive_and_negative_oracle(self):
        cases = OWNER.run_review()["native_cases"]
        failed = [case["name"] for case in cases if not case["ok"]]
        self.assertEqual([], failed)
        bad = {case["finding_codes"][0]: case for case in cases if case["case_kind"] == "bad"}
        self.assertEqual(set(OWNER.PROTECTED_FAILURE_IDS), set(bad))
        for case in bad.values():
            self.assertEqual("violation", case["observed_status"], case["name"])
        self.assertTrue(any(case["name"] == "runner_preserves_supplied_exploration_report"
                            and case["ok"] for case in cases))

    def test_invocation_priority_oracle_rejects_running_lower_priority_hook(self):
        original = OWNER.invoke_block

        def wrong_priority(block, value, state):
            if isinstance(block, OWNER.Priority):
                return block.run(value, state)
            return original(block, value, state)

        with patch.object(OWNER, "invoke_block", wrong_priority):
            cases = OWNER.run_review()["native_cases"]
        self.assertFalse(next(case for case in cases if case["name"] == "invocation_and_input_hooks")["ok"])

    def test_branch_oracle_rejects_loss_of_second_nondeterministic_result(self):
        import flowguard.workflow as workflow_module
        original = workflow_module.normalize_function_results

        def lose_branch(raw):
            values = original(raw)
            return values[:1]

        with patch.object(workflow_module, "normalize_function_results", lose_branch):
            cases = OWNER.run_review()["native_cases"]
        by_name = {case["name"]: case for case in cases}
        self.assertFalse(by_name["all_nondeterministic_branches"]["ok"])
        self.assertFalse(by_name["unsafe_second_branch_detected"]["ok"])


if __name__ == "__main__":
    unittest.main()
