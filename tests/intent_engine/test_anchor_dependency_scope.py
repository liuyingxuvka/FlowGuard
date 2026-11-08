"""Coarse file selection cannot reuse green after a new same-name binding."""
from contextlib import closing

from tests.intent_engine import _cli_fixture as cli_fixture

from flowguard.intent import cache, cli, deps
from flowguard.structure import build
from test_cli import project


def test_unrelated_file_is_reused_but_new_same_name_site_cannot_borrow_green(tmp_path, monkeypatch):
    root, cfg = project(tmp_path)
    cli.init(cfg)
    copy = root / 'another.py'
    copy.write_text('def accept(days: int) -> bool:\n    return days <= 4\n')
    assert cli_fixture.check(cfg, everything=True) == 0
    before = cache.read(cfg)
    saved = before['deps']['LIMIT']
    with closing(build(root)) as graph:
        target = root.name + ':accept'
        node = graph.node(target)
        assert node and node['fp']
        assert saved['dependencies']['node:' + target] == node['fp']
        assert deps.function_fingerprints(graph, [target])[node['file']][node['qual']] == node['fp']
        old_copy_fp = graph.node('another:accept')['fp']
        assert old_copy_fp and old_copy_fp != node['fp']
        assert not deps.stale(saved, deps.Now(cfg, graph))
    observed = cli_fixture.calls(monkeypatch)
    assert cli_fixture.check(cfg) == 0 and observed == []
    assert cache.read(cfg)['attempt'] == before['attempt']

    # The file listing is intentionally coarse: new files trigger one real check.
    (root / 'unrelated.py').write_text('UNRELATED = 123\n')
    with closing(build(root)) as graph:
        assert 'listing:' in deps.stale(saved, deps.Now(cfg, graph))
    assert cli_fixture.check(cfg) == 0 and len(observed) == 1
    fresh = cache.read(cfg)
    assert fresh['attempt']['stamp'] > before['attempt']['stamp']
    with closing(build(root)) as graph:
        assert not deps.stale(fresh['deps']['LIMIT'], deps.Now(cfg, graph))

    # This file already existed in the refreshed baseline. Only its binding is
    # new; discovery must collect its actual code, not borrow the older home.
    observed.clear()
    copy.write_text('# flowguard: sensor LIMIT(days: days) -> answer: bool\n' + copy.read_text())
    with closing(build(root)) as graph:
        assert graph.node('another:accept')['fp'] == old_copy_fp
    assert cli_fixture.check(cfg) == 1
    assert len(observed) == 1
    actual = cache.read(cfg)
    assert actual['attempt']['stamp'] > fresh['attempt']['stamp']
    other = [result for result in actual['results']['LIMIT']['items'].values()
             if result.get('target') == 'another:accept']
    assert other and any(result['verdict'] == 'red' and result['n'] > 0 for result in other)
    assert any('days=4' in reason and 'code True' in reason
               for result in other for reason in result.get('red', ()))
