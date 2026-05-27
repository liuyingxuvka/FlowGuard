## Context

FlowGuard now has a split between a compact core modeling API and many
satellite helpers for structure, evidence, model mesh, test mesh, UI, and
release confidence. The broad public facade in `flowguard.__init__` is
intentional compatibility surface, while `flowguard.__main__` still contains
one wrapper function per template command. The current shadow workspace also
contains a duplicate nested `.flowguard/existing_model_preflight` artifact that
is absent from the Git checkout.

Other agents may be editing adjacent FlowGuard proof and evidence modules in
the same Git checkout. This change therefore avoids the dirty files currently
owned by peer work and uses a narrow implementation surface.

## Goals / Non-Goals

**Goals:**

- Preserve all public import and CLI behavior while reducing repeated command
  registration code.
- Use FlowGuard Architecture Reduction to classify which simplification
  candidates are ready and which require StructureMesh or replay evidence.
- Use StructureMesh-style target ownership to keep the `flowguard.__init__`
  facade stable while internals can continue to simplify behind it.
- Clean duplicate shadow-only model artifacts during sync without deleting
  peer-created source or OpenSpec work.
- Verify real Git checkout, editable install, and shadow workspace behavior.

**Non-Goals:**

- Do not remove names from `flowguard.__all__` or shrink `API_SURFACE`.
- Do not split large helper modules such as `templates.py`,
  `ui_structure.py`, or `model_test_alignment.py` in this pass.
- Do not modify peer-owned proof/evidence files already dirty in the Git
  checkout.
- Do not publish, tag, or push unless a later release task explicitly does so.

## Decisions

1. Keep `flowguard.__init__` as the public facade.
   - Rationale: API surface tests intentionally assert a broad import facade.
   - Alternative considered: remove helper exports directly. Rejected because
     it is a breaking public API change, not a safe architecture reduction.

2. Consolidate template CLI wrapper registration through a command table.
   - Rationale: all template commands share the same parser shape and dispatch
     through `_run_file_template`; a table keeps command names visible while
     removing repeated functions.
   - Alternative considered: leave wrappers as-is. Rejected because this is a
     safe, focused contraction with straightforward parity tests.

3. Treat duplicate `.flowguard` model artifacts as sync cleanup, not product
   behavior.
   - Rationale: the nested shadow copy is not present in the Git checkout and
     has identical model hashes. Removing it during sync improves local
     structure without changing package behavior.
   - Alternative considered: add code to ignore nested artifacts. Rejected
     because the simpler fix is to keep the shadow workspace aligned.

4. Run broad checks in the background only after the code change is made.
   - Rationale: background progress is useful for time, but final confidence
     requires exit artifacts and result inspection.
   - Alternative considered: start full regression before edits. Rejected
     because later edits would stale the evidence.

## Risks / Trade-offs

- [Risk] CLI template command parity can drift when wrapper functions are
  removed. -> Mitigation: add focused tests for every template command,
  including stdout JSON and parser wiring.
- [Risk] Syncing from Git to shadow can delete peer work. -> Mitigation:
  synchronize only this change's touched files and the known duplicate artifact
  cleanup; do not bulk-delete unrelated OpenSpec/source paths.
- [Risk] Editable install can read the wrong workspace. -> Mitigation: run
  import/version checks from both the Git checkout and shadow workspace after
  `pip install -e`.
- [Risk] Full regression may overlap with peer changes. -> Mitigation: report
  final status and any failures with the current dirty tree rather than
  reverting peer edits.
