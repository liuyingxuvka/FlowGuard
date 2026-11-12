"""The session's comparison of one recorded call, for runtime-level tests.

`Runtime.hook` only records a real call (its JSON arguments and result). After the tests,
`plugin.Observations._compare` runs each recorded sample once in the sealed environment on the
baseline source and once on the current source (with the project constants each imports); these helpers
make the same two calls, so a
runtime test can state what that comparison sees without a pytest session.
"""
import json

from flowguard.intent import runtime as R


def sealed_pair(runtime, reading, file, qual):
    """(baseline outcome, current outcome) of one recorded call, each a `runtime.sealed` result."""
    assert reading.sample is not None, reading.reasons
    sample, module = reading.sample, reading.target.partition(':')[0]
    old = None if runtime._baseline_error else runtime._source(file)
    before = (R.sealed(old, qual, sample['args'], sample['kwargs'], runtime.imports(file, module, True)) if old is not None
              else dict(status='unavailable', reason='no baseline source'))
    after = R.sealed((runtime.root / file).read_text(encoding='utf-8-sig'), qual, sample['args'], sample['kwargs'],
                     runtime.imports(file, module))
    return before, after


def comparable(before, after):
    """The session's rule: an unavailable side, or the same exception on both, is not compared."""
    return (before['status'] != 'unavailable' and after['status'] != 'unavailable'
            and not (before['status'] == after['status'] == 'raised' and before['error'] == after['error']))


def differs(before, after):
    return comparable(before, after) and json.dumps(before, sort_keys=True) != json.dumps(after, sort_keys=True)


def value(outcome):
    return outcome['value'] if outcome['status'] == 'ok' else outcome
