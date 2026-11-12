"""The vitest execution side: ecma facts it shares with check --static, the plan, init wiring, and real vitest runs.

The real runs need node and npm (GitHub runners have both): a session installs vitest into a temporary folder.
If either is missing or the install fails, the test fails with the reason; nothing is skipped.
"""
import json
import os
import re
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
        const BASE_CHARGE = 5, FREE_DAYS = 3;

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
    assert code == 0 and 'lead: old values 100 remain in 1 decisions: src/b.ts:4' in text, text


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
    answer = _prepare(tmp_path)
    assert answer['status'] == 'off' and answer['reason'] == 'no functions to observe in this change (anchors or changed module-level functions)'
    assert answer['seconds'] >= 0
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
    assert band['numbers'] == [30, 100]  # neighbours are made only from calls recorded by the tests
    assert 'const LOW = 30' in band['source'] and 'const FULL = 100' in band['source']
    assert label['strings'] == ['AREA', 'TEAM', '<other>'], label
    fee, preview = points['typescript/src/fees/late-fee.ts:lateFee'], points['typescript/src/preview/fee-preview.ts:lateFee']
    assert fee['anchored'] and fee['params'] == ['days', 'member'] and fee['form'] == 'function', fee
    assert preview['form'] == 'const' and preview['line'] == 3 and [copy['id'] for copy in preview['copies']] == [fee['id']], preview
    assert fee['numbers'] == [0, 1, 2, 3, 5]  # JSON numbers and source constants, no synthetic NaN/grid
    assert 'const FREE_DAYS = 3' in fee['source'] and not fee['skip']
    assert [item['name'] for item in plan['unplanned']] == ['CELL'], plan['unplanned']
    assert 'old_source' in band and 'old_source' in label
    assert 'baselines' not in plan and 'copy_files' not in plan  # no executable project-module imports
    frozen = json.loads(Path(answer['plan']).read_text())
    frozen.pop('prepare_seconds')
    again = _prepare(tmp_path)
    current = json.loads(Path(answer['plan']).read_text())
    assert again['plan'] == answer['plan'] and again['seconds'] == current.pop('prepare_seconds')
    assert current == frozen  # source plan is cached; timing belongs to this invocation


def test_the_plan_says_head_until_a_task_baseline_is_recorded(tmp_path):
    _commit(tmp_path, {'src/limits.ts': 'export function limit(days: number) { return days <= 3; }\n'})
    head = _git(tmp_path, 'rev-parse', 'HEAD').strip()
    (tmp_path / 'src/limits.ts').write_text('export function limit(days: number) { return days <= 4; }\n', encoding='utf-8')
    answer = _prepare(tmp_path)
    plan = json.loads(Path(answer['plan']).read_text(encoding='utf-8'))
    assert (plan['baseline'], plan['baseline_kind']) == (head, 'HEAD'), plan     # nothing recorded: HEAD stands in
    code, text = _flowguard(tmp_path, 'check', '--static')       # what flowguard.static.test.mjs runs records the task start
    assert code == 0, text
    again = _prepare(tmp_path)
    plan = json.loads(Path(again['plan']).read_text(encoding='utf-8'))
    assert again['plan'] != answer['plan'] and (plan['baseline'], plan['baseline_kind']) == (head, 'task'), plan



def _report(root, plan):
    """What the vitest plugin prints after the tests, here for a run whose tests reached none of the plan's points."""
    observations = root / '.observations'
    observations.mkdir()
    run = subprocess.run([sys.executable, '-m', 'flowguard.intent.vitest', 'report', '--root', str(root), '--plan', plan,
                          '--observations', str(observations)], cwd=root, capture_output=True, encoding='utf-8',
                         timeout=180, env=_environment())
    return run.returncode, display_text(run)


def test_the_report_title_says_how_far_head_lies_after_the_task_start_as_pytest_does(tmp_path):
    """An agent that never runs new-task: in a vitest project the execution side's block can be FlowGuard's only
    output, so it too names the commits since the task start and the next step."""
    limit = '// flowguard: sensor LIMIT\nexport function limit(days: number) {{ return days <= {}; }}\n'
    _commit(tmp_path, {'src/limits.ts': limit.format(3)})
    start = _git(tmp_path, 'rev-parse', 'HEAD').strip()
    assert _flowguard(tmp_path, 'check', '--static')[0] == 0      # records the task start
    for days in (4, 5):
        _commit(tmp_path, {'src/limits.ts': limit.format(days)}, message=f'task {days}')
    code, text = _report(tmp_path, _prepare(tmp_path)['plan'])
    assert code == 0 and text.splitlines()[0].startswith(f'FlowGuard（since task start {start[:7]}, commits before HEAD: 2; first run python -m flowguard new-task for a new task)') \
        and re.search(r'; [0-9]+\.[0-9]{3} s$', text.splitlines()[0]) and 'unverified: LIMIT（src/limits.ts:2)：not reached by any test' in text, text
    assert _flowguard(tmp_path, 'new-task')[0] == 0
    head = _git(tmp_path, 'rev-parse', 'HEAD').strip()
    (tmp_path / 'src/limits.ts').write_text(limit.format(6), encoding='utf-8')
    code, text = _report(tmp_path, _prepare(tmp_path)['plan'])
    assert code == 0 and text.splitlines()[0].startswith(f'FlowGuard（since task start {head[:7]}）') \
        and re.search(r'; [0-9]+\.[0-9]{3} s$', text.splitlines()[0]), text


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


def test_a_function_that_names_a_database_client_is_not_executed_in_a_project_module(tmp_path):
    _commit(tmp_path, {'src/effects/audited.ts': FEES['src/effects/audited.ts']})
    _sensor(tmp_path, 'src/effects/audited.ts', 'export function activeCount', 'ACTIVE_COUNT')
    plan = json.loads(Path(_prepare(tmp_path)['plan']).read_text(encoding='utf-8'))
    [point] = [point for entry in plan['files'].values() for point in entry['points']]
    assert point['skip'] == 'uses nonliteral constant prisma' and point['source'] == '', point


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


def test_init_wires_a_one_line_vitest_config_without_swallowing_its_code(tmp_path):
    # Round 29: `defineConfig({ test: {...} });` on one line became `plugins: [flowguard()], // flowguard: vitest test:
    # {...} });`: the line comment swallowed the rest of the line and vitest failed to parse the config.
    vitest = '{"name": "%s", "type": "module", "scripts": {"test": "vitest run"}, "devDependencies": {"vitest": "4.1.11"}}\n'
    head = "import { defineConfig } from 'vitest/config';\n\n"
    configs = {
        'line': "export default defineConfig({ test: { setupFiles: ['./setup.ts'] } });\n",
        'lines': "export default defineConfig({\n  test: { setupFiles: ['./setup.ts'] },\n});\n",
        'empty': 'export default defineConfig({});\n',
        'plugins': "export default defineConfig({ plugins: [], test: { environment: 'node' } });\n",
    }
    _commit(tmp_path, {name: text for folder, config in configs.items()
                       for name, text in ((f'{folder}/package.json', vitest % folder), (f'{folder}/vitest.config.mjs', head + config))})
    code, text = _flowguard(tmp_path, 'init')
    assert code == 0, text
    wired = {folder: (tmp_path / folder / 'vitest.config.mjs').read_text(encoding='utf-8').partition('// flowguard: vitest (python')[2]
             .partition('\n')[2] for folder in configs}
    plugin = '  plugins: [flowguard()], // flowguard: vitest\n'
    assert wired == {
        'line': "\nexport default defineConfig({\n" + plugin + "  test: { setupFiles: ['./setup.ts'] } });\n",
        'lines': "\nexport default defineConfig({\n" + plugin + "  test: { setupFiles: ['./setup.ts'] },\n});\n",
        'empty': '\nexport default defineConfig({\n' + plugin + '});\n',
        'plugins': "\nexport default defineConfig({ plugins: [flowguard() /* flowguard: vitest */, ], test: { environment: 'node' } });\n",
    }, wired
    for folder in configs:             # each wired config is still a module node can read
        run = subprocess.run([_tool('node'), '--check', str(tmp_path / folder / 'vitest.config.mjs')], capture_output=True,
                             encoding='utf-8', timeout=60)
        assert run.returncode == 0, (folder, run.stdout + run.stderr)
    # deleting the marked lines undoes it, and no code of the project's goes with them
    undone = '\n'.join(line for line in (tmp_path / 'line/vitest.config.mjs').read_text(encoding='utf-8').splitlines()
                       if 'flowguard: vitest' not in line)
    assert undone == head + "export default defineConfig({\n  test: { setupFiles: ['./setup.ts'] } });", undone


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
        assert 'Generated api/flowguard.static.test.mjs (vitest): npm test runs python -m flowguard check --static' in text, text
        # npm test runs every file, so the integration and end-to-end suites left alone are not worth a line
        assert 'run vitest on integration, end-to-end or other suites' not in text, text


TEST_FILE = "import { it } from 'vitest';\nit('a', () => {});\n"


def _script_packages(root, packages):
    """Commit one package.json per folder, its scripts given, with a test file in each folder named after it."""
    files = {}
    for folder, (scripts, folders) in packages.items():
        files[f'{folder}/package.json'] = scripts if isinstance(scripts, str) else \
            json.dumps({'name': folder, 'scripts': scripts, 'devDependencies': {'vitest': VITEST}}) + '\n'
        files.update({f'{folder}/{inner}/a.test.ts': TEST_FILE for inner in folders})
    _commit(root, files)
    return {folder: files[f'{folder}/package.json'] for folder in packages}


def _scripts(root, folder):
    return json.loads((root / folder / 'package.json').read_text(encoding='utf-8'))['scripts']


def test_init_wires_a_filtered_test_script_first_and_names_the_script_that_runs_the_static_test(tmp_path):
    # Round 23: "test": "vitest run src" beside test:unit got the static test in test:unit only, so npm test did not
    # run it, and init still printed that npm test runs the check; so it did with only integration suites or no script.
    start = _script_packages(tmp_path, {
        'filtered': ({'test': 'vitest run src', 'test:unit': 'vitest run tests/unit'}, ['src', 'tests/unit']),
        'unitonly': ({'test:unit': 'vitest run tests/unit'}, ['tests/unit']),
        'suites': ({'test:integration': 'vitest run tests/integration', 'test:e2e': 'vitest run tests/e2e'},
                   ['tests/integration', 'tests/e2e']),
        'bare': ('{"name": "bare", "devDependencies": {"vitest": "4.1.11"}}\n', []),
    })
    code, text = _flowguard(tmp_path, 'init')
    assert code == 0, text
    assert _scripts(tmp_path, 'filtered') == {'test': 'vitest run src flowguard.static.test.mjs', 'test:unit': 'vitest run tests/unit'}
    assert ('filtered/package.json script "test" runs vitest on named paths only; init added flowguard.static.test.mjs: '
            'vitest run src flowguard.static.test.mjs') in text, text
    assert _scripts(tmp_path, 'unitonly') == {'test:unit': 'vitest run tests/unit flowguard.static.test.mjs'}
    for folder in ('suites', 'bare'):
        assert (tmp_path / folder / 'package.json').read_text(encoding='utf-8') == start[folder], text
    assert text.count('init added') == 2 and text.count('npm test runs') == 1, text
    for again in (text, _flowguard(tmp_path, 'init')[1]):
        assert 'Generated filtered/flowguard.static.test.mjs (vitest): npm test runs python -m flowguard check --static' in again
        assert 'Generated unitonly/flowguard.static.test.mjs (vitest): npm run test:unit runs python -m flowguard check --static' \
            in again, again
        assert ('suites/package.json scripts "test:integration", "test:e2e" run vitest on integration, end-to-end or other '
                'suites that reach real databases and services: init leaves them alone; to run the check with one of them, '
                'add "&& vitest run flowguard.static.test.mjs" to it yourself') in again, again
        for folder in ('suites', 'bare'):
            assert (f'Generated {folder}/flowguard.static.test.mjs (vitest), but init finds no script in {folder}/package.json '
                    'that runs it: add "&& vitest run flowguard.static.test.mjs" to the script you run your tests with, so it '
                    'runs python -m flowguard check --static and fails on red (npx vitest run flowguard.static.test.mjs runs '
                    'it alone).') in again, again
    assert 'init added' not in again and _scripts(tmp_path, 'filtered')['test'] == 'vitest run src flowguard.static.test.mjs', again


