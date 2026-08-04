from types import SimpleNamespace
from unittest import mock

from flowguard.__main__ import (
    _compact_self_architecture_reduction_payload,
    _run_flowguard_self_blueprint_check_command,
)
from flowguard.architecture_reduction import ROUTE_STRUCTURE_MESH
from flowguard.self_architecture_reduction import (
    _reverse_call_alias_index,
    review_flowguard_self_architecture_reduction,
)


def _bundle(*, ok: bool = True):
    surfaces = tuple(
        SimpleNamespace(
            surface_id=f"surface:{index:02d}",
            path="flowguard/large.py",
            line_end=100 + index,
            structure_fingerprint=f"sha256:shape:{index:02d}",
            roles=(),
            surface_kind="function",
        )
        for index in range(151)
    )
    inventory = SimpleNamespace(
        surfaces=surfaces,
        required_surface_ids=tuple(row.surface_id for row in surfaces),
        inventory_fingerprint="sha256:inventory",
    )
    behavior_report = SimpleNamespace(
        contracts=(),
        fingerprint="sha256:behavior",
    )
    return SimpleNamespace(
        ok=ok,
        inventory=inventory,
        behavior_report=behavior_report,
        manifest=SimpleNamespace(fingerprint="sha256:blueprint"),
        qualification=SimpleNamespace(static_fingerprint="sha256:qualification"),
        static_readiness=SimpleNamespace(
            fingerprint="sha256:readiness"
        ),
    )


def test_self_reduction_has_complete_denominator_and_never_auto_proves_similarity():
    report = review_flowguard_self_architecture_reduction(
        self_blueprint=_bundle()
    )

    assert report.ok
    assert report.denominator_complete
    assert len(report.candidates) == 1
    assert report.safe_unapplied_candidate_ids == ()
    assert report.candidates[0].proof_status == "risky_keep"
    assert report.candidates[0].target_action == "manual_review"
    assert report.reduction_report.decision == "no_ready_reduction_candidates"
    assert report.fingerprint.startswith("sha256:")


def test_self_reduction_cannot_pass_when_bound_self_blueprint_is_blocked():
    report = review_flowguard_self_architecture_reduction(
        self_blueprint=_bundle(ok=False)
    )
    assert report.status == "blocked"
    assert not report.ok


def test_self_reduction_inventory_covers_routes_adapters_helpers_and_validation_paths():
    rows = (
        SimpleNamespace(
            surface_id="route:a",
            path="flowguard/a.py",
            symbol="run_a",
            line_end=20,
            structure_fingerprint="sha256:route-a",
            roles=("entrypoint",),
            surface_kind="entrypoint",
            calls=("dispatch",),
        ),
        SimpleNamespace(
            surface_id="route:b",
            path="flowguard/b.py",
            symbol="run_b",
            line_end=20,
            structure_fingerprint="sha256:route-b",
            roles=("entrypoint",),
            surface_kind="entrypoint",
            calls=("dispatch",),
        ),
        SimpleNamespace(
            surface_id="adapter:a",
            path="flowguard/a_adapter.py",
            symbol="observe_a",
            line_end=20,
            structure_fingerprint="sha256:adapter-a",
            roles=(),
            surface_kind="function",
            calls=("normalize",),
        ),
        SimpleNamespace(
            surface_id="adapter:b",
            path="flowguard/b_provider.py",
            symbol="observe_b",
            line_end=20,
            structure_fingerprint="sha256:adapter-b",
            roles=(),
            surface_kind="function",
            calls=("normalize",),
        ),
        SimpleNamespace(
            surface_id="helper:a",
            path="flowguard/a.py",
            symbol="_normalize_a",
            line_end=20,
            structure_fingerprint="sha256:helper-a",
            roles=(),
            surface_kind="function",
            calls=("canonical",),
        ),
        SimpleNamespace(
            surface_id="helper:b",
            path="flowguard/b.py",
            symbol="_normalize_b",
            line_end=20,
            structure_fingerprint="sha256:helper-b",
            roles=(),
            surface_kind="function",
            calls=("canonical",),
        ),
        SimpleNamespace(
            surface_id="validation:a",
            path="flowguard/a.py",
            symbol="review_a",
            line_end=20,
            structure_fingerprint="sha256:validation-a",
            roles=(),
            surface_kind="function",
            calls=("qualify", "report"),
        ),
        SimpleNamespace(
            surface_id="validation:b",
            path="flowguard/b.py",
            symbol="check_b",
            line_end=20,
            structure_fingerprint="sha256:validation-b",
            roles=(),
            surface_kind="function",
            calls=("qualify", "report"),
        ),
    )
    bundle = _bundle()
    bundle.inventory.surfaces = rows
    bundle.inventory.required_surface_ids = tuple(row.surface_id for row in rows)

    report = review_flowguard_self_architecture_reduction(self_blueprint=bundle)
    signals = {row.metadata["signal"] for row in report.candidates}

    assert signals >= {
        "duplicate_route",
        "adapter_layer",
        "helper_path",
        "validation_path",
    }
    assert all(row.proof_status == "risky_keep" for row in report.candidates)
    assert report.safe_unapplied_candidate_ids == ()
    assert all(
        row.required_next_route == ROUTE_STRUCTURE_MESH
        for row in report.candidates
        if row.affected_public_entrypoints
    )


