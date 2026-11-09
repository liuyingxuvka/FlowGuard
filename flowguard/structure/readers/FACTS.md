# File-local facts consumed by the existing Map store

Reader signature: `extract(root: Path, rel: str, data: bytes, module: str, is_test: bool) -> dict`.
Use `.common.blank(module,data,language)`, parse/text/walk/position/fingerprint helpers.
No reader imports or executes the project. All values are JSON serializable.

- `nodes`: old Map node fields `qual,kind(function/method/class/const/interface/enum/namespace/struct),cls,line,end,sig,doc,fp,shape(list[int]),size,raw(optional dict)`; add `column,end_column`. `raw.declared_qual` retains the logical name before an overload suffix. Overloads must have distinct qual (e.g. signature/line suffix); do not collapse partial declarations.
- `syntax_calls`: `node` full `module:qual` (module for top-level), `file,line,column,end_line,end_column,text` callee spelling, `resolved` nullable; `reason` for uncertainty; `candidate` lexical name, `scope` enclosing qual, `parameters` enclosing arg names if relevant. Dot/member/dynamic/macro calls are not resolved merely by same suffix. Keep actual calls including unknowns.
- `dependencies`: `module` source spelling, `name` imported symbol or empty, `alias` local binding or empty, `kind` (`import`, `include`, `using`, `reexport`, `dynamic`), `line,column`, `scope` (empty top-level), `relative` bool; `reason` for nonliteral/unknown. Source declarations remain separate from resolved project targets. Store owner links these once using actual mapped files/config.
- `assignments`: existing fixed-query shape: `node,file,line,target,field,value,literal`; add position, `operation` write/update. Unknown RHS is `literal=False,value=None`, never a made-up value.
- `symbol_reads`: `node,file,line,column,text,kind='read',resolved=None`; deterministic fields/keys also `keys` entries `(kind,value,line,qual)` where kind `field`/`config`/`constant` etc. Dynamic bracket names keep an unknown read, not a definite field.
- Declaration positions use one-based Unicode character columns (helper converts UTF-8 bytes), end is exclusive. Parser errors stay explicit; partial facts never mean complete semantics. Grammar modules load lazily in common.parser; versions in `parser` metadata participate in invalidation.

Python reader and home/API remain unchanged. Foreign facts feed the same file/node/edge/key tables and MapHandle queries; native foreign execution/home/liveness is not implied by a grammar parse. All unsupported semantics remain unknown.

## Query coverage

`MapHandle.query_coverage()` reports only queries used on that handle. Fixed queries
`handlers/literal_sets/assignments/calls/imports/tests` are tracked; `calls(include_reads=True)`
also tracks `symbol_reads`. `functions()` delegates to tracked `nodes()`, while `node(id)`
and `nodes(file=...)` scope parsing coverage to their actual file. `keys()` is tracked too.
All queries accept an optional `language='python'` where absence claims intentionally
cover only Python. Unsupported source files and parse failures remain issues when their
source scope was queried. Normal Python behavior rules are not globally blocked.

The initial foreign readers implement nodes/functions, explicit call sites, dependency
declarations, assignments (including unknown values) and definite keys. C, C++ and C# do not
implement handler analysis; no foreign reader implements literal-set queries, native test
discovery or full symbol-read coverage; available definite member reads are returned, but
`include_reads=True` does not claim a complete symbol-read set. The matrix is public in `capabilities()['languages']` and
`['available']`. The structure engine consumes coverage issues as grey for that declaration;
an empty unavailable result is not evidence of no violations. This is static syntax
coverage, not a promise of full compiler semantics or runtime execution.


## C++ reference initialization

The C++ reader decodes a known grammar ambiguity in reference direct-initializers
only when the original parenthesized expression and semicolon are independently
parsed completely from the same parser-input ranges after the existing BOM/newline
normalization. It does not rewrite the initialization syntax.
`parser.syntax_recovery` describes this support and `syntax_recoveries` records
the actual declaration locations. Calls, writes and owners retain the existing normalized-input location convention;
no nested function is invented for the variable. Uncovered errors, including
expression forms outside the grammar's support, remain parse errors and make the
queried source scope incomplete. For a valid but ambiguous reference declarator, known
lexical value/type bindings distinguish an initializer from a function declaration.
An unresolved binding remains in `binding_unknowns`; the existing query coverage
reports it as a declaration-binding issue, separately from syntax errors. Both
`binding_unknowns` and `syntax_recoveries` survive the existing file-fact store.
This is finite source coverage, not full type or execution proof.


