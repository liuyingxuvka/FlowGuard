"""Real route-text failures keep their original diagnostics in the shared owner."""
import pytest

from tests.route_text_support import check_route_texts, local_link


@pytest.fixture
def route(tmp_path):
    skill, project = tmp_path / 'skill', tmp_path / 'project'
    skill.mkdir()
    project.mkdir()
    origin = skill / 'entry.md'
    origin.write_text('# Route\n', encoding='utf-8')
    def check(texts, flags=(), project_prefixes=('src/', 'tests/', 'examples/')):
        check_route_texts('route', texts, flags, skill_root=skill,
                          project_root=project, project_prefixes=project_prefixes)
    return origin, skill, project, check


def test_real_local_links_fragments_and_paths_are_accepted(route):
    origin, skill, project, check = route
    reference = skill / 'reference name.md'
    reference.write_text('# Policy: 三_Days\n', encoding='utf-8')
    (skill / 'scripts').mkdir()
    (skill / 'scripts/run.py').write_text('', encoding='utf-8')
    (project / 'src').mkdir()
    (project / 'src/app.py').write_text('', encoding='utf-8')
    text = ('[reference](reference%20name.md#policy-三_days) '
            '[self](#route) [external](https://invalid.example/missing#heading)\n\n'
            '`scripts/run.py` `src/app.py` `command --known`')
    check({origin: text}, {'--known'})
    assert local_link(origin, 'reference%20name.md#policy-三_days') == (reference, 'policy-三_days')
    assert local_link(origin, '#route') == (origin, 'route')
    assert local_link(origin, 'https://invalid.example/missing') is None


def test_duplicate_paragraphs_are_normalized_and_reported(route):
    origin, _, _, check = route
    paragraph = 'one two three four five six seven eight'
    with pytest.raises(AssertionError) as error:
        check({origin: paragraph + '\n\n one  two three four five six seven eight '})
    assert str(error.value) == 'route: repeated paragraph: ' + paragraph
    check({origin: 'one two three four five six seven\n\none two three four five six seven'})


@pytest.mark.parametrize('link,reason', [
    ('absent.md', 'dead link'),
    ('#absent', 'missing heading'),
])
def test_missing_links_and_headings_keep_the_original_message(route, link, reason):
    origin, _, _, check = route
    with pytest.raises(AssertionError) as error:
        check({origin: f'[reference]({link})'})
    assert str(error.value) == f'route: {reason}: {link} in {origin}'


def test_unknown_cli_flags_keep_the_original_message(route):
    origin, _, _, check = route
    with pytest.raises(AssertionError) as error:
        check({origin: '`command --unknown`'}, {'--known'})
    assert str(error.value) == 'route: unknown option: command --unknown'


@pytest.mark.parametrize('prefix', ['references/', 'assets/', 'scripts/', 'agents/', 'src/', 'tests/', 'examples/'])
def test_missing_skill_and_project_paths_keep_the_original_message(route, prefix):
    origin, _, _, check = route
    code = prefix + 'absent.py'
    with pytest.raises(AssertionError) as error:
        check({origin: f'`{code}`'})
    assert str(error.value) == 'route: missing path: ' + code


def test_each_repository_keeps_its_project_prefix_policy(route):
    origin, _, _, check = route
    check({origin: '`src/not-a-worldguard-path.py`'}, project_prefixes=('worldguard/', 'tests/'))
    with pytest.raises(AssertionError) as error:
        check({origin: '`worldguard/absent.py`'}, project_prefixes=('worldguard/', 'tests/'))
    assert str(error.value) == 'route: missing path: worldguard/absent.py'


def test_existing_command_and_placeholder_exemptions_remain(route):
    origin, _, _, check = route
    check({origin: '\n'.join('`' + code + '`' for code in [
        'grep --not-a-cli-option', 'git --not-a-cli-option', 'pip --not-a-cli-option',
        'python -m pytest --not-a-cli-option', 'python -m flowguard --not-a-cli-option',
        'scripts/<route>.py', 'scripts/*.py',
    ])})
