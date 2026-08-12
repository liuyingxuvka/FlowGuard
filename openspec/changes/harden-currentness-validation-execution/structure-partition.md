# StructureMesh Partition

The current `structure_refactor_mesh` model derives three child boundaries
from the currentness failure set. They are not arbitrary line-count splits.

| Parent facade | Child owner | Owns | Must not own |
|---|---|---|---|
| `flowguard.ui_structure` | `flowguard.ui_implementation_evidence` | complete/scoped runnable-claim admission, omitted-evidence classification, content-plan/current-revision admission | interaction graph types, journeys, visible-surface discovery |
| `flowguard.validation_ownership` and `flowguard.evidence_receipts` | `flowguard.process_supervision` | child process containment, timeout/cancel/interrupt termination, descendant-zero terminal facts | receipt semantics, owner DAG identity, claim scope |
| `flowguard.__init__` | `flowguard.api_registry` | ordered public-name projection, duplicate and missing-name findings | importing domain modules, route judgment, domain defaults |

Public imports remain on the existing facades. Child modules do not import the
package facade, and `api_registry` contains no domain imports. Timeout/default
values remain declared by their existing command/owner contracts; extraction
does not create a second configuration owner.

Required parity:

- old public symbols and `__all__` order are exact;
- complete/scoped UI good and bad cases are unchanged except for the newly
  required explicit scope;
- process terminal status, lease settlement, and receipt publication gates
  stay owned by their original modules;
- no facade imports a child that imports the facade back;
- no fallback module, alias API, or alternate success route is introduced.
