"""A small, real consumer lifecycle for first-current adoption.

The fixture deliberately owns only two model instances.  Its model and owner
runner files are real files and ``run_manifest_regressions`` executes those
runners; the test does not replace the authority loader, revision verifier, or
native-owner evidence producer with mocks.  This keeps the acceptance test
focused on the finite consumer boundary instead of the author's 51-model
maintenance suite.
"""

from __future__ import annotations

import json
import hashlib
import os
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from unittest import mock

import pytest

import flowguard.validation_ownership as validation_ownership
from flowguard.evidence_receipts import fingerprint_value
from flowguard.model_authority import (
    LIFECYCLE_ACTIVE,
    ModelAuthorityError,
    ModelRevisionSet,
    SUBJECT_OBSERVED_IMPLEMENTATION,
)
from flowguard.model_authority_store import (
    activate_model_revision_set,
    bootstrap_initial_current_model_authority,
    load_current_model_authority_state,
    load_observed_model_system,
    read_selected_model_closure,
)
from flowguard.model_intent import ModelIntentContribution
from flowguard.model_intent_authority import EffectiveIntentTransition
from flowguard.model_purpose import build_model_purpose_closure, file_fingerprint
from flowguard.model_regressions import MANIFEST_SCHEMA, run_manifest_regressions
from flowguard.model_revision_builder import build_current_model_revision
from flowguard.model_revision_owner_evidence import (
    produce_model_revision_owner_evidence,
)
from flowguard.model_revision_set import derive_revision_snapshot_diff
from flowguard.model_system_inventory import build_manifest_model_system_snapshot
from flowguard.native_case_mapping import (
    NATIVE_CASE_MAPPING_SCHEMA,
    compute_native_case_mapping_fingerprint,
)
from flowguard.native_case_protocol import (
    BAD_DIMENSIONS,
    GOOD_DIMENSIONS,
    NativeCaseBinding,
)
from flowguard.process_supervision import run_supervised_bytes
from flowguard.project_manifest import manifest_text_fingerprint
from flowguard.source_identity import source_file_fingerprint
from tests.test_model_maturation import _path_quality


_MODEL_IDS = ("alpha", "beta", "alpha_beta_connection")


