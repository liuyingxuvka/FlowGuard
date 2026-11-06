"""Calibrated point shapes do not create finite domains or pure capabilities."""
from pathlib import Path

import pytest

from flowguard.intent import anchors as A
from test_anchors import GOOD, source, session


@pytest.mark.parametrize('annotation,value', [
    ('str', 'gone'),
    ('list[dict]', [{'id': 'x', 'score': 1, 'matches': {'name': ['x']}}]),
    ('Path', Path('fixtures/world.yaml')),
    ('pathlib.Path', Path('fixtures/world.yaml')),
    ('dict[str, Any]', {'contract_id': 'scene', 'rows': [True, None, {'at': '08:00'}]}),
    ('dict', {'open': [], 'resolved': []}),
    ('str | Path', 'world.yaml'),
    ('str | Path', Path('world.yaml')),
    ('Optional[list[dict[str, Any]]]', None),
    ('typing.List[typing.Dict[str, typing.Any]]', [{'ok': True}]),
    ('tuple[int, str]', (1, 'one')),
    ('tuple[int, ...]', (1, 2, 3)),
    ('tuple[()]', ()),
    ('tuple', ({'ready': True}, Path('world.yaml'))),
    ('Annotated[list[int], "values"]', [1, 2]),
])
def test_real_point_return_shapes(annotation, value):
    assert A._accepts(annotation, value)


@pytest.mark.parametrize('annotation,value', [
    ('list[dict]', [{} , 1]),
    ('list[int]', [True]),
    ('dict[str, Any]', {1: 'wrong key'}),
    ('dict[str, int]', {'score': 'wrong value'}),
    ('Path', 'not-a-path-object'),
    ('str | Path', 1),
    ('tuple[int, str]', (1,)),
    ('tuple[int, ...]', (1, 'wrong')),
    ('tuple[()]', (1,)),
    ('list[int]', (1,)),
])
def test_known_point_shape_mismatch_is_false(annotation, value):
    assert not A._accepts(annotation, value)


def test_unknown_object_and_cycle_stay_unsupported_without_hooks():
    called = []
    class Unknown:
        def __iter__(self): called.append('iter'); return iter(())
        def __fspath__(self): called.append('fspath'); return 'invented'
        def __repr__(self): called.append('repr'); return 'invented'
    with pytest.raises(ValueError, match='unsupported object'):
        A._accepts('dict[str, Any]', {'object': Unknown()})
    assert not A._accepts('Path', Unknown())
    assert not called
    cyclic = []
    cyclic.append(cyclic)
    with pytest.raises(ValueError, match='cyclic'):
        A._accepts('list', cyclic)


def test_unknown_annotation_is_not_evaluated_or_imported():
    called = []
    class PretendTyping:
        def __class_getitem__(cls, key): called.append(key); return int
    for annotation in ('PretendTyping[int]', 'private.module.Class[int]', '__import__("os").Path'):
        with pytest.raises(ValueError):
            A._accepts(annotation, 1)
    assert not called


@pytest.mark.parametrize('annotation,value', [
    ('list[Unknown]', []),
    ('dict[str, Unknown]', {}),
    ('tuple[Unknown, ...]', ()),
    ('str | Unknown', 'known branch'),
])
def test_empty_or_other_union_branch_cannot_hide_unknown_annotation(annotation, value):
    with pytest.raises(ValueError):
        A._accepts(annotation, value)


@pytest.mark.parametrize('annotation', ['Path', 'list[int]', 'dict[str, Any]', 'tuple[int, ...]', 'str | Path'])
def test_point_shapes_never_become_cells_kinds(annotation):
    with pytest.raises(ValueError):
        A._kind(annotation)


def test_point_containers_do_not_expand_direct_pure_observation(tmp_path):
    root, index = source(tmp_path, '''# flowguard: sensor check(values: 1) -> positive: bool
def check(values: list[int]) -> bool: return values[0] > 0
''')
    with session(root):
        result = A.observe(root, index.entries[0], {'values': [1]})
    assert result.status == 'grey'
    root2, index2 = source(tmp_path, '''# flowguard: sensor check(active: 1) -> output: dict[str, Any]
def check(active: bool) -> dict[str, Any]: return {'active': active}
''', name='result')
    with session(root2):
        result = A.observe(root2, index2.entries[0], {'active': True})
    assert result.status == 'grey'
