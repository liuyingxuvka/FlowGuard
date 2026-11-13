"""A calibration selector names one collected test of its own session, by resolved file and full id."""
from types import SimpleNamespace

import pytest

from flowguard.intent import calibration


def collected(request, root, file, names, *, path=None):
    """Real pytest Function items under one real Module node; nothing is imported or run."""
    module = pytest.Module.from_parent(request.node, path=path or root / file, nodeid=file)
    return [pytest.Function.from_parent(module, name=name, callobj=lambda: None) for name in names]


def test_each_session_reads_its_own_items_through_its_file_lookup(request, tmp_path):
    root = tmp_path.resolve()
    (root / 'tests' / 'sub').mkdir(parents=True)
    for name in ('test_alpha.py', 'test_beta.py'):
        (root / 'tests' / name).write_text('')
    runtime = SimpleNamespace(root=root)
    alpha = collected(request, root, 'tests/test_alpha.py', ['test_one[a]', 'test_one[b]', 'test_two'])
    beta = collected(request, root, 'tests/test_beta.py', ['test_one[a]'])
    # The same file reached through another spelling resolves to it and keeps its own node id prefix.
    spelled = collected(request, root, 'tests/sub/../test_beta.py', ['test_three'],
                        path=root / 'tests' / 'sub' / '..' / 'test_beta.py')
    with calibration.session(runtime, alpha + beta + spelled):
        for item in alpha + beta:
            assert calibration._context(root, item.nodeid) == (calibration._CURRENT.get(), item)
        assert calibration._context(root, 'tests/test_beta.py::test_three')[1] is spelled[0]
        for selector in ('tests/test_alpha.py::test_one', 'tests/test_gamma.py::test_one[a]',
                         'tests/test_beta.py::test_two'):
            with pytest.raises(ValueError) as error:
                calibration._context(root, selector)
            assert str(error.value) == 'calibration must name exactly one collected test, including its parameter id'
        with calibration.session(runtime, beta):
            # A later session answers from its own items, not from the lookup the outer session built.
            with pytest.raises(ValueError, match='^calibration must name exactly one collected test'):
                calibration._context(root, alpha[0].nodeid)
            assert calibration._context(root, beta[0].nodeid)[1] is beta[0]
        with calibration.session(runtime, alpha[:1] + beta + alpha[1:]):
            for item in alpha + beta:           # one file's items need not be adjacent
                assert calibration._context(root, item.nodeid)[1] is item
        with calibration.session(runtime, alpha + alpha):
            with pytest.raises(ValueError, match='^calibration must name exactly one collected test'):
                calibration._context(root, alpha[0].nodeid)
        assert calibration._context(root, alpha[2].nodeid)[1] is alpha[2]
        with pytest.raises(ValueError) as error:
            calibration._context(root / 'tests', 'test_alpha.py::test_two')
        assert str(error.value) == 'calibrated observation needs the existing collected pytest session'
        for selector in ('tests/test_alpha.py', '../outside.py::test_two'):
            with pytest.raises(ValueError) as error:
                calibration._context(root, selector)
            assert str(error.value) == 'calibration test does not belong to the indexed project source'
