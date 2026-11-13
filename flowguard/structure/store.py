"""SQLite storage of the map and its incremental build (C-1).

A build hashes every Python file, re-extracts only files whose bytes changed (or whose module
name changed), and re-links only those files, the files that import them (two levels through a
package `__init__`), files whose missing imports a new module may now satisfy, and files whose
guessed calls name a short name that was added or removed. Edges carry a provenance: `resolved`
(1.x `discover._resolve` through imports), `guessed` (an attribute call linked only because one
function in the repository has that name) or `observed` (added by a tracer). A vanished id is kept
in `gone` with its fingerprint, so `moved()` can propose where it went; nothing is re-pointed.
"""
from __future__ import annotations

import json
import posixpath
import sqlite3
import sys
import time
import zlib
from array import array
from pathlib import Path

from flowguard.map.common import DEFAULT_IGNORE, MapError, content_digest, is_test_file, matches_any, read_source
from flowguard.map.discover import _injected_classes, _resolve, _resolve_injected, _scope_imports
from flowguard.map.inventory import list_files
from . import analysis as fgs
from . import decide, roots as rootmod
from .extract import extract, syntax_tree
from .roots import syspath_entries
from .paths import project_files
from .readers.registry import ECMA, language_for, module_name, OTHER_SOURCE

FORMAT = "flowguard-map-1"
SCHEMA = """
CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS root(path TEXT PRIMARY KEY, how TEXT, rank INT);
CREATE TABLE IF NOT EXISTS file(path TEXT PRIMARY KEY, sha TEXT, module TEXT, names TEXT, is_test INT,
  parse_error TEXT, loc INT, build INT, syspath TEXT, data BLOB, physical_lines INT);
CREATE TABLE IF NOT EXISTS node(nid INTEGER PRIMARY KEY, id TEXT UNIQUE, file TEXT, module TEXT, qual TEXT,
  short TEXT, kind TEXT, cls TEXT, line INT, end_line INT, sig TEXT, doc TEXT, fp TEXT, shape BLOB, size INT,
  effects TEXT, raw BLOB, build INT);
CREATE INDEX IF NOT EXISTS node_file ON node(file);
CREATE INDEX IF NOT EXISTS node_fp ON node(fp);
CREATE INDEX IF NOT EXISTS node_short ON node(short);
CREATE INDEX IF NOT EXISTS node_module ON node(module, kind);
CREATE TABLE IF NOT EXISTS edge(src TEXT, dst TEXT, kind TEXT, prov TEXT, file TEXT, line INT);
CREATE INDEX IF NOT EXISTS edge_src ON edge(src);
CREATE INDEX IF NOT EXISTS edge_dst ON edge(dst);
CREATE INDEX IF NOT EXISTS edge_file ON edge(file);
CREATE TABLE IF NOT EXISTS site(node TEXT, line INT, field TEXT, op TEXT, const TEXT, value TEXT, vkind TEXT,
  identity TEXT, leads TEXT, neg INT, pred TEXT, file TEXT, sigs TEXT);
CREATE INDEX IF NOT EXISTS site_node ON site(node);
CREATE INDEX IF NOT EXISTS site_identity ON site(identity);
CREATE INDEX IF NOT EXISTS site_file ON site(file);
CREATE TABLE IF NOT EXISTS site_history(node TEXT, line INT, field TEXT, op TEXT, const TEXT, value TEXT,
  vkind TEXT, identity TEXT, leads TEXT, neg INT, pred TEXT, file TEXT, sigs TEXT, build INT,
  UNIQUE(node,line,field,op,const,value,identity,file,sigs));
CREATE INDEX IF NOT EXISTS site_history_node ON site_history(node);
CREATE TABLE IF NOT EXISTS key(node TEXT, kind TEXT, value TEXT, line INT, file TEXT);
CREATE INDEX IF NOT EXISTS key_kv ON key(kind, value);
CREATE INDEX IF NOT EXISTS key_file ON key(file);
CREATE TABLE IF NOT EXISTS tok(tid INTEGER PRIMARY KEY, tok TEXT UNIQUE, kind TEXT);
CREATE TABLE IF NOT EXISTS post(tid INT, nid INT, PRIMARY KEY(tid, nid)) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS post_nid ON post(nid);
CREATE TABLE IF NOT EXISTS unres(node TEXT, last TEXT, file TEXT);
CREATE INDEX IF NOT EXISTS unres_last ON unres(last);
CREATE INDEX IF NOT EXISTS unres_file ON unres(file);
CREATE TABLE IF NOT EXISTS gone(id TEXT, fp TEXT, kind TEXT, shape BLOB, file TEXT, sig TEXT, build INT, readers TEXT);
CREATE INDEX IF NOT EXISTS gone_id ON gone(id);
CREATE TABLE IF NOT EXISTS delta(build INT, id TEXT, change TEXT, old_fp TEXT, new_fp TEXT, old_sig TEXT,
  new_sig TEXT, file TEXT);
CREATE INDEX IF NOT EXISTS delta_file ON delta(file, build);
CREATE TABLE IF NOT EXISTS part(kind TEXT, path TEXT, data BLOB, PRIMARY KEY(kind, path)) WITHOUT ROWID;
"""
GUESS_MIN = 4                                       # fgmap: a short name of more than 3 letters, not COMMON
SKETCH = 4                                          # shape postings per node (the smallest 3-gram hashes)


def pack(obj) -> bytes:
    return zlib.compress(json.dumps(obj, separators=(",", ":")).encode(), 1)


def unpack(blob):
    return json.loads(zlib.decompress(blob)) if blob else {}


def save_facts(con, path: str, facts: dict) -> None:
    """A file's stored facts: the whole record in `file.data`, and each kind once more in `part`.

    A query that needs one or two kinds of every file (languages, anchors, writes) reads those parts
    instead of unpacking every file's whole record. Four derived parts index the record: `facts.imports`
    is the `imports` of the `facts` kind, `assignments.fields` the fields its assignments write,
    `assignments.writes` the assignment rows `MapHandle.writes` reads (every row of a Python record, the
    member assignments with a field of a JS/TS one) and `syntax_calls.unresolved` [node, file, text] of each
    JS/TS syntax call the linker left unresolved, a JSX element aside (what `MapHandle.call_index` resolves
    by name). A derived part with nothing in it is not stored; a reader reads its absence as empty."""
    con.execute("UPDATE file SET data=? WHERE path=?", (pack(facts), path))
    con.execute("DELETE FROM part WHERE path=?", (path,))
    rows = [(kind, path, pack(value)) for kind, value in facts.items()]
    if isinstance(facts.get("facts"), dict) and "imports" in facts["facts"]:
        rows.append(("facts.imports", path, pack(facts["facts"]["imports"])))
    language = facts.get("language", "python")
    if facts.get("assignments"):
        fields = {row.get("field") for row in facts["assignments"]}
        rows.append(("assignments.fields", path, pack(sorted(fields - {None}) + ([None] if None in fields else []))))
        written = facts["assignments"] if language == "python" else \
            [row for row in facts["assignments"] if row.get("form") == "member" and row.get("field")] if language in ECMA else []
        if written:
            rows.append(("assignments.writes", path, pack(written)))
    if language in ECMA:
        unresolved = [[call["node"], call["file"], call["text"]] for call in facts.get("syntax_calls", ())
                      if not (call.get("resolved") or call.get("kind") == "jsx-element")]
        if unresolved:
            rows.append(("syntax_calls.unresolved", path, pack(unresolved)))
    con.executemany("INSERT INTO part VALUES(?,?,?)", rows)


