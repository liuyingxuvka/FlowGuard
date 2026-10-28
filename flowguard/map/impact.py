"""Change impact: declared and parsed callers, bound tests and executable models."""

from __future__ import annotations

import ast
import json
import os
import subprocess
import tempfile
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path

from .common import DEFAULT_TEST_COMMAND, SOURCE_EXTS, git_paths, glob_match, is_collectable_test, is_product_file, is_test_file, matches_any, norm, normalize_newlines, read_source
from .inventory import Inventory
from .mapfile import component_files, component_scope, component_subtree, component_graph, dependency_evidence, flow_step_parts, ignore_patterns, is_stale, model_registry, read_model_contract, top_level_imports

from .tree import build_tree






def changed_files(root: Path, base: str, *, data=None, inv=None) -> list[str]:
    """Keep both sides of renames and deleted paths, plus untracked files."""
    files: set[str] = set()
    commands = (["git", "-C", str(root), "diff", "--name-status", "-z", "-M", base],
                ["git", "-C", str(root), "ls-files", "-o", "--exclude-standard", "-z"])
    for i, cmd in enumerate(commands):
        try:
            fields = _read_git_paths(root, *cmd[3:])
        except subprocess.CalledProcessError as exc:
            return _no_git_changes(root,data,inv)
        if i == 1:
            files.update(norm(f) for f in fields)
            continue
        cursor = 0
        while cursor < len(fields):
            status = fields[cursor]
            count = 2 if status.startswith(("R", "C")) else 1
            files.update(norm(f) for f in fields[cursor + 1:cursor + 1 + count])
            cursor += 1 + count
    return sorted(f for f in files if "__pycache__" not in Path(f).parts and not f.endswith((".pyc", ".pyo"))
                  and not f.startswith(".flowguard/cache/"))




def test_groups(imp: Impact) -> tuple[dict[str, list[str]], list[str]]:
    groups: dict[str, list[str]] = defaultdict(list)
    no_command = []
    for test in imp.tests:
        command = next((cmd for pattern, cmd in imp.test_commands.items() if glob_match(test, pattern)), None)
        if command is None and test.endswith(".py"):
            command = imp.test_command
        if command:
            nodes=imp.test_functions.get(test)
            groups[command].extend(test+'::'+symbol.replace('.', '::') for symbol in nodes) if nodes else groups[command].append(test)
        else:
            no_command.append(test)
    return groups, no_command


def run_commands(imp: Impact, *, moving_models: set[str] | None = None) -> list[str]:
    """The exact commands of the ``run:`` lines, in order (tests per command, then the selected models)."""
    import shlex

    groups, _ = test_groups(imp)
    commands = []
    for command, tests in groups.items():
        line=f"{command} " + " ".join(shlex.quote(t) for t in tests)
        if len(line)>8000:
            line=f"{command} " + " ".join(shlex.quote(t) for t in dict.fromkeys(test.split('::',1)[0] for test in tests))
        commands.append(line)
    model_ids = [mid for path, mid in zip(imp.models, imp.model_ids) if path not in (moving_models or set())]
    if model_ids:
        commands.append("python -m flowguard map models " + " ".join(model_ids))
    return commands


