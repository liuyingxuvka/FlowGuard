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

import ast
import json
import os
import posixpath
import re
import sqlite3
from pathlib import Path

from flowguard.map.common import MapError, cache_dir, git_blob, git_common_directory, git_path_object, git_run, glob_match, is_test_file, sha256_bytes
from . import homes, store
from .extract import extract
from .store import shape_list
from .query import Rows, may_share, tokens

NODE_COLS = ("id", "file", "module", "qual", "kind", "cls", "line", "end_line", "sig", "doc", "fp", "size", "effects", "build")
SIMILAR = 0.85
PRISMA_CLIENT = re.compile(r'(^|/)(@prisma/client|\.prisma/client|generated/prisma)(/|$)')
ARCHIVES = ('**/docs/**',)        # files no code runs against: database histories, release snapshots


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
        self._derived = {}
        self._queried = set()

    def refresh(self) -> dict:
        self.con.close()
        self.stats = store.build(self.root, self.path, **self.options)
        self.con = sqlite3.connect(self.path, timeout=30)
        self._syntax_cache = None
        self._file_cache = {}
        self._derived = {}
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
        rows = self._kinds('language', 'binding_unknowns')
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
            self._file_cache[row['file']] = {kind: store.unpack(blob) for kind, blob in self.con.execute(
                "SELECT kind, data FROM part WHERE path=? AND kind IN ('language', 'locations')", (row['file'],))}
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
        if file is None and module is None and 'details' not in self._derived:
            # Every file's language and locations in one read, not one read per file.
            for path, _, facts in self._kinds('language', 'locations'):
                self._file_cache.setdefault(path, facts)
            self._derived['details'] = True
        return self._language_rows([self._details(dict(zip(NODE_COLS, r))) for r in self.con.execute(sql, args)],language)

    def outline(self, kinds=('function', 'method', 'class')) -> dict[str, dict]:
        """{id: {id, qual, doc, file, line, kind}} of the nodes of these kinds: the columns a search ranks
        on, without the per-file details that nodes() adds to every row."""
        self._mark_query('nodes')
        names = ('id', 'qual', 'doc', 'file', 'line', 'kind')
        return {row[0]: dict(zip(names, row)) for row in self.con.execute(
            f"SELECT {', '.join(names)} FROM node WHERE kind IN ({','.join('?' * len(kinds))}) ORDER BY id", list(kinds))}

    def functions(self, *, language=None) -> dict[str, dict]:
        """Functions and methods by id (what fg2.mapiface.MapView.functions returns from fgmap)."""
        return {n["id"]: n for n in self.nodes(language=language) if n["kind"] in ("function", "method")}

    def _files(self):
        """(path, parse error, facts) of every mapped file, unpacked once per handle and build."""
        if self._syntax_cache is None:
            self._syntax_cache = [(path, error, store.unpack(data)) for path, error, data in
                                  self.con.execute("SELECT path, parse_error, data FROM file ORDER BY path")]
        return self._syntax_cache

    def _kinds(self, *kinds):
        """(path, parse error, facts) of every mapped file in path order, like `_files()`, with only these
        kinds of facts: each kind's parts are read and unpacked once per handle and build."""
        held = self._derived.setdefault('parts', {})
        held.update(store.parts(self.con, [kind for kind in dict.fromkeys(kinds) if kind not in held]))
        if 'paths' not in self._derived:
            self._derived['paths'] = self.con.execute('SELECT path, parse_error FROM file ORDER BY path').fetchall()
        return [(path, error, {kind: held[kind][path] for kind in kinds if path in held[kind]})
                for path, error in self._derived['paths']]

    def assignments_to(self, fields):
        """The assignment facts of the files that assign one of `fields` (or a row without a field), in
        path order: the `assignments.fields` index part decides which files are unpacked."""
        fields = set(fields)
        wanted = [path for path, _, data in self._kinds('assignments.fields')
                  if fields.intersection(data.get('assignments.fields', ())) or None in data.get('assignments.fields', ())]
        rows = []
        for start in range(0, len(wanted), 500):
            chunk = wanted[start:start + 500]
            found = dict(self.con.execute(f"SELECT path, data FROM part WHERE kind='assignments' AND path IN "
                                          f"({','.join('?' * len(chunk))})", chunk))
            rows.extend(row for path in chunk for row in store.unpack(found.get(path)) or ())
        return rows

    def _syntax(self, kind):
        return [fact for _, _, data in self._kinds(kind) for fact in data.get(kind, [])]

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
        """Assignments to literal values; opt in to targets whose value is unknown. A Python right side
        that names an enum member or a module constant (also through `a if c else b`) is folded as the
        decision sites fold it, into `values` (and `value` when there is one)."""
        self._mark_query('assignments',language)
        return self._language_rows([self._folded(row) for row in self._syntax('assignments')
                if include_unknown or row.get('literal',True)],language)

    def _value_env(self, module):
        """The module's folded constants for its own code: own constants and imported ones."""
        from . import decide
        envs = self.__dict__.setdefault('_value_envs', {})
        if module not in envs:
            envs[module] = {}
            envs[module] = decide.module_env(decide.own_env(self._const_rows(module)), self._module_imports(module),
                                             lambda name: decide.own_env(self._const_rows(name)))
        return envs[module]

    def _const_rows(self, module):
        """(qual, sig) of the module's constants in line order, as `decide.own_env` folds them."""
        return self.con.execute("SELECT qual, sig FROM node WHERE module=? AND kind='const' ORDER BY line", (module,)).fetchall()

    def _module_imports(self, module):
        """The `imports` of the module's Python facts ({} without them)."""
        stored = self.con.execute('SELECT path FROM file WHERE module=? LIMIT 1', (module,)).fetchone()
        stored = stored and self.con.execute("SELECT data FROM part WHERE kind='facts.imports' AND path=?", stored).fetchone()
        return store.unpack(stored[0]) if stored else {}

    def _folded(self, row, env_of=None):
        """The row with the constant values its right side folds to; `env_of(module)` stands for `_value_env`."""
        if not row.get('expr') or row.get('literal') or '(' in row['expr'] and ' if ' not in row['expr']:
            return row                    # a call's result is not a constant this map can fold
        values = _fold_values(row['expr'], (env_of or self._value_env)(row['node'].partition(':')[0]))
        if values is None:
            return row
        return dict(row, values=values, **({'value': values[0]} if len(values) == 1 else {}))

    # ---- writes, string literals and schema descriptions ---------------------------------------
    def _schema_rows(self):
        """(path, schema facts) of every Prisma/SQL file, read once per handle and build."""
        if 'schema_rows' not in self._derived:
            self._derived['schema_rows'] = self._read_schema_rows()
        return self._derived['schema_rows']

    def _read_schema_rows(self):
        return _schema_rows_of((path, facts) for path, _, facts in self._kinds('language', 'schema'))

    def schemas(self):
        """What every mapped Prisma schema (models, fields, @map, @@map, @relation) and SQL file
        (CREATE TABLE, ALTER TABLE ADD/DROP COLUMN, DROP TABLE) declares, by file."""
        rows = self._schema_rows()
        self._mark_query('schema', files=[path for path, _ in rows])
        return [dict(schema, file=path) for path, schema in rows]

    def _models(self):
        if 'models' not in self._derived:
            self._derived['models'] = _models_of(self._schema_rows())
        return self._derived['models']

    def definitions(self, replaced):
        """The definitions values and models are read from (`writes(definitions=)`) when the files of `replaced`,
        [(path, module, facts)], hold those facts instead of the map's ({} for a file absent there), such as their
        facts at a baseline commit: every other file keeps the map's. Built as the map builds its own."""
        return Definitions(self, replaced)

    def writes(self, target=None, *, language=None, by_name=False, facts=None, fold=True, definitions=None):
        """Who writes what, statically: Prisma client writes bound to schema models (connect and nested
        writes follow @relation), SQL write statements (TS/JS raw SQL, .sql files and Python string literals,
        recorded for the function holding them), and Python attribute assignments bound to a class. A Python
        row carries `value` when the assignment or statement spells the written literal. `by_name=True` adds property assignments `obj.f = ...`
        that only a field name ties to a target (how='name'). `target` is `Model.field`, `table.column`,
        a model or table, or a bare field/column name; rows whose fields are not visible (spread,
        non-literal data) are kept for their model with `unclear=True`. `facts` reads these file facts
        (for example one file's facts at a baseline commit) instead of the map's; `fold=False` skips folding Python
        right sides into `values` (who writes, not what). `definitions` (`definitions()`) binds models, resolves JS/TS
        set names and folds Python constants with other definitions than the map's, such as the baseline's.
        Never execution evidence."""
        from .readers.prisma import bind, bind_sql
        from .readers.registry import ECMA, language_for
        self._mark_query('writes', language)
        models = self._models() if definitions is None else definitions.models
        sets = None if definitions is None else definitions.sets
        env_of = None if definitions is None else definitions.env
        rows = []
        if facts is None:
            listed = self._kinds('language', 'writes')
            if by_name or any(data.get('language', 'python') == 'python' for _, _, data in listed):
                listed = self.write_records()      # only these rows read assignments
            facts = [data for _, _, data in listed]
        for facts in list(facts):
            kind = facts.get('language', 'python')
            if language is not None and kind != language:
                continue
            writes = facts.get('writes', [])
            rows += [self._resolved(dict(row, language=kind), sets) for row in bind([w for w in writes if w.get('via') == 'prisma'], models)]
            rows += [dict(row, language=kind) for row in bind_sql([w for w in writes if w.get('via') == 'sql'], models)]
            for row in facts.get('assignments', []):
                row = self._folded(row, env_of) if kind == 'python' and fold else row
                if kind in ECMA and row.get('form') == 'member' and by_name and row.get('field'):
                    rows.append(dict(node=row['node'], function=row['node'].partition(':')[2] or '<module>', file=row['file'],
                                     line=row['line'], column=row.get('column'), call_line=row['line'], how='name',
                                     method='assign', kind='assign', model=None, field=row['field'], table=None, db_column=None,
                                     nested=False, unclear=False, schema=None, receiver=row['target'].rpartition('.')[0],
                                     reason='property assignment matched by field name only', language=kind))
                elif kind == 'python':
                    owner, _, written = row['field'].partition(':')
                    cls, dot, attr = written.rpartition('.')
                    if not dot or '[' in written or (row.get('unresolved') and not by_name):
                        continue
                    rows.append(dict(node=row['node'], function=row['node'].partition(':')[2] or '<module>', file=row['file'],
                                     line=row['line'], column=None, call_line=row['line'],
                                     how='name' if row.get('unresolved') else 'attribute', method='assign', kind='assign',
                                     model=None if row.get('unresolved') else cls, field=attr, table=None, db_column=None,
                                     nested=False, unclear=False, schema=None, receiver=cls,
                                     reason='attribute assignment matched by field name only' if row.get('unresolved') else '',
                                     language=kind, **({'value': row['value']} if row.get('literal') else {}),
                                     **({key: row[key] for key in ('value', 'values') if key in row} if row.get('values') else {})))
        if target is not None:
            rows = [row for row in rows if _writes_target(row, target, models)]
        return Rows(sorted(rows, key=lambda row: (row['file'], row['line'], row.get('column') or 0, str(row['field']))))

    def write_records(self):
        """(path, parse error, record) of every mapped file in path order, its record as `writes(facts=)` reads it: its
        `language`, its `writes` and, as `assignments`, the assignment rows `writes` reads (the `assignments.writes`
        part: none of a JS/TS file but its member assignments with a field)."""
        return [(path, error, {('assignments' if kind == 'assignments.writes' else kind): value for kind, value in data.items()})
                for path, error, data in self._kinds('language', 'writes', 'assignments.writes')]

    def writes_to(self, rows, target):
        """The rows of `writes()` that write `target`, in their order: what `writes(target)` gives when `rows` is
        `writes()` with the same options, without reading every write again for each target."""
        models = self._models()
        return Rows(row for row in rows if _writes_target(row, target, models))

    def file_facts(self, path):
        """The whole stored fact record of one mapped file, or None when the file is not on the map."""
        row = self.con.execute('SELECT data FROM file WHERE path=?', (path,)).fetchone()
        return store.unpack(row[0]) if row else None

    def _baseline_revision(self, revision):
        """Pin a mutable Git name, while an already immutable commit is verified once."""
        if revision == ':':
            return revision
        held = self._derived.setdefault('baseline_revisions', {})
        if re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', revision) and revision in held:
            return held[revision]
        commit = git_run(self.root, 'rev-parse', '--verify', revision + '^{commit}').stdout.decode().strip()
        held[commit] = commit
        return commit

    def _baseline_object(self, revision, path):
        revision = self._baseline_revision(revision)
        if revision == ':':
            return git_path_object(self.root, revision, path)
        trees = self._derived.setdefault('baseline_objects', {})
        if revision not in trees:
            listing = git_run(self.root, 'ls-tree', '-r', '-t', '-z', revision).stdout
            objects = {}
            for row in listing.split(b'\0'):
                if row:
                    description, _, name = row.partition(b'\t')
                    objects[os.fsdecode(name)] = description.split()[2].decode()
            trees[revision] = objects
        return trees[revision].get(Path(path).as_posix())

    def _baseline_bytes(self, revision, path):
        blob = self._baseline_object(revision, path)
        if blob is None:
            return None
        held = self._derived.setdefault('baseline_bytes', {})
        if blob not in held:
            held[blob] = git_run(self.root, 'cat-file', 'blob', blob).stdout
        return held[blob]

    def _baseline_facts(self, revision, path, module, is_test=False):
        """Rebuildable source facts, shared by every baseline query of this map.

        Git's immutable blob and the map reader/context signature own the key;
        no comparison or verification result is stored. Existing transactions
        keep ownership of their commit, including these disposable facts.
        """
        blob = self._baseline_object(revision, path)
        if blob is None:
            return {}
        key = self._baseline_key(blob, path, module, is_test)
        facts = self._derived.setdefault('baseline_facts', {})
        if key not in facts:
            row = self.con.execute('SELECT v FROM meta WHERE k=?', (key,)).fetchone()
            if row is None:
                data = self._baseline_bytes(revision, path)
                packed = store.pack(extract(self.root, path, data, module, is_test))
                active = self.con.in_transaction
                from flowguard.intent.cache import put_meta
                put_meta(self.con, key, packed)
                decoded = store.unpack(packed)
                self._put_parts(key, decoded)          # in the same commit
                if not active:
                    self.con.commit()
            else:
                decoded = store.unpack(row[0])
            decoded['nodes']  # Required fact record; a broken cache is not an absent source file.
            facts[key] = decoded
        return facts[key]

    def _put_parts(self, key, facts):
        """Each kind of one baseline record under `KEY:KIND`, and the list of its kinds under `KEY:`."""
        from flowguard.intent.cache import put_meta
        for kind, value in facts.items():
            put_meta(self.con, key + ':' + kind, store.pack([value]))
        put_meta(self.con, key + ':', store.pack(sorted(facts)))

    def _baseline_key(self, blob, path, module, is_test):
        reader = self.con.execute("SELECT v FROM meta WHERE k='reader_digest'").fetchone()[0]
        identity = json.dumps([blob, reader, path, module, bool(is_test)], separators=(',', ':'))
        return 'baseline_facts:' + sha256_bytes(identity.encode())

    def _baseline_part(self, revision, path, module, kind, is_test=False):
        """One kind of `_baseline_facts` (None when the record has none, or when the file was absent), kept
        apart under the record's key once it was read: a query that needs only a file's nodes or literals does
        not decode its whole record again (most of a record is the symbol reads and syntax calls)."""
        blob = self._baseline_object(revision, path)
        if blob is None:
            return None
        key = self._baseline_key(blob, path, module, is_test)
        parts = self._derived.setdefault('baseline_parts', {})
        whole = self._derived.get('baseline_facts', {})
        if (key, kind) not in parts and key in whole:
            parts[(key, kind)] = whole[key].get(kind)  # the record this handle already decoded holds it
        if (key, kind) not in parts:
            row = self.con.execute('SELECT v FROM meta WHERE k=?', (key + ':' + kind,)).fetchone()
            kinds = None if row is not None else self.con.execute('SELECT v FROM meta WHERE k=?', (key + ':',)).fetchone()
            if row is not None:
                value = store.unpack(row[0])[0]
            elif kinds is not None and kind not in store.unpack(kinds[0]):
                value = None                           # the record has no such kind
            else:
                # A record kept before its parts were: they are written once, in one commit.
                facts = self._baseline_facts(revision, path, module, is_test)
                active = self.con.in_transaction
                self._put_parts(key, facts)
                if not active:
                    self.con.commit()
                value = facts.get(kind)
            parts[(key, kind)] = value
        return parts[(key, kind)]

    # ---- declared value sets, typed values, Prisma reads, relations and calls by name ----------
    def _ts_sets(self):
        """{name: [row]} of the JS/TS value sets (`as const` arrays and objects, `new Set([...])`, closed
        string unions and aliases of them), read once per handle."""
        if 'ts_sets' not in self._derived:
            self._derived['ts_sets'] = _sets_of(facts for _, _, facts in self._kinds('value_sets'))
        return self._derived['ts_sets']

    def _ts_values(self, name, file=None, seen=frozenset()):
        """(values, row) a JS/TS set name stands for, following aliases (`(typeof X)[number]`); a name
        defined more than once with different values resolves only in the file that defines it, or through the
        file's own import of it (`import type { Granularity } from './types'`); otherwise test files' definitions
        do not stand in the way of the production ones."""
        rows = self._ts_sets().get(name, [])
        local = [row for row in rows if row['file'] == file]
        if not local and file is not None and len(rows) > 1 and len(seen) < 4:
            imported = self._ts_import(file, name)
            if imported is not None and imported[0] != file:
                values, origin = self._ts_values(imported[1], imported[0], seen | {name})
                if values is not None:
                    return values, origin
            production = [row for row in rows if not is_test_file(row['file'])]
            rows = production or rows
        rows = local or rows
        resolved = []
        for row in rows:
            if row['kind'] == 'alias':
                if row['of'] in seen | {name}:
                    continue
                values, origin = self._ts_values(row['of'], row['file'], seen | {name})
                if values is not None:
                    resolved.append((tuple(values), dict(origin, line=row['line'], file=row['file'], name=name)))
            else:
                resolved.append((tuple(row['values']), row))
        if len({values for values, _ in resolved}) != 1:
            return None, None
        return list(resolved[0][0]), resolved[0][1]

    def _ts_import(self, file, name):
        """(file, imported name) that `file` imports `name` from, when it imports it from a mapped file."""
        imports = self._derived.setdefault('ts_imports', {})
        if file not in imports:
            facts = {kind: store.unpack(blob) for kind, blob in self.con.execute(
                "SELECT kind, data FROM part WHERE path=? AND kind = 'dependencies'", (file,))}
            imports[file] = {row['alias']: (row['resolved'], row['name']) for row in facts.get('dependencies', ())
                             if row.get('kind') == 'import' and row.get('alias') and row.get('resolved')}
        found = imports[file].get(name)
        if found is None or found[1] in ('default', '*'):
            return None
        target = self.con.execute('SELECT path FROM file WHERE module=?', (found[0],)).fetchone()
        return (target[0], found[1]) if target else None

    def _resolved(self, row, sets=None):
        """A write's `values` with its `Name.KEY` spellings read from `{KEY: 'v'} as const` objects (of `sets`,
        `_ts_sets` by default); a row with a spelling no object resolves keeps no values (the value is not visible)."""
        refs = row.pop('refs', None)
        if not refs:
            return row if row.get('values') else {key: value for key, value in row.items() if key != 'values'}
        values = list(row.get('values') or ())
        sets = self._ts_sets() if sets is None else sets
        for ref in refs:
            name, _, key = ref.partition('.')
            members = [found for found in sets.get(name, []) if found['kind'] == 'const-object' and key in found['members']]
            if len({found['members'][key] for found in members}) != 1:
                return {key: value for key, value in row.items() if key != 'values'}
            values.append(members[0]['members'][key])
        return dict(row, values=values)

    def declarations(self, *, exported=True):
        """Named JS/TS value sets with their resolved values: [{name, file, line, values, kind}] (an alias
        appears with the values of the set it names). Only exported declarations by default: a module's
        own local type of one name is not a second declaration of another module's. A `{K: 'v'} as const`
        object counts only when its values are codes (no white space), not texts or class lists."""
        out = []
        for name, rows in sorted(self._ts_sets().items()):
            for row in rows:
                if exported and not row.get('exported'):
                    continue
                values, origin = self._ts_values(name, row['file']) if row['kind'] == 'alias' else (row['values'], row)
                if values and (origin or row)['kind'] == 'const-object' and any(len(value.split()) != 1 for value in values):
                    continue
                if values:
                    out.append(dict(name=name, file=row['file'], line=row['line'], values=tuple(values), kind=row['kind']))
        return out

    def prisma_schemas_in_use(self):
        """The Prisma schema files the client generator reads: each file named `schema.prisma` (Prisma's
        default name, the place a project's sync script copies a provider template onto), each file or
        folder a package.json names in `"prisma": {"schema": ...}` or a script's `--schema` (each package.json
        from a Prisma file's nearest package up to the repository root: a workspace root names a member's
        schema), and the `schema:` of a `prisma.config.ts` (`.mts`, `.js`, `.mjs`, `.cjs`) beside one of them
        (`_config_schemas`). Other `.prisma` files (`schema.sqlite.prisma` templates, fragments) only
        describe. A package whose Prisma files name none of these (the generated `schema.prisma` git-ignored,
        a schema set up in CI) uses them all: `prisma_schemas_guessed` lists those files, and the value gate
        says so. `archived` files (a release snapshot under `docs/`) are neither in use nor guessed. A schema
        folder (`readers.prisma.schema_folders`) is one schema: all its files are in use when one is."""
        if 'schemas_in_use' in self._derived:
            return self._derived['schemas_in_use']
        from .readers.prisma import schema_folders
        files = [path for path, schema in self._schema_rows() if schema.get('kind') == 'prisma' and not self.archived(path)]
        named = set()
        for package in sorted({folder for path in files for folder in self._packages_up(path)}):
            named |= self._prisma_named(package)

        def in_use(path):
            return posixpath.basename(path) == 'schema.prisma' or path in named or any(path.startswith(folder + '/') for folder in named)

        used = {path for path in files if in_use(path)}
        for schema in schema_folders(self._live_prisma()):
            if used & set(schema['files']):
                used |= set(schema['files'])
        guessed = set()
        for package in sorted({self.package(path) for path in files}):
            own = [path for path in files if self.package(path) == package]
            if not used & set(own):
                guessed.update(own)
        used |= guessed
        self._derived['schemas_in_use'] = used
        self._derived['schemas_guessed'] = frozenset(guessed)
        return used

    def _live_prisma(self):
        """The Prisma schema facts of every mapped `.prisma` file that is not `archived`, with its `file`."""
        return [schema for schema in self.schemas() if schema.get('kind') == 'prisma' and not self.archived(schema['file'])]

    def _packages_up(self, file):
        """The folder of every package.json from a file's nearest package (`package`) up to the root ('')."""
        folders = [self.package(file)]
        while folders[-1]:
            folders.append(self.package(folders[-1]))
        return folders

    def _prisma_named(self, package):
        """The repository paths one package folder names as Prisma schemas: its package.json's
        `"prisma": {"schema": ...}` and scripts' `--schema`, and its prisma.config.* `schema:`."""
        listed = []
        manifest = self.root / package / 'package.json'
        if manifest.is_file():
            try:
                data = json.loads(manifest.read_text(encoding='utf-8-sig'))
            except json.JSONDecodeError as error:
                raise MapError(f'{posixpath.join(package, "package.json")} is not valid JSON: {error}') from error
            settings = data.get('prisma') if isinstance(data, dict) else None
            listed += [settings['schema']] if isinstance(settings, dict) and isinstance(settings.get('schema'), str) else []
            scripts = data.get('scripts') if isinstance(data, dict) else None
            for script in (scripts or {}).values() if isinstance(scripts, dict) else ():
                if isinstance(script, str):
                    listed += [found[1] for found in re.finditer(r'--schema(?:=|\s+)["\']?([^\s"\'&|;]+)', script)]
        for suffix in ('ts', 'mts', 'js', 'mjs', 'cjs'):
            config = self.root / package / f'prisma.config.{suffix}'
            if config.is_file():
                listed += _config_schemas(config.read_text(encoding='utf-8-sig'))
        return {posixpath.normpath(posixpath.join(package, re.sub(r"\\+", "/", item))) for item in listed if item.strip()}

    def _config_url(self, path):
        """The datasource url (`env:NAME` or the literal) a `prisma.config.*` gives a Prisma schema file: the
        `datasource: { url: ... }` of the config of a package folder from the file's nearest package up to the
        root that names the file or its folder (`_prisma_named`: its package.json and its config), or, with a
        config that names no schema, holds it at Prisma's default place (`prisma/schema.prisma`,
        `schema.prisma`); '' when none does. Prisma 7 takes the url from there, not from the schema."""
        for package in self._packages_up(path):
            for suffix in ('ts', 'mts', 'js', 'mjs', 'cjs'):
                config = self.root / package / f'prisma.config.{suffix}'
                if not config.is_file():
                    continue
                text = config.read_text(encoding='utf-8-sig')
                url, named = _config_url(text), self._prisma_named(package)
                defaults = set() if _config_schemas(text) else \
                    {posixpath.normpath(posixpath.join(package, item)) for item in ('prisma/schema.prisma', 'schema.prisma')}
                if url and (path in named | defaults or any(path.startswith(folder + '/') for folder in named)):
                    return url
        return ''

    def prisma_schemas_guessed(self):
        """The Prisma files `prisma_schemas_in_use` takes because their package names no schema in use."""
        self.prisma_schemas_in_use()
        return self._derived['schemas_guessed']

    def value_sets(self):
        """The declared value sets of fields that code outside Python declares: a field of a Prisma schema in
        use (`prisma_schemas_in_use`; a schema folder is one schema, `readers.prisma.schema_folders`) typed with
        a Prisma enum and a SQL `CHECK (column IN ('a', ...))` on a model's table (the latest one in a
        migrations folder; several descriptions add up), keyed and gated `Model.field`, both kept when a field
        has both; and a JS/TS interface, class or object type member annotated with a closed string union or an
        alias of `as const`/`new Set` values, keyed `Type.field` and gated `ts:Type.field` (a TS type is not the
        Prisma model of the same name). The enum of a schema in use judges only the writes `scope` gives that
        schema (`scope`: the schemas in use that declare that set, `packages` their packages; the gate gives a
        write the schema of its client or of its package, `health._foreign_writes`). A TS set judges only the
        typed objects the gate gives one of the files declaring the member with it (`scope`; a file declaring the
        type's name types its own objects, `ts_type_files`). A
        guessed schema (`prisma_schemas_guessed`) gates only the models no schema in use defines and only the
        writes of its own package and of packages without a Prisma file defining that model
        (`excluded_packages`); each guessed enum of a field is its own set (a value must be in each, as beside
        a CHECK), shared by the package's files that spell the same enum alike (`files`). Each row: key, name,
        field (the gate's key), values, where (file:line), kind, guessed, file (the first of `files`), files (the
        files that declare it), place (where the set is declared: the schema, the CHECK's description, the first TS
        file declaring the member with it, the first guessed file), scope, packages, excluded_packages, fold (the
        database compares text without case: SQL Server and MySQL default collations)."""
        if 'value_sets' in self._derived:
            return self._derived['value_sets']
        from .readers.prisma import schema_folders
        in_use, guessed = self.prisma_schemas_in_use(), self.prisma_schemas_guessed()
        live = self._live_prisma()
        # The schemas in use first: a guessed file only fills the models none of them defines.
        schemas = sorted((schema for schema in schema_folders(live) if schema['files'][0] in in_use),
                         key=lambda schema: (schema['files'][0] in guessed, schema['file']))
        defined = {model['name'] for schema in schemas if schema['files'][0] not in guessed for model in schema['models']}
        model_packages = {}
        for schema in live:
            for model in schema['models']:
                model_packages.setdefault(model['name'], set()).add(self.package(schema['file']))
        enums_out, guesses, providers = {}, {}, {}
        for schema in schemas:
            guess, package = schema['files'][0] in guessed, self.package(schema['files'][0])
            enums = {enum['name']: enum for enum in schema['enums']}
            for model in schema['models']:
                if guess and model['name'] in defined:
                    continue
                providers.setdefault(model['name'], schema['provider'])
                for field in model['fields']:
                    enum = enums.get(field['type'])
                    if not enum or not enum['fields']:
                        continue
                    key, values = f"{model['name']}.{field['name']}", tuple(member['name'] for member in enum['fields'])
                    if guess:
                        guesses.setdefault((key, package, enum['name'], values), []).append((enum['file'], enum['line']))
                        continue
                    row = enums_out.get((key, values))
                    if row is None:
                        enums_out[key, values] = dict(
                            key=key, name=key, field=key, values=values, where=f"enum {enum['name']} ({enum['file']}:{enum['line']})",
                            kind='prisma-enum', guessed=False, fold=False, file=enum['file'], files=(enum['file'],),
                            place=schema['file'], scope=(schema['file'],), packages=(package,), excluded_packages=frozenset())
                    else:                   # another schema in use with the same set: one set, judging both
                        enums_out[key, values] = dict(row, files=tuple(dict.fromkeys((*row['files'], enum['file']))),
                                                      scope=(*row['scope'], schema['file']), packages=(*row['packages'], package))
        rows = list(enums_out.values())
        for (key, package, enum, values), places in guesses.items():
            files = tuple(file for file, _ in places)
            rows.append(dict(
                key=key, name=key, field=key, values=values,
                where=f"enum {enum} ({', '.join(f'{file}:{line}' for file, line in places)}"
                      ", generator schema not found; checked against all schemas in this package)",
                kind='prisma-enum', guessed=True, fold=False, file=files[0], files=files, place=files[0], scope=(), packages=(),
                excluded_packages=frozenset(model_packages.get(key.partition('.')[0], set()) - {package})))
        for key, (_, check) in self._check_sets().items():
            model = key.partition('.')[0]
            rows.append(dict(key=key, name=key, field=key, values=check['values'], where=check['where'],
                             kind='sql-check', guessed=False, fold=providers.get(model, '') in ('sqlserver', 'mysql'),
                             file=check['file'], files=(check['file'],), place=check['description'], scope=(), packages=(),
                             excluded_packages=frozenset()))
        types = {}
        for _, _, facts in self._kinds('typed_fields'):
            for row in facts.get('typed_fields', ()):
                key = f"{row['container']}.{row['field']}"
                if row['kind'] == 'union':
                    values, where, file = row['values'], f"{row['file']}:{row['line']}", row['file']
                else:
                    values, origin = self._ts_values(row['of'], row['file'])
                    if not values:
                        continue
                    where, file = f"{row['of']} ({origin['file']}:{origin['line']})", origin['file']
                types.setdefault(key, {}).setdefault(tuple(values), []).append((row['file'], where, file))
        for key, sets in types.items():
            for values, places in sets.items():
                files = tuple(dict.fromkeys(file for _, _, file in places))
                declaring = tuple(dict.fromkeys(place for place, _, _ in places))
                # each set judges the typed objects the gate gives one of the files declaring it
                rows.append(dict(key=key, name=key, field='ts:' + key, values=values, where=places[0][1], kind='ts-type',
                                 guessed=False, fold=False, file=files[0], files=files, place=declaring[0], packages=(),
                                 scope=declaring, excluded_packages=frozenset()))
        self._derived['value_sets'] = sorted(rows, key=lambda row: (row['key'], row['field'], row['place']))
        return self._derived['value_sets']

    def prisma_fields_in_use(self):
        """{model name: [(schema, package, {field: enum values or None}, own client)]}: each schema in use that
        defines the model (a schema folder is one schema; guessed schemas left out), in path order, with its
        package, each scalar field it declares (the values of an enum that has members, None for any other type)
        and whether it writes a client of its own (a generator `output`). The value gate gives a Prisma write the
        schema of its client or of its own package from these (`health._foreign_writes`)."""
        if 'fields_in_use' not in self._derived:
            from .readers.prisma import schema_folders
            in_use, guessed, out = self.prisma_schemas_in_use(), self.prisma_schemas_guessed(), {}
            for schema in sorted(schema_folders(self._live_prisma()), key=lambda schema: schema['file']):
                if schema['files'][0] not in in_use or schema['files'][0] in guessed:
                    continue
                enums = {enum['name']: tuple(member['name'] for member in enum['fields']) for enum in schema['enums'] if enum['fields']}
                names = {model['name'] for model in schema['models']}
                for model in schema['models']:
                    out.setdefault(model['name'], []).append((schema['file'], self.package(schema['files'][0]), {
                        field['name']: enums.get(field['type']) for field in model['fields']
                        if field['type'] not in names and not field.get('relation') and not field['list']},
                        bool(schema.get('outputs'))))
            self._derived['fields_in_use'] = out
        return self._derived['fields_in_use']

    def ts_type_files(self):
        """{type name: the files declaring it}: each top-level JS/TS interface, class and type alias. A typed object
        in one of these files is of that file's own type (`health._foreign_writes`)."""
        if 'ts_type_files' not in self._derived:
            out = {}
            for _, _, facts in self._kinds('type_names'):
                for row in facts.get('type_names', ()):
                    out.setdefault(row['name'], set()).add(row['file'])
            self._derived['ts_type_files'] = {name: frozenset(files) for name, files in out.items()}
        return self._derived['ts_type_files']

    def archived(self, path):
        """Is this file an archive (a database history or release snapshot kept under a `docs` folder), a
        description no code runs against? `[tool.flowguard] archives`, a list of path patterns (`**` crosses
        folders, a folder covers what is in it), replaces the default `ARCHIVES`; `archives = []` makes every
        file live."""
        if 'archives' not in self._derived:
            patterns = store.project_config(self.root).get('archives', list(ARCHIVES))
            if not isinstance(patterns, list) or not all(isinstance(item, str) and item.strip('/') for item in patterns):
                raise ValueError('[tool.flowguard] archives must be a list of path patterns')
            self._derived['archives'] = tuple(item.strip('/') for item in patterns)
        return any(glob_match(path, pattern) or glob_match(path, pattern + '/**') for pattern in self._derived['archives'])

    def _check_sets(self):
        """{Model.field: (per description {description: (values, file, line)}, the gate's set)} of SQL
        `CHECK (column IN (...))` on mapped tables outside `archived` files: a migrations folder's latest CHECK
        of a column, or one file's; the gate's set adds the descriptions up and is cited from a migrations
        folder when one has it (its `description`: the folder, `prisma/migrations/`, or the .sql file)."""
        if 'check_sets' in self._derived:
            return self._derived['check_sets']
        from .readers.sql import MIGRATION
        models, groups = self._models(), {}
        for schema in sorted((item for item in self.schemas() if item.get('kind') == 'sql' and not self.archived(item['file'])),
                             key=lambda item: item['file']):
            found = MIGRATION.match(schema['file'])
            group = groups.setdefault(found.group('folder') + '/' if found else schema['file'], {})
            for item in [*schema.get('tables', ()), *schema.get('changes', ())]:
                for check in item.get('checks', ()):
                    group[(item.get('name') or item['table']).casefold(), check['column'].casefold()] = \
                        (item.get('name') or item['table'], dict(check, file=schema['file']))
        out = {}
        # A migrations folder (applied in order) is the description a CHECK is cited from when it has one.
        for description, group in sorted(groups.items(), key=lambda item: (not item[0].endswith('/'), item[0])):
            for (table, column), (spelled, check) in group.items():
                model = models.table_model(spelled)
                field = models.column_field(model, check['column']) if model else None
                if field is None:
                    continue
                key = f"{model}.{field['name']}"
                each, gate = out.setdefault(key, ({}, None))
                each[description] = (tuple(check['values']), check['file'], check['line'])
                if gate is None:
                    gate = dict(values=tuple(check['values']), where=f"CHECK {check['file']}:{check['line']}", file=check['file'],
                                description=description)
                else:
                    gate = dict(gate, values=tuple(dict.fromkeys([*gate['values'], *check['values']])))
                out[key] = (each, gate)
        self._derived['check_sets'] = out
        return out

    def field_declarations(self):
        """{Model.field: [(file, line, values)]}: every declaration of one database field's values, also those
        of schemas not in use: each Prisma schema's enum typing it (a schema folder is one schema, its enums
        cited from their own files; `archived` files left out), each SQL description's CHECK on its column
        and each exported JS/TS declaration (outside tests) named like one of those enums."""
        from .readers.prisma import schema_folders
        enum_names, found = {}, {}
        for schema in schema_folders(self._live_prisma()):
            enums = {enum['name']: enum for enum in schema['enums']}
            for model in schema['models']:
                for field in model['fields']:
                    enum = enums.get(field['type'])
                    if enum and enum['fields']:
                        key = f"{model['name']}.{field['name']}"
                        found.setdefault(key, []).append((enum['file'], enum['line'],
                                                          frozenset(member['name'] for member in enum['fields'])))
                        enum_names.setdefault(key, set()).add(field['type'])
        for key, (each, _) in self._check_sets().items():
            found.setdefault(key, []).extend((file, line, frozenset(values)) for values, file, line in each.values())
        from flowguard.map.common import is_test_file
        by_name = {}
        for row in self.declarations():
            if not is_test_file(row['file']):
                by_name.setdefault(row['name'], []).append((row['file'], row['line'], frozenset(row['values'])))
        for key, names in enum_names.items():
            found[key].extend(item for name in sorted(names) for item in by_name.get(name, ()))
        return found

    def typed_writes(self, facts=None, *, definitions=None):
        """Values JS/TS code gives a typed member: a class field initializer, `this.f = 'v'` in a class, and
        the literal fields of an object written as `const x: T = {...}`, `{...} satisfies T` or `{...} as T`.
        Not database writes: they feed the value gate only; `prisma` marks a `T` the file imports from the
        Prisma client (`_prisma_client`), also under another local name (`{ Item as Row }`), and an `NS.T`
        whose `NS` is a namespace or named import of the client and `T` a mapped model: a model's type,
        gated by `model`, the imported model's name; `schema` is the schema whose client output the import
        names ('' for `@prisma/client`). A module that re-exports the client's types is not followed.
        `type_from` is the module a `T` of the file's own project is imported from by a relative path, as a
        path without its extension ('' otherwise). `facts` reads these file facts instead; `definitions`
        (`definitions()`) resolves `Name.KEY` spellings and binds models with other definitions than the map's, such
        as the baseline's (as `writes(definitions=)`)."""
        rows, seen = [], set()
        models = (self._models() if definitions is None else definitions.models).by_name
        sets = None if definitions is None else definitions.sets
        for facts in [data for _, _, data in self._kinds('language', 'typed_writes', 'dependencies')] if facts is None else facts:
            written = facts.get('typed_writes', ())
            if not written:
                continue
            client, origin, imported = {}, {}, {}
            for row in facts.get('dependencies', ()):
                if row.get('kind') == 'import' and row.get('alias'):
                    module = row.get('module') or ''
                    schema = self._client_schema(written[0]['file'], module)
                    if schema is not None:
                        client[row['alias']], origin[row['alias']] = row['name'], schema
                    elif module in ('.', '..') or module.startswith(('./', '../')):
                        imported[row['alias']] = _module_stem(posixpath.normpath(
                            posixpath.join(posixpath.dirname(written[0]['file']), module)))
            for row in written:
                key = (row['file'], row['line'], row['column'], row['container'], row['field'])
                if key in seen:
                    continue
                seen.add(key)
                space, dot, name = row['container'].partition('.')
                if dot:
                    model = name if space in client and client[space] != 'default' and name in models else None
                else:
                    model = client[space] if client.get(space) not in (None, '*', 'default') else None
                rows.append(self._resolved(dict(row, model=model or row['container'], language=facts.get('language'),
                                                prisma=model is not None, schema=origin.get(space, '') if model else '',
                                                type_from='' if dot or model else imported.get(space, '')), sets))
        return Rows(rows)

    def _prisma_client(self, file, module):
        """Does `file` import the Prisma client by this spelling: `@prisma/client`, `.prisma/client`, a
        `generated/prisma` folder, or the `output` folder of a mapped schema's generator (`generator client
        { output = "../generated/db" }`, resolved from the schema's folder): by a relative path into it, or,
        for a folder inside `node_modules` (`../node_modules/@prisma-db-1/client`), by the package name after
        it from a file under the folder that holds that `node_modules`, as Node resolves a bare import."""
        return self._client_schema(file, module) is not None

    def _client_schema(self, file, module):
        """The schema whose client `file` imports by this spelling (`_prisma_client`): the schema (a file, or a
        schema folder's name, `readers.prisma.schema_folders`) whose generator `output` the import names, also
        one under `generated/prisma`; '' for a client spelling that names no schema (`@prisma/client`,
        `.prisma/client`, another `generated/prisma` folder) and for an output folder several schemas in use
        write to; None when it is no Prisma client. A schema in use owns its output folder: a provider template
        with the same generator block does not take it."""
        if 'prisma_outputs' not in self._derived:
            from .readers.prisma import schema_folders
            in_use, writers = self.prisma_schemas_in_use(), {}
            for schema in schema_folders(self._live_prisma()):
                for output in schema['outputs']:
                    if output.strip():
                        folder = posixpath.normpath(posixpath.join(posixpath.dirname(schema['file']), re.sub(r'\\+', '/', output)))
                        writers.setdefault(folder, []).append(schema)
            outputs = {}
            for folder, schemas in sorted(writers.items(), key=lambda item: -len(item[0])):    # the deepest folder first
                used = [schema['file'] for schema in schemas if schema['files'][0] in in_use] or [schema['file'] for schema in schemas]
                outputs[folder] = used[0] if len(used) == 1 else ''
            self._derived['prisma_outputs'] = outputs
        outputs = self._derived['prisma_outputs']
        if module in ('.', '..') or module.startswith(('./', '../')):
            target = posixpath.normpath(posixpath.join(posixpath.dirname(file), module))
            found = next((schema for folder, schema in outputs.items() if target == folder or target.startswith(folder + '/')), None)
            if found is not None:
                return found
        else:
            for folder, schema in outputs.items():
                parts = folder.split('/')
                at = max((index for index, part in enumerate(parts[:-1]) if part == 'node_modules'), default=None)
                if at is None:
                    continue
                holder, name = '/'.join(parts[:at]), '/'.join(parts[at + 1:])
                if (module == name or module.startswith(name + '/')) and (not holder or file.startswith(holder + '/')):
                    return schema
        return '' if PRISMA_CLIENT.search(module) else None

    def queries(self, model=None):
        """Prisma reads (`count`, `findMany`, `findFirst`, `aggregate`, ...), bound to their model by
        accessor: `keys` the fields its `where` filters on (through AND/OR/NOT), `loads` the relations its
        `include`/`select` load, `counts` the relations its `_count` counts ('*' for all)."""
        models = self._models()
        rows = []
        for _, _, facts in self._kinds('language', 'queries'):
            for row in facts.get('queries', ()):
                bound = models.by_accessor.get(row['accessor'])
                if model is None or bound == model:
                    rows.append(dict(row, model=bound, language=facts.get('language')))
        return Rows(rows)

    def sql_reads(self, table=None):
        """The tables each function reads in the SQL of its string literals (a FROM or a JOIN), as rows {node, file,
        line, function, method, table}, the table in lower case as the SQL reader keeps it (`analysis.sql_names`);
        `table` keeps the reads of one table, its case aside. A write's own statement (UPDATE, INSERT, DELETE) reads
        no table here."""
        self._mark_query('sql_reads')
        rows = []
        wanted = None if table is None else 'sql:' + str(table).lower()
        found = self.con.execute("SELECT DISTINCT k.node FROM key k WHERE k.kind = 'sql'" + (' AND k.value = ?' if table else ''),
                                 (str(table).lower(),) if table else ()).fetchall()
        for (ident,) in found:
            item = self.con.execute('SELECT file, qual, line, raw FROM node WHERE id = ?', (ident,)).fetchone()
            if item is None:
                continue
            file, qual, line, raw = item
            for name in sorted((store.unpack(raw) if raw else {}).get('sr', ())):
                if name.startswith('sql:') and (wanted is None or name == wanted):
                    rows.append(dict(node=ident, file=file, line=line, function=qual, method='select', table=name[4:]))
        return Rows(rows)

    def children(self, model):
        """Relations whose foreign key references `model`: [{child, relation, keys, on_delete, required,
        file, line, nullable}] from the mapped Prisma schemas (`readers.prisma.Models.children`)."""
        names = ('child', 'relation', 'keys', 'on_delete', 'required', 'file', 'line', 'nullable')
        return [dict(zip(names, row)) for row in self._models().children(model)]

    def package(self, file):
        """The folder of the nearest package.json above a file ('' when none or at the root): one JS/TS
        package (backend, frontend) of a repository that holds several."""
        packages = self._derived.setdefault('packages', {})
        folder, trail = posixpath.dirname(file), []
        while folder not in packages:
            trail.append(folder)
            if not folder or folder == posixpath.dirname(folder) or (self.root / folder / 'package.json').is_file():
                packages[folder] = folder
                break
            folder = posixpath.dirname(folder)
        for item in trail:
            packages[item] = packages[folder]
        return packages[folder]

    def call_index(self):
        """({caller: {callee: how}}, {callee: {caller: how}}): the map's resolved call edges ('edge'), and JS/TS
        member calls resolved by name ('name'), only to functions of the caller's own package (`package`):
        `this.m()` to the method of the same class or object literal, `holder.m()` to the method of the class
        or `const holder = {...}` named so, and a callee name only one function of the package has. Prisma
        client calls (`x.model.update(...)`) are never resolved by name."""
        if 'calls' in self._derived:
            return self._derived['calls']
        from .readers.ecma import PRISMA_READS, PRISMA_WRITES
        from .readers.registry import ECMA
        prisma = PRISMA_WRITES | PRISMA_READS
        down = {}
        for src, dst in self.con.execute("SELECT src, dst FROM edge WHERE kind = 'calls' AND dst NOT LIKE 'unknown-%'"):
            down.setdefault(src, {})[dst] = 'edge'
        foreign = {}                        # file: is it JS/TS (read once per file)
        def ecma(file):
            if file not in foreign:
                foreign[file] = language_of(file) in ECMA
            return foreign[file]
        by_name, by_holder, owners = {}, {}, {}
        for ident, file, qual, raw in self.con.execute(
                "SELECT n.id, n.file, n.qual, n.raw FROM node n WHERE n.kind IN ('function', 'method')"):
            if not file or not ecma(file) or '<anonymous' in qual:
                continue
            data = store.unpack(raw) if raw else {}
            name = data.get('name') or qual.rpartition('.')[2]
            by_name.setdefault(name, []).append((ident, file))
            holder = data.get('holder') or (qual.rpartition('.')[0] if '.' in qual else '')
            if holder:
                by_holder.setdefault((holder, name), []).append((ident, file))
                owners[ident] = holder
        # Each list of candidates (named by `key`) grouped by package once, and each answer kept for its file: the
        # calls of one file name the same functions again and again.
        packages, grouped, chosen = {}, {}, {}
        def package(file):
            if file not in packages:
                packages[file] = self.package(file)
            return packages[file]
        def one(key, candidates, file):
            if (key, file) not in chosen:
                if key not in grouped:
                    grouped[key] = {}
                    for ident, where in candidates:
                        grouped[key].setdefault(package(where), []).append((ident, where))
                candidates = grouped[key].get(package(file), [])
                local = [ident for ident, where in candidates if where == file]
                picked = local if len(local) == 1 else [ident for ident, _ in candidates]
                chosen[(key, file)] = picked[0] if len(picked) == 1 else None
            return chosen[(key, file)]
        holders = {}                        # caller: the holder `this` names in it
        def holder_of(caller):
            if caller not in holders:
                named = caller.partition(':')[0] + ':' + '.'.join(part for part in caller.partition(':')[2].split('.')
                                                                  if not part.startswith('<anonymous'))
                holders[caller] = owners.get(named) or next((owners[ident] for ident in owners if named.startswith(ident + '.')), '')
            return holders[caller]
        # The JS/TS syntax calls the linker left unresolved, JSX elements aside (`store.save_facts`).
        for _, _, facts in self._kinds('syntax_calls.unresolved'):
            for caller, file, text in facts.get('syntax_calls.unresolved', ()):
                parts = text.split('.')
                name = parts[-1]
                if not name.isidentifier() or len(parts) >= 3 and name in prisma:
                    continue
                receiver = parts[-2] if len(parts) >= 2 else ''
                if receiver == 'this':
                    holder = holder_of(caller)
                    target = one(('holder', holder, name), by_holder.get((holder, name), []), file) if holder else None
                elif receiver:
                    target = one(('receiver', receiver, name), by_holder.get((receiver, name), []) or by_name.get(name, []), file)
                else:
                    target = one(('name', name), by_name.get(name, []), file)
                if target and target != caller:
                    down.setdefault(caller, {}).setdefault(target, 'name')
        up = {}
        for src, targets in down.items():
            for dst, how in targets.items():
                up.setdefault(dst, {})[src] = how
        self._derived['calls'] = down, up
        return down, up

    def call_tree(self, node, depth=3, *, up=0):
        """{function: how} of `node` (with the functions nested in it) and what they call, `depth` levels down;
        with `up`, first the callers `up` levels up, each with what it calls; from production code the way up
        does not enter test files (a test that calls a function is not part of its operation). how is 'edge',
        'name' (some JS/TS call on the way was resolved by name) or 'self'."""
        import bisect
        down, upward = self.call_index()
        if 'callers' not in self._derived:
            self._derived['callers'] = sorted(down)
        callers = self._derived['callers']
        if 'test_modules' not in self._derived:
            self._derived['test_modules'] = {module for (module,) in self.con.execute('SELECT module FROM file WHERE is_test = 1')}
        tests = self._derived['test_modules']
        climb_tests = node.partition(':')[0] in tests
        def body(ident):
            found = [ident]
            index = bisect.bisect_left(callers, ident + '.')
            while index < len(callers) and callers[index].startswith(ident + '.'):
                found.append(callers[index])
                index += 1
            return found
        roots = {node: 'self'}
        frontier = {node: 'self'}
        for _ in range(up):
            nxt = {}
            for ident, how in frontier.items():
                for item in body(ident):
                    for caller, edge in upward.get(item, {}).items():
                        if not climb_tests and caller.partition(':')[0] in tests:
                            continue
                        named = caller.partition(':')[0] + ':' + '.'.join(part for part in caller.partition(':')[2].split('.')
                                                                          if not part.startswith('<anonymous'))
                        if named not in roots:
                            nxt[named] = 'name' if 'name' in (how, edge) else 'edge'
            roots.update(nxt)
            frontier = nxt
        seen = dict(roots)
        frontier = dict(roots)
        for _ in range(depth):
            nxt = {}
            for ident, how in frontier.items():
                for item in body(ident):
                    seen.setdefault(item, how)
                    for callee, edge in down.get(item, {}).items():
                        if callee not in seen:
                            nxt[callee] = 'name' if 'name' in (how, edge) else 'edge'
            seen.update(nxt)
            frontier = nxt
        for ident, how in list(frontier.items()):
            for item in body(ident):
                seen.setdefault(item, how)
        return seen

    def literals(self, *, language=None, contexts=None):
        """String literals used to decide or name a value: comparisons (compare), switch cases (case),
        returned values (return), union type members (union), `new Set([...])` (set), array elements
        (array) and `.includes()/.has()` arguments (member). Object keys, logging calls and error
        messages are left out. A JS/TS comparison with a constant's name (`status === ACTIVE`,
        `kind === Kind.A`) is a compare row with the folded value and `name` (see `_compared_values`)."""
        self._mark_query('literals', language)
        folded = [row for row in self._compared_values() if isinstance(row['value'], str)]
        rows = self._language_rows(self._syntax('literals') + folded, language)
        return Rows(row for row in rows if contexts is None or row['context'] in contexts)

    def numbers(self):
        """JS/TS number literals in comparisons (`===`, `<`, `>=`, ...) and `case` labels, in the literal
        row shape: what an old-value lead looks for after a numeric constant changes. A comparison with
        a constant's name (`rounded > LIMIT`, also imported) is a row with the folded value and `name`."""
        folded = [row for row in self._compared_values()
                  if isinstance(row['value'], (int, float)) and not isinstance(row['value'], bool)]
        return Rows(self._syntax('numbers') + folded)

    def label_tables(self, tables=None):
        """Label tables that disagree: module-level JS/TS tables of production code (`const_tables` and
        `option_lists`, outside tests and `archived` files) with at least 3 keys and only non-empty string
        values, an enum object (every value its key) aside. A label table shows text: at least half of its
        values start with a capital and have a lower-case letter (a CSS class list, a variant name or a code is
        no label). Two label tables are copies when they share at least 3 keys, at least half of the smaller
        one's, and one of those keys has the same label in both; copies form a family. Each family row lists
        its `tables` (name, file, line, values), `differ` ({key: {label: [table index]}} for keys with several
        labels) and `lacking` ({table index: keys}): a table whose keys are all a family table's but for at
        most a third of them, also a table that maps the keys to codes (`ORG_TYPE_TO_ROLE` without ENTITY).
        `tables` replaces the map's rows (for example a baseline's)."""
        import itertools
        if tables is None:
            tests = {path for (path,) in self.con.execute('SELECT path FROM file WHERE is_test = 1')}
            tables = [dict(row, kind=kind) for _, _, facts in self._kinds('const_tables', 'option_lists')
                      for kind in ('const_tables', 'option_lists') for row in facts.get(kind, ())
                      if row['file'] not in tests and not self.archived(row['file'])]
        # An option without a key ({ value: '', label: 'All' }) is a filter's "no choice", not a key.
        tables = [dict(row, values={key: value for key, value in row['values'].items() if key}) for row in tables]
        tables = [row for row in tables if len(row['values']) >= 3
                  and all(isinstance(value, str) and value for value in row['values'].values())
                  and any(key != value for key, value in row['values'].items())]
        def shown(text):
            return text[:1].isupper() and any(ch.islower() for ch in text)
        labels = [i for i, row in enumerate(tables) if 2 * sum(map(shown, row['values'].values())) >= len(row['values'])]
        def shares(a, b):
            common = a.keys() & b.keys()
            return len(common) >= 3 and 2 * len(common) >= min(len(a), len(b))
        peers = {i: set() for i in labels}
        for i, j in itertools.combinations(labels, 2):
            a, b = tables[i]['values'], tables[j]['values']
            if shares(a, b) and any(a[key] == b[key] for key in a.keys() & b.keys()):
                peers[i].add(j)
                peers[j].add(i)
        out, seen = [], set()
        for start in labels:
            if start in seen or not peers[start]:
                continue
            family, todo = [], [start]
            while todo:
                item = todo.pop()
                if item not in family:
                    family.append(item)
                    todo.extend(peers[item])
            seen.update(family)
            members = sorted(family, key=lambda i: (-len(tables[i]['values']), tables[i]['kind'] != 'const_tables',
                                                    tables[i]['file'], tables[i]['line']))
            keys = sorted({key for i in members for key in tables[i]['values']})
            differ = {}
            for key in keys:
                spelled = {}
                for position, i in enumerate(members):
                    if key in tables[i]['values']:
                        spelled.setdefault(tables[i]['values'][key], []).append(position)
                # 'Code (required)' or 'Area / Expert group' is the label 'Code' or 'Area' with an addition.
                plain = {label for label in spelled if not any(label != other and label.startswith(other)
                                                                and not label[len(other):].strip()[:1].isalnum()
                                                                for other in spelled)}
                if len(plain) > 1:
                    differ[key] = {label: spelled[label] for label in sorted(plain)}
            shown_at, lacking = list(members), {}
            for i, row in enumerate(tables):
                if row['kind'] != 'const_tables' or i in labels and i not in family:
                    continue                  # a dropdown offers a choice of keys; another label table has its family
                for other in members:
                    mine, theirs = row['values'].keys(), tables[other]['values'].keys()
                    if mine < theirs and shares(row['values'], tables[other]['values']) and 3 * len(theirs - mine) <= len(theirs):
                        if i not in shown_at:
                            shown_at.append(i)
                        lacking.setdefault(shown_at.index(i), set()).update(theirs - mine)
            if differ or lacking:
                out.append(dict(tables=[tables[i] for i in shown_at], differ=differ,
                                lacking={i: sorted(keys) for i, keys in sorted(lacking.items())}))
        return out

    def lookup_keys(self):
        """JS/TS lookups `TABLE[expression]` in a module object constant (`const LABELS = {...}`, also
        imported): one row per lookup with the table's `keys`, the strings that select a stored value."""
        rows = []
        for row in self._syntax('table_lookups'):
            found, table = self._ts_constant(row['file'], row['name'])
            if found and isinstance(table, dict):
                rows.append(dict(row, keys=list(table)))
        return Rows(rows)

    def _compared_values(self):
        """The compared_names rows whose name folds to one literal: a module `const NAME = literal`, a member
        `Obj.KEY` of a module object constant, or either one imported from a mapped module."""
        if 'compared_values' not in self._derived:
            rows = []
            for row in self._syntax('compared_names'):
                found, value = self._ts_constant(row['file'], row['name'])
                if found and not isinstance(value, dict) and value is not None:
                    rows.append(dict(node=row['node'], file=row['file'], value=value, context='compare',
                                     function=row['function'], name=row['name'], folded=True,
                                     **{key: row[key] for key in ('line', 'column', 'end_line', 'end_column')}))
            self._derived['compared_values'] = rows
        return self._derived['compared_values']

    def _ts_constant(self, file, name, depth=0):
        """(found, value) of a JS/TS name in `file`: its literal, a module object's {key: literal}, or `Obj.KEY`."""
        head, _, member = name.partition('.')
        tables = self._derived.setdefault('ts_files', {})
        if file not in tables:
            facts = {kind: store.unpack(blob) for kind, blob in self.con.execute(
                "SELECT kind, data FROM part WHERE path=? AND kind IN ('const_tables', 'dependencies')", (file,))}
            consts = {qual: _js_literal(sig) for qual, sig in self.con.execute(
                "SELECT qual, sig FROM node WHERE file=? AND kind='const'", (file,))}
            consts.update({row['name']: row['values'] for row in facts.get('const_tables', ())})
            imports = {row['alias']: (row['resolved'], row['name']) for row in facts.get('dependencies', ())
                       if row.get('kind') == 'import' and row.get('alias') and row.get('resolved')}
            tables[file] = (consts, imports)
        consts, imports = tables[file]
        if head in consts:
            value = consts[head]
            if not member:
                return value is not _UNREADABLE, value
            return (isinstance(value, dict) and value.get(member) is not None), value.get(member) if isinstance(value, dict) else None
        if head in imports and depth < 3:
            module, imported = imports[head]
            target = self.con.execute('SELECT path FROM file WHERE module=?', (module,)).fetchone()
            if target is None or imported == 'default':
                return False, None
            return self._ts_constant(target[0], member if imported == '*' else imported + ('.' + member if member else ''),
                                     depth + 1) if imported != '*' or member else (False, None)
        return False, None

    def literal_groups(self, *, language=None, contexts=None, min_spellings=2):
        """String literals of production code grouped ignoring case, whitespace and punctuation (`literal_key`),
        within one kind of spelling (`literal_shape`: a code such as MAIN_DEPARTMENT never groups with the key
        'main-department' or the label 'Main department', nor a route '/admin' with 'admin'); a group with
        several spellings ('My Organization' / 'My organization') is a clue of drift, not a verdict. A spelling
        that only test files use does not count."""
        tests = {path for (path,) in self.con.execute('SELECT path FROM file WHERE is_test = 1')}
        groups = {}
        for row in self.literals(language=language, contexts=contexts):
            if not isinstance(row['value'], str) or row['file'] in tests:
                continue                    # numbers in comparisons serve old-value leads, not spellings
            key = literal_key(row['value'])
            if key:
                groups.setdefault((key, literal_shape(row['value'])), {}).setdefault(row['value'], []).append(row)
        return [dict(key=key, spellings={value: found for value, found in sorted(spellings.items())})
                for (key, _), spellings in sorted(groups.items()) if len(spellings) >= min_spellings]

    def schema_gaps(self, schemas=None):
        """Columns one description of a table has and another lacks. Each SQL description of tables (one
        .sql file, or one Prisma `migrations/` folder applied in order) and each Prisma schema (models, @map,
        @@map) is compared once, with the schema it describes: one in use (`prisma_schemas_in_use`) when one
        shares its tables, else the schema sharing the most tables and columns, then the nearest folder. A
        schema whose tables and columns all occur in a schema of another package (`package`) is a projection
        and lacks nothing. Archived files (`archived`) describe nothing. Only tables a description creates
        are compared; a description that creates at least half of a schema's tables also reports the tables
        it lacks. `schemas` replaces the map's descriptions (for example with a baseline's)."""
        from .readers.prisma import gaps
        rows = self.schemas() if schemas is None else schemas
        return gaps([row for row in rows if not self.archived(row['file'])], self.prisma_schemas_in_use(), self.package)

    def schema_delete_rules(self, schemas=None):
        """Relations whose delete rule differs between two Prisma schemas of one database, the pairs
        `schema_gaps` compares (`readers.prisma.delete_rules`): a provider template that cascades or nulls
        where the schema in use refuses the delete, or either schema without a foreign key the other has.
        `schemas` replaces the map's descriptions. A Prisma schema whose datasource has a provider and no url
        takes the url its `prisma.config.*` gives (`_config_url`)."""
        from .readers.prisma import delete_rules
        rows = self.schemas() if schemas is None else schemas
        rows = [dict(row, url=self._config_url(row['file'])) if row.get('kind') == 'prisma' and row['provider'] and not row['url']
                else row for row in rows if not self.archived(row['file'])]
        return delete_rules(rows, self.prisma_schemas_in_use(), self.package)

    def calls(self, *, include_reads=False, language=None):
        """Syntactic calls; optionally include symbol reads, never execution evidence."""
        self._mark_query('calls',language)
        rows = self._syntax('syntax_calls')
        if include_reads:
            self._mark_query('symbol_reads',language)
            rows += self._syntax('symbol_reads')
        return self._language_rows(rows,language)

    def python_calls(self):
        """The rows of `calls()` that Python files make (each row's `file` is the file whose facts hold it), read from
        those files' parts alone, once per handle and build: a JS/TS project's calls are not unpacked for them. The
        query counts as `calls()` (`query_coverage`): its other rows are only left out."""
        from .readers.registry import language_for
        self._mark_query('calls')
        if 'python_calls' not in self._derived:
            wanted = [path for (path,) in self.con.execute('SELECT path FROM file ORDER BY path') if language_for(path) == 'python']
            rows = []
            for start in range(0, len(wanted), 500):
                chunk = wanted[start:start + 500]
                found = dict(self.con.execute(f"SELECT path, data FROM part WHERE kind='syntax_calls' AND path IN "
                                              f"({','.join('?' * len(chunk))})", chunk))
                rows.extend(row for path in chunk for row in store.unpack(found.get(path)) or ())
            self._derived['python_calls'] = rows
        return Rows(self._derived['python_calls'])

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


    # ---- other homes ---------------------------------------------------------------
    def other_homes(self, ident: str, k: int = 5, *, words: str = "", decides=None,
                    not_same=(), sites=None) -> list[dict]:
        """One static decision-site query. Candidates never execute.

        `sites` names the rule's realized sites as (node, line, text); without
        them the home's own sites are used. `search_homes` also returns whether
        readable sites were found, so an empty list is not proof of no copies.
        """
        return self.search_homes(ident, k=k, words=words, decides=decides,
                                 not_same=not_same, sites=sites)['candidates']

    def search_homes(self, ident, *, k=None, words='', decides=None,
                     not_same=(), sites=None, since=None):
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
            for candidate in homes.other_homes(self.con, target, None, words, decides, excluded, sites):
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
                row_sigs = [set(json.loads(raw)) for (raw,) in self.con.execute('SELECT sigs FROM site WHERE node=?',(candidate['id'],))]
                matched = [g for g in old if any({s for s in g['sigs'] if s.startswith(('sg:n:','sg:t:','sg:m:','sg:s:','sg:set:','sg:v:','sg:f:'))} & own for own in row_sigs)]
                if not matched:
                    continue
                prior = found.setdefault(candidate['id'],dict(candidate,anchors=[target]))
                prior['stale'] = True
                prior['old_values'] = sorted({g['value'] for g in matched})
                prior['identity_shared'] = any(g['identity'] and any('sg:id:'+g['identity'] in own for own in row_sigs) for g in matched)
                prior['reason'] = 'stale copy? still matches old '+', '.join(prior['old_values'])+' -> update, bind or distinct; '+candidate['reason']
        ranked = homes.ranked(found.values(), k)
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

    def import_aliases(self, words):
        """{map id: ['module:name (file)']}: the names an import binds that share a word with `words`."""
        wanted = tokens(words)
        aliases, known = {}, {}
        modules = self.con.execute('SELECT path, module FROM file').fetchall()
        imports = store.parts(self.con, ('facts.imports',))['facts.imports']
        for file, module in modules:
            for name, target in imports.get(file, {}).items():
                if may_share(wanted, name) and wanted & tokens(name):
                    if target not in known:
                        known[target] = self.canonical(target)
                    canonical = known[target]
                    if canonical:
                        aliases.setdefault(canonical, []).append(f'{module}:{name} ({file})')
        return aliases

    def search(self, words):
        """Rank generated sites before bare name matches; intent ranking belongs to the caller."""
        wanted = tokens(words)
        sites = {}
        for ident, field, constant, identity in self.con.execute('SELECT node, field, const, identity FROM site'):
            sites.setdefault(ident, set()).update(tokens(' '.join(value or '' for value in (field,constant,identity))))
        aliases = self.import_aliases(words)
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
        delta = _without_moves(delta)
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
        for _, found in self._file_deltas(since, files):
            rows += found
        return rows

    def _file_deltas(self, since: str, files: list[str]) -> list[tuple]:
        """(file, its delta rows) for each of `files` that has a reader, in their order."""
        out = []
        names = {f: m for f, m in self.con.execute("SELECT path, module FROM file")}
        from .readers.registry import language_for, module_name
        for f in files:
            if not language_for(f):
                continue
            rows = []
            module = names.get(f) or (f[:-3].replace("/", ".") if language_for(f) == "python" else module_name(f))
            old = {f"{module}:{n['qual']}": (n["fp"], n["sig"]) for n in
                   self._baseline_part(since, f, module, 'nodes') or []}
            new = {i: (fp, sig) for i, fp, sig in self.con.execute("SELECT id, fp, sig FROM node WHERE file = ? AND "
                                                                    "kind NOT IN ('module','alias','missing')", (f,))}
            for i in sorted(set(old) | set(new)):
                if i not in new:
                    rows.append((i, "removed", old[i][0], None, old[i][1], None))
                elif i not in old:
                    rows.append((i, "added", None, new[i][0], None, new[i][1]))
                elif old[i][0] != new[i][0]:
                    rows.append((i, "changed", old[i][0], new[i][0], old[i][1], new[i][1]))
            out.append((f, rows))
        return out


