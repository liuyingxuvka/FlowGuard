## Purpose

Keep the package-owned FlowGuard consumer authority tied to the exact package
release so installation and downstream project checks cannot accept stale
version metadata as current.

## ADDED Requirements

### Requirement: Packaged authority carries the package release identity

Every published FlowGuard package MUST contain one readable consumer-suite
authority whose release version exactly equals the package's own version. The
authority MUST continue to describe the same clean, author-free consumer file
projection and MUST be the only normal runtime authority for that projection.

#### Scenario: Current package and authority agree

- **WHEN** a package is installed and its consumer-suite authority is loaded
- **THEN** the authority version equals the installed package version
- **AND** the authority remains valid for the exact declared member and file
  projection

#### Scenario: Stale authority is present

- **WHEN** the package version differs from the authority version
- **THEN** package currentness and consumer installation checks fail visibly
- **AND** they identify both versions without accepting the package as current

#### Scenario: Non-editable package is inspected

- **WHEN** FlowGuard is installed without its source checkout
- **THEN** the package-owned authority is readable from package data
- **AND** its version equality is checked without importing an author-side path