## TS/JS facts beyond the first readers (round 20)

- `nodes[].shape`: every named function or method (declaration, method, or a function/arrow bound
  by `const f = ...` or `export default`) gets the Python map's sketch: sorted 3-gram hashes of
  its body's node kinds in depth-first order, nested function and class bodies excluded,
  operators kept, comments dropped, the smallest 64 kept (`analysis.kinds_shape`). Only anonymous
  functions (`<anonymous@line,column>`: callbacks, object/class-field arrows) have an empty shape;
  size never excludes a function. TS and Python shapes use different node kinds and are not compared.
- `handlers`: one row per `catch` clause, in the Python row shape (`node,file,line,kind='catch',
  type,name,raises,reraise,non_raising,body`) plus `propagates`, `hands_on`, `function` and `key`.
  A catch is handed on (`non_raising=False`) when every path ends in `throw`, `return
  Promise.reject(...)`, or a call that receives the caught identifier unchanged as its first
  argument: `next(err)`, `reject(err)`, a parameter of an enclosing function (`callback(err)`), or
  a name listed in `[tool.flowguard] propagate`. A path that finishes or leaves otherwise
  (swallowed, logged, a default returned) is a fallback. `type` is the catch parameter's spelling,
  or `any` without one; `function` is the nearest named function (anonymous callbacks and `@line`
  suffixes drop out); `key` is `file:function:type`, the ledger key form.
- `literals`: string literals in `===/!==/==/!=` (not against `typeof`), `case`, returned values
  (through `?:`, `??`, `||`, `&&`, parentheses, `as`), union type members, `new Set([...])`,
  array elements and `.includes()/.has()` arguments, each with `context`. Object keys, arguments
  of `console.*`/`logger.*` calls, `new *Error(...)` and `throw` are never recorded.
- `writes`: Prisma client calls `<client>.<accessor>.<create|createMany|update|updateMany|upsert|
  delete|deleteMany|...AndReturn>(...)` as syntax paths `[field, op, field, ..., field|op]` from
  `data`, `upsert` `create`/`update`, nested operations and `connect*`/`disconnect`/`set`;
  `where`, `select`, `include`, `orderBy` never contribute. A local `const x = {...}` (block
  scoped, with later `x.f = ...`), `cond && {...}`, `cond ? {...} : {...}` and `rows.map(r => ({...}))`
  are followed; other spreads and values are `leaf='spread'|'opaque'` with a reason.
  `$executeRaw`/`$executeRawUnsafe` SQL text is read by `readers/sql.py:statements`. A `delete`/`deleteMany`
  inside a loop of its function (a for/while/do body, a `.forEach`/`.map` callback) carries `loop: true`. A
  written value keeps `values` for a literal, each branch of `c ? a : b` and the fallback of `x ?? 'v'`; when only
  that fallback is spelled the row also carries `partial: true`.
- `assignments[].form`: `member` (`obj.f = ...`), `pair`, `declarator`, `class-field` or `identifier`.

## Schema files