def _without_moves(delta):
    """Delta rows without nested callbacks that only moved. A callback is named by where it starts
    (`<anonymous@LINE,COL>`), so a line added above it (a comment, an owner anchor) gives the same code
    another id: one id is removed and one added, or an id now names the next callback ("changed"). With
    positions aside, a callback whose old and new code (fingerprint) both occur again at the same place of
    the same function only moved; its row is dropped. A row with a part that occurs only on one side stays."""
    import re
    from collections import Counter
    position = re.compile(r"<anonymous@\d+,\d+>")
    def key(ident, fp):
        return position.sub("<anonymous>", ident), fp
    rows = [row for row in delta if position.search(row[0])]
    common = Counter(key(row[0], row[2]) for row in rows if row[2] is not None) \
        & Counter(key(row[0], row[3]) for row in rows if row[3] is not None)
    before, after, kept = Counter(common), Counter(common), []
    for row in delta:
        old, new = key(row[0], row[2]), key(row[0], row[3])
        if position.search(row[0]) and (row[2] is None or before[old] > 0) and (row[3] is None or after[new] > 0):
            if row[2] is not None:
                before[old] -= 1
            if row[3] is not None:
                after[new] -= 1
            continue
        kept.append(row)
    return kept


def _fold_values(text, env):
    """The constant values a right side can take: one folded constant, or each branch of `a if c else b`."""
    import ast
    from . import features as ff
    node = _expression(text)
    if node is None:
        return None
    branches, values = [node], []
    while branches:
        current = branches.pop(0)
        if isinstance(current, ast.IfExp):
            branches[:0] = [current.body, current.orelse]
            continue
        folded = ff.fold(current, env, {})
        if not folded or folded[0] not in ('str', 'num'):
            return None
        values.append(folded[1])
    return values


