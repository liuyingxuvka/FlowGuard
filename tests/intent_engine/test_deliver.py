"""`signals.deliver`: one policy turns findings, what a change touches and known.toml entries into the nine kinds.

Every case is a synthetic `health.Issue` or `sources.Known`; deliver reads no map, no Git and no file.
"""
import pytest

from flowguard.intent import signals
from flowguard.intent.health import Issue
from flowguard.intent.signals import Line, deliver
from flowguard.intent.sources import Known


def issue(name, family, *members, fresh=(), files=(), detail=()):
    """A finding whose members are (function, place); each says `writes A` and has the step `fix FUNCTION`."""
    return Issue(name, 2, 'short', 'text', 'step', files=frozenset(files), family=family, subject=f'subject {name}',
                 parts=tuple((function, place, 'writes A', f'fix {function or "the file"}') for function, place in members),
                 fresh=frozenset(fresh), detail=detail)


def entry(identifier, act, finding='', *, nodes=(), files=(), asked='', sites=('src/a.py:f',)):
    return Known(identifier, tuple(sites), f'why {identifier}', act, ask='which one?' if act == 'ask' else '',
                 asked=asked, finding=finding, nodes=frozenset(nodes), files=frozenset(files))


def kinds(lines):
    return [(line.kind, line.name, line.function) for line in lines]


PAIR = issue('pair:A>B', 'pair', ('m:f', 'src/a.py:f'), ('m:g', 'src/b.py:g'), fresh=['m:f'])


def test_a_fresh_member_of_a_family_that_can_be_red_is_red_with_its_subject_place_and_step():
    lines, ignored = deliver([PAIR], touched_functions=(), touched_files=())
    assert lines == [Line('red', 'pair:A>B', 'm:f', 'subject pair:A>B: src/a.py:f writes A', 'fix m:f', ('src/a.py:f',))]
    assert ignored == 0


def test_an_old_member_is_before_only_when_the_change_touches_its_function_or_with_everything():
    assert kinds(deliver([PAIR], touched_functions={'m:g'}, touched_files=())[0]) == [
        ('red', 'pair:A>B', 'm:f'), ('before', 'pair:A>B', 'm:g')]
    before = deliver([PAIR], touched_functions={'m:g'}, touched_files=())[0][1]
    assert (before.text, before.step) == ('subject pair:A>B at src/b.py:g was broken at task start',
                                          'leave it unless your task is about it')
    # The file of an old function-level member is no touch: only its function is.
    assert kinds(deliver([PAIR], touched_functions={'m:other'}, touched_files={'src/b.py'})[0]) == [('red', 'pair:A>B', 'm:f')]
    assert kinds(deliver([PAIR], touched_functions=(), touched_files=(), everything=True)[0]) == [
        ('red', 'pair:A>B', 'm:f'), ('before', 'pair:A>B', 'm:g')]


@pytest.mark.parametrize('act', ['leave', 'ask', 'fix', 'ignore'])
def test_a_known_entry_never_silences_a_fresh_red_and_is_named_in_its_detail(act):
    # D29: also an entry whose sites the change touches gets no line of its own beside that red.
    known = [entry('k', act, 'pair:A>B', nodes={'m:f'})]
    lines, ignored = deliver([PAIR], touched_functions={'m:f'}, touched_files=(), known=known)
    assert kinds(lines) == [('red', 'pair:A>B', 'm:f')] and ignored == 0
    assert any('known.k' in text for text in lines[0].detail), lines[0].detail


def test_a_fresh_member_of_a_structure_family_is_impact_and_keeps_the_finding_detail():
    delete = issue('delete:src/a.py:f:Order', 'delete', ('m:f', 'src/a.py:f'), fresh=['m:f'], detail=('Order has children',))
    lines, ignored = deliver([delete], touched_functions=(), touched_files=())
    assert lines == [Line('impact', 'delete:src/a.py:f:Order', 'm:f', 'subject delete:src/a.py:f:Order: src/a.py:f writes A',
                          'fix it, or say why in your report', ('src/a.py:f',), ('Order has children',))]
    assert ignored == 0