def render_impact(
    imp: Impact,
    *,
    moving_models: set[str] | None = None,
    verbose: bool = False,
    unmapped: list[str] | None = None,
) -> str:
    missing = imp.unmapped if unmapped is None else unmapped
    selected = list(zip(imp.models, imp.model_ids))
    moving = [(path, mid) for path, mid in selected if path in (moving_models or set())]
    models = (
        [path for path, mid in selected if path not in (moving_models or set())]
        if moving_models
        else imp.models
    )
    model_ids = (
        [mid for path, mid in selected if path not in (moving_models or set())]
        if moving_models
        else imp.model_ids
    )
    lines = [
        f"changed files: {len(imp.changed)}  directly affected: {', '.join(imp.direct) or '-'}",
        f"dependents: {', '.join(imp.dependents) or '-'}",
    ]
    if imp.depth is not None:
        lines.append(
            f"TRUNCATED impact: explicit --depth {imp.depth}; callers beyond this depth were not selected"
        )
    if missing:
        lines.append(
            "UNMAPPED changed files (add each to one component's files): " + ", ".join(missing)
        )
    lines.extend("UNCERTAIN " + message for message in imp.uncertainty[:5])
    if len(imp.uncertainty) > 5:
        lines.append(
            f"UNCERTAIN {len(imp.uncertainty) - 5} more surfaces; use map impact --json for all paths"
        )
    lines.extend("BLOCKED " + message for message in imp.blocked)
    lines.extend("NO CHECKS for: " + path for path in imp.no_checks)
    if imp.comment_only:
        lines.append(
            "comment-only edits (no tests or models selected): " + ", ".join(imp.comment_only)
        )
    lines.extend(
        f"UNEXPLAINED {item} has no model anchor, test or NOT_MODELED reason"
        for item in imp.unexplained[:5]
    )
    if len(imp.unexplained) > 5:
        lines.append(
            f"UNEXPLAINED +{len(imp.unexplained) - 5} more "
            f"(python -m flowguard read --component {imp.unexplained[5].partition(':')[0]})"
        )
    lines.extend(imp.flow_models[:5])
    lines.extend("relies on: " + item for item in imp.relied_models[:5])
    if len(imp.relied_models) > 5:
        lines.append(f"relies on: +{len(imp.relied_models) - 5} more")
    if imp.no_git:
        lines.append(imp.no_git)
    if imp.changed_functions:
        lines.append(
            "changed functions: "
            + ", ".join(imp.changed_functions[:5])
            + (f" +{len(imp.changed_functions)-5}" if len(imp.changed_functions) > 5 else "")
        )
    lines.extend(
        f"UNCERTAIN: {path}: {reason}; this file uses the broad selection"
        for path, reason in sorted(imp.uncertain_files.items())
    )
    if imp.unreached:
        lines.append("no model reaches: " + ", ".join(imp.unreached[:5]))
    lines.extend("also reached: " + line for line in imp.also_reached)
    lines.extend(imp.port_lines)
    if imp.changed_functions or imp.no_git:
        choices = [
            mid + (" (" + imp.model_reasons[mid][0] + ")" if imp.model_reasons.get(mid) else "")
            for mid in model_ids
        ]
        lines.append(
            f"models to run ({len(choices)}): "
            + (", ".join(choices[:8]) or "-")
            + (f" +{len(choices)-8}" if len(choices) > 8 else "")
        )
    else:
        lines.append(
            f"models to run: {len(models)} selected (full list: python -m flowguard map impact --json)"
            if len(models) > 8
            else f"models to run: {', '.join(models) or '-'}"
        )
    if moving:
        lines.append(
            "moving to target: "
            + ", ".join(mid for path, mid in moving)
            + " (python -m flowguard target check runs their target versions)"
        )
    lines.extend(imp.consumer_lines)
    lines.extend(imp.promise_lines)
    lines.extend(
        "WARN promise_removed " + finding["component"] + ": " + finding["message"]
        for finding in imp.promise_findings
    )
    groups, no_command = test_groups(imp)
    commands = run_commands(imp, moving_models=moving_models)
    if imp.changed_functions or imp.test_functions:
        lines.append(
            f"tests to run ({imp.selected_test_functions} of {imp.total_test_functions} test functions, {len(imp.tests)} file"
            + ("s" if len(imp.tests) != 1 else "")
            + f"): bound {imp.bound_test_count}, calling {imp.calling_test_count}, whole files {len(imp.whole_test_files)}"
        )
    else:
        lines.append(
            f"tests to run ({len(imp.tests)} of {imp.total_tests}): "
            + ("see run below" if imp.tests else "-")
        )
    import shlex

    counts = getattr(imp, "_test_function_counts", {})
    for (command, selectors), rendered in zip(groups.items(), commands):
        argv = shlex.split(command)
        pytest = (
            len(argv) >= 3
            and argv[1:3] == ["-m", "pytest"]
            or bool(argv)
            and Path(argv[0]).name in {"pytest", "pytest.exe"}
        )
        if verbose or not pytest:
            lines.append("run: " + rendered)
            continue
        files = list(dict.fromkeys(selector.partition("::")[0] for selector in selectors))
        tests = sum(1 if "::" in selector else counts.get(selector, 1) for selector in selectors)
        names = ", ".join(files[:3])
        if len(files) > 3:
            names += f", +{len(files)-3} more"
        lines.append(
            f"run: python -m flowguard change --run (pytest: {tests} tests in {len(files)} files: {names})"
        )
    lines.extend("NO TEST COMMAND for: " + test for test in no_command)
    lines.extend("run: " + command for command in commands[len(groups) :])
    for cid in imp.needs_review:
        message = f"REVIEW {cid}: its files changed; update its description if behavior changed, then confirm {cid}"
        if imp.review_models.get(cid):
            message += (
                f"; models to re-read: {', '.join(imp.review_models[cid])} "
                "(does the change need a new input, state or invariant?)"
            )
        lines.append(message)
    for cid in imp.map_review:
        lines.append(f"NOTE {cid}: map description changed; verification selection shown above")
    return "\n".join(lines)

