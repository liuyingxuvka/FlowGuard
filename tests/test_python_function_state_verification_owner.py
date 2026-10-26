"""Engine-owner oracles must detect real broken behavior: the engine's feature model on the real engine."""
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import flowguard.workflow as workflow_module

PATH = Path(__file__).resolve().parents[1] / ".flowguard/models/python_function_state_verification.py"
NAME = "_python_function_state_verification_owner_test"
from flowguard.map.mapfile import load_map, resolve_model_path
from flowguard.map.targetfile import build_target_view, load_target
active = load_target(PATH.parents[2])
if active is not None:
    view = build_target_view(PATH.parents[2], load_map(PATH.parents[2]), active)
    PATH = resolve_model_path(PATH.parents[2], ".flowguard/models/python_function_state_verification.py", view=view)
SPEC = importlib.util.find_spec("python_function_state_verification") if active is None else None
if SPEC is None:
    SPEC = importlib.util.spec_from_file_location(NAME, PATH)
OWNER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = OWNER
SPEC.loader.exec_module(OWNER)


def caught(report):
    return {(violation.rule_name, violation.features) for violation in report.violations}


def owner_report(*feature_names):
    """Keep the full engine check by default; focus an oracle on its named contrast."""
    if not feature_names:
        return OWNER.conformance()
    selected = tuple(feature for feature in OWNER.FEATURES if feature.name in feature_names)
    if {feature.name for feature in selected} != set(feature_names):
        raise ValueError("oracle names an unknown engine feature")
    return OWNER.feature_conformance(selected, OWNER.clean_fixture, OWNER.run_engine)


class PythonEngineOwnerTests(unittest.TestCase):
    def test_the_real_engine_reports_every_defect_alone_and_in_pairs(self):
        report = owner_report()
        self.assertTrue(report.ok, report.format_text())
        self.assertEqual(122, report.executed)            # clean fixture, 16 features, 105 nonexclusive pairs; writes are checked by ports

    def test_invocation_priority_oracle_rejects_running_lower_priority_hook(self):
        original = workflow_module.invoke_block

        def wrong_priority(block, value, state):
            if hasattr(block, "run"):
                return block.run(value, state)
            return original(block, value, state)

        with patch.object(workflow_module, "invoke_block", wrong_priority):
            report = owner_report("block_invoked_through_run")
        self.assertIn(("clean_input_accepted", ()), caught(report))
        self.assertIn(("benign_features_neutral", ("block_invoked_through_run",)), caught(report))

    def test_branch_oracle_rejects_loss_of_second_nondeterministic_result(self):
        original = workflow_module.normalize_function_results

        def lose_branch(raw):
            return original(raw)[:1]

        with patch.object(workflow_module, "normalize_function_results", lose_branch):
            report = owner_report("unsafe_second_branch", "block_invoked_through_run")
        self.assertIn(("clean_input_accepted", ()), caught(report))             # both:b is never reached
        self.assertIn(("every_defect_reported", ("unsafe_second_branch",)), caught(report))   # right is lost


if __name__ == "__main__":
    unittest.main()
