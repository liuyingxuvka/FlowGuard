"""Filesystem directory aliases retain the configured intent collection."""
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

from flowguard.intent.config import load_config
from flowguard.intent.plugin import _intent_path


def test_real_and_directory_alias_collect_the_same_intent_and_preserve_leaf_roles(tmp_path):
    real = tmp_path / 'real'
    (real / 'tests/intent').mkdir(parents=True)
    alias = tmp_path / 'alias'
    alias.symlink_to(real, target_is_directory=True)
    (real / 'pyproject.toml').write_text(
        '[tool.pytest.ini_options]\npythonpath=["."]\n'
        '[tool.flowguard]\nauthority_docs=["SPEC.txt"]\n')
    (real / 'SPEC.txt').write_text('The phase is ready.\n')
    (real / 'sample.py').write_text('class Phase:\n    status="ready"\n')
    phase = real / 'tests/intent/phase.py'
    phase.write_text(
        'from flowguard.intent import states\n'
        'states("sample:Phase.status",["ready"],'
        'source=\'doc SPEC.txt "The phase is ready."\')\n')
    (real / 'tests/test_sentinel.py').write_text(
        'def test_flowguard_intent(request):\n'
        '    from flowguard.intent.plugin import sentinel\n'
        '    sentinel(request.config)\n')
    sdk = Path(__file__).resolve().parents[2]
    launch = ('import sys;sys.path.insert(0,sys.argv.pop(1));import pytest;'
              'raise SystemExit(pytest.main(sys.argv[1:]))')
    for entry in (real, alias):
        command = [sys.executable, '-c', launch, str(sdk), '-q', '--tb=short',
                   '-p', 'no:cacheprovider', '-p', 'flowguard.intent.plugin',
                   '-c', str(entry / 'pyproject.toml'), str(entry / 'tests')]
        result = subprocess.run(command, cwd=sdk, capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        assert '2 passed' in result.stdout, result.stdout
    config = SimpleNamespace(_flowguard_intent=SimpleNamespace(cfg=load_config(real)))
    assert _intent_path(phase, config)
    assert _intent_path(alias / 'tests/intent/phase.py', config)
    outside = real / 'tests/outside.py'
    outside.write_text('VALUE = 1\n')
    assert not _intent_path(outside, config)
    outside_link = real / 'tests/outside_link.py'
    outside_link.symlink_to(phase)
    assert not _intent_path(outside_link, config)
    inside_link = real / 'tests/intent/inside_link.py'
    inside_link.symlink_to(outside)
    assert _intent_path(inside_link, config)