class ChangedFiles(list):
    """An operation-local file list carrying the explicit no-git explanation."""
    def __init__(self, paths, no_git=''):
        super().__init__(paths)
        self.no_git=no_git


def _no_git_changes(root, data=None, inv=None):
    from .mapfile import load_map, owner_index
    from .inventory import build_inventory
    data=data if data is not None else load_map(root)
    inv=inv if inv is not None else build_inventory(root,ignore_patterns(data))
    stale=[c for c in data['components'] if c.get('status')!='confirmed' or is_stale(root,c,inv)]
    owned,_=owner_index(data,inv)
    unmapped=[path for path in inv.source if path not in owned and not inv.is_test(path)
              and not path.startswith('.flowguard/') and not any(part.endswith('.egg-info') or part in ('build','dist') for part in Path(path).parts)]
    paths=sorted({path for comp in stale for path in component_files(comp,inv)}|set(unmapped))
    ids=', '.join(c['id'] for c in stale) or '-'
    note=(f'NO GIT: changed files = the files of {len(stale)} component(s) whose fingerprint differs from map.json ({ids}) and {len(unmapped)} unmapped file(s); '
          'tests come from those components; a test file edited alone is not seen: run it by path; there is no old text, so these files use the file-level selection; model files are compared by target check, not here')
    return ChangedFiles(paths,note)

def _closure(edges, start):
    # Keep the internal call site compatible; discovery owns reachability for all views.
    from .discover import reachable_functions
    return reachable_functions(edges, start)


def _changed_symbols(root, inv, changed, base, raw):
    """Qualified changed symbols and explicit uncertainty, using the one AST digest owner."""
    from .inventory import function_digests, resolve_module
    functions, uncertain = set(), {}
    reverse = defaultdict(set)
    for caller, targets in raw.get('edges', {}).items():
        for target in targets: reverse[target].add(caller)
    for path in changed:
        if inv.is_test(path) or path.startswith('.flowguard/') or path not in inv.source and Path(path).suffix not in SOURCE_EXTS:
            continue
        if not path.endswith('.py'):
            uncertain[path] = 'not Python'; continue
        if path in inv.dynamic_files:
            uncertain[path] = 'dynamic imports'; continue
        if path.endswith('__init__.py') and path in inv.py and inv.py[path].lazy_exports:
            uncertain[path] = 'lazy package exports'; continue
        previous = subprocess.run(['git','-C',str(root),'show',f'{base}:{path}'],capture_output=True) if base else None
        if previous is None or previous.returncode:
            uncertain[path] = 'no old source text'; continue
        try:
            before = function_digests(normalize_newlines(previous.stdout))
            source = read_source(root/path)
            after = function_digests(source)
        except (OSError, SyntaxError, ValueError):
            uncertain[path] = 'source cannot be parsed'; continue
        if set(before['functions']) - set(after['functions']) or set(before['classes']) - set(after['classes']):
            uncertain[path] = 'a symbol was removed or renamed'; continue
        if before['statements'] != after['statements']:
            uncertain[path] = 'a nonbinding module statement changed'; continue
        signature_changed = set()
        for symbol, value in after['functions'].items():
            old = before['functions'].get(symbol)
            if old != value:
                functions.add(path+'#'+symbol)
            if old and old['sig_digest'] != value['sig_digest']:
                signature_changed.add(path+'#'+symbol)
        for symbol, value in after['classes'].items():
            old = before['classes'].get(symbol)
            if old and set(old['names']) - set(value['names']):
                uncertain[path] = 'a class binding was removed or renamed'
            if old != value:
                class_node = path+'#'+symbol
                functions.add(class_node)
                signature_changed.add(class_node)
                functions.update(path+'#'+name for name in after['functions'] if name.startswith(symbol+'.'))
                _binding_users(root,inv,path,symbol.split('.')[0],functions,raw)
        for node in signature_changed:
            functions.update(reverse.get(node, ()))
        for name, value in before['bindings'].items():
            if after['bindings'].get(name) != value:
                _binding_users(root,inv,path,name,functions,raw)
        for importer,info in inv.py.items():
            if path in inv.file_deps.get(importer, ()):
                try:
                    syntax=ast.parse(read_source(root/importer))
                    if any(isinstance(n,ast.ImportFrom) and any(a.name=='*' for a in n.names) for n in ast.walk(syntax)):
                        uncertain[path]='a project file imports this file with *'
                except (OSError,SyntaxError): pass
    return functions, uncertain


