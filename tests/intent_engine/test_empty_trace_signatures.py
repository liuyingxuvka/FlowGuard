"""No recording means no new trace evidence or static dependency scan."""
import types

from flowguard.intent import deps


def test_empty_trace_recording_is_still_a_generator_and_never_scans_dependencies(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('an empty recording must not scan test dependencies')
    monkeypatch.setattr(deps, 'test_dependencies', forbidden)
    values = deps.trace_signatures(object(), object(), {})
    assert isinstance(values, types.GeneratorType)
    assert list(values) == []
