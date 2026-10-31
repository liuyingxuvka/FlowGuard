"""Collect pilot behavior only on an interpreter that supports the pilot."""

import sys


# Keep bootstrap and isolation guards collected on every supported product interpreter.
# List only the behavior files: a new guard remains collected unless explicitly classified.
collect_ignore = [
    "test_explore.py",
    "test_footprint.py",
    "test_gc1_reach.py",
    "test_gc3_stuck.py",
    "test_honest_output.py",
    "test_project.py",
    "test_proof.py",
    "test_skeleton.py",
    "test_testrec.py",
] if sys.version_info < (3, 12) else []
