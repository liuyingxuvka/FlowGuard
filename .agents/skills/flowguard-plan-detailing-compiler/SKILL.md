---
name: flowguard-plan-detailing-compiler
description: Use only when explicitly requested or delegated by flowguard-development-process-flow's plan_detailing mode to compile a rough non-trivial plan into structured FlowGuard artifacts, steps, receipts, validations, failure/rework branches, and claim boundaries.
---

# FlowGuard Plan Detailing Compiler

## Purpose
Turn rough plan prose into checkable `PlanDetail` rows before execution; never execute the plan or treat detail as implementation proof.

## Entrypoint Scope
Delegated FlowGuard mode skill; route `plan_detailing_compiler`, role `delegated_mode`, native owner `development_process_flow`. Generic work enters `flowguard-development-process-flow` first.

## Local Material Routing
Read `references/plan_detailing_compiler_protocol.md` for required rows, finding codes, projection order, and confidence decisions.

## Entrypoint Acceptance Map
Accept an explicit/delegated rough plan and sources; compile scope/state/artifact/receipt/validation rows; block missing rework, payload/UI, or final evidence detail; return structured projections to DevelopmentProcessFlow and typed satellites.

## Use When
- Use for delegated `plan_detailing` where scope, steps, artifacts, side effects, UI actions, real payload surfaces, validation, or rework are underspecified.

## Do Not Use When
- Do not activate as a generic planner, execute work, or replace downstream route evidence; return unclear FlowGuard routing to `model-first-function-flow`.

## Required Workflow
1. Capture goal, assumptions, sources, risk surfaces, state/side effects, artifacts, UI actions, and payload/work-package surfaces.
2. Keep AI steps in `agent_operation`; record sibling-plane targets separately, then add ordered steps, step receipts, validations, failure/rework/continue gates, freshness rules, and questions; run `review_plan_detail()`.
3. Project passing/scoped rows to process, agent workflow, UI, Model-Test Alignment, and TestMesh owners.

## Hard Gates
- Verify the real FlowGuard check engine and AGENTS.md managed record; never create a fake mini-framework.
- Long prose, checkboxes, or plan progress cannot satisfy structured detail or terminal evidence.
- Full claims require resolved questions, final evidence ids, payload cases for the real surface, human-operability gates, and template harvest closure.
- Projection preserves receipts and target references: AgentWorkflow owns AI-operation order, DevelopmentProcessFlow owns lifecycle freshness, and neither absorbs product-runtime behavior.

## Output Requirements
- Return evidence, failures, blockers, skipped_checks, residual_risk, claim_boundary, typed_next_actions, `PlanDetail` rows, gaps, and projections.

## SkillGuard Maintenance
- Edit contract source, regenerate; SkillGuard cannot execute or create receipts.
