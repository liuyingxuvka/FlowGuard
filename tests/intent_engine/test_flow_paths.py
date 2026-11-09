"""Definite source order is narrower than a call graph, and never imports the project."""
from contextlib import closing
from types import SimpleNamespace

import pytest

from flowguard.intent.flow_paths import analyze_paths
from flowguard.structure import build


def observed(graph, targets):
    entries = []
    for name, target in targets.items():
        node = graph.node(target)
        entries.append(SimpleNamespace(name=name, target=target, kind='event', file=node['file'],
                                       module=node['module'], qual=node['qual'], target_line=node['line'],
                                       source_role='production', status='ok'))
    return SimpleNamespace(entries=tuple(entries))


def inspect(tmp_path, source, targets, *, entry='entry', others=()):
    (tmp_path / 'app.py').write_text(source)
    for filename, text in others:
        path = tmp_path / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    with closing(build(tmp_path)) as graph:
        return analyze_paths(graph, observed(graph, targets), (entry,), tuple(targets))


LEAVES = 'def check(): return True\ndef post(*args): return None\n'
TARGETS = {'entry': 'app:entry', 'check': 'app:check', 'post': 'app:post'}


def test_source_sequence_is_not_the_call_graph_fork(tmp_path):
    result = inspect(tmp_path, LEAVES + 'def entry():\n    check()\n    post()\n', TARGETS)
    assert result.paths == (('entry', 'check', 'post'),)
    assert result.complete and not result.unknown


def test_repeated_calls_retain_occurrences(tmp_path):
    result = inspect(tmp_path, LEAVES + 'def entry():\n    check()\n    check()\n    post()\n', TARGETS)
    assert result.paths == (('entry', 'check', 'check', 'post'),)


def test_arguments_are_called_before_the_outer_call(tmp_path):
    result = inspect(tmp_path, LEAVES + 'def entry(): return post(check())\n', TARGETS)
    assert result.paths == (('entry', 'check', 'post'),)


def test_literal_if_and_return_remove_unreachable_calls(tmp_path):
    result = inspect(tmp_path, LEAVES + 'def entry():\n    if True:\n        check()\n        return\n    post()\n', TARGETS)
    assert result.paths == (('entry', 'check'),)
    assert result.complete


def test_literal_false_branch_cannot_invent_a_bypass(tmp_path):
    result = inspect(tmp_path, LEAVES + 'def entry():\n    if False:\n        post()\n        return\n    check()\n    post()\n', TARGETS)
    assert result.paths == (('entry', 'check', 'post'),)
    assert result.complete


def test_local_literal_boolean_condition_is_proved_without_execution(tmp_path):
    result = inspect(tmp_path, LEAVES + 'def entry():\n    ready = True\n    if not ready:\n        return post()\n    check()\n    post()\n', TARGETS)
    assert result.paths == (('entry', 'check', 'post'),)
    assert result.complete


def test_unknown_branch_does_not_make_a_possible_bypass_definite(tmp_path):
    result = inspect(tmp_path, LEAVES + 'def entry(ready):\n    if ready:\n        check()\n    post()\n', TARGETS)
    assert result.paths == ()
    assert not result.complete
    assert any('branch condition is not a proved boolean literal' in reason for reason in result.unknown)


def test_a_known_direct_bypass_has_a_complete_path(tmp_path):
    result = inspect(tmp_path, LEAVES + 'def entry():\n    post()\n', TARGETS)
    assert result.paths == (('entry', 'post'),)
    assert result.complete


def test_non_anchor_helpers_and_import_aliases_are_folded(tmp_path):
    source = 'from moved.worker import execute as moved\ndef entry(): moved()\n'
    helper = 'from actions import check, post\ndef execute():\n    check()\n    post()\n'
    targets = {'entry': 'app:entry', 'check': 'actions:check', 'post': 'actions:post'}
    result = inspect(tmp_path, source, targets, others=(('moved/__init__.py', ''),
                     ('moved/worker.py', helper), ('actions.py', LEAVES)))
    assert result.paths == (('entry', 'check', 'post'),)
    assert result.complete
    assert 'moved/worker.py' in result.files


