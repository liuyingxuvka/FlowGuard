"""Git history and literal evidence for impact selection."""
from __future__ import annotations
import ast
import json
import os
import subprocess
import tempfile
from collections import defaultdict, deque
from pathlib import Path
from .common import glob_match, is_collectable_test, norm, normalize_newlines, read_source
from .inventory import Inventory
from .mapfile import model_registry, read_model_contract, top_level_imports



def project_relative(root: Path, path: str) -> str:
    """'C:\\repo\\shop\\api.py', '/repo/shop/api.py' or './shop/api.py' -> 'shop/api.py'."""
    candidate = Path(path)
    if candidate.is_absolute():
        try:
            return candidate.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            pass                                    # outside the project: reported as unmapped
    return norm(path)

def _previous_map(root: Path, base: str | None) -> dict | None:
    if base is None:
        return None
    res = subprocess.run(["git", "-C", str(root), "show", f"{base}:.flowguard/map.json"],
                         capture_output=True)                     # bytes: json.loads decodes UTF-8 itself
    try:
        data = json.loads(res.stdout) if res.returncode == 0 else None
        return data if isinstance(data, dict) and isinstance(data.get("components"), list) else None
    except ValueError:
        return None

def _comment_only(root: Path, base: str | None, path: str) -> bool:
    """Changed, AST-equivalent source only; physical newline differences alone keep the full impact closure."""
    if base is None or not path.endswith(".py"):
        return False
    old = subprocess.run(["git", "-C", str(root), "show", f"{base}:{path}"], capture_output=True)
    try:
        previous = normalize_newlines(old.stdout)
        new = normalize_newlines((root / path).read_bytes())
        return old.returncode == 0 and previous != new and ast.dump(ast.parse(previous)) == ast.dump(ast.parse(new))
    except (OSError, SyntaxError, ValueError):
        return False

def _removed_model_context(root: Path, base: str | None, changed: list[str]) -> tuple[set[str], dict, dict]:
    """Read real Git removals through the canonical static registry; never import old code."""
    if base is None or not any(Path(p).parent.as_posix() == ".flowguard/models" for p in changed):
        return set(), {}, {}
    try:
        removed = {p for p in _read_git_paths(root, "diff", "--no-renames", "--diff-filter=D", "--name-only", "-z",
                                        base, "--", ".flowguard/models")
                   if Path(p).parent.as_posix() == ".flowguard/models" and p.endswith(".py")
                   and not os.path.lexists(root / p)}
        if not removed.intersection(changed):
            return set(), {}, {}
        paths = [p for p in _read_git_paths(root, "ls-tree", "-r", "--name-only", "-z", base, "--", ".flowguard/models")
                 if Path(p).parent.as_posix() == ".flowguard/models" and p.endswith(".py")]
    except subprocess.CalledProcessError:
        return set(), {}, {}             # missing/unknown models retain the existing hard gate
    contracts, imports = {}, {}
    with tempfile.TemporaryDirectory(prefix="flowguard-previous-models-") as directory:
        prior_root = Path(directory)
        for path in paths:
            blob = subprocess.run(["git", "-C", str(root), "show", f"{base}:{path}"], capture_output=True)
            if blob.returncode:
                return removed, {}, {p: [] for p in removed}  # an incomplete namespace cannot prove unique identity
            target = prior_root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(blob.stdout)
            if path in removed:
                try:
                    imports[path] = top_level_imports(ast.parse(read_source(target)))
                except (OSError, SyntaxError, ValueError, TypeError):
                    imports[path] = []
        prior = model_registry(prior_root, {"components": [], "flows": []})
        counts: dict[str, int] = defaultdict(int)
        for entry in prior.entries:
            counts[entry.id] += 1
        for entry in prior.entries:
            if entry.kind == "contract" and counts[entry.id] == 1:
                contracts[entry.path] = read_model_contract(prior_root / entry.path)
    return removed, contracts, imports

