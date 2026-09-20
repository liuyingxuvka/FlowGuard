# FlowGuard lifecycle operations

FlowGuard exposes one public skill and three lifecycle operations. They are
not execution-depth profiles and they do not silently promote one another.

| Operation | Purpose | Write boundary |
| --- | --- | --- |
| `read` | Read the accepted current model and the selected domain material | no source, current, evidence, installation, or release writes |
| `change` | Freeze the explicit request, compute the necessary owner closure, run only missing owners, and accept once through CAS | scoped source/evidence/current changes only after all hard gates pass |
| `release` | Check the declared release scope, reuse exact valid evidence, fill missing artifact obligations, and verify the actual projection | release artifacts and explicitly authorized installation only |

The current request supplies the real repository root and request file. Missing,
ambiguous, stale, foreign, or contradictory inputs are blockers. There is no
`light`, `affected`, or `full` public selector, and no fallback to an older
command or profile.

Domain-specific protocols are stored under
`.agents/skills/flowguard/references/domains/<subject>/` and loaded only after
the selected subject is known. These references do not create additional
discoverable skills.

All operations preserve `unknown`, `blocked`, `not-run`, `skipped`, stale, and
failed states. Exact functional evidence may be reused; installation, Git,
tags, and GitHub publication remain separate claims from source/model evidence.