def parts(con, kinds) -> dict:
    """{kind: {path: value}} of the stored parts of these kinds; a file without a kind has no entry."""
    found = {kind: {} for kind in kinds}
    if found:
        for kind, path, blob in con.execute(f"SELECT kind, path, data FROM part WHERE kind IN ({','.join('?' * len(found))})",
                                            list(found)):
            found[kind][path] = unpack(blob)
    return found


def shape_blob(values: list[int]) -> bytes:
    return array("I", values).tobytes()


def shape_list(blob) -> list[int]:
    a = array("I")
    a.frombytes(blob or b"")
    return list(a)


def connect(path: Path) -> sqlite3.Connection:
    """SQLite owns serialization and rollback; a failed cache read is never an empty map."""
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=30)
    try:
        con.execute('PRAGMA journal_mode=DELETE')
        con.execute('PRAGMA synchronous=FULL')
        con.executescript('BEGIN IMMEDIATE;\n' + SCHEMA + '\nCOMMIT;')
        with con:
            con.execute('BEGIN IMMEDIATE')
            if 'physical_lines' not in {row[1] for row in con.execute('PRAGMA table_info(file)')}:
                con.execute('ALTER TABLE file ADD COLUMN physical_lines INT DEFAULT 0')
            row = con.execute("SELECT v FROM meta WHERE k='format'").fetchone()
            if row and row[0] != FORMAT:
                raise MapError(f'{path}: cache format {row[0]!r} differs from {FORMAT!r}; '
                               'preserve or remove the disposable cache before rebuilding')
            if row is None:
                con.execute("INSERT INTO meta VALUES('format', ?)", (FORMAT,))
    except BaseException as error:
        con.close()
        if isinstance(error, sqlite3.DatabaseError):
            raise MapError(f'{path}: SQLite cache could not be opened: {error}; '
                           'no cache result was accepted') from error
        raise
    return con


def project_config(root: Path, *, section='flowguard') -> dict:
    """Read a tool section from the project's existing TOML; damaged inputs are errors."""
    import tomllib
    path = Path(root) / 'pyproject.toml'
    if not path.exists() and not path.is_symlink():
        return {}
    return tomllib.loads(path.read_text(encoding='utf-8-sig')).get('tool', {}).get(section, {})


def reader_digest():
    """A map also depends on the reader that produced it, not only project bytes."""
    package = Path(__file__).resolve().parents[1]
    paths = sorted((package / 'structure').rglob('*.py'))
    paths += [package / 'map' / name for name in ('common.py', 'inventory.py', 'discover.py', 'discovery_syntax.py')]
    paths.append(package / 'intent' / 'anchors.py')
    text = sys.version + '\n' + '\n'.join(path.name + ':' + content_digest(path) for path in paths)
    return content_digest(Path(__file__), data=text.encode())


