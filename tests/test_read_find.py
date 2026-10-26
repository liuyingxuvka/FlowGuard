"""Tests grouped by their model or native component."""
from __future__ import annotations
import pytest,os,json
from pathlib import Path


def test_find_ranks_the_component_that_defines_an_exact_symbol_first(tmp_path):
    from flowguard.map.inventory import Inventory, PyInfo
    from flowguard.map.views import find_owners
    from _fg_helpers import view__component as _component
    inv = Inventory(tmp_path, ['owner.py'], ['owner.py'], [],
                    {'owner.py': PyInfo('owner', {'anchor_problems', 'Thing.anchor_problems'})}, {}, {})
    data = dict(components=[_component('descriptions', summary='anchor problems',
                                       responsibilities=['anchor problems']),
                            dict(_component('implementation'), files=['owner.py'])])
    for words in (['anchor_problems'], ['ANCHOR_PROBLEMS'], ['Thing.anchor_problems']):
        assert find_owners(data, inv, words)[0][1] == 'implementation'


def test_find_matches_word_forms(tmp_path):
    from flowguard.map.views import find_owners
    from _fg_helpers import view__inventory as _inventory, view__component as _component
    data = dict(components=[_component('timed', responsibilities=['rejects expired tokens']),
                            _component('signing', responsibilities=['rotation of signing keys']),
                            _component('orders', responsibilities=['promotion of orders'])])
    inv = _inventory(tmp_path)
    assert find_owners(data, inv, ['expire'])[0][1] == 'timed'
    assert find_owners(data, inv, ['rotate'])[0][1] == 'signing'
    assert find_owners(data, inv, ['rotating'])[0][1] == 'signing'
    assert find_owners(data, inv, ['promote'])[0][1] == 'orders'
    assert find_owners(data, inv, ['order'])[0][1] == 'orders'
    from flowguard.map.views import _stem
    assert len({_stem(word) for word in ('expire', 'expired', 'expires')}) == 1
    assert len({_stem(word) for word in ('rotate', 'rotation', 'rotating')}) == 1
    assert _stem('order') == _stem('orders') and _stem('promote') == _stem('promotion')


def test_find_bonus_needs_the_joined_query():
    from pathlib import Path
    from flowguard.map.views import find_owners
    from flowguard.map.inventory import build_inventory
    from flowguard.map.mapfile import load_map, ignore_patterns
    from flowguard.map.views import defined_symbols
    root = Path(__file__).resolve().parents[1]
    data = load_map(root)
    inv = build_inventory(root, ignore_patterns(data), with_bodies=False, write_cache=False)
    queries = {"promote target": "map-target", "target check environment error blocks promotion": "map-target", "find_owners": "map-read"}
    for query, cid in queries.items():
        assert find_owners(data, inv, query.split())[0][1] == cid
    owner = next(c for c in data["components"] if c["id"] == "map-target")
    for query in ("promote target", "promote_target", "PromoteTarget"):
        assert any(name == "promote_target" for name, _ in defined_symbols(owner, inv, query.split()))
    generic = next(c for c in data["components"] if c["id"] == "map-file")
    assert not defined_symbols(generic, inv, ["promote", "target"])


def test_locate_prefers_the_owner_over_a_deeper_reacher(tmp_path):
    from _fg_helpers import view_locate_fixture as locate_fixture
    helper=locate_fixture();helper['fixture'](tmp_path)
    code,text=helper['observe'](tmp_path,'owned')
    assert code==0 and text.splitlines()[1].startswith('model owner (owned: Run)')
    assert 'reached by: deeper' in text
    assert 'called by tests: 1 unbound (tests/test_api.py::test_unbound)' in text
    code,text=helper['observe'](tmp_path,'reached')
    assert code==0 and text.startswith('no model owns api.py:helper')
    assert 'deeper (via api.py:wrapper)' in text


def test_locate_bound_test_shows_model_rule_and_code(tmp_path):
    from _fg_helpers import view_locate_fixture as locate_fixture
    helper=locate_fixture();helper['fixture'](tmp_path)
    code,text=helper['observe'](tmp_path,'bound')
    assert code==0
    assert 'bound to: owner (rule safe)' in text
    assert 'calls: api.py:owned (owned by owner)' in text
    assert 'code: owner owns api.py:owned < app < system' in text


def test_locate_output_within_budget(tmp_path):
    from _fg_helpers import view_locate_fixture as locate_fixture
    helper=locate_fixture();helper['fixture'](tmp_path)
    for case in helper['CASES']:
        code,text=helper['observe'](tmp_path,case)
        assert len(text)<=2000,(case,len(text))
