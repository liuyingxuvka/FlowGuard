"""The map handle the intent core uses (C-1, C-5).

    from flowguard.structure import build
    m = build("/path/to/repo")                    # incremental; .flowguard/cache/map.sqlite
    m.node("makerspace.standing:refusal")         # None when the id is not on the map (never re-pointed)
    m.sites("makerspace.standing:refusal")        # folded decision sites with constant identities
    m.search_homes("makerspace.standing:refusal", words="3 grace days")  # static clues, never execution
    m.impact(["src/makerspace/standing.py"])      # dirty set: changed, callers, constant readers, removed names
    m.moved()                                     # "moved? old -> new (same body)" proposals
"""
from __future__ import annotations

import json
import posixpath
import sqlite3
from pathlib import Path

from flowguard.map.common import MapError, cache_dir, git_blob, git_common_directory, git_run
from . import homes, store
from .extract import extract
from .store import shape_list
from .query import Rows, tokens

NODE_COLS = ("id", "file", "module", "qual", "kind", "cls", "line", "end_line", "sig", "doc", "fp", "size", "effects", "build")
SIMILAR = 0.85


def build(root, store_path=None, *, roots=None, force=False, workers=None) -> "MapHandle":
    """Bring the map of `root` up to date and return a handle on it."""
    root = Path(root).resolve()
    path = Path(store_path) if store_path else cache_dir(root) / "map.sqlite"    # 1.x: writes its .gitignore
    if path.is_dir() or (store_path and not str(store_path).endswith(".sqlite")):
        path = path / "map.sqlite"
    options = dict(roots=roots, force=force, workers=workers)
    stats = store.build(root, path, **options)
    return MapHandle(root, path, stats, options)


