"""The existing project policies survive migration to the shared pytest owner."""
import sys
import textwrap

import pytest

from test_plugin import run


def project(root, files, policy='forbid', collect_only=False):
    text = f'[tool.flowguard]\nskip_policy="{policy}"\n'
    if collect_only:
        text += '[tool.pytest.ini_options]\naddopts="--collect-only"\n'
    (root / 'pyproject.toml').write_text(text)
    for name, source in files.items():
        (root / name).write_text(textwrap.dedent(source))
    return root


def summary(result):
    return result.stdout.strip().splitlines()[-1]


def test_forbid_retains_the_original_worldguard_three_runtime_skip_outcomes(tmp_path):
    root = project(tmp_path, {'test_probe.py': '''
        import pytest
        def test_skipped():
            pytest.skip('the input was not there')
        @pytest.mark.skip(reason='marked')
        def test_marked():
            pass
        @pytest.mark.skipif(True, reason='condition')
        class TestConditional:
            def test_inside(self):
                pass
        def test_fine():
            pass
    '''})
    result = run(root)
    assert result.returncode == 1, result.stdout + result.stderr
    assert summary(result).startswith('1 failed, 1 passed, 2 errors') and 'skipped' not in summary(result)
    for message in ('test_skipped was skipped (the input was not there)',
                    'test_marked was skipped (marked)', 'test_inside was skipped (condition)'):
        assert message in result.stdout


@pytest.mark.parametrize('source', [
    "import pytest\npytest.skip('no input here', allow_module_level=True)\n",
    "import pytest\npytest.importorskip('a_module_that_is_not_installed')\n",
])
def test_forbid_retains_the_original_worldguard_collection_skip_failure(tmp_path, source):
    root = project(tmp_path, {'test_gone.py': source, 'test_other.py': 'def test_fine(): pass\n'})
    result = run(root)
    assert result.returncode != 0 and 'error' in summary(result) and 'skipped' not in summary(result)
    assert 'was skipped while it was collected' in result.stdout


def test_forbid_retains_the_original_worldguard_xfail_and_xpass_failures(tmp_path):
    root = project(tmp_path, {'test_probe.py': '''
        import pytest
        @pytest.mark.xfail(raises=RuntimeError)
        def test_hides_a_fault():
            raise RuntimeError('injected')
        @pytest.mark.xfail(reason='flaky', strict=False)
        def test_passes_anyway():
            pass
        def test_marks_itself():
            pytest.xfail('not now')
    '''})
    result = run(root)
    assert result.returncode == 1, result.stdout + result.stderr
    assert summary(result).startswith('3 failed') and 'xfail' not in summary(result) and 'xpass' not in summary(result)
    for message in ('test_hides_a_fault is marked as expected to fail',
                    'test_passes_anyway is marked as expected to fail (flaky)',
                    'test_marks_itself is marked as expected to fail (not now)'):
        assert message in result.stdout


@pytest.mark.parametrize('teardown', [False, True])
def test_forbid_retains_explicit_exit_zero_as_a_failure(tmp_path, teardown):
    source = '''import pytest
@pytest.fixture(autouse=True)
def cut_short():
    yield
    pytest.exit('stop here', returncode=0)
def test_first():
    pass
''' if teardown else '''import pytest
def test_first():
    pytest.exit('stop here', returncode=0)
def test_second():
    pass
'''
    root = project(tmp_path, {'test_probe.py': source})
    result = run(root)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "the run was ended early by pytest.exit('stop here')" in result.stdout + result.stderr


def test_no_skip_retains_physicsguard_xpass_and_direct_exit_semantics(tmp_path):
    root = project(tmp_path, {'test_probe.py': '''import pytest
@pytest.mark.xfail(reason='not a skip', strict=False)
def test_passes_anyway():
    pass
'''}, policy='no_skip')
    result = run(root)
    assert result.returncode == 0 and '1 xpassed' in summary(result), result.stdout + result.stderr
    (root / 'test_probe.py').write_text("import pytest\ndef test_exit():\n    pytest.exit('explicit stop', returncode=0)\n")
    result = run(root)
    assert result.returncode == 0, result.stdout + result.stderr


def test_no_skip_still_refuses_an_effective_skipif(tmp_path):
    root = project(tmp_path, {'test_probe.py': '''import pytest
@pytest.mark.skipif(True, reason='condition')
def test_cannot_pass_by_skip():
    pass
'''}, policy='no_skip')
    result = run(root)
    assert result.returncode == 1 and 'ended skipped' in result.stdout


