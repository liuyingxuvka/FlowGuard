"""Drive the real pytest collection sentinel; Flow reads its source events."""
from pathlib import Path
import tempfile

import pytest


# flowguard: event SENTINEL_CASE(loaded: bool, complete: bool) calibrated_by=tests/test_sentinel_anchor_case.py::test_sentinel_anchor_case[True-True]
@pytest.mark.parametrize('loaded,complete', [(True, True), (False, True), (True, False), (False, False)])
def test_sentinel_anchor_case(loaded: bool, complete: bool):
    with tempfile.TemporaryDirectory(prefix='flowguard-native-sentinel-') as folder:
        root = Path(folder)
        (root / 'tests/intent').mkdir(parents=True)
        (root / 'pyproject.toml').write_text(
            '[tool.pytest.ini_options]\npythonpath=["."]\n'
            '[tool.flowguard]\nauthority_docs=["SPEC.txt"]\n')
        (root / 'SPEC.txt').write_text('The phase is ready.\n')
        (root / 'sample.py').write_text('class Phase:\n    status="ready"\n')
        (root / 'tests/intent/phase.py').write_text(
            'from flowguard.intent import states\n'
            'states("sample:Phase.status",["ready"],source=\'doc SPEC.txt "The phase is ready."\')\n')
        sentinel_test = root / 'tests' / ('test_' + root.name.replace('-', '_') + '.py')
        sentinel_test.write_text(
            'def test_flowguard_intent(request):\n'
            '    from flowguard.intent.plugin import sentinel\n'
            '    sentinel(request.config)\n')
        selected = root / 'tests' if complete else sentinel_test
        plugin = 'flowguard.intent.plugin' if loaded else 'no:flowguard.intent.plugin'
        pytest.main(['-q', '--tb=short', '-p', 'no:cacheprovider', '-p', plugin,
                     '-c', str(root / 'pyproject.toml'), str(selected)])