@__import__('functools').lru_cache(maxsize=4096)
def _expression(text):
    import ast
    try:
        return ast.parse(text, mode='eval').body
    except SyntaxError:
        return None


_UNREADABLE = object()


def _js_literal(text):
    """The value of a JS/TS literal the reader stored as a constant's signature, else _UNREADABLE."""
    text = text.strip()
    if text in ('true', 'false'):
        return text == 'true'
    if text == 'null':
        return None
    from flowguard.map.common import literal_value
    # A signature that is not a literal Python can read is not folded: no value is invented.
    value = literal_value(text.replace('_', '') if text[:1].isdigit() or text[:1] in '-.' else text, _UNREADABLE)
    return value if isinstance(value, (int, float, str)) else _UNREADABLE


_JS_STRING = r'''"(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*'|`(?:\\.|[^`\\$])*`'''
_JS_COMMENT_OR_STRING = re.compile(r'//[^\n]*|/\*.*?\*/|' + _JS_STRING, re.S)
# `schema: 'x'` (also a quoted key), or `path.join(...)`/`path.resolve(...)` of string literals after
# leading names such as `__dirname` or `import.meta.dirname`
_CONFIG_SCHEMA = re.compile(
    r'''(?<![\w$.])(?:schema|"schema"|'schema')\s*:\s*(?:(?P<plain>%(s)s)|path\s*\.\s*(?:join|resolve)\s*\(\s*'''
    r'''(?P<args>(?:%(n)s\s*,\s*)*(?:%(s)s)(?:\s*,\s*(?:%(s)s))*)\s*,?\s*\))'''
    % dict(s=_JS_STRING, n=r'[A-Za-z_$][\w$]*(?:\s*\.\s*[A-Za-z_$][\w$]*)*'))


