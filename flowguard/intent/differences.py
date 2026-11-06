"""Behavior differences over the union of two source-owned decision partitions.

Source predicates describe the cells, never their expected answers. Every answer
comes from the one fresh-process anchor executor. This module owns no registry.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
import io
from pathlib import Path
import tarfile
import tempfile
import time

from flowguard.map.common import git_run, read_source
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


def _label(rows, witness, kinds, consts, atoms, truth, points):
    numeric = [name for name, kind in kinds.items() if kind.name in ('int', 'float', 'dec')]
    if len(kinds) == len(numeric) == 1 and rows and all(row[numeric[0]] is not None for row in rows):
        name = numeric[0]
        ordered = sorted({row[name] for row in rows})
        all_points = sorted({p for p in points[name] if p is not None})
        indices = [all_points.index(p) for p in ordered]
        if indices == list(range(min(indices), max(indices) + 1)):
            cuts = sorted({C.coerce(v, kinds[name]) for v in consts[name]
                           if C.coerce(v, kinds[name]) is not None and kinds[name].accepts(C.coerce(v, kinds[name]))})
            lower = max((v for v in cuts if v <= ordered[0]), default=None)
            upper = min((v for v in cuts if v >= ordered[-1]), default=None)
            closed_lower = lower in ordered if lower is not None else False
            closed_upper = upper in ordered if upper is not None else False
            if kinds[name].name == 'int':
                low = lower + (not closed_lower) if lower is not None else None
                high = upper - (not closed_upper) if upper is not None else None
                if low == high and low is not None:
                    return f'{name}={C.show(low)}'
                return f'{name}={C.show(low) if low is not None else "−∞"}–{C.show(high) if high is not None else "∞"}'
            return (f'{C.show(lower) if lower is not None else "−∞"} '
                    f'{"<=" if closed_lower else "<"} {name} '
                    f'{"<=" if closed_upper else "<"} {C.show(upper) if upper is not None else "∞"}')
    if atoms:
        parts = list(dict.fromkeys(f'undefined ({text})' if yes is None else text if yes else f'not ({text})'
                                   for (text, _, _), yes in zip(atoms, truth)))
        parts.extend(f'{name}={C.show(witness[name])}' for name, kind in kinds.items()
                     if kind.name in ('bool', 'enum', 'str') or witness[name] is None)
        return ' and '.join(parts)
    return C.show_cell(witness)


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


def _schema(anchor):
    return (anchor.kind, tuple((p.name, p.unit, p.source_type) for p in anchor.parameters),
            anchor.output, anchor.output_type, anchor.values)


def _source_index(root, graph=None):
    from . import anchors
    if graph is not None:
        return anchors.collect(graph)
    from flowguard.map.inventory import list_files
    from flowguard.structure import roots
    from flowguard.structure.paths import project_code
    files = list_files(root)
    python = [file for file in files if file.endswith('.py') and project_code(str(root / file), root)]
    sources = {file: (root / file).read_bytes() for file in python}
    syspath = {file: roots.syspath_entries(ast.parse(read_source(root / file, data=raw)), file)
               for file, raw in sources.items() if b'sys.path' in raw or b'addsitedir' in raw}
    detected = roots.detect(root, files, python, syspath)
    names = roots.names(python, detected)[0]
    selected = [(file, names[file][0][0], '/tests/' in '/'+file or Path(file).name.startswith('test_'))
                for file, raw in sources.items() if b'flowguard:' in raw]
    return anchors.collect_sources(root, selected)


def _pairs(before, after):
    old = {(a.name, a.target): a for a in before.entries if a.kind == 'sensor'}
    new = {(a.name, a.target): a for a in after.entries if a.kind == 'sensor'}
    pairs = [(old.pop(key), new.pop(key)) for key in sorted(old.keys() & new.keys())]
    for name in sorted({key[0] for key in old} & {key[0] for key in new}):
        left = [key for key in old if key[0] == name]
        right = [key for key in new if key[0] == name]
        if len(left) == len(right) == 1:
            pairs.append((old.pop(left[0]), new.pop(right[0])))
    missing = [f'{name}: sensor added, removed or ambiguous; no previous pairing'
               for name in sorted({key[0] for key in old} | {key[0] for key in new})]
    return pairs, missing


def _compare_pairs(left_root, right_root, pairs, *, changed_only, automatic=False, source_only_history=False):
    from .anchors import decision_reading
    from .calibration import execute_many
    prepared_at = time.perf_counter()
    pending, reasons = [], []
    for left, right in pairs:
        old = decision_reading(left_root, left)
        new = decision_reading(right_root, right)
        closed = old.dependencies_complete and new.dependencies_complete
        if changed_only and closed and (_schema(left), old.fingerprint, old.dependencies) == (_schema(right), new.fingerprint, new.dependencies):
            continue
        if _schema(left) != _schema(right):
            reasons.append(f'{right.name}: anchor signature or units changed; no common declared input/output role')
            continue
        if source_only_history and (left.calibrated_by or right.calibrated_by):
            reasons.append(f'{right.name}: historical calibrated test non-code inputs are not closed by the source-only snapshot; check-only boundary')
            continue
        if not closed:
            reasons.append(f'{right.name}: helper dependencies are not statically closed; check-only')
        pending.append((left, right, old, new))
    deferred = automatic and (len(pending) > 20 or any(a.calibrated_by or b.calibrated_by for a, b, _, _ in pending) or reasons)
    if automatic and not deferred:
        coupled = [right.name for _, right, old, new in pending
                   if any(view.reading.links or any(len(plane.coefs) > 1 for plane in view.reading.planes)
                          for view in (old, new))]
        if coupled:
            reasons.append('coupled-field partition is check-only: ' + ', '.join(coupled))
            deferred = True
    if automatic and not deferred:
        # Automatic information has a small execution budget. Estimate before
        # enumerating; explicit check/compare still retain every original cell.
        point_bound = 0
        for _, _, old, new in pending:
            consts = {name: [value for view in (old, new) for value in view.reading.consts.get(name, ())]
                      for name in old.kinds}
            links = {link for view in (old, new) for link in view.reading.links}
            points, _ = C.field_points(old.kinds, consts, links)
            count = 1
            for values in points.values():
                count *= len(values)
            point_bound += count
        if point_bound > 256:
            reasons.append(f'automatic union grid bound {point_bound} exceeds 256; explicit check keeps the complete domain')
            deferred = True
    if deferred:
        return dict(status='grey', total=0, changed=0, changes=[], complete=False, reasons=list(dict.fromkeys(reasons + ['behavior difference deferred to check: isolated calibration, unresolved dependencies, large domain or more than 20 changed sensors'])), selected=len(pending), deferred=True)
    selected = [(left, right, joint_partition(old, new)) for left, right, old, new in pending]
    before_requests = [(left, region.inputs) for left, _, part in selected for region in part.regions]
    after_requests = [(right, region.inputs) for _, right, part in selected for region in part.regions]
    partition_seconds = time.perf_counter() - prepared_at
    start = time.perf_counter()
    if Path(left_root).resolve() == Path(right_root).resolve():
        values = execute_many(left_root, before_requests + after_requests) if before_requests or after_requests else []
        before_values, after_values = values[:len(before_requests)], values[len(before_requests):]
        old_seconds, new_seconds = time.perf_counter() - start, 0.0
    else:
        before_values = execute_many(left_root, before_requests) if before_requests else []
        old_seconds = time.perf_counter() - start
        start = time.perf_counter()
        after_values = execute_many(right_root, after_requests) if after_requests else []
        new_seconds = time.perf_counter() - start
    if len(before_values) != len(before_requests) or len(after_values) != len(after_requests):
        raise ValueError('anchor executor returned the wrong number of observations')
    items, offset = [], 0
    for left, right, partition in selected:
        end = offset + len(partition.regions)
        item = _result(right.name, partition, before_values[offset:end], after_values[offset:end], mismatch_is_red=not changed_only)
        item.update(before_target=left.target, after_target=right.target)
        for change in item['changes']:
            change.update(before_target=left.target, after_target=right.target)
        items.append(item)
        reasons.extend(item['reasons'])
        offset = end
    return dict(status='red' if not changed_only and any(item['changed'] for item in items) else 'grey' if reasons else 'ok',
                total=sum(item['total'] for item in items),
                checked=sum(item['checked'] for item in items), unknown=sum(item['unknown'] for item in items),
                changed=sum(item['changed'] for item in items),
                changes=[change for item in items for change in item['changes']], items=items,
                complete=not reasons and all(item['complete'] for item in items),
                reasons=list(dict.fromkeys(reasons)), selected=len(selected), deferred=False,
                comparison=not changed_only,
                phases={'partition_and_selection': partition_seconds,
                        'old_execution': old_seconds, 'new_execution': new_seconds})


def changed(root, base='HEAD', *, graph=None, automatic=False):
    """Compare only changed sensors; old and working sources never share a process."""
    root = Path(root).resolve()
    start = time.perf_counter()
    current = _source_index(root, graph)
    indexed = time.perf_counter()
    found = git_run(root, 'rev-parse', '--verify', base+'^{commit}', allowed=(0, 128))
    if found.returncode:
        return dict(status='grey', base=base, total=0, changed=0, changes=[], complete=False,
                    reasons=['old source unavailable: '+found.stderr.decode(errors='replace').strip()],
                    selected=0, deferred=False, automatic_eligible=False,
                    elapsed_seconds=time.perf_counter()-start)
    revision = found.stdout.decode().strip()
    # Pure observation needs source and package configuration, not the project's
    # unrelated data blobs. In a partial clone, never fetch an entire data archive.
    from flowguard.structure.roots import CONFIGS
    changed_paths = {path.decode() for path in git_run(root, 'diff', '--name-only', '-z', revision).stdout.split(b'\0') if path}
    changed_paths.update(path.decode() for path in git_run(root, 'ls-files', '--others', '--exclude-standard', '-z').stdout.split(b'\0') if path)
    source_changes = sorted(path for path in changed_paths if path.endswith('.py') or Path(path).name in CONFIGS)
    if not source_changes:
        return dict(status='ok', base=revision, total=0, changed=0, changes=[], items=[],
                    complete=True, reasons=[], selected=0, deferred=False, automatic_eligible=True,
                    elapsed_seconds=time.perf_counter()-start,
                    scope='no changed source/configuration; no behavior comparison attempted',
                    phases={'current_index': indexed-start},
                    snapshot=dict(kind='no-source-change', paths=0, omitted_noncode_paths=0, archive_bytes=0))
    tracked = [path.decode() for path in git_run(root, 'ls-tree', '-r', '--name-only', '-z', revision).stdout.split(b'\0') if path]
    paths = [path for path in tracked if path.endswith('.py') or Path(path).name in CONFIGS]
    archive = git_run(root, 'archive', revision, '--', *paths).stdout if paths else b''
    archived = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix='flowguard-difference-') as folder:
        previous = Path(folder)
        if archive:
            with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
                stream.extractall(previous, filter='data')
        previous_index = _source_index(previous)
        prepared = time.perf_counter()
        pairs, missing = _pairs(previous_index, current)
        report = _compare_pairs(previous, root, pairs, changed_only=True, automatic=automatic, source_only_history=True)
    report['reasons'] = list(dict.fromkeys(report['reasons'] + missing))
    if report['reasons'] and report['status'] == 'ok':
        report['status'] = 'grey'
        report['complete'] = False
    elapsed = time.perf_counter() - start
    report.update(base=revision, elapsed_seconds=elapsed,
                  automatic_eligible=not report['reasons'] and not report.get('deferred') and elapsed <= 3 and report['selected'] <= 20)
    report['snapshot'] = dict(kind='tracked-python-and-project-config', paths=len(paths),
                              omitted_noncode_paths=len(tracked)-len(paths), archive_bytes=len(archive))
    report['source_changes'] = source_changes
    report.setdefault('phases', {}).update(current_index=indexed-start, archive=archived-indexed,
                                          old_extract_and_index=prepared-archived)
    return report


def compare(root, left, right, *, graph=None):
    """K5 uses the same partition/execution core for two present source anchors."""
    root = Path(root).resolve()
    index = _source_index(root, graph)
    def resolve(value):
        matches = [a for a in index.entries if a.kind == 'sensor' and (a.name == value or a.target == value)]
        if len(matches) != 1:
            raise ValueError(f'{value}: name must identify one sensor; use module:qual for a copy')
        return matches[0]
    return _compare_pairs(root, root, [(resolve(left), resolve(right))], changed_only=False)


def agreements(root, graph=None, *, index=None, automatic=False):
    """Check necessary same-name sensor copies, reusing the caller's source index.

    A deterministic reference against each other copy needs n−1 comparisons;
    equality over their complete joint partitions is transitive. Different names
    are never made equal merely because their bodies look alike.
    """
    root = Path(root).resolve()
    index = _source_index(root, graph) if index is None else index
    pairs, conflicts, groups = [], [], 0
    for name, entries in sorted(index.by_name.items()):
        sensors = sorted((a for a in entries if a.kind == 'sensor'), key=lambda a: a.target)
        if len(sensors) < 2:
            continue
        groups += 1
        if len({_schema(a) for a in sensors}) > 1:
            conflicts.append(f'{name}: same sensor name has conflicting roles, units or signatures')
        else:
            pairs.extend((sensors[0], other) for other in sensors[1:])
    report = _compare_pairs(root, root, pairs, changed_only=False, automatic=automatic)
    report.update(groups=groups, active=bool(groups))
    if conflicts:
        report.update(status='red', complete=False, reasons=list(dict.fromkeys(report['reasons'] + conflicts)))
    return report


def render(report, limit=10):
    """At most ten changed-class lines; details and unknown scope stay in data."""
    lines = [f'{row["anchor"]}'
             + (f' ({row["before_target"]} ↔ {row["after_target"]})' if report.get('comparison') else '')
             + f': {row["region"]}: {row["before"]} → {row["after"]}'
             for row in report['changes'][:min(10, max(0, limit))]]
    if report.get('reasons'):
        lines.append(('冲突: ' if report.get('status') == 'red' and not report['changes'] else '未覆盖: ')
                     + '; '.join(report['reasons'][:2]))
    if report.get('complete'):
        lines.append(f'共 {report["total"]} 类，变 {report["changed"]} 类')
    else:
        lines.append(f'候选 {report["total"]} 类，已比较 {report.get("checked", 0)} 类；'
                     f'比较未完成，已证变化 {report["changed"]} 类')
    return '\n'.join(lines)


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
    role = lambda a: (tuple(p.name for p in a.parameters), a.output)
    if {role(a) for a in left} != {role(a) for a in right}:
        result.update(status='ok' if source_ready and not problems else 'grey',
                      complete=source_ready and not problems, distinct_holds=True,
                      scope='declared-role-separation', behavior_checked=False,
                      reasons=([reason] if not source_ready else []) + [issue.message for issue in problems])
        return result
    units = lambda a: tuple(p.unit for p in a.parameters)
    if {units(a) for a in left} != {units(a) for a in right}:
        result['reasons'] = ['distinct sensor units have no declared common input domain; no conversion is guessed']
        return result
    types = lambda a: (tuple(p.source_type for p in a.parameters), a.output_type)
    if {types(a) for a in left} != {types(a) for a in right}:
        result['reasons'] = ['distinct sensor types have no declared common input/output domain']
        return result
    report = _compare_pairs(root, root, [(a, b) for a in left for b in right], changed_only=False)
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
            f'distinct broken: {declaration.a} and {declaration.b} agree on every class; {declaration.why}'])))
    elif unresolved or not source_ready or not report['items']:
        result.update(status='grey', complete=False,
                      reasons=list(dict.fromkeys(result['reasons'] + ([reason] if not source_ready else []))))
        if unresolved:
            result['distinct_holds'] = None
    else:
        result['status'] = 'ok'
    return result
