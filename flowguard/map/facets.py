"""Static node facets: literals and source facts, never imported model hooks."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from .common import matches_any, read_source, parse_test_anchor
from .inventory import Inventory
from .lint import architecture_variants, coverage_facts, explained_by, test_source
from .mapfile import owner_index, component_files, component_scope, component_subtree, is_stale, resolve_model_path


@dataclass(frozen=True)
class Facets:
    purpose: str
    rules: tuple[str, ...]
    rules_source: str
    known_bad: tuple[str, ...]
    known_bad_source: str
    code: tuple[str, ...]
    tests: tuple[str, ...]
    rule_count: int | None
    test_count: int
    rule_notes: tuple[str, ...] = ()    # description of each rule, aligned with ``rules``
    model_id: str = ""
    cases: tuple | None = None          # feature-kit models: (defect names, benign names)

    @property
    def known_bad_count(self) -> int | None:
        return None if self.known_bad_source == "runtime" else len(self.known_bad)

    @property
    def rule_count_text(self) -> str:
        """Exact count, ``~N`` for names merely found in the file, ``?`` when unreadable."""
        if self.rule_count is None:
            return "?"
        return f"~{self.rule_count}" if self.rules_source == "file" else str(self.rule_count)


from .modelstatic import StaticModel as _StaticModel, file_rules as _file_rules, call_name as _call_name, BUILTIN_RULE_HELPERS


def model_port_line(node, tree, *, limit=200):
    """One bounded port line; model literals own the data, this view owns its presentation."""
    from .port import Port, keeps_classes
    port = node.contract.get("port", Port())
    def brief(items):
        items = list(items)
        return ",".join(map(str, items[:6])) + (f",+{len(items)-6}" if len(items)>6 else "")
    parts = ["state " + (brief(port.state) if port.state is not None else "?")]
    if port.reads_parent:
        parts.append("reads parent " + brief(port.reads_parent))
    if port.outputs:
        outputs = []
        for key, values in port.outputs.items():
            destinations = []
            for other in tree.nodes.values():
                item = (other.contract.get("HANDOFF", {}).get(node.id, {}) or {}).get(key)
                if item is not None:
                    into = item if isinstance(item, str) else item[0]
                    destinations.append(other.id + ("." + into if into else ""))
            outputs.append(f"{key}=" + "|".join(map(str, values)) + (" -> " + brief(destinations) if destinations else ""))
        parts.append("out " + brief(outputs))
    elif port.outputs is None and node.parent_kind == "model":
        parts.append("out ?")
    if port.keeps:
        kinds = keeps_classes(node.id)
        parts.append("keeps " + brief(name+(f"({kinds[name]})" if name in kinds else "") for name in port.keeps))
    received = []
    for child, keys in (port.handoff or {}).items():
        for key, item in keys.items():
            into = item if isinstance(item, str) else item[0]
            received.append(f"{child}.{key} -> {into}")
    if received:
        parts.append("from " + brief(received))
    for selector, alternatives in (port.dispatch or {}).items():
        parts.append(f"dispatch {selector}: " + brief(f"{value}->{child}" for value,child in alternatives.items()))
    line = "port: " + ("~ " if port.approximate else "") + " | ".join(parts)
    return line if len(line)<=limit else line[:max(0,limit-3)]+"..."


def model_facets(root: Path, node, *, view=None) -> Facets:
    contract = node.contract
    try:
        path = resolve_model_path(root, node.path, view=view)
        if path is None:
            raise FileNotFoundError(node.path)
        syntax = ast.parse(read_source(path))
    except (OSError, SyntaxError):
        syntax = ast.Module(body=[], type_ignores=[])
    doc = ast.get_docstring(syntax)
    purpose = doc.strip().splitlines()[0] if doc and doc.strip() else "(no purpose line: add a module docstring)"
    static = _StaticModel(root, node.path, syntax, view=view)
    found = static.explorer_rules()
    if found is not None:
        source, notes = "explorer", dict(sorted(found))
    else:
        notes = dict.fromkeys(_file_rules(syntax), "")
        source = "file" if notes else "runtime"
    rules = set(notes)
    known = static.known_bad()
    literal_bad = known is not None
    bad = known if literal_bad else ()
    from .mapfile import load_map, MapError, process_model_reason
    try:
        reason = process_model_reason(view.data if view is not None else load_map(root), contract)
    except MapError:
        reason = ""
    code = [f"{block} -> {anchor}" for block, anchor in sorted(contract.get("IMPLEMENTED_BY", {}).items())]
    if reason:
        code.append(f"process model (no code yet): {reason}")
    code.extend(f"USES {name} -> {anchor}" for name, anchor in sorted(contract.get("USES", {}).items()))
    if contract.get("NOT_MODELED"):
        code.append(f"not modeled: {len(contract['NOT_MODELED'])}")
    tests = [f"{rule} -> {anchor}" + (" (not nested)" if anchor.split(":", 1)[0] in node.nonnested_tests else "")
             for rule, anchors in sorted(contract.get("TESTED_BY", {}).items()) for anchor in anchors]
    untested = sorted(rule for rule in rules if not contract.get("TESTED_BY", {}).get(rule))
    if untested:
        tests.append("untested: " + ", ".join(untested))
    names = tuple(sorted(rules))
    return Facets(purpose, names, source, bad, "literal" if literal_bad else "runtime",
                  tuple(code), tuple(tests), len(rules) if source != "runtime" else None,
                  sum(len(anchors) for anchors in contract.get("TESTED_BY", {}).values()),
                  tuple(notes[name] for name in names), node.id, static.cases if source == "explorer" else None)


def coverage_line(coverage, *, summary=False):
    """Explained counts split by source: a model anchor, a test naming it, or a NOT_MODELED reason."""
    records = [record.get("_direct", record) for record in coverage.values()] if summary else [coverage]

    def part(label, key, sources):
        done, total = (sum(record[key][i] for record in records) for i in (0, 1))
        model, test, reason = (sum(record.get(sources, (0, 0, 0))[i] for record in records) for i in (0, 1, 2))
        text = f"{label} {model + test} of {total} bound (model {model}, test {test}), {reason} by reason"
        if key == "entrypoints":
            text += f", {sum(record.get('unlisted', 0) for record in records)} unlisted"
        return text
    line = ("coverage: " + part("entrypoints", "entrypoints", "entry_sources") + "; "
            + part("state writers", "state_writers", "writer_sources"))
    if summary:
        return line
    missing = coverage["unexplained"]
    if missing:
        line += "; unexplained: " + ", ".join(missing[:5])
        if len(missing) > 5:
            line += f" +{len(missing) - 5} more"
        line += " (explain: add it to a model's IMPLEMENTED_BY, bind a TESTED_BY test, or add NOT_MODELED with a reason)"
    return line


def _test_function_index(root: Path, inv: Inventory, *, source_cache=None) -> dict[str, set[str]]:
    """One view-local index: inventory symbols alone also include variables and classes."""
    found = {}
    for path in inv.tests:
        if not path.endswith(".py"):
            continue
        from .testtree import test_functions
        try:
            names = set(test_functions(test_source(root, path, source_cache)))
        except OSError:
            names = set()
        found[path] = names
    return found


def _bindable(root, unbound, nodes, source_cache, limit=3):
    """Unbound tests whose body names a model anchor symbol as a whole word: ready to bind in TESTED_BY."""
    import re
    anchors = sorted({(node.id, anchor.partition(":")[2].rsplit(".", 1)[-1]) for node in nodes
                      for anchor in node.contract.get("IMPLEMENTED_BY", {}).values() if ":" in anchor})
    found, parsed = [], {}
    for item in unbound:
        path, _, name = item.partition(":")
        if path not in parsed:
            try:
                source = test_source(root, path, source_cache)
                parsed[path] = (source, {f"{owner}.{n.name}" if owner else n.name: n
                                         for owner, n in _test_functions(ast.parse(source))})
            except (OSError, SyntaxError, ValueError):
                parsed[path] = ("", {})
        source, functions = parsed[path]
        node = functions.get(name)
        body = ast.get_source_segment(source, node) or "" if node is not None else ""
        for mid, symbol in anchors:
            if symbol and re.search(rf"(?<!\w){re.escape(symbol)}(?!\w)", body.partition(":")[2]):
                found.append(f"{item} -> model {mid} (mentions {symbol})")
                break
        if len(found) >= limit:
            break
    return found


def _test_functions(syntax):
    for node in syntax.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
            yield "", node
        elif isinstance(node, ast.ClassDef):
            for method in node.body:
                if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)) and method.name.startswith("test"):
                    yield node.name, method


def _test_facts(paths, nodes, functions, *, root=None, source_cache=None):
    actual = {(path, name) for path in paths for name in functions.get(path, ())}
    bound = set()
    for node in nodes:
        for anchors in node.contract.get("TESTED_BY", {}).values():
            for anchor in anchors:
                try:
                    path, name, _ = parse_test_anchor(anchor)
                except ValueError:
                    continue
                matches = {(p, s) for p, s in actual if p == path and s == name}
                if not matches:
                    matches = {(p, s) for p, s in actual if p == path and s.endswith("." + name)}
                if len(matches) == 1:
                    bound.update(matches)
    unbound = sorted(f"{path}:{name}" for path, name in actual - bound)
    facts = [f"{len(paths)} files: " + (", ".join(sorted(paths)) or "-"), f"{len(actual)} functions, {len(bound)} bound"]
    if unbound:
        facts.append("unbound: " + ", ".join(unbound[:5]) + (f" +{len(unbound) - 5} more" if len(unbound) > 5 else ""))
        bindable = _bindable(root, unbound, nodes, source_cache) if root is not None else []
        if bindable:
            facts.append("bindable: " + ", ".join(bindable))
    return tuple(facts), len(actual)


def used_by_lines(data, inv, tree, cid):
    """Read-only model references to this component's code; never ownership or coverage."""
    owner, _ = owner_index(data, inv)
    members = {comp["id"] for comp in component_subtree(data, cid)}
    return [f"  used by: {node.id} (USES {name})" for node in sorted(tree.nodes.values(), key=lambda node: node.id)
            for name, anchor in sorted(node.contract.get("USES", {}).items())
            if owner.get(anchor.partition(":")[0]) in members]