def _config_schemas(text):
    """The schema paths a `prisma.config.ts` names, comments left out: `schema: 'x'` (`'schema': 'x'`,
    `"schema": "x"`) and `path.join(...)`/`path.resolve(...)` whose arguments are string literals (leading
    names such as `__dirname` or `import.meta.dirname` stand for the config's folder). Any other value (a variable, a
    template with `${}`) names nothing."""
    text = _JS_COMMENT_OR_STRING.sub(lambda found: found[0] if found[0][0] in '"\'`' else ' ', text)
    out = []
    for found in _CONFIG_SCHEMA.finditer(text):
        parts = [found['plain']] if found['plain'] else re.findall(_JS_STRING, found['args'])
        out.append(posixpath.join(*(re.sub(r'\\+', '/', part[1:-1]) for part in parts)))
    return out


# `datasource: { ... url: env('NAME') | process.env.NAME | process.env['NAME'] | 'literal' ... }` (also quoted keys)
_CONFIG_DATASOURCE = re.compile(r'''(?<![\w$.])(?:datasource|"datasource"|'datasource')\s*:\s*\{(?P<body>[^{}]*)\}''')
_CONFIG_URL = re.compile(
    r'''(?<![\w$.])(?:url|"url"|'url')\s*:\s*(?:env\s*\(\s*(?P<env>%(s)s)\s*\)|process\s*\.\s*env\s*(?:\.\s*(?P<name>[A-Za-z_$][\w$]*)|'''
    r'''\[\s*(?P<key>%(s)s)\s*\])|(?P<plain>%(s)s))''' % dict(s=_JS_STRING))


