# UI Observed Surface Protocol

Use this protocol whenever a UI exists, has been migrated, or can run. The observed real surface is the first hard gate before broad UI modeling or completion claims.

## Inventory

Record each visible button, icon button, menu item, input, picker, dropdown, tab, toggle, table, displayed field, status/helper/placeholder text, dialog, toolbar, panel, and region with stable id, kind, label/text, enabled state, region, revision, and evidence reference.

Use `UIObservedSurfaceInventory`, `UIObservedSurfaceItem`, and `review_ui_observed_surface_inventory(...)` when available. Map every item to a `UIControl`, `UIDisplayElement`, or `UIVisibleSurfaceItem`, or create a blindspot with owner, reason, validation boundary, and rationale.

## Visible surface review

Use `UIVisibleSurface`, `UIVisibleSurfaceItem`, and `review_ui_visible_surface(...)` to bind helper copy, status, placeholders, metadata, and disabled reasons to the state/region/control/display that owns their user-facing purpose.

Block or scope when:

- the model lists intended controls but never counts the real page/window;
- a visible or enabled actionable item has no mapping;
- label similarity is treated as behavior evidence;
- a blindspot lacks owner, reason, validation boundary, or rationale;
- a disabled control is visible without a reason a user can understand;
- implementation terms such as debug route, hydration, backend, mock, or dataset id leak without user value;
- placeholders or containers are treated as completed capability proof;
- helper/status messages compete or repeat without rationale.

## Handoff

Send mapped controls/displays to the interaction model, capability owners to capability coverage, actionable blindspots to implementation evidence, and visible text ownership to the journey/structure/text protocol. Inventory completeness proves surface accounting only, not functional behavior or runnable completion.
