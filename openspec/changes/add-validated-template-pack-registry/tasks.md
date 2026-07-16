## 1. Executable Model

- [x] 1.1 Add an isolated, change-scoped FlowGuard model for manifest validation, zero/one/many selection, composition conflicts, instantiation, and receipt freshness.
- [x] 1.2 Run the correct workflow and broken manifest, selection, parameter, and freshness variants; inspect every counterexample.

## 2. Registry Implementation

- [x] 2.1 Implement canonical manifest, entry, predicate, validation, sealing, and JSON identity behavior in `flowguard/template_packs.py`.
- [x] 2.2 Implement explicit base/no-match, one-match, and composable-many selection with field-owner conflict detection.
- [x] 2.3 Implement strict parameter rendering, immutable selection/instance receipts, and current-versus-stale receipt validation.

## 3. Focused Test Mesh

- [x] 3.1 Add manifest and bounded-predicate good/bad cases in one dedicated new test module.
- [x] 3.2 Add the complete zero/one/many/base/composability/field-owner decision matrix.
- [x] 3.3 Add deterministic identity, blocked instantiation, tamper, and stale manifest/context/parameter/output cases.

## 4. Verification

- [x] 4.1 Add a focused verification contract whose inputs are limited to this change's artifacts, model, module, and dedicated tests.
- [x] 4.2 Run OpenSpec validation, the executable FlowGuard model, the dedicated test module, and final isolated boundary checks.

## 5. Owner Handoff

- [x] 5.1 Launcher owner: consume the stable registry API through a separate coordinated integration change; intentionally do not modify CLI or public facade here.

## 6. SkillGuard-Neutral Projection

- [x] 6.1 Register every current FlowGuard file-template factory and built-in trusted risk template behind an exact target-owned template route and one validated base.
- [x] 6.2 Emit a strict unsealed central catalog and complete applicability inventory with current native manifest, file-content, factory, and validator identities.
- [x] 6.3 Cover base, exact domain route, unknown route, invalid request fingerprint, and candidate-inventory parity in focused tests.
- [x] 6.4 Cross-validate all 36 projected templates with the current SkillGuard compiler and selector without moving FlowGuard semantic ownership.
