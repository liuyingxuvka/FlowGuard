"""Private source collection must preserve the real suite's collection receipt."""
from tests.intent_engine._source_fixture import source_sessions
from tests.intent_engine.test_composition import project


def test_real_source_subtree_does_not_replace_the_outer_intent_collection(tmp_path, request):
    state = request.config._flowguard_intent
    collected = state.collected
    values = collected.copy()
    selected = state.selected.copy()
    complete = state.complete_collection
    model, engine, _ = project(tmp_path)
    assert engine.m is model
    assert state.collected is collected
    assert state.collected == values
    assert state.selected == selected
    assert state.complete_collection is complete


def test_empty_source_subtree_does_not_change_the_real_collection(tmp_path, request):
    from flowguard.intent import calibration
    from flowguard.intent.config import load_config
    from flowguard.intent.loader import load
    from tests.intent_engine._source_fixture import source_engine
    state = request.config._flowguard_intent
    collected, complete = state.collected, state.complete_collection
    selected = state.selected.copy()
    model = load(load_config(tmp_path))
    assert not model.errors and not model.rules
    assert source_engine(model).m is model
    assert not calibration.probe_context(request.config)
    assert state.collected is collected
    assert state.selected == selected
    assert state.complete_collection is complete


def test_real_private_deselection_stays_unavailable_without_deselecting_host(tmp_path, request, monkeypatch):
    from flowguard.intent.config import load_config
    from flowguard.intent.loader import load
    from tests.intent_engine._source_fixture import scenario, source_engine
    (tmp_path / 'tests/intent').mkdir(parents=True)
    (tmp_path / 'pyproject.toml').write_text('[tool.flowguard]\n')
    code, intent = scenario(tmp_path, 'policy', 'def limit(x): return x <= 3\n',
        "from flowguard.intent import rule\n@rule('LIMIT', decides='limit', fields={'x': int}, source='assumed: bounded value')\ndef LIMIT(x): return x <= 3\n",
        rule='LIMIT', target='limit', parameters={'x': 'int'}, source_parameters={'x': 'int'},
        body='answer=app.limit(x)\nassert type(answer) is bool')
    (tmp_path / 'policy.py').write_text(code)
    (tmp_path / 'tests/intent/policy.py').write_text(intent)
    class PruneNative:
        def pytest_collection_modifyitems(self, config, items):
            if items and all(item.path.is_relative_to(tmp_path) for item in items):
                config.hook.pytest_deselected(items=list(items))
                items.clear()
    state = request.config._flowguard_intent
    monkeypatch.setattr(state, 'ordinary_deselected', False)
    model = load(load_config(tmp_path))
    assert not model.errors
    plugin = PruneNative()
    request.config.pluginmanager.register(plugin)
    try:
        engine = source_engine(model)
    finally:
        request.config.pluginmanager.unregister(plugin)
    assert state.ordinary_deselected is False
    rule = model.rules['LIMIT']
    assert rule.homes
    result = engine.run_home(rule, rule.homes[0], 'cells')
    assert result['verdict'] == 'grey', result
    assert state.ordinary_deselected is False
