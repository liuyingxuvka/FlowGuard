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
  `$executeRaw`/`$executeRawUnsafe` SQL text is read by `readers/sql.py:statements`.
- `assignments[].form`: `member` (`obj.f = ...`), `pair`, `declarator`, `class-field` or `identifier`.

## Schema files

`.prisma` (`readers/prisma.py`) and `.sql` (`readers/sql.py`) are read by FlowGuard's own text
readers: no grammar package. Nodes are `model`/`enum` (Prisma) and `table` (SQL CREATE TABLE);
keys `model`, `table`, `column`; the `schema` fact holds models with fields (`column` from
`@map`, table from `@@map`, `relation` from `@relation(fields, references)`) or tables, ALTER
ADD/DROP COLUMN and DROP TABLE changes. Schema files have no code, so code queries over them are
complete and empty. `MapHandle.writes()` binds write paths to models at query time (accessor
`centralEmployee` -> model `CentralEmployee`, relation -> model, `connect` -> the foreign-key
fields on whichever side `@relation(fields: [...])` names); `schema_gaps()` compares descriptions.