`.prisma` (`readers/prisma.py`) and `.sql` (`readers/sql.py`) are read by FlowGuard's own text
readers: no grammar package. Nodes are `model`/`enum` (Prisma) and `table` (SQL CREATE TABLE);
keys `model`, `table`, `column`; the `schema` fact holds models with fields (`column` from
`@map`, table from `@@map`, `relation` from `@relation(fields, references)`) or tables, ALTER
ADD/DROP/RENAME COLUMN, ALTER ... RENAME TO (`rename`, SQLite's table rebuild) and DROP TABLE changes, and
the lines of CREATE TABLE statements whose table or columns are not spelled (`unread`: `AS SELECT`, a
name built at run time). Schema files have no code, so code queries over them are
complete and empty. `MapHandle.writes()` binds write paths to models at query time (accessor
`centralEmployee` -> model `CentralEmployee`, relation -> model, `connect` -> the foreign-key
fields on whichever side `@relation(fields: [...])` names); `schema_gaps()` compares each live description
once with the schema it describes (`archived()` files under `docs/` by default, `[tool.flowguard] archives`,
describe nothing).

## Python writes and literals

- `writes` (Python): SQL `INSERT`/`UPDATE`/`DELETE` statements in a function's string literals, read by
  `readers/sql.py:statements` (also the written tables and columns of `analysis.sql_names`), recorded for
  that function (`<module>` outside functions) with `values` for the columns a statement spells as a
  literal. `MapHandle.writes()` adds attribute assignments (bound to a class, or `how='name'` with
  `by_name=True`); a row carries `value` when the written literal is spelled. Test files contribute none.
- `literals` (Python): strings in `==`/`!=`/`is` comparisons (compare), the containers of `in` tests
  (member), `case` patterns (case), returned values through `?:`/and/or and lambda bodies (return), set
  literals and `set()`/`frozenset()` arguments (set) and `Literal[...]` members (union). Dict keys,
  `'key' in mapping`, logging/print calls, exception constructors and `raise` are never recorded; test
  files contribute none. `literal_groups()` groups Python and TS/JS rows together.
- Owner comments: `# flowguard: owner NAME` on a function is a sensor with `owner=True`; `owner T.c
  writers=... with=M.f[=v] alone=f(why)` (and `// flowguard: owner ...` in TS/JS) is an anchor of kind `owner` with `writers`, `pairs`, `alone`.
- `assignments` (Python): a computed right side keeps `expr`; `MapHandle.assignments()`/`writes()` fold it with the
  decision sites' constant folding (enum members, module and imported constants, each branch of `?:`) into `values`.
  `row['k'] = v` has `form='key'` and the field `receiver.k`; a class-body default is `module:Class.name`.
- `field_types` (Python): `name: Type` in a class body, with the annotated class id (an enum is a declared value
  set) and `optional`. TS/TSX `literals` in a union carry the `declaration` (type alias) name; Python `X = Literal[...]` too.

## Facts for the static checks (round 20, stage 7b)

- `writes[].values` / `writes[].refs` (TS/JS): the literals a Prisma `data` field writes (each branch of `c ? a : b`)
  and `Name.KEY` spellings of a member; `MapHandle.writes()` reads a `Name.KEY` from a `{KEY: 'v'} as const` object
  of that name and keeps no `values` when a spelling does not resolve.
- `queries` (TS/JS): Prisma reads (`count`, `findMany`, `findFirst`, `findUnique`, `aggregate`, `groupBy`, ...) with
  `keys` (fields their `where` filters on, through AND/OR/NOT, arrays, spreads and one local const), `loads`
  (relations `include`/`select` load) and `counts` (relations `_count` counts, `*` for all).
- `value_sets` (TS/JS, module level): `[...] as const` (`const-array`), `{K: 'v'} as const` (`const-object`, with
  `members`), `new Set([...])` (`set`), closed string unions (`union`) and aliases `(typeof X)[number]`,
  `(typeof X)[keyof typeof X]` or a plain type name (`alias`, with `of`); `exported` says whether it is exported.
- `typed_fields` (TS/JS): interface, class and object-type members annotated with a union or an alias, as
  `container`, `field`, `optional`; `typed_writes`: the literal values a class field initializer, `this.f = ...`
  in a class, or an object written as `const x: T = {...}`, `{...} satisfies T`, `{...} as T` give a member.
- `numbers` (TS/JS): number literals in `===`/`<`/`>=`/... comparisons and `case` labels, in the literal row shape.
- `nodes[].raw.holder` (TS/JS methods): the class or `const x = {...}` object a method belongs to; calls are
  resolved by name through it, inside the caller's package (nearest `package.json`; `MapHandle.call_index()`).
- Prisma fields carry `on_delete` (from `@relation(..., onDelete: X)`); SQL tables and ALTER changes carry `checks`
  (`CHECK (col IN ('a', ...))` with string values, also inside `EXEC(N'...')`).