def component_facets(root: Path, data: dict, inv: Inventory, component: dict, tree, graph, functions, *, coverage=None) -> Facets:
    cid = component["id"]
    members = component_subtree(data, cid)
    responsibilities = tuple(rule for member in members for rule in member.get("responsibilities", []))
    scoped = component_scope(data, component)
    files = component_files(scoped, inv)
    code = [f"{len(files)} files/{sum(inv.loc.get(path, 0) for path in files)} loc"]
    if scoped.get("files"):
        code.append("files: " + ", ".join(scoped["files"]))
    for key, label in (("entrypoints", "entry"), ("state", "state"), ("side_effects", "effects")):
        if scoped.get(key):
            code.append(label + ": " + "; ".join(scoped[key]))
    if coverage is not None:
        code.append(coverage_line(coverage))
    if is_stale(root, component, inv):
        code.append("STALE")
    paths = {path for path in inv.tests if matches_any(path, scoped.get("tests", []))}
    tests, count = _test_facts(paths, tree.models_for_component(cid), functions, root=root, source_cache={})
    rules = responsibilities + (
        f"layer {component.get('layer') or '-'} may use: " + (", ".join(scoped.get("depends_on", [])) or "-"),)
    return Facets(component.get("summary") or "(no summary yet)", rules, "map",
                  tuple(dict.fromkeys(name for member in members for name, _, _ in architecture_variants(data, graph, only=member["id"]))), "system", tuple(code), tests,
                  len(responsibilities), count)


