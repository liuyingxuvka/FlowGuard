"""Collect pilot behavior only on an interpreter that supports the pilot."""

import sys


# Keep bootstrap and isolation guards collected on every supported product interpreter.
# List only the behavior files: a new guard remains collected unless explicitly classified.
collect_ignore = [
    "test_audit_command.py",
    "test_rules.py",
    "test_rule_runtime.py",
    "test_capture.py",
    "test_rule_scope.py",
    "test_audit_output.py",
    "test_no_skeleton.py",
    "test_text_report.py",
    "test_explore.py",
    "test_footprint.py",
    "test_gc1_reach.py",
    "test_gc2_offered.py",
    "test_gc3_stuck.py",
    "test_gc4_saved_files.py",
    "test_gc5_settings.py",
    "test_gc6_crash.py",
    "test_gc8_diff.py",
    "test_honest_output.py",
    "test_input_facts.py",
    "test_project.py",
    "test_proof.py",
    "test_skeleton.py",
    "test_testrec.py",
    "test_where.py",
] if sys.version_info < (3, 12) else []
