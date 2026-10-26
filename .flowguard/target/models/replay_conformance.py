"""Replay catches expected-trace corruption and duplicate effects."""
from flowguard.kit import feature_explorer,feature_variants,feature_conformance
from _engine_features import REPLAY_CONFORMANCE_FEATURES as FEATURES,clean_fixture,run_engine
MODEL_ID='replay_conformance'
PARENT='engine-conformance'
IMPLEMENTED_BY={'Replay': 'flowguard/conformance.py:replay_trace'}
TESTED_BY = {'each_defect_rejected': ['tests/test_python_function_state_verification_owner.py:test_the_real_engine_reports_every_defect_alone_and_in_pairs'], 'every_defect_reported': ['tests/test_python_function_state_verification_owner.py:test_the_real_engine_reports_every_defect_alone_and_in_pairs']}
def build_explorer():return feature_explorer(FEATURES)
def broken_variants():return feature_variants(FEATURES)
def conformance():return feature_conformance(FEATURES,clean_fixture,run_engine)

# No benign feature exists in this disjoint table. The current kit generates
# two witnessed rules; feature_conformance still always checks the clean fixture,
# and the shared owner oracle covers clean acceptance across all three tables.
