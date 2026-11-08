"""CI transport and strict coverage checks for the existing check/pytest runner."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[2]
SUPPORTED = {('ubuntu-latest', '3.11'), ('ubuntu-latest', '3.13'), ('windows-latest', '3.12')}
COVERAGE_JOB = 'Complete coverage (three platforms)'
SENTINEL = 'tests/test_flowguard_intent.py::test_flowguard_intent'


def matrix(root=ROOT):
    """Read the workflow's single literal plan; publication uses this same plan."""
    text = (root / '.github/workflows/ci.yml').read_text(encoding='utf-8')
    found = re.findall(r"^\s*include: \$\{\{ fromJSON\('([^'\n]+)'\) \}\}\s*$", text, re.M)
    assert len(found) == 1, 'one explicit CI matrix is required'
    plan = json.loads(found[0])
    assert isinstance(plan, list) and plan, 'CI matrix is empty'
    keys = {'os', 'python', 'shard', 'shard_count'}
    assert all(isinstance(row, dict) and set(row) == keys for row in plan), 'unexpected CI matrix fields'
    assert {(row['os'], row['python']) for row in plan} == SUPPORTED, 'complete three-platform matrix required'
    counts = {row['shard_count'] for row in plan}
    assert len(counts) == 1, 'all platforms must use one shard count'
    count = counts.pop()
    assert type(count) is int and count > 0, 'invalid shard count'
    for platform, python in SUPPORTED:
        shards = [row['shard'] for row in plan if (row['os'], row['python']) == (platform, python)]
        assert all(type(index) is int for index in shards), 'shard index must be an integer'
        assert sorted(shards) == list(range(1, count + 1)), 'missing or duplicate CI shard'
    return plan


def job_name(row):
    return f"Complete tests ({row['os']}, py{row['python']}, shard {row['shard']}/{row['shard_count']})"


def required_jobs(root=ROOT):
    return {job_name(row) for row in matrix(root)} | {COVERAGE_JOB}


def _nodes(value, label):
    assert isinstance(value, list) and all(isinstance(item, str) and item and '\0' not in item for item in value), label
    assert len(value) == len(set(value)), f'duplicate nodeid in {label}'
    return set(value)


def validate_receipt(data, *, source_sha, run_id, run_attempt, plan):
    assert isinstance(data, dict) and type(data.get('schema')) is int and data['schema'] == 1, 'unknown coverage schema'
    assert data.get('source_sha') == source_sha, 'coverage source differs'
    assert (type(data.get('run_id')) is int and type(data.get('run_attempt')) is int
            and data['run_id'] == run_id and data['run_attempt'] == run_attempt), 'coverage run/attempt differs'
    key = data.get('platform'), data.get('python'), data.get('shard_index'), data.get('shard_count')
    expected = {(row['os'], row['python'], row['shard'], row['shard_count']) for row in plan}
    assert key in expected, 'unexpected platform, Python or shard'
    assert type(data['shard_index']) is int and type(data['shard_count']) is int, 'invalid shard identity'
    assert data.get('exit') == 0 and type(data['exit']) is int, 'original check did not succeed'
    assert type(data.get('pytest_exit')) is int and data['pytest_exit'] == 0 and data.get('errors') == [], 'original pytest did not complete cleanly'
    collected = _nodes(data.get('collected_nodeids'), 'collected')
    common = _nodes(data.get('common_nodeids'), 'common')
    partition = _nodes(data.get('partition_nodeids'), 'partition')
    selected = _nodes(data.get('selected_nodeids'), 'selected')
    completed = _nodes(data.get('completed_nodeids'), 'completed')
    assert common <= collected and partition <= collected - common, 'invalid common/partition scope'
    assert selected == common | partition, 'selected nodes differ from the planned shard'
    assert completed == selected, 'selected nodes did not all finish'
    ordinary = sorted(collected - common)
    assigned = {node for offset, node in enumerate(ordinary) if offset % data['shard_count'] == data['shard_index'] - 1}
    assert partition == assigned, 'ordinary nodes are not in their fixed partition'
    assert data.get('sentinel') == 'ok' and SENTINEL in common, 'complete intent sentinel required'
    intent = data.get('intent')
    assert isinstance(intent, dict), 'intent completion is missing'
    declared = _nodes(intent.get('declared_nodeids'), 'declared intent')
    assert declared and declared <= common, 'complete intent collection required in every shard'
    assert _nodes(intent.get('selected_nodeids'), 'selected intent') == declared, 'intent items were omitted'
    assert _nodes(intent.get('completed_nodeids'), 'completed intent') == declared, 'intent items did not finish'
    return key, collected, common, partition


