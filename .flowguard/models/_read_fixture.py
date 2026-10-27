"""Read shows each requested component, its five static facets and model contracts completely, without imports.

The input features are valid adversarial observations, not rejected requests.
Literal abstract outputs witness the promises; conformance checks the same
predicates on render_show itself, over fresh copies of one real project.
"""
from dataclasses import dataclass, replace
from pathlib import Path
import importlib.util
import re
import shutil
import sys
import tempfile
from flowguard.core import FunctionResult, Invariant
from flowguard.explorer import Explorer
from flowguard.kit import Feature, feature_conformance, feature_explorer
from flowguard.map.common import DEFAULT_IGNORE
from flowguard.map.inventory import build_inventory
from flowguard.map.views import render_show
from flowguard.workflow import Workflow
PURPOSE = 'Explain read probe behavior.'
MODEL_LINE = 'model read_probe: Explain read probe behavior. (2 rules, 2 known-bad, 1 tests)'
LARGE_TESTS = 300
LARGE_MODEL_LINE = MODEL_LINE.replace('1 tests', f'{LARGE_TESTS} tests')
FACETS = ('purpose', 'rules', 'known-bad', 'code', 'tests')
MODEL_SOURCE = '"""Explain read probe behavior."""\nfrom pathlib import Path\nPath(__file__).parents[2].joinpath("model_import.marker").write_text("imported")\nMODEL_ID = "read_probe"\nCOMPONENTS = ["alpha"]\nIMPLEMENTED_BY = {"Run": "alpha.py:run"}\nTESTED_BY = {"works": ["tests/test_alpha.py:test_run"]}\nRULES = [Invariant("works", "works", None), Invariant("stable", "stable", None)]\ndef build_explorer(): return Explorer(Workflow(()), (0,), (), invariants=RULES)\ndef broken_variants(): return {"one": None, "two": None}\n'
_PROBE_HEAD = '"""Probe."""\nfrom flowguard.core import Invariant\nfrom flowguard.explorer import Explorer\nfrom flowguard.workflow import Workflow\n'
_PROBE_EXPLORER = 'def _explorer(kind=""):\n    return Explorer(Workflow(()), (0,), (), invariants=RULES)\n'
PROBE_FILES = {'helper_split': {'.flowguard/models/_probe_common.py': _PROBE_HEAD + 'def _ok(state, trace): return True\nA = Invariant("a_rule", "a holds", _ok)\nB = Invariant("b_rule", "b holds", _ok)\nBOTH = (A, B)\n', '.flowguard/models/probe_child.py': _PROBE_HEAD + 'from _probe_common import A, B\nMODEL_ID = "probe_child"\nPARENT = "probe_parent"\nIMPLEMENTED_BY = {"Run": "alpha.py:run"}\nTESTED_BY = {"a_rule": ["tests/test_alpha.py:test_run"]}\ndef _explorer():\n    return Explorer(Workflow(()), (0,), (), invariants=(A, B))\ndef build_explorer(): return _explorer()\ndef broken_variants(): return {"child_bad": _explorer()}\n', '.flowguard/models/probe_parent.py': _PROBE_HEAD + 'from _probe_common import BOTH\nMODEL_ID = "probe_parent"\nIMPLEMENTED_BY = {"Run": "alpha.py:run"}\ndef _explorer():\n    return Explorer(Workflow(()), (0,), (), invariants=BOTH)\ndef build_explorer(): return _explorer()\ndef broken_variants(): return {"parent_bad": _explorer()}\n'}, 'wrapper': {'.flowguard/models/probe_wrapper.py': _PROBE_HEAD + ('MODEL_ID = "probe_wrapper"\nIMPLEMENTED_BY = {"Run": "alpha.py:run"}\ndef _rule(name, text):\n    return Invariant(name, text, lambda state, trace: True)\nRULES = (_rule("x_rule", "x holds"), _rule("y_rule", "y holds"))\n' + _PROBE_EXPLORER + 'def build_explorer(): return _explorer()\ndef broken_variants():\n    return {name: _explorer(name) for name in ("x_bad", "y_bad")}\n')}, 'loops': {'.flowguard/models/probe_tuple.py': _PROBE_HEAD + ('MODEL_ID = "probe_tuple"\nIMPLEMENTED_BY = {"Run": "alpha.py:run"}\nRULES = (Invariant("t_rule", "t holds", lambda state, trace: True),)\n' + _PROBE_EXPLORER + 'def build_explorer(): return _explorer()\ndef broken_variants():\n    return {name: _explorer(kind) for name, kind in (("a_bad", "a"), ("b_bad", "b"))}\n'), '.flowguard/models/probe_loop.py': _PROBE_HEAD + ('MODEL_ID = "probe_loop"\nIMPLEMENTED_BY = {"Run": "alpha.py:run"}\nRULES = (Invariant("l_rule", "l holds", lambda state, trace: True),)\nFEATURES = {"one": ("x", "m_one", 1), "two": ("y", "m_two", 2)}\nEXPECTED = {"alpha": 1, "beta": 2}\n' + _PROBE_EXPLORER + 'def build_explorer(): return _explorer()\ndef broken_variants():\n    result = {}\n    for _, mutation, _ in FEATURES.values():\n        result[mutation] = _explorer(mutation)\n    for case in EXPECTED:\n        result[f"ignore_{case}"] = _explorer(case)\n    return result\n')}, 'kit': {'.flowguard/models/probe_kit.py': '"""Probe."""\nfrom flowguard.kit import Feature, feature_explorer, feature_variants\nMODEL_ID = "probe_kit"\nIMPLEMENTED_BY = {"Run": "alpha.py:run"}\nFEATURES = (Feature("d_one", True, ("c1",), lambda plan: plan), Feature("d_two", True, ("c2",), lambda plan: plan),\n            Feature("b_one", False, (), lambda plan: plan))\ndef build_explorer(): return feature_explorer(FEATURES, codes="first")\ndef broken_variants(): return feature_variants(FEATURES, codes="first")\n'}}
PROBE_TRUTH = {'helper_split': (('probe_child', (('a_rule', 'a holds'), ('b_rule', 'b holds')), ('child_bad',), ('a_rule',)), ('probe_parent', (('a_rule', 'a holds'), ('b_rule', 'b holds')), ('parent_bad',), ())), 'wrapper': (('probe_wrapper', (('x_rule', 'x holds'), ('y_rule', 'y holds')), ('x_bad', 'y_bad'), ()),), 'loops': (('probe_loop', (('l_rule', 'l holds'),), ('ignore_alpha', 'ignore_beta', 'm_one', 'm_two'), ()), ('probe_tuple', (('t_rule', 't holds'),), ('a_bad', 'b_bad'), ())), 'kit': (('probe_kit', (('benign_features_neutral', 'removing legal benign features does not change the verdict'), ('clean_input_accepted', 'an input with no defect is accepted'), ('each_defect_rejected', 'an input with any defect is rejected'), ('first_defect_reported', 'a rejection reports the declared codes of the expected defects')), ('ignores_d_one', 'rejects_b_one', 'reports_last_defect_only'), ()),)}
KIT_CASES = 'cases: 2 defects (d_one, d_two), 1 benign (b_one)'