def test_an_ignore_entry_counts_the_members_of_a_family_that_may_be_ignored_and_shows_none():
    delete = issue('delete:x', 'delete', ('m:f', 'src/a.py:f'), ('m:g', 'src/b.py:g'), ('m:h', 'src/c.py:h'), fresh=['m:f'])
    lines, ignored = deliver([delete], touched_functions={'m:g'}, touched_files=(), known=[entry('k', 'ignore', 'delete:x')])
    assert lines == [] and ignored == 3            # fresh, old touched and old untouched members alike
    # Beside an entry of another act the members stay shown: the touched old one as that entry's, once its sites
    # are touched too.
    both = [entry('k', 'ignore', 'delete:x'), entry('l', 'leave', 'delete:x', nodes={'m:g'})]
    lines, ignored = deliver([delete], touched_functions={'m:g'}, touched_files=(), known=both)
    assert kinds(lines) == [('known', 'known.l', 'm:g'), ('impact', 'delete:x', 'm:f')] and ignored == 0
    away = [entry('k', 'ignore', 'delete:x'), entry('l', 'leave', 'delete:x', nodes={'m:other'})]
    lines, ignored = deliver([delete], touched_functions={'m:g'}, touched_files=(), known=away)
    assert kinds(lines) == [('impact', 'delete:x', 'm:f')] and ignored == 0


def test_ignore_holds_only_for_families_that_may_be_ignored():
    for family, ignorable in signals.FAMILIES.items():
        assert ignorable[2] == (family in ('delete', 'columns', 'ondelete', 'labels', 'uncreated', 'copies',
                                           'declarations', 'writers')), family
    # D10: an ignore entry on a pair is no entry at all: the fresh member stays red, the touched old one before.
    lines, ignored = deliver([PAIR], touched_functions={'m:g'}, touched_files=(), known=[entry('k', 'ignore', 'pair:A>B')])
    assert kinds(lines) == [('red', 'pair:A>B', 'm:f'), ('before', 'pair:A>B', 'm:g')] and ignored == 0


def test_ignored_members_are_counted_once_each():
    delete = issue('delete:x', 'delete', ('m:f', 'src/a.py:f'))
    assert deliver([delete, delete], touched_functions=(), touched_files=(), known=[entry('k', 'ignore', 'delete:x')]) == ([], 1)


@pytest.mark.parametrize('act, asked, step', [
    ('leave', '', 'leave it (the owner deferred it)'),
    ('ask', '', 'ask owner (not asked yet)'),
    ('ask', '2026-11-12', 'asked on 2026-11-12; leave it until the owner answers'),
    ('fix', '', 'fix it in this change and say so in your report'),
])
def test_a_touched_old_member_named_by_a_known_entry_is_a_known_line_with_the_step_of_its_act(act, asked, step):
    known = [entry('k', act, 'pair:A>B', asked=asked, nodes={'m:g'})]
    lines, _ = deliver([PAIR], touched_functions={'m:g'}, touched_files=(), known=known)
    assert kinds(lines) == [('red', 'pair:A>B', 'm:f'), ('known', 'known.k', 'm:g')]
    assert (lines[1].text, lines[1].step, lines[1].places) == ('known.k at src/b.py:g', step, ('src/b.py:g',))
    assert 'why: why k' in lines[1].detail
    # A site of the entry in a file the change touches counts as well.
    by_file = [entry('k', act, 'pair:A>B', asked=asked, files={'src/b.py'})]
    assert kinds(deliver([PAIR], touched_functions={'m:g'}, touched_files={'src/b.py'}, known=by_file)[0]) == [
        ('red', 'pair:A>B', 'm:f'), ('known', 'known.k', 'm:g')]
    # Untouched, the old member says nothing; with everything it is listed.
    assert kinds(deliver([PAIR], touched_functions=(), touched_files=(), known=known)[0]) == [('red', 'pair:A>B', 'm:f')]
    assert kinds(deliver([PAIR], touched_functions=(), touched_files=(), known=known, everything=True)[0]) == [
        ('red', 'pair:A>B', 'm:f'), ('known', 'known.k', 'm:g')]