class MapHandle:
    def __init__(self, root: Path, path: Path, stats: dict, options=None):
        self.root, self.path, self.stats = root, path, stats
        self.options = dict(options or {}, force=False)
        self.con = sqlite3.connect(path, timeout=30)
        self._syntax_cache = None
        self._file_cache = {}
        self._queried = set()

    def refresh(self) -> dict:
        self.con.close()
        self.stats = store.build(self.root, self.path, **self.options)
        self.con = sqlite3.connect(self.path, timeout=30)
        self._syntax_cache = None
        self._file_cache = {}
        self._queried = set()
        return self.stats

    def close(self) -> None:
        self.con.close()

    # ---- structure ----------------------------------------------------------------
    def roots(self) -> list[dict]:
        return [{"path": p, "how": h} for p, h in self.con.execute("SELECT path, how FROM root ORDER BY rank")]

    def capabilities(self):
        """Actual file coverage, parser status and the explicit native-execution boundary."""
        return self.stats.get('capabilities', {})

    def _mark_query(self, name, language=None, files=None):
        from .readers.registry import SUFFIXES
        if language is not None and language not in SUFFIXES.values():
            raise MapError('no source reader for language '+str(language))
        self._queried.add((name, language, tuple(files) if files is not None else None))

    def reset_query_coverage(self):
        """Start a separate predicate's coverage scope without rebuilding the map."""
        self._queried.clear()

    def _language_rows(self, rows, language):
        from .readers.registry import language_for
        # Synthetic missing-import nodes have no physical source language.
        # Keep them in unfiltered nodes/import links, rather than passing None
        # to the suffix reader during a query about actual source files.
        return Rows(row for row in rows if language is None or
                    row.get('file') is not None and language_for(row['file']) == language)

    def query_coverage(self):
        """Coverage of queries this handle actually served; no cache or new record store."""
        from .readers.registry import query_support
        grouped = {}
        rows = [(file, error, store.unpack(blob))
                for file,error,blob in self.con.execute('SELECT path,parse_error,data FROM file')]
        for query, language, files in self._queried:
            for file,error,facts in rows:
                actual = facts.get('language','python')
                if language is not None and actual != language or files is not None and file not in files:
                    continue
                reason = ('source parse failed: '+error) if error else ''
                bindings = facts.get('binding_unknowns', [])
                if not reason and bindings and query in {'nodes','calls','assignments','keys'}:
                    first = bindings[0]
                    reason = f'source declaration binding unknown: {first["name"]} at line {first["line"]} requires type/value context'
                if not reason and not query_support(actual).get(query,False):
                    reason = query+' coverage is not implemented for '+actual
                if reason:
                    grouped.setdefault((query,actual,reason),set()).add(file)
            if language is None:
                for file in self.capabilities().get('unsupported_files',[]):
                    if files is not None and file not in files:
                        continue
                    grouped.setdefault((query,'unsupported','no source reader for these files'),set()).add(file)
        issues = [dict(query=q,language=lang,reason=reason,files=sorted(files))
                  for (q,lang,reason),files in sorted(grouped.items())]
        return dict(queried=sorted({item[0] for item in self._queried}),complete=not issues,issues=issues)

    def _details(self, row):
        if row is None:
            return None
        if row['file'] not in self._file_cache:
            data = self.con.execute('SELECT data FROM file WHERE path=?',(row['file'],)).fetchone()
            self._file_cache[row['file']] = store.unpack(data[0]) if data else {}
        facts = self._file_cache[row['file']]
        return dict(row, language=facts.get('language','python'),
                    **facts.get('locations',{}).get(row['qual'],{}))

    def node(self, ident: str) -> dict | None:
        row = self.con.execute(f"SELECT {', '.join(NODE_COLS)} FROM node WHERE id = ?", (ident,)).fetchone()
        if row:
            self._mark_query('nodes', files=[row[1]])
        else:
            files = [item[0] for item in self.con.execute('SELECT path FROM file WHERE module=?',(ident.partition(':')[0],))]
            self._mark_query('nodes', files=files)
        return self._details(dict(zip(NODE_COLS, row))) if row else None

    def canonical(self, ident: str) -> str | None:
        """The map's id for `module:Qual.name` written with any importable name of its file (a rule's home
        may say `pkg.tools.calendar:isleap` where the map's primary name is `calendar`), or None."""
        if self.node(ident):
            return ident
        module, sep, qual = ident.partition(":")
        rel = module.replace(".", "/")
        for r in [x["path"] for x in self.roots()]:
            for cand in (posixpath.join(r, rel + ".py"), posixpath.join(r, rel, "__init__.py")):
                row = self.con.execute("SELECT module FROM file WHERE path = ?", (cand,)).fetchone()
                if row:
                    other = row[0] + sep + qual
                    return other if self.node(other) else None
        return None

    def nodes(self, kind: str | None = None, module: str | None = None, file: str | None = None, *, language=None) -> list[dict]:
        scoped = [file] if file else [row[0] for row in self.con.execute("SELECT path FROM file WHERE module=?",(module,))] if module else None
        self._mark_query("nodes",language,scoped)
        where, args = [], []
        for col, value in (("kind", kind), ("module", module), ("file", file)):
            if value is not None:
                where.append(f"{col} = ?")
                args.append(value)
        sql = f"SELECT {', '.join(NODE_COLS)} FROM node" + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY id"
        return self._language_rows([self._details(dict(zip(NODE_COLS, r))) for r in self.con.execute(sql, args)],language)

    def functions(self, *, language=None) -> dict[str, dict]:
        """Functions and methods by id (what fg2.mapiface.MapView.functions returns from fgmap)."""
        return {n["id"]: n for n in self.nodes(language=language) if n["kind"] in ("function", "method")}

    def _syntax(self, kind):
        if self._syntax_cache is None:
            self._syntax_cache = [store.unpack(data) for (data,) in self.con.execute("SELECT data FROM file ORDER BY path")]
        return [fact for data in self._syntax_cache for fact in data.get(kind, [])]

    def handlers(self, *, language=None):
        self._mark_query("handlers",language)
        return self._language_rows(self._syntax("handlers"),language)

    def literal_sets(self, *, numeric=False, min_size=0, shares_with=None, min_shared=3, language=None):
        """Literal tables; shared-value counts ignore ubiquitous 0 and ±1."""
        self._mark_query("literal_sets",language)
        rows = self._language_rows(self._syntax("literal_sets"),language)
        shared = set()
        if shares_with:
            module, _, name = shares_with.partition(':')
            node = self.node(shares_with)
            if node:
                shared = {value for row in rows if row['node'].partition(':')[0] == module
                          and node['line'] <= row['line'] <= (node['end_line'] or node['line'])
                          for value in row['numeric_values']}
        result = []
        for row in rows:
            values = row['numeric_values']
            size = len(values) if numeric else len(row['value']) if isinstance(row['value'], (list, dict)) else 0
            if size < min_size or numeric and not values:
                continue
            if shares_with and len((shared & set(values)) - {0,1,-1}) < min_shared:
                continue
            result.append(row)
        return Rows(result)

    def assignments(self, *, include_unknown=False, language=None):
        """Assignments to literal values; opt in to targets whose value is unknown."""
        self._mark_query('assignments',language)
        return self._language_rows([row for row in self._syntax('assignments')
                if include_unknown or row.get('literal',True)],language)

    def calls(self, *, include_reads=False, language=None):
        """Syntactic calls; optionally include symbol reads, never execution evidence."""
        self._mark_query('calls',language)
        rows = self._syntax('syntax_calls')
        if include_reads:
            self._mark_query('symbol_reads',language)
            rows += self._syntax('symbol_reads')
        return self._language_rows(rows,language)

    def imports(self, *, declarations=False, language=None):
        """Dependency links, or literal source declarations including external imports.

        A declaration proves syntax, not that the import ran. Aliases keep the
        imported module/name identity; TYPE_CHECKING declarations stay labelled.
        """
        self._mark_query('imports',language)
        if declarations:
            rows = []
            for file, module, blob in self.con.execute("SELECT path, module, data FROM file ORDER BY path"):
                data = store.unpack(blob)
                for declaration in data.get('dependencies', []):
                    rows.append(dict(declaration, src=module, dst=declaration.get('resolved') or declaration['module'],
                        node=module, file=file, prov='source', language=data.get('language')))
                for typing, group in ((False, data.get('lines_all', {})), (True, data.get('typing', {}))):
                    for identity, lines in group.items():
                        imported, _, name = identity.partition(':')
                        rows.extend(dict(src=module, dst=identity, node=module, file=file, line=line,
                                         kind='import-declaration', prov='source', module=imported,
                                         name=name, typing=typing) for line in lines)
            return self._language_rows(sorted(rows, key=lambda row: (row['file'], row['line'], row['dst'])),language)
        cols = ("src", "dst", "kind", "prov", "file", "line")
        return self._language_rows([dict(zip(cols,row),node=row[0]) for row in self.con.execute(
            "SELECT src, dst, kind, prov, file, line FROM edge WHERE kind LIKE 'imports%' ORDER BY file,line,dst")],language)

    def tests(self, *, language=None):
        self._mark_query("tests",language)
        return self.nodes(kind="test",language=language)

    def blocks(self) -> list[tuple[str, list[str]]]:
        """Default blocks: one per package (a top-level module is its own). Declared blocks are C-12's."""
        out: dict = {}
        for ident, n in self.functions().items():
            out.setdefault(n["module"].rpartition(".")[0] or n["module"], []).append(ident)
        return sorted(out.items())

    def sites(self, ident: str) -> list[dict]:
        cols = ("line", "field", "op", "const", "value", "vkind", "identity", "leads", "neg", "pred")
        return [dict(zip(cols, r)) for r in self.con.execute(
            f"SELECT {', '.join(cols)} FROM site WHERE node = ? ORDER BY line", (ident,))]

    def keys(self, ident: str | None = None, kind: str | None = None, value: str | None = None, *, language=None) -> list[dict]:
        files = [row[0] for row in self.con.execute("SELECT file FROM node WHERE id=?",(ident,))] if ident else None
        self._mark_query("keys",language,files)
        where, args = [], []
        for col, v in (("node", ident), ("kind", kind), ("value", value)):
            if v is not None:
                where.append(f"{col} = ?")
                args.append(v)
        sql = "SELECT node, kind, value, line, file FROM key" + (" WHERE " + " AND ".join(where) if where else "")
        return self._language_rows([dict(zip(("node","kind","value","line","file"),r)) for r in self.con.execute(sql,args)],language)

    def edges(self, ident: str, direction: str = "out", kind: str | None = None) -> list[dict]:
        me, other = ("src", "dst") if direction == "out" else ("dst", "src")
        sql = f"SELECT src, dst, kind, prov, file, line FROM edge WHERE {me} = ?" + (" AND kind = ?" if kind else "")
        rows = self.con.execute(sql, (ident, kind) if kind else (ident,)).fetchall()
        return [dict(zip(("src", "dst", "kind", "prov", "file", "line"), r)) for r in rows]

    def callers(self, ident: str, depth: int = 1, guessed: bool = False) -> list[str]:
        """Callers up to `depth` levels; guessed edges count only when an observed edge confirms them,
        unless guessed=True."""
        seen, frontier = set(), {ident}
        for _ in range(depth):
            nxt = set()
            for node in frontier:
                for src, prov in self.con.execute("SELECT src, prov FROM edge WHERE dst = ? AND kind = 'calls'", (node,)):
                    if prov == "guessed" and not guessed and not self._observed(src, node):
                        continue
                    if src not in seen and src != ident:
                        nxt.add(src)
            seen |= nxt
            frontier = nxt
        return sorted(seen)

    def _observed(self, src: str, dst: str) -> bool:
        return self.con.execute("SELECT 1 FROM edge WHERE src = ? AND dst = ? AND prov = 'observed'", (src, dst)).fetchone() is not None

    def add_observed(self, pairs) -> int:
        """Record caller -> callee pairs a tracer saw; they confirm guessed edges and survive relinks."""
        rows = [(s, d, "calls", "observed", "<observed>", 0) for s, d in sorted({(s,d) for s,d in pairs}) if not self._observed(s, d)]
        self.con.executemany("INSERT INTO edge VALUES(?,?,?,?,?,?)", rows)
        self.con.commit()
        return len(rows)

    # ---- other homes ---------------------------------------------------------------
    def other_homes(self, ident: str, k: int = 5, *, words: str = "", decides=None,
                    not_same=(), weak: bool = False, sites=None) -> list[dict]:
        """One static decision-site query. Words re-rank; candidates never execute.

        `sites` names the rule's realized sites as (node, line, text); without
        them the home's own sites are used. `search_homes` also returns whether
        readable sites were found, so an empty list is not proof of no copies.
        """
        return self.search_homes(ident, k=k, words=words, decides=decides,
                                 not_same=not_same, weak=weak, sites=sites)['candidates']

    def search_homes(self, ident, *, k=None, words='', decides=None,
                     not_same=(), weak=True, sites=None, since=None):
        """Static candidates and an explicit searched/not-searched fact, never a verdict."""
        requested = ident
        ident = self.canonical(ident) or ident
        node = self.node(ident)
        if node is None:
            return dict(candidates=[], total=0, searched=False, anchors=[], searched_anchors=[], historical_sites=0,
                        reason=f'anchor gone: {requested} -> restore the home or inspect a moved? proposal')
        not_same = [self.canonical(target) or target for target in not_same]
        if sites is not None:
            sites = [(self.canonical(target) or target, line, text) for target, line, text in sites]
        anchors = [ident] if node['kind'] != 'class' else [n['id'] for n in self.nodes(module=node['module'])
                   if n['cls'] == node['qual'] and n['kind'] in ('method','function')]
        anchors.sort(key=lambda target: (not target.endswith('.__init__'), target))
        excluded = set(not_same) | set(anchors) | {ident}
        found, searched, historical = {}, [], 0
        for target in anchors:
            groups, _ = homes.site_groups(self.con, target, sites)
            if groups:
                searched.append(target)
            for candidate in homes.other_homes(self.con, target, None, words, decides, excluded, weak, sites):
                candidate.setdefault('anchors', []).append(target)
                prior = found.get(candidate['id'])
                if prior:
                    prior['anchors'] = sorted(set(prior['anchors'] + candidate['anchors']))
                else:
                    found[candidate['id']] = candidate
            old = self._old_groups(target, groups) if sites != [] else []
            if not old and since and sites != []:
                old = self._groups_at(target,since)
            historical += len(old)
            for candidate in homes.site_homes(self.con, target, words=words, exclude=excluded, groups=old):
                if not weak and candidate['strength']=='weak':
                    continue
                row_sigs = [set(json.loads(raw)) for (raw,) in self.con.execute('SELECT sigs FROM site WHERE node=?',(candidate['id'],))]
                matched = [g for g in old if any({s for s in g['sigs'] if s.startswith(('sg:n:','sg:t:','sg:m:','sg:s:','sg:set:','sg:v:','sg:f:'))} & own for own in row_sigs)]
                if not matched:
                    continue
                prior = found.setdefault(candidate['id'],dict(candidate,anchors=[target]))
                prior['stale'] = True
                prior['old_values'] = sorted({g['value'] for g in matched})
                prior['identity_shared'] = any(g['identity'] and any('sg:id:'+g['identity'] in own for own in row_sigs) for g in matched)
                prior['reason'] = 'stale copy? still matches old '+', '.join(prior['old_values'])+' -> update, bind or distinct; '+candidate['reason']
        ranked = sorted(found.values(), key=lambda row: (row['strength'] != 'strong', -row['score'], row['id']))
        if k is not None:
            ranked = [row for strength in ('strong','weak') for row in [c for c in ranked if c['strength'] == strength][:k]]
        return dict(candidates=ranked, total=len(found), searched=bool(searched), anchors=anchors,
                    searched_anchors=searched, historical_sites=historical,
                    reason='' if searched else 'not searched: no readable decision sites -> bind the real decision function')

    def _old_groups(self, target, current):
        current_sets = {frozenset(group['sigs']) for group in current}
        current_fields = {group.get('field') for group in current}
        related = {sig for group in current for sig in group['sigs'] if sig.startswith(('sg:field:','sg:id:'))}
        found = {}
        for line,field,op,const,value,identity,raw in self.con.execute('SELECT line,field,op,const,value,identity,sigs FROM site_history WHERE node=? ORDER BY build DESC',(target,)):
            sigs = set(json.loads(raw))
            if frozenset(sigs) in current_sets or current and field not in current_fields and not sigs & related:
                continue
            found.setdefault(frozenset(sigs),dict(node=target,line=line,field=field,text=homes.site_text(field,op,const),sigs=sigs,value=value,identity=identity))
        return list(found.values())

    def _groups_at(self, target, revision):
        """Fresh clones read old source through the same extractor, never execute it."""
        from . import decide
        module, _, qual = target.partition(':')
        node = self.node(target)
        files = {name:path for path,name in self.con.execute('SELECT path,module FROM file')}
        data = git_blob(self.root,revision,node['file']) if node else None
        if data is None:
            return []
        facts = extract(self.root,node['file'],data,module,False)
        before = next((n for n in facts['nodes'] if n['qual']==qual),None)
        if not before:
            return []
        def own_of(name):
            path = files.get(name)
            raw = git_blob(self.root,revision,path) if path else None
            parsed = extract(self.root,path,raw,name,False) if raw is not None else {'nodes':[]}
            return decide.own_env([(n['qual'],n['sig']) for n in parsed['nodes'] if n['kind']=='const'])
        own = decide.own_env([(n['qual'],n['sig']) for n in facts['nodes'] if n['kind']=='const'])
        imports = facts.get('facts',{}).get('imports',{})
        env = decide.module_env(own,imports,own_of)
        env = decide.class_env(env,before.get('cls',''),[])
        raw = before.get('raw',{})
        result = []
        for site in raw.get('sites',[]):
            row = decide.fold_site(site,env,raw.get('lex',{}),module,before.get('cls',''),imports,set(own),lambda mod,name: mod+':'+name)
            sigs = set(decide.site_signatures(row,env,raw.get('lex',{})))
            if sigs:
                result.append(dict(node=target,line=row['line'],field=row['field'],text=homes.site_text(row['field'],row['op'],row['const']),sigs=sigs,value=row['value'],identity=row['identity']))
        return result

    def search(self, words):
        """Rank generated sites before bare name matches; intent ranking belongs to the caller."""
        wanted = tokens(words)
        sites = {}
        for ident, field, constant, identity in self.con.execute('SELECT node, field, const, identity FROM site'):
            sites.setdefault(ident, set()).update(tokens(' '.join(value or '' for value in (field,constant,identity))))
        aliases = {}
        for file, module, data in self.con.execute('SELECT path,module,data FROM file'):
            for name, target in store.unpack(data).get('facts', {}).get('imports', {}).items():
                if wanted & tokens(name):
                    canonical = self.canonical(target)
                    if canonical:
                        aliases.setdefault(canonical, []).append(f'{module}:{name} ({file})')
        result = []
        for node in self.nodes():
            hits = {'sites': sorted(wanted & sites.get(node['id'],set())),
                    'doc': sorted(wanted & tokens(node['doc'] or '')),
                    'name': sorted(wanted & tokens(node['id'])),
                    'aliases': sorted(aliases.get(node['id'], []))}
            if any(hits.values()):
                result.append(dict(node, matches=hits, score=3*len(hits['sites'])+2*len(hits['doc'])+len(hits['name'])+len(hits['aliases'])))
        return sorted(result, key=lambda row: (-row['score'], row['id']))



    # ---- identity --------------------------------------------------------------------
    def moved(self, ids=None, rev: str | None = None) -> list[dict]:
        """Proposals for ids that left the map: same fingerprint elsewhere (`same body`), else a shape at
        least 0.85 alike among nodes added since (`similar body`), else `gone`. Without `ids`, every id the
        store saw vanish. An id the store never saw takes its old fingerprint from git at `rev`."""
        gone = {r[0]: r for r in self.con.execute("SELECT id, fp, kind, shape, file, sig, build FROM gone ORDER BY build")}
        wanted = list(ids) if ids is not None else sorted(gone)
        out = []
        for old in wanted:
            if self.node(old):
                continue
            if old in gone:
                _, fp, kind, shape, _, _, since = gone[old]
            elif rev:
                try:
                    fp, kind, shape = self.fingerprint_at(rev, old)
                except MapError as e:
                    out.append({"old": old, "new": None, "how": str(e), "score": 0.0, "line": f"anchor gone ({e})"})
                    continue
                since = 0
            else:
                out.append({"old": old, "new": None, "how": "unknown", "score": 0.0,
                            "line": f"anchor gone: {old} (no fingerprint in the cache; pass rev=)"})
                continue
            out += self._proposals(old, fp, kind, shape_list(shape) if isinstance(shape, bytes) else shape, since)
        return out

    def _proposals(self, old, fp, kind, shape, since) -> list[dict]:
        kinds = ('function', 'method', 'test') if kind in ('function', 'method', 'test') else (kind,)
        marks = ','.join('?' for _ in kinds)
        same = self.con.execute(f"SELECT id, build FROM node WHERE fp = ? AND kind IN ({marks}) AND id != ? ORDER BY build DESC, id",
                                (fp, *kinds, old)).fetchall()
        same_name = [(ident, number) for ident, number in same if ident.partition(':')[2] == old.partition(':')[2]]
        if same_name:
            same = same_name
        if kind == "const":                               # a value like 3 is everywhere: same name or module only
            mod, _, name = old.partition(":")
            last = name.rpartition(".")[2]
            same = [(i, b) for i, b in same if i.partition(":")[2].rpartition(".")[2] == last or i.startswith(mod + ":")]
        if same:
            newer = [i for i, b in same if b >= since] or [i for i, _ in same]
            return [{"old": old, "new": new, "how": "same body", "score": 1.0,
                     "line": f"moved? {old} -> {new} (same body)"} for new in newer]
        best = []
        if shape:
            for new, blob in self.con.execute(f"SELECT id, shape FROM node WHERE kind IN ({marks}) AND build >= ?", (*kinds, since)):
                other = shape_list(blob)
                inter = len(set(shape) & set(other))
                score = inter / len(set(shape) | set(other)) if other else 0.0
                if score >= SIMILAR:
                    best.append((score, new))
        if best:
            best.sort(key=lambda x: (-x[0], x[1]))
            return [{"old": old, "new": new, "how": f"similar body {score:.2f}", "score": round(score, 2),
                     "line": f"moved? {old} -> {new} (similar body {score:.2f})"} for score, new in best]
        return [{"old": old, "new": None, "how": "gone", "score": 0.0, "line": f"anchor gone: {old}"}]

    def fingerprint_at(self, rev: str, ident: str) -> tuple[str, str, list]:
        """(fp, kind, shape) of `module:Qual.name` in the code at git revision `rev`."""
        if git_common_directory(self.root) is None:
            raise MapError("no git history here")
        if git_run(self.root, "rev-parse", "-q", "--verify", rev + "^{commit}", allowed=(0, 1)).returncode:
            shallow = git_run(self.root, "rev-parse", "--is-shallow-repository").stdout.strip() == b"true"
            raise MapError("no history: use fetch-depth 0" if shallow else f"revision {rev} not found")
        module, _, qual = ident.partition(":")
        from .readers.registry import language_for, module_name
        prefix, slash, foreign_file = module.partition('/')
        if slash and language_for(foreign_file) and module_name(foreign_file) == module:
            candidates = [foreign_file]
        else:
            rel = module.replace('.', '/')
            candidates = [candidate for r in [x['path'] for x in self.roots()]
                          for candidate in (posixpath.join(r, rel+'.py'),posixpath.join(r,rel,'__init__.py'))]
        for cand in candidates:
            data = git_blob(self.root, rev, cand)
            if data is None:
                continue
            for n in extract(self.root, cand, data, module, False)["nodes"]:
                if n["qual"] == qual:
                    return n["fp"], n["kind"], n["shape"]
        raise MapError(f"{ident} not in the code at {rev}")

    # ---- impact ----------------------------------------------------------------------
    def impact(self, changed_files=None, since: str | None = None) -> dict:
        """The dirty set of a change. Without `since`: what the last build that touched each file changed.
        With `since=REV`: the working tree against git REV (changed files from git when not given)."""
        con = self.con
        if since is None:
            files = list(changed_files) if changed_files is not None else [
                f for (f,) in con.execute("SELECT DISTINCT file FROM delta WHERE build = (SELECT MAX(build) FROM delta)")]
            delta = []
            for f in files:
                delta += con.execute("SELECT id, change, old_fp, new_fp, old_sig, new_sig FROM delta WHERE file = ? AND "
                                     "build = (SELECT MAX(build) FROM delta WHERE file = ?)", (f, f)).fetchall()
        else:
            files = list(changed_files) if changed_files is not None else self._git_changed(since)
            delta = self._delta_against(since, files)
        changed = sorted({i for i, c, *_ in delta if c == "changed"})
        added = sorted({i for i, c, *_ in delta if c == "added"})
        removed = sorted({i for i, c, *_ in delta if c == "removed"})
        kinds = {i: (self.node(i) or {}).get("kind") for i in changed}
        constants = [{"id": i, "old": o, "new": n} for i, c, _, _, o, n in delta
                     if c == "changed" and kinds.get(i) == "const"]
        readers = {}
        for c in constants:
            found = {s for (s,) in con.execute("SELECT src FROM edge WHERE dst = ? AND kind = 'reads'", (c["id"],))}
            found |= {s for (s,) in con.execute("SELECT node FROM site WHERE identity = ? OR identity LIKE ?",
                                                (c["id"], c["id"] + "[%"))}
            readers[c["id"]] = sorted(found)
        removed_readers = {i: self._removed_readers(i) for i in removed}
        dirty = set(changed) | set(added) | set(removed) | {r for v in readers.values() for r in v} \
            | {r for v in removed_readers.values() for r in v}
        level1, level2, guessed = set(), set(), set()
        for d in dirty:
            for src, prov in con.execute("SELECT src, prov FROM edge WHERE dst = ? AND kind = 'calls'", (d,)):
                (guessed if prov == "guessed" and not self._observed(src, d) else level1).add(src)
        for d in level1:
            level2 |= set(self.callers(d))
        level1 -= dirty
        level2 -= dirty | level1
        data_files, unknown = {}, []
        for f in files:
            if f.endswith(".py"):
                continue
            base = posixpath.basename(f)
            hit = sorted({n for (n,) in con.execute("SELECT node FROM key WHERE kind = 'file' AND (value = ? OR value = ? "
                                                    "OR ? LIKE '%' || value)", (f, base, f))})
            (data_files.__setitem__(f, hit) if hit else unknown.append(f))
        dirty |= {n for v in data_files.values() for n in v}
        return {"files": sorted(files), "changed": changed, "added": added, "removed": removed,
                "constants": constants, "constant_readers": readers, "removed_readers": removed_readers,
                "callers": sorted(level1), "callers2": sorted(level2), "guessed_callers": sorted(guessed - level1),
                "data_files": data_files, "unknown": unknown, "dirty": sorted(dirty),
                "tests": self._tests_for(files, dirty)}

    def _removed_readers(self, ident: str) -> list[str]:
        con = self.con
        module, _, name = ident.partition(":")
        out = {s for (s,) in con.execute("SELECT src FROM edge WHERE dst = ?", (ident,))}
        row = con.execute("SELECT readers FROM gone WHERE id = ? ORDER BY build DESC", (ident,)).fetchone()
        if row and row[0]:
            out |= set(json.loads(row[0]))
        for miss in (f"missing:{module}:{name}", f"missing:{module}.{name}", f"missing:{module}"):
            out |= {s for (s,) in con.execute("SELECT src FROM edge WHERE dst = ?", (miss,))}
        return sorted(out - {ident})

    def _tests_for(self, files: list[str], dirty: set) -> list[str]:
        """Test files whose static import closure reaches a changed file or a dirty node's module."""
        con = self.con
        modules = {m for (m,) in con.execute(f"SELECT id FROM node WHERE kind IN ('module','alias') AND file IN "
                                             f"({','.join('?' * len(files))})", files)} if files else set()
        modules |= {d.partition(":")[0] for d in dirty}
        seen, frontier = set(modules), set(modules)
        while frontier:
            nxt = set()
            for m in frontier:
                for (src,) in con.execute("SELECT src FROM edge WHERE dst = ? AND kind LIKE 'imports%'", (m,)):
                    if src not in seen:
                        seen.add(src)
                        nxt.add(src)
                for (src,) in con.execute("SELECT src FROM edge WHERE dst = ? AND kind = 'alias'", (m,)):
                    if src not in seen:
                        seen.add(src)
                        nxt.add(src)
            frontier = nxt
        tests = set()
        for m in seen:
            row = con.execute("SELECT f.path FROM node n JOIN file f ON f.path = n.file WHERE n.id = ? AND f.is_test = 1",
                              (m,)).fetchone()
            if row:
                tests.add(row[0])
        tests |= {f for f in files if con.execute("SELECT 1 FROM file WHERE path = ? AND is_test = 1", (f,)).fetchone()}
        return sorted(tests)

    def _git_changed(self, since: str) -> list[str]:
        out = git_run(self.root, "diff", "--name-only", "--relative", since, "--").stdout.decode().split("\n")
        out += git_run(self.root, "ls-files", "--others", "--exclude-standard").stdout.decode().split("\n")
        return sorted({f for f in out if f})

    def _delta_against(self, since: str, files: list[str]) -> list[tuple]:
        rows = []
        names = {f: m for f, m in self.con.execute("SELECT path, module FROM file")}
        from .readers.registry import language_for, module_name
        for f in files:
            if not language_for(f):
                continue
            data = git_blob(self.root, since, f)
            module = names.get(f) or (f[:-3].replace("/", ".") if language_for(f) == "python" else module_name(f))
            old = {f"{module}:{n['qual']}": (n["fp"], n["sig"]) for n in
                   (extract(self.root, f, data, module, False)["nodes"] if data is not None else [])}
            new = {i: (fp, sig) for i, fp, sig in self.con.execute("SELECT id, fp, sig FROM node WHERE file = ? AND "
                                                                    "kind NOT IN ('module','alias','missing')", (f,))}
            for i in sorted(set(old) | set(new)):
                if i not in new:
                    rows.append((i, "removed", old[i][0], None, old[i][1], None))
                elif i not in old:
                    rows.append((i, "added", None, new[i][0], None, new[i][1]))
                elif old[i][0] != new[i][0]:
                    rows.append((i, "changed", old[i][0], new[i][0], old[i][1], new[i][1]))
        return rows