def _write_consumer(root: Path) -> None:
    """Write two business models and one explicit connection owner."""

    (root / ".flowguard").mkdir(parents=True, exist_ok=True)
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "consumer-design.md").write_text(
        "Alpha classifies a finite numeric boundary; beta consumes the explicit alpha-to-beta connection.\n",
        encoding="utf-8",
    )
    (root / "src" / "alpha.py").write_text(
        "def classify(value: int) -> str:\n"
        "    if type(value) is not int:\n"
        "        raise TypeError('value must be int')\n"
        "    if value < 0:\n"
        "        return 'negative'\n"
        "    if value == 0:\n"
        "        return 'zero'\n"
        "    return 'positive'\n",
        encoding="utf-8",
    )
    (root / "src" / "beta.py").write_text(
        "def enabled(flag: bool) -> str:\n"
        "    if not isinstance(flag, bool):\n"
        "        raise TypeError('flag must be bool')\n"
        "    return 'on' if flag else 'off'\n",
        encoding="utf-8",
    )
    (root / "src" / "join.py").write_text(
        "from .alpha import classify\n"
        "from .beta import enabled\n\n"
        "ALPHA_TO_BETA = {'negative': False, 'zero': False, 'positive': True}\n\n"
        "def alpha_to_beta(label: str) -> str:\n"
        "    return enabled(ALPHA_TO_BETA[label])\n\n"
        "def enabled_from_value(value: int) -> str:\n"
        "    return alpha_to_beta(classify(value))\n",
        encoding="utf-8",
    )
    rows: list[dict[str, object]] = []
    protected_failure = "consumer:invalid-boundary"
    case_selectors: dict[str, tuple[tuple[str, str, str], ...]] = {
        "alpha": (
            ("good-negative", "good", "ok"),
            ("good-zero", "good", "ok"),
            ("good-positive", "good", "ok"),
            ("known-bad", "bad", "violation"),
        ),
        "beta": (
            ("good-disabled", "good", "ok"),
            ("good-enabled", "good", "ok"),
            ("known-bad", "bad", "violation"),
        ),
        "alpha_beta_connection": (
            ("join-negative", "good", "ok"),
            ("join-zero", "good", "ok"),
            ("join-positive", "good", "ok"),
            ("known-bad", "bad", "violation"),
        ),
    }
    runner_prelude = (
        "import sys, types\n"
        "if 'flowguard' not in sys.modules:\n"
        "    _pkg = types.ModuleType('flowguard')\n"
        "    _pkg.__path__ = [__import__('pathlib').Path(__file__).resolve().parents[4].joinpath('flowguard').as_posix()]\n"
        "    _pkg.__package__ = 'flowguard'\n"
        "    sys.modules['flowguard'] = _pkg\n"
        "\n"
        "def make_report(cases, function_name):\n"
        "    results = []\n"
        "    for case in cases:\n"
        "        initial = {'fields': {'case': case['name'], 'phase': 'initial'}}\n"
        "        final = {'fields': {'case': case['name'], 'phase': case.get('observed_status', 'ok')}}\n"
        "        results.append({\n"
        "            'scenario_name': case['name'],\n"
        "            'ok': bool(case['ok']),\n"
        "            'status': 'pass' if case['ok'] else 'fail',\n"
        "            'scenario_run': {\n"
        "                'observed_status': case.get('observed_status', 'ok'),\n"
        "                'traces': [{\n"
        "                    'initial_state': initial,\n"
        "                    'steps': [{\n"
        "                        'old_state': initial,\n"
        "                        'new_state': final,\n"
        "                        'function_name': function_name,\n"
        "                        'function_output': case.get('observed_status', 'ok'),\n"
        "                        'label': 'native-executed',\n"
        "                    }],\n"
        "                    'final_state': final,\n"
        "                    'labels': ['native-executed'],\n"
        "                }],\n"
        "                'final_states': [final],\n"
        "                'observed_violation_names': list(case.get('finding_codes', ())),\n"
        "            },\n"
        "        })\n"
        "    return {'results': results, 'exit_code': 0 if all(item['ok'] for item in cases) else 1}\n"
    )
    runner_sources = {
        "alpha": runner_prelude + """import json\nfrom src.alpha import classify\nfrom flowguard.native_case_runner import native_main\n\ndef run_review():\n    cases = []\n    for name, value, expected in ((\"good-negative\", -1, \"negative\"), (\"good-zero\", 0, \"zero\"), (\"good-positive\", 1, \"positive\")):\n        observed = classify(value)\n        cases.append({\"name\": name, \"ok\": observed == expected, \"observed_status\": \"ok\" if observed == expected else \"violation\", \"case_kind\": \"good\"})\n    try:\n        classify(\"invalid\")\n    except (TypeError, ValueError):\n        cases.append({\"name\": \"known-bad\", \"ok\": True, \"observed_status\": \"violation\", \"finding_codes\": [\"consumer:invalid-boundary\"], \"case_kind\": \"bad\"})\n    print(json.dumps({\"cases\": cases}, sort_keys=True))\n    return make_report(cases, \"classify\")\n\ndef main():\n    return native_main(\"model:alpha\", run_review)\n\nif __name__ == \"__main__\":\n    raise SystemExit(main())\n""",
        "beta": runner_prelude + """import json\nfrom src.beta import enabled\nfrom flowguard.native_case_runner import native_main\n\ndef run_review():\n    cases = []\n    for name, flag, expected in ((\"good-disabled\", False, \"off\"), (\"good-enabled\", True, \"on\")):\n        observed = enabled(flag)\n        cases.append({\"name\": name, \"ok\": observed == expected, \"observed_status\": \"ok\" if observed == expected else \"violation\", \"case_kind\": \"good\"})\n    try:\n        enabled(\"invalid\")\n    except (TypeError, ValueError):\n        cases.append({\"name\": \"known-bad\", \"ok\": True, \"observed_status\": \"violation\", \"finding_codes\": [\"consumer:invalid-boundary\"], \"case_kind\": \"bad\"})\n    print(json.dumps({\"cases\": cases}, sort_keys=True))\n    return make_report(cases, \"enabled\")\n\ndef main():\n    return native_main(\"model:beta\", run_review)\n\nif __name__ == \"__main__\":\n    raise SystemExit(main())\n""",
        "alpha_beta_connection": runner_prelude + """import json\nfrom src.join import enabled_from_value\nfrom flowguard.native_case_runner import native_main\n\ndef run_review():\n    cases = []\n    for name, value, expected in ((\"join-negative\", -1, \"off\"), (\"join-zero\", 0, \"off\"), (\"join-positive\", 1, \"on\")):\n        observed = enabled_from_value(value)\n        cases.append({\"name\": name, \"ok\": observed == expected, \"observed_status\": \"ok\" if observed == expected else \"violation\", \"case_kind\": \"good\"})\n    try:\n        enabled_from_value(\"invalid\")\n    except (TypeError, ValueError, KeyError):\n        cases.append({\"name\": \"known-bad\", \"ok\": True, \"observed_status\": \"violation\", \"finding_codes\": [\"consumer:invalid-boundary\"], \"case_kind\": \"bad\"})\n    print(json.dumps({\"cases\": cases}, sort_keys=True))\n    return make_report(cases, \"enabled_from_value\")\n\ndef main():\n    return native_main(\"model:alpha_beta_connection\", run_review)\n\nif __name__ == \"__main__\":\n    raise SystemExit(main())\n""",
    }
    runner_sources["alpha"] = runner_sources["alpha"].replace(
        "    print(json.dumps({\"cases\": cases}, sort_keys=True))\n",
        "    if __import__('pathlib').Path('trigger-alpha-source-drift').is_file():\n"
        "        __import__('pathlib').Path('src/alpha.py').write_text(\"def classify(value):\\n    return 'drifted-during-owner-run'\\n\", encoding='utf-8')\n"
        "    print(json.dumps({\"cases\": cases}, sort_keys=True))\n",
        1,
    )
    for model_id in _MODEL_IDS:
        model_path = root / ".flowguard" / "models" / "owners" / model_id / "model.py"
        runner_path = root / ".flowguard" / "verification" / "owners" / model_id / "run_checks.py"
        model_path.parent.mkdir(parents=True, exist_ok=True)
        runner_path.parent.mkdir(parents=True, exist_ok=True)
        model_path.write_text(
            f"MODEL_ID = {model_id!r}\nBOUNDARY = ('start', 'ready')\nCASES = {tuple(item[0] for item in case_selectors[model_id])!r}\n",
            encoding="utf-8",
        )
        runner_path.write_text(runner_sources[model_id], encoding="utf-8")
        input_paths = [
            model_path.relative_to(root).as_posix(),
            runner_path.relative_to(root).as_posix(),
        ]
        if model_id == "alpha_beta_connection":
            input_paths.extend(("src/alpha.py", "src/beta.py", "src/join.py"))
        else:
            input_paths.append(f"src/{model_id}.py")
        purpose = build_model_purpose_closure(
            model_instance_id=f"regression:{model_id}:current",
            reusable_model_type_id=model_id,
            task_intent_id=f"consumer-intent:{model_id}",
            guarded_purpose=(
                f"Keep the finite {model_id} model from accepting an invalid "
                "consumer boundary or stale owner evidence."
            ),
            protected_failure_ids=(protected_failure,),
            known_good_case_id=f"native-runner:consumer:{model_id}:good",
            failure_bindings=(
                {
                    "failure_id": protected_failure,
                    "known_bad_case_id": f"native-runner:consumer:{model_id}:bad",
                    "oracle_id": f"native:consumer:{model_id}:oracle",
                },
            ),
            claim_boundary=(
                "This fixture proves only the finite business and connection-owner "
                "boundary; it makes no claim about unlisted production paths."
            ),
            evidence_check_ids=(f"check:model-regression:{model_id}",),
            model_sha256=file_fingerprint(model_path),
            runner_sha256=file_fingerprint(runner_path),
        )
        rows.append(
            {
                "model_id": model_id,
                "model_path": model_path.relative_to(root).as_posix(),
                "runner": ["{python}", runner_path.relative_to(root).as_posix()],
                "tier": "full",
                "timeout_seconds": 60,
                "shard_safe": True,
                "mutation_policy": "none",
                "input_globs": input_paths,
                "intent_source_inputs": ["docs/consumer-design.md"],
                "expected_artifacts": [],
                "distribution_policy": "required_public",
                "absence_reason": "Required in this finite consumer fixture.",
                "exclusion_reason": "",
                "purpose_closure": purpose.to_dict(),
            }
        )
    manifest_path = root / ".flowguard" / "models" / "regression-manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": MANIFEST_SCHEMA,
                "governed_input_globs": [
                    ".flowguard/models/owners/**/*.py",
                    ".flowguard/verification/owners/**/*.py",
                    "src/**/*.py",
                ],
                "snapshot_only_input_globs": [],
                "shared_input_groups": [],
                "models": rows,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    mapping_bindings: list[NativeCaseBinding] = []
    for model_id, selectors in case_selectors.items():
        for selector, kind, observed_status in selectors:
            mapping_bindings.append(
                NativeCaseBinding(
                    owner_id=f"model:{model_id}",
                    blueprint_case_id=f"consumer:{model_id}:{selector}",
                    blueprint_source_case_id=selector,
                    native_case_ids=(f"case:{model_id}:{selector}",),
                    case_kind=kind,
                    evidence_scope="implementation_boundary",
                    covered_dimensions=(GOOD_DIMENSIONS if kind == "good" else BAD_DIMENSIONS),
                    expected_status="pass",
                    expected_observed_status=observed_status,
                    protected_failure_ids=(protected_failure,),
                    expected_finding_codes=(protected_failure,) if kind == "bad" else (),
                    mapping_fingerprint="",
                )
            )
    mapping_fingerprint = compute_native_case_mapping_fingerprint(
        source_manifest_fingerprint=source_file_fingerprint(manifest_path),
        source_paths=(manifest_path.relative_to(root).as_posix(),),
        bindings=mapping_bindings,
    )
    mapping_payload = {
        "schema_version": NATIVE_CASE_MAPPING_SCHEMA,
        "mapping_fingerprint": mapping_fingerprint,
        "source_manifest_fingerprint": source_file_fingerprint(manifest_path),
        "source_paths": [manifest_path.relative_to(root).as_posix()],
        "diagnostic_native_case_ids": [],
        "bindings": [
            replace(binding, mapping_fingerprint=mapping_fingerprint).to_dict()
            for binding in sorted(
                mapping_bindings,
                key=lambda item: item.blueprint_case_id,
            )
        ],
    }
    (root / ".flowguard" / "models" / "native-case-mapping.json").write_text(
        json.dumps(mapping_payload, sort_keys=True), encoding="utf-8"
    )
    (root / ".flowguard" / "structure").mkdir(parents=True, exist_ok=True)
    (root / ".flowguard" / "structure" / "owner-bindings.json").write_text(
        json.dumps(
            {
                "schema": "flowguard.native_owner_model_bindings.v1",
                "system_id": "flowguard",
                "candidate_model_ids": list(_MODEL_IDS),
                "bindings": [
                    {
                        "owner_route": "model_mesh_maintenance",
                        "model_ids": list(_MODEL_IDS),
                        "protected_failure_ids": [protected_failure],
                    },
                    {
                        "owner_route": "model_test_alignment",
                        "model_ids": list(_MODEL_IDS),
                        "protected_failure_ids": [protected_failure],
                    },
                ],
                "claim_boundary": "Only this finite two-model plus connection-owner map.",
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    # This is the fixture's explicit cross-model connection: alpha publishes
    # a bounded result consumed at beta's parent boundary.  The semantic mesh
    # is intentionally tiny, but it exercises the same typed parent/child and
    # cross-parent relation edges used by a real consumer instead of relying
    # on a flat root-to-model projection.  The connection terminates at the
    # typed parent endpoint, so selecting beta remains local and an unrelated
    # alpha source edit does not silently widen beta's read.
    semantic_mesh = {
        "schema_version": "flowguard.semantic_self_mesh.v3",
        "mesh_id": "mesh:consumer-current",
        "claim_scope": "consumer-fixture",
        "derivation_base_snapshot_path": ".flowguard/models/regression-manifest.json",
        "derivation_base_snapshot_fingerprint": "sha256:consumer-fixture-base",
        "current_manifest_path": ".flowguard/models/regression-manifest.json",
        "observed_base_added_model_ids": [],
        "observed_base_removed_model_ids": [],
        "declared_model_count": 3,
        "semantic_universe_fingerprint": "sha256:consumer-fixture-universe",
        "semantic_disposition_fingerprint": "sha256:consumer-fixture-disposition",
        "semantic_relation_fingerprint": "sha256:consumer-fixture-relation",
        "semantic_model_status": "current",
        "whole_system_completion_claim": "Only the finite two-model plus connection-owner mesh is declared.",
        "currentness_owner": "consumer-fixture",
        "claim_boundary": "This fixture proves only a finite parent/child and cross-model connection.",
        "allowed_dispositions": ["retain"],
        "semantic_parents": [
            {"parent_id": "parent:alpha", "purpose": "Owns alpha's finite producer boundary."},
            {"parent_id": "parent:beta", "purpose": "Owns beta's finite consumer boundary."},
            {"parent_id": "parent:alpha_beta_connection", "purpose": "Owns the independently executed alpha-to-beta boundary."},
        ],
        "required_terminal_evidence": ["consumer-fixture:connection"],
        "models": [
            {
                "model_id": "alpha",
                "disposition": "retain",
                "consumer_ids": ["parent:beta"],
                "rationale": "Alpha's bounded result is consumed by beta.",
                "structural_parent_id": "parent:alpha",
                "cross_boundary_parent_ids": ["parent:beta", "parent:alpha_beta_connection"],
            },
            {
                "model_id": "beta",
                "disposition": "retain",
                "consumer_ids": ["parent:alpha"],
                "rationale": "Beta closes the dependent consumer boundary.",
                "structural_parent_id": "parent:beta",
                "cross_boundary_parent_ids": [],
            },
            {
                "model_id": "alpha_beta_connection",
                "disposition": "retain",
                "consumer_ids": ["parent:beta"],
                "rationale": "The connection owner executes the real alpha-to-beta join independently.",
                "structural_parent_id": "parent:alpha_beta_connection",
                "cross_boundary_parent_ids": ["parent:beta"],
            },
        ],
        "feedback_progress_contracts": [],
    }
    semantic_path = (
        root
        / ".flowguard"
        / "models"
        / "owners"
        / "authoritative_model_system"
        / "semantic_model_mesh.json"
    )
    semantic_path.parent.mkdir(parents=True, exist_ok=True)
    semantic_path.write_text(json.dumps(semantic_mesh, sort_keys=True), encoding="utf-8")
    (root / ".flowguard" / "project.toml").write_text(
        '[flowguard]\nadopted_package_version = "0.69.0"\n',
        encoding="utf-8",
    )


def _design_contributions(root: Path, *, include_beta: bool = True) -> tuple[ModelIntentContribution, ...]:
    source = root / "docs" / "consumer-design.md"
    selected = _MODEL_IDS if include_beta else ("alpha",)
    return tuple(
        ModelIntentContribution(
            contribution_id=f"intent:consumer-design:{model_id}",
            source_kind="design",
            source_ref="docs/consumer-design.md",
            source_fingerprint=source_file_fingerprint(source),
            subject_lane="normative_target",
            subject_role="design",
            lifecycle_state="candidate",
            decision_state="accepted",
            logical_model_id=f"model:{model_id}",
            unresolved_owner_id="",
            supersedes_contribution_ids=(),
            conflicts_with_contribution_ids=(),
            target_obligation_ids=(),
            target_state_ids=(),
            target_transition_ids=(),
            target_invariant_ids=(),
            target_relation_ids=(f"relation:model-realizes-purpose:{model_id}",),
            desired_terminal_state_ids=(),
            target_output_ids=(),
            declared_consumer_ids=(),
            effective_revision="consumer-design-current",
            rationale=(
                f"The exact consumer design source declares {model_id}'s "
                "current owner and finite boundary."
            ),
        )
        for model_id in selected
    )


def _consumer_roots(tmp_path: Path) -> tuple[Path, Path]:
    target = tmp_path / "consumer"
    staging = tmp_path / "staging"
    _write_consumer(target)
    shutil.copytree(target, staging)
    return target, staging


def _prepare_parent(staging: Path):
    receipt_root = staging / "work" / "model-owner-receipts"
    parent_dir = staging / "work" / "model-parent"
    report = run_manifest_regressions(
        staging,
        tier="full",
        jobs=1,
        output_dir=parent_dir,
        receipt_dir=receipt_root,
        require_executed_case_ids=True,
    )
    assert report.status == "pass", report.to_dict()
    assert report.parent_receipt_path
    return report, receipt_root


def _publish_initial(
    target: Path,
    staging: Path,
    *,
    parent,
    receipt_root: Path,
    include_beta: bool = True,
):
    manifest_path = target / ".flowguard" / "project.toml"
    expected_absent = manifest_text_fingerprint(manifest_path.read_text(encoding="utf-8"))
    return bootstrap_initial_current_model_authority(
        target,
        staging_root=staging,
        expected_absent_manifest_fingerprint=expected_absent,
        snapshot_id="snapshot:consumer-current",
        bootstrap_evidence_fingerprint=fingerprint_value(
            {"parent": parent.parent_receipt_fingerprint, "models": list(_MODEL_IDS)}
        ),
        model_parent_receipt=parent.parent_receipt_path,
        receipt_root=receipt_root,
        revision_set_id="revision:consumer-current",
        task_id="task:consumer-current",
        activation_receipt_id="activation:consumer-current",
        current_design_intent_contributions=_design_contributions(
            staging, include_beta=include_beta
        ),
        intent_receipt_id="receipt:intent-bootstrap:consumer-current",
        intent_rationale="Accept the two exact consumer design contributions once.",
        intent_claim_boundary="Only the finite two-model consumer design boundary.",
        decision_reason="Every declared consumer model has current intent and owner evidence.",
    )


def _adopt(target: Path, staging: Path, *, include_beta: bool = True):
    parent, receipt_root = _prepare_parent(staging)
    return _publish_initial(
        target,
        staging,
        parent=parent,
        receipt_root=receipt_root,
        include_beta=include_beta,
    )


def _current_intent_retain_transitions(
    target: Path,
) -> tuple[EffectiveIntentTransition, ...]:
    state = load_current_model_authority_state(target)
    assert state.accepted_revision is not None
    return tuple(
        EffectiveIntentTransition(
            prior_contribution_id=contribution.contribution_id,
            prior_contribution_fingerprint=contribution.fingerprint,
            action="retain",
            replacement_contribution_ids=(),
            reason=(
                "The consumer requirement remains current while its exact "
                "implementation evidence is refreshed."
            ),
        )
        for contribution in (
            state.accepted_revision.current_effective_intent_view.active_contributions
        )
    )


def _prepare_affected_update(
    target: Path,
    *,
    receipt_root: Path,
    snapshot_id: str,
    output_name: str,
):
    parent = run_manifest_regressions(
        target,
        tier="full",
        jobs=1,
        output_dir=target / "work" / output_name / "model-parent",
        receipt_dir=receipt_root,
        require_executed_case_ids=True,
    )
    assert parent.status == "pass", parent.to_dict()
    owner_report = produce_model_revision_owner_evidence(
        target,
        model_parent_receipt=parent.parent_receipt_path,
        snapshot_id=snapshot_id,
        receipt_root=receipt_root,
        output_path=target / "work" / output_name / "native-owner-evidence.json",
    )
    _head, base = load_observed_model_system(target)
    candidate = build_manifest_model_system_snapshot(
        target,
        snapshot_id=snapshot_id,
        system_id=base.system_id,
        subject_lane=base.subject_lane,
        lifecycle=base.lifecycle,
    )
    diff = derive_revision_snapshot_diff(base, candidate)
    path_quality_rows = tuple(
        _path_quality(
            member.member_id,
            member.candidate_instance_fingerprint,
            candidate.fingerprint,
        )
        for member in diff.members
        if member.operation in {"add", "replace"}
    )
    built = build_current_model_revision(
        target,
        model_parent_receipt=parent.parent_receipt_path,
        receipt_root=receipt_root,
        revision_set_id=f"revision:{output_name}",
        task_id=f"task:{output_name}",
        snapshot_id=snapshot_id,
        effective_intent_transitions=_current_intent_retain_transitions(target),
        native_owner_contracts=owner_report.bundle.contracts,
        native_owner_receipts=owner_report.bundle.receipts,
        native_owner_verification_results=(
            owner_report.bundle.verification_results
        ),
        path_quality_subjects=tuple(row[0] for row in path_quality_rows),
        path_quality_results=tuple(row[1] for row in path_quality_rows),
        decision_reason=(
            "The real consumer change and its typed dependent connection have "
            "exact current owner evidence."
        ),
    )
    assert built.status == "pass", built.to_dict()
    revision = ModelRevisionSet.from_dict(
        json.loads(Path(built.revision_set_path).read_text(encoding="utf-8"))
    )
    return parent, candidate, revision, built


def _file_inventory(*roots: Path) -> dict[str, bytes]:
    inventory: dict[str, bytes] = {}
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            inventory[str(path.resolve())] = path.read_bytes()
    return inventory


def _run_public_read(target: Path, request_path: Path, *extra: str):
    project_root = Path(__file__).resolve().parents[1]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        item
        for item in (str(project_root), environment.get("PYTHONPATH", ""))
        if item
    )
    return subprocess.run(
        (
            sys.executable,
            "-m",
            "flowguard",
            "read",
            "--root",
            str(target),
            "--request",
            str(request_path),
            "--json",
            *extra,
        ),
        cwd=project_root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def _run_public_change(target: Path, request_path: Path):
    project_root = Path(__file__).resolve().parents[1]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        item
        for item in (str(project_root), environment.get("PYTHONPATH", ""))
        if item
    )
    return subprocess.run(
        (
            sys.executable,
            "-m",
            "flowguard",
            "change",
            "--root",
            str(target),
            "--request",
            str(request_path),
            "--json",
        ),
        cwd=project_root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def _run_public_release(target: Path, request_path: Path):
    project_root = Path(__file__).resolve().parents[1]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        item
        for item in (str(project_root), environment.get("PYTHONPATH", ""))
        if item
    )
    return subprocess.run(
        (
            sys.executable,
            "-m",
            "flowguard",
            "release",
            "--root",
            str(target),
            "--request",
            str(request_path),
            "--json",
        ),
        cwd=project_root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def _write_release_request(
    target: Path,
    *,
    artifact: dict[str, str] | None = None,
) -> tuple[Path, dict[str, object]]:
    head, snapshot = load_observed_model_system(target)
    state = load_current_model_authority_state(target)
    assert state.accepted_revision is not None
    obligations = sorted(
        {
            obligation
            for evidence in state.accepted_revision.required_evidence_refs
            for obligation in evidence.obligation_ids
        }
    )
    contract = {
        "schema": "flowguard.release_contract.v1",
        "target_id": head.system_id,
        "required_model_ids": sorted(
            row.logical_model_id for row in snapshot.model_instances
        ),
        "required_check_ids": obligations,
        "required_source_paths": ["src/alpha.py", "src/beta.py", "src/join.py"],
        "artifact_members": [],
    }
    contract_raw = json.dumps(contract, sort_keys=True).encode("utf-8")
    contract_path = target / "release-contract.json"
    contract_path.write_bytes(contract_raw)
    request = {
        "operation": "release",
        "target_id": head.system_id,
        "scope": contract["required_model_ids"],
        "expected_current": head.fingerprint,
        "release_contract": {
            "path": contract_path.relative_to(target).as_posix(),
            "sha256": hashlib.sha256(contract_raw).hexdigest(),
        },
        "artifact": artifact,
    }
    request_path = target / "release-request.json"
    request_path.write_text(json.dumps(request, sort_keys=True), encoding="utf-8")
    return request_path, request


def test_public_release_source_qualification_reuses_accepted_current_with_qualification_receipt(
    tmp_path: Path,
):
    target, staging = _consumer_roots(tmp_path)
    _adopt(target, staging)
    # The public release seam consumes the canonical leaf store.  Bootstrap
    # keeps the producer receipts in isolated staging, so publish that exact
    # content-addressed store as the fixture's pre-existing accepted evidence
    # before measuring release-side writes.
    public_receipts = target / ".flowguard" / "evidence" / "model-owner-receipts"
    public_receipts.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(staging / "work" / "model-owner-receipts", public_receipts)
    original_head, _snapshot = load_observed_model_system(target)
    request_path, _request = _write_release_request(target)
    before = _file_inventory(target / ".flowguard")

    completed = _run_public_release(target, request_path)

    assert completed.returncode == 0, completed.stderr or completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["status"] == "pass"
    assert payload["qualification"] == "source_qualification_only"
    assert payload["artifact_status"] == "not_run"
    assert payload["producer_count"] == 0
    assert payload["run_count"] == 0
    assert payload["reused_count"] == 3
    assert payload["write_count"] == 1
    qualification_path = (target / payload["qualification_receipt_path"]).resolve()
    assert qualification_path.is_file()
    assert payload["qualification_receipt_fingerprint"].startswith("sha256:")
    assert load_observed_model_system(target)[0] == original_head
    after = _file_inventory(target / ".flowguard")
    assert set(after) == set(before) | {str(qualification_path)}
    for path, content in before.items():
        assert after[path] == content


def test_public_release_wrong_artifact_hash_blocks_before_source_qualification(
    tmp_path: Path,
):
    target, staging = _consumer_roots(tmp_path)
    _adopt(target, staging)
    artifact_path = target / "dist" / "bundle.txt"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text("real bytes", encoding="utf-8")
    request_path, _request = _write_release_request(
        target,
        artifact={"path": "dist/bundle.txt", "sha256": "0" * 64},
    )

    completed = _run_public_release(target, request_path)

    assert completed.returncode == 1
    payload = json.loads(completed.stdout)
    assert payload["status"] == "blocked"
    assert payload["reason"] == "artifact_invalid"
    assert payload["producer_count"] == 0
    assert payload["run_count"] == 0
    assert payload["write_count"] == 0


def test_public_release_blocks_unaccepted_source_change_without_moving_current(
    tmp_path: Path,
):
    target, staging = _consumer_roots(tmp_path)
    _adopt(target, staging)
    original_head, _snapshot = load_observed_model_system(target)
    request_path, _request = _write_release_request(target)
    (target / "src" / "alpha.py").write_text(
        "def classify(value):\n    return 'unaccepted'\n",
        encoding="utf-8",
    )

    completed = _run_public_release(target, request_path)

    assert completed.returncode == 1
    payload = json.loads(completed.stdout)
    assert payload["status"] == "blocked"
    assert payload["reason"] == "source_requires_change"
    assert payload["producer_count"] == 0
    assert payload["run_count"] == 0
    assert payload["write_count"] == 0
    assert load_observed_model_system(target)[0] == original_head


def test_public_change_bootstrap_runs_three_real_owners_and_publishes_current(
    tmp_path: Path,
):
    target, source_staging = _consumer_roots(tmp_path)
    staging = target / ".flowguard" / "work" / "bootstrap" / "bootstrap-case"
    staging.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source_staging), staging)
    candidate = build_manifest_model_system_snapshot(
        staging,
        snapshot_id="snapshot:public-bootstrap",
    )
    preparation_path = target / "revision-preparation.json"
    preparation = {
        "schema": "flowguard.revision_preparation.v1",
        "target_id": candidate.system_id,
        "base_head_fingerprint": None,
        "snapshot_id": "snapshot:public-bootstrap",
        "revision_set_id": "revision:public-bootstrap",
        "task_id": "task:public-bootstrap",
        "activation_receipt_id": "activation:public-bootstrap",
        "decision_reason": "Accept the three finite current consumer owners.",
        "intent_contributions": [],
        "intent_dispositions": [],
        "effective_intent_transitions": [],
        "removal_dispositions": [],
        "current_design_intent_contributions": [
            item.to_dict() for item in _design_contributions(staging)
        ],
        "accepted_boundary_contract_ref": None,
        "path_quality_outputs": [],
        "bootstrap_staging_root": staging.relative_to(target).as_posix(),
    }
    preparation_raw = json.dumps(preparation, sort_keys=True).encode("utf-8")
    preparation_path.write_bytes(preparation_raw)
    request_path = target / "change-request.json"
    request_path.write_text(
        json.dumps(
            {
                "operation": "change",
                "target_id": candidate.system_id,
                "scope": list(_MODEL_IDS),
                "expected_current": None,
                "bootstrap": True,
                "revision_input": {
                    "path": preparation_path.relative_to(target).as_posix(),
                    "sha256": hashlib.sha256(preparation_raw).hexdigest(),
                },
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    completed = _run_public_change(target, request_path)

    assert completed.returncode == 0, completed.stderr or completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["status"] == "pass"
    assert payload["bootstrap"] is True
    assert payload["required_count"] == 3
    assert payload["run_count"] == 3
    assert payload["reused_count"] == 0
    assert payload["head"]["generation"] == 2
    current_head, current_snapshot = load_observed_model_system(target)
    assert current_head.generation == 2
    assert {row.logical_model_id for row in current_snapshot.model_instances} == set(
        _MODEL_IDS
    )


def test_public_change_rejects_bad_preparation_hash_before_any_producer(tmp_path: Path):
    target, source_staging = _consumer_roots(tmp_path)
    staging = target / ".flowguard" / "work" / "bootstrap" / "bad-hash"
    staging.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source_staging), staging)
    candidate = build_manifest_model_system_snapshot(
        staging,
        snapshot_id="snapshot:bad-hash",
    )
    preparation_path = target / "revision-preparation.json"
    preparation_path.write_text("{}", encoding="utf-8")
    request_path = target / "change-request.json"
    request_path.write_text(
        json.dumps(
            {
                "operation": "change",
                "target_id": candidate.system_id,
                "scope": list(_MODEL_IDS),
                "expected_current": None,
                "bootstrap": True,
                "revision_input": {
                    "path": preparation_path.relative_to(target).as_posix(),
                    "sha256": "0" * 64,
                },
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    completed = _run_public_change(target, request_path)

    assert completed.returncode == 1
    payload = json.loads(completed.stdout)
    assert payload["status"] == "blocked"
    assert payload["producer_count"] == 0
    assert "does not match file bytes" in payload["error"]
    assert not list(staging.rglob("native-case-results.json"))


def test_public_change_current_alpha_executes_connection_reuses_beta_and_activates(
    tmp_path: Path,
):
    target, staging = _consumer_roots(tmp_path)
    _adopt(target, staging)
    # Move the already accepted leaf store to the public seam's canonical
    # root so the current planner can reuse beta and rerun only alpha plus its
    # independently owned connection proof.
    public_receipts = target / ".flowguard" / "evidence" / "model-owner-receipts"
    public_receipts.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(staging / "work" / "model-owner-receipts", public_receipts)
    original_head, _snapshot = load_observed_model_system(target)
    (target / "src" / "alpha.py").write_text(
        "def classify(value: int) -> str:\n"
        "    if isinstance(value, bool) or not isinstance(value, int):\n"
        "        raise TypeError('value must be int')\n"
        "    if value < 0:\n        return 'negative'\n"
        "    if value == 0:\n        return 'zero'\n"
        "    return 'positive'\n",
        encoding="utf-8",
    )
    preparation = {
        "schema": "flowguard.revision_preparation.v1",
        "target_id": original_head.system_id,
        "base_head_fingerprint": original_head.fingerprint,
        "snapshot_id": "snapshot:public-alpha-current",
        "revision_set_id": "revision:public-alpha-current",
        "task_id": "task:public-alpha-current",
        "activation_receipt_id": "activation:public-alpha-current",
        "decision_reason": "Accept the current alpha refinement and dependent connection proof.",
        "intent_contributions": [],
        "intent_dispositions": [],
        "effective_intent_transitions": [
            item.to_dict() for item in _current_intent_retain_transitions(target)
        ],
        "removal_dispositions": [],
        "current_design_intent_contributions": [],
        "accepted_boundary_contract_ref": None,
        "path_quality_outputs": [
            {
                "model_id": model_id,
                "producer_owner_id": f"model:{model_id}",
                "case_id": f"native-case-set:{model_id}",
                "artifact_id": f"path-quality:{model_id}",
            }
            for model_id in ("alpha", "alpha_beta_connection")
        ],
        "bootstrap_staging_root": None,
    }
    preparation_raw = json.dumps(preparation, sort_keys=True).encode("utf-8")
    preparation_path = target / "current-preparation.json"
    preparation_path.write_bytes(preparation_raw)
    request_path = target / "current-change-request.json"
    request_path.write_text(
        json.dumps(
            {
                "operation": "change",
                "target_id": original_head.system_id,
                "scope": ["alpha"],
                "expected_current": original_head.fingerprint,
                "bootstrap": False,
                "revision_input": {
                    "path": preparation_path.relative_to(target).as_posix(),
                    "sha256": hashlib.sha256(preparation_raw).hexdigest(),
                },
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    unknown_request = json.loads(request_path.read_text(encoding="utf-8"))
    unknown_request["scope"] = ["unknown-model-or-boundary"]
    unknown_request_path = target / "unknown-scope-change-request.json"
    unknown_request_path.write_text(
        json.dumps(unknown_request, sort_keys=True), encoding="utf-8"
    )
    before_unknown = _file_inventory(public_receipts)
    unknown = _run_public_change(target, unknown_request_path)
    assert unknown.returncode == 1
    unknown_payload = json.loads(unknown.stdout)
    assert unknown_payload["status"] == "blocked"
    assert unknown_payload["producer_count"] == 0
    assert "unknown IDs" in unknown_payload["error"]
    assert _file_inventory(public_receipts) == before_unknown

    completed = _run_public_change(target, request_path)

    assert completed.returncode == 0, completed.stderr or completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["status"] == "pass"
    assert payload["bootstrap"] is False
    assert payload["required_count"] == 3
    assert payload["run_count"] == 2
    assert payload["reused_count"] == 1
    assert payload["affected_model_ids"] == ["alpha", "alpha_beta_connection"]
    assert payload["head"]["generation"] == original_head.generation + 1
    assert load_observed_model_system(target)[0].fingerprint == payload["head"]["fingerprint"]

    # Replaying the stale CAS request is rejected before another producer is
    # leased and cannot add evidence or move the current pointer.
    evidence_before_replay = _file_inventory(public_receipts)
    stale_replay = _run_public_change(target, request_path)
    assert stale_replay.returncode == 1
    stale_payload = json.loads(stale_replay.stdout)
    assert stale_payload["status"] == "blocked"
    assert stale_payload["producer_count"] == 0
    assert "expected_current" in stale_payload["error"]
    assert _file_inventory(public_receipts) == evidence_before_replay

    # Freeze a second current request, then change its governed source while
    # the real owner process is deliberately in flight. Final freshness must
    # block activation and retain the previously accepted head.
    accepted_head, _accepted_snapshot = load_observed_model_system(target)
    alpha_path = target / "src" / "alpha.py"
    alpha_text = alpha_path.read_text(encoding="utf-8") + "# second candidate\n"
    alpha_path.write_text(alpha_text, encoding="utf-8")
    drift_preparation = dict(preparation)
    drift_preparation.update(
        {
            "base_head_fingerprint": accepted_head.fingerprint,
            "snapshot_id": "snapshot:public-alpha-drift",
            "revision_set_id": "revision:public-alpha-drift",
            "task_id": "task:public-alpha-drift",
            "activation_receipt_id": "activation:public-alpha-drift",
            "effective_intent_transitions": [
                item.to_dict() for item in _current_intent_retain_transitions(target)
            ],
        }
    )
    drift_raw = json.dumps(drift_preparation, sort_keys=True).encode("utf-8")
    drift_preparation_path = target / "drift-preparation.json"
    drift_preparation_path.write_bytes(drift_raw)
    drift_request_path = target / "drift-change-request.json"
    drift_request_path.write_text(
        json.dumps(
            {
                "operation": "change",
                "target_id": accepted_head.system_id,
                "scope": ["alpha"],
                "expected_current": accepted_head.fingerprint,
                "bootstrap": False,
                "revision_input": {
                    "path": drift_preparation_path.relative_to(target).as_posix(),
                    "sha256": hashlib.sha256(drift_raw).hexdigest(),
                },
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (target / "trigger-alpha-source-drift").write_text("drift", encoding="utf-8")
    drift_completed = _run_public_change(target, drift_request_path)
    assert drift_completed.returncode == 1, drift_completed.stderr or drift_completed.stdout
    drift_payload = json.loads(drift_completed.stdout)
    assert drift_payload["status"] == "blocked"
    assert drift_payload.get("reason") == "owner_execution_failed_or_source_drifted", drift_payload
    assert drift_payload["producer_count"] >= 1
    assert drift_payload["write_count"] == 0
    assert load_observed_model_system(target)[0] == accepted_head


def test_two_model_consumer_first_adoption_is_current_and_basic_navigation_is_read_only(tmp_path: Path):
    target, staging = _consumer_roots(tmp_path)
    source_before = {
        relative: (target / relative).read_bytes()
        for relative in (
            "docs/consumer-design.md",
            ".flowguard/models/owners/alpha/model.py",
            ".flowguard/models/owners/beta/model.py",
        )
    }

    report = _adopt(target, staging)
    assert report["status"] == "pass"
    head, snapshot = load_observed_model_system(target)
    assert head.generation == 2
    assert snapshot.subject_lane == SUBJECT_OBSERVED_IMPLEMENTATION
    assert snapshot.lifecycle == LIFECYCLE_ACTIVE
    state = load_current_model_authority_state(target)
    assert state.accepted_revision is not None
    assert any(
        relation.kind == "depends_on"
        and relation.source.endpoint_id == "model:alpha"
        and relation.target.endpoint_id == "parent:beta"
        for relation in snapshot.relations
    )

    for model_id in _MODEL_IDS:
        navigation = read_selected_model_closure(
            target,
            selected_model_ids=(model_id,),
            authority_state=state,
        )
        assert navigation.selected_model_ids == (model_id,)
        assert navigation.authority_integrity == "pass"
        assert navigation.selected_source_currentness == "current"
        assert navigation.execution_evidence_status == "not_run"
        assert navigation.producer_count == 0
        assert navigation.write_count == 0

    assert {
        relative: (target / relative).read_bytes()
        for relative in source_before
    } == source_before


def test_public_read_returns_bounded_selected_map_without_writing(tmp_path: Path):
    target, staging = _consumer_roots(tmp_path)
    _adopt(target, staging)
    head, _snapshot = load_observed_model_system(target)
    request_path = target / "read-request.json"
    request_path.write_text(
        json.dumps(
            {
                "operation": "read",
                "target_id": head.system_id,
                "scope": ["alpha"],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    authority_root = target / ".flowguard"
    before = _file_inventory(authority_root)
    completed = _run_public_read(target, request_path)

    assert completed.returncode == 0, completed.stderr or completed.stdout
    assert len(completed.stdout.encode("utf-8")) <= 8192
    payload = json.loads(completed.stdout)
    assert payload["status"] == "pass"
    assert payload["target_id"] == head.system_id
    assert payload["requested_model_ids"] == ["alpha"]
    assert payload["selected_model_ids"] == ["alpha"]
    assert payload["authority_integrity"] == "pass"
    assert payload["selected_source_currentness"] == "current"
    assert payload["execution_evidence_status"] == "not_run"
    assert payload["required_count"] == 0
    assert payload["run_count"] == 0
    assert payload["reused_count"] == 0
    assert payload["producer_count"] == 0
    assert payload["write_count"] == 0
    assert [row["model_id"] for row in payload["map"]["models"]] == ["alpha"]
    assert payload["map"]["models"][0]["model_path"]
    assert payload["map"]["models"][0]["runner_path"]
    assert payload["map"]["models"][0]["input_paths"]
    assert payload["map"]["intents"]
    assert _file_inventory(authority_root) == before


def test_public_read_preserves_stale_state_and_rejects_invalid_scope_without_writing(
    tmp_path: Path,
):
    target, staging = _consumer_roots(tmp_path)
    _adopt(target, staging)
    head, _snapshot = load_observed_model_system(target)
    request_path = target / "read-request.json"
    authority_root = target / ".flowguard"

    request_path.write_text(
        json.dumps(
            {
                "operation": "read",
                "target_id": head.system_id,
                "scope": ["unknown"],
            }
        ),
        encoding="utf-8",
    )
    before_invalid = _file_inventory(authority_root)
    invalid = _run_public_read(target, request_path)
    assert invalid.returncode == 1
    invalid_payload = json.loads(invalid.stdout)
    assert invalid_payload["status"] == "blocked"
    assert "unknown model IDs" in invalid_payload["error"]
    assert invalid_payload["producer_count"] == 0
    assert _file_inventory(authority_root) == before_invalid

    request_path.write_text(
        json.dumps(
            {
                "operation": "read",
                "target_id": head.system_id,
                "scope": ["alpha"],
            }
        ),
        encoding="utf-8",
    )
    (target / "src" / "alpha.py").write_text(
        "def classify(value):\n    return 'changed'\n",
        encoding="utf-8",
    )
    before_stale = _file_inventory(authority_root)
    stale = _run_public_read(target, request_path)
    assert stale.returncode == 0, stale.stderr or stale.stdout
    stale_payload = json.loads(stale.stdout)
    assert stale_payload["status"] == "pass"
    assert stale_payload["selected_source_currentness"] == "stale"
    assert stale_payload["stale_obligations"]
    assert stale_payload["as_of"]["authority_head_fingerprint"] == head.fingerprint
    assert stale_payload["write_count"] == 0
    assert _file_inventory(authority_root) == before_stale


def test_public_read_rejects_non_exact_request_and_missing_current(tmp_path: Path):
    target, _staging = _consumer_roots(tmp_path)
    request_path = target / "read-request.json"
    request_path.write_text(
        json.dumps(
            {
                "operation": "read",
                "target_id": "consumer",
                "scope": ["alpha"],
                "bootstrap": True,
            }
        ),
        encoding="utf-8",
    )
    before = _file_inventory(target / ".flowguard")

    invalid = _run_public_read(target, request_path)
    assert invalid.returncode == 1
    invalid_payload = json.loads(invalid.stdout)
    assert invalid_payload["status"] == "blocked"
    assert "fields are not exact-current" in invalid_payload["error"]
    assert _file_inventory(target / ".flowguard") == before

    request_path.write_text(
        json.dumps(
            {
                "operation": "read",
                "target_id": "consumer",
                "scope": ["alpha"],
            }
        ),
        encoding="utf-8",
    )
    no_current = _run_public_read(target, request_path)
    assert no_current.returncode == 1
    no_current_payload = json.loads(no_current.stdout)
    assert no_current_payload["status"] == "blocked"
    assert no_current_payload["reason"] == "current_model_missing"
    assert no_current_payload["current_authority"] == "missing"
    assert no_current_payload["producer_count"] == 0
    assert no_current_payload["execution_evidence_status"] == "not_run"
    assert no_current_payload["blockers"] == ["current_model_missing"]
    assert _file_inventory(target / ".flowguard") == before


def test_unrelated_model_drift_keeps_beta_map_and_selected_alpha_is_explicitly_stale(tmp_path: Path):
    target, staging = _consumer_roots(tmp_path)
    _adopt(target, staging)
    (target / ".flowguard" / "models" / "owners" / "alpha" / "model.py").write_text(
        "MODEL_ID = 'alpha'\nBOUNDARY = ('start', 'changed')\n",
        encoding="utf-8",
    )

    beta = read_selected_model_closure(target, selected_model_ids=("beta",))
    assert beta.selected_model_ids == ("beta",)
    assert beta.selected_source_currentness == "current"
    assert beta.producer_count == 0
    assert beta.write_count == 0

    alpha = read_selected_model_closure(target, selected_model_ids=("alpha",))
    assert alpha.selected_model_ids == ("alpha",)
    assert alpha.selected_source_currentness == "stale"
    assert any(item.startswith("selected_source_stale:") for item in alpha.stale_obligations)
    assert alpha.producer_count == 0
    assert alpha.write_count == 0


def test_first_adoption_requires_each_model_intent_and_leaves_target_without_authority(tmp_path: Path):
    target, staging = _consumer_roots(tmp_path)
    with pytest.raises(ModelAuthorityError, match="owners lack"):
        _adopt(target, staging, include_beta=False)
    assert "[model_authority]" not in (target / ".flowguard" / "project.toml").read_text(
        encoding="utf-8"
    )


def test_consumer_runners_execute_business_models_and_independent_connection_owner(tmp_path: Path):
    target, staging = _consumer_roots(tmp_path)
    report, _receipt_root = _prepare_parent(staging)
    assert report.status == "pass", report.to_dict()
    results = {item.model_id: item for item in report.results}
    assert set(results) == set(_MODEL_IDS)
    assert results["alpha"].producer_invocations == 1
    assert results["beta"].producer_invocations == 1
    assert results["alpha_beta_connection"].producer_invocations == 1
    assert {
        "case:alpha:good-negative",
        "case:alpha:good-zero",
        "case:alpha:good-positive",
        "case:alpha:known-bad",
    } <= set(results["alpha"].executed_case_ids)
    assert {
        "case:alpha_beta_connection:join-negative",
        "case:alpha_beta_connection:join-zero",
        "case:alpha_beta_connection:join-positive",
    } <= set(results["alpha_beta_connection"].executed_case_ids)
    assert all(item.native_case_verification and item.native_case_verification.ok for item in results.values())
    # The independent connection runner imported the actual source functions;
    # the parent receipt must include all three exact owners.
    assert json.loads(
        (staging / "work" / "model-parent" / "report.json").read_text(
            encoding="utf-8"
        )
    )["status"] == "pass"


def test_affected_alpha_update_reuses_beta_validates_connection_and_activates_once(
    tmp_path: Path,
):
    target, staging = _consumer_roots(tmp_path)
    _adopt(target, staging)
    receipt_root = staging / "work" / "model-owner-receipts"
    original_head, _original_snapshot = load_observed_model_system(target)

    # This is a real behavior refinement: bool is no longer accepted as a
    # numeric positive value.  The existing good/bad native cases still run
    # against the actual implementation and the typed alpha->beta connection
    # must be carried into the affected closure.
    (target / "src" / "alpha.py").write_text(
        "def classify(value: int) -> str:\n"
        "    if isinstance(value, bool) or not isinstance(value, int):\n"
        "        raise TypeError('value must be int')\n"
        "    if value < 0:\n"
        "        return 'negative'\n"
        "    if value == 0:\n"
        "        return 'zero'\n"
        "    return 'positive'\n",
        encoding="utf-8",
    )
    stale = read_selected_model_closure(target, selected_model_ids=("alpha",))
    unrelated = read_selected_model_closure(target, selected_model_ids=("beta",))
    assert stale.selected_source_currentness == "stale"
    assert unrelated.selected_source_currentness == "current"
    assert stale.producer_count == unrelated.producer_count == 0

    parent, candidate, revision, built = _prepare_affected_update(
        target,
        receipt_root=receipt_root,
        snapshot_id="snapshot:consumer-affected-update",
        output_name="consumer-affected-update",
    )
    results = {item.model_id: item for item in parent.results}
    assert results["alpha"].execution_disposition == "execute"
    assert results["alpha"].producer_invocations == 1
    assert results["beta"].execution_disposition == "reuse_current"
    assert results["beta"].producer_invocations == 0
    assert results["alpha_beta_connection"].execution_disposition == "execute"
    assert results["alpha_beta_connection"].producer_invocations == 1
    assert built.affected_owner_routes == (
        "model_mesh_maintenance",
        "model_test_alignment",
    )
    assert (
        "model_relation:relation:semantic-cross-boundary-support:alpha:parent:alpha_beta_connection"
        in revision.affected_closure_ids
    )
    assert "model_instance:model:beta" in revision.affected_closure_ids

    current_head, _receipt = activate_model_revision_set(
        target,
        candidate,
        revision,
        receipt_id="activation:consumer-affected-update",
    )
    assert current_head.generation == original_head.generation + 1
    assert read_selected_model_closure(
        target, selected_model_ids=("alpha",)
    ).selected_source_currentness == "current"
    assert read_selected_model_closure(
        target, selected_model_ids=("beta",)
    ).selected_source_currentness == "current"

    # Replaying the same accepted transition is a stale CAS loser.  It must
    # not produce a second generation or overwrite the winner.
    with pytest.raises(ModelAuthorityError, match="changed|rebase|base snapshot"):
        activate_model_revision_set(
            target,
            candidate,
            revision,
            receipt_id="activation:consumer-affected-update-loser",
        )
    assert load_observed_model_system(target)[0] == current_head


def test_report_task_and_repeat_reads_do_not_reopen_terminal_consumer_work(
    tmp_path: Path,
):
    target, staging = _consumer_roots(tmp_path)
    _adopt(target, staging)
    manifest_path = target / ".flowguard" / "project.toml"
    authority_root = target / ".flowguard" / "models" / "authority"
    target_evidence_root = target / ".flowguard" / "evidence"
    receipt_root = staging / "work" / "model-owner-receipts"
    before_manifest = manifest_path.read_bytes()
    before_evidence = _file_inventory(
        authority_root,
        target_evidence_root,
        receipt_root,
    )

    report_path = target / "reports" / "consumer-status.md"
    task_path = target / "tasks" / "consumer-checklist.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    task_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("consumer local validation complete\n", encoding="utf-8")
    task_path.write_text("- [x] read current model map\n", encoding="utf-8")

    reads = tuple(
        read_selected_model_closure(target, selected_model_ids=("alpha",))
        for _ in range(3)
    )
    assert all(item.authority_integrity == "pass" for item in reads)
    assert all(item.selected_source_currentness == "current" for item in reads)
    assert all(item.producer_count == 0 and item.write_count == 0 for item in reads)
    assert manifest_path.read_bytes() == before_manifest
    assert _file_inventory(
        authority_root,
        target_evidence_root,
        receipt_root,
    ) == before_evidence
    assert not (target / ".flowguard" / "evidence" / "completion-epochs").exists()
    assert not (target / ".flowguard" / "evidence" / "validation-owners" / "leases").exists()


def test_missing_exact_leaf_evidence_is_finite_and_never_publishes_target_head(
    tmp_path: Path,
):
    target, staging = _consumer_roots(tmp_path)
    parent, receipt_root = _prepare_parent(staging)
    beta_result = next(item for item in parent.results if item.model_id == "beta")
    Path(beta_result.receipt_path).unlink()
    before_manifest = (target / ".flowguard" / "project.toml").read_bytes()

    with pytest.raises(ModelAuthorityError) as raised:
        _publish_initial(
            target,
            staging,
            parent=parent,
            receipt_root=receipt_root,
        )

    assert any(
        token in str(raised.value).casefold()
        for token in ("missing", "unavailable", "current receipt")
    )
    assert (target / ".flowguard" / "project.toml").read_bytes() == before_manifest
    assert "[model_authority]" not in before_manifest.decode("utf-8")


def test_unsafe_authority_path_and_corrupt_object_return_bounded_diagnostics(
    tmp_path: Path,
):
    unsafe_target, unsafe_staging = _consumer_roots(tmp_path / "unsafe")
    _adopt(unsafe_target, unsafe_staging)
    unsafe_manifest = unsafe_target / ".flowguard" / "project.toml"
    unsafe_text = unsafe_manifest.read_text(encoding="utf-8")
    unsafe_lines = tuple(
        'observed_snapshot_path = "../outside.json"'
        if line.startswith("observed_snapshot_path = ")
        else line
        for line in unsafe_text.splitlines()
    )
    unsafe_manifest.write_text("\n".join(unsafe_lines) + "\n", encoding="utf-8")
    unsafe = read_selected_model_closure(
        unsafe_target, selected_model_ids=("alpha",)
    )
    assert unsafe.authority_integrity == "blocked"
    assert unsafe.producer_count == 0 and unsafe.write_count == 0
    assert "repository-relative" in unsafe.findings[0]["message"]

    corrupt_target, corrupt_staging = _consumer_roots(tmp_path / "corrupt")
    _adopt(corrupt_target, corrupt_staging)
    _head, snapshot = load_observed_model_system(corrupt_target)
    snapshot_path = (
        corrupt_target
        / ".flowguard"
        / "models"
        / "authority"
        / "snapshots"
        / f"{snapshot.fingerprint.split(':', 1)[1]}.json"
    )
    manifest_before = (corrupt_target / ".flowguard" / "project.toml").read_bytes()
    snapshot_path.write_text("{", encoding="utf-8")
    corrupt = read_selected_model_closure(
        corrupt_target, selected_model_ids=("alpha",)
    )
    assert corrupt.authority_integrity == "blocked"
    assert corrupt.producer_count == 0 and corrupt.write_count == 0
    assert "cannot load model-system snapshot" in corrupt.findings[0]["message"]
    assert (corrupt_target / ".flowguard" / "project.toml").read_bytes() == manifest_before


def test_git_timeout_is_terminal_cleanup_confirmed_and_not_retried(
    tmp_path: Path,
):
    target, _staging = _consumer_roots(tmp_path)
    terminal = run_supervised_bytes(
        (sys.executable, "-c", "import time; time.sleep(60)"),
        cwd=target,
        timeout_seconds=0.05,
        grace_seconds=0.05,
    )
    assert terminal.timed_out
    assert terminal.cleanup_confirmed
    assert terminal.descendant_process_ids == ()

    with mock.patch.object(
        validation_ownership,
        "run_supervised_bytes",
        return_value=terminal,
    ) as git_call:
        with pytest.raises(validation_ownership.GitQueryTimeout) as raised:
            validation_ownership.resolve_input_manifest(
                target,
                ("src/**/*.py",),
            )

    assert raised.value.code == "git_query_timeout"
    assert raised.value.cleanup_confirmed
    assert git_call.call_count == 1


def test_required_connection_failure_is_terminal_and_preserves_current_pointer(
    tmp_path: Path,
):
    target, staging = _consumer_roots(tmp_path)
    _adopt(target, staging)
    receipt_root = staging / "work" / "model-owner-receipts"
    manifest_path = target / ".flowguard" / "project.toml"
    before_manifest = manifest_path.read_bytes()
    before_head, _snapshot = load_observed_model_system(target)
    join_path = target / "src" / "join.py"
    join_path.write_text(
        join_path.read_text(encoding="utf-8").replace(
            "'zero': False",
            "'zero': True",
        ),
        encoding="utf-8",
    )

    report = run_manifest_regressions(
        target,
        tier="full",
        jobs=1,
        output_dir=target / "work" / "required-connection-failure",
        receipt_dir=receipt_root,
        require_executed_case_ids=True,
    )
    results = {item.model_id: item for item in report.results}
    assert report.status == "fail"
    assert results["alpha"].execution_disposition == "reuse_current"
    assert results["alpha"].producer_invocations == 0
    assert results["beta"].execution_disposition == "reuse_current"
    assert results["beta"].producer_invocations == 0
    assert results["alpha_beta_connection"].status == "fail"
    assert results["alpha_beta_connection"].producer_invocations == 1
    assert "model.nonzero_exit" in results["alpha_beta_connection"].finding_codes
    assert manifest_path.read_bytes() == before_manifest
    assert load_observed_model_system(target)[0] == before_head
