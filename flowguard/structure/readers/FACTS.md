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
declarations, assignments (including unknown values) and definite keys. They do not yet
implement handler analysis, literal-set queries, native test discovery or full symbol-read
coverage; available definite member reads are returned, but `include_reads=True` does not
claim a complete symbol-read set. The matrix is public in `capabilities()['languages']` and
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