def test_self_reduction_reverse_call_index_preserves_exact_short_and_qualified_callers():
    rows = (
        SimpleNamespace(
            surface_id="helper:a",
            path="flowguard/a.py",
            symbol="pkg.a._normalize",
            line_end=20,
            structure_fingerprint="sha256:helper-a",
            roles=(),
            surface_kind="function",
            calls=("canonical",),
        ),
        SimpleNamespace(
            surface_id="helper:b",
            path="flowguard/b.py",
            symbol="pkg.b._normalize",
            line_end=20,
            structure_fingerprint="sha256:helper-b",
            roles=(),
            surface_kind="function",
            calls=("canonical",),
        ),
        SimpleNamespace(
            surface_id="caller:short",
            path="flowguard/short.py",
            symbol="call_short",
            line_end=20,
            structure_fingerprint="sha256:caller-short",
            roles=(),
            surface_kind="function",
            calls=("_normalize",),
        ),
        SimpleNamespace(
            surface_id="caller:qualified",
            path="flowguard/qualified.py",
            symbol="call_qualified",
            line_end=20,
            structure_fingerprint="sha256:caller-qualified",
            roles=(),
            surface_kind="function",
            calls=("pkg.a._normalize",),
        ),
        SimpleNamespace(
            surface_id="caller:unrelated",
            path="flowguard/unrelated.py",
            symbol="call_unrelated",
            line_end=20,
            structure_fingerprint="sha256:caller-unrelated",
            roles=(),
            surface_kind="function",
            calls=("normalize_other",),
        ),
    )
    bundle = _bundle()
    bundle.inventory.surfaces = rows
    bundle.inventory.required_surface_ids = tuple(row.surface_id for row in rows)

    report = review_flowguard_self_architecture_reduction(self_blueprint=bundle)
    helper_candidate = next(
        row for row in report.candidates if row.metadata["signal"] == "helper_path"
    )

    assert helper_candidate.metadata["caller_ids"] == (
        "caller:qualified",
        "caller:short",
    )


def test_reverse_call_alias_index_reads_each_surface_call_list_once():
    class CountedSurface:
        def __init__(self, index: int) -> None:
            self.surface_id = f"surface:{index:04d}"
            self.call_reads = 0
            self._calls = (f"pkg.call_{index % 7}", "shared")

        @property
        def calls(self):
            self.call_reads += 1
            return self._calls

    surfaces = tuple(CountedSurface(index) for index in range(500))

    exact, short = _reverse_call_alias_index(surfaces)

    assert all(row.call_reads == 1 for row in surfaces)
    assert len(exact["shared"]) == 500
    assert len(short["shared"]) == 500


def test_composed_self_check_builds_blueprint_once_and_reuses_exact_bundle():
    bundle = SimpleNamespace(
        ok=True,
        manifest=SimpleNamespace(fingerprint="sha256:blueprint"),
    )
    bundle.to_dict = mock.Mock(return_value={"ok": True, "fingerprint": "blueprint"})
    reduction = SimpleNamespace(ok=True)
    reduction.to_dict = mock.Mock(
        return_value={
            "ok": True,
            "self_blueprint_fingerprint": "sha256:blueprint",
        }
    )
    args = SimpleNamespace(
        root=".",
        compact=False,
        json=True,
        include_architecture_reduction=True,
    )

    with (
        mock.patch(
            "flowguard.self_blueprint.build_flowguard_self_blueprint",
            return_value=bundle,
        ) as build,
        mock.patch(
            "flowguard.self_architecture_reduction.review_flowguard_self_architecture_reduction",
            return_value=reduction,
        ) as review,
        mock.patch("flowguard.__main__._emit_payload") as emit,
    ):
        exit_code = _run_flowguard_self_blueprint_check_command(args)

    assert exit_code == 0
    build.assert_called_once_with(".")
    review.assert_called_once_with(".", self_blueprint=bundle)
    emitted = emit.call_args.args[0]
    assert emitted["architecture_reduction_review"]["ok"] is True
    assert emitted["composed_self_maintenance_review"] is True