def test_a_touched_old_member_named_by_a_known_entry_whose_sites_are_untouched_says_nothing():
    # 4.7: `known` needs the entry's sites touched, `before` needs no entry naming the finding.
    for sites in (dict(), dict(nodes={'m:other'}), dict(files={'src/other.py'})):
        known = [entry('k', 'leave', 'pair:A>B', **sites)]
        assert kinds(deliver([PAIR], touched_functions={'m:g'}, touched_files={'src/b.py'}, known=known)[0]) == [
            ('red', 'pair:A>B', 'm:f')], sites
        assert kinds(deliver([PAIR], touched_functions={'m:g'}, touched_files=(), known=known, everything=True)[0]) == [
            ('red', 'pair:A>B', 'm:f'), ('known', 'known.k', 'm:g')], sites
    # The entry's sites touched and the member not: the entry's own line (beside no red, which would name it).
    old = issue('pair:A>B', 'pair', ('m:g', 'src/b.py:g'))
    known = [entry('k', 'leave', 'pair:A>B', nodes={'m:other'})]
    assert kinds(deliver([old], touched_functions={'m:other'}, touched_files=(), known=known)[0]) == [('known', 'known.k', '')]
    assert kinds(deliver([old], touched_functions={'m:other', 'm:g'}, touched_files=(), known=known)[0]) == [
        ('known', 'known.k', 'm:g')]


def test_writers_findings_have_lines_of_their_own_only_with_everything():
    writers = issue('writers:Order.status', 'writers', ('m:f', 'src/a.py:f'), ('m:g', 'src/b.py:g'), fresh=['m:f'])
    assert deliver([writers], touched_functions={'m:f', 'm:g'}, touched_files=()) == ([], 0)
    assert deliver([writers], touched_functions={'m:g'}, touched_files=(), known=[entry('k', 'leave', 'writers:Order.status')]) == ([], 0)
    assert kinds(deliver([writers], touched_functions=(), touched_files=(), everything=True)[0]) == [
        ('before', 'writers:Order.status', 'm:g'), ('impact', 'writers:Order.status', 'm:f')]
    assert deliver([writers], touched_functions=(), touched_files=(), known=[entry('k', 'ignore', 'writers:Order.status')]) == ([], 2)


@pytest.mark.parametrize('act, step', [
    ('leave', 'the owner deferred it: revert, or say why in your report'),
    ('ask', 'the owner has not decided: revert, or say why in your report'),
    ('fix', 'say so in your report; remove known.k once the owner agrees'),
    ('ignore', 'say so in your report; remove known.k once the owner agrees'),
])
def test_known_fixed_needs_a_finding_whose_family_ran_and_that_is_gone(act, step):
    known = [entry('k', act, 'same:ISO_WEEKS', nodes={'m:f'})]
    lines, _ = deliver([], touched_functions=(), touched_files=(), known=known, ran={'same'})
    assert lines == [Line('known fixed?', 'known.k', '', 'known.k: same:ISO_WEEKS no longer found', step, (), lines[0].detail)]
    # The family did not run: nothing is said to be fixed (a touched site still gives the known line).
    assert deliver([], touched_functions=(), touched_files=(), known=known, ran={'pair'}) == ([], 0)
    touched = deliver([], touched_functions={'m:f'}, touched_files=(), known=known, ran=frozenset())[0]
    assert kinds(touched) == ([] if act == 'ignore' else [('known', 'known.k', '')])
    # The finding is still there: not fixed.
    same = issue('same:ISO_WEEKS', 'same', ('a.ts|b.ts', 'src/a.ts:weeks'))
    assert 'known fixed?' not in [line.kind for line in deliver([same], touched_functions=(), touched_files=(), known=known, ran={'same'})[0]]
    # An entry without a finding is never fixed.
    assert deliver([], touched_functions=(), touched_files=(), known=[entry('n', act)], ran=set(signals.FAMILIES)) == ([], 0)


