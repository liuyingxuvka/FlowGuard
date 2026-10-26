"""Four-test native shards; fresh process evidence, no cached verdicts."""
from pathlib import Path
import os,time
from _testtree_fixture import runner_fixture

def one_shard(root,case):
    from flowguard.pytest_shards_cli import _run_one_shard
    root=runner_fixture(root)
    if case=='one_fails':(root/'tests/test_one.py').write_text('def test_a(): assert False\ndef test_b(): assert True\n')
    if case=='one_skips':(root/'tests/test_one.py').write_text('import pytest\ndef test_a(): pytest.skip("required")\ndef test_b(): assert True\n')
    nodes=('tests/test_one.py::test_a','tests/test_two.py::test_b')
    environment=dict(os.environ)
    for key in ('FLOWGUARD_PYTEST_COLLECTION_NODEIDS','FLOWGUARD_PYTEST_SHARD_NODEIDS','FLOWGUARD_PYTEST_SHARD_COLLECTION','FLOWGUARD_PYTEST_NODEIDS'):environment.pop(key,None)
    environment['PYTEST_DISABLE_PLUGIN_AUTOLOAD']='1'
    environment['PYTHONDONTWRITEBYTECODE']='1'
    environment['PYTHONPATH']=os.pathsep.join(x for x in (str(root),environment.get('PYTHONPATH','')) if x)
    row,projection=_run_one_shard(root=root,environment=environment,shard_index=0,shard_nodeids=nodes,shard_timeout=20,deadline=time.monotonic()+(-1 if case=='past_deadline' else 30),output_root=root/'.flowguard/cache/one-shard')
    return row,projection,nodes

def suite_cases(root):
    from flowguard.pytest_shards_cli import run,build_parser
    from flowguard.pytest_shards import aggregate_pytest_projections
    root=runner_fixture(root)
    args=build_parser().parse_args(['--root',str(root),'--shards','2'])
    first_code,first=run(args)
    record=root/'.flowguard/cache/test-durations.json'
    first_record=record.exists()
    second_code,second=run(args)
    (root/'tests/test_one.py').write_text('def test_a(): assert False\ndef test_b(): assert True\n')
    fail_code,failed=run(args)
    before=record.read_bytes() if record.exists() else None
    (root/'tests/test_broken.py').write_text('def test_broken(:\n')
    blocked_code,blocked=run(args)
    return dict(first=first,second=second,failed=failed,blocked=blocked,first_code=first_code,second_code=second_code,fail_code=fail_code,blocked_code=blocked_code,recorded=first_record,preserved=before==(record.read_bytes() if record.exists() else None))
