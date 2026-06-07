## 1. Specification And Model Scope

- [x] 1.1 Validate the OpenSpec change artifacts.
- [x] 1.2 Update the default replacement field-lifecycle FlowGuard model with the minimal route-ref gate.

## 2. Core Implementation

- [x] 2.1 Add route-ref classification helpers and broad-claim detection to `flowguard/field_lifecycle.py`.
- [x] 2.2 Add field lifecycle findings for missing gate, negative test, and replay evidence route refs.
- [x] 2.3 Keep bounded field-lifecycle plans backward compatible.

## 3. Templates, Docs, And Skill Guidance

- [x] 3.1 Update the FieldLifecycleMesh public template to show `gate:`, `test:`, and `replay:` refs.
- [x] 3.2 Update FieldLifecycleMesh, Model-Test Alignment, Runtime Gateway, Closure Contract, AGENTS snippet, and API docs.
- [x] 3.3 Update the installed `flowguard-field-lifecycle-mesh` Codex skill guidance.

## 4. Verification And Sync

- [x] 4.1 Add focused field lifecycle and public template tests.
- [x] 4.2 Run focused tests, OpenSpec strict validation, project audit, and relevant FlowGuard checks.
- [x] 4.3 Run aggregate FlowGuard model regression and full unit regression, using background execution for long checks where useful.
- [x] 4.4 Sync editable local install and verify import path/version/helper availability.
- [x] 4.5 Sync the shadow workspace without deleting peer-only files and verify the shadow import path/version/helper availability.
- [x] 4.6 Record FlowGuard adoption evidence and KB postflight.
