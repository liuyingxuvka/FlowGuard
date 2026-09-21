# FlowGuard author-maintenance reference

This is author-side guidance for the registered FlowGuard skill suite. It is not
consumer material. The target suite owns route meaning, model judgment, native
checks, and evidence interpretation; SkillGuard owns author identity and clean
projection only.

For a source change, freeze the affected route/member closure, source and contract
identities, exact declared checks, owner DAG, evidence root, and claim boundary.
Run the real target-owned checks and reconcile current receipts. A source `light` or
`affected` result does not become a full release claim. Read the target's own route
fragment and the SkillGuard author references only for the selected boundary.

Installation, global-router currentness, and GitHub publication are separate explicit
claims. They do not follow from source checks or a full profile. The current joint
audit is source-only: do not install the consumer projection until separately
authorized.

Author-side checks:

```powershell
python -m flowguard read --root . --request read.json --json
python .agents/skills/skillguard/scripts/skillguard.py read --root . --request skillguard-read.json --json
```
