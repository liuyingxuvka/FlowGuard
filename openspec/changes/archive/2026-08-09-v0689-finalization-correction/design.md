## Context

The repository already has a canonical content-addressed directory projection
and a separate single-file portable envelope. The v0.68.9 audit found that the
directory is the correct DNA boundary, while the envelope expands all shards
into one JSON value and repeats shared member and binding data. The project
record was also newer than its adoption metadata, and the observed model
inventory changed without a fresh accepted revision set.

## Goals / Non-Goals

**Goals:**

- Make directory export and verification the direct, bounded path.
- Keep parent/child model relations, code contracts, tests, oracles, and
  execution statuses addressable without copying the whole graph.
- Repair the model authority pointer using the existing revision and owner
  evidence pipeline.
- Remove or contract only paths with current contract proof, and make prompt
  expansion conditional on exact triggers.
- Finish with one clean install projection and one foreground final validation
  for the unchanged `v0.68.9` release identity.

**Non-Goals:**

- No independent reconstruction tool or routine rebuild of FlowGuard.
- No new compatibility reader, alias, fallback authority, or second DNA format.
- No claim that static DNA verification executes or reconstructs a target.
- No version bump beyond `0.68.9`.

## Decisions

1. **Reuse the existing canonical projection.** Add directory-first helpers and
   CLI routing around `serialize_canonical_blueprint_projection`,
   `write_canonical_blueprint_projection`, and
   `load_canonical_blueprint_projection` instead of inventing another model
   schema. This keeps model authority, portable exchange, and release evidence
   separate.

2. **Stream or reference large payloads.** The directory writer remains the
   only full materialization step. Portable summaries reference shard paths,
   member counts, and fingerprints; the optional bundle is retained for an
   explicit request and is never loaded during ordinary directory checks.

3. **Use one authority repair.** Build the live snapshot candidate, execute the
   five required owner routes under their native owners, build one
   `ModelRevisionSet`, and activate it atomically. The project pointer is
   updated only after the accepted revision and activation receipt exist.

4. **Use affected-only validation before release validation.** Prompt,
   portable, alignment, reduction, and affected model checks run once after
   implementation settles. A single foreground parent then owns the release
   validation; child results remain independently typed and cannot be promoted
   by a static wrapper.

5. **Prefer contraction over deletion only with proof.** Route candidates
   through ArchitectureReduction and StructureMesh. Keep unresolved candidates
   visible, remove proven duplicate wrappers, and do not replace uncertainty
   with aliases or fallback paths.

## Risks / Trade-offs

- **[Risk]** Directory-first APIs could accidentally become a second authority.
  **Mitigation:** require the exact canonical projection fingerprint and source
  blueprint identity on every directory result; no independent pointer is
  written.
- **[Risk]** Deduplicating payloads could change fingerprints. **Mitigation:**
  preserve canonical member and shard identities, add tests for round-trip
  equality, and change the bundle schema only through explicit derived
  transport metadata.
- **[Risk]** A required native owner may fail or time out. **Mitigation:** keep
  the owner `not_run`/blocked, do not relabel it, and stop release closure
  until a fresh terminal receipt exists.
- **[Risk]** Parallel agents may touch nearby files. **Mitigation:** inspect
  status before every write, edit only owned paths, and never reset or clean
  unrelated work.

## Migration Plan

1. Add the OpenSpec change and focused directory-first tests.
2. Implement the smallest direct path and update the model revision evidence.
3. Run affected checks and refresh the installed projection.
4. Run one frozen foreground release parent and inspect every child disposition.
5. Commit and push the corrective commit while retaining the `v0.68.9` tag and
   release identity.