class Linker:
    """Name resolution for one build: every module name, the 1.x resolver's inputs, constant envs."""

    def __init__(self, con, root: Path, file_names: dict, every: dict, root_dirs: list[str], multi=None,
                 syspath=None):
        self.con, self.root = con, root
        self.primary = {f: ns[0][0] for f, ns in file_names.items()}
        self.mod_to_path = {n: f for f, ns in file_names.items() for n, _ in ns}
        self.every = every
        self.multi = multi or {}                     # a module name several files can have, by root
        self.syspath = {f: [d for _, d in v] for f, v in (syspath or {}).items() if v}
        self.root_dirs = root_dirs
        self.namespaces = {".".join(n.split(".")[:i]) for n in list(every) + list(self.mod_to_path)
                           for i in range(1, n.count(".") + 1)} - set(every) - set(self.mod_to_path)
        self.py_paths = tuple(sorted(file_names))
        self.tops = {n.split(".")[0] for n in every} | {n.split(".")[0] for n in self.mod_to_path}
        self._data, self._own = {}, {}
        self.index = {}
        self.short = {}
        for file, qual, kind, cls in con.execute(
                "SELECT file, qual, kind, cls FROM node WHERE kind IN ('function','method','class')"):
            if language_for(file) != 'python':
                continue
            if kind != "class":
                self.index.setdefault(file, {})[qual] = {"class": cls}
                last = qual.rsplit(".", 1)[-1]
                self.short.setdefault(last, set()).add(f"{self.primary.get(file, '?')}:{qual}")
        self.tids = {}
        self.resolve_errors = []                     # 1.x _resolve recursion on self-referring constructors
        self.consts = {i for (i,) in con.execute("SELECT id FROM node WHERE kind='const'")}
        self.names = {}
        self._external: dict = {}
        self._envp: dict = {}
        self._suffix = None
        self.injected = None

    def data(self, path: str) -> dict:
        if path not in self._data:
            row = self.con.execute("SELECT data FROM file WHERE path=?", (path,)).fetchone()
            self._data[path] = unpack(row[0]) if row else {}
        return self._data[path]

    def facts(self):
        linker = self

        class View(dict):
            """Facts loaded on first use; `get` loads too (1.x `_resolve` calls facts.get(path, {}), and a
            plain dict.get would make an edge depend on which files an earlier link happened to load)."""
            def __missing__(self, path):
                value = linker.data(path).get("facts") or {"functions": {}, "classes": [], "imports": {}, "instances": {}}
                self[path] = value
                return value

            def get(self, path, default=None):
                return self[path] if path in linker.primary else default
        return View()

    def choose(self, name: str, importer: str, want: str = "") -> str:
        """The file an ambiguous module name means for one importer: the one that binds the imported name,
        then the one under a directory the importer puts on sys.path (latest insert first), then the one
        whose root holds the importer (deepest), then the one in the importer's own directory."""
        files = list(dict.fromkeys(self.multi[name]))
        if want:
            binding = [f for f in files if self.binds(f, want)]
            if len(binding) == 1:
                return binding[0]
            files = binding or files
        rel = name.replace(".", "/")

        def root_of(f):
            for tail in (rel + ".py", rel + "/__init__.py"):
                if f == tail:
                    return ""
                if f.endswith("/" + tail):
                    return f[:-len(tail) - 1]
            return None
        roots = {f: root_of(f) for f in files}
        for d in reversed(self.syspath.get(importer, [])):
            hit = [f for f in files if roots[f] == d]
            if hit:
                return hit[0]
        under = [f for f in files if roots[f] is not None and (roots[f] == "" or importer.startswith(roots[f] + "/"))]
        if under:
            return max(under, key=lambda f: len(roots[f]))
        here = posixpath.dirname(importer)
        return next((f for f in files if roots[f] == here), self.mod_to_path.get(name) or self.every.get(name) or files[0])

    def binds(self, f: str, name: str) -> bool:
        """Does file f bind `name` by itself: a module-level name, a lazy export, or a submodule of its package."""
        d = self.data(f)
        if name in d.get("bound", []) or name in d.get("lazy", {}):
            return True
        if f == "__init__.py" or f.endswith("/__init__.py"):
            base = posixpath.dirname(f)
            return any(posixpath.join(base, name + tail) in self.primary for tail in (".py", "/__init__.py"))
        return False

    def exact(self, name: str, importer: str, want: str = "") -> str | None:
        """The file a module name means exactly (no prefix fallback), or None. An ambiguous name is chosen
        per importer (`choose`), with `want` the name a `from` import takes from it."""
        if name in self.multi:
            return self.choose(name, importer, want)
        if name in self.mod_to_path:
            return self.mod_to_path[name]
        if name in self.every:
            return self.every[name]
        here = posixpath.dirname(importer)
        if posixpath.join(here, "__init__.py") not in self.primary:
            rel = name.replace(".", "/")
            for cand in (posixpath.join(here, rel + ".py"), posixpath.join(here, rel, "__init__.py")):
                if cand in self.primary:
                    return cand
        return None

    def envp(self, ident: str | None) -> list:
        """The name-carrying parameters of a getenv wrapper (extract.env_reads), or []."""
        if not ident:
            return []
        if ident not in self._envp:
            row = self.con.execute("SELECT raw FROM node WHERE id=?", (ident,)).fetchone()
            self._envp[ident] = (unpack(row[0]).get("envp", []) if row and row[0] else [])
        return self._envp[ident]

    def external(self, top: str) -> bool:
        """Does the interpreter find this top-level name outside the repository (stdlib, site-packages)?"""
        if top not in self._external:
            self._external[top] = bool(rootmod.installed_tops({top}, self.root))
        return self._external[top]

    def by_suffix(self, mod: str, importer: str, want: str = "") -> str | None:
        """The repository file an import names when no import root reaches it, by file path: a module of
        that dotted path in the importer's directory (pytest and scripts put it on sys.path), else under one
        of the importer's parent directories (the deepest), else the only such file in the repository. With
        `want`, the file must bind that name (or have it as a submodule). None when nothing or several files
        fit equally, and for a top-level name the interpreter finds outside the repository."""
        if not mod or self.external(mod.split(".")[0]):
            return None
        if self._suffix is None:
            self._suffix = {}
            for path in self.py_paths:
                parts = path[:-3].split("/")
                if parts[-1] == "__init__":
                    parts = parts[:-1]
                for i in range(len(parts)):
                    self._suffix.setdefault(".".join(parts[i:]), []).append(path)
        files = [f for f in self._suffix.get(mod, []) if f != importer and (not want or self.binds(f, want))]
        if not files:
            return None
        rel = mod.replace(".", "/")

        def base(f):                                  # the directory that would have to be on sys.path
            tail = f[:-len("/__init__.py")] if f.endswith("/__init__.py") else f[:-3]
            if tail == rel:
                return ""
            return tail[:-len(rel) - 1] if tail.endswith("/" + rel) else None
        here = posixpath.dirname(importer)
        under = [(len(b), f) for f in files if (b := base(f)) is not None and (b == "" or here == b or
                                                                             here.startswith(b + "/"))]
        if under:
            best = max(n for n, _ in under)
            top = [f for n, f in under if n == best]
            return top[0] if len(top) == 1 else None
        return files[0] if len(files) == 1 else None

    def relative(self, importer: str, level: int, module: str, name: str) -> tuple[str, str] | None:
        """(file, module name as the map knows it) of a relative import resolved against the importer's
        directory, for a relative import that no package name anchors."""
        d = posixpath.dirname(importer)
        for _ in range(level - 1):
            d = posixpath.dirname(d)
        rel = posixpath.join(d, module.replace(".", "/")) if module else d
        if module:
            for cand in (rel + ".py", rel + "/__init__.py"):
                if cand in self.primary and self.binds(cand, name):
                    return cand, self.primary[cand]
            for cand in (rel + "/" + name + ".py", rel + "/" + name + "/__init__.py"):
                if cand in self.primary:
                    return cand, self.primary[cand]
            return None
        for cand in (posixpath.join(rel, name + ".py"), posixpath.join(rel, name, "__init__.py")):
            if cand in self.primary:
                return cand, self.primary[cand]
        init = posixpath.join(rel, "__init__.py") if rel else "__init__.py"
        if init in self.primary and self.binds(init, name):
            return init, self.primary[init]
        return None

    def is_module(self, name: str) -> bool:
        return name in self.mod_to_path or name in self.every

    def canon(self, mod: str, name: str, depth: int = 0) -> str | None:
        """`module:NAME` of a constant reached as mod.name, through submodules and re-exports."""
        parts = name.split(".")
        while len(parts) > 1 and self.is_module(f"{mod}.{parts[0]}"):
            mod, parts = f"{mod}.{parts[0]}", parts[1:]
        if len(parts) == 1 and self.is_module(f"{mod}.{parts[0]}"):
            return None
        path = self.mod_to_path.get(mod) or self.every.get(mod)
        dotted = ".".join(parts)
        if path is None:
            return f"{mod}:{dotted}"
        primary = self.primary[path]
        if f"{primary}:{dotted}" in self.consts or f"{primary}:{parts[0]}" in self.consts or depth >= 3:
            return f"{primary}:{dotted}"
        binding = (self.data(path).get("facts") or {}).get("imports", {}).get(parts[0])
        rest = ".".join(parts[1:])
        if binding and ":" in binding:
            m2, _, n2 = binding.partition(":")
            return self.canon(m2, n2 + (f".{rest}" if rest else ""), depth + 1)
        if binding and rest:
            return self.canon(binding, rest, depth + 1)
        return f"{primary}:{dotted}"

    def own_env(self, module: str) -> dict:
        if module not in self._own:
            path = self.mod_to_path.get(module) or self.every.get(module)
            rows = self.con.execute("SELECT qual, sig FROM node WHERE file=? AND kind='const' ORDER BY line",
                                    (path,)).fetchall() if path else []
            self._own[module] = decide.own_env(rows)
        return self._own[module]


