"""Executable regressions for actual repaired model/native observations."""
from __future__ import annotations

from pathlib import Path
import pprint

from ..map.common import content_digest
from .checks import GONE, check_model, replay_conflict
from .explore import Bounds
from .model import ModelError, load_model


def write_executable(root, relative, source):
    """Write executable source, execute it, then retain its actual content identity."""
    from .project import _atomic_write
    root = Path(root).resolve()
    relative = Path(relative)
    if relative.is_absolute() or '..' in relative.parts:
        raise ModelError('a generated regression must stay inside its project')
    destination = root / relative
    if destination.exists() and destination.read_text(encoding='utf-8') != source:
        raise ModelError(f'the existing regression {relative.as_posix()} differs; review its source')
    _atomic_write(destination, source)
    exec(compile(source, str(destination), 'exec'), {'__file__':str(destination), '__name__':'__main__'})
    return dict(path=relative.as_posix(), digest=content_digest(destination), passed=True)


def assert_model_regression(root, model_path, entry):
    """A pure model artifact makes only a model-correction claim."""
    from .diagram import ROUTE_KINDS
    from .routes import route_checks
    root = Path(root).resolve()
    loaded = load_model(root / model_path, root)
    report = check_model(loaded)
    if not report.graph.complete or report.graph.errors or any(f.cls == 'error' for f in report.findings):
        raise AssertionError('the model correction is no longer a complete error-free check')
    if entry['id'] in {finding.id for finding in report.findings}:
        raise AssertionError('the original model conflict reproduces')
    from .descriptors import closed_rule_definition
    rules = {f'rule:{rule.kind}:{rule.name}':rule for rule in loaded.model.rules}
    for original in entry.get('closed_rules', []):
        rule = rules.get(original['id'])
        if (rule is None or rule.source not in original['sources'] or
                not closed_rule_definition(rule, original)):
            raise AssertionError('the original source-bound model predicate changed')
    if entry['kind'] == 'NEVER REACHED':
        if entry['subject'] not in report.reached:
            raise AssertionError('the original reach obligation has no reaching witness')
    elif entry['kind'] in ROUTE_KINDS:
        _, graph, routes = route_checks(root / model_path, root, Bounds())
        if not graph.complete or any(f.id == entry['id'] for f in routes.findings):
            raise AssertionError('the original model route conflict remains or is unknown')
    elif not entry.get('replay') or replay_conflict(loaded.model, entry, Bounds())[0] != GONE:
        raise AssertionError('the original model failure condition remains or is unknown')
    return report


def model_regression(root, entry):
    relative = Path('tests/flowguard_model') / ('test_' + entry['id'].replace('-', '_') + '.py')
    function = 'test_' + entry['id'].replace('-', '_')
    original = {key:entry[key] for key in ('id','kind','subject','replay','detail','target') if key in entry}
    if 'model_correction' in entry:
        original['closed_rules'] = entry['model_correction']['closed_rules']
    data = pprint.pformat(original, sort_dicts=True, width=100)
    model_path = '.flowguard/flow/' + entry['model'] + '.py'
    source = ('"""Preserve the repaired model behavior; this makes no native code claim."""\n'
              'from pathlib import Path\nfrom flowguard.flow.regression import assert_model_regression\n\n'
              f'def {function}():\n'
              '    root = Path(__file__).resolve().parents[2]\n'
              f'    assert_model_regression(root, {model_path!r}, {data})\n\n'
              "if __name__ == '__main__':\n"
              f'    {function}()\n')
    return write_executable(root, relative, source)


def assert_requirement_regression(root, model_path, entry):
    """Execute the new model contract and revalidate its source-bound change."""
    from . import history
    from .descriptors import input_evidence, model_descriptor
    root = Path(root).resolve()
    loaded = load_model(root / model_path, root)
    report = check_model(loaded)
    descriptor = model_descriptor(loaded, report, 'executed requirement regression',
                                  input_evidence(root, loaded.reads))
    current = dict(receipt=descriptor['receipt'], finished=True, loaded=True,
        complete=report.graph.complete, errors=len(report.graph.errors), scope=descriptor['scope'],
        obligations=descriptor['obligations'], replay='not_run',
        conflicts=[dict(id=f.id, kind=f.kind, subject=f.subject) for f in report.findings if f.cls == 'conflict'])
    if any(f.kind in {'STUCK', 'NEVER REACHED'} for f in report.findings) or any(f.cls == 'error' for f in report.findings):
        raise AssertionError('the replacement requirement still has a real dead end, unreachable promise or model error')
    if history.assess(entry, current, root=root)['outcome'] != 'requirement_changed':
        raise AssertionError('the source-bound requirement change is no longer established')


