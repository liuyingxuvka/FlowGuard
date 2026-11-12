"""A sealed function reads a literal constant from a project module it imports, from that module's source.

Nothing is imported or executed. A name is read only when a sealed function reads it, each module source is
parsed once per runtime, and a value is used only when nothing that runs while the module loads could change
it; anything else stays not compared with its reason.
"""
import ast
from collections import Counter
import sys

import pytest

from flowguard.intent.runtime import Runtime, sealed


def _project(tmp_path, files):
    for relative, text in files.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode('latin-1') if isinstance(text, str) and '# -*- coding: latin-1 -*-' in text
                         else text if isinstance(text, bytes) else text.encode('utf-8'))
    return Runtime(tmp_path, previous={})


def _policy(tmp_path, files, policy, args=(5,)):
    runtime = _project(tmp_path, {'shop/__init__.py': '', **files, 'shop/policy.py': policy})
    return sealed(policy, 'allows', list(args), {}, runtime.imports('shop/policy.py', 'shop.policy'))


def _layered(tmp_path, depth, width=2):
    """`depth` levels of `width` modules; each module imports every module of the next level."""
    files = {'shop/__init__.py': ''}
    for level in range(depth):
        for column in range(width):
            lines = [f'C{level}_{column} = {level * 10 + column}']
            if level + 1 < depth:
                lines += [f'from shop.m{level + 1}_{other} import C{level + 1}_{other}' for other in range(width)]
            files[f'shop/m{level}_{column}.py'] = '\n'.join(lines) + '\n'
    return files


def _counting(monkeypatch):
    """How often each project source is parsed."""
    parsed, real = Counter(), ast.parse
    def counting(source, filename='<unknown>', *args, **kwargs):
        if str(filename).endswith('.py'):
            parsed[str(filename)] += 1
        return real(source, filename, *args, **kwargs)
    monkeypatch.setattr(ast, 'parse', counting)
    return parsed


def test_a_sealed_call_reads_only_the_imported_modules_its_function_reads(tmp_path, monkeypatch):
    # Twelve levels of two modules (2**13 import paths). The function's file imports the first level.
    files = _layered(tmp_path, 12)
    imports = ''.join(f'from shop.m0_{column} import C0_{column}\n' for column in range(2))
    runtime = _project(tmp_path, {**files, 'shop/policy.py': imports})
    resolver = runtime.imports('shop/policy.py', 'shop.policy')
    parsed = _counting(monkeypatch)
    # A name the function never reads is never resolved: no imported module is read at all.
    assert sealed(imports + 'def allows(days):\n    return days <= 2\n', 'allows', [3], {}, resolver) == {'status': 'ok', 'value': False}
    assert parsed == Counter()
    # A name it reads: each project module involved is parsed at most once, never once per import path.
    reads = imports + 'def allows(days):\n    return days <= C0_1\n'
    assert sealed(reads, 'allows', [1], {}, resolver) == {'status': 'ok', 'value': True}
    assert parsed and max(parsed.values()) == 1 and sum(parsed.values()) <= len(files), parsed
    # The runtime keeps each module's literals and the answer for its loading: a second call parses nothing.
    parsed.clear()
    assert sealed(reads, 'allows', [2], {}, runtime.imports('shop/policy.py', 'shop.policy')) == {'status': 'ok', 'value': False}
    assert parsed == Counter()


@pytest.mark.parametrize('models', [
    'from os.path import *\nOrder = 1\n',                    # a star import in the imported module
    'def broken(:\n',                                        # a module that does not parse
    b'Order = 1\x00\n',                                      # a null byte
    'from shop.base import *\n',                             # a star import of a project module
])
def test_a_problem_in_an_imported_module_leaves_functions_that_do_not_read_it_compared(tmp_path, models):
    policy = 'from shop.models import Order\ndef allows(days):\n    return days <= 2\n'
    assert _policy(tmp_path, {'shop/models.py': models, 'shop/base.py': 'X = 1\n'}, policy) == {'status': 'ok', 'value': False}


def test_a_module_that_does_not_parse_refuses_only_the_names_read_from_it(tmp_path):
    policy = 'from shop.models import LIMIT\ndef allows(days):\n    return days <= LIMIT\n'
    answer = _policy(tmp_path, {'shop/models.py': 'LIMIT = 3\ndef broken(:\n'}, policy)
    assert answer == {'status': 'unavailable', 'reason': 'uses LIMIT: shop/models.py does not parse: invalid syntax (line 2)'}


def test_a_star_import_in_an_imported_module_hides_only_the_literals_assigned_before_it(tmp_path):
    settings = 'EARLY = 3\nfrom os.path import *\nLATE = 4\n'
    early = 'from shop.settings import EARLY\ndef allows(days):\n    return days <= EARLY\n'
    late = 'from shop.settings import LATE\ndef allows(days):\n    return days <= LATE\n'
    assert _policy(tmp_path / 'a', {'shop/settings.py': settings}, early) == {
        'status': 'unavailable', 'reason': 'uses unavailable binding EARLY'}
    assert _policy(tmp_path / 'b', {'shop/settings.py': settings}, late, args=(4,)) == {'status': 'ok', 'value': True}


