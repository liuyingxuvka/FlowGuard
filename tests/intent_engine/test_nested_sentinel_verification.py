"""A real nested Sentinel keeps one protected temporary source slot."""
import importlib
from pathlib import Path
import threading
import uuid

import pytest

from flowguard.intent import plugin
from flowguard.intent.config import load_config, setup_path
from flowguard.intent.flow import Capture, runtime_check
from flowguard.intent.imports import _finder, prepare
from flowguard.intent.loader import load


def root(path, value=None, name=None):
    (path/'tests/intent').mkdir(parents=True)
    (path/'pyproject.toml').write_text('[tool.pytest.ini_options]\npythonpath=["."]\n')
    if name is not None:
        (path/(name+'.py')).write_text('VALUE = '+str(value)+'\n')
    return path


def config(path):
    return pytest.Config.fromdictargs({}, ['-p', 'flowguard.intent.plugin',
        '-c', str(path/'pyproject.toml'), str(path)])


@pytest.mark.parametrize('loaded,complete', [(True,True),(True,False),(False,True),(False,False)])
def test_native_sentinel_reaches_the_actual_check_under_an_outer_verifier(loaded, complete):
    from tests.test_sentinel_anchor_case import test_sentinel_anchor_case as native
    outer = plugin._CURRENT
    host = _finder.host
    assert outer is not None and host == outer.cfg.root
    model = outer.get_model()
    with Capture(outer.cfg.root, model.anchor_index, 'native', models=model.flows.values(), _ordinary=True) as observed:
        native(loaded, complete)
    assert plugin._CURRENT is outer and _finder.host == host and not _finder.active
    events = [event for event in observed.events if event.anchor in ('SENTINEL_CASE','SENTINEL_CHECK')]
    expected = 'return' if loaded and complete else 'raise'
    assert [(event.anchor,event.phase)for event in events] == [
        ('SENTINEL_CASE','call'),('SENTINEL_CHECK','call'),('SENTINEL_CHECK',expected),('SENTINEL_CASE','return')]
    if expected == 'raise':
        assert type(events[2].error) is AssertionError
    else:
        assert events[2].states['Session.sentinel'] == 'ok'
    result = runtime_check(model.flows['SENTINEL_OBSERVATION'], observed, model.anchor_index, rules=model.rules)
    assert not result['red'], result
    assert observed.issues == []


def test_active_target_survives_same_root_reentry_and_blocks_all_source_switches(tmp_path):
    outer = plugin._CURRENT
    name = 'active_target_'+uuid.uuid4().hex
    b, c = root(tmp_path/'B',3,name), root(tmp_path/'C',4,name)
    child = config(b)
    try:
        state = plugin._CURRENT
        assert state is not outer and state.owns_root and _finder.active and _finder.root == b
        state.get_model()
        setup_path(load_config(b))
        saved = importlib.import_module(name)
        assert saved.VALUE == 3
        reentered = config(b)
        try:
            assert plugin._CURRENT is not state and not plugin._CURRENT.owns_root
            for target in (outer.cfg.root,c):
                with pytest.raises(ValueError, match='nested pytest verification is active'):
                    load(root=target)
                assert _finder.root == b and importlib.import_module(name) is saved
        finally:
            reentered._ensure_unconfigure()
        assert plugin._CURRENT is state and _finder.active
        with pytest.raises(ValueError, match='nested pytest verification is active'):
            prepare(c)
        original = (b/(name+'.py')).read_bytes()
        (b/(name+'.py')).write_text('VALUE = 5\n')
        try:
            with pytest.raises(ValueError, match='source changed during pytest verification'):
                load(root=b)
            assert importlib.import_module(name) is saved and saved.VALUE == 3
        finally:
            (b/(name+'.py')).write_bytes(original)
    finally:
        child._ensure_unconfigure()
    assert plugin._CURRENT is outer and not _finder.active
    load(root=c)
    changed = importlib.import_module(name)
    assert changed is not saved and changed.VALUE == 4


def test_failed_target_preparation_never_claims_the_source_slot(tmp_path):
    outer = plugin._CURRENT
    b = root(tmp_path/'B')
    real = plugin.Session
    class BrokenSession(real):
        def __init__(self, config):
            super().__init__(config)
            raise RuntimeError('session initialization failed')
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(plugin, 'Session', BrokenSession)
    try:
        with pytest.raises(RuntimeError, match='session initialization failed'):
            config(b)
    finally:
        monkeypatch.undo()
    assert plugin._CURRENT is outer and not _finder.active


def test_a_different_thread_cannot_borrow_the_active_parent_session(tmp_path):
    outer = plugin._CURRENT
    b = root(tmp_path/'threaded')
    errors = []
    def worker():
        try:
            nested = config(b)
        except pytest.UsageError as error:
            errors.append(str(error))
        else:
            nested._ensure_unconfigure()
    thread = threading.Thread(target=worker)
    thread.start();thread.join(10)
    assert not thread.is_alive()
    assert errors and 'another pytest verification is active' in errors[0], errors
    assert plugin._CURRENT is outer and not _finder.active
