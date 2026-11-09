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


def test_engine_digest_is_the_same_in_a_child_of_a_c_locale_process(tmp_path):
    # Under a C/POSIX locale Python runs in UTF-8 mode and gives its child C.UTF-8 (PEP 538/540); the child
    # then runs without UTF-8 mode. Both decode alike, so a check's child must not see a changed engine.
    import os, subprocess, sys
    from pathlib import Path
    probe = ('import sys, subprocess, os\n'
             'from pathlib import Path\n'
             'from flowguard.intent.deps import Now\n'
             'class Cfg: root = Path(sys.argv[1])\n'
             'print(sys.flags.utf8_mode, Now(Cfg, None)("engine:"))\n'
             'if len(sys.argv) > 2:\n'
             '    sys.stdout.flush()\n'
             '    subprocess.run([sys.executable, "-c", sys.argv[2], sys.argv[1]], check=True)\n')
    env = {key: value for key, value in os.environ.items()
           if key not in {'LC_ALL', 'LANG', 'LANGUAGE', 'LC_CTYPE', 'PYTHONUTF8', 'PYTHONCOERCECLOCALE'}}
    env['LC_CTYPE'] = 'C'
    env['PYTHONPATH'] = os.pathsep.join([str(Path(__file__).resolve().parents[2]), env.get('PYTHONPATH', '')])
    result = subprocess.run([sys.executable, '-c', probe, str(tmp_path), probe], env=env,
                            capture_output=True, text=True, check=True)
    lines = result.stdout.split()
    assert len(lines) == 4, result
    assert lines[1] == lines[3], result.stdout