def requirement_regression(root, entry):
    relative = Path('tests/flowguard_model') / ('test_' + entry['id'].replace('-', '_') + '_requirements.py')
    function = 'test_' + entry['id'].replace('-', '_') + '_requirements'
    original = {key:entry[key] for key in ('id','kind','model','subject','sources','subject_terms','history') if key in entry}
    original['history'] = {**original['history'], 'latest':None}
    data = pprint.pformat(original, sort_dicts=True, width=100)
    model_path = '.flowguard/flow/' + entry['model'] + '.py'
    source = ('"""Retain the implemented replacement requirement and its original authority."""\n'
              'from pathlib import Path\nfrom flowguard.flow.regression import assert_requirement_regression\n\n'
              f'def {function}():\n'
              '    root = Path(__file__).resolve().parents[2]\n'
              f'    assert_requirement_regression(root, {model_path!r}, {data})\n\n'
              "if __name__ == '__main__':\n" + f'    {function}()\n')
    return write_executable(root, relative, source)


def _closed_model_rules(loaded, entry, current, comparison):
    """Only an unchanged closed predicate can resolve a file-dependency unknown."""
    from .descriptors import closed_rule_evidence
    reasons = comparison['reasons']
    if comparison['outcome'] != 'retain' or not reasons or current['conflicts'] or any(
            row['code'] != 'obligation_relation_unknown' for row in reasons):
        return None
    old = {row['id']:row for row in entry['history']['baseline']['obligations']}
    new = {row['id']:row for row in current['obligations']}
    rules = {f'rule:{rule.kind}:{rule.name}':rule for rule in loaded.model.rules}
    closed = []
    for reason in reasons:
        name = reason['subject']
        a, b, rule = old.get(name), new.get(name), rules.get(name)
        if (a is None or b is None or rule is None or rule.kind != 'only_when' or
                a['cases'] is not None or b['cases'] is not None or a['definition'] is None or
                a['definition'] != b['definition']):
            return None
        proof = closed_rule_evidence(rule, a, entry)
        if proof is None:
            return None
        closed.append({**proof, **{key:a[key] for key in ('id', 'definition', 'sources')}})
    return dict(kind='model_corrected', original_receipt=entry['history']['baseline']['receipt'], closed_rules=closed)


def prepare_model_closures(root, loaded, report, descriptor, previous):
    """Worker-side pure-model correction; caller only consumes the receipt."""
    from . import history
    from ..map.inventory import coverage_kind
    model = loaded.model
    if model.config or getattr(model, 'adapter_binding', None):
        return {}, []
    present = {finding.id for finding in report.findings}
    observation = dict(receipt=descriptor['receipt'], finished=True, loaded=True,
                       complete=report.graph.complete, errors=len(report.graph.errors),
                       scope=descriptor['scope'], obligations=descriptor['obligations'], replay='not_run',
                       conflicts=[dict(id=f.id, kind=f.kind, subject=f.subject) for f in report.findings if f.cls == 'conflict'])
    closures, limits = {}, []
    for entry in previous:
        old_scope = entry.get('history', {}).get('baseline', {}).get('scope') or {}
        anchors = old_scope.get('coverage', {}).get('anchors', [])
        if entry['model'] != model.id or entry['id'] in present or entry.get('native_confirmation') or not anchors:
            continue
        comparison = history.assess(entry, observation, root=root)
        correction = _closed_model_rules(loaded, entry, observation, comparison)
        if correction is None and (comparison['outcome'] not in {'model_absent', 'requirement_changed'} or
                any(coverage_kind(root, values) not in {'model-only', 'data-only'} for values in (anchors, model.covers))):
            continue
        try:
            saved = dict(entry, model_correction=correction) if correction is not None else entry
            regression = (requirement_regression if comparison['outcome'] == 'requirement_changed' else model_regression)(root, saved)
        except (AssertionError, ModelError) as error:
            limits.append(entry['id'] + ': ' + str(error))
            continue
        closures[entry['id']] = dict(kind='requirement_changed' if comparison['outcome'] == 'requirement_changed' else 'model_corrected', boundary='model-only', complete_scope=True,
                                     original_condition_gone=True, regression=regression,
                                     model_receipt=descriptor['receipt'])
        if correction is not None:
            closures[entry['id']]['model_correction'] = correction
        if 'resolution' in comparison:
            closures[entry['id']]['resolution'] = comparison['resolution']
            closures[entry['id']]['scope_preserved'] = comparison['resolution']['scope']['before'] == comparison['resolution']['scope']['after']
    return closures, limits