def test_composed_self_check_fails_when_reduction_review_is_blocked():
    bundle = SimpleNamespace(
        ok=True,
        manifest=SimpleNamespace(fingerprint="sha256:blueprint"),
    )
    bundle.to_dict = mock.Mock(return_value={"ok": True, "fingerprint": "blueprint"})
    reduction = SimpleNamespace(ok=False)
    reduction.to_dict = mock.Mock(
        return_value={
            "ok": False,
            "self_blueprint_fingerprint": "sha256:blueprint",
        }
    )
    args = SimpleNamespace(
        root=".",
        compact=False,
        json=True,
        include_architecture_reduction=True,
    )

    with (
        mock.patch(
            "flowguard.self_blueprint.build_flowguard_self_blueprint",
            return_value=bundle,
        ),
        mock.patch(
            "flowguard.self_architecture_reduction.review_flowguard_self_architecture_reduction",
            return_value=reduction,
        ),
        mock.patch("flowguard.__main__._emit_payload"),
    ):
        exit_code = _run_flowguard_self_blueprint_check_command(args)

    assert exit_code == 1


def test_compact_reduction_payload_never_expands_full_report():
    report = SimpleNamespace(
        schema_version="flowguard.self_architecture_reduction_review.v2",
        status="pass",
        ok=True,
        fingerprint="sha256:reduction",
        self_blueprint_fingerprint="sha256:blueprint",
        candidate_inventory_fingerprint="sha256:candidates",
        candidates=(),
        denominator_complete=True,
        safe_unapplied_candidate_ids=(),
        reduction_report=SimpleNamespace(decision="retain", required_next_routes=()),
        claim_boundary="bounded",
        to_dict=mock.Mock(side_effect=AssertionError("full report expanded")),
    )

    payload = _compact_self_architecture_reduction_payload(report)

    assert payload["fingerprint"] == "sha256:reduction"
    report.to_dict.assert_not_called()


def test_compact_composed_self_check_never_expands_full_blueprint():
    bundle = SimpleNamespace(
        ok=True,
        manifest=SimpleNamespace(fingerprint="sha256:blueprint"),
        behavior_report=SimpleNamespace(
            owner_structure_status="complete",
            behavior_closure_status="complete",
            coverage_edges=(),
            findings=(),
        ),
        resource_inventory=SimpleNamespace(complete=True),
        intent_inventory=SimpleNamespace(complete=True),
        target_system_report=SimpleNamespace(
            status="complete",
            fingerprint="sha256:target",
        ),
        static_readiness=SimpleNamespace(
            status="ready",
        ),
        understanding_summary=SimpleNamespace(
            deepest_proven_layer="static_blueprint",
            first_gap=None,
            gap_count=0,
        ),
        test_inventory=SimpleNamespace(nodes=(), required_node_ids=()),
        binding_report=SimpleNamespace(findings=()),
        to_dict=mock.Mock(side_effect=AssertionError("full blueprint expanded")),
    )
    reduction = SimpleNamespace(
        schema_version="flowguard.self_architecture_reduction_review.v2",
        status="pass",
        ok=True,
        fingerprint="sha256:reduction",
        self_blueprint_fingerprint="sha256:blueprint",
        candidate_inventory_fingerprint="sha256:candidates",
        candidates=(),
        denominator_complete=True,
        safe_unapplied_candidate_ids=(),
        reduction_report=SimpleNamespace(decision="retain", required_next_routes=()),
        claim_boundary="bounded",
        to_dict=mock.Mock(side_effect=AssertionError("full reduction expanded")),
    )
    args = SimpleNamespace(
        root=".",
        compact=True,
        json=True,
        include_architecture_reduction=True,
    )

    with (
        mock.patch(
            "flowguard.self_blueprint.build_flowguard_self_blueprint",
            return_value=bundle,
        ),
        mock.patch(
            "flowguard.self_architecture_reduction.review_flowguard_self_architecture_reduction",
            return_value=reduction,
        ),
        mock.patch("flowguard.__main__._emit_payload") as emit,
    ):
        exit_code = _run_flowguard_self_blueprint_check_command(args)

    assert exit_code == 0
    bundle.to_dict.assert_not_called()
    reduction.to_dict.assert_not_called()
    assert emit.call_args.args[0]["composed_self_maintenance_review"] is True