def test_an_entry_whose_sites_the_change_touches_is_known_once_and_never_for_ignore():
    known = [entry('fn', 'ask', nodes={'m:f'}, sites=('src/a.py:f', 'src/b.py:g')),
             entry('file', 'leave', files={'prisma/schema.prisma'}, sites=('prisma/schema.prisma:Order.status',)),
             entry('quiet', 'ignore', nodes={'m:f'}), entry('away', 'fix', nodes={'m:x'})]
    lines, ignored = deliver([], touched_functions={'m:f'}, touched_files={'prisma/schema.prisma'}, known=known)
    assert kinds(lines) == [('known', 'known.fn', ''), ('known', 'known.file', '')] and ignored == 0
    assert (lines[0].text, lines[0].step, lines[0].places) == ('known.fn at src/a.py:f, src/b.py:g', 'ask owner (not asked yet)',
                                                               ('src/a.py:f', 'src/b.py:g'))
    assert 'ask: which one?' in lines[0].detail
    # With everything, every entry but the ignore one is listed.
    assert kinds(deliver([], touched_functions=(), touched_files=(), known=known, everything=True)[0]) == [
        ('known', 'known.fn', ''), ('known', 'known.file', ''), ('known', 'known.away', '')]
    # An entry that already has a line for one of its finding's members gets no second one.
    named = [entry('k', 'leave', 'pair:A>B', nodes={'m:g'})]
    assert kinds(deliver([PAIR], touched_functions={'m:g'}, touched_files=(), known=named)[0]) == [
        ('red', 'pair:A>B', 'm:f'), ('known', 'known.k', 'm:g')]


def test_a_file_level_member_is_touched_through_the_findings_files():
    columns = issue('columns:db.sql~schema.prisma', 'columns', ('', 'db.sql:3'), files={'db.sql', 'schema.prisma'})
    assert deliver([columns], touched_functions={'m:f'}, touched_files=()) == ([], 0)
    lines, _ = deliver([columns], touched_functions=(), touched_files={'schema.prisma'})
    assert kinds(lines) == [('before', 'columns:db.sql~schema.prisma', '')] and lines[0].places == ('db.sql:3',)
    fresh = issue('input:known.x', 'input', ('', '.flowguard/known.toml:3'), fresh=[''])
    assert kinds(deliver([fresh], touched_functions=(), touched_files=())[0]) == [('red', 'input:known.x', '')]


def test_lines_are_unique_by_kind_name_and_function_and_follow_the_order_of_kinds():
    extra = [Line('not compared', 'not compared', '', '2 functions (async) '), Line('loosened', 'loosened:except', '', 'x'),
             Line('changed', 'changed:m:f', 'm:f', 'a'), Line('impact', 'impact:m:f', 'm:f', 'b'),
             Line('changed', 'changed:m:f', 'm:f', 'second copy is dropped'), Line('red', 'pair:A>B', 'm:f', 'merged red')]
    lines, _ = deliver([PAIR, PAIR], touched_functions={'m:g'}, touched_files=(), known=[entry('k', 'fix', 'gone:x')],
                       ran={'pair'}, extra=extra)
    assert kinds(lines) == [('red', 'pair:A>B', 'm:f'), ('before', 'pair:A>B', 'm:g'), ('changed', 'changed:m:f', 'm:f'),
                            ('impact', 'impact:m:f', 'm:f'), ('loosened', 'loosened:except', ''), ('not compared', 'not compared', '')]
    assert lines[0].text == 'subject pair:A>B: src/a.py:f writes A' and lines[2].text == 'a'
    assert [line.kind for line in lines] == sorted((line.kind for line in lines), key=signals.KINDS.index)
    # 'gone:x' names no family, so its entry is never called fixed.
    assert signals.family_of('gone:x') == '' and signals.family_of('pair:A>B') == 'pair'


def test_a_finding_without_family_subject_or_parts_and_an_unknown_kind_or_act_are_refused():
    with pytest.raises(ValueError, match='family'):
        deliver([Issue('pair:A>B', 2, 's', 't', 'st')], touched_functions=(), touched_files=())
    with pytest.raises(ValueError, match='subject'):
        deliver([Issue('pair:A>B', 2, 's', 't', 'st', family='pair', subject='together A')], touched_functions=(), touched_files=())
    with pytest.raises(ValueError, match='fresh'):
        deliver([issue('pair:A>B', 'pair', ('m:f', 'a.py:f'), fresh=['m:g'])], touched_functions=(), touched_files=())
    with pytest.raises(ValueError, match='kind'):
        deliver([], touched_functions=(), touched_files=(), extra=[Line('lead', 'x')])
    with pytest.raises(ValueError, match='act'):
        deliver([], touched_functions=(), touched_files=(), known=[entry('k', 'later')])