def test_callback_parameter_cannot_borrow_a_global_with_the_same_name(tmp_path):
    result = inspect(tmp_path, LEAVES + 'def entry(post):\n    check()\n    post()\n', TARGETS)
    assert not result.complete and result.paths == ()
    assert any('dynamic callable parameter post' in reason for reason in result.unknown)


@pytest.mark.parametrize('statement', ['for item in ():\n        check()', 'try:\n        check()\n    finally:\n        post()'])
def test_unsupported_control_flow_is_explicit(tmp_path, statement):
    result = inspect(tmp_path, LEAVES + 'def entry():\n    ' + statement + '\n', TARGETS)
    assert result.paths == () and not result.complete
    assert result.unknown


def test_recursion_is_unknown_instead_of_an_implicit_finite_proof(tmp_path):
    source = LEAVES + 'def helper(): helper()\ndef entry():\n    helper()\n    post()\n'
    result = inspect(tmp_path, source, TARGETS)
    assert not result.complete and result.paths == ()
    assert any('recursive helper' in reason for reason in result.unknown)


def test_external_call_prevents_a_complete_path(tmp_path):
    source = 'from unknown_service import ready\n' + LEAVES + 'def entry():\n    ready()\n    post()\n'
    result = inspect(tmp_path, source, TARGETS)
    assert not result.complete and result.paths == ()
    assert any('call target is not uniquely mapped' in reason for reason in result.unknown)


def test_nested_helper_return_does_not_return_from_the_caller(tmp_path):
    source = LEAVES + 'def helper():\n    check()\n    return\n    post()\ndef entry():\n    helper()\n    post()\n'
    result = inspect(tmp_path, source, TARGETS)
    assert result.complete and result.paths == (('entry', 'check', 'post'),)


def test_source_is_only_read_and_never_imported(tmp_path):
    source = 'raise AssertionError("do not import project for static paths")\n' + LEAVES + 'def entry():\n    check()\n    post()\n'
    result = inspect(tmp_path, source, TARGETS)
    assert result.complete and result.paths == (('entry', 'check', 'post'),)


def test_stale_anchored_callee_cannot_supply_a_definite_path(tmp_path):
    (tmp_path / 'app.py').write_text('from actions import post\ndef entry(): post()\n')
    action = tmp_path / 'actions.py'
    action.write_text('def post(): return None\n')
    with closing(build(tmp_path)) as graph:
        index = observed(graph, {'entry': 'app:entry', 'post': 'actions:post'})
        action.write_text('def post(): raise RuntimeError("changed after map")\n')
        result = analyze_paths(graph, index, ('entry',), ('entry', 'post'))
    assert not result.complete and result.paths == ()
    assert any('source map is stale' in reason for reason in result.unknown)


def test_invalid_non_entry_anchor_cannot_supply_a_definite_path(tmp_path):
    (tmp_path / 'app.py').write_text(LEAVES + 'def entry(): post()\n')
    with closing(build(tmp_path)) as graph:
        index = observed(graph, TARGETS)
        index.entries[-1].status = 'red'
        result = analyze_paths(graph, index, ('entry',), tuple(TARGETS))
    assert not result.complete and result.paths == ()
    assert any('anchor source is unverified' in reason for reason in result.unknown)


def test_parameter_receiver_cannot_be_statically_dispatched(tmp_path):
    source = 'class Worker:\n    def post(self): return None\ndef entry(worker: Worker): worker.post()\n'
    targets = {'entry': 'app:entry', 'post': 'app:Worker.post'}
    result = inspect(tmp_path, source, targets)
    assert not result.complete and result.paths == ()
    assert any('dynamic receiver parameter worker' in reason for reason in result.unknown)


def test_unpacking_mapping_does_not_hide_an_implicit_dispatch(tmp_path):
    source = LEAVES + 'def entry(mapping):\n    value = {**mapping}\n    post()\n'
    result = inspect(tmp_path, source, TARGETS)
    assert not result.complete and result.paths == ()
    assert any('mapping expansion may dispatch' in reason for reason in result.unknown)