def _binding_indexes(data: dict, tree=None) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    tests: dict[str, set[str]] = defaultdict(set)
    models: dict[str, set[str]] = defaultdict(set)
    for comp in data.get("components", []):
        for pat in comp.get("tests", []):
            tests[pat].add(comp["id"])
        paths = [n.path for n in tree.models_for_component(comp["id"])] if tree is not None else comp.get("models", [])
        for path in paths:
            models[path].add(comp["id"])
    return tests, models

def _owner_model_paths(path: str, declared: dict[str, set[str]]) -> set[str]:
    return {path} if path in declared else set()

def _tests_reaching(inv: Inventory, changed: list[str], *, package_init: bool = True) -> set[str]:
    """Runtime import closure including package initialization, without graph hubs."""
    targets = set(changed)
    collectable = {t for t in inv.tests if is_collectable_test(t) and inv.is_test(t)}
    out = set()
    for path in targets:
        if Path(path).name == "conftest.py":
            prefix = path.rpartition("/")[0]
            out.update(t for t in collectable if not prefix or t.startswith(prefix + "/"))
    reverse: dict[str, set[str]] = defaultdict(set)
    for path in inv.source:
        deps = set(inv.file_deps.get(path, ()))
        parts = Path(path).parts[:-1]
        deps.update("/".join((*parts[:i], "__init__.py")) for i in range(1, len(parts) + 1)
                    if package_init and "/".join((*parts[:i], "__init__.py")) in inv.py)
        for dep in deps:
            if dep != path:
                reverse[dep].add(path)
    seen, queue = set(targets), deque(targets)
    while queue:
        for caller in reverse.get(queue.popleft(), ()):
            if caller not in seen:
                seen.add(caller)
                queue.append(caller)
    return out | (seen & collectable)

def _anchor_changed(root, base, path, symbol):
    from .inventory import function_digests
    if base is None or not path.endswith('.py'): return True
    previous=subprocess.run(['git','-C',str(root),'show',f'{base}:{path}'],capture_output=True)
    if previous.returncode: return True
    try:
        old=function_digests(normalize_newlines(previous.stdout))
        new=function_digests(read_source(root/path))
    except (OSError,SyntaxError,ValueError): return True
    return any(old[group].get(symbol)!=new[group].get(symbol) for group in ('functions','classes')) or not any(symbol in old[group] for group in ('functions','classes'))

def _commands_for_tests(data, previous, tests):
    test_commands, blocked = {}, []
    for test in sorted(tests):
        commands = {cmd for pat, cmd in data.get("test_commands", {}).items() if glob_match(test, pat)}
        if not commands:
            commands = {cmd for pat, cmd in (previous or {}).get("test_commands", {}).items()
                        if glob_match(test, pat)}
        if len(commands) == 1:
            test_commands[test] = next(iter(commands))
        elif commands:
            test_commands[test] = ""       # neither display nor run an arbitrary ambiguous command
            blocked.append(f"{test}: ambiguous test commands: {', '.join(sorted(commands))}")
        elif not test.endswith(".py"):
            blocked.append(f"{test}: no executable test command; declare test_commands or retire the test")
    return test_commands, blocked

def read_git_paths(root, *arguments):
    """Run Git against a disposable index: diff may refresh even with optional locks off."""
    import shutil
    where = subprocess.run(['git', '-C', str(root), 'rev-parse', '--git-path', 'index'],
                           capture_output=True, check=True)
    source = Path(os.fsdecode(where.stdout).strip())
    if not source.is_absolute():
        source = root / source
    with tempfile.TemporaryDirectory(prefix='flowguard-read-index-') as folder:
        index = Path(folder) / 'index'
        if source.exists():
            shutil.copy2(source, index)  # Preserve Git's racy-clean timestamp window.
        env = dict(os.environ, GIT_OPTIONAL_LOCKS='0', GIT_INDEX_FILE=str(index))
        result = subprocess.run(['git', '-C', str(root), *arguments], env=env,
                                capture_output=True, check=True)
        return [os.fsdecode(item) for item in result.stdout.split(b'\0') if item]


_read_git_paths = read_git_paths  # Compatibility for existing map-impact imports.

