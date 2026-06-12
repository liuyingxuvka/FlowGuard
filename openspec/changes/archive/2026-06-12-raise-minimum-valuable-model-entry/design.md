## Context

FlowGuard currently has a compact model-first entry path and compact public
templates. That reduced prompt weight, but it also lets agents stop at models
that only cover a success path or a generic dedup example. The user-facing
failure is simple: the model runs but does not clearly prevent a real mistake.

There is also no lightweight experience loop for recurring risks. Similar work
on the same machine should reuse prior modeling patterns without requiring a
project-level template system, database, or service. The portable target is:
packaged public templates for everyone, plus a local per-machine template
library that any installed FlowGuard copy can use.

## Goals / Non-Goals

**Goals:**

- Make the default model-first AI entry a minimum valuable model, not a thin
  happy-path starter.
- Require every default model creation/deepening flow to name the protected
  error class and include modeled state, side effects, completion evidence, and
  a known-bad case.
- Add a standard-library-only risk template library with two default layers:
  packaged public templates and per-machine local templates.
- Use portable per-user storage, with environment-variable override, instead of
  hard-coded machine paths.
- Search templates before model creation and harvest local candidate templates
  after successful reusable modeling work.
- Keep project-level template libraries out of the default scope.
- Export helpers and CLI commands through route-scoped API groups.
- Update templates, docs, installed skill material, tests, local install, and
  shadow workspace copies.

**Non-Goals:**

- Do not add a network service, vector database, or external dependency.
- Do not store production code or project-private payloads in the local template
  library by default.
- Do not make every project carry a template library.
- Do not claim a harvested candidate is a trusted public template until it is
  reviewed and packaged in a later release.
- Do not force direct `Explorer(...)` users into the orchestration helper; the
  structured fields and audit warnings support but do not replace direct use.

## Decisions

1. **Rename the default mental model to minimum valuable model.**
   The skill kernel and docs should stop teaching "thin default path" as the
   default. The replacement is still compact, but it must have teeth: a real
   protected error class, model-critical state, side effects, completion
   evidence, and one known-bad case.

2. **Use two template layers by default.**
   Public templates live in the package and work on any computer after install.
   Local templates live under a platform-appropriate per-user data root. The
   default root is computed at runtime and can be overridden with
   `FLOWGUARD_TEMPLATE_LIBRARY_ROOT`.

3. **Keep local templates as small risk cards.**
   A `RiskTemplate` records id, title, summary, workflow families,
   protected error classes, required state, required side effects, required
   evidence, known-bad cases, merge keys, source, status, and metadata. It does
   not store whole project models or source code.

4. **Make pre-search and post-harvest explicit.**
   `search_risk_templates(...)` searches public and local templates. A
   `TemplateReuseReview` records matches and whether a no-match reason is
   acceptable. `harvest_risk_template_candidate(...)` writes a candidate JSON
   card only when the model has enough reusable structure.

5. **Put structured fields where agents already declare risk.**
   `RiskIntent` gains optional fields for `protected_error_classes`,
   `must_model_side_effects`, `completion_evidence`, `known_bad_cases`,
   `used_template_ids`, and `template_no_match_reason`. `FlowGuardCheckPlan`
   gains optional `template_reuse_review` and `minimum_model_contract` fields.

6. **Audit gaps remain warning-oriented unless the model is structurally
   unusable.**
   The audit should report `missing_protected_error_class`,
   `missing_completion_evidence`, `missing_known_bad_case`,
   `missing_template_reuse_review`, and `success_path_only_model` as confidence
   gaps. It should not break existing direct models solely because they do not
   opt into the helper path.

7. **Model similarity gets reusable-risk ids.**
   `ModelSignature` should carry template ids, known-bad case ids, evidence gate
   ids, and maturity level so similar model families can reveal missing depth.

## Risks / Trade-offs

- [Risk] The entry becomes heavy again. -> Mitigation: keep the public starter
  compact and move long explanations to docs/full templates; the required
  fields are short lists.
- [Risk] Local harvested templates may contain project-specific details. ->
  Mitigation: save candidates with abstract fields only and mark them
  `candidate` until reviewed.
- [Risk] Agents skip search because the local library is empty. -> Mitigation:
  packaged public templates always exist, and no-match must be recorded when no
  template applies.
- [Risk] Template matching overfits by name. -> Mitigation: match by protected
  error class, workflow family, state/evidence terms, and explicit merge keys.
- [Risk] Public API grows too broad. -> Mitigation: add a route-scoped
  `risk_template_library` group and starter subset; keep helpers out of
  `CORE_API`.

## Migration Plan

1. Create OpenSpec requirements and a FlowGuard self-model for the new entry and
   template library behavior.
2. Add `flowguard.risk_templates` with public built-ins, portable local root
   discovery, load/search/review/merge/harvest/write helpers.
3. Extend `RiskIntent`, `FlowGuardCheckPlan`, audit, runner, and summary
   sections.
4. Upgrade default templates, risk-intent templates, CLI commands, API exports,
   and model-similarity signatures.
5. Update skill guidance, docs, API docs, README, and adoption snippets.
6. Run focused tests, template smoke tests, OpenSpec strict validation,
   FlowGuard model checks, broad tests as practical, local editable install
   verification, installed skill sync, shadow workspace sync, project audit, and
   adoption logging.

## Open Questions

- Public/template promotion policy is out of scope for this change. Local
  candidates are harvested now; promotion to packaged public templates remains
  a future reviewed release workflow.