@dataclass(frozen=True)
class ReadCase:
    import_marker: bool = False
    missing_summary: bool = False
    component: str | None = None
    probe: str = ''
    layered: bool = False
    relied: bool = False
    flowing: bool = False
    sources: bool = False
    review: bool = False
    query: str = ''
FEATURES = (Feature('import_time_marker', False, (), lambda case: replace(case, import_marker=True)), Feature('missing_summary', False, (), lambda case: replace(case, missing_summary=True)), Feature('large_component', False, (), lambda case: replace(case, component='alpha')), Feature('late_upper_component', False, (), lambda case: replace(case, layered=True)), Feature('relied_component', False, (), lambda case: replace(case, relied=True, component='beta'), conflicts=('large_component',)), Feature('component_in_flow', False, (), lambda case: replace(case, flowing=True, component='beta'), conflicts=('large_component',)), Feature('helper_split_model', False, (), lambda case: replace(case, probe='helper_split'), exclusive=True), Feature('wrapper_rule_model', False, (), lambda case: replace(case, probe='wrapper'), exclusive=True), Feature('loop_built_variants_model', False, (), lambda case: replace(case, probe='loops'), exclusive=True), Feature('kit_model', False, (), lambda case: replace(case, probe='kit'), exclusive=True), Feature('review_fixture', False, (), lambda case: replace(case, review=True), exclusive=True), Feature('inflected_query', False, (), lambda case: replace(case, query='expire'), exclusive=True))

