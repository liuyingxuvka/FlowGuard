"""Static facts formerly embedded in legacy impact test fixtures."""
from _pure_helpers import write,git
from flowguard.map.inventory import build_inventory
from flowguard.map.common import DEFAULT_IGNORE

def test_impact_static_parenthesized_import_is_not_dynamic(project):
    write(project,'shop/api.py','from shop.orders import (\n    place_order,\n)\n')
    inv=build_inventory(project,DEFAULT_IGNORE)
    assert 'shop/orders.py' in inv.file_deps['shop/api.py']
    assert 'shop/api.py' not in inv.dynamic_files

def test_non_ascii_file_names_are_inventoried_and_fingerprinted(project):
    from flowguard.map.common import content_digest
    write(project,'shop/工具.py','def 帮助():\n    return 1\n')
    git(project,'add','-A')
    inv=build_inventory(project,DEFAULT_IGNORE)
    assert 'shop/工具.py' in inv.source
    before=content_digest(project/'shop/工具.py')
    write(project,'shop/工具.py','def 帮助():\n    return 2\n')
    assert content_digest(project/'shop/工具.py')!=before

def test_explicit_test_named_product_file_is_owned_and_not_run_as_test(project):
    write(project,'shop/test_inventory.py','VALUE = 1\n')
    inv=build_inventory(project,DEFAULT_IGNORE)
    assert inv.is_test('shop/test_inventory.py')
    inv.set_explicit_sources(['shop/test_inventory.py'])
    assert 'shop/test_inventory.py' in inv.source
    assert not inv.is_test('shop/test_inventory.py') and 'shop/test_inventory.py' not in inv.tests

def test_lazy_facade_selection_preserves_ancestor_initialization_without_hub(tmp_path):
    write(tmp_path,'pkg/__init__.py',"import importlib\n_TABLE = {'pkg.a': ('A',), 'pkg.b': ('B',)}\ndef __getattr__(name):\n    return importlib.import_module('pkg.a')\n")
    write(tmp_path,'pkg/a.py','A = 1\n');write(tmp_path,'pkg/b.py','B = 2\n')
    write(tmp_path,'consumer.py','from pkg import A\n')
    inv=build_inventory(tmp_path,DEFAULT_IGNORE)
    assert 'pkg/a.py' in inv.file_deps['consumer.py']
    assert 'pkg/b.py' not in inv.file_deps['consumer.py'] and 'pkg/__init__.py' not in inv.file_deps['consumer.py']

def test_npm_static_import_is_not_a_dynamic_surface(project):
    write(project,'web/app.js',"import React from 'react';\n")
    assert 'web/app.js' not in build_inventory(project,DEFAULT_IGNORE).dynamic_files