def _binding_users(root, inv, path, name, functions, raw):
    """Resolve imported names/aliases before matching actual function references."""
    from .inventory import resolve_module
    for other in inv.py:
        if other != path and path not in inv.file_deps.get(other, ()):
            continue
        try: syntax = ast.parse(read_source(root/other))
        except (OSError,SyntaxError): continue
        names = {name} if other == path else set()
        modules = set()
        # Local imports are included; shadowing can only conservatively add callers.
        for statement in ast.walk(syntax):
            if isinstance(statement,ast.ImportFrom):
                parts=other.removesuffix('.py').split('/')[:-1]
                module='.'.join(parts[:len(parts)-statement.level+1]+([statement.module] if statement.module else [])) if statement.level else statement.module or ''
                target=resolve_module(module,other,inv.mod_to_path,inv.py,inv.import_roots)
                if target == path:
                    names.update(alias.asname or alias.name for alias in statement.names if alias.name==name)
            elif isinstance(statement,ast.Import):
                for alias in statement.names:
                    target=resolve_module(alias.name,other,inv.mod_to_path,inv.py,inv.import_roots)
                    if target==path: modules.add(alias.asname or alias.name)
        def dotted(node):
            if isinstance(node,ast.Name): return node.id
            if isinstance(node,ast.Attribute): return dotted(node.value)+'.'+node.attr
            return ''
        def visit(nodes,prefix=''):
            for statement in nodes:
                if isinstance(statement,(ast.FunctionDef,ast.AsyncFunctionDef)):
                    symbol=prefix+statement.name
                    class References(ast.NodeVisitor):
                        found=False
                        def visit_FunctionDef(self,node): pass
                        visit_AsyncFunctionDef=visit_FunctionDef
                        def visit_ClassDef(self,node): pass
                        def visit_Name(self,node):
                            if isinstance(node.ctx,ast.Load) and node.id in names: self.found=True
                        def visit_Attribute(self,node):
                            if node.attr==name and dotted(node.value) in modules: self.found=True
                            self.generic_visit(node)
                    references=References()
                    for item in [*statement.body,*statement.decorator_list,*statement.args.defaults,*statement.args.kw_defaults]:
                        if item is not None: references.visit(item)
                    if references.found: functions.add(other+'#'+symbol)
                    visit(statement.body,symbol+'.')
                elif isinstance(statement,ast.ClassDef): visit(statement.body,prefix+statement.name+'.')
                else:
                    for attribute in ('body','orelse','finalbody'):
                        if isinstance(getattr(statement,attribute,None),list): visit(getattr(statement,attribute),prefix)
        visit(syntax.body)