def test_init_tries_the_next_script_after_one_it_cannot_wire(tmp_path):
    # Round 23: a unit script that names its own root, or that init cannot edit safely, ended the search.
    _script_packages(tmp_path, {
        'rooted': ({'test:unit': 'vitest run tests/unit --root .', 'test:api': 'vitest run tests/api'}, ['tests/unit', 'tests/api']),
        'names': ({'test:unit': 'vitest run tests/unit -t fast', 'test:api': 'vitest run tests/api'}, ['tests/unit', 'tests/api']),
        # the file spells the slash as \/ : the command JSON reads is not spelled as json.dumps writes it
        'escaped': ('{"name": "escaped", "scripts": {"test:unit": "vitest run tests\\/unit", "test:api": "vitest run tests/api"}, '
                    '"devDependencies": {"vitest": "4.1.11"}}\n', ['tests/unit', 'tests/api']),
    })
    code, text = _flowguard(tmp_path, 'init')
    assert code == 0 and text.count('init added') == 3, text
    for folder, command in (('rooted', 'vitest run tests/unit --root .'), ('names', 'vitest run tests/unit -t fast'),
                            ('escaped', 'vitest run tests/unit')):
        assert _scripts(tmp_path, folder) == {'test:unit': command, 'test:api': 'vitest run tests/api flowguard.static.test.mjs'}
        assert f'Generated {folder}/flowguard.static.test.mjs (vitest): npm run test:api runs python -m flowguard check' in text, text
    for folder, option, command in (('rooted', '--root', 'vitest run tests/unit --root .'),
                                    ('names', '-t', 'vitest run tests/unit -t fast')):
        assert (f'{folder}/package.json script "test:unit" runs vitest with {option}, which init does not read ({command}): '
                'init cannot tell whether it runs flowguard.static.test.mjs; if it does not, add "&& vitest run flowguard.static.test.mjs" '
                'to it yourself') in text, text
    assert ('escaped/package.json script "test:unit" runs vitest on named paths only: change it to vitest run tests/unit '
            'flowguard.static.test.mjs so it runs flowguard.static.test.mjs too') in text, text
    assert '"test:unit": "vitest run tests\\/unit"' in (tmp_path / 'escaped/package.json').read_text(encoding='utf-8')


def test_init_wires_the_unit_script_and_leaves_other_suites_and_watch_scripts_alone(tmp_path):
    # Round 23: the other-suite test was a word match on the name (test:int, test:db and a test:all that runs
    # tests/integration got the static test), and among unit scripts the file order picked a watch variant.
    _script_packages(tmp_path, {
        'suites': ({'test:int': 'vitest run tests/int', 'test:integrations': 'vitest run tests/integrations',
                    'test:db': 'vitest run tests/db', 'test:it': 'vitest run tests/it',
                    'test:acceptance': 'vitest run tests/acceptance', 'test:all': 'vitest run tests/core tests/integration',
                    'test': 'vitest run tests/integration', 'test:core': 'vitest run tests/core'},
                   ['tests/int', 'tests/integrations', 'tests/db', 'tests/it', 'tests/acceptance', 'tests/integration',
                    'tests/core']),
        'ranked': ({'test:unit:watch': 'vitest watch tests/unit', 'test:quick': 'vitest --watch tests/unit',
                    'test:unit-ci': 'vitest run tests/unit --reporter=junit', 'test:unit': 'vitest run tests/unit --reporter=dot'},
                   ['tests/unit']),
        'lengths': ({'test:units-all': 'vitest run tests/u', 'test:api': 'vitest run tests/api', 'test:units': 'vitest run tests/u'},
                    ['tests/u', 'tests/api']),
        'plain': ({'unit': 'vitest run tests/unit', 'test:smoke': 'vitest run tests/smoke'}, ['tests/unit', 'tests/smoke']),
    })
    code, text = _flowguard(tmp_path, 'init')
    assert code == 0 and text.count('init added') == 4, text
    for folder, script in (('suites', 'test:core'), ('ranked', 'test:unit'), ('lengths', 'test:units'), ('plain', 'unit')):
        added = [name for name, command in _scripts(tmp_path, folder).items() if 'flowguard.static.test.mjs' in command]
        assert added == [script], (folder, added, text)
        assert f'Generated {folder}/flowguard.static.test.mjs (vitest): npm run {script} runs python -m flowguard check' in text, text
    assert 'leaves them alone' not in text, text


def test_init_finds_the_static_test_in_every_call_of_every_test_script(tmp_path):
    # Round 23: only a bare word in a script's first runner call counted, so ./flowguard.static.test.mjs, a later
    # && call or a run of the whole folder (.) got the static test a second time.
    start = _script_packages(tmp_path, {
        'dotted': ({'test:unit': 'vitest run tests/unit ./flowguard.static.test.mjs', 'test:api': 'vitest run tests/api'},
                   ['tests/unit', 'tests/api']),
        'later': ({'test:unit': 'vitest run tests/unit && vitest run tests/api flowguard.static.test.mjs'}, ['tests/unit', 'tests/api']),
        'whole': ({'test': 'vitest run ./'}, []),
    })
    code, text = _flowguard(tmp_path, 'init')
    assert code == 0 and 'init added' not in text, text
    for folder, script in (('dotted', 'npm run test:unit'), ('later', 'npm run test:unit'), ('whole', 'npm test')):
        assert (tmp_path / folder / 'package.json').read_text(encoding='utf-8') == start[folder], text
        assert f'Generated {folder}/flowguard.static.test.mjs (vitest): {script} runs python -m flowguard check' in text, text



def _says(text, folder, runs):
    """The line init printed for the static test of `folder`: which script runs it, or None for 'no script'."""
    line = next(line for line in text.splitlines() if line.startswith(f'Generated {folder}/flowguard.static.test.'))
    if ' runs python -m flowguard check --static and fails on red.' in line and '), but ' not in line:
        return line.split('): ', 1)[1].split(' runs python', 1)[0]
    assert runs is None, line
    return None


def test_init_reads_only_calls_whose_options_it_knows_and_never_turns_the_static_test_into_an_option_value(tmp_path):
    # Round 23 final check of r23-init: jest's --testPathIgnorePatterns made the wired file an ignore pattern; an
    # option init does not know made a test script "run nothing"; -t with the file named still counted as running
    # it; vitest's -w (watch) was wired; jest's -w (workers) is harmless.
    jest = lambda scripts: json.dumps({'name': 'j', 'scripts': scripts, 'devDependencies': {'jest': '29.7.0'}}) + '\n'
    start = _script_packages(tmp_path, {
        'ignore': (jest({'test': 'jest', 'test:unit': 'jest tests/unit --testPathIgnorePatterns fixtures'}), ['tests/unit']),
        'workers': (jest({'test:unit': 'jest tests/unit -w 2 --ci'}), ['tests/unit']),
        'unknown': ({'test': 'vitest run --typecheck'}, []),
        'named': ({'test': 'vitest run flowguard.static.test.mjs -t fast'}, []),
        'watch': ({'test:unit': 'vitest -w tests/unit'}, ['tests/unit']),
        'known': ({'test:unit': 'vitest run tests/unit --reporter dot --coverage --maxWorkers=2'}, ['tests/unit']),
    })
    code, text = _flowguard(tmp_path, 'init')
    assert code == 0, text
    for folder in ('ignore', 'unknown', 'named', 'watch'):
        assert (tmp_path / folder / 'package.json').read_text(encoding='utf-8') == start[folder], (folder, text)
    assert _scripts(tmp_path, 'workers') == {'test:unit': 'jest tests/unit -w 2 --ci flowguard.static.test.js'}, text
    assert _scripts(tmp_path, 'known') == {
        'test:unit': 'vitest run tests/unit --reporter dot --coverage --maxWorkers=2 flowguard.static.test.mjs'}, text
    for folder, runs in (('ignore', 'npm test'), ('workers', 'npm run test:unit'), ('unknown', None), ('named', None),
                         ('watch', None), ('known', 'npm run test:unit')):
        assert _says(text, folder, runs) == runs, (folder, text)
    assert ('ignore/package.json script "test:unit" runs jest with --testPathIgnorePatterns, which init does not read '
            '(jest tests/unit --testPathIgnorePatterns fixtures)') in text, text
    assert ('unknown/package.json script "test" runs vitest with --typecheck, which init does not read (vitest run --typecheck): '
            'init cannot tell whether it runs flowguard.static.test.mjs') in text, text
    assert 'named/package.json script "test" runs vitest with -t, which init does not read' in text, text


def test_init_never_counts_a_call_that_picks_its_files_elsewhere_as_running_the_static_test(tmp_path):
    # Round 23 check: -c, --project, --shard and --changed counted as running every file, so init printed "npm test runs"
    # for a test script that runs one config's files only; --dir without paths got no line and advice that broke it.
    start = _script_packages(tmp_path, {
        'config': ({'test': 'vitest run -c vitest.unit.config.ts', 'test:e2e': 'vitest run tests/e2e'}, ['tests/e2e', 'tests/unit']),
        'project': ({'test': 'vitest run --project unit', 'test:unit': 'vitest run tests/unit'}, ['tests/unit']),
        'folder': ({'test': 'vitest run --dir src'}, ['src']),
        'shard': ({'test': 'vitest run --shard=1/2'}, []),
        'covered': ({'test': 'vitest run', 'test:changed': 'vitest run --changed'}, []),
    })
    code, text = _flowguard(tmp_path, 'init')
    assert code == 0 and text.count('init added') == 1, text
    assert _scripts(tmp_path, 'project') == {'test': 'vitest run --project unit',
                                             'test:unit': 'vitest run tests/unit flowguard.static.test.mjs'}, text
    for folder in ('config', 'folder', 'shard', 'covered'):
        assert (tmp_path / folder / 'package.json').read_text(encoding='utf-8') == start[folder], text
    for folder, runs in (('config', None), ('project', 'npm run test:unit'), ('folder', None), ('shard', None),
                         ('covered', 'npm test')):
        assert _says(text, folder, runs) == runs, text
    for folder, option, command in (('config', '-c', 'vitest run -c vitest.unit.config.ts'),
                                    ('project', '--project', 'vitest run --project unit'),
                                    ('folder', '--dir', 'vitest run --dir src'), ('shard', '--shard', 'vitest run --shard=1/2')):
        assert (f'{folder}/package.json script "test" runs vitest with {option}, which init does not read ({command}): '
                'init cannot tell whether it runs flowguard.static.test.mjs; if it does not, add "&& vitest run flowguard.static.test.mjs" '
                'to it yourself') in text, text
    assert ('config/package.json script "test:e2e" runs vitest on an integration, end-to-end or other suite that reaches '
            'real databases and services: init leaves it alone') in text, text
    # npm test already runs every file: a script with no path that picks its own files is not worth a line
    assert 'test:changed' not in text, text


def test_init_never_names_a_watch_script_or_another_suite_as_the_script_that_runs_the_static_test(tmp_path):
    # Round 23 check: with nothing wired, init named the first script of the file that ran the static test, also a
    # database suite or a watch script, and named a suite with its own config that does not run it at all.
    start = _script_packages(tmp_path, {
        'configs': ({'test:integration': 'vitest run -c vitest.integration.config.ts', 'test:unit': 'vitest run -c vitest.unit.config.ts'},
                    []),
        'watching': ({'test:watch': 'vitest watch', 'test:ci': 'vitest run --coverage'}, []),
        'database': ({'test:integration': 'DATABASE_URL=x vitest run'}, []),
        'both': ({'test:watch': 'vitest watch', 'test:integration': 'vitest run'}, []),
        # a watch script that already names the static test: nothing is added a second time
        'named': ({'test:watch': 'vitest watch tests/unit flowguard.static.test.mjs', 'test:unit': 'vitest run tests/unit'},
                  ['tests/unit']),
    })
    code, text = _flowguard(tmp_path, 'init')
    assert code == 0 and 'init added' not in text, text
    for folder in start:
        assert (tmp_path / folder / 'package.json').read_text(encoding='utf-8') == start[folder], text
    for folder, runs in (('configs', None), ('watching', 'npm run test:ci'), ('database', None), ('both', None), ('named', None)):
        assert _says(text, folder, runs) == runs, text
    edit = ('add "&& vitest run flowguard.static.test.mjs" to the script you run your tests with, so it runs python -m '
            'flowguard check --static and fails on red')
    assert f'Generated configs/flowguard.static.test.mjs (vitest), but init finds no script in configs/package.json that runs it: {edit}' \
        in text, text
    assert ('configs/package.json script "test:integration" runs vitest on an integration, end-to-end or other suite') in text, text
    assert 'configs/package.json script "test:unit" runs vitest with -c, which init does not read (vitest run -c vitest.unit.config.ts)' in text, text
    for folder, left in (('database', '"test:integration" runs'), ('both', '"test:watch", "test:integration" run'),
                         ('named', '"test:watch" runs')):
        assert (f'Generated {folder}/flowguard.static.test.mjs (vitest), but in {folder}/package.json only {left} it, and init '
                f'names no watch or debug script, nor a suite that reaches real databases and services: {edit}') in text, text


