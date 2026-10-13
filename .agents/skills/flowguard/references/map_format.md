# `.flowguard/map.json` format (schema `flowguard.map.v1`)

```json
{
  "schema": "flowguard.map.v1",
  "project": "shop",
  "layers": ["ui", "api", "domain", "infra"],
  "ignore": ["docs/**", "scripts/**"],
  "test_command": "python -m pytest -q",
  "components": [
    {
      "id": "orders",
      "layer": "domain",
      "summary": "Places orders and charges the customer.",
      "responsibilities": ["place an order", "charge the customer once per order id"],
      "files": ["shop/orders/*.py"],
      "entrypoints": ["shop/orders/service.py:OrderService.place"],
      "state": ["orders table"],
      "side_effects": ["charges the card through the payment gateway"],
      "depends_on": ["storage", "payments"],
      "tests": ["tests/test_orders*.py"],
      "models": [".flowguard/models/order_placement.py"],
      "status": "confirmed",
      "fingerprint": "sha256:..."
    }
  ],
  "flows": [
    {"id": "checkout", "summary": "cart to paid order", "steps": ["api:checkout", "orders:place", "payments:charge"],
     "model": ".flowguard/models/order_placement.py"}
  ],
  "accepted_debts": [
    {"code": "dependency_cycle", "component": "orders", "contains": "payments", "reason": "split planned"}
  ]
}
```

| field | meaning | who writes it |
| --- | --- | --- |
| `layers` | allowed dependency direction, top to bottom; a component may import its own or lower layers | human/AI |
| `ignore` | globs excluded from the inventory (in addition to `.flowguard/**`, `.git/**`, build dirs) | human/AI |
| `test_command` | how to run tests; `impact` appends the selected test files | human/AI |
| `id` | lowercase `[a-z0-9][a-z0-9_.-]*`, unique | human/AI |
| `files` | globs (`*` = one directory level, `**` = any depth); every non-test source file must match exactly one component | human/AI |
| `entrypoints` | `path:Symbol` or `path:Class.method`; must exist (`check`) | human/AI |
| `depends_on` | components it imports; must equal the real import graph (`check`); `deps --write` fills it | tool, then reviewed |
| `tests` | test files/globs that exercise the component; must match something (`check`) | human/AI |
| `models` | contract model files (`.flowguard/models/<id>.py`) or model runners (`.../run_checks.py`) protecting the component; must exist (`check`) | human/AI |
| `status` | `draft` or `confirmed` | `confirm` |
| `_hint` | facts written by `scan` to help describe a draft (file count, public symbols, discovered entrypoints and effects); `confirm` deletes it | `scan` |
| `fingerprint` | hash of the component's files at the last `confirm`; mismatch = STALE | `confirm` only |
| `flows[].steps` | `component` or `component:Symbol`; symbols must exist in that component (`check`) | human/AI |

Tests are files whose name starts with `test_`, ends with `_test.py`, contains `.test.`/`.spec.`,
or that live in a `tests/`, `test/` or `__tests__/` directory. Tests are not owned by components;
they are linked through `tests`.

`.flowguard/cache/` holds parse and model-result caches. It is never committed and can be deleted at any time.
