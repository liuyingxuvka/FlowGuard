## ADDED Requirements

### Requirement: Finite growth enters normal task understanding
Normal task production SHALL preserve explicitly declared finite software path changes and independently observed current path states through original references. Public read SHALL consume those references without executing a producer, scanning a repository or mutating authority. Unobserved scope SHALL remain explicit.

#### Scenario: A path is added, deleted or renamed
- **WHEN** a task declares a finite path change
- **THEN** its original request and real present, missing or unavailable observations remain bound to the task and current accepted identity, with any missing model binding and next owner visible.

#### Scenario: No change was observed
- **WHEN** a task has no declared observed changes
- **THEN** the result retains NOT_OBSERVED rather than inferring growth coverage from selected model paths.

#### Scenario: Growth evidence is stale or foreign
- **WHEN** the task, head, source, path scope or original evidence hash does not match
- **THEN** the read rejects the evidence and cannot close the task from it.

### Requirement: Insufficient tasks publish authentic diagnostics
A task with insufficient functional evidence SHALL expose its original terminal reason, first missing input and next responsible owner through independently authenticated receipt-free diagnostic references. Such a diagnostic SHALL remain needs_evidence and SHALL NOT grant verified task closure.

#### Scenario: Preflight or maturation is insufficient
- **WHEN** production cannot establish current functional sufficiency
- **THEN** public read preserves the original failure or gap and next action without fabricating a successful receipt.

#### Scenario: A caller forges a completed diagnostic
- **WHEN** diagnostic fields, raw reports, current identities or a claimed next owner do not match original evidence
- **THEN** the reader rejects that claim.

### Requirement: Current action detail and unknown coverage are readable
A compact understanding result SHALL expose proven current state, required targets, precise gaps, compromises, unknown scope and original action detail references. An action location SHALL be bound to actual current code, contract, scope and retained obligations. Empty evidence SHALL NOT imply whole-software optimality.

#### Scenario: An authentic action target is available
- **WHEN** current accepted detail contains a real action target
- **THEN** strict resolution returns its actual path and symbol and rejects wrong-hash, foreign or stale references.

#### Scenario: No current action pointer exists
- **WHEN** an independently authenticated current projection contains zero selected pointers
- **THEN** the availability result is not_applicable, actual task closure is not claimed, and a request for a missing location remains needs_evidence.

### Requirement: Bounded reads share current evidence without weakening checks
One ordinary read invocation SHALL share authenticated original inputs and complete typed current state, consume required selected native proof and perform a fresh end guard. Separate invocations SHALL independently establish currentness. Bounded pages SHALL retain exact size limits and lossless reassembly.

#### Scenario: A selected task reads a shared input repeatedly
- **WHEN** multiple validators need the same input inside one invocation
- **THEN** they use the same verified initial bytes while a separate ending read still detects drift.

#### Scenario: An unselected native leaf is stale
- **WHEN** an ordinary task has sufficient current selected leaves but an unrelated leaf is stale
- **THEN** selected sufficiency does not become a global currentness claim, and complete validation still rejects the stale complete-set claim.