def _config_url(text):
    """The datasource url a `prisma.config.ts` gives, read as `_config_schemas` reads `schema:` (comments
    left out): `env('NAME')`, `process.env.NAME` or `process.env['NAME']` as `env:NAME`, a string literal as
    itself, as the Prisma reader writes a schema's url; '' for any other value or none."""
    text = _JS_COMMENT_OR_STRING.sub(lambda found: found[0] if found[0][0] in '"\'`' else ' ', text)
    for block in _CONFIG_DATASOURCE.finditer(text):
        found = _CONFIG_URL.search(block['body'])
        if found:
            quoted = found['env'] or found['key']
            return f"env:{found['name']}" if found['name'] else f'env:{quoted[1:-1]}' if quoted else found['plain'][1:-1]
    return ''


def _module_stem(path):
    """A module path without its JS/TS extension or `/index` (`src/types.js`, `src/types/index.ts` -> `src/types`)."""
    path = re.sub(r'\.(d\.)?[cm]?[jt]sx?$', '', path)
    return path[:-len('/index')] if path.endswith('/index') else path


def language_of(path):
    from .readers.registry import language_for
    return language_for(path)


def literal_key(value: str) -> str:
    """Letters and digits only, case folded: the spelling-independent identity of a label."""
    return ''.join(ch for ch in value.casefold() if ch.isalnum())


