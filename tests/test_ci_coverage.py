"""Publication needs complete unsharded checks on all three supported platforms."""
from __future__ import annotations

import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import re
import textwrap

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('flowguard_ci_coverage_tests', ROOT / '.github/scripts/ci_coverage.py')
COVERAGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(COVERAGE)
SHA, RUN, ATTEMPT, REPOSITORY = 'a' * 40, 123, 2, 'owner/FlowGuard'
EXPECTED_JOBS = {
    'Complete tests (ubuntu-latest, py3.11)',
    'Complete tests (ubuntu-latest, py3.13)',
    'Complete tests (windows-latest, py3.12)',
}
REQUIRED_STEPS = {
    'Verify the active virtual environment before installation',
    'Verify the frozen source before execution',
    'Complete unsharded intent and project tests',
    'Verify the frozen source after execution',
}
SKILL_STEP = 'Verify the distributable skill in a temporary directory'


def ci_context():
    current = dict(id=RUN, run_attempt=ATTEMPT, head_sha=SHA, head_branch='main', event='push',
                   repository={'full_name': REPOSITORY}, head_repository={'full_name': REPOSITORY},
                   path='.github/workflows/ci.yml', status='completed', conclusion='success')
    jobs = []
    for name in sorted(EXPECTED_JOBS):
        steps = REQUIRED_STEPS | ({SKILL_STEP} if name == 'Complete tests (ubuntu-latest, py3.11)' else set())
        jobs.append(dict(name=name, head_sha=SHA, run_id=RUN, run_attempt=ATTEMPT, status='completed', conclusion='success',
                         steps=[dict(name=step, status='completed', conclusion='success') for step in sorted(steps)]))
    return current, jobs


def validate(current, jobs):
    COVERAGE.validate_ci_run(current, jobs, source_sha=SHA, repository=REPOSITORY, run_id=RUN, run_attempt=ATTEMPT)


def test_three_full_platform_checks_are_sufficient_and_independently_required():
    current, jobs = ci_context()
    assert COVERAGE.required_jobs() == EXPECTED_JOBS
    validate(current, jobs)
    for missing in EXPECTED_JOBS:
        with pytest.raises(AssertionError, match='complete exact CI job set'):
            validate(current, [job for job in jobs if job['name'] != missing])


@pytest.mark.parametrize('defect', [
    'extra_job', 'duplicate_job', 'job_skip', 'job_failure', 'job_cancelled', 'job_running',
    'job_sha', 'job_attempt', 'job_run', 'boolean_job_attempt', 'boolean_job_run',
    'run_sha', 'run_attempt', 'run_id', 'run_branch', 'run_event', 'run_workflow',
    'run_status', 'run_result', 'fork', 'head_fork', 'boolean_run_attempt', 'boolean_run_id',
])
def test_foreign_partial_or_failed_ci_is_never_release_evidence(defect):
    current, jobs = ci_context()
    if defect == 'extra_job':
        jobs.append(dict(jobs[0], name='Other check'))
    elif defect == 'duplicate_job':
        jobs[-1] = copy.deepcopy(jobs[0])
    elif defect.startswith('job_') and defect.removeprefix('job_') in {'skip', 'failure', 'cancelled'}:
        jobs[0]['conclusion'] = {'job_skip': 'skipped', 'job_failure': 'failure', 'job_cancelled': 'cancelled'}[defect]
    elif defect == 'job_running':
        jobs[0]['status'] = 'in_progress'
    elif defect in {'job_sha', 'job_attempt', 'job_run', 'boolean_job_attempt', 'boolean_job_run'}:
        key, value = {'job_sha': ('head_sha', 'b' * 40), 'job_attempt': ('run_attempt', 1),
                      'job_run': ('run_id', RUN + 1), 'boolean_job_attempt': ('run_attempt', True),
                      'boolean_job_run': ('run_id', True)}[defect]
        jobs[0][key] = value
    elif defect in {'fork', 'head_fork'}:
        current['repository' if defect == 'fork' else 'head_repository']['full_name'] = 'other/FlowGuard'
    else:
        key, value = {'run_sha': ('head_sha', 'b' * 40), 'run_attempt': ('run_attempt', 1),
                      'run_id': ('id', RUN + 1), 'run_branch': ('head_branch', 'other'),
                      'run_event': ('event', 'workflow_dispatch'), 'run_workflow': ('path', '.github/workflows/other.yml'),
                      'run_status': ('status', 'in_progress'), 'run_result': ('conclusion', 'failure'),
                      'boolean_run_attempt': ('run_attempt', True), 'boolean_run_id': ('id', True)}[defect]
        current[key] = value
    with pytest.raises(AssertionError):
        validate(current, jobs)


@pytest.mark.parametrize('step', sorted(REQUIRED_STEPS | {SKILL_STEP}))
@pytest.mark.parametrize('defect', ['missing', 'duplicate', 'skipped', 'failure', 'cancelled', 'running'])
def test_a_green_job_cannot_hide_a_missing_or_unfinished_required_step(step, defect):
    current, jobs = ci_context()
    job = next(job for job in jobs if any(item['name'] == step for item in job['steps']))
    selected = next(item for item in job['steps'] if item['name'] == step)
    if defect == 'missing':
        job['steps'].remove(selected)
    elif defect == 'duplicate':
        job['steps'].append(selected.copy())
    elif defect == 'running':
        selected['status'] = 'in_progress'
    else:
        selected['conclusion'] = defect
    with pytest.raises(AssertionError, match='required full-check step'):
        validate(current, jobs)


