"""The public facade is plain data: every name resolves, importing is cheap."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

import flowguard

ROOT = Path(__file__).resolve().parents[1]


class PublicApiTests(unittest.TestCase):
    def test_every_public_name_resolves_from_its_owner(self) -> None:
        missing = [name for name in flowguard.__all__ if not hasattr(flowguard, name)]
        self.assertEqual([], missing)

    def test_public_names_are_unique_and_sorted(self) -> None:
        self.assertEqual(sorted(set(flowguard.__all__)), list(flowguard.__all__))

    def test_import_flowguard_loads_only_the_facade(self) -> None:
        code = "import sys, flowguard; print(sorted(m for m in sys.modules if m.startswith('flowguard')))"
        result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, check=True)
        self.assertEqual("['flowguard']", result.stdout.strip())

    def test_core_engine_names_are_public(self) -> None:
        for name in ("Workflow", "FunctionResult", "Invariant", "replay_trace", "Scenario", "Explorer"):
            self.assertIn(name, flowguard.__all__)

    def test_unknown_attribute_is_attribute_error(self) -> None:
        with self.assertRaises(AttributeError):
            getattr(flowguard, "no_such_public_name")

    def test_version_matches_pyproject(self) -> None:
        text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn(f'version = "{flowguard.__version__}"', text)


    def test_consumer_names_stay_public(self) -> None:
        # Original consumer module paths are part of the compatibility promise.
        imports = (
            ('flowguard', 'FunctionResult'),
            ('flowguard', 'Invariant'),
            ('flowguard', 'InvariantResult'),
            ('flowguard', 'ReplayObservation'),
            ('flowguard', 'Scenario'),
            ('flowguard', 'ScenarioExpectation'),
            ('flowguard', 'Workflow'),
            ('flowguard', 'replay_trace'),
            ('flowguard', 'select_covering_traces'),
            ('flowguard.conformance', 'ConformanceReport'),
            ('flowguard.conformance', 'ConformanceViolation'),
            ('flowguard.conformance', 'projected_output_matches'),
            ('flowguard.conformance', 'projected_state_matches'),
            ('flowguard.explorer', 'Explorer'),
            ('flowguard.kit', 'Feature'),
            ('flowguard.kit', 'feature_conformance'),
            ('flowguard.kit', 'feature_explorer'),
            ('flowguard.kit', 'feature_variants'),
            ('flowguard.replay', 'ReplayObservation'),
        )
        code = "\n".join(f"from {module} import {name}" for module, name in imports)
        # A fresh interpreter cannot borrow an attribute cached by another test.
        result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

if __name__ == "__main__":
    unittest.main()


def test_lazy_getattr_resolves_public_names_and_rejects_unknown_ones():
    import flowguard
    from flowguard.explorer import Explorer

    assert flowguard.__getattr__("Explorer") is Explorer
    for name, error in (("not_a_flowguard_name", AttributeError), ("RuntimeGateway", AttributeError)):
        try:
            flowguard.__getattr__(name)
        except error:
            continue
        raise AssertionError(f"{name} should raise {error.__name__}")

def test_stable_surface_is_listed(tmp_path):
    """Changing a list here needs a consumer need named in the plan item."""
    import importlib
    import re
    from flowguard.map.mapfile import TOP_KEYS, COMPONENT_KEYS, read_model_contract
    from flowguard.map.port import Port, _receipts

    assert tuple(flowguard.__all__) == ('CheckReport', 'ConformanceReport', 'ConformanceRule', 'ConformanceViolation', 'DeadBranch', 'ExceptionBranch', 'Explorer', 'FEATURE_INVARIANTS', 'Feature', 'FeatureReport', 'FeatureState', 'FeatureViolation', 'FunctionBlock', 'FunctionResult', 'GraphEdge', 'Invariant', 'InvariantResult', 'InvariantViolation', 'LoopCheckConfig', 'LoopCheckReport', 'OracleCheckResult', 'ReachabilityCondition', 'ReachabilityFailure', 'ReplayAdapter', 'ReplayObservation', 'Scenario', 'ScenarioExpectation', 'ScenarioRun', 'TemplateFile', 'Trace', 'TraceStep', 'Workflow', 'WorkflowPath', 'WorkflowRun', 'adoption_template_files', 'all_items_have_source', 'at_most_once_by', 'cache_matches_source', 'check_loops', 'default_conformance_rules', 'enumerate_input_sequences', 'feature_conformance', 'feature_explorer', 'feature_variants', 'forbid_label_after', 'no_contradictory_values', 'no_duplicate_by', 'no_duplicate_values', 'only_named_block_writes', 'projected_output_matches', 'projected_state_matches', 'reachable_states', 'replay_trace', 'require_label', 'require_label_order', 'require_reachable', 'run_exact_sequence', 'select_covering_traces', 'tarjan_scc', 'to_json_text', 'to_jsonable', 'ui_journey_template_files', 'validator_template_files', 'write_template_files')
    imports = (
        ('flowguard', ('Workflow', 'FunctionResult', 'Invariant', 'InvariantResult',
                       'ReplayObservation', 'replay_trace', 'select_covering_traces',
                       'Scenario', 'ScenarioExpectation')),
        ('flowguard.conformance', ('ConformanceReport', 'ConformanceViolation',
                                  'projected_output_matches', 'projected_state_matches')),
        ('flowguard.explorer', ('Explorer',)),
        ('flowguard.replay', ('ReplayObservation',)),
        ('flowguard.kit', ('Feature', 'feature_conformance', 'feature_explorer',
                          'feature_variants', 'reachable_states')),
    )
    for module, group in imports:
        for name in group:
            assert getattr(importlib.import_module(module), name) is not None
    assert TOP_KEYS == {'schema', 'project', 'layers', 'ignore', 'test_command',
                        'test_commands', 'components', 'flows', 'accepted_debts',
                        'fingerprint_format', 'model_digests', 'import_roots',
                        'large_model_seconds', 'large_test_seconds'}
    assert COMPONENT_KEYS == {'id', 'layer', 'summary', 'responsibilities', 'files',
                              'entrypoints', 'state', 'side_effects', 'depends_on',
                              'tests', 'models', 'status', 'fingerprint', '_hint', 'parent'}
    model = tmp_path / 'surface.py'
    model.write_text("""raise RuntimeError('contract reading must never import this file')
