"""A single normalized duration needs the same source field to be a weak clue."""
from contextlib import closing

from flowguard.structure import build


def test_single_duration_copy_needs_the_same_field_and_boundary(tmp_path):
    (tmp_path/'app.py').write_text('''def owner(days): return days <= 3
def copy(days): return days <= 3
def other_field(hours): return hours <= 72
def next_boundary(days): return days <= 4
''')
    with closing(build(tmp_path,tmp_path/'map.sqlite')) as graph:
        found=graph.search_homes('app:owner',weak=True)
        candidates={row['id']:row for row in found['candidates']}
        assert 'app:copy' in candidates
        assert candidates['app:copy']['strength']=='weak'
        assert 'candidate only' in candidates['app:copy']['reason']
        assert 'app:other_field' not in candidates
        assert 'app:next_boundary' not in candidates
        assert 'app:copy' not in {row['id'] for row in graph.search_homes('app:owner',weak=False)['candidates']}


def test_new_single_time_admission_does_not_relax_multisite_decisions(tmp_path):
    (tmp_path/'app.py').write_text('''def owner(days, suspended): return days <= 3 and not suspended
def only_time(days): return days <= 3
def full_copy(days, suspended): return days <= 3 and not suspended
''')
    with closing(build(tmp_path,tmp_path/'map.sqlite')) as graph:
        candidates={row['id'] for row in graph.search_homes('app:owner',weak=True)['candidates']}
        assert 'app:full_copy' in candidates
        assert 'app:only_time' not in candidates