@dataclass(frozen=True)
class ReadObservation:
    case: ReadCase
    text: str
    imported: bool = False
    runtime: tuple = ()

def _names(observation):
    if observation.case.review or observation.case.query:
        return True
    wanted = (observation.case.component,) if observation.case.component else ('alpha', 'beta')
    components = all(re.search(r'^## ' + re.escape(cid) + r' \[', observation.text, re.M) for cid in wanted)
    model = observation.case.component not in (None, 'alpha') or MODEL_LINE in observation.text or LARGE_MODEL_LINE in observation.text
    return bool(components and model)


def _focused(observation):
    """The requested component is never hidden: its heading and own five facets are always printed."""
    cid = observation.case.component
    if cid is None:
        return True
    match = re.search(f'^## {cid} \\[[^\\n]*\\n((?:  [^\\n]*\\n?)*)', observation.text, re.M)
    if match is None or f'not shown: {cid}' in observation.text:
        return False
    own = [line.strip().partition(':')[0] for line in match.group(1).splitlines() if line.startswith('  ') and (not line.startswith('   '))]
    return own[:len(FACETS)] == list(FACETS)

def _model_contract(observation):
    if observation.case.review or observation.case.query:
        return True
    rows = tuple((line.strip() for line in observation.text.splitlines() if line.lstrip().startswith('model read_probe:')))
    expected = LARGE_MODEL_LINE if observation.case.component else MODEL_LINE
    if observation.case.component not in (None, 'alpha'):
        return not rows
    return all((row == expected for row in rows)) and (bool(rows) or 'truncated' in observation.text or 'shortened' in observation.text)

def _static(observation):
    """Static counts and names equal the explorer's invariants and broken_variants() keys."""
    lines = observation.text.splitlines()
    complete = 'truncated' not in observation.text and 'shortened' not in observation.text
    for mid, rules, bads in observation.runtime:
        rows = [index for index, line in enumerate(lines) if line.strip().startswith(f'model {mid}: ')]
        if complete and (not rows):
            return False
        for index in rows:
            counts = re.search('\\((\\S+) rules, (\\S+) known-bad', lines[index])
            if counts is None or counts.groups() != (str(len(rules)), str(len(bads))):
                return False
            facets = {line.strip().partition(': ')[0]: line.strip().partition(': ')[2] for line in lines[index + 1:index + 6]}
            if 'rules' in facets:
                shown = {item.partition(': ')[0] for item in facets['rules'].split('; ') if not item.startswith('cases: ')}
                if shown != set(rules) or {item for item in facets['known-bad'].split(', ')} != set(bads):
                    return False
    return True
RELIED_LINE = 'relies on: model read_probe (stable, works) via alpha: run'

def _relied(observation):
    """read --component beta names the rules of alpha's model that beta's code calls."""
    if not observation.case.relied or 'shortened' in observation.text or 'truncated' in observation.text:
        return True
    return any((line.strip() == RELIED_LINE for line in observation.text.splitlines()))
COVERAGE_LINE = 'coverage: entrypoints 3/4 explained (model 1, test 1, reason 1); state writers 0/0 explained (model 0, test 0, reason 0)'

def _by_source(observation):
    """The coverage line counts explanations by model, test and reason; they add up to the explained count."""
    if not observation.case.sources:
        return True
    line = next((row for row in observation.text.splitlines() if row.startswith('coverage:')), '')
    parts = re.findall('(\\d+)/(\\d+) explained \\(model (\\d+), test (\\d+), reason (\\d+)\\)', line)
    return line == COVERAGE_LINE and len(parts) == 2 and all((int(done) == int(model) + int(test) + int(reason) for done, _, model, test, reason in parts))
FLOW_LINE = 'flows: chain (step 1 of 2; model read_probe: stable, works)'

def _flows(observation):
    """read --component X lists each flow with a step in X, with the flow's model and its rules."""
    if not observation.case.flowing or 'shortened' in observation.text or 'truncated' in observation.text:
        return True
    return any((line.strip() == FLOW_LINE for line in observation.text.splitlines()))

