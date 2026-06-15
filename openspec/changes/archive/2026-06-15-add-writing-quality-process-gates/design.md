## Overview

The change adds writing-quality evidence as a process surface. FlowGuard does
not become a thesis reviewer; it records which owner skill must provide current
evidence before a broad done/release/high-quality claim is allowed.

## Design

DevelopmentProcessFlow should treat the following as freshness-sensitive
artifacts when in scope:

- literature progression ledgers
- method depth ledgers
- figure/table argument ledgers
- AI-style density ledgers
- citation/footnote verification matrices
- installed skill prompt sync
- final prose changes after any of those reviews

Known bad states:

- `literature_progression_not_checked`
- `method_depth_not_defined`
- `figure_table_argument_not_checked`
- `ai_style_pass_skipped`
- `citation_audit_disposition_only`
- `final_text_changed_after_citation_audit`

## Risks

- FlowGuard wording must remain general, not thesis-specific enough to bloat
  every route.
- Owner skills must remain responsible for semantic checks.
