"""A green shard is insufficient unless every planned node and job is accounted for."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('flowguard_ci_coverage_tests', ROOT / '.github/scripts/ci_coverage.py')
COVERAGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(COVERAGE)
SHA = 'a' * 40
RUN = 123
ATTEMPT = 2
REPOSITORY = 'owner/FlowGuard'
RULE = 'tests/intent/contract.py::RULE[rules]'
COMMON = [COVERAGE.SENTINEL, RULE, 'tests/test_scenario.py::test_observation[original]']
ORDINARY = [f'tests/test_cases.py::test_case[{index:02}]' for index in range(36)]


def receipt(row):
    partition = sorted(ORDINARY)[row['shard'] - 1::row['shard_count']]
    selected = sorted(COMMON + partition)
    return dict(schema=1, source_sha=SHA, run_id=RUN, run_attempt=ATTEMPT,
                platform=row['os'], python=row['python'], shard_index=row['shard'], shard_count=row['shard_count'],
                collected_nodeids=sorted(COMMON + ORDINARY), common_nodeids=sorted(COMMON), partition_nodeids=partition,
                selected_nodeids=selected, completed_nodeids=selected.copy(),
                intent=dict(declared_nodeids=[RULE], selected_nodeids=[RULE], completed_nodeids=[RULE]),
                sentinel='ok', exit=0, pytest_exit=0, errors=[])


def receipts():
    return [receipt(row) for row in COVERAGE.matrix(ROOT)]


def aggregate(data):
    return COVERAGE.aggregate(data, source_sha=SHA, run_id=RUN, run_attempt=ATTEMPT, plan=COVERAGE.matrix(ROOT))


def test_six_disjoint_shards_cover_every_ordinary_node_on_every_supported_platform():
    result = aggregate(receipts())
    assert {(item['platform'], item['python']) for item in result['platforms']} == COVERAGE.SUPPORTED
    assert all(item['shards'] == [1, 2, 3, 4, 5, 6] and item['collected'] == 39
               and item['common'] == 3 and item['partitioned'] == 36 for item in result['platforms'])


@pytest.mark.parametrize('defect', [
    'missing', 'extra', 'duplicate', 'sha', 'run', 'attempt', 'platform', 'python', 'shard',
    'count', 'selected', 'unfinished', 'partition', 'collection', 'intent', 'no_intent',
    'sentinel', 'check_exit', 'pytest_exit', 'errors', 'boolean_schema', 'boolean_attempt',
])
def test_incomplete_or_foreign_coverage_cannot_be_aggregated(defect):
    data = receipts()
    first = data[0]
    if defect == 'missing':
        data.pop()
    elif defect == 'extra':
        data.append(copy.deepcopy(first))
    elif defect == 'duplicate':
        data[-1] = copy.deepcopy(first)
    elif defect == 'sha':
        first['source_sha'] = 'b' * 40
    elif defect == 'run':
        first['run_id'] += 1
    elif defect == 'attempt':
        first['run_attempt'] -= 1
    elif defect == 'platform':
        first['platform'] = 'macos-latest'
    elif defect == 'python':
        first['python'] = '3.10'
    elif defect == 'shard':
        first['shard_index'] = True
    elif defect == 'count':
        first['shard_count'] = 5
    elif defect == 'selected':
        first['selected_nodeids'].pop()
    elif defect == 'unfinished':
        first['completed_nodeids'].pop()
    elif defect == 'partition':
        first['partition_nodeids'][0] = ORDINARY[1]
    elif defect == 'collection':
        first['collected_nodeids'].remove(ORDINARY[-1])
    elif defect == 'intent':
        first['intent']['completed_nodeids'] = []
    elif defect == 'no_intent':
        first['intent'] = dict(declared_nodeids=[], selected_nodeids=[], completed_nodeids=[])
    elif defect == 'sentinel':
        first['sentinel'] = 'failed'
    elif defect == 'check_exit':
        first['exit'] = 1
    elif defect == 'pytest_exit':
        first['pytest_exit'] = 1
    elif defect == 'errors':
        first['errors'] = ['selected test never completed']
    elif defect == 'boolean_schema':
        first['schema'] = True
    elif defect == 'boolean_attempt':
        first['run_attempt'] = True
    with pytest.raises(AssertionError):
        aggregate(data)


@pytest.mark.parametrize('row', COVERAGE.matrix(ROOT))
def test_each_raw_shard_is_required_independently(row):
    data = receipts()
    data = [item for item in data if (item['platform'], item['python'], item['shard_index'])
            != (row['os'], row['python'], row['shard'])]
    with pytest.raises(AssertionError, match='missing or extra'):
        aggregate(data)


def ci_context():
    current = dict(id=RUN, run_attempt=ATTEMPT, head_sha=SHA, head_branch='main', event='push',
                   repository={'full_name': REPOSITORY}, head_repository={'full_name': REPOSITORY},
                   path='.github/workflows/ci.yml', status='completed', conclusion='success')
    jobs = [dict(name=name, head_sha=SHA, run_id=RUN, run_attempt=ATTEMPT, status='completed', conclusion='success')
            for name in sorted(COVERAGE.required_jobs(ROOT))]
    return current, jobs


@pytest.mark.parametrize('defect', [None, 'extra_job', 'duplicate_job', 'skip', 'failure', 'cancelled',
                                  'job_sha', 'job_attempt', 'job_run', 'run_attempt', 'fork', 'head_fork'])
def test_publisher_requires_the_exact_nineteen_same_attempt_successes(defect):
    current, jobs = ci_context()
    if defect == 'extra_job':
        jobs.append(dict(jobs[0], name='Other check'))
    elif defect == 'duplicate_job':
        jobs[-1] = jobs[0].copy()
    elif defect in {'skip', 'failure', 'cancelled'}:
        jobs[0]['conclusion'] = {'skip': 'skipped', 'failure': 'failure', 'cancelled': 'cancelled'}[defect]
    elif defect == 'job_sha':
        jobs[0]['head_sha'] = 'b' * 40
    elif defect == 'job_attempt':
        jobs[0]['run_attempt'] = ATTEMPT - 1
    elif defect == 'job_run':
        jobs[0]['run_id'] = RUN + 1
    elif defect == 'run_attempt':
        current['run_attempt'] = ATTEMPT + 1
    elif defect == 'fork':
        current['repository']['full_name'] = 'other/FlowGuard'
    elif defect == 'head_fork':
        current['head_repository']['full_name'] = 'other/FlowGuard'
    if defect:
        with pytest.raises(AssertionError):
            COVERAGE.validate_ci_run(current, jobs, source_sha=SHA, repository=REPOSITORY,
                                     run_id=RUN, run_attempt=ATTEMPT, expected_jobs=COVERAGE.required_jobs(ROOT))
    else:
        COVERAGE.validate_ci_run(current, jobs, source_sha=SHA, repository=REPOSITORY,
                                 run_id=RUN, run_attempt=ATTEMPT, expected_jobs=COVERAGE.required_jobs(ROOT))


def git_project(tmp_path):
    project = tmp_path / 'project'
    project.mkdir()
    subprocess.run(['git', 'init', '-q', str(project)], check=True)
    (project / 'source.py').write_text('VALUE = 1\n', encoding='utf-8')
    subprocess.run(['git', '-C', str(project), 'add', 'source.py'], check=True)
    subprocess.run(['git', '-C', str(project), '-c', 'user.name=Coverage test', '-c', 'user.email=coverage@example.invalid',
                    'commit', '-qm', 'original source'], check=True)
    return project, subprocess.check_output(['git', '-C', str(project), 'rev-parse', 'HEAD'], text=True).strip()


def test_ci_export_preserves_original_execution_facts_and_binds_actual_runner(tmp_path, monkeypatch):
    project, source_sha = git_project(tmp_path)
    data = receipt(COVERAGE.matrix(ROOT)[0])
    data['source_sha'] = source_sha
    for field in ('run_id', 'run_attempt', 'platform', 'python'):
        data.pop(field)
    data['interpreter'] = dict(version=list(sys.version_info[:3]), executable=sys.executable,
                               prefix=sys.prefix, base_prefix=sys.base_prefix)
    report = tmp_path / 'original.json'
    report.write_text(json.dumps(data), encoding='utf-8')
    output = tmp_path / 'coverage.json'
    target_python = '.'.join(map(str, sys.version_info[:2]))
    platform = next(row['os'] for row in COVERAGE.matrix(ROOT) if row['python'] == target_python)
    # The supported test interpreters are the same explicit versions as the CI matrix.
    monkeypatch.setenv('GITHUB_SHA', source_sha)
    monkeypatch.setenv('GITHUB_RUN_ID', str(RUN))
    monkeypatch.setenv('GITHUB_RUN_ATTEMPT', str(ATTEMPT))
    monkeypatch.setenv('GITHUB_WORKSPACE', str(project))
    monkeypatch.setenv('RUNNER_OS', 'Windows' if platform == 'windows-latest' else 'Linux')
    COVERAGE.main(['export', str(report), '--platform', platform, '--python', target_python, '--output', str(output)])
    result = json.loads(output.read_text(encoding='utf-8'))
    assert {key: value for key, value in result.items() if key not in {'run_id', 'run_attempt', 'platform', 'python'}} == data
    assert (result['run_id'], result['run_attempt'], result['platform'], result['python']) == (RUN, ATTEMPT, platform, target_python)


@pytest.mark.parametrize('defect', ['head', 'tracked_source'])
def test_ci_identity_rejects_a_different_or_edited_real_git_tree(tmp_path, defect):
    project, source_sha = git_project(tmp_path)
    if defect == 'head':
        source_sha = 'b' * 40
    else:
        (project / 'source.py').write_text('VALUE = 2\n', encoding='utf-8')
    with pytest.raises(AssertionError):
        COVERAGE.frozen_source(project, source_sha)


def test_publication_starts_after_the_source_ci_instead_of_waiting_for_another_run():
    text = (ROOT / '.github/workflows/publish-release.yml').read_text(encoding='utf-8')
    assert 'workflow_run:' in text and 'types: [completed]' in text
    assert 'github.event.workflow_run.head_repository.full_name == github.repository' in text
    assert "startsWith(github.event.workflow_run.head_commit.message, 'Release FlowGuard v')" in text
    assert "assert output(\"git\", \"show\", \"-s\", \"--format=%s\", \"HEAD\") == f\"Release FlowGuard {tag}\"" in text
    assert 'successful_ci(api(f\'actions/runs/{ci_run_id}\'))' in text
    assert 'time.sleep' not in text and 'while time.monotonic' not in text