def test_init_reads_only_whole_folders_as_other_suites(tmp_path):
    # Round 23 check: folders were also split on - and _, so src/lazy-load (load) or packages/it-utils (it) made a
    # unit script, or the test script itself, another suite; npm test then did not run the static test.
    _script_packages(tmp_path, {
        'lazy': ({'test': 'vitest run src/lazy-load src/core', 'test:unit': 'vitest run src/core'}, ['src/lazy-load', 'src/core']),
        'utils': ({'test:unit': 'vitest run packages/it-utils'}, ['packages/it-utils']),
        'perf': ({'test:unit': 'vitest run src/perf_utils'}, ['src/perf_utils']),
        'whole': ({'test:unit': 'vitest run src/db', 'test:api': 'vitest run tests/load/api'}, ['src/db', 'tests/load/api']),
    })
    code, text = _flowguard(tmp_path, 'init')
    assert code == 0 and text.count('init added') == 3, text
    assert _scripts(tmp_path, 'lazy') == {'test': 'vitest run src/lazy-load src/core flowguard.static.test.mjs',
                                          'test:unit': 'vitest run src/core'}, text
    for folder, path in (('utils', 'packages/it-utils'), ('perf', 'src/perf_utils')):
        assert _scripts(tmp_path, folder) == {'test:unit': f'vitest run {path} flowguard.static.test.mjs'}, text
    for folder, runs in (('lazy', 'npm test'), ('utils', 'npm run test:unit'), ('perf', 'npm run test:unit'), ('whole', None)):
        assert _says(text, folder, runs) == runs, text
    # a whole folder named db or load is another suite
    assert ('whole/package.json scripts "test:unit", "test:api" run vitest on integration, end-to-end or other suites that '
            'reach real databases and services: init leaves them alone') in text, text


def test_init_reads_watch_turned_off_as_no_watch(tmp_path):
    # Round 23 check: --watchAll=false (Jest's way to turn watching off) and --watch=false counted as watching, so the
    # unit script was skipped without a word; a script that does watch is still never the one.
    jest = '{"name": "%s", "scripts": {"test:unit": "jest %s tests/unit"}, "devDependencies": {"jest": "29.7.0"}}\n'
    _script_packages(tmp_path, {
        'off': ({'test:unit-dev': 'vitest --watch tests/unit', 'test:unit': 'vitest --watch=false tests/unit'}, ['tests/unit']),
        'apart': ({'test:unit': 'vitest --watch false tests/unit'}, ['tests/unit']),
        'jest': (jest % ('jest', '--watchAll=false'), ['tests/unit']),
        'jestapart': (jest % ('jestapart', '--watchAll false'), ['tests/unit']),
        'on': ({'test:unit': 'vitest --watch=true tests/unit'}, ['tests/unit']),
    })
    code, text = _flowguard(tmp_path, 'init')
    assert code == 0 and text.count('init added') == 4, text
    assert _scripts(tmp_path, 'off') == {'test:unit-dev': 'vitest --watch tests/unit',
                                         'test:unit': 'vitest --watch=false tests/unit flowguard.static.test.mjs'}, text
    assert _scripts(tmp_path, 'apart') == {'test:unit': 'vitest --watch false tests/unit flowguard.static.test.mjs'}, text
    assert _scripts(tmp_path, 'jest') == {'test:unit': 'jest --watchAll=false tests/unit flowguard.static.test.js'}, text
    assert _scripts(tmp_path, 'jestapart') == {'test:unit': 'jest --watchAll false tests/unit flowguard.static.test.js'}, text
    assert _scripts(tmp_path, 'on') == {'test:unit': 'vitest --watch=true tests/unit'}, text
    for folder, runs in (('off', 'npm run test:unit'), ('apart', 'npm run test:unit'), ('jest', 'npm run test:unit'),
                         ('jestapart', 'npm run test:unit'), ('on', None)):
        assert _says(text, folder, runs) == runs, text


def _jest(folder, scripts, **fields):
    return json.dumps({'name': folder, **fields, 'scripts': scripts, 'devDependencies': {'jest': '29.7.0'}}) + '\n'


def test_init_never_reads_an_option_value_as_a_path_nor_adds_its_test_where_an_option_would_take_it(tmp_path):
    # Round 24 review: the value of --coverage.include or of vitest's -u / --update read as a folder, so init added
    # the static test to a script that runs every file, and vitest then ran that file alone (vitest 4 reads
    # "vitest run -u tests" as update "tests" and no filter); added after a trailing -u or --silent, the file
    # became that option's value (vitest refuses "--silent flowguard.static.test.mjs").
    start = _script_packages(tmp_path, {
        'included': ({'test': 'vitest run --coverage --coverage.include src'}, ['src']),
        'update': ({'test': 'vitest run', 'test:update': 'vitest run -u tests'}, ['tests']),
        'spelled': ({'test': 'vitest run --update tests --coverage.reporter text'}, ['tests', 'text']),
        'trailing': ({'test:unit': 'vitest run tests/unit -u'}, ['tests/unit']),
        'silent': ({'test:unit': 'vitest run tests/unit --silent'}, ['tests/unit']),
        'given': ({'test:unit': 'vitest run tests/unit --update=new'}, ['tests/unit']),
    })
    code, text = _flowguard(tmp_path, 'init')
    assert code == 0, text
    for folder in ('included', 'update', 'spelled'):
        assert (tmp_path / folder / 'package.json').read_text(encoding='utf-8') == start[folder], (folder, text)
        assert _says(text, folder, 'npm test') == 'npm test', (folder, text)
    for folder, command in (('trailing', 'vitest run tests/unit flowguard.static.test.mjs -u'),
                            ('silent', 'vitest run tests/unit flowguard.static.test.mjs --silent'),
                            ('given', 'vitest run tests/unit --update=new flowguard.static.test.mjs')):
        assert _scripts(tmp_path, folder) == {'test:unit': command}, (folder, text)
        assert (f'{folder}/package.json script "test:unit" runs vitest on named paths only; init added '
                f'flowguard.static.test.mjs: {command}') in text, text
        assert _says(text, folder, 'npm run test:unit') == 'npm run test:unit', (folder, text)


def test_init_reads_the_reporting_options_and_boolean_values_of_plain_test_scripts(tmp_path):
    # Round 24 review: jest's --reporters, --coverageReporters and --no-watchman and vitest's --no-color made a
    # plain test script one init cannot read, and --coverage.enabled true or --silent passed-only read the value
    # as a path, so a script that runs every file counted as running nothing. jest's arrays take every word after
    # them up to the next option, so the static test goes before a trailing --reporters.
    start = _script_packages(tmp_path, {
        'reporters': (_jest('reporters', {'test': 'jest --ci --reporters=default --reporters=jest-junit'}), []),
        'summary': (_jest('summary', {'test': 'jest --coverage --coverageReporters=text-summary --coverageDirectory out'}),
                    []),
        'watchman': (_jest('watchman', {'test:unit': 'jest --runInBand --no-watchman tests/unit'}), ['tests/unit']),
        'arrays': (_jest('arrays', {'test:unit': 'jest tests/unit --coverageReporters text lcov'}), ['tests/unit']),
        'color': ({'test:unit': 'vitest run --no-color tests/unit'}, ['tests/unit']),
        'enabled': ({'test': 'vitest run --coverage.enabled true'}, []),
        'shuffled': ({'test:unit': 'vitest run --sequence.shuffle tests/unit'}, ['tests/unit']),
        'passed': ({'test': 'vitest run --silent passed-only'}, []),
    })
    code, text = _flowguard(tmp_path, 'init')
    assert code == 0 and 'which init does not read' not in text, text
    for folder in ('reporters', 'summary', 'enabled', 'passed'):
        assert (tmp_path / folder / 'package.json').read_text(encoding='utf-8') == start[folder], (folder, text)
        assert _says(text, folder, 'npm test') == 'npm test', (folder, text)
    for folder, command in (('watchman', 'jest --runInBand --no-watchman tests/unit flowguard.static.test.js'),
                            ('arrays', 'jest tests/unit flowguard.static.test.js --coverageReporters text lcov'),
                            ('color', 'vitest run --no-color tests/unit flowguard.static.test.mjs'),
                            ('shuffled', 'vitest run --sequence.shuffle tests/unit flowguard.static.test.mjs')):
        assert _scripts(tmp_path, folder) == {'test:unit': command}, (folder, text)
        assert _says(text, folder, 'npm run test:unit') == 'npm run test:unit', (folder, text)


def test_init_reads_a_vitest_option_that_takes_only_a_few_words_by_those_words(tmp_path):
    # Round 25 check: --silent took any word, so vitest 2's "vitest run --silent tests/unit" (a flag and a folder; vitest
    # 3.1 on take only true, yes, false, no or passed-only and refuse a path) counted as running every file and was
    # left without the static test. vitest 3 reads --coverage.all, --coverage.thresholds.autoUpdate and the poolOptions
    # booleans as flags, vitest 4 the word after them as their value (all: "tests/unit", and every file runs): a call
    # that gives one another word than true, yes, false or no is one init cannot read; before, init either left it
    # as running every file or added the static test, which vitest 4 then ran alone.
    vitest = lambda folder, scripts, version: json.dumps({'name': folder, 'scripts': scripts,
                                                          'devDependencies': {'vitest': version}}) + '\n'
    start = _script_packages(tmp_path, {
        'silent': (vitest('silent', {'test': 'vitest run --silent tests/unit'}, '^2.1.9'), ['tests/unit']),
        'yes': ({'test': 'vitest run --silent yes'}, []),
        'all': (vitest('all', {'test': 'vitest run --coverage --coverage.all tests/unit'}, '^3.2.4'), ['tests/unit']),
        'auto': (vitest('auto', {'test:unit': 'vitest run --coverage.thresholds.autoUpdate tests/unit'}, '^3.2.4'),
                 ['tests/unit']),
        'pool': ({'test:unit': 'vitest run --poolOptions.forks.singleFork tests/unit'}, ['tests/unit']),
        'alltrue': ({'test:unit': 'vitest run --coverage.all true tests/unit'}, ['tests/unit']),
        'autolast': ({'test:unit': 'vitest run tests/unit --coverage.thresholds.autoUpdate'}, ['tests/unit']),
    })
    code, text = _flowguard(tmp_path, 'init')
    assert code == 0, text
    for folder, script, command in (
            ('silent', 'test', 'vitest run --silent tests/unit flowguard.static.test.mjs'),
            ('alltrue', 'test:unit', 'vitest run --coverage.all true tests/unit flowguard.static.test.mjs'),
            ('autolast', 'test:unit', 'vitest run tests/unit flowguard.static.test.mjs --coverage.thresholds.autoUpdate')):
        assert _scripts(tmp_path, folder) == {script: command}, (folder, text)
        runs = 'npm test' if script == 'test' else 'npm run ' + script
        assert _says(text, folder, runs) == runs, (folder, text)
    assert (tmp_path / 'yes/package.json').read_text(encoding='utf-8') == start['yes'], text
    assert _says(text, 'yes', 'npm test') == 'npm test', text
    for folder, script, option in (('all', 'test', '--coverage.all'), ('auto', 'test:unit', '--coverage.thresholds.autoUpdate'),
                                   ('pool', 'test:unit', '--poolOptions.forks.singleFork')):
        assert (tmp_path / folder / 'package.json').read_text(encoding='utf-8') == start[folder], (folder, text)
        assert _says(text, folder, None) is None, (folder, text)
        assert (f'{folder}/package.json script "{script}" runs vitest with {option}, which init does not read '
                f'({json.loads(start[folder])["scripts"][script]}): init cannot tell whether it runs '
                'flowguard.static.test.mjs; if it does not, add "&& vitest run flowguard.static.test.mjs" to it yourself'
                ) in text, (folder, text)

