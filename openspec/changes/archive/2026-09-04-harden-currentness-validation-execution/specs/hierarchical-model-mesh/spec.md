## ADDED Requirements

### Requirement: Recursive subtree receipts are mandatory
Every non-leaf ModelMesh node SHALL consume one independently verified,
exact-current canonical subtree receipt. The receipt SHALL bind the node,
structural parent, direct-child set, partition fingerprint,
descendant-universe fingerprint, owner, subject, obligations, toolchain,
environment, and terminal result. Ordinary passed/current flags or string-only
child ids SHALL NOT close a non-leaf boundary.

#### Scenario: Non-leaf child is only locally green
- **WHEN** a parent names a child that declares descendants but receives only a
  local passed/current evidence row
- **THEN** the parent SHALL remain blocked
- **AND** the local result SHALL NOT be promoted to subtree coverage

#### Scenario: Five-level tree is composed bottom-up
- **WHEN** a five-level hierarchy has exact leaf receipts and every non-leaf
  consumes its verified child subtree receipt
- **THEN** the root MAY compose the tree in post-order
- **AND** every child producer, scope, obligation, and fingerprint remains
  visible in the root receipt

### Requirement: Finite leaf products have kernel-owned denominators
For full or broad claims the kernel SHALL derive the finite leaf Cartesian
product from fingerprinted input and state axes. Every recursive leaf node and
its terminal receipt SHALL carry those axes, the canonical cell set, and one
typed `ContractProductSignature`. Caller-supplied expected ids MAY be compared
but SHALL NOT define the denominator. A local group SHALL reject an axis from
another model, and a full-product claim SHALL identify one exact product
signature rather than a set of singleton groups.

#### Scenario: Caller supplies a smaller expected set
- **WHEN** supplied expected ids are fewer than the derived product
- **THEN** the leaf SHALL be incomplete with a denominator mismatch

#### Scenario: Cross-model interface product
- **WHEN** two different models must be composed
- **THEN** the composition SHALL use a typed parent-interface product and an
  explicit refinement contract rather than a model-local product