def _is_test(rel: str) -> bool:
    return is_test_file(rel) or rel.endswith("conftest.py")


def build(root, db_path=None, *, roots=None, force=False, workers=None) -> dict:
    """Commit one complete map build, or leave the last complete build unchanged."""
    t0 = time.perf_counter()
    root = Path(root).resolve()
    db_path = Path(db_path) if db_path else root / '.flowguard/cache/map.sqlite'
    con = connect(db_path)
    try:
        with con:
            con.execute('BEGIN IMMEDIATE')
            stats = _build(con, root, roots, force, workers, t0)
            prepared = time.perf_counter()
        committed = time.perf_counter()
    except sqlite3.DatabaseError as error:
        raise MapError(f'{db_path}: SQLite cache build failed: {error}; '
                       'no partial build was accepted') from error
    finally:
        con.close()
    stats['seconds'] = round(committed - t0, 3)
    if 'phases' in stats:
        stats['phases']['commit'] = round(committed - prepared, 3)
    return stats


def ignored(root):
    """The patterns of the paths a map of `root` never reads: FlowGuard's defaults and `[tool.flowguard] exclude`."""
    # A real package may be named venv (CPython has one). Environment ownership
    # is decided by project_code, including pyvenv.cfg, rather than that name.
    return [pattern for pattern in DEFAULT_IGNORE if pattern != 'venv/**'] + [str(p) for p in project_config(root).get("exclude", [])]


def _build(con, root, roots, force, workers, t0):
    ignore = ignored(root)
    files = [f for f in list_files(root) if not matches_any(f, ignore)]
    sources = [f for f in files if language_for(f)]
    py = [f for f, owned in zip(sources, project_files([str(root / f) for f in sources], root)) if owned]
    python_files = [f for f in py if language_for(f) == 'python']
    blobs = {f: (root / f).read_bytes() for f in py}
    shas = {f: content_digest(root / f, data=b) for f, b in blobs.items()}
    old = {p: (s, n, sp) for p, s, n, sp in con.execute("SELECT path, sha, names, syspath FROM file")}
    changed = {f for f in py if f not in old or old[f][0] != shas[f]}
    from .readers.context import context_digest
    tool_digest = content_digest(Path(__file__), data=(reader_digest() + context_digest(root, files)).encode())
    previous_tool = con.execute("SELECT v FROM meta WHERE k='reader_digest'").fetchone()
    if force or previous_tool is None or previous_tool[0] != tool_digest:
        changed = set(py)
    removed = set(old) - set(blobs)
    syspath = {}
    for f in py:
        if f in changed:
            if f in python_files and (b"sys.path" in blobs[f] or b"addsitedir" in blobs[f]):
                try:
                    syspath[f] = syspath_entries(syntax_tree(read_source(root / f, data=blobs[f])), f)
                except SyntaxError:
                    syspath[f] = []
        elif old[f][2]:
            syspath[f] = json.loads(old[f][2])
    found_roots = rootmod.detect(root, files, python_files, {f: v for f, v in syspath.items() if v})
    if roots is not None:
        explicit = []
        for value in roots:
            path = Path(value)
            if path.is_absolute():
                path = path.resolve()
                if not path.is_relative_to(root):
                    raise ValueError(f'import root must be inside the project: {path}')
                value = path.relative_to(root).as_posix()
            normalized = rootmod._norm('', str(value).replace('\\', '/'))
            if normalized is None:
                raise ValueError(f'import root must be inside the project: {value}')
            explicit.append((normalized, "[tool.flowguard] roots"))
        found_roots = sorted(dict(found_roots + explicit).items(), key=lambda item: (-len(item[0]), item[0]))
    tops = rootmod.implicit_tops(python_files, found_roots)
    shadowed = rootmod.installed_tops(tops, root) if tops else set()
    file_names, every, multi = rootmod.names(python_files, found_roots, shadowed)
    for f in py:
        if f not in file_names:
            name = module_name(f)
            file_names[f] = [(name, '')]
            every[name] = f
    old_roots = con.execute("SELECT path, how FROM root ORDER BY rank").fetchall()
    roots_changed = [tuple(r) for r in old_roots] != [tuple(r) for r in found_roots]
    renamed = {f for f in py if f not in changed and old[f][1] != json.dumps(file_names[f])}
    stats = {"files": len(py), "parsed": 0, "linked": 0, "removed": len(removed), "build": None,
             "roots": [{"path": p, "how": h} for p, h in found_roots]}
    if not (changed or removed or renamed or roots_changed):
        stats.update(build=int(con.execute("SELECT v FROM meta WHERE k='build'").fetchone()[0]),
                     seconds=round(time.perf_counter() - t0, 3), changed=False,
                     source_lines=con.execute('SELECT COALESCE(SUM(physical_lines),0) FROM file WHERE is_test=0').fetchone()[0],
                     test_lines=con.execute('SELECT COALESCE(SUM(physical_lines),0) FROM file WHERE is_test=1').fetchone()[0])
        stats.update(capabilities=_capabilities(con, files))
        return stats
    build_no = int((con.execute("SELECT v FROM meta WHERE k='build'").fetchone() or [0])[0]) + 1
    redo = changed | renamed
    touched = redo | removed
    snapshot = {r[0]: r for r in con.execute(
        f"SELECT id, fp, kind, shape, file, sig, short FROM node WHERE file IN ({','.join('?' * len(touched))})",
        sorted(touched))} if touched else {}
    old_modules = {r[0] for r in snapshot.values() if r[2] in ("module", "alias")}
    # A constructor call in another file can change an injected collaborator.
    # Relink possible owner classes from bytes already read; never reparse them just for this.
    relink = set(redo) | {f for f in py if b"self." in blobs[f] and b"__init__" in blobs[f]}
    if snapshot:
        marks = ",".join("?" * len(snapshot))
        readers = {}
        for src, dst, kind in con.execute(f"SELECT src, dst, kind FROM edge WHERE dst IN ({marks})", list(snapshot)):
            readers.setdefault(dst, set()).add(src)
        importers = {f for (f,) in con.execute(
            f"SELECT DISTINCT file FROM edge WHERE kind LIKE 'imports%' AND dst IN ({marks})", list(snapshot))}
        relink |= importers
        inits = sorted(f for f in importers if f.endswith("__init__.py"))   # a package re-exports names
        if inits:
            relink |= {f for (f,) in con.execute(
                f"SELECT DISTINCT file FROM edge WHERE kind LIKE 'imports%' AND dst IN (SELECT id FROM node WHERE "
                f"kind IN ('module','alias') AND file IN ({','.join('?' * len(inits))}))", inits)}
    else:
        readers = {}
    for f in sorted(touched):
        _delete_file(con, f, keep_file=f in redo)
    t_read = time.perf_counter()
    order = sorted(redo)
    extracted, stats["workers"] = extract_all(root, [(f, blobs[f], file_names[f][0][0], _is_test(f)) for f in order], workers=workers)
    for f, facts in zip(order, extracted):            # stored in path order whatever process read the file
        _store_file(con, f, facts, shas[f], file_names[f], _is_test(f), build_no)
        stats["parsed"] += 1
    t_extract = time.perf_counter()
    for f in removed:
        con.execute("DELETE FROM file WHERE path=?", (f,))
        con.execute("DELETE FROM part WHERE path=?", (f,))
    new_modules = {ns[0][0] for f in redo for ns in [file_names[f]]}
    added_names = new_modules - old_modules
    if added_names or removed:
        # Previously missing literal foreign imports may now bind a new file.
        # Re-link cached facts; do not reparse unchanged source or guess a target.
        relink |= {path for path in py if language_for(path) != 'python'}
    if added_names:
        marks = ",".join("?" * len(added_names))
        relink |= {f for (f,) in con.execute(f"SELECT DISTINCT file FROM edge WHERE dst IN ({marks})",
                                              [f"missing:{n}" for n in added_names])}
    shorts = {r[6] for r in snapshot.values() if r[2] in ("function", "method")}
    shorts |= {s for (s,) in con.execute(
        f"SELECT short FROM node WHERE file IN ({','.join('?' * len(redo))}) AND kind IN ('function','method')",
        sorted(redo))} if redo else set()
    shorts = [s for s in shorts if s and len(s) >= GUESS_MIN and s not in fgs.COMMON]
    for i in range(0, len(shorts), 500):
        chunk = shorts[i:i + 500]
        relink |= {f for (f,) in con.execute(
            f"SELECT DISTINCT file FROM unres WHERE last IN ({','.join('?' * len(chunk))})", chunk)}
    if roots_changed or renamed:
        relink = set(py)
    relink &= set(py)
    con.execute("DELETE FROM root")
    con.executemany("INSERT INTO root VALUES(?,?,?)", [(p, h, i) for i, (p, h) in enumerate(found_roots)])
    linker = Linker(con, root, file_names, every, [p for p, _ in found_roots], multi, syspath)
    linker.names = file_names
    facts = linker.facts()
    for f in sorted(relink):
        if f not in redo:
            _unlink_file(con, f)
        _link_file(con, linker, facts, f)
        stats["linked"] += 1
    con.execute("DELETE FROM node WHERE kind IN ('missing','alias') AND id NOT IN (SELECT dst FROM edge) "
                "AND id NOT IN (SELECT src FROM edge)")
    t_link = time.perf_counter()
    _record_delta(con, snapshot, readers, build_no, redo)
    con.execute("INSERT OR REPLACE INTO meta VALUES('build', ?)", (str(build_no),))
    con.execute("INSERT OR REPLACE INTO meta VALUES('reader_digest', ?)", (tool_digest,))
    con.execute("INSERT OR REPLACE INTO meta VALUES('built_at', ?)", (time.strftime("%Y-%m-%dT%H:%M:%S"),))
    stats['source_lines'] = con.execute('SELECT COALESCE(SUM(physical_lines),0) FROM file WHERE is_test=0').fetchone()[0]
    stats['test_lines'] = con.execute('SELECT COALESCE(SUM(physical_lines),0) FROM file WHERE is_test=1').fetchone()[0]
    t_end = time.perf_counter()
    stats["phases"] = {"read": round(t_read - t0, 2), "extract": round(t_extract - t_read, 2),
                       "link": round(t_link - t_extract, 2), "store": round(t_end - t_link, 2)}
    stats.update(build=build_no, seconds=round(time.perf_counter() - t0, 3), changed=True,
                 resolve_errors=linker.resolve_errors[:20], resolve_error_count=len(linker.resolve_errors),
                 capabilities=_capabilities(con, files))
    return stats