def _layer_order(observation):
    """Top-level components appear top-down by layer; within a layer the map.json order holds."""
    if not observation.case.layered:
        return True
    rank = {'beta': 0, 'alpha': 1}
    shown = [cid for cid in dict.fromkeys(re.findall('^## (\\S+) \\[', observation.text, re.M)) if cid in rank]
    return shown == sorted(shown, key=rank.get)
REVIEW_FALSE_STRENGTHS = ('no dependency cycles', 'every flow has a model', 'every state writer explained')
REVIEW_HUB = 'hub'
REVIEW_FILES = {'app.py': 'import store\ndef run(): return store.save()\n', 'store.py': 'import app\ndef save(): return True\n', 'hub.py': 'import lib1\nimport lib2\nimport lib3\ndef run(): return lib1.run() and lib2.run() and lib3.run()\n', 'lib1.py': 'class Box:\n    def put(self, value):\n        self.value = value\ndef run(): return Box()\n', 'lib2.py': 'def run(): return True\n', 'lib3.py': 'def run(): return True\n', 'u1.py': 'import hub\ndef run(): return hub.run()\n', 'u2.py': 'import hub\ndef run(): return hub.run()\n', 'u3.py': 'import hub\ndef run(): return hub.run()\n'}
REVIEW_TEXT = '# read fixture review: 11 components, 1 models, 1 flows; architecture: 1 error(s), 3 warning(s), 0 accepted debt(s)\nstrengths: no layer violations; one owner per responsibility, state and side effect; no accepted debts\ndefects:\n  ERROR dependency_cycle x1: app: app <-> store\n  WARN  untested_component x10: app: no tests mapped\ncomponents: id layer files/loc duties uses/used-by models(rules/known-bad) tests(bound/functions) unexplained\n  hub - 1/4 7 3/3 0(0/0) 0/0 0\noptimise next:\n  1. fix dependency_cycle app: app <-> store; references/architecture_review.md (dependency_cycle)\n  2. split hub: hub (used by 3, uses 3, 7 duties, 4 loc); references/routes.md#Add or split a component, as a target\n  3. explain lib1: 1 unexplained entrypoints and state writers; python -m flowguard read --component lib1\n  4. model flow trip: no model; references/map_format.md'

def _review_section(text, heading):
    lines = text.splitlines()
    start = next((index for index, line in enumerate(lines) if line.startswith(heading)), None)
    if start is None:
        return None
    rows = []
    for line in lines[start + 1:]:
        if not line.startswith('  '):
            break
        rows.append(line.strip())
    return rows

def _ranked(observation):
    """Every ERROR defect is a `fix <code>` step, and every fix step comes before any other step."""
    if not observation.case.review:
        return True
    defects, steps = (_review_section(observation.text, 'defects:'), _review_section(observation.text, 'optimise next:'))
    if defects is None or steps is None:
        return False
    errors = {row.split()[1] for row in defects if row.startswith('ERROR ')}
    fixes = [index for index, row in enumerate(steps) if re.match('\\d+\\. fix ', row)]
    named = {row.split()[2] for row in steps if re.match('\\d+\\. fix ', row)}
    return bool(errors) and errors <= named and (fixes == list(range(len(fixes))))

def _true_strengths(observation):
    """No strength line claims what the fixture contradicts."""
    if not observation.case.review:
        return True
    line = next((row for row in observation.text.splitlines() if row.startswith('strengths: ')), None)
    if line is None:
        return False
    claimed = {item.strip() for item in line[len('strengths: '):].split(';')}
    return not claimed & set(REVIEW_FALSE_STRENGTHS)

def _recipes(observation):
    """Every optimise-next step names a references/... recipe or a python -m flowguard command."""
    if not observation.case.review:
        return True
    steps = _review_section(observation.text, 'optimise next:')
    return bool(steps) and all(('references/' in row or 'python -m flowguard' in row for row in steps))
FIND_DUTY = 'reject expired tokens'

def _word_forms(observation):
    """read --find ranks the component whose duty differs from the query only by a common word ending first."""
    if not observation.case.query:
        return True
    return observation.text.splitlines()[:1] == ['alpha']

def _summary(observation):
    if not observation.case.missing_summary or not re.search('^## alpha \\[', observation.text, re.M):
        return True
    alpha = observation.text.split('## alpha [', 1)[1].split('\n## ', 1)[0]
    return '(no summary yet)' in alpha