def system_facets(data: dict, inv: Inventory, tree, graph, functions, *, coverage=None) -> Facets:
    tests, count = _test_facts(set(inv.tests), tree.nodes.values(), functions)
    return Facets(f"{data.get('project', '')}: {len(data['components'])} components",
                  ("layers order: " + (" > ".join(data.get("layers", [])) or "none"),
                   "no unaccepted dependency cycle", "one owner per responsibility"), "map",
                  tuple(name for name, _, _ in architecture_variants(data, graph)), "system-root",
                  (f"{len(data['components'])} components, {len(inv.source)} source files",)
                  + ((coverage_line(coverage, summary=True),) if coverage is not None else ()), tests, 3, count)


def _definitions(root: Path, logical: str, syntax, view=None):
    """Static rule and known-bad names, each with its defining expression (None when not located)."""
    static = _StaticModel(root, logical, syntax, view=view)
    found = static.explorer_rules()
    rules = [name for name, _ in found] if found is not None else _file_rules(syntax)
    for node in ast.walk(syntax):
        if isinstance(node, ast.Call) and (_call_name(node) == "Invariant" or _call_name(node) in BUILTIN_RULE_HELPERS):
            given = node.args[0] if node.args else next((k.value for k in node.keywords if k.arg == "name"), None)
            name = static.value(given, static.main) if given is not None else None
            if isinstance(name, str) and name in rules:
                static.rule_defs.setdefault(name, static._definition(node, static.main))
    bad = static.known_bad() or ()
    return ({name: static.rule_defs.get(name) for name in rules}, {name: static.bad_defs.get(name) for name in bad})