def test_init_reads_a_runner_started_through_node_and_spells_each_edit_the_way_jest_runs_an_es_module(tmp_path):
    # Round 24 review: "node --experimental-vm-modules node_modules/jest/bin/jest.js", jest's own way to run ES
    # module tests, was no call of jest, and the advice "&& jest flowguard.static.test.js" fails to parse the
    # generated ES module test (jest runs it only under --experimental-vm-modules).
    node = 'node --experimental-vm-modules node_modules/jest/bin/jest.js'
    start = _script_packages(tmp_path, {
        'whole': (_jest('whole', {'test': node}, type='module'), []),
        'unit': (_jest('unit', {'test': f'{node} tests/unit'}, type='module'), ['tests/unit']),
        'started': ({'test:unit': 'node node_modules/vitest/vitest.mjs run tests/unit'}, ['tests/unit']),
        'named': (_jest('named', {'test': f'{node} --testNamePattern=fast'}, type='module'), []),
        'options': (_jest('options', {'test': 'NODE_OPTIONS=--experimental-vm-modules jest -t fast'}, type='module'), []),
        'none': (_jest('none', {'test': 'echo none'}, type='module'), []),
        'commonjs': (_jest('commonjs', {'test': 'echo none'}), []),
    })
    code, text = _flowguard(tmp_path, 'init')
    assert code == 0, text
    assert (tmp_path / 'whole/package.json').read_text(encoding='utf-8') == start['whole'], text
    assert _says(text, 'whole', 'npm test') == 'npm test', text
    assert _scripts(tmp_path, 'unit') == {'test': f'{node} tests/unit flowguard.static.test.js'}, text
    assert _scripts(tmp_path, 'started') == {'test:unit': 'node node_modules/vitest/vitest.mjs run tests/unit '
                                                          'flowguard.static.test.mjs'}, text
    for folder, call, alone in (('named', f'{node} flowguard.static.test.js', f'{node} flowguard.static.test.js'),
                                ('options', 'NODE_OPTIONS=--experimental-vm-modules jest flowguard.static.test.js',
                                 'NODE_OPTIONS=--experimental-vm-modules npx jest flowguard.static.test.js'),
                                ('none', f'{node} flowguard.static.test.js', f'{node} flowguard.static.test.js'),
                                ('commonjs', 'jest flowguard.static.test.js', 'npx jest flowguard.static.test.js')):
        assert (tmp_path / folder / 'package.json').read_text(encoding='utf-8') == start[folder], (folder, text)
        assert (f'Generated {folder}/flowguard.static.test.js (jest), but init finds no script in {folder}/package.json '
                f'that runs it: add "&& {call}" to the script you run your tests with, so it runs python -m flowguard '
                f'check --static and fails on red ({alone} runs it alone).') in text, (folder, text)
    for folder, option, call in (('named', '--testNamePattern', f'{node} flowguard.static.test.js'),
                                 ('options', '-t', 'NODE_OPTIONS=--experimental-vm-modules jest flowguard.static.test.js')):
        assert (f'{folder}/package.json script "test" runs jest with {option}, which init does not read '
                f'({json.loads(start[folder])["scripts"]["test"]}): init cannot tell whether it runs '
                f'flowguard.static.test.js; if it does not, add "&& {call}" to it yourself') in text, (folder, text)



def test_an_es_module_jest_package_whose_script_sets_the_vm_flag_outside_jests_own_call_gets_an_es_module_test(tmp_path):
    # Final check of r25-init: `export NODE_OPTIONS=--experimental-vm-modules && jest`, Windows' `set NODE_OPTIONS=... &&
    # npx jest` and a script that runs jest through `npm run` under the flag got the CommonJS test, which jest under
    # the flag loads as an ES module of a "type": "module" package and fails (`require is not defined`).
    _script_packages(tmp_path, {
        'export': (_jest('export', {'test': 'export NODE_OPTIONS=--experimental-vm-modules && jest'}, type='module'), []),
        'winset': (_jest('winset', {'test': 'set NODE_OPTIONS=--experimental-vm-modules && npx jest'}, type='module'), []),
        'chain': (_jest('chain', {'test': 'NODE_OPTIONS=--experimental-vm-modules npm run test:jest', 'test:jest': 'jest'},
                        type='module'), []),
        'plain': (_jest('plain', {'test': 'jest'}, type='module'), []),
    })
    code, text = _flowguard(tmp_path, 'init')
    assert code == 0, text
    for folder in ('export', 'winset', 'chain'):
        generated = (tmp_path / folder / 'flowguard.static.test.js').read_text(encoding='utf-8')
        assert "from 'node:" in generated and 'require(' not in generated, (folder, generated)
    generated = (tmp_path / 'plain/flowguard.static.test.js').read_text(encoding='utf-8')
    assert "require('node:child_process')" in generated, generated       # jest without the flag loads CommonJS


def test_init_starts_jest_for_an_es_module_package_without_another_script_s_settings_or_debugger(tmp_path):
    # Round 25 check: the advice for other scripts copied the whole start of any call with --experimental-vm-modules,
    # a debugger that waits (--inspect-brk) or an integration suite's database URL with its password included; and
    # jest's documented debug script counted as the suite that runs the check.
    node = 'node --experimental-vm-modules node_modules/jest/bin/jest.js'
    start = _script_packages(tmp_path, {
        'debugname': (_jest('debugname', {'debug': f'node --inspect-brk --experimental-vm-modules node_modules/jest/bin/jest.js '
                                                   '--runInBand', 'test': 'echo no tests yet'}, type='module'), []),
        'debugonly': (_jest('debugonly', {'test:debug': 'node --inspect-brk --experimental-vm-modules '
                                                        'node_modules/jest/bin/jest.js --runInBand', 'test': 'echo none'},
                            type='module'), []),
        'envfirst': (_jest('envfirst', {'test:integration': 'DATABASE_URL=postgres://u:secret@localhost/t '
                                                            'NODE_OPTIONS=--experimental-vm-modules jest tests/integration',
                                        'test': 'echo none'}, type='module'), ['tests/integration']),
        'heap': (_jest('heap', {'test': 'node --max-old-space-size=4096 --experimental-vm-modules node_modules/.bin/jest -t fast'},
                       type='module'), []),
        'crossenv': (_jest('crossenv', {'test': 'cross-env NODE_OPTIONS="--experimental-vm-modules --no-warnings" jest -t a'},
                           type='module'), []),
    })
    code, text = _flowguard(tmp_path, 'init')
    assert code == 0 and 'secret' not in text and '--inspect-brk' not in text.replace(start['debugname'], ''), text
    for folder in start:
        assert (tmp_path / folder / 'package.json').read_text(encoding='utf-8') == start[folder], (folder, text)
        assert _says(text, folder, None) is None, (folder, text)
    advice = lambda folder, call, alone, found=None: (
        f'Generated {folder}/flowguard.static.test.js (jest), but {found or f"init finds no script in {folder}/package.json that runs it"}: '
        f'add "&& {call} flowguard.static.test.js" to the script you run your tests with, so it runs python -m flowguard '
        f'check --static and fails on red ({alone} flowguard.static.test.js runs it alone).')
    vm = 'NODE_OPTIONS=--experimental-vm-modules jest'
    for line in (advice('debugname', node, node),
                 advice('debugonly', node, node, 'in debugonly/package.json only "test:debug" runs it, and init names no '
                                                 'watch or debug script, nor a suite that reaches real databases and services'),
                 advice('envfirst', vm, 'NODE_OPTIONS=--experimental-vm-modules npx jest'),
                 'envfirst/package.json script "test:integration" runs jest on an integration, end-to-end or other suite that '
                 f'reaches real databases and services: init leaves it alone; to run the check with it, add "&& {vm} '
                 'flowguard.static.test.js" to it yourself',
                 advice('heap', 'node --experimental-vm-modules node_modules/.bin/jest',
                        'node --experimental-vm-modules node_modules/.bin/jest'),
                 # the edit named for a script still starts jest the way that script does
                 'heap/package.json script "test" runs jest with -t, which init does not read (node --max-old-space-size=4096 '
                 '--experimental-vm-modules node_modules/.bin/jest -t fast): init cannot tell whether it runs '
                 'flowguard.static.test.js; if it does not, add "&& node --max-old-space-size=4096 --experimental-vm-modules '
                 'node_modules/.bin/jest flowguard.static.test.js" to it yourself',
                 advice('crossenv', f'cross-env {vm}', f'npx cross-env {vm}')):
        assert line in text, (line, text)


def test_init_writes_a_commonjs_test_for_an_es_module_package_whose_scripts_run_plain_jest(tmp_path):
    # Round 25 check: a "type": "module" package whose scripts run jest without --experimental-vm-modules loads every
    # test as CommonJS, so the generated ES module test failed ("Cannot use import statement outside a module") in the
    # script init had added it to, and the advice spelled two different calls in one output.
    start = _script_packages(tmp_path, {
        'plain': (_jest('plain', {'test': 'jest --ci -t one', 'test:unit': 'jest tests/unit'}, type='module'), ['tests/unit']),
        'bare': (_jest('bare', {'test': 'jest -t fast'}, type='module'), []),
        'mixed': (_jest('mixed', {'test:legacy': 'jest tests/legacy', 'test': 'NODE_OPTIONS=--experimental-vm-modules jest -t a'},
                        type='module'), ['tests/legacy']),
    })
    code, text = _flowguard(tmp_path, 'init')
    assert code == 0, text
    for folder in ('plain', 'bare'):
        generated = (tmp_path / folder / 'flowguard.static.test.js').read_text(encoding='utf-8')
        assert "require('node:child_process')" in generated and "from 'node:" not in generated, (folder, generated)
    assert _scripts(tmp_path, 'plain') == {'test': 'jest --ci -t one', 'test:unit': 'jest tests/unit flowguard.static.test.js'}
    assert _says(text, 'plain', 'npm run test:unit') == 'npm run test:unit', text
    assert ('plain/package.json script "test" runs jest with -t, which init does not read (jest --ci -t one): init cannot tell '
            'whether it runs flowguard.static.test.js; if it does not, add "&& jest flowguard.static.test.js" to it yourself'
            ) in text, text
    assert ('Generated bare/flowguard.static.test.js (jest), but init finds no script in bare/package.json that runs it: add '
            '"&& jest flowguard.static.test.js" to the script you run your tests with') in text, text
    assert '"&& jest flowguard.static.test.js" to it yourself' in text.partition('bare/package.json script "test"')[2], text
    # a package that runs jest under --experimental-vm-modules keeps the ES module test, and a call without the flag
    # cannot load it: init neither adds it there nor names that call's way of starting jest
    generated = (tmp_path / 'mixed/flowguard.static.test.js').read_text(encoding='utf-8')
    assert "import { spawnSync } from 'node:child_process';" in generated, generated
    assert (tmp_path / 'mixed/package.json').read_text(encoding='utf-8') == start['mixed'], text
    assert _says(text, 'mixed', None) is None, text
    assert ('Generated mixed/flowguard.static.test.js (jest), but init finds no script in mixed/package.json that runs it: add '
            '"&& NODE_OPTIONS=--experimental-vm-modules jest flowguard.static.test.js"') in text, text
    assert '&& jest flowguard.static.test.js' not in text.partition('Generated mixed/')[2].partition('Generated ')[0], text

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
    # vitest colours its output where it detects CI; a failed case's message then ends with a colour reset (`\x1b[39m`)
    # that splits one red into two lines that differ. The tests read the text a reader sees, without the colours.
    return run.returncode, display_text(ANSI.sub('', run.stdout + run.stderr))


ANSI = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')


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
    assert 'changed: ' not in text and 'same-name anchor' not in text, text
    _sensor(root, 'src/fees/late-fee.ts', 'export function lateFee', 'LATE_FEE')
    _sensor(root, 'src/preview/fee-preview.ts', 'export const lateFee', 'LATE_FEE')
    code, text = _vitest(root, vitest_home)
    assert code == 1, text
    # Samples come from real calls, the copies' numbers and their numeric neighbours (signals.copy_inputs, as
    # pytest compares), not the retired fractional grid. The copies already differed at 4 (6 and 7), the input
    # closest to the real lateFee(2, true).
    assert 'before: same-name anchor LATE_FEE: days=4, member=T' in text, text
    assert 'red: FEE_WINDOW: days=5 member=T -> rule 7, code 9（src/preview/fee-preview.ts:3 lateFee）' in text, text
    assert 'FEE_WINDOW source: assumed: three free days, then 5 plus 1 a day for members and 2 a day for others' in text, text
    _commit(root, message='sensors')
    late = root / 'src/fees/late-fee.ts'
    late.write_text(late.read_text(encoding='utf-8').replace('days > FREE_DAYS', 'days >= FREE_DAYS'), encoding='utf-8')
    test = root / 'tests/fees.test.ts'
    test.write_text(test.read_text().replace('expect(lateFee(2, true)).toBe(0);', 'expect(lateFee(2, true)).toBe(0); expect(lateFee(3, false)).toBe(5);'))
    code, text = _vitest(root, vitest_home)
    assert code == 1, text
    assert 'changed: LATE_FEE' in text and 'days=3' in text and 'function result 0 → 5' in text, text
    assert 'red: FEE_WINDOW: days=3 member=F -> rule 0, code 5（src/fees/late-fee.ts:4 lateFee）' in text, text
    # the unchanged copy compared on every replayed class prints nothing of its own
    assert not [line for line in text.splitlines() if line.startswith('unverified') and 'fee-preview.ts' in line], text