def test_a_smaller_candidate_matrix_cannot_reduce_publication_requirements(tmp_path, monkeypatch):
    workflow = tmp_path / '.github/workflows/ci.yml'
    workflow.parent.mkdir(parents=True)
    workflow.write_text('jobs: {checks: {strategy: {matrix: {include: [{os: ubuntu-latest, python: "3.11"}]}}}}\n')
    monkeypatch.chdir(tmp_path)
    current, jobs = ci_context()
    assert COVERAGE.required_jobs() == EXPECTED_JOBS
    with pytest.raises(AssertionError, match='complete exact CI job set'):
        validate(current, jobs[:1])


def workflow_steps():
    text = (ROOT / '.github/workflows/ci.yml').read_text(encoding='utf-8')
    assert re.findall(r'^  (\w+):$', text.split('jobs:\n', 1)[1], re.M) == ['checks']
    assert 'fail-fast: false' in text
    assert 'name: Complete tests (${{ matrix.os }}, py${{ matrix.python }})' in text
    assert re.findall(r'- os: (\S+)\n            python: "([^"]+)"', text) == [
        ('ubuntu-latest', '3.11'), ('ubuntu-latest', '3.13'), ('windows-latest', '3.12'),
    ]
    assert re.search(r'--shard\b|matrix\.shard|\bshard_count:', text) is None
    return dict(re.findall(r'^      - name: (.+?)\n(.*?)(?=^      - name: |\Z)', text, re.M | re.S))


def test_repository_workflow_runs_the_complete_check_without_shards_or_filters():
    steps = workflow_steps()
    assert steps['Complete unsharded intent and project tests'].strip() == 'run: python -m flowguard check --all --deep'
    for name in ('Verify the frozen source before execution', 'Verify the frozen source after execution'):
        assert steps[name].strip() == 'run: python .github/scripts/ci_coverage.py identity'
    assert 'ref: ${{ github.sha }}' in steps['Checkout the triggering source and its history']
    assert 'fetch-depth: 0' in steps['Checkout the triggering source and its history']
    assert 'scripts/install_skill.py' in steps[SKILL_STEP] and '--check' in steps[SKILL_STEP]
    assert "if: matrix.os == 'ubuntu-latest' && matrix.python == '3.11'" in steps[SKILL_STEP]


def test_workflow_verifies_an_actual_fresh_outside_virtual_environment(tmp_path):
    runner = tmp_path / 'runner'
    environment = runner / 'flowguard-ci-venv'
    project = tmp_path / 'project'
    project.mkdir()
    subprocess.run([sys.executable, '-m', 'venv', '--without-pip', str(environment)], check=True)
    python = environment / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    script = textwrap.dedent(workflow_steps()['Verify the active virtual environment before installation'].split('        run: |\n', 1)[1])
    script = script.replace('${{ matrix.python }}', '.'.join(map(str, sys.version_info[:2])))
    script = script.replace('${{ matrix.os }}', 'windows-latest' if os.name == 'nt' else 'ubuntu-latest')
    context = dict(os.environ, RUNNER_TEMP=str(runner), GITHUB_WORKSPACE=str(project))
    completed = subprocess.run([str(python), '-c', script], env=context, text=True, capture_output=True)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    for source, wrong, message in [('tuple(map(int, \"' + '.'.join(map(str, sys.version_info[:2])) + '\".split(\".\")))', '(0, 0)', 'actual Python must match the matrix'),
                                   ('sys.platform ==', '\"wrong-platform\" ==', 'actual platform must match the matrix')]:
        rejected = subprocess.run([str(python), '-c', script.replace(source, wrong)], env=context, text=True, capture_output=True)
        assert rejected.returncode != 0 and message in rejected.stderr
    context['GITHUB_WORKSPACE'] = str(runner)
    rejected = subprocess.run([str(python), '-c', script], env=context, text=True, capture_output=True)
    assert rejected.returncode != 0 and 'virtual environment must be outside the project' in rejected.stderr


def git_project(tmp_path):
    project = tmp_path / 'project'
    project.mkdir()
    subprocess.run(['git', 'init', '-q', str(project)], check=True)
    (project / 'source.py').write_text('VALUE = 1\n', encoding='utf-8')
    subprocess.run(['git', '-C', str(project), 'add', 'source.py'], check=True)
    subprocess.run(['git', '-C', str(project), '-c', 'user.name=Coverage test', '-c', 'user.email=coverage@example.invalid',
                    'commit', '-qm', 'original source'], check=True)
    return project, subprocess.check_output(['git', '-C', str(project), 'rev-parse', 'HEAD'], text=True).strip()


def test_identity_preserves_the_exact_ci_attempt_and_real_git_source(tmp_path, monkeypatch, capsys):
    project, source_sha = git_project(tmp_path)
    for key, value in dict(GITHUB_SHA=source_sha, GITHUB_RUN_ID=str(RUN), GITHUB_RUN_ATTEMPT=str(ATTEMPT),
                           GITHUB_WORKSPACE=str(project)).items():
        monkeypatch.setenv(key, value)
    COVERAGE.main(['identity'])
    assert json.loads(capsys.readouterr().out) == dict(source_sha=source_sha, run_id=RUN, run_attempt=ATTEMPT,
                                                    tracked_source_unchanged=True)


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
