"""The vitest execution side: ecma facts it shares with check --static, the plan, init wiring, and real vitest runs.

The real runs need node and npm (GitHub runners have both): a session installs vitest into a temporary folder.
If either is missing or the install fails, the test fails with the reason; nothing is skipped.
"""
import json
import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from tests.intent_engine import _cli_fixture
from tests.intent_engine._cli_fixture import SOURCE, display_text

VITEST = '4.1.11'


def _git(root, *arguments):
    return subprocess.run(['git', '-C', str(root), *arguments], check=True, capture_output=True, text=True, timeout=30).stdout


def _write(root, files):
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(text).lstrip(), encoding='utf-8', newline='\n')


def _commit(root, files=(), message='fixture baseline'):
    _write(root, {'.gitignore': '.flowguard/cache/\n__pycache__/\n.pytest_cache/\nnode_modules/\naudit.log\n', **dict(files)})
    if not (root / '.git').exists():
        _git(root, 'init', '-q', '-b', 'main')
        _git(root, 'config', 'core.autocrlf', 'false')
    _git(root, 'add', '.')
    _git(root, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', message)
    return root


def _flowguard(root, *arguments):
    result = subprocess.run([sys.executable, '-c', _cli_fixture._BOOT, SOURCE, 'unused-marker', '', '--root', str(root), *arguments],
                            cwd=root, capture_output=True, encoding='utf-8', timeout=180,
                            env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8'))
    return result.returncode, display_text(result)


def _environment():
    return dict(os.environ, FLOWGUARD_PYTHON=sys.executable, PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1',
                PYTHONPATH=SOURCE + os.pathsep + os.environ.get('PYTHONPATH', ''))


def _prepare(root):
    run = subprocess.run([sys.executable, '-m', 'flowguard.intent.vitest', 'prepare', '--root', str(root)], cwd=root,
                         capture_output=True, encoding='utf-8', timeout=180, env=_environment())
    assert run.returncode == 0, run.stdout + run.stderr
    return json.loads(run.stdout.strip().splitlines()[-1])


FEES = {
    'src/fees/limits.ts': '''
        export const FREE_DAYS = 3;
        export const BASE_CHARGE = 5;
    ''',
    'src/fees/late-fee.ts': '''
        import { BASE_CHARGE, FREE_DAYS } from './limits';

        export function lateFee(days: number, member: boolean): number {
          if (days > FREE_DAYS) {
            return BASE_CHARGE + (days - FREE_DAYS) * (member ? 1 : 2);
          }
          return 0;
        }
    ''',
    'src/preview/fee-preview.ts': '''
        // The checkout preview's own copy of the same judgment.
        export const lateFee = (days: number, member: boolean): number =>
          days > 3 ? 5 + (days - 3) * 2 : 0;
    ''',
    'src/effects/audited.ts': '''
        import { appendFileSync } from 'node:fs';

        export function auditedFee(days: number): number {
          appendFileSync(new URL('../../audit.log', import.meta.url), `fee ${days}\\n`);
          return days > 3 ? days * 2 : 0;
        }

        const prisma = { employee: { count: (limit: number) => Math.min(limit, 7) } };

        export function activeCount(limit: number): number {
          return limit > 0 ? prisma.employee.count(limit) : 0;
        }
    ''',
    'tests/fees.test.ts': '''
        import { expect, it } from 'vitest';
        import { lateFee } from '../src/fees/late-fee';
        import { lateFee as previewFee } from '../src/preview/fee-preview';
        import { activeCount, auditedFee } from '../src/effects/audited';

        it('charges a base fee after the free days', () => {
          expect(lateFee(5, false)).toBe(9);
          expect(lateFee(2, true)).toBe(0);
          expect(previewFee(6, false)).toBe(11);
        });

        it('audits a fee and counts', () => {
          expect(auditedFee(4)).toBe(8);
          expect(activeCount(3)).toBe(3);
        });
    ''',
    'tests/intent/fee_rules.py': '''
        from flowguard.intent import rule


        @rule("FEE_WINDOW", decides="late fee", fields={"days": int, "member": bool},
              source="assumed: three free days, then 5 plus 1 a day for members and 2 a day for others",
              anchor="LATE_FEE")
        def FEE_WINDOW(days, member):
            if days <= 3:
                return 0
            return 5 + (days - 3) * (1 if member else 2)
    ''',
}


def _sensor(root, file, before, name):
    path = root / file
    text = path.read_text(encoding='utf-8')
    path.write_text(text.replace(before, f'// flowguard: sensor {name}\n' + before, 1), encoding='utf-8', newline='\n')


# ---- ecma facts shared by check --static and the execution side --------------------------------------

def test_comparisons_with_constant_names_and_table_lookups_fold_through_imports(tmp_path):
    from contextlib import closing
    from flowguard.intent.anchors import collect
    from flowguard.structure import build
    _write(tmp_path, {
        'src/limits.ts': '''
            export const FREE_DAYS = 3;
            export const LABELS = { ACTIVE: 'Active', RETIRED: 'Retired' } as const;
        ''',
        'src/fee.ts': '''
            import { FREE_DAYS, LABELS } from './limits';
            const MAX = 10;
            const Kind = { A: 'a', B: 'b' };

            // flowguard: sensor FEE
            export function fee(days: number, kind: string): number {
              if (days > FREE_DAYS && days <= MAX) return 1;
              if (kind === Kind.A) return 2;
              return 0;
            }

            // flowguard: sensor LABEL
            export const label = (status: string) => LABELS[status] ?? 'x';

            // flowguard: sensor
            export function broken() {}
        ''',
    })
    with closing(build(tmp_path)) as graph:
        numbers = {(row['function'], row['value'], row.get('name')) for row in graph.numbers()}
        strings = {(row['function'], row['value'], row.get('name')) for row in graph.literals(contexts={'compare'})}
        keys = [(row['function'], row['name'], row['keys']) for row in graph.lookup_keys()]
        index = collect(graph)
    assert {('fee', 3, 'FREE_DAYS'), ('fee', 10, 'MAX')} <= numbers, numbers
    assert ('fee', 'a', 'Kind.A') in strings, strings
    assert keys == [('label', 'LABELS', ['ACTIVE', 'RETIRED'])], keys
    sensors = [(a.name, a.qual, a.line, a.target_line, [p.name for p in a.parameters]) for a in index.entries if a.kind == 'sensor']
    assert sensors == [('FEE', 'fee', 5, 6, ['days', 'kind']), ('LABEL', 'label', 12, 13, ['status'])], sensors
    assert [issue.message for issue in index.issues] == ['src/fee.ts:15: sensor needs one NAME: // flowguard: sensor NAME']


def test_check_static_old_value_lead_reads_the_folded_constant_names_too(tmp_path):
    _commit(tmp_path, {
        'src/limits.ts': 'export const LIMIT = 100;\n',
        'src/a.ts': 'export function over(x: number): boolean {\n  return x > 100;\n}\n',
        'src/b.ts': "import { LIMIT } from './limits';\n\nexport function full(y: number): boolean {\n  return y >= LIMIT;\n}\n",
    })
    (tmp_path / 'src/a.ts').write_text('export function over(x: number): boolean {\n  return x > 105;\n}\n', encoding='utf-8')
    code, text = _flowguard(tmp_path, 'check', '--static')
    assert code == 0 and '线索：旧值 100 还出现在 1 个判断里：src/b.ts:4' in text, text


# ---- the plan ----------------------------------------------------------------------------------------

def test_prepare_is_off_without_a_ts_change_and_plans_anchored_and_changed_functions(tmp_path):
    _commit(tmp_path, {
        **{name: text for name, text in FEES.items() if name.startswith('src/')},
        'src/colors.ts': '''
            export const LOW = 30;
            export const FULL = 100;
            const LABELS: Record<string, string> = { TEAM: 'Team', AREA: 'Area' };

            export function band(percent: number): string {
              if (percent > FULL) return 'over';
              return percent > LOW ? 'ok' : 'low';
            }

            export function typeLabel(type: string): string {
              return LABELS[type] ?? type;
            }

            export class Grid {
              cell(value: number) { return value > LOW; }
            }
        ''',
    })
    assert _prepare(tmp_path) == {'status': 'off', 'reason': '相对基准没有 TS/JS 改动：执行侧不准备'}
    _sensor(tmp_path, 'src/fees/late-fee.ts', 'export function lateFee', 'LATE_FEE')
    _sensor(tmp_path, 'src/preview/fee-preview.ts', 'export const lateFee', 'LATE_FEE')
    _sensor(tmp_path, 'src/colors.ts', '  cell(value', 'CELL')
    colors = tmp_path / 'src/colors.ts'
    colors.write_text(colors.read_text(encoding='utf-8').replace("'low'", "'under'").replace("?? type", "?? '-'"), encoding='utf-8')
    answer = _prepare(tmp_path)
    assert answer['status'] == 'on' and answer['adapter'].endswith('flowguard/adapters/vitest/index.mjs'), answer
    plan = json.loads(Path(answer['plan']).read_text(encoding='utf-8'))
    points = {point['id']: point for entry in plan['files'].values() for point in entry['points']}
    assert set(points) == {'typescript/src/fees/late-fee.ts:lateFee', 'typescript/src/preview/fee-preview.ts:lateFee',
                           'typescript/src/colors.ts:band', 'typescript/src/colors.ts:typeLabel'}, points
    band, label = points['typescript/src/colors.ts:band'], points['typescript/src/colors.ts:typeLabel']
    assert not band['anchored'] and band['name'] == 'band' and band['bounds'] == [30, 100], band
    assert {29, 30, 31, 29.99, 30.01, 99.99, 100, 100.01, 101} <= {value for value in band['numbers'] if not isinstance(value, dict)}
    assert label['strings'] == ['AREA', 'TEAM', '<other>'], label
    fee, preview = points['typescript/src/fees/late-fee.ts:lateFee'], points['typescript/src/preview/fee-preview.ts:lateFee']
    assert fee['anchored'] and fee['params'] == ['days', 'member'] and fee['form'] == 'function', fee
    assert preview['form'] == 'const' and preview['line'] == 3 and [copy['id'] for copy in preview['copies']] == [fee['id']], preview
    assert {'$num': 'NaN'} in fee['numbers'] and -2.5 in fee['numbers'], fee['numbers']     # copies add the representatives
    assert [item['name'] for item in plan['unplanned']] == ['CELL'], plan['unplanned']
    assert [item['file'].endswith('src/colors.ts') for item in plan['baselines']].count(True) == 1
    stamp = Path(answer['plan']).stat().st_mtime_ns
    assert _prepare(tmp_path) == answer and Path(answer['plan']).stat().st_mtime_ns == stamp   # the cached plan


def test_a_function_reading_a_changed_constant_or_table_is_planned_as_changed(tmp_path):
    _commit(tmp_path, {
        'src/limits.ts': "export const LIMIT = 3;\nexport const LABELS = { TEAM: 'Team', AREA: 'Area' };\n",
        'src/use.ts': "import { LIMIT as MAX, LABELS } from './limits';\n\nexport function over(days: number): boolean {\n"
                      "  return days > MAX;\n}\n\nexport const label = (type: string) => LABELS[type] ?? type;\n\n"
                      "export function same(days: number): number {\n  return days;\n}\n",
    })
    limits = tmp_path / 'src/limits.ts'
    limits.write_text(limits.read_text(encoding='utf-8').replace("AREA: 'Area'", "AREA: 'Areas'"), encoding='utf-8')
    plan = json.loads(Path(_prepare(tmp_path)['plan']).read_text(encoding='utf-8'))
    assert sorted(point['fn'] for entry in plan['files'].values() for point in entry['points']) == ['label'], plan['files']
    limits.write_text("export const LIMIT = 4;\nexport const LABELS = { TEAM: 'Team', AREA: 'Area' };\n", encoding='utf-8')
    plan = json.loads(Path(_prepare(tmp_path)['plan']).read_text(encoding='utf-8'))
    [point] = [point for entry in plan['files'].values() for point in entry['points']]
    assert (point['fn'], point['bounds']) == ('over', [4]), point     # the folded value of the changed constant


def test_a_function_that_names_a_database_client_is_planned_but_never_replayed(tmp_path):
    _commit(tmp_path, {'src/effects/audited.ts': FEES['src/effects/audited.ts']})
    _sensor(tmp_path, 'src/effects/audited.ts', 'export function activeCount', 'ACTIVE_COUNT')
    plan = json.loads(Path(_prepare(tmp_path)['plan']).read_text(encoding='utf-8'))
    [point] = [point for entry in plan['files'].values() for point in entry['points']]
    assert point['skip'] == '看不清：函数里用到数据库客户端，不回放', point


# ---- init ---------------------------------------------------------------------------------------------

def test_init_wires_the_vitest_config_readably_and_says_jest_is_static_only(tmp_path):
    vitest = '{"name": "web", "type": "module", "scripts": {"test": "vitest run"}, "devDependencies": {"vitest": "4.1.11"}}\n'
    _commit(tmp_path, {
        'web/package.json': vitest,
        'web/vitest.config.ts': "import react from '@vitejs/plugin-react';\nimport { defineConfig } from 'vitest/config';\n\n"
                                "export default defineConfig({\n  plugins: [react()],\n  test: { environment: 'jsdom' },\n});\n",
        'api/package.json': vitest.replace('web', 'api'),
        'api/vitest.config.ts': "import { defineConfig } from 'vitest/config';\n\nexport default defineConfig({\n  test: {},\n});\n",
        'cjs/package.json': vitest.replace('web', 'cjs'),
        'cjs/vitest.config.cjs': "module.exports = { test: {} };\n",
        'job/package.json': '{"name": "job", "scripts": {"test": "jest"}, "devDependencies": {"jest": "29.7.0"}}\n',
    })
    code, text = _flowguard(tmp_path, 'init')
    assert code == 0, text
    web = (tmp_path / 'web/vitest.config.ts').read_text(encoding='utf-8')
    assert "import flowguard from './flowguard.vitest.mjs'; // flowguard: vitest" in web, web
    assert 'plugins: [flowguard() /* flowguard: vitest */, react()]' in web, web
    api = (tmp_path / 'api/vitest.config.ts').read_text(encoding='utf-8')
    assert 'export default defineConfig({\n  plugins: [flowguard()], // flowguard: vitest\n  test: {},' in api, api
    assert "Wired FlowGuard's execution side into web/vitest.config.ts through web/flowguard.vitest.mjs" in text, text
    assert 'cjs/vitest.config.cjs is CommonJS and the execution side supports ESM configs only' in text, text
    assert (tmp_path / 'cjs/vitest.config.cjs').read_text(encoding='utf-8') == "module.exports = { test: {} };\n"
    assert 'The execution side supports vitest only: this jest project runs check --static alone.' in text, text
    assert not (tmp_path / 'job/flowguard.vitest.mjs').exists()
    generated = (tmp_path / 'web/flowguard.vitest.mjs').read_text(encoding='utf-8')
    # No machine path in a committed file: the interpreter that ran init is read from the git-ignored cache.
    assert "'-m', 'flowguard.intent.vitest', 'prepare'" in generated and sys.executable not in generated
    assert '".flowguard/cache/python"' in generated and sys.executable not in (tmp_path / 'web/flowguard.static.test.mjs').read_text(encoding='utf-8')
    assert (tmp_path / '.flowguard/cache/python').read_text(encoding='utf-8') == sys.executable
    code, again = _flowguard(tmp_path, 'init')
    assert code == 0 and 'web/vitest.config.ts already lists flowguard().' in again, again
    assert (tmp_path / 'web/vitest.config.ts').read_text(encoding='utf-8') == web          # run twice, wired once
    undone = '\n'.join(line for line in web.splitlines() if 'flowguard: vitest' not in line or 'plugins' in line)
    assert undone.replace('flowguard() /* flowguard: vitest */, ', '') + '\n' == \
        "import react from '@vitejs/plugin-react';\nimport { defineConfig } from 'vitest/config';\n\n" \
        "export default defineConfig({\n  plugins: [react()],\n  test: { environment: 'jsdom' },\n});\n"


def test_init_adds_its_test_to_suite_scripts_on_named_folders_and_skips_a_package_without_a_runner(tmp_path):
    package = ('{\n  "name": "api",\n  "type": "module",\n  "scripts": {\n    "test": "vitest run",\n'
               '    "test:unit": "prisma generate && vitest run tests/unit --reporter=dot",\n'
               '    "test:one": "vitest run tests/unit/a.test.ts",\n    "check:schema": "vitest run tests/unit"\n  },\n'
               '  "devDependencies": {\n    "vitest": "4.1.11"\n  }\n}\n')
    _commit(tmp_path, {'api/package.json': package, 'api/tests/unit/a.test.ts': "import { it } from 'vitest';\nit('a', () => {});\n",
                       'lib/package.json': '{"name": "lib", "scripts": {"build": "tsc"}, "devDependencies": {"typescript": "5.6.0"}}\n'})
    code, text = _flowguard(tmp_path, 'init')
    assert code == 0, text
    after = package.replace('vitest run tests/unit --reporter=dot', 'vitest run tests/unit --reporter=dot flowguard.static.test.mjs')
    assert (tmp_path / 'api/package.json').read_text(encoding='utf-8') == after       # its own formatting kept
    assert ('api/package.json script "test:unit" runs vitest on named paths only; init added flowguard.static.test.mjs: '
            'prisma generate && vitest run tests/unit --reporter=dot flowguard.static.test.mjs') in text, text
    assert not (tmp_path / 'lib/flowguard.static.test.mjs').exists()
    assert 'lib/package.json names no test runner (vitest or jest in its dependencies or scripts): no FlowGuard test' in text, text
    code, again = _flowguard(tmp_path, 'init')
    assert code == 0 and (tmp_path / 'api/package.json').read_text(encoding='utf-8') == after and 'init added' not in again, again


def test_init_wires_one_unit_suite_script_and_never_an_integration_suite(tmp_path):
    # Planning Tool 0.6.28 (round 22): test:unit already ran the static test, and init added it to
    # test:integration too, the suite that writes real databases and no agent may run.
    scripts = ('"test": "vitest run", "test:integration": "vitest run tests/integration", '
               '"test:e2e": "vitest run tests/e2e", "test:api": "vitest run tests/api", "test:unit": "vitest run tests/unit"')
    package = '{"name": "api", "scripts": {' + scripts + '}, "devDependencies": {"vitest": "4.1.11"}}\n'
    files = {'api/package.json': package}
    files.update({f'api/tests/{folder}/a.test.ts': "import { it } from 'vitest';\nit('a', () => {});\n"
                  for folder in ('unit', 'integration', 'e2e', 'api')})
    _commit(tmp_path, files)
    code, text = _flowguard(tmp_path, 'init')
    assert code == 0 and text.count('init added') == 1, text
    after = package.replace('"vitest run tests/unit"', '"vitest run tests/unit flowguard.static.test.mjs"')
    assert (tmp_path / 'api/package.json').read_text(encoding='utf-8') == after, text       # the unit suite, once
    # the static test already in one suite: init adds it nowhere else, also with only integration suites left
    wired = package.replace('"vitest run tests/integration"', '"vitest run tests/integration flowguard.static.test.mjs"')
    for start in (wired.replace(', "test:unit": "vitest run tests/unit"', '').replace(', "test:api": "vitest run tests/api"', ''),
                  package.replace(', "test:unit": "vitest run tests/unit"', '').replace(', "test:api": "vitest run tests/api"', '')):
        (tmp_path / 'api/package.json').write_text(start, encoding='utf-8')
        code, text = _flowguard(tmp_path, 'init')
        assert code == 0 and 'init added' not in text and (tmp_path / 'api/package.json').read_text(encoding='utf-8') == start, text


# ---- real vitest -----------------------------------------------------------------------------------

def _tool(name):
    found = shutil.which(name)
    assert found, f'{name} is required for the vitest adapter tests (GitHub runners and this machine have it)'
    return found


@pytest.fixture(scope='session')
def vitest_home(tmp_path_factory):
    """A folder with vitest installed; the test projects live in its subfolders and resolve it from there."""
    home = tmp_path_factory.mktemp('vitest-home')
    (home / 'package.json').write_text('{"name": "flowguard-vitest-tests", "private": true, "type": "module"}\n', encoding='utf-8')
    run = subprocess.run([_tool('npm'), 'install', '--no-audit', '--no-fund', '--legacy-peer-deps', f'vitest@{VITEST}'],
                         cwd=home, capture_output=True, encoding='utf-8', timeout=600)
    assert run.returncode == 0 and (home / 'node_modules/vitest/vitest.mjs').is_file(), \
        f'npm could not install vitest@{VITEST} for the adapter tests:\n{run.stdout}\n{run.stderr}'
    return home


def _vitest(project, home):
    run = subprocess.run([_tool('node'), str(home / 'node_modules/vitest/vitest.mjs'), 'run'], cwd=project,
                         capture_output=True, encoding='utf-8', timeout=600, env=_environment())
    return run.returncode, display_text(run.stdout + run.stderr)


def _fees_project(home, name):
    root = home / name
    _commit(root, {'package.json': '{"name": "fees", "private": true, "type": "module", "scripts": {"test": "vitest run"}, '
                                   '"devDependencies": {"vitest": "' + VITEST + '"}}\n', **FEES})
    code, text = _flowguard(root, 'init')
    assert code == 0 and 'Generated flowguard.vitest.mjs and vitest.config.mjs' in text, text
    _commit(root, message='flowguard init')
    return root


def test_vitest_reports_copies_rules_and_the_changed_case_class(vitest_home):
    root = _fees_project(vitest_home, 'fees')
    code, text = _vitest(root, vitest_home)
    assert code == 0 and 'FlowGuard check --static' not in text.split('Test Files')[-1], text  # no change: nothing added
    assert '变：' not in text and '同名锚点' not in text, text
    _sensor(root, 'src/fees/late-fee.ts', 'export function lateFee', 'LATE_FEE')
    _sensor(root, 'src/preview/fee-preview.ts', 'export const lateFee', 'LATE_FEE')
    code, text = _vitest(root, vitest_home)
    assert code == 1, text
    # the smallest differing input, as the pytest side picks it; the copies differ for members after day 3
    assert '红：同名锚点 LATE_FEE：days=3.01, member=T，5.01 ≠ 5.02（src/fees/late-fee.ts:4 lateFee ≠ src/preview/fee-preview.ts:3 lateFee）' in text, text
    assert '红：FEE_WINDOW: days=6 member=T -> rule 8, code 11（src/preview/fee-preview.ts:3 lateFee）' in text, text
    assert 'FEE_WINDOW 出处：assumed: three free days, then 5 plus 1 a day for members and 2 a day for others' in text, text
    _commit(root, message='sensors')
    late = root / 'src/fees/late-fee.ts'
    late.write_text(late.read_text(encoding='utf-8').replace('days > FREE_DAYS', 'days >= FREE_DAYS'), encoding='utf-8')
    code, text = _vitest(root, vitest_home)
    assert code == 1, text
    assert '变：LATE_FEE（src/fees/late-fee.ts:4）已比较 12 类（划分未完成），变 2 类：days=3，member=F 等 2 类；函数返回值 0 → 5' in text, text
    assert '红：FEE_WINDOW: days=3 member=F -> rule 0, code 5（src/fees/late-fee.ts:4 lateFee）' in text, text
    # the unchanged copy compared on every replayed class prints nothing of its own
    assert not [line for line in text.splitlines() if line.startswith('未验证') and 'fee-preview.ts' in line], text


def test_a_disagreeing_same_name_pair_is_compared_again_in_a_run_without_a_ts_change(vitest_home):
    root = _fees_project(vitest_home, 'again')
    _sensor(root, 'src/fees/late-fee.ts', 'export function lateFee', 'LATE_FEE')
    _sensor(root, 'src/preview/fee-preview.ts', 'export const lateFee', 'LATE_FEE')
    code, text = _vitest(root, vitest_home)
    red = '红：同名锚点 LATE_FEE：days=3.01, member=T，5.01 ≠ 5.02'
    assert code == 1 and red in text, text
    _commit(root, message='sensors')            # nothing changed against the baseline any more
    code, text = _vitest(root, vitest_home)
    assert code == 1 and red in text, text      # the registered copies still disagree: still red
    preview = root / 'src/preview/fee-preview.ts'
    preview.write_text(preview.read_text(encoding='utf-8').replace('(days - 3) * 2', '(days - 3) * (member ? 1 : 2)'),
                       encoding='utf-8', newline='\n')
    _commit(root, message='the copies agree')
    code, text = _vitest(root, vitest_home)
    assert code == 0 and '同名锚点' not in text, text
    assert _prepare(root) == {'status': 'off', 'reason': '相对基准没有 TS/JS 改动：执行侧不准备'}   # compared, agreed: cleared


ISO_WEEK = '''
    function isoWeek(date: Date): number {
      const day = date.getUTCDay() || 7;
      const thursday = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate() + 4 - day));
      const start = Date.UTC(thursday.getUTCFullYear(), 0, 1);
      return Math.ceil(((thursday.getTime() - start) / 86400000 + 1) / 7);
    }
'''


def test_a_same_name_red_names_an_input_next_to_the_one_the_test_used_and_fails_a_test_case(vitest_home):
    root = vitest_home / 'weeks'
    _commit(root, {
        'package.json': '{"name": "weeks", "private": true, "type": "module", "scripts": {"test": "vitest run"}, '
                        '"devDependencies": {"vitest": "' + VITEST + '"}}\n',
        'src/chart.ts': ISO_WEEK + '''
            // flowguard: sensor ISO_WEEKS_IN_YEAR
            export function weeksInYear(year: number): number {
              return isoWeek(new Date(Date.UTC(year, 11, 28)));
            }
        ''',
        'src/calendar.ts': ISO_WEEK + '''
            // flowguard: sensor ISO_WEEKS_IN_YEAR
            export function weekCount(year: number): number {
              return isoWeek(new Date(Date.UTC(year, 11, 31)));
            }
        ''',
        'tests/chart.test.ts': '''
            import { expect, it } from 'vitest';
            import { weeksInYear } from '../src/chart';

            it('counts the weeks of this year', () => {
              expect(weeksInYear(2026)).toBe(53);
            });
        ''',
    })
    code, text = _flowguard(root, 'init')
    assert code == 0, text
    run = subprocess.run([_tool('node'), str(vitest_home / 'node_modules/vitest/vitest.mjs'), 'run', '--reporter=default',
                          '--reporter=json', '--outputFile.json=results.json'], cwd=root, capture_output=True, encoding='utf-8',
                         timeout=600, env=_environment())
    text = display_text(run.stdout + run.stderr)
    # 2025 is next to the 2026 the test used (2026 itself agrees: both count 53); year=0 would be read as 1900
    red = '红：同名锚点 ISO_WEEKS_IN_YEAR：year=2025，52 ≠ 1（src/chart.ts:9 weeksInYear ≠ src/calendar.ts:9 weekCount）'
    assert run.returncode == 1 and red in text, text
    results = json.loads((root / 'results.json').read_text(encoding='utf-8'))
    cases = {case['title']: case for result in results['testResults'] for case in result['assertionResults']}
    assert cases['counts the weeks of this year']['status'] == 'passed', cases
    session = cases['FlowGuard execution side']             # the red is a failed test case in vitest's own results
    assert session['status'] == 'failed' and red.removeprefix('红：') in display_text(''.join(session['failureMessages'])), session
    assert red in text.split('Test Files')[-1], text          # the block still follows the summary
    run = subprocess.run([_tool('node'), str(vitest_home / 'node_modules/vitest/vitest.mjs'), 'run', 'tests'], cwd=root,
                         capture_output=True, encoding='utf-8', timeout=600, env=_environment())
    text = display_text(run.stdout + run.stderr)            # a path filter leaves the session test out:
    assert run.returncode == 1 and red in text and 'FlowGuard execution side' not in text, text   # the teardown judges


def test_a_run_lists_only_its_own_packages_unreached_points_one_per_place(vitest_home):
    root = vitest_home / 'mono'
    _commit(root, {
        'web/package.json': '{"name": "web", "private": true, "type": "module", "scripts": {"test": "vitest run"}, '
                            '"devDependencies": {"vitest": "' + VITEST + '"}}\n',
        'web/src/a.ts': '// flowguard: sensor A_LIMIT\nexport function over(x: number): boolean {\n  return x > 3;\n}\n',
        'web/src/b.ts': '// flowguard: sensor B_LIMIT\nexport function under(x: number): boolean {\n  return x < 3;\n}\n',
        'web/src/c.ts': '// flowguard: sensor B_LIMIT\nexport function below(x: number): boolean {\n  return x < 3;\n}\n',
        'web/tests/a.test.ts': "import { expect, it } from 'vitest';\nimport { over } from '../src/a';\n\n"
                               "it('over', () => { expect(over(4)).toBe(true); });\n",
        'api/package.json': '{"name": "api", "private": true, "type": "module", "scripts": {"build": "tsc"}}\n',
        'api/src/d.ts': '// flowguard: sensor API_LIMIT\nexport function limit(x: number): boolean {\n  return x > 9;\n}\n',
    })
    code, text = _flowguard(root, 'init')
    assert code == 0, text
    code, text = _vitest(root / 'web', vitest_home)
    assert code == 0, text
    unverified = [line for line in text.splitlines() if line.startswith('未验证')]
    assert unverified[0].startswith('未验证 2 项（不是通过）'), unverified                   # two places, two items
    assert '未验证：B_LIMIT（web/src/b.ts:2）：没有测试走到' in unverified and '未验证：B_LIMIT（web/src/c.ts:2）：没有测试走到' in unverified
    assert 'API_LIMIT' not in text and 'api/src' not in text, text      # no web test can reach the api package


def test_a_replay_refuses_writes_and_database_clients_and_the_real_call_still_runs(vitest_home):
    root = _fees_project(vitest_home, 'effects')
    _sensor(root, 'src/effects/audited.ts', 'export function auditedFee', 'AUDITED_FEE')
    _sensor(root, 'src/effects/audited.ts', 'export function activeCount', 'ACTIVE_COUNT')
    code, text = _vitest(root, vitest_home)
    assert code == 0, text
    assert (root / 'audit.log').read_text(encoding='utf-8') == 'fee 4\n'         # only the test's own call wrote
    assert '未验证 2 项（不是通过）' in text, text
    assert '未验证：AUDITED_FEE：看不清：回放中碰到 fs.appendFileSync，回放作废' in text, text
    assert '未验证：ACTIVE_COUNT：看不清：函数里用到数据库客户端，不回放' in text, text


def test_the_adapter_spells_windows_and_vite_ids_as_one_file(tmp_path):
    adapter = Path(SOURCE) / 'flowguard/adapters/vitest/index.mjs'
    script = ("import { normalize } from " + json.dumps(adapter.as_uri()) + ";\n"
              "console.log(JSON.stringify([normalize('C:\\\\Users\\\\Ann\\\\src\\\\a.ts', true), normalize('/C:/Users/Ann/src/a.ts?v=1', true),"
              " normalize('/@fs/C:/Users/Ann/src/a.ts', true), normalize('c:/users/ann/src/a.ts', true),"
              " normalize('/home/ann/src/a.ts?flowguard-baseline', false)]));\n")
    (tmp_path / 'probe.mjs').write_text(script, encoding='utf-8')
    run = subprocess.run([_tool('node'), str(tmp_path / 'probe.mjs')], capture_output=True, encoding='utf-8', timeout=60)
    assert run.returncode == 0, run.stdout + run.stderr
    assert json.loads(run.stdout) == ['c:/users/ann/src/a.ts'] * 4 + ['/home/ann/src/a.ts'], run.stdout