def target_goal_rules(root: Path, target, view=None, *, current_data=None) -> list[str]:
    """Compare rule definitions globally; a moved name acquires at most one new owner."""
    from .mapfile import load_map, model_registry
    from .targetfile import build_target_view
    current = load_map(root) if current_data is None else current_data
    view = view or build_target_view(root, current, target)
    def definitions(data, planned=None):
        found = {}
        for entry in model_registry(root, data, view=planned).entries:
            if entry.kind != "contract":
                continue
            path = planned.resolve(entry.path) if planned is not None else root / entry.path
            try:
                syntax = ast.parse(read_source(path))
                rules, bad = _definitions(root, entry.path, syntax, planned)
                found[entry.id] = (rules, bad, syntax)
            except (OSError, SyntaxError, ValueError, TypeError):
                continue
        return found
    before, after = definitions(current), definitions(view.data, view)
    targets = []
    for filename, physical in sorted(target.models.items()):
        if filename.startswith("_"):
            continue
        try:
            syntax = ast.parse(read_source(root / physical))
            mid = next((n.value.value for n in syntax.body if isinstance(n, ast.Assign)
                        and any(isinstance(t, ast.Name) and t.id == "MODEL_ID" for t in n.targets)
                        and isinstance(n.value, ast.Constant)), Path(filename).stem)
            if mid in after:
                targets.append(mid)
        except (OSError, SyntaxError, ValueError):
            continue
    moved = _moved_names(before, after, targets)
    out = []
    for mid in targets:
        new = after[mid]
        old = before.get(mid, ({}, {}, None))
        changed_file = old[2] is None or ast.dump(new[2]) != ast.dump(old[2])
        items = []
        for kind, label in ((0, ""), (1, " (known-bad)")):
            for name, definition in sorted(new[kind].items()):
                donor = moved.get((mid, kind, name))
                if donor:
                    items.append(f">{name} (from {donor}){label}")
                elif name not in old[kind]:
                    items.append(f"+{name}{label}")
                elif ((definition is None or old[kind][name] is None) and changed_file
                      or definition is not None and old[kind][name] is not None and definition != old[kind][name]):
                    items.append(f"~{name}{label}")
            for name in sorted(set(old[kind]) - set(new[kind])):
                if not any(k == kind and n == name and donor == mid for (r, k, n), donor in moved.items()):
                    items.append(f"-{name}{label}")
        if items:
            out.append(f"model {mid}: " + ", ".join(items))
    return out


NO_PROMISE_GOAL = "goal rules: none (no promise changes: structure and descriptions only; system rules apply)"


def goal_rules_line(root: Path, current_data: dict, target, view) -> tuple[str, list, list]:
    """(the ``goal rules:`` line, goal items, promise changes) shared by target check and read --target."""
    from .targetfile import target_promise_changes

    goal = target_goal_rules(root, target, view, current_data=current_data)
    promises = target_promise_changes(current_data, view.data, target)
    line = "goal rules: " + "; ".join(goal) if goal else "goal rules: none" if promises else NO_PROMISE_GOAL
    return line, goal, promises

def _moved_names(before, after, targets, kinds=(0, 1)):
    """One relocation decision for goal rules and removed-promise reporting."""
    moved={}
    for kind in kinds:
        names={name for mid in targets for name in after[mid][kind] if name not in before.get(mid, ({}, {}, {}))[kind]}
        for name in sorted(names):
            donors=sorted(mid for mid in before if name in before[mid][kind] and name not in after.get(mid, ({}, {}, {}))[kind])
            recipients=sorted(mid for mid in targets if name in after[mid][kind] and name not in before.get(mid, ({}, {}, {}))[kind])
            if not donors: continue
            chosen=None
            if len(recipients)==1:
                recipient=recipients[0]
                donor=next((mid for mid in donors if before[mid][kind][name] is not None and before[mid][kind][name]==after[recipient][kind][name]),donors[0])
                chosen=(recipient,donor)
            else:
                exact=[(recipient,donor) for recipient in recipients for donor in donors if before[donor][kind][name] is not None and before[donor][kind][name]==after[recipient][kind][name]]
                if len(exact)==1: chosen=exact[0]
            if chosen: moved[(chosen[0],kind,name)]=chosen[1]
    return moved


