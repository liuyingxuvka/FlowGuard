"""Require three complete, unsharded checks of the exact published source."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess


SUPPORTED = (('ubuntu-latest', '3.11'), ('ubuntu-latest', '3.13'), ('windows-latest', '3.12'))
JOBS = frozenset(f'Complete tests ({platform}, py{python})' for platform, python in SUPPORTED)
STEPS = frozenset({
    'Verify the active virtual environment before installation',
    'Verify the frozen source before execution',
    'Complete unsharded intent and project tests',
    'Verify the frozen source after execution',
})
SKILL_JOB = 'Complete tests (ubuntu-latest, py3.11)'
SKILL_STEP = 'Verify the distributable skill in a temporary directory'


def required_jobs():
    """The supported platforms are fixed here, not inferred from a proposed workflow."""
    return JOBS


def validate_ci_run(current, jobs, *, source_sha, repository, run_id, run_attempt):
    assert re.fullmatch(r'[0-9a-f]{40}', source_sha), 'full source SHA required'
    assert type(run_id) is int and run_id > 0 and type(run_attempt) is int and run_attempt > 0, 'exact CI run/attempt required'
    assert type(current['id']) is int and type(current['run_attempt']) is int, 'CI identity must be integer'
    assert current['id'] == run_id and current['run_attempt'] == run_attempt, 'CI run/attempt differs'
    assert current['head_sha'].lower() == source_sha, 'CI source differs from the selected source'
    assert current['head_branch'] == 'main' and current['event'] == 'push', 'CI must check the pushed main source'
    assert current['repository']['full_name'] == repository and current['head_repository']['full_name'] == repository, 'CI repository differs'
    assert current['path'].split('@')[0] == '.github/workflows/ci.yml', 'CI workflow differs'
    assert current['status'] == 'completed' and current['conclusion'] == 'success', 'CI did not complete successfully'
    assert len(jobs) == len(JOBS) and {job['name'] for job in jobs} == JOBS, 'complete exact CI job set required'
    for job in jobs:
        assert (job['status'] == 'completed' and job['conclusion'] == 'success'
                and job['head_sha'].lower() == source_sha and type(job['run_id']) is int
                and job['run_id'] == run_id and type(job['run_attempt']) is int
                and job['run_attempt'] == run_attempt), 'every exact-source platform check must succeed'
        required = STEPS | ({SKILL_STEP} if job['name'] == SKILL_JOB else set())
        for name in required:
            steps = [step for step in job.get('steps', ()) if step['name'] == name]
            assert len(steps) == 1 and steps[0]['status'] == 'completed' and steps[0]['conclusion'] == 'success', 'required full-check step did not succeed: ' + name


def frozen_source(project, source_sha):
    actual = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=project, text=True).strip()
    assert actual == source_sha, 'the checked-out source differs from the CI source'
    result = subprocess.run(['git', 'diff', '--quiet', 'HEAD', '--'], cwd=project)
    assert result.returncode == 0, 'tracked source/tests changed during validation'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['identity'])
    parser.parse_args(argv)
    source_sha = os.environ['GITHUB_SHA'].lower()
    run_id, run_attempt = int(os.environ['GITHUB_RUN_ID']), int(os.environ['GITHUB_RUN_ATTEMPT'])
    assert re.fullmatch(r'[0-9a-f]{40}', source_sha) and run_id > 0 and run_attempt > 0, 'invalid CI identity'
    frozen_source(Path(os.environ['GITHUB_WORKSPACE']).resolve(), source_sha)
    print(json.dumps(dict(source_sha=source_sha, run_id=run_id, run_attempt=run_attempt, tracked_source_unchanged=True)))


if __name__ == '__main__':
    main()
