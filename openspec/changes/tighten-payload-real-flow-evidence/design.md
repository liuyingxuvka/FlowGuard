## Context

The previous validation-gate change correctly introduced
`ArtifactPayloadContract`, `ArtifactPayloadCase`, and `ArtifactPayloadEvidence`.
Its intent was representative payload validation: a synthetic payload is a
controlled test input for a real payload-bearing function. Current wording and
tests do not enforce that distinction strongly enough.

## Goals / Non-Goals

**Goals:**

- Keep Model-Test Alignment as the semantic owner for artifact payload
  validation.
- Require current external payload evidence to identify concrete execution
  proof before it can support green confidence.
- Teach agents that synthetic files and work packages are inputs for real
  import/export/upload/download/save/load/generate/consume surfaces.
- Keep installed Codex skills synchronized with repository guidance.

**Non-Goals:**

- Do not add a new satellite skill.
- Do not build parsers for every payload format.
- Do not require manual review when automated proof covers the boundary.
- Do not claim exhaustive security validation from representative packs.

## Decisions

1. **Use a proof gate on `ArtifactPayloadEvidence`.**
   Payload evidence already carries `evidence_ref` and `proof_artifact`. Add a
   review-time blocker when a current external passing row lacks both. This is
   smaller and clearer than adding a new route or a broad data model.

2. **Keep manual and automated proof rules aligned.**
   Manual payload evidence already needs structured observation plus
   `evidence_ref` or `proof_artifact`. Automated, browser, desktop, and replay
   payload evidence should also point to a concrete result, command, screenshot,
   replay output, or proof artifact when supporting broad confidence.

3. **Use wording as a safety boundary.**
   Replace "fake file/work-package pack" wording with "synthetic payload cases
   for the real payload surface" everywhere agents read first: `SKILL.md`,
   protocol references, templates, docs, and tests.

4. **Sync as part of done.**
   This project has a local source repository, a Gate/shadow workspace, and
   installed Codex skills. Broad confidence requires all three surfaces to carry
   the same prompt and helper behavior.

## Risks / Trade-offs

- [Risk] Existing examples without evidence refs will fail. -> Mitigation:
  update examples and tests with explicit proof references.
- [Risk] The proof gate becomes too ceremonial. -> Mitigation: accept either a
  lightweight evidence ref or a full `ProofArtifactRef`; do not require manual
  checks when automation already proves the surface.
- [Risk] Source and Gate workspaces drift. -> Mitigation: verify hashes or
  focused imports/tests in both workspaces after sync.

## Migration Plan

1. Add OpenSpec specs for the tightened evidence boundary.
2. Add the payload execution-proof blocker and tests.
3. Update docs, templates, skill prompts, and prompt coverage tests.
4. Bump local package metadata and refresh project adoption records.
5. Sync the local source repository, Gate workspace, and installed Codex skills.
6. Run focused and broad validation, then record FlowGuard/KB postflight.