def root_inspect(tmp_path, source, *, wrapper=False, others=()):
    from flowguard.intent.flow_paths import analyze_root_paths
    (tmp_path / 'app.py').write_text(source)
    for filename, text in others:
        path = tmp_path / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    targets = {'start': 'app:start', 'owner': 'app:owner', 'publish': 'app:publish',
               'new_wrapper' if wrapper else 'new_entry': 'app:new_entry'}
    with closing(build(tmp_path)) as graph:
        return analyze_root_paths(graph, observed(graph, targets), ('start', 'owner', 'publish'))


ROOT_CODE = ('def owner(): return True\ndef publish(): return None\n'
             'def start():\n    owner()\n    publish()\n')


def test_new_main_root_can_expose_a_different_production_entry(tmp_path):
    source = ROOT_CODE + 'def new_entry(): publish()\nif __name__ == "__main__":\n    new_entry()\n'
    result = root_inspect(tmp_path, source)
    assert result.paths == (('new_entry', 'publish'),)
    assert result.complete


def test_new_root_wrapper_through_the_original_start_is_legal(tmp_path):
    source = ROOT_CODE + 'def new_entry(): start()\nif __name__ == "__main__":\n    new_entry()\n'
    result = root_inspect(tmp_path, source, wrapper=True)
    assert result.paths == (('new_wrapper', 'start', 'owner', 'publish'),)
    assert result.complete


def test_no_caller_library_function_is_not_assumed_to_be_an_entry(tmp_path):
    result = root_inspect(tmp_path, ROOT_CODE + 'def new_entry(): publish()\n')
    assert result.paths == () and not result.complete
    assert any('external entry status is not proved' in reason for reason in result.unknown)


def test_plain_module_source_call_also_supplies_a_root(tmp_path):
    result = root_inspect(tmp_path, ROOT_CODE + 'def new_entry(): publish()\nnew_entry()\n')
    assert result.paths == (('new_entry', 'publish'),)
    assert result.complete


def test_unknown_module_root_branch_is_grey_not_a_definite_bypass(tmp_path):
    result = root_inspect(tmp_path, ROOT_CODE + 'def new_entry(): publish()\nif configured:\n    new_entry()\n')
    assert result.paths == () and not result.complete
    assert any('branch condition is not a proved boolean literal' in reason for reason in result.unknown)


def test_module_reassignment_does_not_call_the_old_function_declaration(tmp_path):
    result = root_inspect(tmp_path, ROOT_CODE + 'def new_entry(): publish()\nnew_entry = None\nnew_entry()\n')
    assert result.paths == () and not result.complete
    assert any('reassigned' in reason for reason in result.unknown)


def test_call_before_a_module_definition_is_not_a_proved_entry(tmp_path):
    result = root_inspect(tmp_path, ROOT_CODE + 'new_entry()\ndef new_entry(): publish()\n')
    assert result.paths == () and not result.complete
    assert any('defined after this root call' in reason for reason in result.unknown)


def test_imported_module_alias_can_reach_a_new_production_entry(tmp_path):
    source = ROOT_CODE + 'def new_entry(): publish()\n'
    result = root_inspect(tmp_path, source, others=(('cli.py',
                          'from app import new_entry as run\nif __name__ == "__main__":\n    run()\n'),))
    assert result.complete and result.paths == (('new_entry', 'publish'),)


def test_test_module_invocation_is_not_a_production_root(tmp_path):
    source = ROOT_CODE + 'def new_entry(): publish()\n'
    result = root_inspect(tmp_path, source, others=(('tests/test_sample.py',
                          'from app import new_entry\nnew_entry()\n'),))
    assert result.paths == () and not result.complete
    assert any('external entry status is not proved' in reason for reason in result.unknown)


def test_definition_time_call_is_not_silently_skipped(tmp_path):
    result = root_inspect(tmp_path, ROOT_CODE + 'def new_entry(value=publish()): return None\n')
    assert result.paths == () and not result.complete
    assert any('definition initialization' in reason for reason in result.unknown)


def test_class_initialization_call_is_not_silently_skipped(tmp_path):
    source = ROOT_CODE + 'def new_entry(): return None\nclass Registry:\n    saved = publish()\n'
    result = root_inspect(tmp_path, source)
    assert result.paths == () and not result.complete
    assert any('definition initialization' in reason for reason in result.unknown)