def literal_shape(value: str) -> tuple[str, str]:
    """The kind of spelling a literal is: its leading punctuation (a route '/x', an option '--x', an extension
    '.x') and 'code' (no lower-case letter: MAIN_DEPARTMENT, ID), 'text' (words with spaces: a label) or 'word'
    (a key, an id, one word). Only spellings of one kind can be the same label spelled two ways."""
    body = value.strip()
    lead = body[:len(body) - len(body.lstrip('/\\.-_#@:~+*'))]
    body = body[len(lead):].strip()
    kind = 'code' if not any(ch.islower() for ch in body) else 'text' if any(ch.isspace() for ch in body) else 'word'
    return lead, kind


class Definitions:
    """The value sets (`sets`, as `MapHandle._ts_sets`), schema models (`models`, as `_models`) and each module's
    folded constants (`env(module)`, as `_value_env`) of the map with some files' facts replaced
    (`MapHandle.definitions`); every one is built as the map builds its own."""

    def __init__(self, graph, replaced):
        self.graph = graph
        records = {path: facts for path, _, facts in replaced}
        self.modules = {module: facts for _, module, facts in replaced if module}
        held = {path: facts for path, _, facts in graph._kinds('value_sets')}
        held.update(records)
        self.sets = _sets_of(held[path] for path in sorted(held))
        schemas = dict((path, schema) for path, schema in graph._schema_rows() if path not in records)
        schemas.update(_schema_rows_of(records.items()))
        self.models = _models_of([(path, schemas[path]) for path in sorted(schemas)])
        self._owns, self._envs = {}, {}

    def _own(self, module):
        from . import decide
        if module not in self._owns:
            if module in self.modules:
                facts = self.modules[module]
                consts = sorted((node for node in facts['nodes'] if node['kind'] == 'const'), key=lambda node: node['line']) \
                    if facts else []
                rows = [(node['qual'], node['sig']) for node in consts]
            else:
                rows = self.graph._const_rows(module)
            self._owns[module] = decide.own_env(rows)
        return self._owns[module]

    def env(self, module):
        from . import decide
        if module not in self._envs:
            if module in self.modules:
                facts = self.modules[module]
                imports = facts['facts'].get('imports', {}) if facts else {}     # a test file keeps no `facts`
            else:
                imports = self.graph._module_imports(module)
            self._envs[module] = decide.module_env(self._own(module), imports, self._own)
        return self._envs[module]


