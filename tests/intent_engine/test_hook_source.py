"""The call hook's source text is inspect.getsource's, whatever changed since the last test asked."""
import importlib.util
import inspect
import linecache
import os
import uuid

import pytest

from flowguard.intent import sites


def load(path):
    spec = importlib.util.spec_from_file_location('hook_source_' + uuid.uuid4().hex, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rewrite(path, text):
    before = os.stat(path).st_mtime_ns
    path.write_text(text)
    os.utime(path, ns=(before + 10**9, before + 10**9))      # a new status even within one clock tick


def test_reused_block_follows_the_file_and_the_cached_lines(tmp_path):
    path = tmp_path / 'policy.py'
    path.write_text('def grace(days):\n    return days > 3\nLIMIT = 1\n')
    grace = load(path).grace
    assert sites._source(grace) == inspect.getsource(grace) == 'def grace(days):\n    return days > 3\n'
    # The body changes on disk: checkcache drops the old lines.
    rewrite(path, 'def grace(days):\n    return days >= 30\nLIMIT = 1\n')
    assert sites._source(grace) == inspect.getsource(grace) == 'def grace(days):\n    return days >= 30\n'
    # The line after the block, which the tokenizer read to end it, becomes part of the block.
    rewrite(path, 'def grace(days):\n    return days >= 30\n    LIMIT = 1\n')
    assert sites._source(grace) == inspect.getsource(grace) == 'def grace(days):\n    return days >= 30\n    LIMIT = 1\n'
    # The function now ends the file; text appended later still belongs to it.
    rewrite(path, 'def grace(days):\n    return days >= 30\n')
    assert sites._source(grace) == inspect.getsource(grace) == 'def grace(days):\n    return days >= 30\n'
    rewrite(path, 'def grace(days):\n    return days >= 30\n    # still the body\n    pass\n')
    assert sites._source(grace) == inspect.getsource(grace)
    assert sites._source(grace).endswith('    pass\n')
    # The cached lines themselves are edited, without any file change.
    lines = linecache.getlines(str(path))
    lines[1] = '    return days < 0\n'
    assert sites._source(grace) == inspect.getsource(grace)
    assert 'days < 0' in sites._source(grace)


def test_reused_block_keeps_the_shim_of_the_current_source(tmp_path):
    path = tmp_path / 'policy.py'
    path.write_text('class Grace:\n    def days(self, value):\n        return value > 3\n')
    owner = load(path).Grace
    with sites.intercepted(owner.days, lambda original, bound: original(*bound.args, **bound.kwargs)):
        assert owner().days(4) is True
    # A private name in the body refuses the shim; the earlier block must not hide it.
    rewrite(path, 'class Grace:\n    def days(self, value):\n        return self.__limit(value)\n')
    with pytest.raises(sites.NotMutable, match='^private names in a method$'):
        with sites.intercepted(owner.days, lambda original, bound: original(*bound.args, **bound.kwargs)):
            pass