def _abstract(case, file_order=False):
    if case.review:
        return ReadObservation(case, REVIEW_TEXT)
    if case.query:
        return ReadObservation(case, 'alpha')
    if case.probe:
        rows, details = ([], [])
        for mid, rules, bads, _keys in PROBE_TRUTH[case.probe]:
            row = f'model {mid}: Probe. ({len(rules)} rules, {len(bads)} known-bad, 0 tests)'
            rows.append('  ' + row)
            cases = '; ' + KIT_CASES if case.probe == 'kit' else ''
            details += ['  ' + row, '    purpose: Probe.', '    rules: ' + '; '.join((f'{n}: {d}' for n, d in rules)) + cases, '    known-bad: ' + ', '.join(bads), '    code: -', '    tests: -']
        text = '## alpha [-]\n  Serve alpha\n  ' + MODEL_LINE + '\n' + '\n'.join(rows) + '\n## beta [-]\n  Serve beta\n\n## alpha [-] 1 files/1 loc, 0 rules\n  purpose: Serve alpha\n' + '\n'.join(details)
        runtime = tuple(((mid, tuple((n for n, _ in rules)), bads) for mid, rules, bads, _keys in PROBE_TRUTH[case.probe]))
        return ReadObservation(case, text, runtime=runtime)
    if case.sources:
        text = '# read fixture\n' + COVERAGE_LINE + '\n\n## alpha [-]\n  Serve alpha\n  ' + MODEL_LINE + '\n## beta [-]\n  Serve beta'
        return ReadObservation(case, text)
    if case.relied or case.flowing:
        text = '## beta [-] 1 files/2 loc, 0 rules\n  purpose: Serve beta\n  rules: -\n  known-bad: -\n  code: 1 files/2 loc\n  tests: -' + ('\n  uses alpha: run\n  ' + RELIED_LINE if case.relied else '') + ('\n  ' + FLOW_LINE if case.flowing else '')
        return ReadObservation(case, text)
    if case.component:
        purpose = '(no summary yet)' if case.missing_summary else 'Serve alpha'
        text = '## alpha [-] 1 files/1 loc, 0 rules\n  purpose: ' + purpose + '\n  rules: -\n  known-bad: -\n  code: 1 files/1 loc\n  tests: 1 files: tests/test_alpha.py; 300 functions, 300 bound\n  ' + LARGE_MODEL_LINE
    else:
        purpose = '(no summary yet)' if case.missing_summary else 'Serve alpha'
        alpha = f"## alpha [{('low' if case.layered else '-')}]\n  " + purpose + '\n  ' + MODEL_LINE
        beta = f"## beta [{('top' if case.layered else '-')}]\n  Serve beta"
        text = '\n'.join((beta, alpha) if case.layered and (not file_order) else (alpha, beta))
    return ReadObservation(case, text)

