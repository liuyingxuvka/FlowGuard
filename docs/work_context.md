# Provider-neutral WorkContext

`WorkContext` is FlowGuard's read-only boundary for external requirements,
plans, designs, tasks, status, and other planning inputs. OpenSpec, Spec Kit,
Superpowers, custom skills, and declared files are peer sources. No provider is
the default or the authority for FlowGuard itself.

Each context preserves:

- a stable context id, adapter id, native work id, and native owner;
- a project-bounded context root;
- generic artifact roles such as `scope`, `requirement`, `acceptance`,
  `design`, `plan`, `task`, `status`, and `history`;
- the native artifact id, source reference, byte size, and SHA-256 content
  fingerprint;
- the normative, observed, or experimental subject lane;
- optional behavior-source ids used by the exact coverage inventory.

The common layer never writes provider files, executes provider commands,
starts provider sessions, owns provider checks, caches provider status, or
turns provider completion into model/test evidence. Unknown adapters, paths
outside the project, missing required roles, stale fingerprints, and
provider-authority metadata block the context.

## Declaring project sources

Sources are declared in `.flowguard/project.toml`:

```toml
[[work_context.sources]]
source_id = "current-requirements"
adapter_id = "declared-files"
native_work_id = "current-requirements"
native_owner_id = "project-requirements"
context_root = "openspec/specs"
required = true
required_artifact_roles = ["requirement"]

[[work_context.sources.artifacts]]
artifact_id = "requirement:work-context"
artifact_role = "requirement"
path = "work-context/spec.md"
```

The built-in `openspec` adapter can read one named active change or discover
active changes. The built-in `declared-files` adapter can represent Spec Kit,
Superpowers, custom skill output, ordinary repository documents, or any other
explicit bounded file set without embedding provider logic in the core.

`declared_files_source_profile()` supplies bounded source shapes for `spark`,
`openspark`, and `changelog`. These are still ordinary declared files, not
provider execution bridges. A changelog row is `history`; it does not silently
become intended current behavior. Only an explicit, content-addressed
`WorkContextIntentMapping` can project one current artifact into a
`ModelIntentContribution`. ModelRevisionSet then accepts, defers, rejects, or
supersedes that contribution inside the same model lineage; unresolved or
conflicting effects block acceptance.

## Commands

Read one native work item:

```text
python -m flowguard work-context --root . --adapter openspec --work-id <change-id> --json
```

Generate a project-local executable example:

```text
python -m flowguard work-context-template --destination .
```

`read_project_work_contexts()` reads all declared sources, validates their
exact identities and fingerprints, and returns one declaration fingerprint.
An empty source set is valid when the project selected no external planning
provider; an explicitly required source that discovers no work is blocked.
