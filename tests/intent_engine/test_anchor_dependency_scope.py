"""Binding discovery changes only when a referenced anchor identity changes."""
from contextlib import closing

from tests.intent_engine import _cli_fixture as cli_fixture

from flowguard.intent import cache, cli, deps
from flowguard.structure import build
from test_cli import project


def test_unrelated_file_is_reused_but_new_same_name_site_cannot_borrow_green(tmp_path):
    root, cfg = project(tmp_path)
    cli.init(cfg)
    copy = root / 'another.py'
    copy.write_text('def accept(days: int) -> bool:\n    return days <= 4\n')
    assert cli_fixture.check(cfg, everything=True) == 0
    saved = cache.read(cfg)['deps']['LIMIT']
    with closing(build(root)) as graph:
        now = deps.Now(cfg, graph)
        target = root.name + ':accept'
        assert now('anchor:' + target) == now('anchor:LIMIT')
        assert now('anchor:' + target) != now('anchor:missing')
        assert not deps.stale(saved, now)
    (root / 'unrelated.py').write_text('UNRELATED = 123\n')
    with closing(build(root)) as graph:
        assert not deps.stale(saved, deps.Now(cfg, graph))
    copy.write_text('# flowguard: sensor LIMIT(days: days) -> answer: bool\n' + copy.read_text())
    with closing(build(root)) as graph:
        assert deps.stale(saved, deps.Now(cfg, graph))
    assert cli_fixture.check(cfg) == 1