MODEL_ID = 'surface'
PARENT = 'app'
COMPONENTS = ['app']
IMPLEMENTED_BY = {'Run': 'app.py:run'}
USES = {'Read': 'lib.py:read'}
TESTED_BY = {'safe': ['tests/test_app.py:test_run']}
NOT_MODELED = {'app.py:format': 'presentation only'}
OUTPUTS = {'answer': ('ok', 'no')}
HANDOFF = {'producer': {'answer': 'received'}, 'other': {'value': ('mapped', {'yes': True, 'no': None})}}
READS_PARENT = ('request',)
KEEPS = ('request',)
DISPATCH = {'request': {'one': 'first', 'two': 'second'}}
def project_parent_state(state): return state
""")
    contract = read_model_contract(model)
    assert contract['MODEL_ID'] == 'surface'
    assert contract['PARENT'] == 'app'
    assert contract['COMPONENTS'] == ['app']
    assert contract['IMPLEMENTED_BY'] == {'Run': 'app.py:run'}
    assert contract['USES'] == {'Read': 'lib.py:read'}
    assert contract['TESTED_BY'] == {'safe': ['tests/test_app.py:test_run']}
    assert contract['NOT_MODELED'] == {'app.py:format': 'presentation only'}
    assert contract['OUTPUTS'] == {'answer': ('ok', 'no')}
    assert contract['HANDOFF'] == {'producer': {'answer': 'received'},
                                   'other': {'value': ('mapped', {'yes': True, 'no': None})}}
    assert contract['READS_PARENT'] == ('request',)
    assert contract['KEEPS'] == ('request',)
    assert contract['DISPATCH'] == {'request': {'one': 'first', 'two': 'second'}}
    assert contract['functions'] == ['project_parent_state']
    assert contract['port'].dispatch == contract['DISPATCH']
    # Use the actual shared receipt reader, since expansion needs the producer's
    # declared values; static contract reading alone cannot invent that domain.
    assert _receipts(contract['port'], {'producer': Port(outputs={'answer': ('ok', 'no')}),
                                        'other': Port(outputs={'value': ('yes', 'no')})}) == {
        'producer': {'answer': ('received', {'ok': 'ok', 'no': 'no'})},
        'other': {'value': ('mapped', {'yes': True, 'no': None})},
    }
    help_text = subprocess.check_output([sys.executable, '-m', 'flowguard', '--help'],
                                        cwd=ROOT, text=True)
    # Python 3.13 removes the common indentation from compiled docstrings.
    # Match the command column while keeping the exact verb set below.
    assert set(re.findall(r'^[ \t]*([a-z]+)[ \t]{2,}', help_text, re.M)) == {
        'read', 'change', 'release', 'map', 'template', 'target', 'req'}
