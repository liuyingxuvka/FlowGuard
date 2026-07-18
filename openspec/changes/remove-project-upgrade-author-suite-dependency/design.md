## Context

`project-upgrade` currently calls the author suite validator with
`Path(__file__).resolve().parents[1]` as its repository root. That path is the
FlowGuard checkout during an editable install, but it is `site-packages` after
a normal installation. The author-only
`.skillguard/flowguard-suite/suite-map.json` is intentionally absent from the
package, so the same command that appeared green in the checkout fails with
`suite_map_missing` before writing in an ordinary project.

FlowGuard already creates a clean consumer projection with generated
`consumer-release.json` identities and an installer ownership manifest. The
missing link is a package-owned, immutable description of the exact clean
projection that can be loaded from both editable and non-editable installs.

## Goals / Non-Goals

**Goals:**

- Make project audit and writing upgrade validate the global consumer
  distribution without consulting an author checkout or target-local suite.
- Bind the installed package, its packaged consumer-suite authority, and the
  global 15-skill projection by exact member and raw-file hashes.
- Fail before project mutation when the packaged authority is absent, invalid,
  or differs from the global projection.
- Prove the path through a real non-editable package installation and empty
  ordinary project.

**Non-Goals:**

- Installing or repairing the global skill suite during project adoption.
- Copying skills, suite maps, or author controls into an ordinary project.
- Retaining an editable-checkout fallback, legacy suite-map reader, alias, or
  dual authority.
- Changing FlowPilot or Khaos project files in this change.

## Decisions

### Package one deterministic clean-consumer authority

FlowGuard will generate and track one package data file containing the exact
15 member ids and every clean consumer file fingerprint, including generated
per-member release manifests. The authority contains no author repository path,
SkillGuard contract, receipt, or `.skillguard` material.

The author suite map remains the maintainer-side source used to compile this
artifact. Runtime project adoption never reads that map. A deterministic
maintainer command supports write and check modes so skill-source changes
cannot silently leave package authority stale.

This is preferred over deriving authority solely from the installed ownership
manifest because a self-consistent but stale or rewritten installation would
otherwise have no package-side comparison point.

### Validate the global projection directly

A package runtime validator will load only the packaged authority, inventory
the resolved `$CODEX_HOME/skills` consumer root, and require exact raw parity.
It will also require the installer ownership manifest to name the same members
and fingerprints, reject author-control residue, and reject unregistered
FlowGuard-reserved skill ids while allowing unrelated co-located skills.

`project_adoption._load_suite_evidence()` will consume this validator. Missing
or invalid package authority is a visible blocker; it never falls through to
the author suite validator or a target-local path.

### Keep source and installation gates connected

The FlowGuard skill installer and currentness checker will compare their
generated clean source projection with the packaged authority before
installation or parity claims. This gives the release process one exact chain:

`author source → packaged consumer authority → global consumer projection`.

### Exercise the deployment topology

The regression will build and install FlowGuard non-editably into an isolated
site directory, install the exact 15-skill consumer projection into an
isolated `CODEX_HOME`, and run the CLI from an empty project without the source
checkout on `sys.path`. Success requires current AGENTS/project records,
post-write audit pass, and zero project-local suite, suite-map, or author
control residue.

## Risks / Trade-offs

- **[Compiled authority becomes stale after a skill edit]** → installer,
  authority-check, focused tests, and the final distribution gate all reject
  the mismatch until the deterministic compiler is run.
- **[Non-editable subprocess regression adds test time]** → keep one
  deployment-topology test and use focused in-process tests for individual
  mismatch cases.
- **[Unrelated skills share the global root]** → inventory only the authority's
  declared members, report unrelated ids separately, and still reject every
  undeclared FlowGuard-reserved id.
- **[Project adoption is asked to repair a bad global install]** → remain
  blocked with exact findings; installation repair stays with the distribution
  owner and is not added as a fallback side effect.

## Migration Plan

1. Compile the package-owned authority from the current 15-skill author source.
2. Install FlowGuard 0.58.3 and activate the matching global consumer
   projection transactionally.
3. Verify package authority, source projection, and installed projection exact
   parity.
4. Retry ordinary-project `project-upgrade`; no target migration or suite-map
   creation is needed.
5. If any post-activation check fails, restore the previous package/global
   installation pair; do not make the target project accept the old authority.
