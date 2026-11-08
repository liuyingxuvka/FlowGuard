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
