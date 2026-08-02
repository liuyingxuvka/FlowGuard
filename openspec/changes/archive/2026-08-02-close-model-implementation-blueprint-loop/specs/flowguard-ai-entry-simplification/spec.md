## ADDED Requirements

### Requirement: Whole-software blueprint work is task-triggered rather than a selectable depth mode
The AI entry path SHALL derive a whole-software blueprint obligation only from explicit blueprint, export, reconstruction-qualification, or owner-declared release facts. It SHALL NOT add a user-selectable `DNA` or reconstruction depth, and ordinary work SHALL continue loading only the smallest affected current owner closure.

#### Scenario: User asks for an ordinary bounded code change
- **WHEN** no whole-software blueprint or reconstruction claim is requested or required
- **THEN** the entry path does not scan, export, or reconstruct the complete software

#### Scenario: User asks for a complete portable software blueprint
- **WHEN** the request explicitly claims or exports a whole-software blueprint
- **THEN** the entry path triggers the existing inventory, alignment, mesh, portable, and process owners and preserves their independent results