def test_forbid_partial_selection_and_collection_query_do_not_require_unselected_tests(tmp_path):
    root = project(tmp_path, {'test_probe.py': 'def test_first(): pass\ndef test_second(): pass\n'})
    assert run(root, '-k', 'test_first').returncode == 0
    assert run(root, '--collect-only').returncode == 0


@pytest.mark.parametrize('teardown', [False, True])
def test_recording_a_complete_check_refuses_exit_zero_for_the_default_policy(tmp_path, teardown):
    source = '''import pytest
@pytest.fixture(autouse=True)
def stop():
    yield
    pytest.exit('stop here', returncode=0)
def test_fine(): pass
''' if teardown else "import pytest\ndef test_exit():\n    pytest.exit('stop here', returncode=0)\n"
    root = project(tmp_path, {'test_probe.py': source}, policy='platform')
    result = run(root, '--flowguard-record-tests')
    assert result.returncode == 1 and 'FlowGuard: ' in result.stdout + result.stderr


def test_check_all_does_not_accept_collect_only_as_an_unmodeled_project_validation(tmp_path):
    from flowguard.intent.cli import main
    root = project(tmp_path, {'test_probe.py': 'def test_fine(): pass\n'}, policy='platform', collect_only=True)
    assert main(['--root', str(root), 'check', '--all']) == 1
    output = (root / '.flowguard/cache/check-output.txt').read_text()
    assert 'FlowGuard: ' in output and 'collected test(s) never ran' in output


@pytest.mark.parametrize('statement', [
    'os._exit(0)',
    'importlib.import_module(os.name)._exit(0)',
    'os.execv(sys.executable, [sys.executable, "-c", "pass"])',
])
@pytest.mark.parametrize('complete', [False, True])
def test_main_process_hard_exit_and_exec_cannot_turn_a_failure_into_success(tmp_path, statement, complete):
    root = project(tmp_path, {'test_probe.py': f'''import os,sys,importlib
def test_first():
    assert False
def test_replace_process():
    {statement}
'''}, policy='platform' if complete else 'forbid')
    result = run(root, *(['--flowguard-record-tests'] if complete else []))
    assert result.returncode != 0, result.stdout + result.stderr
    assert 'would end or replace the test process' in result.stdout + result.stderr


def test_a_caught_hard_exit_refusal_is_still_not_a_passing_run(tmp_path):
    root = project(tmp_path, {'test_probe.py': '''import os
def test_caught():
    try:
        os._exit(0)
    except BaseException:
        pass
'''})
    result = run(root)
    assert result.returncode == 1, result.stdout + result.stderr
    assert 'os._exit() would end or replace the test process' in result.stdout + result.stderr


def test_resetting_pytests_failure_counter_does_not_erase_actual_failed_reports(tmp_path):
    root = project(tmp_path, {'test_probe.py': '''def test_first():
    assert False
def test_reset(request):
    request.session.testsfailed = 0
'''})
    result = run(root)
    assert result.returncode == 1 and 'test(s) failed' in result.stdout + result.stderr


@pytest.mark.parametrize('policy', ['platform', 'no_skip'])
def test_plain_non_strict_hard_exit_keeps_its_existing_semantics(tmp_path, policy):
    root = project(tmp_path, {'test_probe.py': 'import os\ndef test_exit():\n    os._exit(0)\n'}, policy=policy)
    assert run(root).returncode == 0


@pytest.mark.skipif(sys.platform == 'win32', reason='fork cleanup exists only on fork platforms')
def test_fork_child_may_use_normal_hard_exit_cleanup(tmp_path):
    root = project(tmp_path, {'test_probe.py': '''import os
def test_child():
    pid = os.fork()
    if pid == 0:
        os._exit(0)
    waited, status = os.waitpid(pid, 0)
    assert waited == pid and os.waitstatus_to_exitcode(status) == 0
'''})
    result = run(root)
    assert result.returncode == 0, result.stdout + result.stderr


def test_multiprocessing_child_may_finish_normally(tmp_path):
    root = project(tmp_path, {'test_probe.py': '''import multiprocessing
def child():
    pass
def test_child():
    process = multiprocessing.get_context('spawn').Process(target=child)
    process.start()
    process.join(10)
    assert process.exitcode == 0
'''})
    result = run(root)
    assert result.returncode == 0, result.stdout + result.stderr