def _delete_file(con, f: str, keep_file: bool) -> None:
    _unlink_file(con, f)
    con.execute("DELETE FROM post WHERE nid IN (SELECT nid FROM node WHERE file=?)", (f,))
    con.execute("DELETE FROM node WHERE file=? AND kind NOT IN ('missing')", (f,))
    if not keep_file:
        con.execute("DELETE FROM file WHERE path=?", (f,))
        con.execute("DELETE FROM part WHERE path=?", (f,))


def _unlink_file(con, f: str) -> None:
    """Remove what linking wrote for one file (edges, sites, keys, postings, unresolved calls)."""
    con.execute("DELETE FROM edge WHERE file=? AND prov != 'observed'", (f,))
    con.execute("INSERT OR IGNORE INTO site_history SELECT *,COALESCE((SELECT CAST(v AS INT)+1 FROM meta WHERE k='build'),1) FROM site WHERE file=?", (f,))
    con.execute("DELETE FROM site WHERE file=?", (f,))
    con.execute("DELETE FROM key WHERE file=?", (f,))
    con.execute("DELETE FROM unres WHERE file=?", (f,))
    con.execute("DELETE FROM post WHERE nid IN (SELECT nid FROM node WHERE file=? AND kind IN ('function','method'))", (f,))


PARALLEL_MIN = 48          # files re-read in one build before extraction runs in worker processes


def workers_wanted(n_files: int) -> int:
    """Worker processes for extracting n files: FG2_MAP_WORKERS when set (0 or 1: in this process), else one
    per usable CPU (at most 8) once there are PARALLEL_MIN files. Workers are forked, so only a process
    with a single thread uses them (forking a threaded process can deadlock); otherwise the build is serial."""
    import os
    import threading
    want = os.environ.get("FG2_MAP_WORKERS", "")
    if want.strip():
        count = int(want)
    elif n_files < PARALLEL_MIN:
        return 1
    else:
        count = min(8, len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else os.cpu_count() or 1)
    import multiprocessing
    if count <= 1 or "fork" not in multiprocessing.get_all_start_methods() or threading.active_count() > 1:
        return 1
    return min(count, max(n_files, 1))


def _extract_one(task):
    root, rel, data, module, is_test = task
    return extract(root, rel, data, module, is_test)