class LegacyShow:
    name = 'Show'
    reads = ()
    writes = ('case', 'text', 'imported', 'runtime')

    def __init__(self, fault=''):
        self.fault = fault

    def apply(self, case, state):
        observed = _abstract(case)
        if self.fault == 'drop_component':
            observed = replace(observed, text=observed.text.split('\n## beta [', 1)[0])
        elif self.fault == 'import_model':
            observed = replace(observed, imported=True)
        elif self.fault == 'overflow':
            observed = replace(observed, text=observed.text.replace(MODEL_LINE, ''))
        elif self.fault == 'drop_model_contract':
            observed = replace(observed, text=observed.text.replace(MODEL_LINE, 'model read_probe: '))
        elif self.fault == 'drop_summary_prompt' and case.missing_summary:
            observed = replace(observed, text=observed.text.replace('(no summary yet)', ''))
        elif self.fault == 'tested_by_keys' and case.probe:
            text = observed.text
            for mid, rules, bads, keys in PROBE_TRUTH[case.probe]:
                if keys:
                    text = text.replace(f'({len(rules)} rules', f'({len(keys)} rules').replace('rules: ' + '; '.join((f'{n}: {d}' for n, d in rules)), 'rules: ' + ', '.join(keys) + ' (from TESTED_BY)')
            observed = replace(observed, text=text)
        elif self.fault == 'kit_hidden' and case.probe == 'kit':
            observed = replace(observed, text=re.sub('\\(4 rules, 3 known-bad', '(4 rules, ? known-bad', observed.text))
        elif self.fault == 'hide_flows' and case.flowing:
            observed = replace(observed, text=observed.text.replace('\n  ' + FLOW_LINE, ''))
        elif self.fault == 'hide_relied' and case.relied:
            observed = replace(observed, text=observed.text.replace('\n  ' + RELIED_LINE, ''))
        elif self.fault == 'map_file_order' and case.layered:
            observed = _abstract(case, file_order=True)
        elif self.fault == 'review_hides_error' and case.review:
            observed = replace(observed, text=re.sub('  1\\. fix [^\\n]*\\n', '', observed.text))
        elif self.fault == 'review_false_strength' and case.review:
            observed = replace(observed, text=observed.text.replace('strengths: ', 'strengths: no dependency cycles; '))
        elif self.fault == 'review_no_recipe' and case.review:
            observed = replace(observed, text=observed.text.replace('; references/map_format.md', ''))
        elif self.fault == 'exact_words_only' and case.query:
            observed = replace(observed, text='')
        elif self.fault == 'hide_focused' and case.component:
            observed = replace(observed, text=f'# read fixture\n... truncated at complete-view chars; not shown: {case.component}; use read --component ID')
        return (FunctionResult(observed.text, observed, label='read'),)

def _files():
    return {'alpha.py': 'def run(): return True\n', 'beta.py': 'def run(): return True\n', 'tests/test_alpha.py': 'def test_run(): pass\n'}

def _large_files():
    names = [f'test_case_{index:03d}' for index in range(LARGE_TESTS)]
    tests = ''.join((f'def {name}(): pass\n' for name in names))
    bound = ', '.join((f'"tests/test_alpha.py:{name}"' for name in names))
    return (tests, f'TESTED_BY = {{"works": [{bound}]}}\n')

def _write(root, relative, source):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding='utf-8')

