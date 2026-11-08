"""Launch the ordinary CLI outside the SDK's active pytest session.

Only this test launcher starts a child. The product still has one top-level
pytest path; its actual arguments are observed without replacing its result.
"""
from pathlib import Path
import json
import re
import subprocess
import sys
import uuid


SOURCE = str(Path(__file__).resolve().parents[2])
_OBSERVED = None


def display_text(result):
    """Decode the supported escaped display only at a human-text assertion."""
    text = result if isinstance(result, str) else result.stdout + result.stderr
    return re.sub(r'\\u([0-9a-fA-F]{4})', lambda match: chr(int(match.group(1), 16)), text)


_BOOT = r'''
import json, sys
source, marker, before, *arguments = sys.argv[1:]
sys.path.insert(0, source)
sys.argv = ['flowguard', *arguments]
from flowguard.intent import cli
_original = cli._run_check_pytest
def _observed(command, *args, **kwargs):
    sys.__stderr__.write(marker + json.dumps(list(command), ensure_ascii=False) + '\n')
    sys.__stderr__.flush()
    return _original(command, *args, **kwargs)
cli._run_check_pytest = _observed
if before:
    exec(before, globals())
raise SystemExit(cli.main())
'''


def calls(monkeypatch):
    """Return only pytest invocations actually reached after this call."""
    observed = []
    monkeypatch.setattr(sys.modules[__name__], '_OBSERVED', observed)
    return observed


def main(argv, *, cwd=None, before_main='', timeout=120):
    marker = 'FLOWGUARD_TEST_PYTEST_' + uuid.uuid4().hex + ':'
    result = subprocess.run([sys.executable, '-c', _BOOT, SOURCE, marker, before_main, *map(str, argv)],
                            cwd=cwd, capture_output=True, text=True, timeout=timeout)
    segments = result.stderr.split(marker)
    stderr = segments[0]
    decoder = json.JSONDecoder()
    for segment in segments[1:]:
        command, offset = decoder.raw_decode(segment)
        assert isinstance(command, list) and all(isinstance(part, str) for part in command), 'invalid actual pytest arguments'
        assert segment[offset:offset + 1] == '\n', 'incomplete pytest observation'
        if _OBSERVED is not None:
            _OBSERVED.append(command)
        stderr += segment[offset + 1:]
    sys.stdout.write(result.stdout)
    sys.stderr.write(stderr)
    return result.returncode


def check(cfg, *, everything=False, since=None, deep=False, base=None, before_main='', timeout=120):
    arguments = ['--root', str(cfg.root), 'check']
    if everything:
        arguments.append('--all')
    if deep:
        arguments.append('--deep')
    if since is not None:
        arguments += ['--since', str(since)]
    if base is not None:
        arguments += ['--base', str(base)]
    return main(arguments, cwd=cfg.root, before_main=before_main, timeout=timeout)
