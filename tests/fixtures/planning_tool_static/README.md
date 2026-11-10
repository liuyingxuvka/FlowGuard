# Planning Tool fragments for `check --static` (round 20, stage 7b)

Copied from the Planning Tool working copy (the owner's repository, through the scratch copy used for the
round-20 survey; no Git command ran there). Each fragment starts with a comment naming its source file and line
range; lines ending in `fixture wrapper` were added so the fragment parses on its own. The `.txt` suffix keeps
the fragments out of FlowGuard's own map; `tests/intent_engine/test_static_check.py` writes them, together
with `tests/fixtures/planning_tool`, into an isolated project under their real names.

| Fixture | Source lines | Used for |
|---|---|---|
| `backend/src/services/authority/authority-integrity-repair.service.ts.txt` | 376-396 | `auditEvent.create` with `severity: 'WARN'` |
| `backend/prisma/migrations/20260910120000_align_runtime_storage_contract/migration.sql.txt` | 558-568 | `ALTER TABLE dbo.audit_events WITH CHECK ADD CONSTRAINT ... CHECK (severity IN (N'INFO', ...))` |