def _runtime(root):
    """Import the probe models (after reading) to obtain their real names; then forget them."""
    models = root / '.flowguard/models'
    sys.path.insert(0, str(models))
    before = set(sys.modules)
    try:
        found = []
        for path in sorted(models.glob('probe_*.py')):
            spec = importlib.util.spec_from_file_location(f'_flowguard_read_truth_{path.stem}', path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            found.append((module.MODEL_ID, tuple(sorted((rule.name for rule in module.build_explorer().invariants))), tuple(sorted(module.broken_variants()))))
        return tuple(found)
    finally:
        sys.path.remove(str(models))
        for name in set(sys.modules) - before:
            sys.modules.pop(name, None)

def _review_components():

    def component(cid, **extra):
        return {**dict(id=cid, summary='Serve ' + cid, responsibilities=[], files=[cid + '.py'], tests=[], models=[], depends_on=[], status='draft', fingerprint='', layer=''), **extra}
    duties = [f'serve hub duty {word}' for word in ('one', 'two', 'three', 'four', 'five', 'six', 'seven')]
    return [component('alpha', tests=['tests/test_alpha.py']), component('beta'), component('app', depends_on=['store']), component('store', depends_on=['app']), dict(component(REVIEW_HUB, depends_on=['lib1', 'lib2', 'lib3']), responsibilities=duties)] + [component(cid) for cid in ('lib1', 'lib2', 'lib3')] + [component(cid, depends_on=[REVIEW_HUB]) for cid in ('u1', 'u2', 'u3')]

def _review(template, case, rules):
    with tempfile.TemporaryDirectory(prefix='flowguard-read-case-') as directory:
        root = Path(directory) / 'project'
        shutil.copytree(template, root)
        model_source = MODEL_SOURCE if case.import_marker else MODEL_SOURCE.replace('Path(__file__).parents[2].joinpath("model_import.marker").write_text("imported")\n', '')
        if case.component:
            tests, tested_by = _large_files()
            _write(root, 'tests/test_alpha.py', tests)
            model_source = model_source.replace('TESTED_BY = {"works": ["tests/test_alpha.py:test_run"]}\n', tested_by)
        _write(root, '.flowguard/models/read_probe.py', model_source)
        components = [dict(id=cid, summary=('Serve ' + cid) * 30, responsibilities=[], files=[cid + '.py'], tests=['tests/test_alpha.py'] if cid == 'alpha' else [], models=[], depends_on=[], status='draft', fingerprint='', layer='') for cid in ('alpha', 'beta')]
        if case.missing_summary:
            components[0].pop('summary')
        if case.layered:
            components[0]['layer'], components[1]['layer'] = ('low', 'top')
        if case.sources:
            _write(root, 'alpha.py', 'def run(): return True\ndef tested(): return True\ndef skipped(): return True\ndef loose(): return True\n')
            _write(root, 'tests/test_alpha.py', 'from alpha import tested\ndef test_run(): pass\ndef test_tested_function(): assert tested()\n')
            components[0]['entrypoints'] = ['alpha.py:run', 'alpha.py:tested', 'alpha.py:skipped', 'alpha.py:loose']
            model_source = model_source.replace('IMPLEMENTED_BY = {"Run": "alpha.py:run"}\n', 'IMPLEMENTED_BY = {"Run": "alpha.py:run"}\nNOT_MODELED = {"alpha.py:skipped": "a deliberate no-op"}\n')
            _write(root, '.flowguard/models/read_probe.py', model_source)
        if case.relied:
            _write(root, 'beta.py', 'import alpha\ndef run(): return alpha.run()\n')
            components[1]['depends_on'] = ['alpha']
        flows = [dict(id='chain', summary='beta then alpha', steps=['beta:run', 'alpha:run'], model='.flowguard/models/read_probe.py')] if case.flowing else []
        data = dict(project='read fixture', layers=['top', 'low'] if case.layered else [], components=components, flows=flows)
        if case.review:
            for relative, source in REVIEW_FILES.items():
                _write(root, relative, source)
            data = dict(project='read fixture', layers=[], components=_review_components(), flows=[dict(id='trip', summary='u1 calls the hub', steps=['u1:run', 'hub:run'])])
        inv = build_inventory(root, DEFAULT_IGNORE, with_bodies=False, write_cache=False)
        for relative, source in PROBE_FILES.get(case.probe, {}).items():
            _write(root, relative, source)
        if case.query:
            from flowguard.map.views import find_owners
            data['components'][0]['responsibilities'] = [FIND_DUTY]
            text = '\n'.join((cid for _, cid, _ in find_owners(data, inv, [case.query])))
        elif case.review:
            from flowguard.map.review import render_review
            text = render_review(root, data, inv)
        else:
            text = show_view(root, data, inv, component=case.component, detail=False)
        if case.probe:
            text += '\n\n' + show_view(root, data, inv, component='alpha', detail=False)
        models = (root / '.flowguard/models').resolve()
        imported = (root / 'model_import.marker').exists() or any((isinstance((file := vars(module).get('__file__')), str) and Path(file).resolve().is_relative_to(models) for module in tuple(sys.modules.values()) if module is not None))
        observed = ReadObservation(case, text, imported, _runtime(root) if case.probe else ())
        failed = [rule.name for rule in rules if not rule.check(observed, None).ok]
        if failed:
            raise RuntimeError(f'native render_show violates {failed!r}: {text!r}')
        return observed

class _Case(str):

    def __new__(cls, native, legacy):
        instance = super().__new__(cls, str(native))
        instance.legacy = legacy
        return instance

    def __getattr__(self, name):
        return getattr(self.legacy, name)

@dataclass(frozen=True, eq=False)
class JointState:
    native: object
    legacy: ReadObservation

    @property
    def case(self):
        return _Case(getattr(self.native, 'case', ''), self.legacy.case)

    def __getattr__(self, name):
        try:
            return getattr(self.native, name)
        except AttributeError:
            return getattr(self.legacy, name)

    def __getitem__(self, index):
        return self.native[index]

    def __bool__(self):
        return bool(self.native)

    def __eq__(self, other):
        if isinstance(other, JointState):
            return self.native == other.native and self.legacy == other.legacy
        return self.native == other

    def __hash__(self):
        return hash((self.native, self.legacy))

class Bridge:
    name = 'Read'
    reads = ()
    writes = ('native', 'legacy')

    def __init__(self, native, fault):
        self.native, self.fault = (native, fault)

    def apply(self, event, state):
        mode, value = event
        if mode == 'legacy':
            return tuple((FunctionResult(item.output, JointState(state.native, item.new_state)) for item in LegacyShow(self.fault).apply(value, state.legacy)))
        run = self.native.workflow.execute(state.native, value)
        if run.exception_branches:
            raise RuntimeError(str(run.exception_branches))
        return tuple((FunctionResult(item.current_input, JointState(item.state, state.legacy)) for item in run.completed_paths))

def legacy_cases(feature_names):
    features = [feature for feature in FEATURES if feature.name in feature_names]
    cases = [ReadCase()]
    for names in feature_explorer(features).external_inputs:
        case = ReadCase()
        for name in names:
            case = next((feature for feature in features if feature.name == name)).apply(case)
        if case not in cases:
            cases.append(case)
    return tuple(cases)

def legacy_conformance(feature_names, rules):
    from flowguard.map.facts import CodeFactsReport, Fact
    with tempfile.TemporaryDirectory(prefix='fg-read-aspect-') as directory:
        root = Path(directory)
        for relative, source in _files().items():
            _write(root, relative, source)
        observations = [_review(root, case, rules) for case in legacy_cases(feature_names)]
        return CodeFactsReport(tuple((Fact(f'view_case_{index}', all((rule.check(observed, None).ok for rule in rules)), observed.text) for index, observed in enumerate(observations))))


def show_view(root, data, inv, **options):
    from inspect import signature
    if 'budget' in signature(render_show).parameters:
        options['budget'] = 8000
    return render_show(root, data, inv, **options)


def complete_view_facts(mode):
    """Real old entrypoints lose a component, a model, a long line or a review row."""
    from flowguard.map.facts import Fact
    from flowguard.map.views import render_show, render_locate, render_field
    from flowguard.map.review import render_review
    import inspect
    with tempfile.TemporaryDirectory(prefix='fg-complete-view-') as directory:
        root = Path(directory)
        long_symbol = 'run_' + 'visible' * 250
        components = []
        for index in range(64):
            cid = f'component_{index:02}_' + 'ownership' * 9
            filename = f'unit{index}.py'
            _write(root, filename, ('def ' + long_symbol + '(row):\n    row["record_code"] = "ready"\n    return row\n') if index == 0 else 'def run(): return True\n')
            components.append(dict(id=cid, summary='Complete purpose ' + 'preserve every word ' * 500 if index == 0 else 'Serve ' + cid, responsibilities=[], files=[filename], tests=[], models=[], depends_on=[], status='draft'))
        data = dict(schema='flowguard.map.v1', project='complete', components=components)
        first = components[0]['id']
        _write(root, '.flowguard/models/probe.py', 'MODEL_ID="probe"\nPARENT=' + repr(first) + '\nIMPLEMENTED_BY={"Run":' + repr('unit0.py:' + long_symbol) + '}\nRULES=(Invariant("safe","keep safe",None),)\ndef build_explorer(): pass\ndef broken_variants(): return {}\n')
        inv = build_inventory(root, DEFAULT_IGNORE, write_cache=False)
        options = {'budget': 8000} if 'budget' in inspect.signature(render_show).parameters else {}
        if mode == 'show':
            text = render_show(root, data, inv, component=None, detail=False, **options)
            correct = all(re.search(r'^## ' + re.escape(c['id']) + r' \[', text, re.M) for c in components) and 'model probe:' in text
        elif mode == 'component':
            text = render_show(root, data, inv, component=first, detail=False, **options)
            correct = components[0]['summary'] in text and 'model probe:' in text
        elif mode == 'find':
            text = render_locate(root, data, inv, 'unit0.py:' + long_symbol)
            correct = ('locate unit0.py:' + long_symbol) in text and not any(line.endswith('...') for line in text.splitlines())
        elif mode == 'field':
            text = render_field(root, data, inv, 'record_code')
            correct = 'unit0.py:' + long_symbol in text and not any(line.endswith('…') for line in text.splitlines())
        else:
            text = render_review(root, data, inv)
            rows = text.split('components: ', 1)[-1].split('optimise next:', 1)[0]
            correct = all('  ' + c['id'] + ' ' in rows for c in components)
        return (Fact(mode + '_complete_real_entrypoint', bool(correct), text),)
