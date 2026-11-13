"""Behavior differences over the union of two source-owned decision partitions.

Source predicates describe the cells, never their expected answers. Every answer
comes from the shared Runtime and real source callable. This module owns no runner.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
import sys
import time

from flowguard.map.common import read_source
from . import cells as C


@dataclass
class Region:
    inputs: dict
    label: str


@dataclass
class Partition:
    regions: list[Region]
    complete: bool
    reasons: list[str]
    representative_points: int


def _atoms(view):
    """Already-read comparisons, with no arbitrary project call during grouping."""
    result, expressions = [], []
    for left, operator, right, _ in C.pairs_of(view.node):
        expressions.append(ast.Compare(left=left, ops=[operator], comparators=[right]))
    # Numeric truth tests cut at zero too (`if days`, `not days`). Leaving them
    # out could merge zero and nonzero although the old predicate distinguishes them.
    expressions.extend(test for node in ast.walk(view.node) for test in C._tests(node))
    seen = set()
    for expression in expressions:
        if not ({n.id for n in ast.walk(expression) if isinstance(n, ast.Name)} & set(view.kinds)):
            continue
        key = ast.dump(expression)
        if key in seen:
            continue
        seen.add(key)
        # Calls are not needed for the common comparison boundary. A readable
        # datetime/constructor atom can safely remain separate grid points here.
        if any(isinstance(n, ast.Call) for n in ast.walk(expression)):
            raise ValueError('comparison contains a call; retain the induced grid')
        code = compile(ast.fix_missing_locations(ast.Expression(expression)), '<anchor partition>', 'eval')
        result.append((ast.unparse(expression), code, view.literal_globals))
    return result


def _key(value):
    return type(value).__module__, type(value).__qualname__, repr(value)


def _smallest(region):
    """The order pytest reports same-name inputs in (`Observations.report`): numbers nearest 0 first, then the rest."""
    return [(0, abs(value), value) if isinstance(value, (int, float)) and not isinstance(value, bool) else (1, 0, C.show(value))
            for _, value in sorted(region.inputs.items())]


def _label(rows, witness, kinds, consts, atoms, truth, points):
    from .signals import class_label
    return class_label(atoms, truth, kinds, witness) if atoms else C.show_cell(witness)


def joint_partition(before, after):
    """One representative per old/new logical class, never grouped by outcomes."""
    kinds = before.kinds
    if kinds != after.kinds:
        raise ValueError('anchor input types changed; no common declared domain')
    readings = [before.reading, after.reading]
    consts = {name: [v for reading in readings for v in reading.consts.get(name, ())] for name in kinds}
    reasons = list(dict.fromkeys([issue.message for view in (before, after) for issue in view.issues]
                               + [why for reading in readings for why in reading.reasons]))
    space = C.build_space(kinds, consts,
                          planes=[p for reading in readings for p in reading.planes],
                          links={link for reading in readings for link in reading.links},
                          reasons=reasons,
                          hints={name: [v for reading in readings for v in reading.hints.get(name, ())] for name in kinds})
    rows = [row for row in space.cells if all(kind.name != 'enum' or row[name] in kind.literals
                                             for name, kind in kinds.items())]
    if not (space.complete and not reasons) and rows:
        rows = _with_representatives(rows, kinds, space.pts, reasons)
    # A finite type retains each real input. Unknown predicates retain their grid;
    # a small sample never becomes an exhaustive behavior-equivalence claim.
    atoms = []
    if space.complete and any(kind.name not in ('bool', 'enum', 'str') for kind in kinds.values()):
        try:
            atoms = _atoms(before) + _atoms(after)
        except ValueError as error:
            reasons.append(str(error))
    group = bool(atoms) and space.complete and not reasons
    groups = {}
    for row in rows:
        if group:
            try:
                truth_values = []
                for _, code, env in atoms:
                    try:
                        truth_values.append(bool(eval(code, {'__builtins__': {}, **env}, row)))
                    except TypeError:
                        if not any(name in kinds and row[name] is None for name in code.co_names):
                            raise
                        # Optional absence is a separate finite input pattern.
                        # An atom in a guarded branch need not be defined there;
                        # its real result/exception still comes from the child.
                        truth_values.append(None)
                truth = tuple(truth_values)
            except (NameError, TypeError, ValueError, AttributeError, ZeroDivisionError, OverflowError) as error:
                reasons.append(f'partition atom unavailable: {type(error).__name__}: {error}')
                group = False
                break
            finite = tuple((name, _key(row[name])) for name, kind in kinds.items()
                           if kind.name in ('bool', 'enum', 'str') or row[name] is None)
            groups.setdefault((finite, truth), []).append(row)
        else:
            groups[(tuple((name, _key(value)) for name, value in sorted(row.items())), ())] = [row]
    if not group:
        groups = {(tuple((name, _key(value)) for name, value in sorted(row.items())), ()): [row] for row in rows}
    regions = []
    for (_, truth), members in groups.items():
        witness = C.smallest(members, space.pts)
        label = _label(members, witness, kinds, consts, atoms, truth, space.pts) if group else C.show_cell(witness)
        regions.append(Region(witness, label))
    regions.sort(key=lambda region: tuple((name, _key(value)) for name, value in sorted(region.inputs.items())))
    return Partition(regions, space.complete and not reasons, list(dict.fromkeys(reasons)), len(rows))


def _with_representatives(rows, kinds, points, reasons, extra=None):
    """An unreadable numeric domain still runs the same fixed representatives on both sides; `extra`
    adds values of its own per input (the literals copy discovery reads from the compared code)."""
    base = C.smallest(rows, points)
    added = 0
    for name, kind in kinds.items():
        for value in [*C.representatives(kind), *(extra or {}).get(name, ())]:
            if not any(_key(row[name]) == _key(value) and all(row[other] == base[other] for other in kinds if other != name)
                       for row in rows):
                rows.append({**base, name: value})
                added += 1
    if added:
        reasons.append(f'numeric classes are not readable here: compared on {len(rows)} representative values '
                       '(boundaries, halves, negatives, non-finite); agreement on them is not a proof')
    return rows


def _result(name, partition, before, after, *, mismatch_is_red=False):
    from .calibration import outcome_equal
    if len(before) != len(partition.regions) or len(after) != len(partition.regions):
        raise ValueError('anchor executor returned the wrong number of observations')
    changes, reasons, checked = [], list(partition.reasons), 0
    for region, old, new in zip(partition.regions, before, after):
        if old.status != 'ok' or new.status != 'ok':
            reasons.extend(old.reasons or (f'old observation is {old.status}',) if old.status != 'ok' else ())
            reasons.extend(new.reasons or (f'new observation is {new.status}',) if new.status != 'ok' else ())
            continue
        checked += 1
        if not outcome_equal(old.value, new.value):
            changes.append(dict(anchor=name, region=region.label,
                                witness={key: C.show(value) for key, value in region.inputs.items()},
                                before=C.show(old.value), after=C.show(new.value)))
    reasons = list(dict.fromkeys(reasons))
    return dict(status='red' if mismatch_is_red and changes else 'grey' if reasons else 'ok',
                total=len(partition.regions), checked=checked,
                unknown=len(partition.regions) - checked, changed=len(changes), changes=changes,
                complete=partition.complete and not reasons, reasons=reasons,
                representative_points=partition.representative_points)


def _compatible(left, right):
    """Omitted short-form labels are unknown, not an invented role conflict."""
    from .anchors import _type_id
    if left.kind != right.kind or tuple(p.name for p in left.parameters) != tuple(p.name for p in right.parameters):
        return False
    known = lambda a, b: not a or not b or a == '?' or b == '?' or a == b
    return (known(left.output, right.output) and known(_type_id(left.output_type), _type_id(right.output_type))
            and all(known(a.unit, b.unit) and known(_type_id(a.source_type), _type_id(b.source_type))
                    for a, b in zip(left.parameters, right.parameters)))


def _source_index(root, graph=None):
    from . import anchors
    if graph is not None:
        return anchors.collect(graph)
    from flowguard.map.common import DEFAULT_IGNORE, matches_any
    from flowguard.map.inventory import list_files
    from flowguard.structure import roots
    from flowguard.structure.paths import project_files
    from flowguard.structure.store import project_config
    # The same file selection as the map build: [tool.flowguard] exclude applies here too.
    ignore = [pattern for pattern in DEFAULT_IGNORE if pattern != 'venv/**'] + [
        str(pattern) for pattern in project_config(Path(root)).get('exclude', [])]
    files = [file for file in list_files(root) if not matches_any(file, ignore)]
    python = [file for file in files if file.endswith('.py')]
    python = [file for file, owned in zip(python, project_files([str(root / file) for file in python], root)) if owned]
    sources = {file: (root / file).read_bytes() for file in python}
    syspath, unreadable = {}, []
    for file, raw in sources.items():
        if b'sys.path' in raw or b'addsitedir' in raw:
            try:
                syspath[file] = roots.syspath_entries(ast.parse(read_source(root / file, data=raw)), file)
            except SyntaxError as error:
                # Only this file is unknown; the map build reads it the same way.
                unreadable.append(anchors.Issue('grey', 'source-syntax', str(error), file, error.lineno or 0))
    detected = roots.detect(root, files, python, syspath)
    names = roots.names(python, detected)[0]
    selected = [(file, names[file][0][0], '/tests/' in '/'+file or Path(file).name.startswith('test_'))
                for file, raw in sources.items() if b'flowguard:' in raw]
    index = anchors.collect_sources(root, selected)
    known = {issue.file for issue in index.issues if issue.code == 'source-syntax'}
    return anchors.Index(index.entries, index.issues + tuple(issue for issue in unreadable if issue.file not in known))


def _compare_pairs(root, pairs, *, answers=False, witnesses=False):
    """Compare current source anchors; historical replay is Runtime's job. With `answers` (same-name copies, the
    reference first in every pair) the result also holds what every compared copy answers on the first input
    where each pair differs, run once more: `answers` [(input shown, [(anchor, value)])]. With `witnesses` it holds
    the inputs ({declared name: value}) of every class where a pair differs, for a comparison elsewhere (`check`
    compares the copies sealed, now and at the baseline, on them)."""
    from .anchors import decision_reading
    from .calibration import execute_many
    prepared_at = time.perf_counter()
    selected, reasons, conflict = [], [], False
    for left, right in pairs:
        if not _compatible(left, right):
            conflict |= left.name == right.name
            reasons.append(f'{right.name}: anchor signature or units changed; no common declared input/output role')
            continue
        if left.calibrated_by or right.calibrated_by:
            reasons.append(f'{right.name}: comparison needs both anchors in the same actual call context; '
                           'independent fresh fixtures are not a shared context')
            continue
        old, new = decision_reading(root, left), decision_reading(root, right)
        if old.kinds != new.kinds:
            reasons.append(f'{right.name}: input kinds are unavailable under one common declared domain')
            continue
        partition = joint_partition(old, new)
        if not old.dependencies_complete or not new.dependencies_complete:
            partition.complete = False
            partition.reasons.append(f'{right.name}: helper dependencies are not statically closed; candidate observations only')
        selected.append((left, right, partition))
    partition_seconds = time.perf_counter() - prepared_at
    requests = [(anchor, region.inputs) for left, right, part in selected
                for anchor in (left, right) for region in part.regions]
    start = time.perf_counter()
    observations = execute_many(root, requests) if requests else []
    if len(observations) != len(requests):
        raise ValueError('anchor executor returned the wrong number of observations')
    items, offset = [], 0
    for left, right, partition in selected:
        size = len(partition.regions)
        item = _result(right.name, partition, observations[offset:offset + size],
                       observations[offset + size:offset + size * 2], mismatch_is_red=True)
        item.update(before_target=left.target, after_target=right.target)
        for change in item['changes']:
            change.update(before_target=left.target, after_target=right.target)
        items.append(item)
        reasons.extend(item['reasons'])
        offset += size * 2
    extra = {}
    if witnesses:
        extra['witnesses'] = [dict(region.inputs) for (_, _, partition), item in zip(selected, items)
                              for region in partition.regions if region.label in {change['region'] for change in item['changes']}]
    if answers:
        # Each pair's smallest input that differs, once per input, smallest first; every copy runs on each.
        regions = {}
        for (left, right, partition), item in zip(selected, items):
            labels = {change['region'] for change in item['changes']}
            if labels:
                region = min((region for region in partition.regions if region.label in labels), key=_smallest)
                regions.setdefault(', '.join(f'{key}={C.show(value)}' for key, value in region.inputs.items()), region)
        regions = dict(sorted(regions.items(), key=lambda entry: _smallest(entry[1])))
        copies = list({anchor.target: anchor for pair in selected for anchor in pair[:2]}.values())
        rerun = [(anchor, region.inputs) for region in regions.values() for anchor in copies]
        observed = execute_many(root, rerun) if rerun else []
        if len(observed) != len(rerun):
            raise ValueError('anchor executor returned the wrong number of observations')
        extra = dict(answers=[(where, [(anchor, seen.value) for anchor, seen in
                                       zip(copies, observed[number * len(copies):(number + 1) * len(copies)])
                                       if seen.status == 'ok'])
                              for number, where in enumerate(regions)])
    return dict(**extra, status='red' if conflict or any(item['changed'] for item in items) else 'grey' if reasons else 'ok',
                total=sum(item['total'] for item in items),
                checked=sum(item['checked'] for item in items), unknown=sum(item['unknown'] for item in items),
                changed=sum(item['changed'] for item in items),
                changes=[change for item in items for change in item['changes']], items=items,
                complete=not reasons and all(item['complete'] for item in items),
                reasons=list(dict.fromkeys(reasons)), selected=len(selected), comparison=True,
                phases={'partition_and_selection': partition_seconds, 'execution': time.perf_counter() - start})


def compare(root, left, right, *, graph=None):
    """K5 uses the same partition/execution core for two present source anchors."""
    root = Path(root).resolve()
    index = _source_index(root, graph)
    def resolve(value):
        matches = [a for a in index.entries if a.kind == 'sensor' and (a.name == value or a.target == value)]
        if len(matches) != 1:
            raise ValueError(f'{value}: name must identify one sensor; use module:qual for a copy')
        return matches[0]
    return _compare_pairs(root, [(resolve(left), resolve(right))])


def render(report, limit=10):
    from .signals import render as render_signals
    return render_signals(report, limit)


def display(text, *, file=None):
    """Write human comparison text, escaping only an unrepresentable display.

    The Unicode render and report data stay unchanged. The ASCII fallback keeps
    real LF boundaries and escapes original backslashes so it is reversible.
    """
    stream = sys.stdout if file is None else file
    encoding = getattr(stream, 'encoding', None)
    if encoding:
        try:
            text.encode(encoding)
        except UnicodeEncodeError:
            text = '\n'.join(line.encode('unicode_escape').decode('ascii') for line in text.split('\n'))
    print(text, file=stream)


def anchor_distinct(root, declaration, *, graph=None, index=None, cfg=None, archive=None):
    """Check an existing Distinct declaration against source-owned sensor names.

    Different declared roles are a sourced structural separation, not a claim
    about behavior. Compatible roles need an actual inequality witness; complete
    equality is a broken distinct. This never waives same-name agreements.
    """
    from . import sources
    from .config import load_config
    root = Path(root).resolve()
    result = dict(kind='anchor_distinct', a=declaration.a, b=declaration.b,
                  why=declaration.why, source=declaration.source,
                  status='grey', total=0, changed=0, changes=[], items=[], reasons=[],
                  complete=False, selected=0, distinct_holds=None, behavior_checked=False,
                  provisional=False, source_verified=False, scope='source-owned-sensors')
    if not isinstance(declaration.why, str) or not declaration.why.strip() or \
            not isinstance(declaration.source, str) or not declaration.source.strip():
        result.update(status='red', reasons=['anchor distinct needs its own why and source'])
        return result
    cfg = load_config(root) if cfg is None else cfg
    archive = sources.Archive(root) if archive is None else archive
    try:
        source = sources.parse(declaration.source)
    except sources.IntentError as error:
        result.update(status='red', reasons=[str(error)])
        return result
    valid, reason = sources.authority(source, None, cfg, archive)
    provisional = source.kind == 'assumed' or valid and source.kind == 'doc' and (
        not declaration.file or sources.provisional(source, cfg, root / declaration.file))
    source_ready = valid or provisional
    result.update(source_verified=valid, provisional=bool(provisional), source_reason=reason)
    index = _source_index(root, graph) if index is None else index
    def resolve(value):
        matches = tuple(a for a in index.entries if a.kind == 'sensor'
                        and (a.target == value if ':' in value else a.name == value))
        if not matches and ':' in value and graph is not None:
            canonical = graph.canonical(value)
            matches = tuple(a for a in index.entries if a.kind == 'sensor' and a.target == canonical)
        return matches
    left, right = resolve(declaration.a), resolve(declaration.b)
    if not left or not right:
        result.update(status='red', reasons=['distinct names a missing source sensor: '
                      + ', '.join(value for value, entries in ((declaration.a, left), (declaration.b, right)) if not entries)])
        return result
    names = {a.name for a in (*left, *right)}
    if len(names) == 1:
        result.update(status='red', reasons=['the same sensor name cannot be distinct; keep its copies in agreement'])
        return result
    problems = [issue for issue in index.issues if issue.name in names]
    if any(issue.level == 'red' for issue in problems):
        result.update(status='red', reasons=list(dict.fromkeys(issue.message for issue in problems)))
        return result
    if not any(tuple(p.name for p in a.parameters) == tuple(p.name for p in b.parameters)
               and (not a.output or not b.output or a.output == b.output) for a in left for b in right):
        result.update(status='ok' if source_ready and not problems else 'grey',
                      complete=source_ready and not problems, distinct_holds=True,
                      scope='declared-role-separation', behavior_checked=False,
                      reasons=([reason] if not source_ready else []) + [issue.message for issue in problems])
        return result
    if any(any(x.unit and y.unit and x.unit != y.unit for x, y in zip(a.parameters, b.parameters))
           for a in left for b in right):
        result['reasons'] = ['distinct sensor units have no declared common input domain; no conversion is guessed']
        return result
    if any(not _compatible(a, b) for a in left for b in right):
        result['reasons'] = ['distinct sensor types have no declared common input/output domain']
        return result
    report = _compare_pairs(root, [(a, b) for a in left for b in right])
    result.update(report, kind='anchor_distinct', comparison=False, scope='joint-declared-input-classes',
                  behavior_checked=bool(report['items']))
    if not source_ready:
        result['reasons'] = list(dict.fromkeys(result['reasons'] + [reason]))
        result['complete'] = False
    broken = [item for item in report['items'] if item['complete'] and item['total'] and item['changed'] == 0]
    unresolved = [item for item in report['items'] if not item['complete']]
    result['distinct_holds'] = bool(report['items']) and not broken and all(item['changed'] for item in report['items'])
    if broken:
        result.update(status='red', reasons=list(dict.fromkeys(result['reasons'] + [
            f'distinct broken: {declaration.a} and {declaration.b} agree on every class; {declaration.why} -> '
            f'keep the copies separate as this distinct requires; if they should agree, ask the owner before removing this distinct'])))
    elif unresolved or not source_ready or not report['items']:
        result.update(status='grey', complete=False,
                      reasons=list(dict.fromkeys(result['reasons'] + ([reason] if not source_ready else []))))
        if unresolved:
            result['distinct_holds'] = None
    else:
        result['status'] = 'ok'
    return result
