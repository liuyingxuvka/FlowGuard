"""Link file facts once into the existing graph; uncertain dispatch is an explicit edge."""
from pathlib import PurePosixPath
import posixpath
from .context import typescript_paths


def link(con, lk, file, data):
    from ..store import _tid
    from ..query import tokens
    module = lk.primary[file]
    files = set(lk.primary)
    rows = con.execute('SELECT id,qual,kind,raw FROM node WHERE file=?', (file,)).fetchall()
    from ..store import unpack
    declarations = [(ident, qual, kind, unpack(raw)) for ident, qual, kind, raw in rows]
    edges = []

    def resolve_module(spelling, importer, kind):
        bases = []
        if spelling.startswith('.') or kind == 'include':
            bases.append(posixpath.normpath(posixpath.join(posixpath.dirname(importer), spelling)))
            if kind == 'include':
                bases.append(posixpath.normpath(spelling))
        else:
            aliases, reason = typescript_paths(lk.root, importer)
            for pattern, base, target in aliases:
                before, star, after = pattern.partition('*')
                if spelling == pattern or star and spelling.startswith(before) and spelling.endswith(after):
                    middle = spelling[len(before):len(spelling)-len(after) if after else None] if star else ''
                    bases.append(posixpath.normpath(posixpath.join(base, target.replace('*', middle))))
        hits = set()
        for base in bases:
            if base.startswith('../') or base == '..':
                continue
            options = [base, *(base + ext for ext in ('.ts','.tsx','.js','.jsx','.mts','.cts','.mjs','.cjs')),
                       *(posixpath.join(base,'index'+ext) for ext in ('.ts','.tsx','.js','.jsx'))]
            if base.endswith(('.js','.jsx')):
                stem = base.rsplit('.',1)[0]
                options += [stem+'.ts', stem+'.tsx']
            hits.update(path for path in options if path in files)
        return next(iter(hits)) if len(hits) == 1 else None

    def exported(path, name, seen=frozenset()):
        if (path,name) in seen:
            return None
        facts = lk.data(path)
        value = facts.get('exports', {}).get(name)
        if isinstance(value, dict):
            target = resolve_module(value['module'],path,'reexport')
            return exported(target,value['name'],seen | {(path,name)}) if target else None
        if isinstance(value, str):
            target = lk.primary[path]+':'+value
            if any(row.get('binding_mutation') and row['target']==value for row in facts.get('assignments',[])):
                return None
            declaration = con.execute('SELECT kind,raw FROM node WHERE id=?',(target,)).fetchone()
            if declaration:
                declared = unpack(declaration[1]).get('declared_qual',value)
                candidates = [qual for qual,raw in con.execute(
                    "SELECT qual,raw FROM node WHERE file=? AND kind IN ('function','method')",(path,))
                    if unpack(raw).get('declared_qual',qual) == declared]
                if declaration[0] in ('function','method') and len(candidates) != 1:
                    return None
                return target
            for binding in facts.get('bindings',[]):
                if binding.get('alias') == value:
                    source = resolve_module(binding['module'],path,'import')
                    return exported(source,binding['name'],seen | {(path,name)}) if source else None
        matches = []
        for item in facts.get('dependencies',[]):
            if item['kind'] == 'reexport' and item.get('name') == '*':
                source = resolve_module(item['module'],path,'reexport')
                if source and (result := exported(source,name,seen | {(path,name)})):
                    matches.append(result)
        return matches[0] if len(set(matches)) == 1 else None

    imports = {}
    for item in data.get('dependencies', []):
        if 'source_reason' not in item:
            item['source_reason'] = item.get('reason', '')
        item['reason'] = item['source_reason']
        item['resolved'] = None
        target = resolve_module(item['module'],file,item['kind']) if item['module'] and not item.get('reason') else None
        if target:
            item['resolved'] = lk.primary[target]
            dst, prov = lk.primary[target], 'resolved'
            if item.get('alias') and item['kind'] == 'import':
                imports[item['alias']] = (target,item.get('name',''))
        else:
            dst, prov = f'unknown-import:{file}:{item["line"]}:{item.get("column",1)}', 'unknown'
            if not item.get('reason'):
                item['reason'] = 'literal dependency is external, ambiguous or outside mapped roots'
        edges.append((module,dst,'imports-'+item['kind'],prov,file,item['line']))
    for call in data.get('syntax_calls', []):
        if 'source_reason' not in call:
            call['source_reason'] = call.get('reason', '')
        call['reason'] = call['source_reason']
        target = None
        name, scope = call.get('candidate',call['text']), call.get('scope','')
        if data.get('parse_error'):
            call['reason']='file has syntax errors; binding is only a partial syntax candidate'
        namespace = call.get('namespace_candidate', [])
        if len(namespace) == 2 and namespace[0] in imports and imports[namespace[0]][1] == '*' and namespace[0] not in call.get('parameters',[]) and namespace[0] not in call.get('shadows',[]) and not data.get('parse_error'):
            target = exported(imports[namespace[0]][0],namespace[1])
        if not call.get('reason'):
            if name in imports:
                target_file, imported = imports[name]
                target = exported(target_file,imported)
            else:
                levels = scope.split('.') if scope else []
                while True:
                    expected = '.'.join([*levels,name])
                    matches = [ident for ident,qual,kind,raw in declarations
                               if raw.get('declared_qual',qual) == expected and kind in ('function','method')
                               and (data['language'] not in ('javascript','typescript','tsx') or kind != 'method')]
                    if len(matches)==1:
                        target=matches[0];break
                    if matches or not levels:
                        break
                    levels.pop()
        if target and not con.execute("SELECT 1 FROM node WHERE id=? AND kind IN ('function','method')",(target,)).fetchone():
            target = None
        if target and any(row.get('binding_mutation') and row['target'] == name for row in data.get('assignments',[])):
            target=None
            call['reason']='callee binding may be reassigned by source code'
        call['resolved'] = target
        if target:
            call['reason']=''
            prov, dst = 'resolved', target
        else:
            prov, dst = 'unknown', f'unknown-call:{file}:{call["line"]}:{call.get("column",1)}'
            if not call.get('reason'):
                call['reason'] = 'callee has no unique lexical/source binding in the mapped project'
        edges.append((call['node'],dst,'calls',prov,file,call['line']))
    con.executemany('INSERT INTO edge VALUES(?,?,?,?,?,?)',edges)
    con.executemany('INSERT INTO key VALUES(?,?,?,?,?)',
                    [(module+(':'+qual if qual else ''),kind,value,line,file)
                     for kind,value,line,qual in data.get('keys',[])])
    for ident,qual,kind,raw in declarations:
        for token in tokens(qual):
            con.execute('INSERT OR IGNORE INTO post VALUES(?,(SELECT nid FROM node WHERE id=?))',(_tid(con,lk.tids,token),ident))
    from ..store import save_facts
    save_facts(con, file, data)
