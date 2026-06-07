## ADDED Requirements

### Requirement: Visual handoff preserves calm text hierarchy
The UI Text Hierarchy Blueprint SHALL include handoff guidance that distinguishes
semantic text roles from final visual text treatments so downstream design does
not turn every semantic hierarchy level into a separate visual font size.

#### Scenario: Semantic roles share visual treatment when their jobs are similar
- **WHEN** a text hierarchy blueprint contains labels, helper text, status text,
  panel headings, or body text with similar local importance
- **THEN** the handoff guidance tells downstream design to consider reusing a
  visual text treatment instead of creating one visual size per semantic role

#### Scenario: Visual differences need a meaning or attention role
- **WHEN** a text treatment is visually different from nearby text through size,
  weight, color role, spacing, or placement
- **THEN** the handoff guidance records or requests the reason for the
  difference, such as primary focus, region scanning, local control, warning,
  helper text, quiet metadata, or brand expression

### Requirement: Typography noise is reported as a design smell
The UI Text Hierarchy Blueprint SHALL allow agents to report excessive one-off
text treatments as a design smell without treating the smell as a universal
hard failure or fixed font-size budget.

#### Scenario: One-off text treatments are flagged softly
- **WHEN** nearby text elements with similar jobs use unrelated visual
  treatments without a clear rationale
- **THEN** the review reports a typography hierarchy smell and recommends
  consolidation, reuse, grouping, spacing, weight, color role, or placement
  before adding another visual text style

#### Scenario: Intentional expressive exceptions are preserved
- **WHEN** a broader text treatment range is used for a hero, editorial,
  marketing, brand-heavy, warning, or state-critical purpose
- **THEN** the review preserves the exception when its attention or meaning role
  is explicit
