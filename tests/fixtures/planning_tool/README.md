# Planning Tool fragments (TS/Prisma/SQL map facts)

Fragments copied from the working tree of the owner's Planning Tool project (at
HEAD `eaef893`) for `tests/structure/test_ts_prisma_facts.py`. Only the needed line ranges were copied;
each fragment starts with a comment naming its source file and line range. Lines ending in
`fixture wrapper` were added so a fragment parses on its own (an enclosing function or object);
every other line is verbatim. The `.txt` suffix keeps the fragments out of FlowGuard's own map;
the tests write them into an isolated project without it.

| Fixture | Source lines | Used for |
|---|---|---|
| `backend/src/services/employee.service.ts.txt` | 251-276, 344-354, 1470-1506, 1925-1953, 2105-2186 | Prisma `create`/`update`/`updateMany`, nested `roles: { create }`, conditional spreads, `const centralData`, `nameFields.x = ...`, catch clauses that rethrow |
| `backend/src/services/employee-transfer.service.ts.txt` | 562-577, 827-852 | `markCentralState`: `organizationalUnitId` only in `where` (not a write); `data` shorthand from a local const |
| `backend/src/services/sync.service.ts.txt` | 555-667 | central and local writes in `$transaction` callbacks, `deleteMany`, catch clauses that return a default (fallbacks) |
| `backend/tests/integration/org-structure.routes.test.ts.txt` | 182-212 | `createMany` with a data array |
| `backend/src/api/routes/absence.routes.ts.txt` | 89-99 | `catch (error) { next(error); }`: handed on, not a fallback |
| `backend/src/services/authority/organization-navigation.ts.txt` | 1-58 | backend label `'My Organization'` (union type, returns) |
| `frontend/src/utils/organization-navigation.ts.txt` | 1-29 | frontend label `'My organization'` (union type, `new Set([...])`) |
| `backend/src/services/utilization/utilization-calculation.ts.txt` | 22-38 | `countWorkingDays` (shape owner) |
| `backend/src/services/org-unit-summary.service.ts.txt` | 191-203 | `countWorkingDaysLocal` (same body) |
| `backend/prisma/schema.prisma.txt` | 17-20, 71-171, 176-223, 253-277, 1305-1324, 1361-1376 | Employee, UserRole, EmployeeTransfer, AuthorityAssignment, AuditEvent, Notification (`@map`, `@@map`, `@relation`) |
| `backend/prisma/central/schema.prisma.txt` | 15-18, 30-50, 64-88, 94-114 | CentralOrgUnit, CentralEmployee, CentralLendingAssignment |
| `backend/prisma/central/init-azure-sql.sql.txt` | 1-54, 80-108 | T-SQL brackets; "Matches the Prisma central schema exactly", yet 7 columns and one table are missing |
| `backend/prisma/central/migrations/*/migration.sql.txt` | baseline 34-49, personnel_lifecycle 1-14, personnel_source_contract 1-7 | `CREATE TABLE` then `ALTER TABLE ... ADD [col]` (also inside `EXEC(N'...')`) applied in folder order |

`synthetic/prisma-relations.ts.txt` is **not** copied: Planning Tool has no Prisma `connect`,
`connectOrCreate`, `disconnect` or `$executeRaw` write, so those calls are written against the copied
schema models only and are marked synthetic in the file.
