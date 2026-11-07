"""Missing static imports remain unknown candidates without breaking navigation."""
from contextlib import closing

from flowguard.intent import cli
from flowguard.intent.config import load_config


def source(repo):
    repo.write({'owner.py': 'def search_budget(value):\n    """Search affordability budget."""\n    return value <= 3\n',
                'consumer.py': 'from owner import never_written\nraise AssertionError("navigation must not import this application")\n'})


def test_search_keeps_missing_identity_and_searches_real_source_without_a_doc(repo):
    source(repo)
    with closing(repo.build()) as graph:
        missing = graph.nodes(kind='missing')
        assert len(missing) == 1 and missing[0]['doc'] is None
        assert missing[0]['file'] is None
        assert any(row['id'] == 'owner:search_budget' for row in graph.search('search affordability budget'))
        found = graph.search('never_written')
        assert len(found) == 1 and found[0]['id'] == missing[0]['id']
        assert found[0]['kind'] == 'missing' and found[0]['file'] is None
        assert found[0]['matches']['doc'] == []


def test_public_show_finds_the_real_owner_in_a_project_with_missing_imports(repo, capsys):
    source(repo)
    assert cli.show(load_config(repo.path), 'search affordability budget') == 0
    text = capsys.readouterr().out
    assert 'owner:search_budget owner.py:1' in text