def model_promises(root, logical, syntax, view=None):
    """Rule/bad definitions, binding names and actual State fields from one model's source."""
    from .port import model_port
    rules,bad=_definitions(root,logical,syntax,view)
    declarations={}
    for node in syntax.body:
        if isinstance(node,ast.Assign):
            for name in node.targets:
                if isinstance(name,ast.Name):
                    try: declarations[name.id]=ast.literal_eval(node.value)
                    except (ValueError,TypeError): pass
    tests=declarations.get('TESTED_BY',{})
    bindings={}
    for name,anchors in tests.items() if isinstance(tests,dict) else ():
        for anchor in anchors:bindings.setdefault(anchor,[]).append(name)
    tests={anchor:tuple(sorted(names)) for anchor,names in bindings.items()}
    return (rules,bad,tests,model_port(syntax).state,declarations.get('PARENT'),logical)


def promise_changes(before, after, changed):
    """Report intentional removals as warnings; distinguish a single receiving owner."""
    moved=_moved_names(before,after,sorted(set(changed)&set(after)),(0,1,2))
    labels=('rule','known-bad','test')
    warnings=[]; lines=[]
    for mid in sorted(set(changed)&set(before)):
        entries=[]
        old,new=before[mid],after.get(mid,({},{},{},(),None,''))
        for kind,label in enumerate(labels):
            for name in sorted(set(old[kind])-set(new[kind])):
                if any(k==kind and n==name and donor==mid for (recipient,k,n),donor in moved.items()): continue
                display=name
                if kind==2:
                    bindings=old[kind][name]
                    display=', '.join(bindings)
                    if len(bindings)!=1 or sum(bindings[0] in names for names in old[kind].values())>1:
                        display+=' ('+name+')'
                item=f'-{label} {display}'
                entries.append(item)
                warnings.append(dict(level='warn',code='promise_removed',component=mid,message=item))
        if old[3] is not None and new[3] is not None:
            retained=set(new[3])
            for child,record in after.items():
                parent,seen=record[4],{child}
                while parent in after and parent not in seen:
                    if parent==mid:
                        retained.update(record[3] or ());break
                    seen.add(parent);parent=after[parent][4]
            for field in sorted(set(old[3])-retained):
                item='-field '+field;entries.append(item)
                warnings.append(dict(level='warn',code='promise_removed',component=mid,message=item))
        if entries: lines.append('promises: '+mid+': '+'; '.join(entries))
    pairs={}
    for (recipient,kind,name),donor in moved.items():
        counts=pairs.setdefault((donor,recipient),[0,0,0]);counts[kind]+=1
    lines.extend(f'moved: {count[0]} rule(s), {count[1]} known-bad, {count[2]} test(s) from {donor} to {recipient}' for (donor,recipient),count in sorted(pairs.items()))
    return lines,warnings

def promise_records(root, data, view=None):
    from .mapfile import model_registry
    found={}
    for entry in model_registry(root,data,view=view).entries:
        if entry.kind!='contract':continue
        path=view.resolve(entry.path) if view is not None else root/entry.path
        try:
            syntax=ast.parse(read_source(path))
            found[entry.id]=model_promises(root,entry.path,syntax,view)
        except (OSError,SyntaxError,ValueError,TypeError):continue
    return found


def target_promise_notes(root, current, target, view):
    before=promise_records(root,current)
    after=promise_records(root,view.data,view)
    paths={'.flowguard/models/'+filename for filename in target.models}
    changed={mid for mid,record in {**before,**after}.items() if record[5] in paths}|set(target.remove['model'])
    # A changed shared rule helper can remove a real rule from one of its importers.
    changed.update(mid for mid in before.keys() & after.keys() if before[mid][:3]!=after[mid][:3] or before[mid][3]!=after[mid][3])
    return promise_changes(before,after,changed)