def test_an_imported_module_is_read_with_its_declared_source_encoding(tmp_path):
    policy = 'from shop.models import NAME\ndef allows(days):\n    return NAME\n'
    assert _policy(tmp_path, {'shop/models.py': '# -*- coding: latin-1 -*-\nNAME = "caf\xe9"\n'}, policy) == {
        'status': 'ok', 'value': 'caf\xe9'}


GRACE = 'from shop.settings import GRACE\ndef allows(days):\n    return days <= GRACE\n'


@pytest.mark.parametrize('files, reason', [
    # A function of the module that declares the name `global` may rebind it, while it loads or later.
    ({'shop/settings.py': 'GRACE = 3\ndef _load():\n    global GRACE\n    GRACE = 9\n_load()\n'},
     'uses unavailable binding GRACE'),
    ({'shop/settings.py': 'GRACE = 3\ndef configure():\n    global GRACE\n    GRACE = 9\n'},
     'uses unavailable binding GRACE'),
    # Any call while it loads may change it (`setattr`, `exec`, a helper of another module).
    ({'shop/settings.py': 'GRACE = 3\nsetattr(__import__("shop.settings"), "GRACE", 9)\n'},
     'uses GRACE: shop/settings.py:2 calls a function when the module loads'),
    ({'shop/settings.py': 'from shop.tweak import apply\nGRACE = 3\napply()\n', 'shop/tweak.py': 'def apply():\n    pass\n'},
     'uses GRACE: shop/settings.py:3 calls a function when the module loads'),
    ({'shop/settings.py': 'GRACE = 3\nglobals()["GRACE"] = 9\n'},
     'uses GRACE: shop/settings.py:2 writes an attribute or item when the module loads'),
    ({'shop/settings.py': 'GRACE = 3\nmatch 9:\n    case GRACE:\n        pass\n'}, 'uses unavailable binding GRACE'),
    ({'shop/settings.py': 'GRACE = 3\nmatch [9]:\n    case [*GRACE]:\n        pass\n'}, 'uses unavailable binding GRACE'),
    ({'shop/settings.py': 'GRACE = 3\nmatch {}:\n    case {**GRACE}:\n        pass\n'}, 'uses unavailable binding GRACE'),
    ({'shop/settings.py': 'GRACE = 3\ntry:\n    pass\nexcept Exception as GRACE:\n    pass\n'}, 'uses unavailable binding GRACE'),
    # A package above the module always loads first; so does every project module these import.
    ({'shop/__init__.py': 'from shop import settings\nsettings.GRACE = 9\n', 'shop/settings.py': 'GRACE = 3\n'},
     'uses GRACE: shop/__init__.py:2 writes an attribute or item when the module loads'),
    ({'shop/__init__.py': 'import shop.tweak\n', 'shop/tweak.py': 'import shop.settings\nshop.settings.GRACE = 9\n',
      'shop/settings.py': 'GRACE = 3\n'},
     'uses GRACE: shop/tweak.py:2 writes an attribute or item when the module loads'),
    ({'shop/settings.py': 'GRACE = 3\nfrom shop import tweak\n', 'shop/tweak.py': 'from shop import settings\nsettings.GRACE = 9\n'},
     'uses GRACE: shop/tweak.py:2 writes an attribute or item when the module loads'),
    ({'shop/settings.py': 'GRACE = 3\n@register\ndef hook():\n    pass\n'},
     'uses GRACE: shop/settings.py:2 runs a decorator when the module loads'),
    ({'shop/settings.py': 'GRACE = 3\nclass Tier(Base):\n    pass\n'},
     'uses GRACE: shop/settings.py:2 defines a class from a base, keyword or decorator when the module loads'),
    ({'shop/settings.py': 'GRACE = 3\nwith lock:\n    pass\n'},
     'uses GRACE: shop/settings.py:2 enters a with block when the module loads'),
])
def test_an_imported_literal_that_loading_or_a_function_could_change_is_not_compared(tmp_path, files, reason):
    assert _policy(tmp_path, files, GRACE) == {'status': 'unavailable', 'reason': reason}


@pytest.mark.parametrize('settings, policy', [
    ('LIMITS = [3]\nLIMITS.append(9)\n', 'from shop.settings import LIMITS\ndef allows(days):\n    return days <= LIMITS[-1]\n'),
    # A list or dict can change in place from any function of the program: only immutable values are read.
    ('LIMITS = [3]\ndef more():\n    LIMITS.append(9)\n', 'from shop.settings import LIMITS\ndef allows(days):\n    return days <= LIMITS[-1]\n'),
    ('LIMITS = {"g": 3}\n', 'from shop.settings import LIMITS\ndef allows(days):\n    return days <= LIMITS["g"]\n'),
])
def test_an_imported_mutable_value_is_not_compared(tmp_path, settings, policy):
    answer = _policy(tmp_path, {'shop/settings.py': settings}, policy)
    assert answer['status'] == 'unavailable' and answer['reason'].startswith('uses '), answer


