"""Exploration and loop checks report every bounded defect."""
from flowguard.kit import feature_explorer,feature_variants,feature_conformance
from _engine_features import ENGINE_EXPLORE_FEATURES as FEATURES,clean_fixture,run_engine
MODEL_ID='engine_explore'
PARENT='engine-explore'
IMPLEMENTED_BY={'Explore': 'flowguard/explorer.py:Explorer.explore', 'Loops': 'flowguard/loop.py:check_loops'}
TESTED_BY = {'each_defect_rejected': ['tests/test_python_function_state_verification_owner.py:test_the_real_engine_reports_every_defect_alone_and_in_pairs'], 'every_defect_reported': ['tests/test_python_function_state_verification_owner.py:test_the_real_engine_reports_every_defect_alone_and_in_pairs', 'tests/test_python_function_state_verification_owner.py:test_branch_oracle_rejects_loss_of_second_nondeterministic_result']}
def build_explorer():return feature_explorer(FEATURES)
def broken_variants():return feature_variants(FEATURES)
def conformance():return feature_conformance(FEATURES,clean_fixture,run_engine)

# No benign feature exists in this disjoint table. The current kit generates
# two witnessed rules; feature_conformance still always checks the clean fixture,
# and the shared owner oracle covers clean acceptance across all three tables.
