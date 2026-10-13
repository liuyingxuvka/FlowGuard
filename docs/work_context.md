# Provider-neutral WorkContext

`WorkContext` is FlowGuard's read-only boundary for external requirements,
plans, designs, tasks, status, and other planning inputs. OpenSpec, Spec Kit,
Superpowers, custom skills, and declared files are peer sources. No provider is
the default, and none decides what FlowGuard itself checks.

Each context preserves:

- a stable context id, adapter id, native work id, and native owner;
- a project-bounded context root;
- generic artifact roles such as `scope`, `requirement`, `acceptance`,
  `design`, `plan`, `task`, `status`, and `history`;
- the native artifact id, source reference, byte size, and SHA-256 content
  fingerprint;
- the normative, observed, or experimental subject lane;
- optional behavior-source ids (`behavior_source_surface_ids`) used by the
  coverage inventory.

The common layer never writes provider files, executes provider commands,
starts provider sessions, owns provider checks, caches provider status, or
turns provider completion into model/test evidence. Unknown adapters, paths
outside the project, missing required roles, stale fingerprints, and metadata
that claims provider execution rights block the context
(`review_work_context()` reports finding codes such as
`work_context_adapter_unregistered`, `work_context_required_role_missing`,
`work_context_artifact_source_changed`, `work_context_fingerprint_stale`, and
`work_context_provider_authority_forbidden`).

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
become intended current behavior. If a current artifact should change what a
model expects, a person or agent edits the model (and its tests) explicitly,
then runs the model and tests to show the new behavior holds; the WorkContext
itself only records which bytes were read.

## API and template

Read one native work item, or discover all active ones for an adapter:

```python
from flowguard import read_work_context, discover_work_contexts, review_work_context

context = read_work_context(".", "<change-id>", adapter_id="openspec")
review = review_work_context(context)
print(review.ok, review.finding_codes)

contexts = discover_work_contexts(".", adapter_id="openspec")
```

Print a starter model for this capability (add `--write <dir>` to write the
files):

```text
python -m flowguard template work-context
```

`read_project_work_contexts()` reads all declared sources, validates their
exact identities and fingerprints, and returns one declaration fingerprint.
An empty source set is valid when the project selected no external planning
provider; an explicitly required source that discovers no work is blocked.