def _sets_of(records):
    """{name: [row]} of the JS/TS value sets of these fact records, in their order."""
    found = {}
    for facts in records:
        for row in facts.get('value_sets', ()):
            found.setdefault(row['name'], []).append(row)
    return found


def _schema_rows_of(listed):
    """(path, schema facts) of each (path, facts) of a Prisma or SQL file."""
    from .readers.registry import SCHEMA_LANGUAGES, SUFFIXES
    suffixes = tuple(suffix for suffix, language in SUFFIXES.items() if language in SCHEMA_LANGUAGES)
    return [(path, facts.get('schema', {})) for path, facts in listed
            if path.lower().endswith(suffixes) and facts.get('language') in SCHEMA_LANGUAGES]


def _models_of(rows):
    from .readers.prisma import Models
    return Models([(path, schema) for path, schema in rows if schema.get('kind') == 'prisma'])


def _write_names(row):
    """(names, fields) a write row is found by: its model and table, its field and column, case folded."""
    return ({str(row.get('model') or '').casefold(), str(row.get('table') or '').casefold()} - {''},
            {str(row.get('field') or '').casefold(), str(row.get('db_column') or '').casefold()} - {''})


def _writes_target(row, target, models) -> bool:
    """`Model.field`, `table.column`, a model or table name, or a bare field/column name."""
    head, dot, tail = target.rpartition('.')
    names, fields = _write_names(row)
    if not dot:
        wanted = target.casefold()
        return wanted in names or wanted in fields
    if head.casefold() not in names and not (row.get('how') == 'name' and row.get('model') is None):
        return False
    return tail.casefold() in fields or row.get('unclear') and row.get('field') in ('?', '*') and head.casefold() in names
