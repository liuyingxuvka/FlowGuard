"""The historical view `show NAME` prints consumes the same source identities as tests."""
from dataclasses import asdict
import importlib.util
import sys
import uuid

from flowguard.intent import anchors, config, debug
from flowguard.intent.flow import Capture, Flow, Node


def observed(root, source, call):
    """The project, its source anchors and the events of one ordinary call of the module (`call(module)`), recorded by
    the capture a test run uses."""
    name = 'debug_app_' + uuid.uuid4().hex
    path = root / (name + '.py')
    path.write_text(source)
    (root / 'pyproject.toml').write_text('[tool.pytest.ini_options]\npythonpath=["."]\n')
    index = anchors.collect_sources(root, [(path.name, name)])
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    with Capture(root, index, 'tests/test_app.py::test_case', _ordinary=True) as captured:
        call(module)
    return config.load_config(root), index, name, captured.events


def test_show_history_marks_changed_source_stale(tmp_path):
    cfg, index, name, events = observed(tmp_path, '# flowguard: event DONE\ndef done():\n    return 7\n',
                                        lambda module: module.done())
    shown = debug.show_observation(cfg, 'DONE', index, [asdict(e) for e in events])
    assert shown['status'] == 'ok' and 'historical' in shown['lines'][0]
    path = tmp_path / (name + '.py')
    path.write_text(path.read_text().replace('return 7', 'return 8'))
    current = anchors.collect_sources(tmp_path, [(path.name, name)])
    stale = debug.show_observation(cfg, 'DONE', current, events)
    assert stale['status'] == 'grey' and stale['stale'] == 2
    assert not stale['events'] and any('stale' in line for line in stale['lines'])


def test_show_model_reuses_path_checks_and_counts_unobserved_edges(tmp_path):
    def run(module):
        module.a()
        module.c()
    cfg, index, _, events = observed(
        tmp_path, '# flowguard: event A\ndef a(): pass\n# flowguard: event B\ndef b(): pass\n# flowguard: event C\ndef c(): pass\n', run)
    model = Flow('STEPS', 'assumed: save before release',
                 (Node('a', 'A', start=True), Node('b', 'B'), Node('c', 'C', end=True)),
                 (('a', 'b'), ('b', 'c')))
    shown = debug.show_observation(cfg, 'STEPS', index, events, model=model)
    assert shown['status'] == 'red' and shown['node_counts'] == {'a': 1, 'c': 1}
    assert shown['edge_counts'] == {('a', 'c'): 1}
    assert any('runtime path a -> c is not allowed' in line for line in shown['lines'])
    assert any('a -> b: 0; unobserved' in line for line in shown['lines'])
