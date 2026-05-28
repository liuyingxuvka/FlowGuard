## Context

External project adoption currently depends on an agent reading
`docs/project_integration.md` and manually copying `docs/agents_snippet.md`.
That is too easy to miss, especially when a direct satellite Skill is invoked
without passing through the kernel. The project also has no first-class record
of which FlowGuard package version last verified its local model/test evidence.

## Goals / Non-Goals

**Goals:**

- Give adopted projects a durable `AGENTS.md` managed block with the FlowGuard
  GitHub URL, verification commands, and version policy.
- Give adopted projects a `.flowguard/project.toml` manifest with repository,
  package version, schema version, and verification metadata.
- Provide read-only audit plus write-mode adopt/upgrade commands.
- Preserve existing project rules by replacing only a marked FlowGuard block.
- Make kernel and satellite Skill prompts tell future agents to check the
  project adoption block during real target-project use.
- Treat stale project FlowGuard versions as explicit upgrade work, not silent
  success.

**Non-Goals:**

- Do not require FlowGuard adoption for read-only explanations or tiny trivial
  edits.
- Do not automatically install from GitHub without user/environment
  authorization.
- Do not rewrite arbitrary project documentation outside the managed AGENTS
  block and FlowGuard manifest/log files.
- Do not claim upgraded model/test evidence solely because the manifest changed.

## Decisions

1. **AGENTS uses a managed block.**
   The helper inserts or replaces text between
   `<!-- BEGIN FLOWGUARD PROJECT RULES -->` and
   `<!-- END FLOWGUARD PROJECT RULES -->`. Existing user or peer-agent rules
   outside those markers remain untouched.

2. **The repository URL is part of the rule.**
   The AGENTS block and manifest both name
   `https://github.com/liuyingxuvka/FlowGuard` so later agents know where the
   real package and docs come from.

3. **Package version and schema version are separate.**
   The manifest records both the FlowGuard package release version and
   `flowguard.SCHEMA_VERSION`, because schema compatibility can remain stable
   across package releases.

4. **Version comparison is conservative.**
   If the installed FlowGuard version is older than the project manifest, the
   audit blocks upgrade confidence and tells the agent to upgrade the tool. If
   the installed version is newer, the audit reports that project upgrade work
   is available. `project-upgrade` updates the manifest only after the command
   is explicitly run.

5. **Logs are evidence records, not proof.**
   `project-adopt` and `project-upgrade` may append adoption evidence, but
   model checks, tests, and closure evidence still have to be rerun when a
   claim depends on them.

6. **Direct satellite use keeps the adoption rule.**
   Satellite Skills get a short hard gate so direct route invocation cannot
   bypass the target-project AGENTS/version adoption check.

## Risks / Trade-offs

- **Risk: AGENTS update becomes noisy.** -> Mitigation: only one managed block
  is inserted/replaced; existing text is preserved.
- **Risk: users mistake manifest update for validation.** -> Mitigation:
  AGENTS, docs, and reports say manifest/log updates do not replace executable
  FlowGuard checks.
- **Risk: version comparisons are imperfect for unusual version strings.** ->
  Mitigation: use a small conservative parser; unknown versions are reported as
  needing human review instead of green.
- **Risk: direct satellite prompts become too long.** -> Mitigation: add only
  one compact target-project adoption bullet to each satellite hard gate.