def test_a_careless_change_of_a_function_reading_a_folded_constant_is_changed(vitest_home):
    # Round 23, Planning Tool: roundFteShare reads FTE_SHARE_FACTOR = 10 ** FTE_SHARE_DECIMALS. That constant was
    # "nonliteral", so its old and new versions were not compared and a careless change passed every test unseen.
    root = vitest_home / 'folded'
    _commit(root, {
        'package.json': '{"name":"folded","private":true,"type":"module","devDependencies":{"vitest":"' + VITEST + '"}}',
        'src/quantity.ts': '''
            const FTE_SHARE_DECIMALS = 4;
            const FTE_SHARE_FACTOR = 10 ** FTE_SHARE_DECIMALS;

            function roundFteShare(value: number): number {
              return Math.round(value * FTE_SHARE_FACTOR) / FTE_SHARE_FACTOR;
            }

            export function toFteShare(hours: number, reference: number): number {
              return roundFteShare(hours / reference);
            }
        ''',
        'tests/quantity.test.ts': ("import {it,expect} from 'vitest'; import {toFteShare} from '../src/quantity';\n"
                                   "it('gives a share', () => { expect(toFteShare(0.75, 40)).toBeGreaterThan(0); "
                                   "expect(toFteShare(20, 40)).toBe(0.5); });\n"),
    })
    assert _flowguard(root, 'init')[0] == 0
    _commit(root, message='wired')
    quantity = root / 'src/quantity.ts'
    quantity.write_text(quantity.read_text(encoding='utf-8').replace('return Math.round(value * FTE_SHARE_FACTOR) / FTE_SHARE_FACTOR;',
                                                                     'return Number(value.toFixed(FTE_SHARE_DECIMALS));'), encoding='utf-8')
    code, text = _vitest(root, vitest_home)
    assert code == 0 and 'nonliteral constant' not in text, text
    changed = [line for line in text.splitlines() if line.startswith('changed') and 'roundFteShare' in line]
    assert changed and 'function result 0.0188 → 0.0187' in changed[0] and 'value=0.01875' in changed[0], text


def test_a_disagreeing_same_name_pair_is_compared_again_in_a_run_without_a_ts_change(vitest_home):
    root = vitest_home / 'again'
    _commit(root, {
        'package.json': '{"name":"again","private":true,"type":"module","devDependencies":{"vitest":"' + VITEST + '"}}',
        'src/a.ts': '// flowguard: same LIMIT\nexport function over(x: number) { return x > 3; }\n',
        'src/b.ts': '// flowguard: same LIMIT\nexport function enough(x: number) { return x > 3; }\n',
        'tests/app.test.ts': "import {it,expect} from 'vitest'; import {over} from '../src/a'; it('real',()=>expect(over(4)).toBe(true));\n",
    })
    assert _flowguard(root, 'init')[0] == 0
    _commit(root, message='wired agreeing copies')
    other = root / 'src/b.ts'
    other.write_text(other.read_text().replace('x > 3', 'x >= 3'))
    code, text = _vitest(root, vitest_home)
    assert code == 1 and 'red: same-name anchor LIMIT: x=3' in text, text
    _commit(root, message='copies disagree')
    assert _flowguard(root, 'new-task')[0] == 0
    code, text = _vitest(root, vitest_home)
    assert code == 0 and 'before: same-name anchor LIMIT: x=3' in text and 'red: same-name anchor' not in text, text
    other.write_text(other.read_text().replace('x >= 3', 'x > 3'))
    _commit(root, message='the copies agree')
    assert _flowguard(root, 'new-task')[0] == 0
    code, text = _vitest(root, vitest_home)
    assert code == 0 and 'same-name anchor' not in text, text
    assert _prepare(root)['status'] == 'on'  # registered copies are checked even when no source changed


def test_a_recorded_function_keeps_its_stack_positions_after_a_line_or_paragraph_separator(vitest_home):
    # JavaScript ends a line at U+2028 and U+2029 too: the recorder's source map counts lines the same way,
    # so a stack position inside a recorded function is the one vitest gives without FlowGuard (line 7, column 13).
    root = vitest_home / 'separators'
    _commit(root, {
        'package.json': '{"name":"separators","private":true,"type":"module","devDependencies":{"vitest":"' + VITEST + '"}}',
        'src/grade.ts': ("/* a note\u2028with a line separator */\nexport const NOTE = 'x\u2029y';\n"
                         "export const seen: string[] = [];\nexport function grade(n: number): string {\n"
                         "  seen.push(new Error('in').stack!.split('\\n')[1].trim());\n"
                         "  return n >= 5 ? 'pass' : 'fail';\n}\n"),
        'tests/grade.test.ts': ("import { expect, it } from 'vitest';\nimport { grade, seen } from '../src/grade';\n"
                                "it('grades', () => { expect(grade(5)).toBe('pass'); expect(seen[0]).toMatch(/grade\\.ts:7:13\\)$/); });\n"),
    })
    assert _flowguard(root, 'init')[0] == 0
    _commit(root, message='wired')
    grade = root / 'src/grade.ts'
    grade.write_text(grade.read_text(encoding='utf-8').replace("n >= 5 ?", "!(n < 5) ?"), encoding='utf-8', newline='\n')
    plan = json.loads(Path(_prepare(root)['plan']).read_text(encoding='utf-8'))
    assert [point['fn'] for entry in plan['files'].values() for point in entry['points']] == ['grade'], plan
    code, text = _vitest(root, vitest_home)
    assert code == 0 and 'Tests  3 passed (3)' in text, text

def test_a_build_and_the_dev_server_never_load_flowguard_only_a_vitest_run_does(vitest_home):
    # R85: FlowGuard never changes the maintained software. The vite config that vitest reads is also the one
    # `vite build` and the dev server read: outside vitest no plugin applies, no Python starts and the code served
    # or bundled is the project's own, also with no FlowGuard installed and with a flowguard.vitest.mjs of an
    # older init (no VITEST check of its own).
    root = vitest_home / 'built'
    _commit(root, {
        'package.json': '{"name":"built","private":true,"type":"module","devDependencies":{"vitest":"' + VITEST + '"}}',
        'vite.config.mjs': ("import { defineConfig } from 'vite';\n\nexport default defineConfig({\n  plugins: [],\n"
                            "  build: { lib: { entry: 'src/grade.ts', formats: ['es'], fileName: 'grade' } },\n});\n"),
        'src/grade.ts': '// flowguard: same PASS_MARK\nexport function grade(n: number): string {\n  return n >= 5 ? "pass" : "fail";\n}\n',
        'src/mark.ts': '// flowguard: same PASS_MARK\nexport function passed(n: number): boolean {\n  return n >= 5;\n}\n',
        'tests/grade.test.ts': ("import { expect, it } from 'vitest';\nimport { grade } from '../src/grade';\n"
                                "it('grades', () => expect(grade(5)).toBe('pass'));\n"),
    })
    assert _flowguard(root, 'init')[0] == 0
    _commit(root, message='wired')
    grade = root / 'src/grade.ts'
    grade.write_text(grade.read_text(encoding='utf-8').replace('n >= 5 ?', '!(n < 5) ?'), encoding='utf-8', newline='\n')
    assert _prepare(root)['status'] == 'on'  # a vitest run would record grade
    vite = vitest_home / 'node_modules/vite/bin/vite.js'
    assert vite.is_file(), 'vite comes with vitest'
    dev = ("const { createServer } = await import('vite');"
           "const server = await createServer({ root: process.cwd(), logLevel: 'silent', server: { middlewareMode: true } });"
           "const result = await server.transformRequest('/src/grade.ts'); await server.close();"
           "process.stdout.write(result.code);")
    wrapper = root / 'flowguard.vitest.mjs'
    current = wrapper.read_text(encoding='utf-8')
    older = current.replace('  if (!process.env.VITEST) return null;\n', '')
    assert older != current
    plain = {key: item for key, item in _environment().items() if key not in ('VITEST', 'TEST')}
    for label, text, python in (('current', current, sys.executable), ('current, no FlowGuard', current, str(root / 'no-python')),
                                ('older init', older, sys.executable)):
        wrapper.write_text(text, encoding='utf-8', newline='\n')
        env = dict(plain, FLOWGUARD_PYTHON=python)
        built = subprocess.run([_tool('node'), str(vite), 'build', '--outDir', 'dist-' + str(len(label))], cwd=root,
                               capture_output=True, encoding='utf-8', timeout=600, env=env)
        assert built.returncode == 0, (label, built.stdout + built.stderr)
        bundle = ''.join(path.read_text(encoding='utf-8') for path in (root / ('dist-' + str(len(label)))).rglob('*.*js'))
        assert '"pass"' in bundle and '__flowguard' not in bundle and '__fg_rt' not in bundle, (label, bundle)
        served = subprocess.run([_tool('node'), '--input-type=module', '-e', dev], cwd=root, capture_output=True,
                                encoding='utf-8', timeout=600, env=env)
        assert served.returncode == 0, (label, served.stdout + served.stderr)
        assert 'function grade' in served.stdout and '__flowguard' not in served.stdout, (label, served.stdout)
    wrapper.write_text(current, encoding='utf-8', newline='\n')
    code, text = _vitest(root, vitest_home)  # the same config in a vitest run: FlowGuard records and reports
    assert code == 0 and 'FlowGuard' in text, text


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
              return isoWeek(new Date(Date.UTC(year, 11, 28)));
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
    calendar = root / 'src/calendar.ts'
    calendar.write_text(calendar.read_text().replace('year, 11, 28', 'year, 11, 31'))
    run = subprocess.run([_tool('node'), str(vitest_home / 'node_modules/vitest/vitest.mjs'), 'run', '--reporter=default',
                          '--reporter=json', '--outputFile.json=results.json'], cwd=root, capture_output=True, encoding='utf-8',
                         timeout=600, env=_environment())
    text = display_text(run.stdout + run.stderr)
    # 2025 is next to the 2026 the test used (2026 itself agrees: both count 53); year=0 would be read as 1900
    red = ('red: same-name anchor ISO_WEEKS_IN_YEAR: year=2025, 2 copies: 1 copies return 52 (src/chart.ts:9 weeksInYear), 1 copies return 1 (src/calendar.ts:9 weekCount) -> first decide which copy is correct, then make the other copy agree with it; if intentionally different, use different names')
    assert run.returncode == 1 and red in text, text
    results = json.loads((root / 'results.json').read_text(encoding='utf-8'))
    cases = {case['title']: case for result in results['testResults'] for case in result['assertionResults']}
    assert cases['counts the weeks of this year']['status'] == 'passed', cases
    session = cases['FlowGuard execution side']             # the red is a failed test case in vitest's own results
    assert session['status'] == 'failed' and red.removeprefix('red: ') in display_text(''.join(session['failureMessages'])), session
    assert red in text.split('Test Files')[-1], text          # the block still follows the summary
    run = subprocess.run([_tool('node'), str(vitest_home / 'node_modules/vitest/vitest.mjs'), 'run', 'tests'], cwd=root,
                         capture_output=True, encoding='utf-8', timeout=600, env=_environment())
    text = display_text(run.stdout + run.stderr)            # a path filter leaves the session test out:
    assert run.returncode == 1 and red in text and 'FlowGuard execution side' not in text, text   # the teardown judges


