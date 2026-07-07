## Design

FlowGuard readiness is modeled as:

`Behavior model -> route-specific Mermaid snapshot -> executable check -> downstream installed-skill regression`

The kernel skill owns the general model-first language. Satellite skills may add diagrams, but they must not flatten LogicGuard, SourceGuard, TraceGuard, or WorldGuard models into a generic flowchart.

SkillGuard integration remains a boundary check only. The contract text declares that duplicate SkillGuard-owned execution paths are invalid without replacing native FlowGuard checks.

## Validation

- Run FlowGuard tests.
- Run downstream LogicGuard semantic guidance test that reads installed FlowGuard skills.
- Re-run SkillGuard route checks on updated FlowGuard skill contracts.
- Verify editable install and installed skill sync.