def _literal_impact(root, data, inv, tree, changed, base, *, function_origins=None, model_origins=None):
    """Fresh source roles add consumers to the same function/test selection, never cache sites."""
    import re
    import difflib
    from collections import Counter
    from .discover import literal_sites
    from .mapfile import owner_index

    owner, _ = owner_index(data, inv)
    model_paths = {node.path: mid for mid, node in tree.nodes.items()}
    model_source = [
        p.relative_to(root).as_posix()
        for p in (root / ".flowguard/models").glob("*.py")
        if not p.name.startswith("_")
    ]
    paths = sorted({path for path in inv.py if not inv.is_test(path)} | set(model_source))
    sites = {}
    sources = {}

    def get(path):
        if path not in sites:
            try:
                sources[path] = read_source(root / path)
                sites[path] = literal_sites(sources[path])
            except OSError:
                sources[path] = ""
                sites[path] = []
        return sites[path]

    def candidate(path, value):
        return path not in inv.py or value in inv.py[path].string_literals

    text_paths = None
    text_cache = {}

    def mentions(value):
        nonlocal text_paths
        if text_paths is None:
            try:
                text_paths = [
                    p
                    for p in _read_git_paths(root, "ls-files", "-z")
                    if Path(p).suffix.lower() in (".md", ".yaml", ".yml", ".json", ".toml")
                ]
            except (OSError, subprocess.CalledProcessError):
                text_paths = []
        pattern = re.compile(r"(?<![A-Za-z0-9_])" + re.escape(value) + r"(?![A-Za-z0-9_])")
        found = []
        for path in sorted(text_paths):
            if path not in text_cache:
                try:
                    text_cache[path] = read_source(root / path)
                except OSError:
                    text_cache[path] = ""
            if pattern.search(text_cache[path]):
                found.append(path)
        return found

    lines = []
    models = set()
    functions = set()
    tests = set()
    mention_lines = []
    typos = []
    role_group = {
        "key_write": "produces",
        "value": "produces",
        "key_read": "handles",
        "compare": "handles",
    }
    histories = {}
    before_counts = Counter()
    after_counts = Counter()
    for source in sorted(changed):
        if inv.is_test(source) or not source.endswith(".py"):
            continue
        blob = (
            subprocess.run(
                ["git", "-C", str(root), "show", f"{base}:{source}"], capture_output=True
            )
            if base
            else None
        )
        previous = (
            read_source(root / source, data=blob.stdout)
            if blob is not None and blob.returncode == 0
            else ""
        )
        before = literal_sites(previous)
        after = get(source)
        histories[source] = (previous, before, after)
        before_counts.update(
            (value, role_group[role]) for value, _, role in before if role in role_group
        )
        after_counts.update(
            (value, role_group[role]) for value, _, role in after if role in role_group
        )
    for source, (previous, before, after) in histories.items():
        cid = owner.get(source) or next(
            (node.home for node in tree.nodes.values() if node.path == source), "unmapped"
        )
        altered = set()
        for tag, i, j, start, end in difflib.SequenceMatcher(
            a=previous.splitlines(), b=sources[source].splitlines()
        ).get_opcodes():
            if tag != "equal":
                altered.update(range(start + 1, end + 1))
        for value, group in sorted(
            {(value, role_group[role]) for value, _, role in before if role in role_group}
        ):
            if before_counts[value, group] <= after_counts[value, group]:
                continue
            local_before = sum(
                v == value and role_group.get(role) == group for v, _, role in before
            )
            local_after = sum(v == value and role_group.get(role) == group for v, _, role in after)
            if local_before <= local_after:
                continue
            produced = group == "produces"
            roles = {"key_read", "compare"} if produced else {"key_write", "value"}
            label = "produces" if produced else "handles"
            action = "read" if produced else "produce"
            locations = []
            for path in paths:
                if not candidate(path, value):
                    continue
                matches = [
                    line
                    for v, line, role in get(path)
                    if v == value and role in roles and not (path == source and line in altered)
                ]
                if matches:
                    locations.append((path, matches))
            if len(locations) > 20:
                lines.append(
                    f"{cid} no longer {label} '{value}': {len(locations)} files {action} it (too common to list)"
                )
                continue

            def order(item):
                path = item[0]
                return (
                    (
                        3
                        if path.startswith(".flowguard/models/")
                        else 2 if path == source else 0 if owner.get(path) != cid else 1
                    ),
                    path,
                )

            locations.sort(key=order)
            for path, found in locations[:5]:
                where = (
                    "model " + model_paths[path]
                    if path in model_paths
                    else owner.get(path, "unmapped")
                )
                verb = "reads" if produced else "produces"
                lines.append(
                    f"{cid} no longer {label} '{value}' that {where} {verb} at {path}:{found[0]}"
                    + (f" (+{len(found)-1} in file)" if len(found) > 1 else "")
                )
            if len(locations) > 5:
                lines.append(f"(+{len(locations)-5} more files)")
            for path, found in locations if produced else ():
                if path in model_paths:
                    models.add(model_paths[path])
                    if model_origins is not None:
                        model_origins.setdefault(model_paths[path], set()).add(source)
                    continue
                try:
                    syntax = ast.parse(sources[path])
                except SyntaxError:
                    continue
                from .discover import function_spans

                spans = function_spans(syntax)
                for line in found:
                    enclosing = [span for span in spans if span[0] <= line <= span[1]]
                    if enclosing:
                        function = path + "#" + min(enclosing, key=lambda span: span[1] - span[0])[2]
                        functions.add(function)
                        if function_origins is not None:
                            function_origins.setdefault(function, set()).add(source)
            for path in inv.tests if produced else ():
                if candidate(path, value) and any(v == value for v, _, role in get(path)):
                    tests.add(path)
            files = mentions(value)
            if files:
                mention_lines.append(
                    f"mentions '{value}' in {len(files)} text files: "
                    + ", ".join(files[:2])
                    + (f", +{len(files)-2}" if len(files) > 2 else "")
                )
        old_consumers = Counter(
            value for value, _, role in before if role in ("key_read", "compare")
        )
        new_consumers = Counter(
            value for value, _, role in after if role in ("key_read", "compare")
        )
        for value, count in new_consumers.items():
            if count <= old_consumers[value]:
                continue
            if any(
                candidate(path, value)
                and any(
                    v == value and role in ("key_write", "value") for v, line, role in get(path)
                )
                for path in paths
            ):
                continue
            if mentions(value):
                continue
            line = next(
                line for v, line, role in after if v == value and role in ("key_read", "compare")
            )
            typos.append(
                f"nothing produces '{value}' (consumed at {source}:{line}); check the spelling"
            )
    return lines + mention_lines[:2] + typos[:1], models, functions, tests

