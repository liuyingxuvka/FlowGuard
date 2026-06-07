## Overview

Add a dependency-free contract checker that validates Guard-family closure JSON. The checker is intentionally a skill asset rather than a new reasoning engine.

## Design

- Closure reports must include owner, artifact kind, closure status, findings, missing inputs, stale evidence, skipped checks, next actions, safe claim, and unsafe claim boundary.
- `passed` reports cannot contain hard findings, missing inputs, stale evidence, or skipped checks.
- Non-pass reports should expose next actions so FlowGuard can route maintenance instead of guessing.

## FlowGuard Use

The kernel records child reports as evidence surfaces. Partial, blocked, downgraded, stale, or skipped child reports become maintenance obligations owned by the appropriate downstream route.

## Risks

- The checker does not replace domain-specific Guard validation.
- It only enforces the closure report shape and obvious unsafe pass claims.