def select_tests(root, data, inv, tree, selected, changed_functions, *, changed=(), uncertain=(), raw=None, extra_files=()):
    """Select bound/direct-call nodes; only the listed fallback cases select whole files."""
    import re
    from .testtree import test_functions, resolve_test_anchor, test_calls
    from .discover import discover_inventory
    raw = raw if raw is not None else discover_inventory(root,inv,data=data,write_cache=False)
    sources, collected, calls = {}, {}, {}
    for path in inv.tests:
        if not path.endswith('.py') or not is_collectable_test(path): continue
        try: sources[path]=read_source(root/path)
        except OSError: continue
        collected[path]=test_functions(sources[path])
        calls[path]=test_calls(path,sources[path],inv)
    nodes=defaultdict(set)
    bound=set()
    for mid in selected:
        if mid not in tree.nodes: continue
        for anchors in tree.nodes[mid].contract.get('TESTED_BY',{}).values():
            for anchor in anchors:
                path,_,symbol=anchor.partition(':')
                resolved=resolve_test_anchor(root/path,symbol)
                if resolved is None: continue
                parameters='['+symbol.split('[',1)[1] if '[' in symbol else ''
                qualified=resolved+parameters
                nodes[path].add(qualified); bound.add((path,qualified))
    targets={fn.replace('#',':',1) for fn in changed_functions}
    closures={}
    def reaches(call):
        start=call.replace(':','#',1)
        if start not in closures: closures[start]=_closure(raw.get('edges',{}),start)
        return closures[start]
    calling=set(); indirect=defaultdict(int)
    for path, tests in calls.items():
        for symbol, sites in tests.items():
            direct=sites & targets
            if direct:
                nodes[path].add(symbol); calling.add((path,symbol))
            for target in targets - direct:
                if any(target.replace(':','#',1) in reaches(site) for site in sites): indirect[target]+=1
    whole={path for path in changed if path in collected}
    whole.update(extra_files)
    for path in changed:
        if Path(path).name=='conftest.py':
            prefix=path.rpartition('/')[0]
            whole.update(t for t in collected if not prefix or t.startswith(prefix+'/'))
    if uncertain: whole.update(_tests_reaching(inv,list(uncertain),package_init=False))
    # A direct imported symbol mentioned without a resolved call is a file-level fallback.
    for path, source in sources.items():
        for fn in changed_functions:
            target,_,symbol=fn.partition('#')
            if target not in inv.file_deps.get(path,()): continue
            leaf=symbol.rpartition('.')[2]
            any_call=any(target+':'+symbol in sites for sites in calls[path].values())
            if not any_call and re.search(r'\b'+re.escape(leaf)+r'\b',source): whole.add(path)
    for path, chosen in nodes.items():
        resolved={name.split('[',1)[0] for name in chosen}
        if collected.get(path) and len(resolved)*2>=len(collected[path]): whole.add(path)
    whole.intersection_update(set(inv.tests))
    for path in whole: nodes.setdefault(path,set())
    # All-case anchors dominate parameter-specific anchors of the same function.
    for path, chosen in nodes.items():
        chosen.difference_update(name for name in list(chosen) if '[' in name and name.split('[',1)[0] in chosen)
    return dict(nodes={path:sorted(chosen) for path,chosen in sorted(nodes.items())},whole_files=sorted(whole),
                bound=len(bound),calling=len(calling-bound),total=sum(map(len,collected.values())),
                selected=sum(len(collected.get(path,{})) if path in whole else len({name.split('[',1)[0] for name in chosen}) for path,chosen in nodes.items()),
                also_reached=[f'{count} test functions call {fn} only through other functions (python -m flowguard change --broad)' for fn,count in sorted(indirect.items())])


SETTINGS_KEYS = ("accepted_debts", "large_model_seconds", "large_test_seconds", "model_digests")
COMPONENT_SETTINGS = ("tests", "summary", "responsibilities", "status", "fingerprint")


_PREVIOUS_MAP_UNREAD = object()


def _map_settings_tests(root, data, inv, base, *, previous=_PREVIOUS_MAP_UNREAD):
    if previous is _PREVIOUS_MAP_UNREAD:
        previous = _previous_map(root, base)
    if previous is None:
        return None

    def structure(mapping):
        result = {key: value for key, value in mapping.items() if key not in SETTINGS_KEYS}
        result["components"] = [
            {key: value for key, value in component.items() if key not in COMPONENT_SETTINGS}
            for component in mapping.get("components", ())
        ]
        return result

    if structure(previous) != structure(data):
        return None
    old = {component["id"]: component for component in previous.get("components", ())}
    return {
        path
        for component in data.get("components", ())
        for path in inv.tests
        if matches_any(path, component.get("tests", ()))
        and not matches_any(path, old.get(component["id"], {}).get("tests", ()))
    }


