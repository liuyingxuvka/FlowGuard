## MODIFIED Requirements

### Requirement: Code contraction candidates
FlowGuard SHALL represent model-backed code contraction opportunities as
structured candidates with candidate type, target code node, source model
element, rationale, affected public entrypoints, affected state, affected side
effects, proof status, required next route, and current lifecycle disposition.

#### Scenario: Safe candidate is reported with proof status
- **WHEN** a handler, module, branch, adapter, or state field has a declared
  reduction candidate with behavior-preserving evidence and no completed
  implementation evidence
- **THEN** the review reports the candidate with a proof status and the next
  route needed before code changes

#### Scenario: Risky candidate is kept visible
- **WHEN** a candidate appears duplicate but lacks enough equivalence, facade,
  conformance, or ownership evidence
- **THEN** the review marks it as risky or blocked instead of treating it as
  safe to remove

#### Scenario: Completed candidate leaves active queue
- **WHEN** a declared reduction candidate has matching implementation evidence
  and current validation evidence
- **THEN** the review MUST NOT report that candidate as active ready work and
  MUST keep completion visible as evidence or historical context
