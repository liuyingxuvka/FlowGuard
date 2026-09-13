## Purpose

This capability gives FlowGuard a verifiable boundary between a bounded retry
cycle for one objective and a genuinely new reviewed piece of work. It lets a
new objective proceed without allowing output paths, timestamps, or caller
invented hashes to reset an old cycle.

## ADDED Requirements

### Requirement: Objective identity is derived from reviewed artifacts

FlowGuard SHALL accept an explicit completion-objective change name and derive
one content-addressed objective fingerprint from that named, current,
unarchived OpenSpec change's planning artifacts. The resolver SHALL reject an
unknown change, an empty change, an unsafe path, a symlink/reparse-point
artifact, an unreadable artifact, or a change with incomplete required
planning artifacts. The caller SHALL NOT supply the objective fingerprint
directly.

#### Scenario: Valid reviewed objective

- **WHEN** the caller names a current OpenSpec change whose proposal, design,
  specifications, and change metadata are readable regular files under the
  repository's OpenSpec changes directory
- **THEN** FlowGuard derives one stable objective fingerprint from those
  artifact identities and binds it to the completion plan

#### Scenario: Unsafe or incomplete objective

- **WHEN** the caller names an unknown, archived-only, symlinked, outside-root,
  unreadable, or artifact-incomplete change
- **THEN** FlowGuard returns a typed blocked result before readiness admission
  or producer reservation and does not create a receipt or run directory

### Requirement: Distinct objectives have independent finite cycles

FlowGuard SHALL keep the existing maximum of one initial producer attempt and
one typed repair for each objective. A distinct, independently fingerprinted
objective SHALL receive a distinct cycle identity while leaving every old
objective ledger and reservation immutable. A changed source, output path,
receipt store, owner disposition, or timestamp SHALL NOT count as a distinct
objective.

#### Scenario: Same objective is attempted a third time

- **WHEN** the named objective has already consumed its initial attempt and its
  one typed repair
- **THEN** FlowGuard blocks the request with the existing finite-cycle error
  and does not regain budget from any path or disposition change

#### Scenario: New objective after an exhausted old objective

- **WHEN** a different reviewed OpenSpec objective has a different derived
  fingerprint and the old objective has an exhausted cycle
- **THEN** FlowGuard creates a new unclaimed cycle identity for the new
  objective without changing or deleting the old ledger

### Requirement: Readiness and full execution share objective identity

The canonical readiness route and formal full-validation route SHALL derive and
validate the same explicit objective fingerprint. A readiness artifact from one
objective SHALL NOT admit a full run for another objective, and omitting the
explicit objective on either side SHALL preserve the deterministic legacy
default rather than silently adopting the other side's objective.

#### Scenario: Readiness and full use the same objective

- **WHEN** both routes name the same current OpenSpec objective and freeze the
  same remaining inputs
- **THEN** their completion epoch identities match before any producer starts

#### Scenario: Readiness and full use different objectives

- **WHEN** the readiness artifact and full command name different objectives
- **THEN** full admission blocks with an objective/epoch identity mismatch and
  does not reserve an attempt