def test_an_imported_tuple_of_literals_is_read(tmp_path):
    policy = 'from shop.settings import LIMITS\ndef allows(days):\n    return days <= LIMITS[1]\n'
    assert _policy(tmp_path, {'shop/settings.py': 'LIMITS = (3, 4)\n'}, policy, args=(4,)) == {'status': 'ok', 'value': True}


def test_the_same_file_constant_a_function_rebinds_with_global_is_not_compared():
    # The sealed file's own top level follows the same rule: `global NAME` anywhere makes NAME unknown.
    source = 'GRACE = 3\ndef configure():\n    global GRACE\n    GRACE = 9\ndef allows(days):\n    return days <= GRACE\n'
    assert sealed(source, 'allows', [5], {}) == {'status': 'unavailable', 'reason': 'uses unavailable binding GRACE'}
    source = 'GRACE = 3\nmatch 9:\n    case GRACE:\n        pass\ndef allows(days):\n    return days <= GRACE\n'
    assert sealed(source, 'allows', [5], {}) == {'status': 'unavailable', 'reason': 'uses unavailable binding GRACE'}


def test_a_package_wins_over_a_module_file_of_the_same_name_as_in_python(tmp_path):
    files = {'shop/settings.py': 'GRACE = 9\n', 'shop/settings/__init__.py': 'GRACE = 3\n'}
    assert _policy(tmp_path, files, GRACE) == {'status': 'ok', 'value': False}


@pytest.mark.parametrize('settings', ['from shop.base import GRACE\n', 'from math import pi as GRACE\n', 'import math as GRACE\n'])
def test_a_re_exported_name_is_not_read(tmp_path, settings):
    # Only a literal the module itself assigns is read; a name it imports, from the project or not, is not.
    files = {'shop/base.py': 'GRACE = 3\n', 'shop/settings.py': settings}
    assert _policy(tmp_path, files, GRACE) == {'status': 'unavailable', 'reason': 'uses unavailable binding GRACE'}


@pytest.mark.parametrize('kind', ['link', 'environment'])
def test_a_module_file_outside_the_project_code_is_never_read(tmp_path, kind):
    # The resolver reads only project source: never a file that links outside the root or one inside an
    # interpreter environment (a folder with pyvenv.cfg, as site-packages is).
    outside = tmp_path / 'outside'
    outside.mkdir()
    (outside / 'settings.py').write_text('GRACE = 3\n', encoding='utf-8')
    root = tmp_path / 'project'
    runtime = _project(root, {'shop/__init__.py': '', 'shop/policy.py': GRACE})
    if kind == 'link':
        (root / 'shop/settings.py').symlink_to(outside / 'settings.py')
    else:
        (root / 'shop/settings.py').write_text('GRACE = 3\n', encoding='utf-8')
        (root / 'shop/pyvenv.cfg').write_text('home = /usr/bin\n', encoding='utf-8')
    assert sealed(GRACE, 'allows', [5], {}, runtime.imports('shop/policy.py', 'shop.policy')) == {
        'status': 'unavailable', 'reason': 'uses unavailable binding GRACE'}


def test_modules_that_import_each_other_are_each_read_once(tmp_path, monkeypatch):
    files = {'shop/settings.py': 'GRACE = 3\nimport shop.rules\n', 'shop/rules.py': 'import shop.settings\nfrom shop import policy\n'}
    runtime = _project(tmp_path, {'shop/__init__.py': '', **files, 'shop/policy.py': GRACE})
    parsed = _counting(monkeypatch)
    assert sealed(GRACE, 'allows', [5], {}, runtime.imports('shop/policy.py', 'shop.policy')) == {'status': 'ok', 'value': False}
    assert parsed and max(parsed.values()) == 1, parsed
    assert 'shop.settings' not in sys.modules


@pytest.mark.parametrize('policy', [
    'import shop.settings\ndef allows(days):\n    return days <= shop.settings.GRACE\n',
    'from shop import settings\ndef allows(days):\n    return days <= settings.GRACE\n',
])
def test_an_attribute_chain_names_why_a_literal_of_its_module_is_not_read(tmp_path, policy):
    files = {'shop/__init__.py': 'from shop import settings\nsettings.GRACE = 9\n', 'shop/settings.py': 'GRACE = 3\nLATE = 2 * 2\n'}
    assert _policy(tmp_path, files, policy) == {
        'status': 'unavailable', 'reason': 'uses GRACE: shop/__init__.py:2 writes an attribute or item when the module loads'}
    # A name that is no literal of the module says only that.
    assert _policy(tmp_path / 'late', files, policy.replace('GRACE', 'LATE')) == {
        'status': 'unavailable', 'reason': 'uses unavailable attribute LATE'}