def test_three_same_name_copies_are_counted_by_answer_and_the_red_leaves_the_choice(vitest_home):
    # Round 22 F1 (the Planning Tool's ISO weeks): two copies count 52 weeks in 2025, one counts 1. 4.2 told the
    # AI to change the copy the test reached, one of the two that agree, and to write a `distinct` TS cannot write.
    root = vitest_home / 'three-weeks'
    copy = '''
        // flowguard: sensor ISO_WEEKS_IN_YEAR
        export function %s(year: number): number {
          return isoWeek(new Date(Date.UTC(year, 11, %d)));
        }
    '''
    _commit(root, {
        'package.json': '{"name": "three-weeks", "private": true, "type": "module", "scripts": {"test": "vitest run"}, '
                        '"devDependencies": {"vitest": "' + VITEST + '"}}\n',
        'src/chart.ts': ISO_WEEK + copy % ('weeksInYear', 28),
        'src/planner.ts': ISO_WEEK + copy % ('isoWeeks', 28),
        'src/calendar.ts': ISO_WEEK + copy % ('weekCount', 28),
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
    calendar = root / 'src/calendar.ts'
    calendar.write_text(calendar.read_text().replace('year, 11, 28', 'year, 11, 31'))
    code, text = _vitest(root, vitest_home)
    red = list(dict.fromkeys(line for line in text.splitlines() if line.startswith('red: same-name anchor')))   # block and failed case
    assert code == 1 and red == [
        'red: same-name anchor ISO_WEEKS_IN_YEAR: year=2025, 3 copies: 2 copies return 52 (src/chart.ts:9 weeksInYear, src/planner.ts:9 isoWeeks), 1 copies return 1 (src/calendar.ts:9 weekCount) -> first decide which copy is correct, then make the remaining copies agree with it; if intentionally different, use different names'], text


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
    unverified = [line for line in text.splitlines() if line.startswith('unverified')]
    assert unverified[0].startswith('unverified 2 items (not passed)'), unverified                   # two places, two items
    assert 'unverified: B_LIMIT（web/src/b.ts:2)：not reached by any test' in unverified and 'unverified: B_LIMIT（web/src/c.ts:2)：not reached by any test' in unverified
    assert 'API_LIMIT' not in text and 'api/src' not in text, text      # no web test can reach the api package


def test_sealed_comparison_does_not_run_writes_or_database_clients_and_the_real_call_still_runs(vitest_home):
    root = _fees_project(vitest_home, 'effects')
    _sensor(root, 'src/effects/audited.ts', 'export function auditedFee', 'AUDITED_FEE')
    _sensor(root, 'src/effects/audited.ts', 'export function activeCount', 'ACTIVE_COUNT')
    code, text = _vitest(root, vitest_home)
    assert code == 0, text
    assert (root / 'audit.log').read_text(encoding='utf-8') == 'fee 4\n'         # only the test's own call wrote
    assert 'unverified 2 items (not passed)' in text, text
    assert 'unverified: AUDITED_FEE：uses imported or mutable binding appendFileSync' in text, text
    assert 'unverified: ACTIVE_COUNT：uses nonliteral constant prisma' in text, text


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


def test_source_only_comparison_strips_types_keeps_defaults_and_same_file_helpers(tmp_path):
    from flowguard.intent.vitest import ADAPTER, sealed_source
    source, why = sealed_source(b'''
        import './must-not-be-imported';
        const SCALE = { value: 3 } as const;
        function identity<T>(x: T): T { return x!; }
        export const fee = (x: number = 2): number =>
          (identity<number>(x) as number) * SCALE.value satisfies number;
    ''', 'src/fee.ts', 'fee')
    assert not why and 'import ' not in source, (source, why)
    run = subprocess.run([_tool('node'), str(ADAPTER / 'sealed.mjs')],
                         input=json.dumps([dict(source=source, fn='fee', args=[])]),
                         text=True, capture_output=True, check=True, timeout=30)
    assert json.loads(run.stdout) == [{'value': 6}], run.stdout + run.stderr


def _sealed(source, fn, args):
    from flowguard.intent.vitest import ADAPTER
    run = subprocess.run([_tool('node'), str(ADAPTER / 'sealed.mjs')], input=json.dumps([dict(source=source, fn=fn, args=args)]),
                         text=True, capture_output=True, check=True, timeout=30)
    [result] = json.loads(run.stdout)
    return result


# Design 4.5: a constant whose right side is built from number and string literals, signs, + - * / % ** and
# constants of the same file above it is folded with JavaScript's numbers by walking its syntax; nothing runs.
# Round 23: Planning Tool's `FTE_SHARE_FACTOR = 10 ** FTE_SHARE_DECIMALS` was "nonliteral", so roundFteShare
# was never compared and a careless change of it went unseen.
ROUND_SHARE = '\nfunction roundShare(value: number): number {\n  return Math.round(value * FTE_SHARE_FACTOR) / FTE_SHARE_FACTOR;\n}\n'


@pytest.mark.parametrize('constants', [
    'const FTE_SHARE_DECIMALS = 4;\nconst FTE_SHARE_FACTOR = 10 ** FTE_SHARE_DECIMALS;',
    'const BASE = 10;\nexport const DECIMALS = BASE - 6;\nconst FTE_SHARE_FACTOR = BASE ** (DECIMALS as number);',    # three
    'const FTE_SHARE_FACTOR = ((7 % 3) + 3) * 5000 / 2 - -0 + +0;',
    'const SECOND = 1000, DAY = 24 * 60 * 60 * SECOND;\nconst FTE_SHARE_FACTOR = DAY /* a day */ / 8640;',
])
def test_a_constant_built_from_literals_and_constants_above_it_is_folded_for_the_sealed_run(constants):
    from flowguard.intent.vitest import sealed_source
    source, why = sealed_source((constants + ROUND_SHARE).encode(), 'src/share.ts', 'roundShare')
    assert not why and 'const FTE_SHARE_FACTOR = 10000;' in source, (source, why)
    assert _sealed(source, 'roundShare', [0.01875]) == {'value': 0.0188}


def test_a_folded_constant_has_the_value_javascript_gives_it():
    from flowguard.intent.vitest import sealed_source
    source, why = sealed_source(b"const R = -7 % 3;\nconst P = 'FTE' + \"-\" + 'share\\t';\nexport function f() { return P + R; }",
                                'src/f.ts', 'f')
    assert not why and 'const R = -1;' in source, (source, why)       # Python's -7 % 3 is 2
    assert _sealed(source, 'f', []) == {'value': 'FTE-share\t-1'}


DOUBLED = "const S0 = '0123456789';\n" + ''.join(f'const S{n + 1} = S{n} + S{n};\n' for n in range(10))


@pytest.mark.parametrize('constants, reason', [
    ('const A = B + 1;\nconst B = A + 1;', 'uses A: B is not a number or text constant before it'),           # a cycle
    ('const A = 2 ** 300;', 'uses A: exponent 300 is above 64'),
    ('const A = 2 ** 64 * 2 ** 64 * 2 ** 64 * 2 ** 64 * 2;', 'uses A: result is above 2**256'),
    ('const A = 10 ** -4;', 'uses A: 10 ** -4 is not exact in floating point'),
    ('const A = 2 ** 0.5;', 'uses A: exponent 0.5 is not a whole number'),
    (DOUBLED + 'const A = S10;', 'uses A: uses S10: text is longer than 10000 characters'),
    ('const HUGE = 2 ** 300;\nconst A = HUGE / 2;', 'uses A: uses HUGE: exponent 300 is above 64'),
    ('const A = 1 / 0;', 'uses A: divides by zero'),
    ("const A = 'a' + 1;", 'uses A: cannot fold string + number'),
    ("const A = '6' * 2;", 'uses A: cannot fold string * number'),
    ('const A = 10n ** 2n;', 'uses A: cannot fold 10n'),
    ('let D = 4;\nconst A = 10 ** D;', 'uses A: D is not a number or text constant before it'),
    ('const A = 10 ** Number("4");', 'uses nonliteral constant A'),                           # a call is never run
])
def test_a_constant_that_does_not_fold_stays_not_compared_with_why(constants, reason):
    from flowguard.intent.vitest import sealed_source
    found = sealed_source((constants + '\nexport function f(x: number) { return x + A; }').encode(), 'src/f.ts', 'f')
    assert found == ('', reason), found


@pytest.mark.parametrize('body,reason', [
    ('return Date.now();', 'uses Date.now'),
    ('return new Date().getTime();', 'uses Date without arguments'),
    ('return Math.random();', 'uses Math.random'),
    ('return require("node:fs");', 'require is not defined'),
    ('return process.cwd();', 'process is not defined'),
    ('return fetch("https://example.invalid");', 'fetch is not defined'),
])
def test_source_only_comparison_has_no_modules_or_implicit_clock(body, reason):
    from flowguard.intent.vitest import ADAPTER
    run = subprocess.run([_tool('node'), str(ADAPTER / 'sealed.mjs')],
                         input=json.dumps([dict(source='function f() {' + body + '}', fn='f', args=[])]),
                         text=True, capture_output=True, check=True, timeout=30)
    [result] = json.loads(run.stdout)
    assert result['error']['name'] == 'ReferenceError' and reason in result['error']['message'], result


def test_records_twenty_distinct_primitive_calls_then_removes_its_wrapper(vitest_home):
    root = vitest_home / 'record-limit'
    _commit(root, {
        'package.json': '{"name":"record-limit","private":true,"type":"module","devDependencies":{"vitest":"' + VITEST + '"}}',
        'src/sample.ts': '''
            let calls = 0;
            // flowguard: same SAMPLE
            export function sample(n: number) { calls++; return n + 1; }
            export function callCount() { return calls; }
        ''',
        'tests/app.test.ts': '''
            import {it,expect} from 'vitest';
            import fs from 'node:fs';
            import path from 'node:path';
            import * as app from '../src/sample';
            it('records actual calls only, with the stated cap', () => {
              const before = app.sample;
              for (let i=0; i<25; i++) expect(app.sample(0)).toBe(1);
              for (let i=0; i<21; i++) expect(app.sample(i)).toBe(i+1);
              expect(app.sample).not.toBe(before);
              expect(before(30)).toBe(31);
              expect(app.callCount()).toBe(47);
              const dir = process.env.FLOWGUARD_VITEST_OBS;
              const records = fs.readdirSync(dir).filter(n=>n.endsWith('.jsonl')).flatMap(n=>
                fs.readFileSync(path.join(dir,n),'utf8').trim().split('\\n').filter(Boolean).map(JSON.parse));
              const calls = records.filter(r=>r.id?.endsWith(':sample') && 'args' in r);
              expect(calls).toHaveLength(20);
              expect(calls.map(r=>r.args[0])).toEqual(Array.from({length:20},(_,i)=>i));
            });
        ''',
    })
    assert _flowguard(root, 'init')[0] == 0
    _commit(root, message='recording fixture')
    code, text = _vitest(root, vitest_home)
    assert code == 0 and 'uses imported or mutable binding calls' in text, text


def test_nonprimitive_arguments_are_untouched_and_the_real_value_is_returned(vitest_home):
    root = vitest_home / 'primitive-only'
    _commit(root, {
        'package.json': '{"name":"primitive-only","private":true,"type":"module","devDependencies":{"vitest":"' + VITEST + '"}}',
        'src/sample.ts': '''
            // flowguard: same IDENTITY
            export function identity(value: unknown) { return value; }
        ''',
        'tests/app.test.ts': '''
            import {it,expect} from 'vitest';
            import {identity} from '../src/sample';
            it('does not inspect an object or proxy', () => {
              let touches = 0;
              const object = { get value() { touches++; return 2; }, toJSON() { touches++; return 2; } };
              const proxy = new Proxy(object, { get() { touches++; throw new Error('read proxy'); },
                ownKeys() { touches++; throw new Error('reflect proxy'); },
                getPrototypeOf() { touches++; throw new Error('read prototype'); } });
              expect(identity(proxy)).toBe(proxy);
              expect(identity(object)).toBe(object);
              expect(touches).toBe(0);
            });
        ''',
    })
    assert _flowguard(root, 'init')[0] == 0
    _commit(root, message='nonprimitive recording fixture')
    code, text = _vitest(root, vitest_home)
    assert code == 0 and 'only primitive JSON arguments and results are recorded' in text, text


@pytest.mark.parametrize('first', [0, 1])
def test_copy_baseline_colour_is_judged_per_input_whatever_the_first_witness(tmp_path, first):
    # Off x=0 the copies already differed at the baseline (before); at x=0 they agreed and differ now (red).
    # Which input the test called first changes neither colour (design 4.5: each input against the baseline).
    from flowguard.intent.config import load_config
    from flowguard.intent.vitest import judge
    _commit(tmp_path, {
        'src/a.ts': '// flowguard: same LIMIT\nexport function f(x: number) { return x === 0 ? 0 : 1; }\n',
        'src/b.ts': '// flowguard: same LIMIT\nexport function g(x: number) { return x === 0 ? 0 : 2; }\n',
    })
    path = tmp_path / 'src/a.ts'
    path.write_text(path.read_text().replace('? 0 : 1', '? 3 : 1'))
    data = json.loads(Path(_prepare(tmp_path)['plan']).read_text())
    records = [dict(id='typescript/src/a.ts:f', args=[first], result=3 if first == 0 else 1)]
    result = judge(load_config(tmp_path), data, records)
    assert len(result['red']) == len(result['before']) == 1, result
    assert result['red'][0].startswith('same-name anchor LIMIT: x=0, ') and 'x=1' not in result['red'][0], result
    assert result['before'][0].startswith('same-name anchor LIMIT: x=') and 'x=0' not in result['before'][0], result


def test_an_old_copy_difference_on_one_input_does_not_colour_a_new_one_on_another(tmp_path):
    # The copies already differed at 91; the change breaks 4..7, where both old copies returned false. The red
    # names the broken input closest to the real call (0): 4, the neighbour of the constant 3.
    from flowguard.intent.config import load_config
    from flowguard.intent.vitest import judge
    _commit(tmp_path, {
        'src/a.ts': '// flowguard: same LIMIT\nexport function f(days: number) { return days <= 3; }\n',
        'src/b.ts': '// flowguard: same LIMIT\nexport function g(days: number) { return days <= 3 || days === 91; }\n',
    })
    path = tmp_path / 'src/a.ts'
    path.write_text(path.read_text().replace('<= 3', '<= 7'))
    data = json.loads(Path(_prepare(tmp_path)['plan']).read_text())
    result = judge(load_config(tmp_path), data, [dict(id='typescript/src/a.ts:f', args=[0], result=True)])
    assert len(result['red']) == len(result['before']) == 1, result
    assert result['red'][0].startswith('same-name anchor LIMIT: days=4, ') and 'days=91' not in result['red'][0], result
    assert 'days=91' in result['before'][0] and not re.search(r'days=[4-7],', result['before'][0]), result


def test_a_copy_whose_baseline_cannot_be_sealed_does_not_hide_a_new_break_between_the_others(tmp_path):
    # f's baseline read an unknown setting; g and h agreed at the baseline and differ now at x=3.
    from flowguard.intent.config import load_config
    from flowguard.intent.vitest import judge
    _commit(tmp_path, {
        'src/a.ts': '// flowguard: same LIMIT\nexport function f(x: number) { return getSetting(x); }\n',
        'src/b.ts': '// flowguard: same LIMIT\nexport function g(x: number) { return x + 1; }\n',
        'src/c.ts': '// flowguard: same LIMIT\nexport function h(x: number) { return x + 1; }\n',
    })
    (tmp_path / 'src/a.ts').write_text((tmp_path / 'src/a.ts').read_text().replace('getSetting(x)', 'x + 1'))
    (tmp_path / 'src/b.ts').write_text((tmp_path / 'src/b.ts').read_text().replace('x + 1', 'x === 3 ? 0 : x + 1'))
    data = json.loads(Path(_prepare(tmp_path)['plan']).read_text())
    result = judge(load_config(tmp_path), data, [dict(id='typescript/src/b.ts:g', args=[2], result=3)])
    assert len(result['red']) == 1 and 'x=3' in result['red'][0] and 'src/c.ts:2 h' in result['red'][0], result
    assert any('baseline could not be compared' in line and 'x=3' in line for line in result['unverified']), result
    assert not result['before'], result


@pytest.mark.parametrize('reference', [False, True])
def test_an_old_copy_difference_does_not_hide_a_newly_broken_pair(tmp_path, reference):
    from flowguard.intent.config import load_config
    from flowguard.intent.vitest import judge
    _commit(tmp_path, {
        'src/chart.ts': '// flowguard: same LIMIT' + (' ref' if reference else '')
                        + '\nexport function chart(days: number) { return days <= 3; }\n',
        'src/calendar.ts': '// flowguard: same LIMIT\nexport function calendar(days: number) { return days <= 3; }\n',
        'src/report.ts': '// flowguard: same LIMIT\nexport function report(days: number) { return days < 3; }\n',
    })
    path = tmp_path / 'src/calendar.ts'
    path.write_text(path.read_text().replace('<= 3', '<= 4'))
    data = json.loads(Path(_prepare(tmp_path)['plan']).read_text())
    points = [point for entry in data['files'].values() for point in entry['points']]
    assert [point['fn'] for point in points if point['owner']] == (['chart'] if reference else [])
    result = judge(load_config(tmp_path), data, [dict(id='typescript/src/chart.ts:chart', args=[4], result=False)])
    assert len(result['red']) == len(result['before']) == 1, result
    assert 'days=4' in result['red'][0] and 'calendar' in result['red'][0], result
    assert 'days=3' in result['before'][0] and 'report' in result['before'][0], result
    assert ('reference src/chart.ts' in result['red'][0]) == reference, result
    assert ('reference src/chart.ts' in result['before'][0]) == reference, result
    assert 'distinct' not in result['red'][0], result


def test_copy_baseline_that_cannot_be_sealed_is_not_called_unchanged(tmp_path):
    from flowguard.intent.config import load_config
    from flowguard.intent.vitest import judge
    _commit(tmp_path, {
        'src/a.ts': '// flowguard: same LIMIT\nexport function f(x: number) { return getSetting(x); }\n',
        'src/b.ts': '// flowguard: same LIMIT\nexport function g(x: number) { return x + 1; }\n',
    })
    path = tmp_path / 'src/a.ts'
    path.write_text(path.read_text().replace('getSetting(x)', 'x + 2'))
    data = json.loads(Path(_prepare(tmp_path)['plan']).read_text())
    result = judge(load_config(tmp_path), data, [dict(id='typescript/src/a.ts:f', args=[2], result=4)])
    assert not result['red'] and not result['before'], result
    assert any('baseline could not be compared' in line for line in result['unverified']), result
    assert 'LIMIT' not in result['same_name_pairs']['compared'], result


def test_a_new_copy_is_absent_at_baseline_rather_than_an_unavailable_old_function(tmp_path):
    from flowguard.intent.config import load_config
    from flowguard.intent.vitest import judge
    _commit(tmp_path, {'src/a.ts': '// flowguard: same LIMIT\nexport function f(x: number) { return x + 1; }\n'})
    _write(tmp_path, {'src/b.ts': '// flowguard: same LIMIT\nexport function g(x: number) { return x + 2; }\n'})
    data = json.loads(Path(_prepare(tmp_path)['plan']).read_text())
    result = judge(load_config(tmp_path), data, [dict(id='typescript/src/a.ts:f', args=[2], result=3)])
    assert len(result['red']) == 1 and 'same-name anchor LIMIT' in result['red'][0], result
    assert not result['before'], result


def test_a_moved_copy_is_compared_with_its_version_at_the_old_path(tmp_path):
    # g already differed at 91; after `git mv` it is the same function at a new path, not a new copy.
    from flowguard.intent.config import load_config
    from flowguard.intent.vitest import judge
    _commit(tmp_path, {
        'src/a.ts': '// flowguard: same LIMIT\nexport function f(days: number) { return days <= 3; }\n',
        'src/b.ts': '// flowguard: same LIMIT\nexport function g(days: number) { return days <= 3 || days === 91; }\n',
    })
    _git(tmp_path, 'mv', 'src/b.ts', 'src/moved.ts')
    data = json.loads(Path(_prepare(tmp_path)['plan']).read_text())
    moved, = [point for entry in data['files'].values() for point in entry['points'] if point['fn'] == 'g']
    assert moved['rel'] == 'src/moved.ts' and not moved['old_skip'] and not moved['changed'], moved
    result = judge(load_config(tmp_path), data, [dict(id='typescript/src/a.ts:f', args=[0], result=True)])
    assert not result['red'] and len(result['before']) == 1, result
    assert 'days=91' in result['before'][0] and 'src/moved.ts' in result['before'][0], result


FEE = '''import { GRACE } from "./limits";
// A fee is due once the grace days have passed.
export function fee(days: number) {
  const late = days > GRACE;
  return !late;
}
'''


def test_a_function_moved_to_another_folder_reads_its_relative_imports_from_its_old_place(tmp_path):
    # src/a/fees.ts moves to src/b/fees.ts and changes. At the baseline its "./limits" was src/a/limits.ts
    # (GRACE = 3), now it is src/b/limits.ts (GRACE = 7): the baseline closed source reads a's literal.
    _commit(tmp_path, {
        'src/a/limits.ts': 'export const GRACE = 3;\n',
        'src/b/limits.ts': 'export const GRACE = 7;\n',
        'src/a/fees.ts': FEE,
    })
    _git(tmp_path, 'mv', 'src/a/fees.ts', 'src/b/fees.ts')     # Git sees the move: most lines stay the same
    _write(tmp_path, {'src/b/fees.ts': FEE.replace('return !late;', 'return !late || days === 100;')})
    data = json.loads(Path(_prepare(tmp_path)['plan']).read_text())
    moved, = [point for entry in data['files'].values() for point in entry['points'] if point['fn'] == 'fee']
    assert moved['rel'] == 'src/b/fees.ts' and moved['changed'] and not moved['skip'] and not moved['old_skip'], moved
    assert 'const GRACE = 7;' in moved['source'] and 'const GRACE = 3;' in moved['old_source'], moved


def test_recorded_inputs_alone_over_the_cap_still_leave_every_constant_a_place_in_vitest(tmp_path):
    # Four copies, 16 distinct far records each: 64 recorded inputs fill the cap alone. The constants 3 and 7
    # still get their place, and the cut is named.
    from flowguard.intent.config import load_config
    from flowguard.intent.vitest import judge
    names = 'fghk'
    _commit(tmp_path, {f'src/{name}.ts': f'// flowguard: same LIMIT\nexport function {name}(days: number) {{ return days <= 3; }}\n'
                       for name in names})
    path = tmp_path / 'src/f.ts'
    path.write_text(path.read_text().replace('<= 3', '<= 7'))
    data = json.loads(Path(_prepare(tmp_path)['plan']).read_text())
    records = [dict(id=f'typescript/src/{name}.ts:{name}', args=[1000 * (number + 1) + 10 * step], result=False)
               for number, name in enumerate(names) for step in range(16)]
    result = judge(load_config(tmp_path), data, records)
    assert len(result['red']) == 1 and 'days=7' in result['red'][0] and not result['before'], result
    assert any('LIMIT: compared on 64 inputs; 2 recorded inputs left out' in line for line in result['unverified']), result


@pytest.mark.parametrize('prefix,expression,name', [
    ('import { Number } from "./dep";', 'Number(x)', 'Number'),
    ('import { custom as Number } from "./dep";', 'Number(x)', 'Number'),
    ('import Number from "./dep";', 'Number(x)', 'Number'),
    ('import * as Math from "./dep";', 'Math.floor(x)', 'Math'),
    ('let Number = (x: number) => 99;', 'Number(x)', 'Number'),
    ('var Number = (x: number) => 99;', 'Number(x)', 'Number'),
    ('if (true) { var Number = (x: number) => 99; }', 'Number(x)', 'Number'),
    ('class Number { static value(x: number) { return 99; } }', 'Number.value(x)', 'Number'),
    ('function helper(x: number) { return x; } helper = (x: number) => 99;', 'helper(x)', 'helper'),
    ('function helper(x: number) { return x; } function replace() { helper = (x: number) => 99; }', 'helper(x)', 'helper'),
])
def test_sealed_source_does_not_replace_an_import_or_mutable_binding_with_a_builtin(prefix, expression, name):
    from flowguard.intent.vitest import sealed_source
    source, reason = sealed_source((prefix + '\nexport function f(x: number) { return ' + expression + '; }').encode(), 'src/f.ts', 'f')
    assert source == '' and reason == 'uses imported or mutable binding ' + name, (source, reason)


def test_a_literal_const_imported_from_a_relative_project_file_is_that_literal():
    from flowguard.intent.vitest import ADAPTER, sealed_source
    files = {'src/settings.ts': b'export const GRACE_DAYS = 3;\nexport const NAME = "late";\nexport const BUILT = GRACE_DAYS + 1;\n'
                                b'export const LIMITS = { a: 1 };\nexport const NEGATIVE = -2 as const;\n'}
    read = lambda path: files.get(path)
    source, reason = sealed_source(b'import { GRACE_DAYS as G, NEGATIVE } from "./settings";\n'
                                   b'export function allows(days: number) { return days <= G && days > NEGATIVE; }', 'src/policy.ts', 'allows', read)
    assert not reason and 'const G = 3;' in source and 'const NEGATIVE = -2;' in source and 'import' not in source, (source, reason)
    run = subprocess.run([_tool('node'), str(ADAPTER / 'sealed.mjs')],
                         input=json.dumps([dict(source=source, fn='allows', args=[3]), dict(source=source, fn='allows', args=[4])]),
                         capture_output=True, text=True, check=True, timeout=30)
    assert json.loads(run.stdout) == [{'value': True}, {'value': False}], run.stdout + run.stderr
    for line, name in (('import { BUILT } from "./settings";', 'BUILT'), ('import { LIMITS } from "./settings";', 'LIMITS'),
                       ('import { MISSING } from "./settings";', 'MISSING'), ('import { GRACE_DAYS } from "settings";', 'GRACE_DAYS'),
                       ('import type { GRACE_DAYS } from "./settings";', 'GRACE_DAYS'), ('import { GRACE_DAYS } from "./other";', 'GRACE_DAYS')):
        closed, why = sealed_source((line + f'\nexport function f(x: number) {{ return x <= {name} as any; }}').encode(), 'src/policy.ts', 'f', read)
        assert closed == '' and why == 'uses imported or mutable binding ' + name, (line, closed, why)
    # Without a reader, as before, nothing imported is available.
    closed, why = sealed_source(b'import { GRACE_DAYS } from "./settings";\nexport function f(x: number) { return x <= GRACE_DAYS; }', 'src/policy.ts', 'f')
    assert closed == '' and why == 'uses imported or mutable binding GRACE_DAYS'


def test_an_imported_file_is_read_once_per_plan_and_only_for_names_a_function_reads():
    from flowguard.intent.vitest import sealed_source
    files = {'src/constants.ts': ''.join(f'export const C{index} = {index};\n' for index in range(300)).encode()}
    names = [f'C{index}' for index in range(0, 300, 10)]
    policy = ('import { ' + ', '.join(names) + ' } from "./constants";\n'
              + ''.join(f'export function f{j}(x: number) {{ return x <= C{(j % 30) * 10}; }}\n' for j in range(50))
              + 'export function plain(x: number) { return x <= 2; }\n').encode()
    reads = []
    def read(path):
        if path in files:
            reads.append(path)
        return files.get(path)
    tables = {}
    closed, why = sealed_source(policy, 'src/policy.ts', 'plain', read, tables)
    assert not why and reads == []              # no imported name is read: the file is not even opened
    for j in range(50):
        closed, why = sealed_source(policy, 'src/policy.ts', f'f{j}', read, tables)
        assert not why and f'const C{(j % 30) * 10} = {(j % 30) * 10};' in closed and closed.count('const ') == 1, (closed, why)
    assert reads == ['src/constants.ts']        # one read and one parse for the whole plan


def test_an_extensionless_import_resolves_in_the_order_vite_does():
    # Vite tries .mjs, .js, .mts, .ts, .jsx, .tsx: with both settings.js and settings.ts the .js file is the one
    # that runs; a file Vite would pick that is not a script (settings.json) is never passed over for another.
    from flowguard.intent.vitest import sealed_source
    source = b'import { GRACE } from "./settings";\nexport function f(x: number) { return x <= GRACE; }'
    for files, expected in (({'src/settings.js': b'export const GRACE = 3;\n', 'src/settings.ts': b'export const GRACE = 9;\n'}, 'const GRACE = 3;'),
                            ({'src/settings.ts': b'export const GRACE = 9;\n'}, 'const GRACE = 9;')):
        closed, why = sealed_source(source, 'src/policy.ts', 'f', files.get)
        assert not why and expected in closed, (files, closed, why)
    closed, why = sealed_source(source, 'src/policy.ts', 'f', {'src/settings.json': b'{"GRACE": 3}\n',
                                                               'src/settings/index.ts': b'export const GRACE = 9;\n'}.get)
    assert closed == '' and why == 'uses imported or mutable binding GRACE', (closed, why)


def test_an_unused_aliased_import_does_not_hide_the_real_builtin():
    from flowguard.intent.vitest import sealed_source
    source, reason = sealed_source(b'import { Number as Custom } from "./dep"; export function f(x: string) { return Number(x); }', 'src/f.ts', 'f')
    assert not reason and 'return Number(x)' in source and 'Custom' not in source, (source, reason)


def test_negative_zero_is_not_encoded_as_positive_zero(vitest_home):
    root = vitest_home / 'negative-zero'
    _commit(root, {
        'package.json': '{"name":"negative-zero","private":true,"type":"module","devDependencies":{"vitest":"' + VITEST + '"}}',
        'src/sample.ts': '''
            // flowguard: same IDENTITY_NUMBER
            export function identity(x: number) { return x; }
            // flowguard: same NEGATIVE_NUMBER
            export function negative(x: number) { return -0; }
        ''',
        'tests/app.test.ts': '''
            import {it,expect} from 'vitest'; import fs from 'node:fs'; import path from 'node:path';
            import {identity,negative} from '../src/sample';
            it('preserves real negative zero without claiming comparable transport', () => {
              expect(Object.is(identity(-0),-0)).toBe(true);
              expect(Object.is(negative(1),-0)).toBe(true);
              expect(identity(1)).toBe(1);
              expect(identity(-Number.MIN_VALUE)).toBe(-Number.MIN_VALUE);
              const dir=process.env.FLOWGUARD_VITEST_OBS;
              const records=fs.readdirSync(dir).filter(n=>n.endsWith('.jsonl')).flatMap(n=>
                fs.readFileSync(path.join(dir,n),'utf8').trim().split('\\n').filter(Boolean).map(JSON.parse));
              const values=records.filter(r=>'args' in r);
              expect(values).toHaveLength(2); expect(values[0].args).toEqual([1]); expect(values[0].result).toBe(1);
              expect(values[1].args).toEqual([-Number.MIN_VALUE]); expect(values[1].result).toBe(-Number.MIN_VALUE);
              expect(records.filter(r=>r.reason)).toHaveLength(2);
            });
        ''',
    })
    assert _flowguard(root, 'init')[0] == 0
    _commit(root, message='negative zero fixture')
    code, text = _vitest(root, vitest_home)
    assert code == 0 and 'only primitive JSON arguments and results are recorded' in text, text
    from flowguard.intent.vitest import ADAPTER
    run = subprocess.run([_tool('node'), str(ADAPTER / 'sealed.mjs')],
                         input=json.dumps([dict(source='function f(x) { return -0; }', fn='f', args=[1])]),
                         capture_output=True, text=True, check=True, timeout=30)
    assert json.loads(run.stdout) == [{'reason': 'negative zero is not compared'}], run.stdout


def test_unsealable_imports_still_leave_real_primitive_calls_for_intent_rules(vitest_home):
    root = vitest_home / 'imported-rule'
    _commit(root, {
        'package.json': '{"name":"imported-rule","private":true,"type":"module","devDependencies":{"vitest":"' + VITEST + '"}}',
        'src/sample.ts': '''
            import {Number} from './dep';
            // flowguard: same CALC
            export function calc(x: number) { return x + 1; }
        ''',
        'src/dep.ts': 'export const Number = (x: number) => 99;\n',
        'tests/app.test.ts': "import {it,expect} from 'vitest'; import {calc} from '../src/sample'; it('actual result',()=>expect(calc(5)).toBe(6));\n",
        'tests/intent/calc.py': '''
            from flowguard.intent import rule
            @rule('CALC_RULE', decides='next value', fields={'x': int}, anchor='CALC', source='assumed: the result is the input plus one')
            def expected(x):
                return x + 1
        ''',
    })
    assert _flowguard(root, 'init')[0] == 0
    _commit(root, message='intent fixture baseline')
    path = root / 'src/sample.ts'
    path.write_text(path.read_text().replace('return x + 1', 'return Number(x)'))
    path = root / 'tests/app.test.ts'
    path.write_text(path.read_text().replace('toBe(6)', 'toBe(99)'))
    code, text = _vitest(root, vitest_home)
    assert code == 1 and 'red: CALC_RULE: x=5 -> rule 6, code 99' in text, text
    assert 'uses imported or mutable binding Number' in text, text


def test_an_intent_rule_citing_a_rule_has_the_source_gate_of_pytest(vitest_home):
    # Stage 3: the TS observation path checked a rule's expectations without its source; a source this change broke
    # is red there as in pytest's intent items, one already broken at task start is before and fails nothing.
    root = vitest_home / 'cited-rule'
    _commit(root, {
        'package.json': '{"name":"cited-rule","private":true,"type":"module","devDependencies":{"vitest":"' + VITEST + '"}}',
        'pyproject.toml': '[tool.flowguard]\nauthority_docs = ["SPEC.md"]\n',
        'SPEC.md': 'The next value is the input plus one.\n',
        '.flowguard/rules.toml': '[rule.next]\ntext = "The next value is the input plus one."\n'
                                 "source = 'doc SPEC.md \"The next value is the input plus one.\"'\n",
        'src/sample.ts': '''
            // flowguard: same CALC
            export function calc(x: number) { return x + 1; }
        ''',
        'tests/app.test.ts': "import {it,expect} from 'vitest'; import {calc} from '../src/sample'; it('actual result',()=>expect(calc(5)).toBe(6));\n",
        'tests/intent/calc.py': '''
            from flowguard.intent import rule
            @rule('CALC_RULE', decides='next value', fields={'x': int}, anchor='CALC', source='rule.next')
            def expected(x):
                return x + 1
        ''',
    })
    assert _flowguard(root, 'init')[0] == 0
    _commit(root, message='intent fixture baseline')
    code, text = _vitest(root, vitest_home)
    assert code == 0 and 'CALC_RULE' not in text, text
    (root / 'SPEC.md').write_text('The next value is the input plus two.\n', encoding='utf-8')
    code, text = _vitest(root, vitest_home)
    gone = 'CALC_RULE: rule.next: SPEC.md does not contain "The next value is the input plus one." -> quote the document exactly'
    assert code == 1 and 'red: ' + gone in text, text
    _commit(root, message='the quote is gone at the start of the next task')
    assert _flowguard(root, 'new-task')[0] == 0
    code, text = _vitest(root, vitest_home)
    assert code == 0 and 'before: ' + gone in text and 'red: ' + gone not in text, text


def test_a_real_same_file_helper_named_number_does_not_replace_the_comparison_codec():
    from flowguard.intent.vitest import ADAPTER, sealed_source
    source, reason = sealed_source(b'function Number(x: number) { return x + 10; } export function f(x: number) { return Number(x); }', 'src/f.ts', 'f')
    assert not reason, reason
    run = subprocess.run([_tool('node'), str(ADAPTER / 'sealed.mjs')],
                         input=json.dumps([dict(source=source, fn='f', args=[5])]), capture_output=True,
                         text=True, check=True, timeout=30)
    assert json.loads(run.stdout) == [{'value': 15}], run.stdout + run.stderr


def test_literal_arithmetic_uses_the_existing_folder_without_running_calls():
    import ast
    from flowguard.intent.vitest import ADAPTER, sealed_source
    from flowguard.structure.api import _expression
    cached = ast.dump(_expression('HOURS * MINUTES * 60 * 1000'))
    source, reason = sealed_source(b'''
        const HOURS = 24;
        const MINUTES = 60;
        const MS_PER_DAY = HOURS * MINUTES * 60 * 1000;
        const ROUNDED = 9007199254740992 + 1 - 9007199254740992;
        export function duration(days: number) { return days * MS_PER_DAY + ROUNDED; }
    ''', 'src/duration.ts', 'duration')
    assert not reason and 'const MS_PER_DAY = 86400000;' in source and 'const ROUNDED = 0;' in source, (source, reason)
    run = subprocess.run([_tool('node'), str(ADAPTER / 'sealed.mjs')],
                         input=json.dumps([dict(source=source, fn='duration', args=[2])]), capture_output=True,
                         text=True, check=True, timeout=30)
    assert json.loads(run.stdout) == [{'value': 172800000}], run.stdout
    assert ast.dump(_expression('HOURS * MINUTES * 60 * 1000')) == cached
    for expression in ('Date.now()', 'Math.floor(2)', 'config.value', 'getHours() * 60'):
        source, reason = sealed_source(('const TIME = ' + expression + '; export function f(x: number) { return x * TIME; }').encode(), 'src/f.ts', 'f')
        assert not source and reason == 'uses nonliteral constant TIME', (source, reason)


def test_prepare_replaces_cached_timing_and_old_and_new_wrappers_share_one_value(tmp_path):
    from flowguard.intent.vitest import ADAPTER
    _commit(tmp_path, {'src/a.ts': '// flowguard: same LIMIT\nexport function f(x: number) { return x > 3; }\n'})
    first = _prepare(tmp_path)
    path = Path(first['plan'])
    data = json.loads(path.read_text())
    data['prepare_seconds'] = 9999
    path.write_text(json.dumps(data))
    second = _prepare(tmp_path)
    data = json.loads(path.read_text())
    assert second['plan'] == first['plan'] and second['seconds'] == data['prepare_seconds'] and 0 <= second['seconds'] < 9999
    script = '''
        import {flowguardPlugin} from @INDEX@;
        const options = {plan: @PLAN@, python: ['python'], root: @ROOT@};
        flowguardPlugin(options).config();
        const legacy = Number(process.env.FLOWGUARD_VITEST_PREPARE_SECONDS);
        flowguardPlugin({...options, prepareSeconds: @SECONDS@}).config();
        console.log(JSON.stringify([legacy, Number(process.env.FLOWGUARD_VITEST_PREPARE_SECONDS)]));
    '''.replace('@INDEX@', json.dumps((ADAPTER / 'index.mjs').as_uri())).replace('@PLAN@', json.dumps(str(path))).replace('@ROOT@', json.dumps(str(tmp_path))).replace('@SECONDS@', json.dumps(second['seconds']))
    run = subprocess.run([_tool('node'), '--input-type=module', '-e', script], text=True, capture_output=True, check=True, timeout=30)
    assert json.loads(run.stdout) == [second['seconds'], second['seconds']], run.stdout + run.stderr


def test_existing_wrapper_without_the_timing_argument_receives_this_preparations_time(vitest_home):
    root = vitest_home / 'old-wrapper-timing'
    _commit(root, {
        'package.json': '{"name":"old-wrapper-timing","private":true,"type":"module","devDependencies":{"vitest":"' + VITEST + '"}}',
        'src/sample.ts': '// flowguard: same VALUE\nexport function value(x: number) { return x; }\n',
        'tests/app.test.ts': '''
            import {it,expect} from 'vitest'; import fs from 'node:fs';
            import {value} from '../src/sample';
            it('keeps the value and receives current preparation time', () => {
              expect(value(4)).toBe(4);
              const plan=JSON.parse(fs.readFileSync(process.env.FLOWGUARD_VITEST_PLAN,'utf8'));
              const seconds=Number(process.env.FLOWGUARD_VITEST_PREPARE_SECONDS);
              expect(seconds).toBeGreaterThan(0); expect(seconds).toBe(plan.prepare_seconds);
            });
        ''',
    })
    assert _flowguard(root, 'init')[0] == 0
    wrapper = root / 'flowguard.vitest.mjs'
    wrapper.write_text(wrapper.read_text().replace(', prepareSeconds: answer.seconds', ''))
    assert 'prepareSeconds' not in wrapper.read_text()
    _commit(root, message='legacy wrapper fixture')
    code, text = _vitest(root, vitest_home)
    assert code == 0, text