def aggregate(receipts, *, source_sha, run_id, run_attempt, plan):
    assert re.fullmatch(r'[0-9a-f]{40}', source_sha), 'full source SHA required'
    assert type(run_id) is int and run_id > 0 and type(run_attempt) is int and run_attempt > 0
    assert len(receipts) == len(plan), 'missing or extra coverage receipt'
    seen, groups = set(), {}
    for data in receipts:
        key, collected, common, partition = validate_receipt(data, source_sha=source_sha, run_id=run_id,
                                                            run_attempt=run_attempt, plan=plan)
        assert key not in seen, 'duplicate shard receipt'
        seen.add(key)
        group = groups.setdefault(key[:2], dict(collected=collected, common=common, covered=set(), shards=[]))
        assert group['collected'] == collected and group['common'] == common, 'shards disagree on full collection/common nodes'
        assert not group['covered'] & partition, 'ordinary primary partitions overlap'
        group['covered'].update(partition)
        group['shards'].append(key[2])
    result = []
    for (platform, python), group in sorted(groups.items()):
        assert group['covered'] == group['collected'] - group['common'], 'ordinary collection is not fully covered'
        result.append(dict(platform=platform, python=python, shards=sorted(group['shards']),
                           collected=len(group['collected']), common=len(group['common']),
                           partitioned=len(group['covered'])))
    assert set(groups) == SUPPORTED, 'a supported platform is missing'
    return dict(schema=1, source_sha=source_sha, run_id=run_id, run_attempt=run_attempt, platforms=result)


def validate_ci_run(current, jobs, *, source_sha, repository, run_id, run_attempt, expected_jobs):
    assert current['id'] == run_id and current['run_attempt'] == run_attempt, 'CI run/attempt differs'
    assert current['head_sha'].lower() == source_sha, 'CI source differs from the selected source'
    assert current['head_branch'] == 'main' and current['event'] == 'push', 'CI must check the pushed main source'
    assert current['repository']['full_name'] == repository and current['head_repository']['full_name'] == repository, 'CI repository differs'
    assert current['path'].split('@')[0] == '.github/workflows/ci.yml', 'CI workflow differs'
    assert current['status'] == 'completed' and current['conclusion'] == 'success', 'CI did not complete successfully'
    assert len(jobs) == len(expected_jobs) and {job['name'] for job in jobs} == expected_jobs, 'complete exact CI job set required'
    assert all(job['status'] == 'completed' and job['conclusion'] == 'success'
               and job['head_sha'].lower() == source_sha and job['run_id'] == run_id
               and job['run_attempt'] == run_attempt for job in jobs), 'every exact-source shard and coverage gate must succeed'


def _identity():
    return os.environ['GITHUB_SHA'].lower(), int(os.environ['GITHUB_RUN_ID']), int(os.environ['GITHUB_RUN_ATTEMPT'])


def frozen_source(project, source_sha):
    actual = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=project, text=True).strip()
    assert actual == source_sha, 'the checked-out source differs from the CI source'
    result = subprocess.run(['git', 'diff', '--quiet', 'HEAD', '--'], cwd=project)
    assert result.returncode == 0, 'tracked source/tests changed during validation'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    operations = parser.add_subparsers(dest='operation', required=True)
    operations.add_parser('identity')
    export = operations.add_parser('export')
    export.add_argument('report', type=Path)
    export.add_argument('--platform', required=True)
    export.add_argument('--python', required=True)
    export.add_argument('--output', type=Path, required=True)
    gather = operations.add_parser('aggregate')
    gather.add_argument('directory', type=Path)
    gather.add_argument('--output', type=Path, required=True)
    options = parser.parse_args(argv)
    source_sha, run_id, run_attempt = _identity()
    project = Path(os.environ['GITHUB_WORKSPACE']).resolve()
    frozen_source(project, source_sha)
    if options.operation == 'identity':
        print(json.dumps(dict(source_sha=source_sha, run_id=run_id, run_attempt=run_attempt, tracked_source_unchanged=True)))
        return
    plan = matrix()
    if options.operation == 'export':
        data = json.loads(options.report.read_text(encoding='utf-8'))
        # The runner supplies event identity; all execution facts remain the original check report.
        data.update(run_id=run_id, run_attempt=run_attempt, platform=options.platform, python=options.python)
        assert os.environ['RUNNER_OS'] == {'ubuntu-latest': 'Linux', 'windows-latest': 'Windows'}[options.platform], 'actual runner platform differs'
        interpreter = data['interpreter']
        version = interpreter['version']
        assert isinstance(version, list) and len(version) == 3 and all(type(part) is int for part in version), 'actual Python identity is missing'
        assert [str(part) for part in version[:2]] == options.python.split('.'), 'actual Python differs from the matrix'
        prefix = Path(interpreter['prefix']).resolve()
        assert prefix != Path(interpreter['base_prefix']).resolve(), 'check must use a virtual environment'
        assert prefix != project and project not in prefix.parents, 'check virtual environment must be outside the project'
        validate_receipt(data, source_sha=source_sha, run_id=run_id, run_attempt=run_attempt, plan=plan)
        result = data
    else:
        assert os.environ['CHECKS_RESULT'] == 'success', 'a test shard failed, was skipped or was cancelled'
        receipts = [json.loads(path.read_text(encoding='utf-8')) for path in sorted(options.directory.rglob('coverage.json'))]
        result = aggregate(receipts, source_sha=source_sha, run_id=run_id, run_attempt=run_attempt, plan=plan)
    options.output.parent.mkdir(parents=True, exist_ok=True)
    options.output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result if options.operation == 'aggregate' else dict(source_sha=source_sha, shard=data['shard_index'],
          count=data['shard_count'], selected=len(data['selected_nodeids']), completed=len(data['completed_nodeids'])), sort_keys=True))


if __name__ == '__main__':
    main()
