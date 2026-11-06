"""Native scenarios for the existing source-boundary guards.

The tests prepare actual inputs and run product entry points. Expected policy
answers remain in tests/intent; these tests never accept a function callback.
"""
import pytest

from tests.intent_support import QuoteCase, expression_node, project_paths, quoted_document, row_program
from flowguard.structure.paths import project_code
from flowguard.map.requests import quote_matches
from flowguard.intent.sources import authority
from flowguard.intent.loader import is_literal, literal_problems


PATH_ROLES = ('source', 'empty', 'sibling', 'environment', 'site_packages',
              'interpreter', 'ordinary_dot_directory', 'relative')
EXPRESSIONS = ('1', '[1, None, True]', "D('1.25')", 'date(2026, 11, 5)',
               'GLOBAL', '1 + 3', 'make_value()')
SPELLINGS = ('direct', 'alias', 'module', 'helper')


# flowguard: event PROJECT_CASE(filename: str)
@pytest.mark.parametrize('filename', PATH_ROLES)
def test_project_anchor_case(filename: str):
    with project_paths() as paths:
        actual_path, root = paths[filename]
        assert root.is_dir()
        if filename == 'environment':
            assert (root / 'custom/pyvenv.cfg').is_file()
        answer = project_code(actual_path, root)
        assert type(answer) is bool


# flowguard: event QUOTE_CASE(quote: QuoteCase)
@pytest.mark.parametrize('quote', tuple(QuoteCase), ids=lambda q: q.name)
def test_quote_anchor_case(quote: QuoteCase):
    answer = quote_matches('alpha beta gamma', quote.value)
    assert type(answer) is bool


# flowguard: event AUTHORITY_CASE(quote: QuoteCase)
@pytest.mark.parametrize('quote', tuple(QuoteCase), ids=lambda q: q.name)
def test_authority_anchor_case(quote: QuoteCase):
    with quoted_document(quote.value) as (source, config):
        assert (config.root / 'contract.txt').read_text(encoding='utf-8') == 'alpha beta gamma'
        answer = authority(source, None, config, None)
        assert type(answer) is tuple and type(answer[0]) is bool


# flowguard: event EXPRESSION_CASE(expression: str, spelling: str)
@pytest.mark.parametrize('expression', EXPRESSIONS)
@pytest.mark.parametrize('spelling', SPELLINGS)
def test_expression_anchor_case(expression: str, spelling: str):
    node = expression_node(expression)
    answer = is_literal(node)
    assert type(answer) is bool


# flowguard: event PROGRAM_CASE(expression: str, spelling: str)
@pytest.mark.parametrize('expression', EXPRESSIONS)
@pytest.mark.parametrize('spelling', SPELLINGS)
def test_program_anchor_case(expression: str, spelling: str):
    tree = row_program(expression, spelling)
    answer = literal_problems(tree, 'fixture.py')
    assert type(answer) is list
