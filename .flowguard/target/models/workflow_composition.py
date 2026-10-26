"""Workflow invocation and result normalization preserve all declared branches."""
from flowguard.kit import feature_explorer,feature_variants,feature_conformance
from _engine_features import WORKFLOW_COMPOSITION_FEATURES as FEATURES,clean_fixture,run_engine
MODEL_ID='workflow_composition'
PARENT='engine-core'
IMPLEMENTED_BY={'InvokeBlock': 'flowguard/core.py:invoke_block'}
TESTED_BY = {'clean_input_accepted': ['tests/test_python_function_state_verification_owner.py:test_the_real_engine_reports_every_defect_alone_and_in_pairs', 'tests/test_python_function_state_verification_owner.py:test_invocation_priority_oracle_rejects_running_lower_priority_hook', 'tests/test_python_function_state_verification_owner.py:test_branch_oracle_rejects_loss_of_second_nondeterministic_result'], 'each_defect_rejected': ['tests/test_python_function_state_verification_owner.py:test_the_real_engine_reports_every_defect_alone_and_in_pairs'], 'every_defect_reported': ['tests/test_python_function_state_verification_owner.py:test_the_real_engine_reports_every_defect_alone_and_in_pairs'], 'benign_features_neutral': ['tests/test_python_function_state_verification_owner.py:test_the_real_engine_reports_every_defect_alone_and_in_pairs', 'tests/test_python_function_state_verification_owner.py:test_invocation_priority_oracle_rejects_running_lower_priority_hook']}
def build_explorer():return feature_explorer(FEATURES)
def broken_variants():return feature_variants(FEATURES)
def conformance():return feature_conformance(FEATURES,clean_fixture,run_engine)