def _git_promise_notes(root, data, changed, base):
    if base is None or not any(path.startswith('.flowguard/models/') and path.endswith('.py') for path in changed):
        return [],[]
    from .facets import promise_records, promise_changes
    from .mapfile import model_registry
    try:
        paths=_read_git_paths(root,'ls-tree','-r','--name-only','-z',base,'--','.flowguard/models')
    except (OSError,subprocess.CalledProcessError):return [],[]
    # Old helpers resolve only against this old namespace; never against today's source.
    with tempfile.TemporaryDirectory(prefix='flowguard-old-promises-') as directory:
        old_root=Path(directory)
        for path in paths:
            if Path(path).parent.as_posix()!='.flowguard/models' or not path.endswith('.py'):continue
            blob=subprocess.run(['git','-C',str(root),'show',f'{base}:{path}'],capture_output=True)
            if blob.returncode:continue
            destination=old_root/path;destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(blob.stdout)
        before=promise_records(old_root,{'components':[],'flows':[]})
        after=promise_records(root,data)
        ids={mid for mid,record in {**before,**after}.items() if record[5] in changed}
        ids.update(mid for mid in before.keys() & after.keys() if before[mid][:3]!=after[mid][:3] or before[mid][3]!=after[mid][3])
        return promise_changes(before,after,ids)