def compute_impact(
    root: Path,
    data: dict,
    inv: Inventory,
    changed: list[str],
    depth: int | None = None,
    *,
    base: str | None = None,
    broad: bool = False,
) -> Impact:
    """Select exact owned/reachable functions, with explicit conservative uncertainty."""
    from .discover import discover_inventory, relied_models
    from .mapfile import owner_index

    if changed is None:
        changed = changed_files(root, base or "HEAD", data=data, inv=inv)
    no_git = getattr(changed, "no_git", "")
    changed = sorted(
        {
            project_relative(root, path)
            for path in changed
            if not project_relative(root, path).startswith(".flowguard/target/")
        }
    )
    previous = _previous_map(root, base) if ".flowguard/map.json" in changed else None
    settings_tests = (
        _map_settings_tests(root, data, inv, base, previous=previous)
        if ".flowguard/map.json" in changed
        else None
    )
    description_review = []
    if settings_tests is not None:
        old_components = {component["id"]: component for component in previous["components"]}
        description_review = [
            component["id"]
            for component in data["components"]
            if any(
                component.get(key) != old_components[component["id"]].get(key)
                for key in ("summary", "responsibilities")
            )
        ]
    effective = [
        path for path in changed if path != ".flowguard/map.json" or settings_tests is None
    ]
    if broad:
        result = _broad_impact(root, data, inv, effective, depth, base=base, broad=True)
        result.changed = changed
        result.no_git = no_git
        result.map_changed = ".flowguard/map.json" in changed
        result.map_review = sorted(set(result.map_review) | set(description_review))
        if settings_tests:
            from .testtree import test_functions

            added = settings_tests - set(result.tests)
            counts = result._test_function_counts
            if not counts:
                counts.update(
                    {
                        path: len(test_functions(read_source(root / path)))
                        for path in inv.tests
                        if path.endswith(".py")
                    }
                )
            result.tests = sorted(set(result.tests) | settings_tests)
            result.whole_test_files = sorted(set(result.whole_test_files) | settings_tests)
            result.selected_test_functions += sum(counts.get(path, 0) for path in added)
            result.total_test_functions = sum(counts.values())
            result.test_commands, problems = _commands_for_tests(data, previous, result.tests)
            result.blocked = sorted(set(result.blocked) | set(problems))
        return result
    if not changed:
        result = _broad_impact(root, data, inv, [], depth, base=base, package_init=False)
        result.no_git = no_git
        return result
    comments = {path for path in changed if _comment_only(root, base, path)}
    source_changes = [
        path
        for path in changed
        if path not in comments
        and not inv.is_test(path)
        and not path.startswith(".flowguard/")
        and (path in inv.source or Path(path).suffix in SOURCE_EXTS)
    ]
    literal_tree = build_tree(root, data, inv)
    consumer_lines, literal_models, literal_functions, literal_tests = _literal_impact(
        root, data, inv, literal_tree, changed, base
    )
    raw = (
        discover_inventory(root, inv, data=data, write_cache=False)
        if source_changes or literal_functions
        else {"files": {}, "edges": {}}
    )
    functions, uncertain = _changed_symbols(root, inv, source_changes, base, raw)
    functions.update(literal_functions)
    certain = set(source_changes) - set(uncertain)
    result = _broad_impact(
        root,
        data,
        inv,
        [path for path in effective if path not in certain],
        depth,
        base=base,
        package_init=False,
    )
    tree = build_tree(root, data, inv)
    owner, _ = owner_index(data, inv)
    direct = {owner[path] for path in changed if path in owner}
    result.changed = changed
    result.map_changed = ".flowguard/map.json" in changed
    result.map_review = sorted(set(result.map_review) | set(description_review))
    result.direct = sorted(set(result.direct) | direct)
    result.needs_review = sorted(
        set(result.needs_review)
        | {c["id"] for c in data["components"] if c["id"] in direct and is_stale(root, c, inv)}
    )
    result.review_models.update(
        {cid: [node.id for node in tree.models_for_component(cid)] for cid in direct}
    )
    result.comment_only = sorted(comments)
    result.unmapped = sorted(
        set(result.unmapped)
        | {
            path
            for path in certain
            if path not in owner and not matches_any(path, ignore_patterns(data))
        }
    )
    selected = set(result.model_ids) | literal_models
    result.consumer_lines = consumer_lines
    result.promise_lines, result.promise_findings = _git_promise_notes(root, data, changed, base)
    from .discover import select_model_functions, anchor_matches

    chosen, reasons, flow_lines, unreached = select_model_functions(data, inv, tree, raw, functions)
    selected.update(chosen)
    result.flow_models.extend(flow_lines)
    own = {mid: node.contract.get("IMPLEMENTED_BY", {}) for mid, node in tree.nodes.items()}
    if source_changes:
        sites = relied_models(
            raw,
            data,
            inv,
            {mid: list(anchors.values()) for mid, anchors in own.items()},
            files=list(certain),
        )
        result.relied_models = sorted(
            set(result.relied_models)
            | {
                f"{mid} via {cid}:{symbol}"
                for mid, locations in sites.items()
                for cid, symbol in locations
            }
        )
        # Full unexplained facts are needed for unowned entrypoints/writers, not owned edits.
        if certain and (
            not functions
            or any(
                not any(
                    anchor_matches(anchor, fn)
                    for anchors in own.values()
                    for anchor in anchors.values()
                )
                for fn in functions
            )
        ):
            from .lint import coverage_facts

            for cid, record in coverage_facts(root, data, inv, tree, raw).items():
                entries = set(record.get("unexplained_entries", ()))
                result.unexplained.extend(
                    f"{cid}: {anchor} ({'entrypoint' if anchor in entries else 'state writer'})"
                    for anchor in record["unexplained"]
                    if anchor.partition(":")[0] in certain
                )
    pairs = sorted((node.path, mid) for mid, node in tree.nodes.items() if mid in selected)
    result.models = [path for path, mid in pairs]
    result.model_ids = [mid for path, mid in pairs]
    result.changed_functions = sorted(fn.replace("#", ":", 1) for fn in functions)
    result.uncertain_files = uncertain
    result.unreached = unreached
    result.model_reasons = dict(reasons)
    result.no_git = no_git
    whole_fallback = bool(uncertain) or any(
        (
            path not in source_changes
            and not inv.is_test(path)
            and not path.startswith(".flowguard/models/")
            and path not in comments
        )
        or (path.startswith(".flowguard/models/") and not (root / path).is_file())
        or (inv.is_test(path) and not is_collectable_test(path))
        for path in effective
    )
    extra = (
        set(result.tests) if whole_fallback else {path for path in result.tests if path in changed}
    )
    if no_git:
        extra.update(
            path
            for c in data["components"]
            if c["id"] in direct
            for path in inv.tests
            if matches_any(path, c.get("tests", ()))
        )
    selection = select_tests(
        root,
        data,
        inv,
        tree,
        selected,
        functions,
        changed=changed,
        uncertain=uncertain,
        raw=raw,
        extra_files=extra | literal_tests | set(settings_tests or ()),
    )
    result.tests = sorted(selection["nodes"])
    result.test_commands, command_problems = _commands_for_tests(data, previous, result.tests)
    result.blocked = sorted(set(result.blocked) | set(command_problems))
    result.test_functions = {
        path: names
        for path, names in selection["nodes"].items()
        if path not in selection["whole_files"]
    }
    result.whole_test_files = selection["whole_files"]
    result.selected_test_functions = selection["selected"]
    result.total_test_functions = selection["total"]
    result.bound_test_count = selection["bound"]
    result.calling_test_count = selection["calling"]
    result.also_reached = selection["also_reached"]
    return result


from .impact_history import (_anchor_changed, _binding_indexes, _commands_for_tests, _comment_only, _git_promise_notes, _literal_impact, _owner_model_paths, _previous_map, _read_git_paths, _removed_model_context, _tests_reaching, project_relative)

from .impact_scope import (
    Impact,
    _broad_impact,
)

from .impact_scope import VERIFICATION_FIELDS