def extract_all(root: Path, tasks: list[tuple], *, workers=None) -> tuple[list[dict], int]:
    """extract() of every (rel, bytes, module, is_test), in the given order, and the number of processes used.
    Each file's facts depend on that file alone, so a pool gives the same facts as one process; the
    results come back in task order and are stored in that order (a deterministic merge)."""
    jobs = [(root, rel, data, module, is_test) for rel, data, module, is_test in tasks]
    n = workers_wanted(len(jobs)) if workers is None else min(max(int(workers), 1), max(len(jobs), 1))
    if n <= 1:
        return [_extract_one(j) for j in jobs], 1
    import multiprocessing
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(max_workers=n, mp_context=multiprocessing.get_context("fork" if "fork" in multiprocessing.get_all_start_methods() else "spawn")) as pool:
        return list(pool.map(_extract_one, jobs, chunksize=max(1, min(16, len(jobs) // (n * 4) or 1)))), n


def _store_file(con, f, facts, sha, names, is_test, build_no) -> None:
    module = names[0][0]
    facts['locations'] = {n['qual']: dict(column=n.get('column',1), end_column=n.get('end_column'))
                          for n in facts.get('nodes', [])}
    keep ={k: facts[k] for k in ("imports", "import_lines", "lines_all", "import_reads", "literal_dynamic_imports",
                                  "unknown_dynamic_imports", "lazy", "bound", "keys", "facts", "optional",
                                  "star", "getattr", "submodules", "doc", "typing", "dirrel",
                                  "handlers", "literal_sets", "assignments", "syntax_calls", "symbol_reads",
                                  "language", "parser", "locations", "dependencies", "exports", "bindings",
                                  "binding_unknowns", "syntax_recoveries", "anchors", "anchor_issues",
                                  "writes", "literals", "schema", "field_types", "queries", "value_sets",
                                  "typed_fields", "typed_writes", "numbers", "compared_names", "const_tables",
                                  "table_lookups", "option_lists", "type_names") if k in facts}
    con.execute("INSERT OR REPLACE INTO file VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (f, sha, module, json.dumps(names), int(is_test), facts["parse_error"], facts["loc"], build_no,
                 json.dumps(facts["syspath"]), None, facts.get('source_lines',0)))
    save_facts(con, f, keep)
    rows = [(module, f, module, "", "", "module", "", 1, None, "", facts.get("doc", ""), facts.get("module_fp", sha[:20]),
             b"", 0, "", b"", build_no)]
    for alias, _root in names[1:]:
        rows.append((alias, f, module, "", "", "alias", "", 1, None, f"alias of {module} (root {_root or '.'})", "",
                     sha[:20], b"", 0, "", b"", build_no))
    effects = {s: sorted({e[0] for e in fn.get("effects", [])}) for s, fn in facts.get("facts", {}).get("functions", {}).items()}
    for n in facts["nodes"]:
        rows.append((f"{module}:{n['qual']}", f, module, n["qual"], n["qual"].rsplit(".", 1)[-1], n["kind"], n["cls"],
                     n["line"], n["end"], n["sig"], n["doc"], n["fp"], shape_blob(n["shape"]), n["size"],
                     ",".join(effects.get(n["qual"], [])), pack(n["raw"]) if n.get("raw") else b"", build_no))
    con.executemany("INSERT OR REPLACE INTO node(id, file, module, qual, short, kind, cls, line, end_line, sig, doc, fp,"
                    " shape, size, effects, raw, build) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)


def _resolve_call(lk, facts, call: str, sym: str, f: str):
    """1.x `discover._resolve`, except that its unbounded recursion on a constructor that names itself
    (seen in pip: `self.x = self.x.y(...)`) is counted in the build stats instead of stopping the build.
    When 1.x finds nothing, a name bound by an import (also inside the function) is followed through
    package re-exports (`from pkg import f` where pkg/__init__.py has `from .impl import f`)."""
    try:
        found = _resolve(call, sym, f, facts, lk.index, lk.mod_to_path, py_paths=lk.py_paths, import_roots=lk.root_dirs)
    except RecursionError:
        lk.resolve_errors.append(f"{f}:{sym}: {call}")
        return None
    if found or (found := _follow_export(lk, facts, call, sym, f)):
        return found
    parts = call.split('.')
    if len(parts) != 3 or parts[0] != 'self' or not facts[f].get('injected'):
        return None
    if lk.injected is None:
        for file in lk.primary:
            data = facts[file]
            for name, function in data.get('functions', {}).items():
                if 'params' in function:
                    lk.index[file][name]['params'] = function['params']
        lk.injected = _injected_classes(facts, lk.index, lk.mod_to_path,
                                       py_paths=lk.py_paths, import_roots=lk.root_dirs)
    return _resolve_injected(call, sym, f, facts[f], lk.index, lk.injected)


def _follow_export(lk, facts, call: str, sym: str, f: str, depth: int = 4) -> str | None:
    parts = call.split(".")
    bound = _scope_imports(facts[f], sym).get(parts[0], "")
    if not bound:
        return None
    mod, _, name = bound.partition(":")
    chain = ([name] if name else []) + parts[1:]
    importer = f
    for _ in range(depth):
        if not chain:
            return None
        if len(chain) > 1 and (sub := lk.exact(f"{mod}.{chain[0]}", importer)):
            mod, chain = lk.primary[sub], chain[1:]              # pkg.sub.f(): into the submodule
            continue
        path = lk.exact(mod, importer, chain[0])
        if path is None:
            return None
        index, symbol = lk.index.get(path, {}), ".".join(chain)
        if symbol in index:
            return f"{path}#{symbol}"
        if f"{symbol}.__init__" in index:
            return f"{path}#{symbol}.__init__"
        if len(chain) == 1 and symbol in facts[path].get("classes", ()):
            return f"{path}#{symbol}"
        again = facts[path].get("imports", {}).get(chain[0])     # a re-export: follow it into its module
        if not again or again == f"{mod}:{chain[0]}":
            return None
        mod, _, name = again.partition(":")
        chain, importer = ([name] if name else []) + chain[1:], path
    return None


def _tid(con, cache: dict, tok: str) -> int:
    if tok not in cache:
        row = con.execute("SELECT tid FROM tok WHERE tok=?", (tok,)).fetchone()
        if row is None:
            cur = con.execute("INSERT INTO tok(tok, kind) VALUES(?, ?)", (tok, tok.split(":", 1)[0]))
            cache[tok] = cur.lastrowid
        else:
            cache[tok] = row[0]
    return cache[tok]


def _link_file(con, lk: Linker, facts, f: str) -> None:
    data = lk.data(f)
    module = lk.primary[f]
    if data.get('language', 'python') != 'python':
        from .readers.link import link
        return link(con, lk, f, data)
    edges, sites, keys, posts, unres = [], [], [], [], []
    edges += [(alias, module, "alias", "resolved", f, 0) for alias, _ in lk.names[f][1:]]
    edges += [(module, f'unknown-import:{f}:{item["line"]}', 'imports-dynamic', 'unknown', f, item['line'])
              for item in data.get('unknown_dynamic_imports', [])]
    lines = data.get("import_lines", {})
    every_line = data.get("lines_all", {})
    optional = set(data.get("optional", []))
    # runtime imports (one edge per statement), then imports under `if TYPE_CHECKING:` (kind imports-typing)
    plan = [(imp, every_line.get(imp, [lines[imp]]), "") for imp in data.get("imports", []) if imp in lines]
    plan += [(imp, at, "imports-typing") for imp, at in sorted(data.get("typing", {}).items())]
    plan += [(imp, at, 'imports-lazy') for imp, at in sorted(data.get('import_reads', {}).items())]
    plan += [(imp, at, 'imports-dynamic') for imp, at in sorted(data.get('literal_dynamic_imports', {}).items())]
    for imp, at, kind_as in plan:                      # an imports entry without a line is an attribute read
        mod, _, name = imp.partition(":")
        target = lk.exact(mod, f, name)
        if kind_as == 'imports-lazy' and target is not None:
            declared = lk.data(target).get('lazy', {})
            if not declared or name != '*' and name not in declared:
                continue  # An ordinary attribute does not add another module import.
        dst, prov = None, "resolved"
        if target is None:
            parts = mod.split(".")                     # os.path: a submodule os.py binds at run time
            for cut in range(len(parts) - 1, 0, -1):
                head = lk.exact(".".join(parts[:cut]), f)
                if head and lk.data(head).get("submodules"):
                    target, mod = head, ".".join(parts[:cut])
                    break
        if target is None and mod in lk.namespaces:   # PEP 420: a directory without __init__.py
            if not name or name == "*":
                continue                               # `import tools.parity` binds a directory: nothing to link
            sub = lk.exact(f"{mod}.{name}", f)
            if sub:
                target, mod = sub, f"{mod}.{name}"
            else:
                dst = f"missing:{imp}"
        elif target is None:
            found = lk.by_suffix(mod, f, name if name and name != "*" else "")
            if found:                                  # no import root reaches it: a file of that dotted path
                target, prov, kind_as = found, "guessed", kind_as or "imports-unrooted"
            elif mod.split(".")[0] in lk.tops:
                dst = f"missing:{mod}"
        elif name and name != "*" and not (name.startswith("__") and name.endswith("__")):
            sub = lk.exact(f"{mod}.{name}", f)
            tdata = lk.data(target)
            lazy = tdata.get('lazy', {}).get(name)
            if lazy and (owner := lk.exact(lazy, f)):
                # The facade mapping is itself a dependency; only the named
                # export reaches its declared owner, not every sibling module.
                edges += [(module, lk.primary[target], kind_as or 'imports-lazy', 'resolved', f, line) for line in at]
                target, mod, kind_as = owner, lazy, kind_as or 'imports-lazy'
            elif sub:
                target, mod = sub, f"{mod}.{name}"
            elif not (name in tdata.get("bound", []) or name in tdata.get("lazy", {}) or tdata.get("getattr")
                      or tdata.get("star") or tdata.get("parse_error")):
                dst = f"missing:{imp}"
        if target is not None and dst is None:
            if name == '*' and kind_as == 'imports-lazy':
                # Reflection of an unknown name and __all__ can read any
                # declared export. These are potential static dependencies.
                for declared in sorted(set(lk.data(target).get('lazy', {}).values())):
                    if owner := lk.exact(declared, f):
                        edges += [(module, lk.primary[owner], 'imports-lazy', 'resolved', f, line) for line in at]
            if lk.mod_to_path.get(mod) == target:
                dst = mod
            elif mod not in lk.mod_to_path and mod != lk.primary[target] and target in lk.multi.get(mod, [lk.every.get(mod)]):
                dst = mod                              # an implicit second name a real import uses
                con.execute("INSERT OR IGNORE INTO node(id, file, module, qual, kind, sig, fp, build) VALUES(?,?,?,?,?,?,?,?)",
                            (mod, target, lk.primary[target], "", "alias", f"alias of {lk.primary[target]} (used by {f})",
                             "", 0))
                edges.append((mod, lk.primary[target], "alias", "resolved", f, 0))
            else:
                dst = lk.primary[target]               # an ambiguous name, as this importer means it
        if dst and dst.startswith("missing:"):
            con.execute("INSERT OR IGNORE INTO node(id, kind, sig, build) VALUES(?, 'missing', ?, 0)",
                        (dst, f"imported by {f}:{at[0]}"))
        if dst and dst != module:
            for line in at:                            # one edge per import statement
                kind = kind_as or ("imports-optional" if line in optional else "imports")
                edges.append((module, dst, kind, prov, f, line))
    for level, rmod, name, line in data.get("dirrel", []):   # `from . import X` that no package name anchors
        hit = lk.relative(f, level, rmod, name)
        if hit and hit[1] != module:
            edges.append((module, hit[1], "imports-optional" if line in optional else "imports", "resolved", f, line))
    ff = data.get("facts") or {}
    imports = ff.get("imports", {})
    scopes = [imports] + [fn.get("local_imports", {}) for fn in ff.get("functions", {}).values()]
    for table in scopes:                                   # names as the store knows them (primary module names),
        for local, target in list(table.items()):         # also for imports inside functions
            mod, sep, name = target.partition(":")
            path = lk.exact(mod, f, name) if mod in lk.multi else lk.mod_to_path.get(mod) or lk.every.get(mod)
            if path and lk.primary.get(path) != mod:
                table[local] = lk.primary[path] + sep + name
    own_rows = con.execute("SELECT qual, sig FROM node WHERE file=? AND kind='const' ORDER BY line", (f,)).fetchall()
    own = decide.own_env(own_rows)
    env = decide.module_env(own, imports, lk.own_env, lk.canon)
    bases = {q: decide.class_bases(sig) for q, sig in con.execute(
        "SELECT qual, sig FROM node WHERE file=? AND kind='class'", (f,))}
    resolved = {}
    for sym, fn in ff.get("functions", {}).items():
        src = f"{module}:{sym}"
        for call in fn.get("calls", []):
            target = _resolve_call(lk, facts, call, sym, f)
            if target:
                path, _, tsym = target.partition("#")
                dst = f"{lk.primary.get(path, path)}:{tsym}"
                resolved[(sym, call)] = dst
                if dst != src:
                    edges.append((src, dst, "calls", "resolved", f, fn.get("line", 0)))
            elif "." in call:
                last = call.rsplit(".", 1)[1]
                if len(last) >= GUESS_MIN and last not in fgs.COMMON:
                    unres.append((src, last, f))
                    cands = lk.short.get(last, set())
                    if len(cands) == 1 and (dst := next(iter(cands))) != src:
                        resolved[(sym, call)] = dst
                        edges.append((src, dst, "calls", "guessed", f, fn.get("line", 0)))
    for nid, qual, cls, rawb in con.execute(
            "SELECT nid, qual, cls, raw FROM node WHERE file=? AND kind IN ('function','method')", (f,)).fetchall():
        raw = unpack(rawb)
        src = f"{module}:{qual}"
        lex = raw.get("lex", {})

        def target_of(name):
            if (qual, name) in resolved:
                return resolved[(qual, name)]
            t = _resolve_call(lk, facts, name, qual, f)
            return f"{lk.primary.get(t.partition('#')[0], '?')}:{t.partition('#')[2]}" if t else None
        feeds = {t for name in raw.get("feeds", []) if (t := target_of(name)) and t != src}
        edges += [(src, t, "feeds", "resolved", f, 0) for t in sorted(feeds)]
        cbases = bases.get(cls, [])
        local = (ff.get("functions", {}).get(qual) or {}).get("local_imports") or {}
        fimports = {**imports, **local} if local else imports      # `from plat.runtime import MIN_PYTHON` inside
        fenv = decide.module_env(own, fimports, lk.own_env, lk.canon) if local else env
        cenv = decide.class_env(fenv, cls, cbases)
        own_names = set(own)
        rows = [decide.fold_site(s, cenv, lex, module, cls, fimports, own_names, lk.canon, cbases)
                for s in raw.get("sites", [])]
        env_names = sorted(t[4:] for t in decide.env_tokens(raw, cenv, lex))
        sigs_of = []
        for r, s in zip(rows, raw.get("sites", [])):
            if r["pred"] and (t := target_of(r["pred"])):
                r["pred"] = t
            r["env"] = s.get("env", 0)
            sigs = decide.site_signatures(r, cenv, lex, raw.get("subj", ()), env_names)
            sigs_of += sigs
            sites.append((src, r["line"], r["field"], r["op"], r["const"], r["value"], r["vkind"], r["identity"],
                          r["lead"], r["neg"], r["pred"], f, json.dumps(sigs)))
        for line,kind,text in raw.get('results',[]):
            if text.strip().casefold() in ('','pass','error','ok'):
                continue
            signature = 'sg:r:'+text
            sigs_of.append(signature)
        for name in raw.get("consts", []):
            if (ident := decide.identity(name, module, cls, fimports, own_names, {}, lk.canon, bases=cbases)) in lk.consts:
                edges.append((src, ident, "reads", "resolved", f, 0))
        toks = decide.env_tokens(raw, cenv, lex)
        if raw.get("cargs"):                           # calls into a getenv wrapper name their variables
            toks |= decide.wrapper_env(raw["cargs"], cenv, lex, lambda call: lk.envp(target_of(call)))
        toks |= set(sigs_of) | {f"sg:cfg:{k[1]}"[:200] for k in data.get("keys", []) if k[0] == "config" and k[3] == qual}
        for tok in toks:
            posts.append((_tid(con, lk.tids, tok), nid))
    for kind, value, line, qual in data.get("keys", []):
        node = f"{module}:{qual}" if qual and not qual.startswith("<") else module
        keys.append((node, kind, str(value)[:200], line, f))
    seen, unique = set(), []
    for e in edges:                                    # one edge per (src, dst, kind, provenance), first line kept;
        key = (e[0], e[1], e[2], e[3], e[5] if e[2].startswith("imports") else 0)   # one per import statement
        if key not in seen:
            seen.add(key)
            unique.append(e)
    con.executemany("INSERT INTO edge VALUES(?,?,?,?,?,?)", unique)
    con.executemany("INSERT INTO site VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", sites)
    con.executemany("INSERT INTO key VALUES(?,?,?,?,?)", keys)
    con.executemany("INSERT OR IGNORE INTO post VALUES(?,?)", posts)
    con.executemany("INSERT INTO unres VALUES(?,?,?)", unres)


def _record_delta(con, snapshot: dict, readers: dict, build_no: int, redo=()) -> None:
    """Delta rows of this build: removed, changed and added nodes of every file it re-read, including a
    new file, whose nodes are all `added` (design 3.7: new nodes are in the dirty set)."""
    files = {r[4] for r in snapshot.values()} | set(redo)
    now = {}
    if files:
        now = {r[0]: r for r in con.execute(
            f"SELECT id, fp, kind, shape, file, sig FROM node WHERE file IN ({','.join('?' * len(files))})", sorted(files))}
    rows, gone = [], []
    for i, r in snapshot.items():
        if r[2] in ("missing", "alias"):
            continue
        if i not in now and not con.execute("SELECT 1 FROM node WHERE id=?", (i,)).fetchone():
            rows.append((build_no, i, "removed", r[1], None, r[5], None, r[4]))
            if r[2] in ("function", "method", "test", "class", "const"):    # anchors and tests may move
                gone.append((i, r[1], r[2], r[3], r[4], r[5], build_no, json.dumps(sorted(readers.get(i, ())))))
        elif i in now and now[i][1] != r[1]:
            rows.append((build_no, i, "changed", r[1], now[i][1], r[5], now[i][5], r[4]))
    for i, r in now.items():
        if i not in snapshot and r[2] not in ("missing", "alias"):
            rows.append((build_no, i, "added", None, r[1], None, r[5], r[4]))
    con.executemany("INSERT INTO delta VALUES(?,?,?,?,?,?,?,?)", rows)
    con.executemany("INSERT INTO gone VALUES(?,?,?,?,?,?,?,?)", gone)
    con.execute("DELETE FROM gone WHERE id IN (SELECT id FROM node)")
    con.execute("DELETE FROM delta WHERE build < ?", (build_no - 20,))


def _capabilities(con, files):
    """Inventory semantics are explicit: parsing never promises foreign execution."""
    languages = {}
    stored = parts(con, ('language', 'parser'))
    for path, error in con.execute('SELECT path,parse_error FROM file'):
        language = stored['language'].get(path, 'python')
        from .readers.registry import query_support
        record = languages.setdefault(language, dict(files=0, parsed=0, errors=0, native_home=language == 'python',
                    queries=query_support(language),
                    parser=stored['parser'].get(path, {'engine':'stdlib ast'})))
        record['files'] += 1
        record['errors' if error else 'parsed'] += 1
    unsupported = [path for path in files if Path(path).suffix.lower() in OTHER_SOURCE]
    from .readers.registry import available
    from .readers.context import config_files
    return dict(languages=languages, available=available(), parser_inputs=config_files(files), unsupported_files=unsupported,
                meaning='static source facts; grammar parse is not execution or complete semantic resolution')
