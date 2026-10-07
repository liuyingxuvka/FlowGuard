# FlowGuard author-maintenance reference

This author-only document maintains one declared public member, `flowguard`,
under `unit:flowguard-suite`. The target owns route meaning, native checks and
results. SkillGuard qualifies its explicit structural author contract; it does
not replace FlowGuard semantic checks or prove GitHub publication.

Read the current installed SkillGuard `SKILL.md`. Set `$SkillGuardCli` to that
entrypoint's `scripts/skillguard.py`; do not search historical supervisor,
compiler, profile, or self-host interfaces. The only public operations are
read/change/release. Pass the absolute `.agents/skills/flowguard` member root,
not the repository root, to SkillGuard.

## One persistent author owner

Freeze the unit, member, exact input and toolchain identities, checks, dependency
DAG, and one execution owner. The existing full `skill_suite_light` child owns
`scripts/check_flowguard_author_skill_assurance.py`; ordinary light currentness
starts no SkillGuard producer. The full release invocation supplies
`--author-state-root` pointing to an existing persistent directory outside the
repository. Never discard or relocate accepted state to retry a failed owner.

The wrapper uses current requests containing `operation`, `target_id`, `scope`,
`contract_path`, and `author_state_root`. Change/release additionally contain
`expected_current` and `facts: {"operation": "<operation>"}`. Read has neither
field. `claim_scope` is not a SkillGuard request field.

A new empty state runs change with `scope: ["route:change"]` and
`expected_current: null`, then release with `scope: ["route:release"]` and the
real change accepted ID, then read of `route:release`. Each step requires exit
zero, `status: pass`, `decision: pass`, and a valid `sha256:` accepted ID before
a dependent step starts. A fresh read is uninitialized, not a failed source.
Failed or interrupted state is retained. A checkpoint never substitutes for a
SkillGuard accepted receipt: reuse verifies its exact accepted ID through read;
changed inputs require change with the observed CAS token. A foreign or
unrecoverable state blocks without deletion, reset, or invented success. The
FlowGuard wrapper binds reuse to the contract's actual declared input bytes,
contract bytes, toolchain, member/unit and state root; inventory shape alone is
not source freshness. If an accepted mutation is recorded but its checkpoint
write fails, recover only from the exact retained request/result and a read of
the same accepted ID. If that result was not durably recorded, the state stays
blocked without deletion, reset, replay, or invented success.

Request files live only in the exact member-private directory
`.skillguard/runtime-requests/full-author-assurance/`. They and external
checkpoint/invocation records are output evidence, not source freshness inputs.
Do not exclude adjacent contract-source, compiled-contract, or check-manifest
files. The clean consumer projection never contains this private directory.

Current declared checks establish the existence of the entrypoint and route
surfaces. Keep their claim separate from native semantic qualification. Native
results come from `skill_native_checks`; `skill_self_governance` consumes those
receipts. The self-maintenance child uses one native composed review through
`scripts/check_self_maintenance_review.py` after its model receipt dependency.
Do not encode native success into undeclared request facts or launch duplicate
native/full checks from this wrapper.

Installation, author shadow, consumer projection, Git and release are separate
claims. Use explicitly selected isolated destinations only when authorized.
No source check updates a global installation. The final release parent and
its consumers are described in `docs/github_release_checklist.md`.
