"""The test-only old observation rejects changed source on every supported Python."""
from contextlib import closing

import pytest
from _similarity_reference import _reference_postings
from test_fix2_mapbase import busy_repo


@pytest.mark.parametrize('change', ['decision', 'comment'])
def test_frozen_whole_function_observation_rejects_changed_source(repo, change):
    files = busy_repo()
    repo.write(files)
    with closing(repo.build()) as graph:
        _reference_postings(graph.con)
    original = files['tools/schema.py']
    altered = original.replace("'2.1'", "'2.2'") if change == 'decision' else original + '# fixture edited\n'
    repo.write({'tools/schema.py': altered})
    with closing(repo.build()) as graph:
        with pytest.raises(AssertionError, match='frozen whole-function example source changed'):
            _reference_postings(graph.con)
