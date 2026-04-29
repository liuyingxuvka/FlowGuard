"""Real domain-model bindings for the durable problem corpus.

This module replaces the Phase 10.8 generic executable template with
workflow-family-specific abstract models. The implementation intentionally
keeps the model finite, deterministic, and standard-library-only.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from flowguard.core import FunctionResult, Invariant, InvariantResult
from flowguard.contract import FunctionContract, check_trace_contracts
from flowguard.executable import (
    ExecutableCaseResult,
    ExecutableCorpusReport,
    build_executable_corpus_report,
)
from flowguard.loop import GraphEdge, LoopCheckConfig, LoopCheckReport, check_loops
from flowguard.progress import ProgressCheckConfig, ProgressCheckReport, check_progress
from flowguard.review import OracleReviewResult, review_scenario
from flowguard.scenario import Scenario, ScenarioExpectation
from flowguard.workflow import Workflow

from .matrix import build_problem_corpus
from .taxonomy import WORKFLOW_FAMILIES
from flowguard.corpus import ProblemCase, ProblemCorpus


SCENARIO_PASS_KINDS = {"positive_correct_case", "boundary_edge_case"}
SCENARIO_VIOLATION_KINDS = {"negative_broken_case", "invalid_initial_state_case"}
LOOP_KINDS = {"loop_or_stuck_case"}


@dataclass(frozen=True)
class DomainModelSpec:
    workflow_family: str
    model_name: str
    block_names: tuple[str, str, str, str]
    state_slots: tuple[str, ...]
    primary_owner: str
    processing_owner: str
    effect_owner: str
    decision_owner: str
    primary_side_effect: str
    secondary_side_effect: str
    success_action: str = "accept"
    reject_action: str = "reject"
    human_action: str = "needs_human"


@dataclass(frozen=True)
class DomainVariantSpec:
    """One concrete real-model variant inside a workflow family."""

    workflow_family: str
    variant_id: str
    title: str
    block_names: tuple[str, str, str, str]
    state_slots: tuple[str, ...]
    keywords: tuple[str, ...] = ()

    def to_model_spec(self, base: DomainModelSpec) -> DomainModelSpec:
        return DomainModelSpec(
            workflow_family=base.workflow_family,
            model_name=f"{base.model_name}.{self.variant_id}",
            block_names=self.block_names,
            state_slots=tuple(dict.fromkeys(base.state_slots + self.state_slots)),
            primary_owner=base.primary_owner,
            processing_owner=base.processing_owner,
            effect_owner=base.effect_owner,
            decision_owner=base.decision_owner,
            primary_side_effect=base.primary_side_effect,
            secondary_side_effect=base.secondary_side_effect,
            success_action=base.success_action,
            reject_action=base.reject_action,
            human_action=base.human_action,
        )


@dataclass(frozen=True)
class DomainCommand:
    case_id: str
    identity: str
    input_pattern: str
    payload: str
    version: int
    sequence_index: int


@dataclass(frozen=True)
class SourceRecord:
    identity: str
    version: int
    payload: str
    owner: str


@dataclass(frozen=True)
class ProcessAttempt:
    identity: str
    owner: str
    source_version: int
    via_cache: bool = False


@dataclass(frozen=True)
class CacheEntry:
    identity: str
    source_version: int
    value: str
    stale: bool = False


@dataclass(frozen=True)
class SideEffectRecord:
    slot: str
    identity: str
    source_version: int | None
    owner: str
    token: str


@dataclass(frozen=True)
class DecisionRecord:
    identity: str
    action: str
    owner: str
    reason: str


@dataclass(frozen=True)
class TraceLink:
    effect_token: str
    source_identity: str
    source_version: int


@dataclass(frozen=True)
class OwnerWrite:
    owner: str
    slot: str
    identity: str
    allowed: bool


@dataclass(frozen=True)
class LeaseRecord:
    identity: str
    lease_id: str
    owner: str
    active: bool
    completed: bool = False


@dataclass(frozen=True)
class AuditEvent:
    identity: str
    source_token: str
    owner: str


@dataclass(frozen=True)
class TerminalRecord:
    identity: str
    status: str
    owner: str


@dataclass(frozen=True)
class DomainState:
    case_id: str
    workflow_family: str
    source_records: tuple[SourceRecord, ...] = ()
    process_attempts: tuple[ProcessAttempt, ...] = ()
    cache_entries: tuple[CacheEntry, ...] = ()
    side_effects: tuple[SideEffectRecord, ...] = ()
    decisions: tuple[DecisionRecord, ...] = ()
    trace_links: tuple[TraceLink, ...] = ()
    owner_writes: tuple[OwnerWrite, ...] = ()
    leases: tuple[LeaseRecord, ...] = ()
    audit_events: tuple[AuditEvent, ...] = ()
    terminal_records: tuple[TerminalRecord, ...] = ()
    invalid_transitions: tuple[str, ...] = ()


@dataclass(frozen=True)
class DomainAccepted:
    case_id: str
    identity: str
    payload: str
    version: int
    input_pattern: str


@dataclass(frozen=True)
class DomainProcessed:
    case_id: str
    identity: str
    payload: str
    source_version: int
    from_cache: bool


@dataclass(frozen=True)
class DomainEffect:
    case_id: str
    identity: str
    effect_tokens: tuple[str, ...]


@dataclass(frozen=True)
class DomainOutcome:
    case_id: str
    identity: str
    status: str


@dataclass(frozen=True)
class IncompatibleDomainOutput:
    case_id: str
    identity: str
    reason: str


@dataclass(frozen=True)
class RealLoopState:
    case_id: str
    workflow_family: str
    phase: str


def _spec(
    workflow_family: str,
    model_name: str,
    block_names: tuple[str, str, str, str],
    state_slots: tuple[str, ...],
) -> DomainModelSpec:
    family = next(item for item in WORKFLOW_FAMILIES if item["name"] == workflow_family)
    actors = tuple(str(item) for item in family["actors"])
    side_effects = tuple(str(item) for item in family["side_effects"])
    return DomainModelSpec(
        workflow_family=workflow_family,
        model_name=model_name,
        block_names=block_names,
        state_slots=state_slots + side_effects,
        primary_owner=actors[0],
        processing_owner=actors[1] if len(actors) > 1 else actors[0],
        effect_owner=actors[2] if len(actors) > 2 else actors[-1],
        decision_owner=actors[-1],
        primary_side_effect=side_effects[0],
        secondary_side_effect=side_effects[-1],
    )


MODEL_SPECS: dict[str, DomainModelSpec] = {
    "crud_lifecycle": _spec(
        "crud_lifecycle",
        "EntityLifecycleModel",
        ("CommandRouter", "EntityValidator", "VersionedEntityStore", "AuditTrailWriter"),
        ("entity_id", "version", "lifecycle_status", "validated_payload_hash", "audit_sequence"),
    ),
    "approval_review_workflow": _spec(
        "approval_review_workflow",
        "ApprovalReviewModel",
        ("SubmissionStore", "ReviewAssignment", "ReviewerDecision", "NotificationOutbox"),
        ("submission_id", "reviewer_id", "decision_reason", "policy_version", "notification_id"),
    ),
    "task_queue_leasing": _spec(
        "task_queue_leasing",
        "TaskQueueLeaseModel",
        ("ReadyQueue", "LeaseAllocator", "WorkExecutor", "CompletionRegistry"),
        ("task_id", "lease_id", "lease_owner", "attempt", "completion_token"),
    ),
    "retry_side_effect": _spec(
        "retry_side_effect",
        "RetrySideEffectModel",
        ("IdempotencyKeyGate", "LocalIntentStore", "ExternalSendAdapter", "ObservationRecorder"),
        ("idempotency_key", "request_hash", "external_operation_id", "send_count", "retry_window"),
    ),
    "cache_materialized_view": _spec(
        "cache_materialized_view",
        "CacheMaterializedViewModel",
        ("SourceStore", "InvalidationController", "ProjectionBuilder", "ViewReader"),
        ("source_id", "source_version", "cache_version", "view_version", "derivation_inputs"),
    ),
    "file_import_transform_export": _spec(
        "file_import_transform_export",
        "FilePipelineModel",
        ("FileWatcher", "Parser", "Transformer", "OutputWriter"),
        ("file_id", "parse_status", "transform_token", "output_path", "processing_record_id"),
    ),
    "event_webhook_ingestion": _spec(
        "event_webhook_ingestion",
        "WebhookIngestionModel",
        ("WebhookReceiver", "DeliveryDedupStore", "EventApplier", "DomainUpdateRecorder"),
        ("delivery_id", "event_offset", "dedup_key", "domain_version", "apply_status"),
    ),
    "notification_send_pipeline": _spec(
        "notification_send_pipeline",
        "NotificationSendModel",
        ("NotificationDecision", "TemplateRenderer", "SendAdapter", "DeliveryLogger"),
        ("notification_id", "template_version", "recipient_id", "delivery_id", "send_status"),
    ),
    "payment_billing_refund": _spec(
        "payment_billing_refund",
        "PaymentLedgerModel",
        ("InvoiceReader", "ChargeGateway", "LedgerWriter", "RefundProcessor"),
        ("invoice_id", "charge_id", "ledger_entry_id", "refund_id", "settlement_status"),
    ),
    "inventory_reservation_allocation": _spec(
        "inventory_reservation_allocation",
        "InventoryReservationModel",
        ("AvailabilityReader", "ReservationStore", "AllocationWriter", "ReleaseController"),
        ("sku", "reservation_id", "available_units", "allocated_units", "release_token"),
    ),
    "scheduler_recurring_job": _spec(
        "scheduler_recurring_job",
        "RecurringJobModel",
        ("CronTrigger", "RunRegistry", "JobWorker", "StatusStore"),
        ("schedule_id", "run_id", "run_window", "worker_token", "status"),
    ),
    "auth_permission_role_transition": _spec(
        "auth_permission_role_transition",
        "PermissionRoleModel",
        ("IdentityStore", "PolicyEvaluator", "PermissionCache", "PolicyAuditWriter"),
        ("principal_id", "role_version", "policy_version", "permission_cache_key", "resource_id"),
    ),
    "session_token_expiration": _spec(
        "session_token_expiration",
        "SessionTokenModel",
        ("SessionStore", "TokenValidator", "ResourceActionGate", "AccessAuditWriter"),
        ("session_id", "token_version", "expiry_state", "resource_id", "access_audit_id"),
    ),
    "form_submission_validation": _spec(
        "form_submission_validation",
        "FormSubmissionModel",
        ("FormReceiver", "FieldValidator", "DraftStore", "ConfirmationEmitter"),
        ("form_id", "field_hash", "validation_status", "draft_id", "confirmation_id"),
    ),
    "search_ranking_recommendation": _spec(
        "search_ranking_recommendation",
        "SearchRankingModel",
        ("CandidateSource", "Scorer", "Ranker", "RecommendationRecorder"),
        ("candidate_id", "score_version", "rank_bucket", "recommendation_id", "source_snapshot"),
    ),
    "data_sync_reconciliation": _spec(
        "data_sync_reconciliation",
        "DataSyncReconciliationModel",
        ("RemoteSnapshotReader", "LocalStateReader", "ReconciliationEngine", "SyncCheckpointWriter"),
        ("remote_id", "remote_version", "local_version", "checkpoint", "conflict_policy"),
    ),
    "migration_schema_evolution": _spec(
        "migration_schema_evolution",
        "SchemaMigrationModel",
        ("OldSchemaReader", "Migrator", "CompatibilityWriter", "CompatibilityReader"),
        ("record_id", "old_schema_version", "new_schema_version", "migration_token", "reader_version"),
    ),
    "human_in_the_loop_workflow": _spec(
        "human_in_the_loop_workflow",
        "HumanReviewModel",
        ("AutomatedDecision", "ReviewQueue", "HumanReviewDecision", "FinalActionStore"),
        ("item_id", "uncertainty_bucket", "review_task_id", "reviewer_id", "final_action"),
    ),
    "moderation_triage": _spec(
        "moderation_triage",
        "ModerationTriageModel",
        ("ContentIngest", "PolicyClassifier", "ModerationQueue", "ContentActionWriter"),
        ("content_id", "policy_version", "queue_id", "moderation_action", "content_status"),
    ),
    "classifier_decision_routing_no_api": _spec(
        "classifier_decision_routing_no_api",
        "ClassifierRoutingModel",
        ("AbstractClassifierOutput", "CategoryRouter", "DownstreamHandler", "RoutingRecorder"),
        ("item_id", "category", "route_id", "handler_name", "handler_result"),
    ),
    "document_generation_export": _spec(
        "document_generation_export",
        "DocumentExportModel",
        ("SourceDataReader", "DocumentRenderer", "ExportWriter", "DocumentIndexer"),
        ("document_id", "render_version", "export_path", "index_key", "source_snapshot"),
    ),
    "checkout_onboarding_flow": _spec(
        "checkout_onboarding_flow",
        "CheckoutOnboardingModel",
        ("StepStateReader", "StepValidator", "ProfileOrPaymentStore", "CompletionRecorder"),
        ("flow_id", "step_id", "profile_version", "payment_token", "completion_id"),
    ),
    "audit_compliance_traceability": _spec(
        "audit_compliance_traceability",
        "AuditComplianceModel",
        ("BusinessActionGate", "AuditEventBuilder", "ImmutableLedgerWriter", "TraceabilityReader"),
        ("actor_id", "business_action_id", "audit_event_id", "ledger_sequence", "trace_reason"),
    ),
    "deployment_release_gate": _spec(
        "deployment_release_gate",
        "DeploymentGateModel",
        ("BuildArtifactReader", "GateChecker", "RolloutController", "RollbackRecorder"),
        ("artifact_id", "gate_version", "rollout_id", "environment", "rollback_token"),
    ),
    "configuration_feature_flag_rollout": _spec(
        "configuration_feature_flag_rollout",
        "FeatureFlagRolloutModel",
        ("FlagConfigReader", "FlagValidator", "RolloutSegmentWriter", "ReaderCacheUpdater"),
        ("flag_id", "config_version", "segment_id", "reader_cache_version", "rollout_status"),
    ),
}


VARIANT_BLUEPRINTS: dict[str, tuple[tuple[str, str, tuple[str, ...], tuple[str, ...]], ...]] = {
    "crud_lifecycle": (
        ("create_only_lifecycle", "Create-only lifecycle", ("create_command", "insert_record"), ("single_valid", "create", "missing_required")),
        ("versioned_update", "Versioned update", ("expected_version", "patch_hash"), ("version", "update", "stale")),
        ("soft_delete_tombstone", "Soft delete and tombstone", ("deleted_at", "tombstone"), ("delete", "tombstone", "terminal")),
        ("restore_undelete", "Restore or undelete", ("restore_token", "restore_reason"), ("restore", "recreate", "conflict")),
        ("bulk_import_update", "Bulk import or update", ("batch_id", "row_index"), ("batch", "bulk", "import")),
        ("concurrent_patch_conflict", "Concurrent patch conflict", ("base_revision", "patch_conflict"), ("concurrent", "conflict", "ordering")),
    ),
    "approval_review_workflow": (
        ("single_reviewer", "Single reviewer", ("reviewer_id", "assignment_id"), ("single", "reviewer", "valid")),
        ("multi_reviewer_quorum", "Multi-reviewer quorum", ("quorum_size", "review_votes"), ("quorum", "multi", "conflict")),
        ("delegated_reviewer", "Delegated reviewer", ("delegate_id", "delegation_reason"), ("delegate", "owner", "permission")),
        ("withdraw_resubmit", "Withdraw and resubmit", ("withdrawn_version", "resubmit_token"), ("withdraw", "resubmit", "terminal")),
        ("escalation_timeout", "Escalation timeout", ("deadline_bucket", "escalation_task"), ("timeout", "waiting", "retry")),
        ("override_with_audit", "Override with audit", ("override_reason", "audit_event_id"), ("override", "audit", "policy")),
    ),
    "task_queue_leasing": (
        ("simple_lease", "Simple lease", ("lease_id", "lease_owner"), ("lease", "single", "valid")),
        ("heartbeat_lease", "Lease with heartbeat", ("heartbeat_at", "lease_expires_at"), ("heartbeat", "expiry", "expired")),
        ("delayed_retry", "Delayed retry", ("retry_at", "attempt"), ("retry", "delay", "attempt")),
        ("dead_letter_queue", "Dead-letter queue", ("dead_letter_reason", "max_attempts"), ("dead", "failure", "too_many")),
        ("priority_queue", "Priority queue", ("priority_bucket", "queue_position"), ("priority", "ordering", "interleaving")),
        ("competing_workers", "Competing worker lease", ("worker_id", "claim_token"), ("double_lease", "concurrent", "worker")),
    ),
    "retry_side_effect": (
        ("idempotency_key_request", "Idempotency-key request", ("idempotency_key", "request_hash"), ("idempotency", "same_key")),
        ("external_success_local_failure", "External success with local failure", ("external_operation_id", "local_commit_status"), ("external_success", "partial")),
        ("timeout_then_observe", "Timeout then observe", ("timeout_bucket", "observation_status"), ("timeout", "observe", "ack")),
        ("compensation_workflow", "Compensation workflow", ("compensation_id", "compensation_status"), ("compensation", "rollback")),
        ("duplicate_retry_window", "Duplicate retry window", ("retry_window", "send_count"), ("retry", "duplicate", "replay")),
        ("conflicting_payload_same_key", "Conflicting payload same key", ("request_hash", "conflict_marker"), ("different_key", "conflict", "payload")),
    ),
    "cache_materialized_view": (
        ("read_through_cache", "Read-through cache", ("cache_key", "read_miss"), ("read", "cache")),
        ("write_through_cache", "Write-through cache", ("write_version", "cache_version"), ("write", "version")),
        ("explicit_invalidation", "Explicit invalidation", ("invalidation_token", "invalidated_at"), ("invalidate", "stale")),
        ("projection_rebuild", "Projection rebuild", ("projection_job", "view_version"), ("projection", "rebuild", "materialized")),
        ("delete_tombstone_propagation", "Delete/tombstone propagation", ("source_deleted", "view_tombstone"), ("delete", "tombstone", "privacy")),
        ("stale_replica_repair", "Stale replica repair", ("replica_version", "repair_token"), ("replica", "repair", "stale")),
    ),
    "file_import_transform_export": (
        ("single_file_import", "Single file import", ("file_id", "manifest_hash"), ("file", "single")),
        ("malformed_row_partial_reject", "Malformed row partial reject", ("row_rejections", "parse_status"), ("malformed", "missing_required")),
        ("schema_versioned_import", "Schema-versioned import", ("schema_version", "compatibility_output"), ("schema", "version")),
        ("retry_after_partial_export", "Retry after partial export", ("partial_export_token", "retry_token"), ("retry", "partial")),
        ("duplicate_file_replay", "Duplicate file replay", ("file_fingerprint", "dedup_record"), ("duplicate", "replay")),
        ("downstream_writer_incompatibility", "Downstream writer incompatibility", ("writer_schema", "consumer_shape"), ("non_consumable", "downstream", "old_consumer")),
    ),
    "event_webhook_ingestion": (
        ("basic_dedup_webhook", "Basic dedup webhook", ("event_id", "dedup_key"), ("webhook", "dedup")),
        ("out_of_order_events", "Out-of-order events", ("event_offset", "subject_version"), ("out_of_order", "ordering")),
        ("replayed_provider_event", "Replayed provider event", ("provider_delivery_id", "replay_count"), ("replay", "duplicate_delivery")),
        ("provider_conflict", "Provider conflict", ("provider_id", "conflict_marker"), ("provider_conflict", "conflict")),
        ("terminal_subject_late_event", "Terminal subject late event", ("terminal_subject", "late_event"), ("terminal", "late")),
        ("ack_durability_order", "Ack durability order", ("ack_id", "durable_record"), ("ack", "durability", "external")),
    ),
    "notification_send_pipeline": (
        ("single_send", "Single send", ("notification_id", "recipient_id"), ("single", "send")),
        ("suppressed_recipient", "Suppressed recipient", ("suppression_record", "preference_version"), ("suppressed", "denial")),
        ("template_render_failure", "Template render failure", ("template_version", "render_error"), ("template", "malformed")),
        ("provider_timeout_retry", "Provider timeout retry", ("provider_message_id", "timeout_bucket"), ("timeout", "retry")),
        ("idempotent_delivery_log", "Idempotent delivery log", ("delivery_log_id", "idempotency_key"), ("idempotency", "duplicate")),
        ("multi_channel_notification", "Multi-channel notification", ("channel", "channel_policy"), ("multi", "channel", "routing")),
    ),
    "payment_billing_refund": (
        ("simple_charge", "Simple charge", ("invoice_id", "charge_id"), ("charge", "single")),
        ("idempotent_charge_retry", "Idempotent charge retry", ("payment_idempotency_key", "charge_attempt"), ("idempotency", "retry")),
        ("settlement_ledger", "Settlement ledger", ("settlement_id", "ledger_entry_id"), ("ledger", "settlement")),
        ("partial_refund", "Partial refund", ("refund_id", "refund_amount_bucket"), ("refund", "partial")),
        ("refund_without_charge_defense", "Refund without charge defense", ("charge_reference", "refund_guard"), ("refund_without_charge", "invalid")),
        ("gateway_success_local_failure", "Gateway success local failure", ("gateway_observation", "local_commit_status"), ("gateway", "external_success", "partial")),
    ),
    "inventory_reservation_allocation": (
        ("simple_reservation", "Simple reservation", ("reservation_id", "stock_on_hand"), ("reservation", "single")),
        ("reservation_expiry", "Reservation expiry", ("reservation_expiry", "expired_status"), ("expiry", "expired")),
        ("allocation_after_reservation", "Allocation after reservation", ("allocation_id", "reservation_reference"), ("allocation", "allocate")),
        ("release_restore_stock", "Release and restore stock", ("release_token", "restored_units"), ("release", "restore")),
        ("oversell_prevention", "Oversell prevention", ("available_units", "oversell_guard"), ("oversell", "reservation_oversell")),
        ("concurrent_order_reservation", "Concurrent order reservation", ("order_line_id", "concurrent_claim"), ("concurrent", "interleaving")),
    ),
    "scheduler_recurring_job": (
        ("single_scheduled_run", "Single scheduled run", ("schedule_id", "run_window"), ("schedule", "single")),
        ("double_fire_prevention", "Double-fire prevention", ("run_slot", "double_fire_guard"), ("double_fire", "duplicate")),
        ("lease_protected_run", "Lease-protected run", ("lease_id", "worker_token"), ("lease", "worker")),
        ("bounded_retry", "Bounded retry", ("attempt", "max_attempts"), ("retry", "bounded")),
        ("missed_window_recovery", "Missed window recovery", ("missed_window", "recovery_run"), ("missed", "window", "stale")),
        ("terminal_run_mutation_defense", "Terminal run mutation defense", ("terminal_status", "mutation_guard"), ("terminal", "mutated")),
    ),
    "auth_permission_role_transition": (
        ("role_grant", "Role grant", ("role_assignment", "grant_reason"), ("grant", "role")),
        ("role_downgrade_cache_invalidation", "Role downgrade cache invalidation", ("role_version", "cache_invalidation"), ("downgrade", "stale_permission")),
        ("owner_transfer", "Owner transfer", ("old_owner", "new_owner"), ("owner", "transfer")),
        ("admin_override_audit", "Admin override audit", ("override_reason", "policy_audit"), ("override", "audit")),
        ("read_only_denial", "Read-only denial", ("write_scope", "read_only_guard"), ("read_only", "denial")),
        ("stale_policy_cache", "Stale policy cache", ("policy_version", "permission_cache"), ("policy_cache", "stale")),
    ),
    "session_token_expiration": (
        ("valid_token_access", "Valid token access", ("session_id", "token_version"), ("valid", "access")),
        ("expired_token_denial", "Expired token denial", ("expiry_state", "expired_at"), ("expired", "expiry")),
        ("revoked_token_denial", "Revoked token denial", ("revocation_id", "revoked_token"), ("revoked", "denial")),
        ("refresh_flow", "Refresh flow", ("refresh_token", "refresh_status"), ("refresh", "retry")),
        ("scope_resource_mismatch", "Scope/resource mismatch", ("token_scope", "resource_id"), ("scope", "resource", "permission")),
        ("replay_after_expiry", "Replay after expiry", ("replay_token", "expired_replay"), ("replay", "expiry")),
    ),
    "form_submission_validation": (
        ("valid_submit", "Valid submit", ("form_id", "validation_status"), ("valid", "submit")),
        ("invalid_field_reject", "Invalid field reject", ("field_error", "invalid_field"), ("invalid", "malformed")),
        ("draft_save", "Draft save", ("draft_id", "draft_version"), ("draft", "save")),
        ("correction_resubmit", "Correction resubmit", ("correction_count", "resubmit_token"), ("correction", "resubmit")),
        ("idempotent_confirmation", "Idempotent confirmation", ("confirmation_id", "idempotency_key"), ("confirmation", "idempotency")),
        ("schema_versioned_validation", "Schema-versioned validation", ("schema_version", "validation_rule"), ("schema", "version")),
    ),
    "search_ranking_recommendation": (
        ("simple_score_rank", "Simple score/rank", ("score_version", "rank_bucket"), ("score", "rank")),
        ("cached_score_repeat", "Cached score repeat", ("score_cache", "refresh_marker"), ("cached", "repeat", "refresh")),
        ("source_deleted", "Source deleted", ("source_deleted", "suppression_record"), ("deleted", "tombstone")),
        ("conflicting_candidate_identity", "Conflicting candidate identity", ("candidate_alias", "identity_conflict"), ("conflict", "identity")),
        ("suppress_recommendation", "Suppress recommendation", ("suppression_reason", "recommendation_guard"), ("suppression", "ignore")),
        ("refresh_rescore_flow", "Refresh/rescore flow", ("refresh_token", "rescore_attempt"), ("refresh", "rescore")),
    ),
    "data_sync_reconciliation": (
        ("remote_to_local_sync", "Remote-to-local sync", ("remote_version", "local_version"), ("remote", "sync")),
        ("local_newer_than_remote", "Local newer than remote", ("local_newer_marker", "stale_remote"), ("local_newer", "stale")),
        ("tombstone_sync", "Tombstone sync", ("remote_tombstone", "local_tombstone"), ("tombstone", "delete")),
        ("conflict_queue", "Conflict queue", ("conflict_queue_id", "source_authority"), ("conflict", "authority")),
        ("checkpoint_resume", "Checkpoint resume", ("checkpoint", "resume_token"), ("checkpoint", "resume")),
        ("replayed_remote_change", "Replayed remote change", ("change_id", "replay_count"), ("replay", "duplicate")),
    ),
    "migration_schema_evolution": (
        ("one_step_migration", "One-step migration", ("old_schema_version", "new_schema_version"), ("migration", "single")),
        ("multi_step_migration", "Multi-step migration", ("migration_step", "intermediate_version"), ("multi", "step")),
        ("resumable_batch", "Resumable batch", ("batch_id", "migration_checkpoint"), ("resume", "batch")),
        ("compatibility_reader", "Compatibility reader", ("reader_version", "compatibility_output"), ("compatibility", "old_consumer")),
        ("default_value_policy", "Default-value policy", ("default_value_application", "policy_version"), ("default", "policy")),
        ("lossy_field_split_merge", "Lossy field split/merge", ("split_field", "merge_policy"), ("lossy", "split", "merge")),
    ),
    "human_in_the_loop_workflow": (
        ("auto_accept", "Auto-accept", ("confidence_bucket", "auto_decision"), ("auto", "accept")),
        ("auto_reject", "Auto-reject", ("rejection_reason", "auto_decision"), ("auto", "reject")),
        ("uncertain_to_review", "Uncertain to review", ("review_task_id", "uncertainty_bucket"), ("uncertain", "unknown", "review")),
        ("reviewer_override", "Reviewer override", ("reviewer_id", "override_reason"), ("override", "reviewer")),
        ("duplicate_review_task", "Duplicate review task", ("review_task_id", "dedup_key"), ("duplicate", "idempotency")),
        ("review_timeout_escalation", "Review timeout/escalation", ("review_deadline", "escalation_task"), ("timeout", "escalation")),
    ),
    "moderation_triage": (
        ("known_safe_content", "Known safe content", ("content_id", "safe_policy"), ("safe", "valid")),
        ("known_violating_content", "Known violating content", ("violation_policy", "content_action"), ("violating", "action")),
        ("unknown_category_queue", "Unknown category queue", ("unknown_category", "moderation_queue"), ("unknown", "category")),
        ("appeal_review", "Appeal/review", ("appeal_id", "review_record"), ("appeal", "review")),
        ("terminal_action_replay", "Terminal action replay", ("terminal_action", "replay_guard"), ("terminal", "replay")),
        ("policy_version_change", "Policy version change", ("policy_version", "policy_change"), ("policy", "version")),
    ),
    "classifier_decision_routing_no_api": (
        ("known_category_route", "Known category route", ("category", "route_id"), ("known", "category")),
        ("unknown_category_route", "Unknown category route", ("unknown_category", "review_queue"), ("unknown", "unhandled")),
        ("confidence_bucket_review", "Confidence bucket review", ("confidence_bucket", "review_threshold"), ("confidence", "review")),
        ("repeated_classification", "Repeated classification", ("classification_cache", "repeat_key"), ("repeated", "classification")),
        ("conflicting_outputs", "Conflicting outputs", ("output_version", "route_conflict"), ("conflict", "contradictory")),
        ("downstream_handler_incompatibility", "Downstream handler incompatibility", ("handler_name", "handler_input_shape"), ("downstream", "non_consumable")),
    ),
    "document_generation_export": (
        ("simple_render_export", "Simple render/export", ("document_id", "render_version"), ("render", "export")),
        ("redaction_before_export", "Redaction before export", ("redaction_policy", "redacted_snapshot"), ("redaction", "privacy")),
        ("duplicate_export_retry", "Duplicate export retry", ("export_key", "retry_token"), ("duplicate", "retry")),
        ("index_after_export", "Index after export", ("index_key", "export_path"), ("index", "export")),
        ("stale_source_version", "Stale source version", ("source_version", "stale_marker"), ("stale", "source")),
        ("writer_bypass_renderer", "Writer bypass renderer", ("render_token", "writer_guard"), ("bypass", "wrong_owner")),
    ),
    "checkout_onboarding_flow": (
        ("linear_checkout", "Linear checkout", ("flow_id", "step_id"), ("linear", "valid")),
        ("skipped_step_defense", "Skipped step defense", ("required_step", "skip_guard"), ("skipped", "invalid_transition")),
        ("payment_retry", "Payment retry", ("payment_token", "retry_key"), ("payment", "retry")),
        ("profile_update", "Profile update", ("profile_version", "profile_record"), ("profile", "update")),
        ("cancellation_terminal", "Cancellation terminal", ("cancel_reason", "terminal_flow"), ("cancel", "terminal")),
        ("idempotent_completion", "Idempotent completion", ("completion_id", "idempotency_key"), ("completion", "idempotency")),
    ),
    "audit_compliance_traceability": (
        ("action_with_audit", "Action with audit", ("business_action_id", "audit_event_id"), ("audit", "action")),
        ("missing_audit_defense", "Missing audit defense", ("audit_required", "audit_guard"), ("missing_audit", "traceability")),
        ("immutable_ledger", "Immutable ledger", ("ledger_sequence", "append_only"), ("ledger", "immutable")),
        ("override_reason", "Override reason", ("override_reason", "actor_id"), ("override", "reason")),
        ("privacy_delete_propagation", "Privacy/delete propagation", ("privacy_tombstone", "delete_policy"), ("privacy", "delete")),
        ("old_policy_replay", "Old policy replay", ("recorded_policy_version", "replay_policy"), ("old_policy", "replay")),
    ),
    "deployment_release_gate": (
        ("gate_pass_rollout", "Gate pass rollout", ("artifact_id", "gate_result"), ("gate_pass", "rollout")),
        ("gate_fail_block", "Gate fail block", ("gate_failure", "promotion_block"), ("gate_fail", "block")),
        ("rollback", "Rollback", ("rollback_token", "previous_deployment"), ("rollback", "failed")),
        ("stale_artifact_block", "Stale artifact block", ("artifact_digest", "stale_artifact"), ("stale", "artifact")),
        ("multi_environment_rollout", "Multi-environment rollout", ("environment", "rollout_wave"), ("multi", "environment")),
        ("terminal_failed_release", "Terminal failed release", ("terminal_status", "failed_release"), ("terminal", "failed")),
    ),
    "configuration_feature_flag_rollout": (
        ("valid_flag_publish", "Valid flag publish", ("flag_id", "config_version"), ("valid", "publish")),
        ("invalid_config_block", "Invalid config block", ("validation_error", "publish_guard"), ("invalid", "config")),
        ("segment_rollout", "Segment rollout", ("segment_id", "segment_rule"), ("segment", "rollout")),
        ("reader_cache_refresh", "Reader cache refresh", ("reader_cache_version", "cache_refresh"), ("cache", "refresh")),
        ("rollback_kill_switch", "Rollback/kill switch", ("kill_switch", "rollback_version"), ("rollback", "kill")),
        ("stale_version_input", "Stale version input", ("stale_version", "version_guard"), ("stale", "version")),
    ),
}


def _camel(value: str) -> str:
    return "".join(part.capitalize() for part in value.split("_") if part)


def _variant_spec(
    base: DomainModelSpec,
    definition: tuple[str, str, tuple[str, ...], tuple[str, ...]],
) -> DomainVariantSpec:
    variant_id, title, state_slots, keywords = definition
    prefix = _camel(variant_id)
    return DomainVariantSpec(
        workflow_family=base.workflow_family,
        variant_id=variant_id,
        title=title,
        block_names=tuple(f"{prefix}{name}" for name in base.block_names),  # type: ignore[arg-type]
        state_slots=state_slots,
        keywords=keywords,
    )


VARIANT_SPECS: dict[str, tuple[DomainVariantSpec, ...]] = {
    family: tuple(_variant_spec(MODEL_SPECS[family], definition) for definition in definitions)
    for family, definitions in VARIANT_BLUEPRINTS.items()
}


def _metadata_value(case: ProblemCase, key: str, default: str = "") -> str:
    for item_key, value in case.metadata:
        if item_key == key:
            return str(value)
    return default


def validate_model_specs() -> tuple[str, ...]:
    """Return errors if the real-model registry does not cover the corpus families."""

    taxonomy_families = {str(item["name"]) for item in WORKFLOW_FAMILIES}
    spec_families = set(MODEL_SPECS)
    variant_families = set(VARIANT_SPECS)
    errors: list[str] = []
    for name in sorted(taxonomy_families - spec_families):
        errors.append(f"missing model spec for {name}")
    for name in sorted(spec_families - taxonomy_families):
        errors.append(f"model spec has no taxonomy family: {name}")
    for name in sorted(taxonomy_families - variant_families):
        errors.append(f"missing variant specs for {name}")
    for name in sorted(variant_families - taxonomy_families):
        errors.append(f"variant spec has no taxonomy family: {name}")
    for name, spec in MODEL_SPECS.items():
        if len(spec.block_names) != 4:
            errors.append(f"{name} must have four block names")
        if len(set(spec.block_names)) != 4:
            errors.append(f"{name} block names must be unique")
        if len(set(spec.state_slots)) < 5:
            errors.append(f"{name} needs domain state slots")
    for name, variants in VARIANT_SPECS.items():
        if len(variants) != 6:
            errors.append(f"{name} must have six variants")
        variant_ids = [variant.variant_id for variant in variants]
        if len(set(variant_ids)) != 6:
            errors.append(f"{name} variant ids must be unique")
        for variant in variants:
            if len(variant.block_names) != 4:
                errors.append(f"{name}/{variant.variant_id} must have four block names")
            if len(set(variant.block_names)) != 4:
                errors.append(f"{name}/{variant.variant_id} block names must be unique")
            if len(set(variant.state_slots)) < 2:
                errors.append(f"{name}/{variant.variant_id} needs variant state slots")
    return tuple(errors)


_CASE_VARIANT_MAP: dict[str, DomainVariantSpec] | None = None


def _case_variant_map() -> dict[str, DomainVariantSpec]:
    """Return the durable corpus-level case-to-variant assignment."""

    global _CASE_VARIANT_MAP
    if _CASE_VARIANT_MAP is not None:
        return _CASE_VARIANT_MAP

    family_positions: Counter[str] = Counter()
    mapping: dict[str, DomainVariantSpec] = {}
    for corpus_case in build_problem_corpus().cases:
        variants = VARIANT_SPECS[corpus_case.workflow_family]
        index = family_positions[corpus_case.workflow_family]
        mapping[corpus_case.case_id] = variants[index % len(variants)]
        family_positions[corpus_case.workflow_family] += 1
    _CASE_VARIANT_MAP = mapping
    return mapping


def select_variant_for_case(case: ProblemCase) -> DomainVariantSpec:
    """Select the durable real model variant for one corpus case.

    Full-corpus cases use a family-local round-robin assignment so every
    variant receives enough executable pressure. Ad hoc cases keep a stable
    fingerprint fallback.
    """

    assigned = _case_variant_map().get(case.case_id)
    if assigned is not None and assigned.workflow_family == case.workflow_family:
        return assigned

    variants = VARIANT_SPECS[case.workflow_family]
    seed = sum(
        ord(char)
        for char in (
            case.case_id
            + case.workflow_family
            + case.failure_mode
            + case.oracle_type
            + case.case_kind
        )
    )
    return variants[seed % len(variants)]


def classify_failure_mode(failure_mode: str) -> str:
    name = failure_mode.lower()
    if "eventual_decision" in name or "without_decision" in name:
        return "missing_decision"
    if "projection" in name or "refinement" in name:
        return "wrong_state_owner"
    if "non_consumable" in name or "unhandled_branch" in name or "old_consumer" in name:
        return "downstream_non_consumable"
    if "duplicate_decision" in name:
        return "duplicate_decision"
    if "contradictory" in name or "conflict" in name or "late_cancel" in name or "terminal_conflict" in name:
        return "contradictory_decision"
    if "missing_decision" in name or "unknown" in name or "human_review_bypass" in name:
        return "missing_decision"
    if "double_lease" in name or "complete_without_lease" in name or "lease_" in name:
        return "lease_violation"
    if "cache" in name or "stale" in name or "version" in name or "schema_default" in name:
        return "cache_source_mismatch"
    if "audit" in name or "trace" in name or "source" in name or "orphaned" in name or "reason" in name:
        return "missing_source_traceability"
    if "owner" in name or "permission" in name or "authority" in name or "read_only" in name or "policy" in name or "boundary" in name:
        return "wrong_state_owner"
    if "idempotency" in name or "retry" in name or "send_before" in name or "external_success" in name or "lost_ack" in name:
        return "repeated_processing_without_refresh"
    if "duplicate" in name or "replay" in name or "double_fire" in name:
        return "duplicate_side_effect"
    if "terminal" in name or "cleanup" in name or "migration_loses" in name or "privacy_delete" in name or "redaction" in name:
        return "invalid_transition"
    if "refund" in name or "reservation" in name or "oversell" in name or "bypass" in name:
        return "invalid_transition"
    if "ordering" in name or "out_of_order" in name or "gap" in name or "partial_commit" in name or "rollback" in name:
        return "invalid_transition"
    if "accepted" in name or "rejected" in name or "mismatch" in name or "second_source" in name:
        return "invalid_transition"
    return "invalid_transition"


def _identity(case: ProblemCase, suffix: str = "A") -> str:
    return f"{case.workflow_family}:{case.case_id}:{suffix}"


def _command(
    case: ProblemCase,
    identity: str,
    sequence_index: int,
    input_pattern: str | None = None,
    payload: str | None = None,
    version: int = 1,
) -> DomainCommand:
    return DomainCommand(
        case_id=case.case_id,
        identity=identity,
        input_pattern=input_pattern or (case.external_inputs[0] if case.external_inputs else "single_valid_input"),
        payload=payload or f"{case.workflow_family}:{case.failure_mode}:payload:{sequence_index}",
        version=version,
        sequence_index=sequence_index,
    )


def input_sequence_for_case(case: ProblemCase) -> tuple[DomainCommand, ...]:
    pattern = case.external_inputs[0] if case.external_inputs else "single_valid_input"
    a = _identity(case, "A")
    b = _identity(case, "B")
    if pattern == "empty_input_sequence":
        if case.case_kind == "negative_broken_case":
            return (_command(case, a, 0, "single_valid_input"),)
        return ()
    if pattern in {
        "repeated_identical_input",
        "duplicate_request_same_idempotency_key",
        "retry_after_partial_success",
        "replayed_webhook",
    }:
        return (_command(case, a, 0, pattern), _command(case, a, 1, pattern))
    if pattern == "same_input_three_times":
        return (
            _command(case, a, 0, pattern),
            _command(case, a, 1, pattern),
            _command(case, a, 2, pattern),
        )
    if pattern == "a_b_a_repeated_input":
        return (_command(case, a, 0, pattern), _command(case, b, 1, pattern), _command(case, a, 2, pattern))
    if pattern == "a_b_b_a_interleaving":
        return (
            _command(case, a, 0, pattern),
            _command(case, b, 1, pattern),
            _command(case, b, 2, pattern),
            _command(case, a, 3, pattern),
        )
    if pattern == "duplicate_request_different_idempotency_key":
        return (_command(case, a, 0, pattern, version=1), _command(case, a, 1, pattern, version=2))
    if pattern == "out_of_order_events":
        return (_command(case, a, 0, pattern, version=2), _command(case, a, 1, pattern, version=1))
    if pattern == "conflicting_same_identity_payload":
        return (
            _command(case, a, 0, pattern, payload="payload-high", version=1),
            _command(case, a, 1, pattern, payload="payload-conflict", version=2),
        )
    if pattern == "batched_mixed_validity_input":
        return (
            _command(case, a, 0, pattern),
            _command(case, b, 1, pattern, payload="payload-boundary"),
            _command(case, _identity(case, "C"), 2, pattern, payload="payload-malformed"),
        )
    return (_command(case, a, 0, pattern),)


def _latest_source(state: DomainState, identity: str) -> SourceRecord | None:
    matches = [record for record in state.source_records if record.identity == identity]
    return matches[-1] if matches else None


def _latest_cache(state: DomainState, identity: str) -> CacheEntry | None:
    matches = [record for record in state.cache_entries if record.identity == identity]
    return matches[-1] if matches else None


def _has_side_effect(state: DomainState, slot: str, identity: str) -> bool:
    return any(record.slot == slot and record.identity == identity for record in state.side_effects)


def _has_decision(state: DomainState, identity: str) -> bool:
    return any(record.identity == identity for record in state.decisions)


def _effect_token(spec: DomainModelSpec, identity: str, sequence_index: int) -> str:
    return f"{spec.primary_side_effect}:{identity}:{sequence_index}"


class DomainSourceBlock:
    reads = ("external_input",)
    writes = ("source_records", "owner_writes")
    input_description = "DomainCommand"
    output_description = "DomainAccepted"
    idempotency = "keeps one source record per identity and version"
    accepted_input_type = DomainCommand

    def __init__(self, spec: DomainModelSpec) -> None:
        self.spec = spec
        self.name = spec.block_names[0]

    def apply(self, input_obj: DomainCommand, state: DomainState):
        existing = _latest_source(state, input_obj.identity)
        source_records = state.source_records
        if existing is None or existing.version != input_obj.version or existing.payload != input_obj.payload:
            source_records = source_records + (
                SourceRecord(
                    identity=input_obj.identity,
                    version=input_obj.version,
                    payload=input_obj.payload,
                    owner=self.spec.primary_owner,
                ),
            )
        new_state = DomainState(
            case_id=state.case_id,
            workflow_family=state.workflow_family,
            source_records=source_records,
            process_attempts=state.process_attempts,
            cache_entries=state.cache_entries,
            side_effects=state.side_effects,
            decisions=state.decisions,
            trace_links=state.trace_links,
            owner_writes=state.owner_writes
            + (OwnerWrite(self.spec.primary_owner, "source_records", input_obj.identity, True),),
            leases=state.leases,
            audit_events=state.audit_events,
            terminal_records=state.terminal_records,
            invalid_transitions=state.invalid_transitions,
        )
        return (
            FunctionResult(
                output=DomainAccepted(
                    case_id=input_obj.case_id,
                    identity=input_obj.identity,
                    payload=input_obj.payload,
                    version=input_obj.version,
                    input_pattern=input_obj.input_pattern,
                ),
                new_state=new_state,
                label=f"{self.spec.model_name}.source_recorded",
                reason=f"{self.name} recorded source identity {input_obj.identity}",
            ),
        )


class DomainProcessBlock:
    reads = ("source_records", "cache_entries", "process_attempts")
    writes = ("process_attempts", "cache_entries")
    input_description = "DomainAccepted"
    output_description = "DomainProcessed"
    idempotency = "reuses cache for repeated identity unless an explicit refresh exists"
    accepted_input_type = DomainAccepted

    def __init__(self, spec: DomainModelSpec, failure_category: str, broken: bool) -> None:
        self.spec = spec
        self.failure_category = failure_category
        self.broken = broken
        self.name = spec.block_names[1]

    def apply(self, input_obj: DomainAccepted, state: DomainState):
        source = _latest_source(state, input_obj.identity)
        source_version = source.version if source is not None else input_obj.version
        cache = _latest_cache(state, input_obj.identity)
        from_cache = cache is not None and not self.broken
        attempts = state.process_attempts
        should_record_attempt = (
            cache is None
            or (self.broken and self.failure_category == "repeated_processing_without_refresh")
        )
        if should_record_attempt:
            attempts = attempts + (
                ProcessAttempt(
                    identity=input_obj.identity,
                    owner=self.spec.processing_owner,
                    source_version=source_version,
                    via_cache=False,
                ),
            )
            if self.broken and self.failure_category == "repeated_processing_without_refresh":
                attempts = attempts + (
                    ProcessAttempt(
                        identity=input_obj.identity,
                        owner=self.spec.processing_owner,
                        source_version=source_version,
                        via_cache=False,
                    ),
                )
        else:
            attempts = attempts + (
                ProcessAttempt(
                    identity=input_obj.identity,
                    owner=self.spec.processing_owner,
                    source_version=source_version,
                    via_cache=True,
                ),
            )

        if self.broken and self.failure_category == "downstream_non_consumable":
            new_state = DomainState(
                case_id=state.case_id,
                workflow_family=state.workflow_family,
                source_records=state.source_records,
                process_attempts=attempts,
                cache_entries=state.cache_entries,
                side_effects=state.side_effects,
                decisions=state.decisions,
                trace_links=state.trace_links,
                owner_writes=state.owner_writes,
                leases=state.leases,
                audit_events=state.audit_events,
                terminal_records=state.terminal_records,
                invalid_transitions=state.invalid_transitions,
            )
            return (
                FunctionResult(
                    output=IncompatibleDomainOutput(
                        case_id=input_obj.case_id,
                        identity=input_obj.identity,
                        reason=self.failure_category,
                    ),
                    new_state=new_state,
                    label=f"{self.spec.model_name}.incompatible_output",
                    reason=f"{self.name} produced an output the next block cannot consume",
                ),
            )

        cache_value = input_obj.payload
        cache_version = source_version
        stale = False
        if self.broken and self.failure_category == "cache_source_mismatch":
            cache_value = f"stale:{input_obj.payload}"
            cache_version = max(0, source_version - 1)
            stale = True
        cache_entries = state.cache_entries
        if cache is None or self.broken and self.failure_category == "cache_source_mismatch":
            cache_entries = cache_entries + (
                CacheEntry(
                    identity=input_obj.identity,
                    source_version=cache_version,
                    value=cache_value,
                    stale=stale,
                ),
            )
        elif cache is None:
            cache_entries = cache_entries + (
                CacheEntry(identity=input_obj.identity, source_version=source_version, value=cache_value),
            )

        new_state = DomainState(
            case_id=state.case_id,
            workflow_family=state.workflow_family,
            source_records=state.source_records,
            process_attempts=attempts,
            cache_entries=cache_entries,
            side_effects=state.side_effects,
            decisions=state.decisions,
            trace_links=state.trace_links,
            owner_writes=state.owner_writes
            + (OwnerWrite(self.spec.processing_owner, "process_attempts", input_obj.identity, True),),
            leases=state.leases,
            audit_events=state.audit_events,
            terminal_records=state.terminal_records,
            invalid_transitions=state.invalid_transitions,
        )
        return (
            FunctionResult(
                output=DomainProcessed(
                    case_id=input_obj.case_id,
                    identity=input_obj.identity,
                    payload=input_obj.payload,
                    source_version=source_version,
                    from_cache=from_cache,
                ),
                new_state=new_state,
                label=(
                    f"{self.spec.model_name}.process_cached"
                    if from_cache
                    else f"{self.spec.model_name}.process_new"
                ),
                reason=f"{self.name} processed identity {input_obj.identity}",
            ),
        )


class DomainEffectBlock:
    reads = ("process_attempts", "source_records")
    writes = ("side_effects", "trace_links", "leases", "audit_events", "owner_writes")
    input_description = "DomainProcessed"
    output_description = "DomainEffect"
    idempotency = "does not write duplicate side effects for the same identity"
    accepted_input_type = DomainProcessed

    def __init__(self, spec: DomainModelSpec, failure_category: str, broken: bool) -> None:
        self.spec = spec
        self.failure_category = failure_category
        self.broken = broken
        self.name = spec.block_names[2]

    def apply(self, input_obj: DomainProcessed, state: DomainState):
        already_written = _has_side_effect(state, self.spec.primary_side_effect, input_obj.identity)
        side_effects = state.side_effects
        trace_links = state.trace_links
        audit_events = state.audit_events
        leases = state.leases
        owner_writes = state.owner_writes
        invalid_transitions = state.invalid_transitions
        effect_tokens: list[str] = []

        write_count = 0 if already_written and not self.broken else 1
        if self.broken and self.failure_category == "duplicate_side_effect":
            write_count = max(2, write_count + 1)
        if self.broken and self.failure_category == "missing_source_traceability":
            write_count = max(1, write_count)
        if self.broken and self.failure_category == "wrong_state_owner":
            owner_writes = owner_writes + (
                OwnerWrite(self.spec.processing_owner, self.spec.primary_side_effect, input_obj.identity, False),
            )
        if self.broken and self.failure_category == "lease_violation":
            leases = leases + (
                LeaseRecord(input_obj.identity, f"lease:{input_obj.identity}:1", self.spec.effect_owner, True, True),
                LeaseRecord(input_obj.identity, f"lease:{input_obj.identity}:2", self.spec.effect_owner, True, False),
            )
        if self.broken and self.failure_category == "invalid_transition":
            invalid_transitions = invalid_transitions + (self.failure_category,)

        for index in range(write_count):
            token = _effect_token(self.spec, input_obj.identity, index)
            effect_tokens.append(token)
            source_version = input_obj.source_version
            if self.broken and self.failure_category == "missing_source_traceability":
                source_version = None
            side_effects = side_effects + (
                SideEffectRecord(
                    slot=self.spec.primary_side_effect,
                    identity=input_obj.identity,
                    source_version=source_version,
                    owner=self.spec.effect_owner,
                    token=token,
                ),
            )
            if not (self.broken and self.failure_category == "missing_source_traceability"):
                trace_links = trace_links + (
                    TraceLink(
                        effect_token=token,
                        source_identity=input_obj.identity,
                        source_version=input_obj.source_version,
                    ),
                )
                audit_events = audit_events + (
                    AuditEvent(input_obj.identity, token, self.spec.effect_owner),
                )

        owner_writes = owner_writes + (
            OwnerWrite(self.spec.effect_owner, self.spec.primary_side_effect, input_obj.identity, True),
        )
        new_state = DomainState(
            case_id=state.case_id,
            workflow_family=state.workflow_family,
            source_records=state.source_records,
            process_attempts=state.process_attempts,
            cache_entries=state.cache_entries,
            side_effects=side_effects,
            decisions=state.decisions,
            trace_links=trace_links,
            owner_writes=owner_writes,
            leases=leases,
            audit_events=audit_events,
            terminal_records=state.terminal_records,
            invalid_transitions=invalid_transitions,
        )
        return (
            FunctionResult(
                output=DomainEffect(
                    case_id=input_obj.case_id,
                    identity=input_obj.identity,
                    effect_tokens=tuple(effect_tokens),
                ),
                new_state=new_state,
                label=f"{self.spec.model_name}.effect_recorded",
                reason=f"{self.name} wrote {len(effect_tokens)} domain side effect(s)",
            ),
        )


class DomainFinalizeBlock:
    reads = ("side_effects", "decisions", "terminal_records")
    writes = ("decisions", "terminal_records", "invalid_transitions")
    input_description = "DomainEffect"
    output_description = "DomainOutcome"
    idempotency = "does not create duplicate or contradictory final decisions"
    accepted_input_type = DomainEffect

    def __init__(self, spec: DomainModelSpec, failure_category: str, broken: bool) -> None:
        self.spec = spec
        self.failure_category = failure_category
        self.broken = broken
        self.name = spec.block_names[3]

    def apply(self, input_obj: DomainEffect, state: DomainState):
        decisions = state.decisions
        terminal_records = state.terminal_records
        invalid_transitions = state.invalid_transitions
        actions: tuple[str, ...]
        if self.broken and self.failure_category == "missing_decision":
            actions = ()
        elif self.broken and self.failure_category == "contradictory_decision":
            actions = (self.spec.success_action, self.spec.reject_action)
        elif self.broken and self.failure_category == "duplicate_decision":
            actions = (self.spec.success_action, self.spec.success_action)
        else:
            actions = () if _has_decision(state, input_obj.identity) else (self.spec.success_action,)

        for action in actions:
            decisions = decisions + (
                DecisionRecord(input_obj.identity, action, self.spec.decision_owner, self.name),
            )

        if not any(record.identity == input_obj.identity for record in terminal_records):
            terminal_records = terminal_records + (
                TerminalRecord(input_obj.identity, "done", self.spec.decision_owner),
            )
        elif self.broken and self.failure_category == "invalid_transition":
            invalid_transitions = invalid_transitions + ("terminal_state_mutated",)

        new_state = DomainState(
            case_id=state.case_id,
            workflow_family=state.workflow_family,
            source_records=state.source_records,
            process_attempts=state.process_attempts,
            cache_entries=state.cache_entries,
            side_effects=state.side_effects,
            decisions=decisions,
            trace_links=state.trace_links,
            owner_writes=state.owner_writes
            + (OwnerWrite(self.spec.decision_owner, "decisions", input_obj.identity, True),),
            leases=state.leases,
            audit_events=state.audit_events,
            terminal_records=terminal_records,
            invalid_transitions=invalid_transitions,
        )
        return (
            FunctionResult(
                output=DomainOutcome(input_obj.case_id, input_obj.identity, "done"),
                new_state=new_state,
                label=f"{self.spec.model_name}.finalized",
                reason=f"{self.name} finalized identity {input_obj.identity}",
            ),
        )


def _duplicate_side_effect_exists(state: DomainState) -> bool:
    counts = Counter((record.slot, record.identity) for record in state.side_effects)
    return any(count > 1 for count in counts.values())


def _repeated_processing_exists(state: DomainState) -> bool:
    non_cache_counts = Counter(
        record.identity for record in state.process_attempts if not record.via_cache
    )
    return any(count > 1 for count in non_cache_counts.values())


def _cache_mismatch_exists(state: DomainState) -> bool:
    sources = {(record.identity, record.version, record.payload) for record in state.source_records}
    for cache in state.cache_entries:
        if cache.stale:
            return True
        if not any(identity == cache.identity and version == cache.source_version for identity, version, _payload in sources):
            return True
    return False


def _missing_traceability_exists(state: DomainState) -> bool:
    trace_tokens = {link.effect_token for link in state.trace_links}
    source_keys = {(record.identity, record.version) for record in state.source_records}
    audit_tokens = {event.source_token for event in state.audit_events}
    for effect in state.side_effects:
        if effect.source_version is None:
            return True
        if (effect.identity, effect.source_version) not in source_keys:
            return True
        if effect.token not in trace_tokens:
            return True
        if effect.token not in audit_tokens:
            return True
    return False


def _wrong_owner_exists(state: DomainState) -> bool:
    return any(not write.allowed for write in state.owner_writes)


def _missing_decision_exists(state: DomainState) -> bool:
    identities_with_effect = {record.identity for record in state.side_effects}
    identities_with_decision = {record.identity for record in state.decisions}
    return bool(identities_with_effect - identities_with_decision)


def _decision_conflict_exists(state: DomainState) -> bool:
    by_identity: dict[str, list[str]] = {}
    for decision in state.decisions:
        by_identity.setdefault(decision.identity, []).append(decision.action)
    for actions in by_identity.values():
        if "accept" in actions and "reject" in actions:
            return True
    return False


def _duplicate_decision_exists(state: DomainState) -> bool:
    counts = Counter((record.identity, record.action) for record in state.decisions)
    return any(count > 1 for count in counts.values())


def _lease_violation_exists(state: DomainState) -> bool:
    active_counts = Counter(record.identity for record in state.leases if record.active)
    if any(count > 1 for count in active_counts.values()):
        return True
    return any(record.completed and not record.active for record in state.leases)


def _invalid_transition_exists(state: DomainState) -> bool:
    return bool(state.invalid_transitions)


def _structural_violation_exists(state: DomainState, category: str) -> bool:
    if category == "duplicate_side_effect":
        return _duplicate_side_effect_exists(state)
    if category == "repeated_processing_without_refresh":
        return _repeated_processing_exists(state)
    if category == "cache_source_mismatch":
        return _cache_mismatch_exists(state)
    if category == "missing_source_traceability":
        return _missing_traceability_exists(state)
    if category == "wrong_state_owner":
        return _wrong_owner_exists(state)
    if category == "missing_decision":
        return _missing_decision_exists(state)
    if category == "contradictory_decision":
        return _decision_conflict_exists(state)
    if category == "duplicate_decision":
        return _duplicate_decision_exists(state)
    if category == "lease_violation":
        return _lease_violation_exists(state)
    if category == "invalid_transition":
        return _invalid_transition_exists(state)
    return _invalid_transition_exists(state)


def _structural_evidence(state: DomainState, category: str) -> tuple[str, ...]:
    side_effect_counts = Counter((record.slot, record.identity) for record in state.side_effects)
    attempt_counts = Counter(record.identity for record in state.process_attempts if not record.via_cache)
    decision_counts = Counter((record.identity, record.action) for record in state.decisions)
    return (
        f"domain_sources={len(state.source_records)}",
        f"domain_process_attempts={len(state.process_attempts)}",
        f"domain_side_effects={len(state.side_effects)}",
        f"domain_decisions={len(state.decisions)}",
        f"domain_trace_links={len(state.trace_links)}",
        f"domain_owner_writes={len(state.owner_writes)}",
        f"domain_leases={len(state.leases)}",
        f"domain_invalid_transitions={len(state.invalid_transitions)}",
        f"structural_category={category}",
        f"max_side_effect_count={max(side_effect_counts.values(), default=0)}",
        f"max_processing_attempt_count={max(attempt_counts.values(), default=0)}",
        f"max_decision_count={max(decision_counts.values(), default=0)}",
    )


def _no_forbidden_owner_write(step) -> bool | str:
    old_writes = tuple(getattr(step.old_state, "owner_writes", ()))
    new_writes = tuple(getattr(step.new_state, "owner_writes", ()))
    added = new_writes[len(old_writes):]
    forbidden = tuple(write for write in added if not getattr(write, "allowed", True))
    if forbidden:
        return f"forbidden owner write observed: {forbidden!r}"
    return True


def _domain_contracts(spec: DomainModelSpec) -> tuple[FunctionContract, ...]:
    return (
        FunctionContract(
            function_name=spec.block_names[0],
            accepted_input_type=DomainCommand,
            output_type=DomainAccepted,
            reads=("external_input",),
            writes=("source_records", "owner_writes"),
            forbidden_writes=(
                "process_attempts",
                "cache_entries",
                "side_effects",
                "decisions",
                "terminal_records",
            ),
            postconditions=(_no_forbidden_owner_write,),
            idempotency_rule="same identity/version is not duplicated as a source record",
            traceability_rule="source record keeps identity, version, payload, and owner",
        ),
        FunctionContract(
            function_name=spec.block_names[1],
            accepted_input_type=DomainAccepted,
            output_type=DomainProcessed,
            reads=("source_records", "cache_entries", "process_attempts"),
            writes=("process_attempts", "cache_entries", "owner_writes"),
            forbidden_writes=("side_effects", "decisions", "terminal_records"),
            postconditions=(_no_forbidden_owner_write,),
            idempotency_rule="repeated identity uses cache unless refresh is explicit",
            traceability_rule="processed output references the source version",
        ),
        FunctionContract(
            function_name=spec.block_names[2],
            accepted_input_type=DomainProcessed,
            output_type=DomainEffect,
            reads=("process_attempts", "source_records"),
            writes=(
                "side_effects",
                "trace_links",
                "leases",
                "audit_events",
                "owner_writes",
                "invalid_transitions",
            ),
            forbidden_writes=("decisions", "terminal_records", "cache_entries"),
            postconditions=(_no_forbidden_owner_write,),
            idempotency_rule="same identity is not written twice to the same side-effect slot",
            traceability_rule="side effects must have a source trace link",
        ),
        FunctionContract(
            function_name=spec.block_names[3],
            accepted_input_type=DomainEffect,
            output_type=DomainOutcome,
            reads=("side_effects", "decisions", "terminal_records"),
            writes=("decisions", "terminal_records", "owner_writes", "invalid_transitions"),
            forbidden_writes=("source_records", "process_attempts", "cache_entries", "side_effects"),
            postconditions=(_no_forbidden_owner_write,),
            idempotency_rule="same identity is not given duplicate or contradictory decisions",
            traceability_rule="final outcome follows a recorded side effect",
        ),
    )


def _contract_evidence(trace, spec: DomainModelSpec) -> tuple[str, ...]:
    if trace is None:
        return ("contract_checked=false", "contract_reason=no_trace_available")
    report = check_trace_contracts(trace, _domain_contracts(spec))
    names = report.violation_names()
    return (
        "contract_checked=true",
        f"contract_checked_steps={report.checked_steps}",
        f"contract_status={'ok' if report.ok else 'violation'}",
        f"contract_findings={','.join(names) if names else 'none'}",
    )


def _case_invariant(case: ProblemCase, category: str) -> Invariant:
    def predicate(state: DomainState, _trace) -> InvariantResult:
        if _structural_violation_exists(state, category):
            return InvariantResult.fail(
                f"{case.failure_mode} observed through {category}",
                {
                    "case_id": case.case_id,
                    "failure_mode": case.failure_mode,
                    "structural_category": category,
                },
            )
        return InvariantResult.pass_()

    return Invariant(
        name=case.failure_mode,
        description=f"{case.case_id} must not exhibit {case.failure_mode}.",
        predicate=predicate,
    )


def _inject_structural_bug(state: DomainState, case: ProblemCase, spec: DomainModelSpec, category: str) -> DomainState:
    identity = _identity(case, "invalid")
    source = SourceRecord(identity, 1, "invalid-initial-payload", spec.primary_owner)
    base = DomainState(
        case_id=state.case_id,
        workflow_family=state.workflow_family,
        source_records=state.source_records + (source,),
        process_attempts=state.process_attempts,
        cache_entries=state.cache_entries,
        side_effects=state.side_effects,
        decisions=state.decisions,
        trace_links=state.trace_links,
        owner_writes=state.owner_writes,
        leases=state.leases,
        audit_events=state.audit_events,
        terminal_records=state.terminal_records,
        invalid_transitions=state.invalid_transitions,
    )
    if category == "duplicate_side_effect":
        effect = SideEffectRecord(spec.primary_side_effect, identity, 1, spec.effect_owner, "invalid-effect")
        return DomainState(**{**base.__dict__, "side_effects": base.side_effects + (effect, effect)})
    if category == "repeated_processing_without_refresh":
        attempt = ProcessAttempt(identity, spec.processing_owner, 1, False)
        return DomainState(**{**base.__dict__, "process_attempts": base.process_attempts + (attempt, attempt)})
    if category == "cache_source_mismatch":
        return DomainState(**{**base.__dict__, "cache_entries": base.cache_entries + (CacheEntry(identity, 0, "stale", True),)})
    if category == "missing_source_traceability":
        effect = SideEffectRecord(spec.primary_side_effect, identity, None, spec.effect_owner, "orphan-effect")
        return DomainState(**{**base.__dict__, "side_effects": base.side_effects + (effect,)})
    if category == "wrong_state_owner":
        return DomainState(**{**base.__dict__, "owner_writes": base.owner_writes + (OwnerWrite(spec.primary_owner, spec.primary_side_effect, identity, False),)})
    if category == "missing_decision":
        effect = SideEffectRecord(spec.primary_side_effect, identity, 1, spec.effect_owner, "undecided-effect")
        return DomainState(**{**base.__dict__, "side_effects": base.side_effects + (effect,), "trace_links": base.trace_links + (TraceLink("undecided-effect", identity, 1),), "audit_events": base.audit_events + (AuditEvent(identity, "undecided-effect", spec.effect_owner),)})
    if category == "contradictory_decision":
        return DomainState(**{**base.__dict__, "decisions": base.decisions + (DecisionRecord(identity, "accept", spec.decision_owner, "invalid"), DecisionRecord(identity, "reject", spec.decision_owner, "invalid"))})
    if category == "duplicate_decision":
        return DomainState(**{**base.__dict__, "decisions": base.decisions + (DecisionRecord(identity, "accept", spec.decision_owner, "invalid"), DecisionRecord(identity, "accept", spec.decision_owner, "invalid"))})
    if category == "lease_violation":
        return DomainState(**{**base.__dict__, "leases": base.leases + (LeaseRecord(identity, "lease-1", spec.effect_owner, True), LeaseRecord(identity, "lease-2", spec.effect_owner, True))})
    return DomainState(**{**base.__dict__, "invalid_transitions": base.invalid_transitions + (category,)})


def initial_state_for_case(case: ProblemCase, spec: DomainModelSpec, category: str) -> DomainState:
    state = DomainState(case_id=case.case_id, workflow_family=case.workflow_family)
    if case.case_kind == "invalid_initial_state_case":
        return _inject_structural_bug(state, case, spec, category)
    return state


def _expected_status(case: ProblemCase, category: str) -> str:
    if case.case_kind in SCENARIO_PASS_KINDS:
        return "ok"
    return "violation"


def _expected_violation_names(case: ProblemCase, category: str) -> tuple[str, ...]:
    if case.case_kind in SCENARIO_PASS_KINDS:
        return ()
    if case.case_kind == "negative_broken_case" and category == "downstream_non_consumable":
        return ("dead_branch",)
    return (case.failure_mode,)


def build_real_model_scenario(case: ProblemCase) -> Scenario:
    base_spec = MODEL_SPECS[case.workflow_family]
    variant = select_variant_for_case(case)
    spec = variant.to_model_spec(base_spec)
    category = classify_failure_mode(case.failure_mode)
    broken = case.case_kind == "negative_broken_case"
    workflow = Workflow(
        (
            DomainSourceBlock(spec),
            DomainProcessBlock(spec, category, broken),
            DomainEffectBlock(spec, category, broken),
            DomainFinalizeBlock(spec, category, broken),
        ),
        name=f"{spec.model_name}:{case.case_id}",
    )
    return Scenario(
        name=case.case_id,
        description=case.title,
        initial_state=initial_state_for_case(case, spec, category),
        external_input_sequence=input_sequence_for_case(case),
        expected=ScenarioExpectation(
            expected_status=_expected_status(case, category),
            expected_violation_names=_expected_violation_names(case, category),
            summary=f"{_expected_status(case, category).upper()} {spec.model_name} for {case.failure_mode}",
        ),
        workflow=workflow,
        invariants=(_case_invariant(case, category),),
        tags=("real_model_corpus", case.case_kind, case.workflow_family, category),
        notes=f"Real domain model binding for {spec.model_name} variant {variant.variant_id}.",
    )


def _loop_variant(case: ProblemCase) -> str:
    name = case.failure_mode.lower()
    if "escape" in name or "forced_progress" in name:
        return "cycle_with_escape_no_forced_progress"
    if "dead_end" in name:
        return "stuck_state"
    if "unreachable" in name:
        return "unreachable_success"
    if "terminal" in name:
        return "terminal_outgoing"
    if "retry" in name:
        return "retry_cycle"
    if "progress" in name:
        return "cycle_with_no_progress"
    return "closed_loop"


def _loop_config(case: ProblemCase, spec: DomainModelSpec) -> tuple[str, LoopCheckConfig]:
    variant = _loop_variant(case)
    start = RealLoopState(case.case_id, case.workflow_family, spec.block_names[0])
    process = RealLoopState(case.case_id, case.workflow_family, spec.block_names[1])
    effect = RealLoopState(case.case_id, case.workflow_family, spec.block_names[2])
    final = RealLoopState(case.case_id, case.workflow_family, spec.block_names[3])
    done = RealLoopState(case.case_id, case.workflow_family, "done")
    ignored = RealLoopState(case.case_id, case.workflow_family, "ignored")

    if variant == "cycle_with_escape_no_forced_progress":
        def transition(state: RealLoopState):
            if state == start:
                return (GraphEdge(start, process, f"{spec.model_name}.start", case.failure_mode),)
            if state == process:
                return (
                    GraphEdge(process, effect, f"{spec.model_name}.continue_cycle", case.failure_mode),
                    GraphEdge(process, done, f"{spec.model_name}.escape_to_done", case.failure_mode),
                )
            if state == effect:
                return (GraphEdge(effect, process, f"{spec.model_name}.cycle_without_ranking_progress", case.failure_mode),)
            return ()

        return variant, LoopCheckConfig(
            initial_states=(start,),
            transition_fn=transition,
            is_terminal=lambda state: state.phase == "done",
            is_success=lambda state: state.phase == "done",
            required_success=True,
        )

    if variant == "stuck_state":
        def transition(state: RealLoopState):
            if state == start:
                return (GraphEdge(start, process, f"{spec.model_name}.enter_processing", case.failure_mode),)
            return ()

        return variant, LoopCheckConfig(
            initial_states=(start,),
            transition_fn=transition,
            is_terminal=lambda state: state.phase == "done",
            is_success=lambda state: state.phase == "done",
            required_success=True,
        )

    if variant == "unreachable_success":
        def transition(state: RealLoopState):
            if state == start:
                return (GraphEdge(start, ignored, f"{spec.model_name}.route_to_non_success", case.failure_mode),)
            return ()

        return variant, LoopCheckConfig(
            initial_states=(start,),
            transition_fn=transition,
            is_terminal=lambda state: state.phase == "ignored",
            is_success=lambda state: state.phase == "done",
            required_success=True,
        )

    if variant == "terminal_outgoing":
        def transition(state: RealLoopState):
            if state == start:
                return (GraphEdge(start, done, f"{spec.model_name}.finish", case.failure_mode),)
            if state == done:
                return (GraphEdge(done, process, f"{spec.model_name}.terminal_mutated", case.failure_mode),)
            return ()

        return variant, LoopCheckConfig(
            initial_states=(start,),
            transition_fn=transition,
            is_terminal=lambda state: state.phase == "done",
            is_success=lambda state: state.phase == "done",
            required_success=False,
        )

    def transition(state: RealLoopState):
        if state == start:
            return (GraphEdge(start, process, f"{spec.model_name}.start", case.failure_mode),)
        if state == process:
            return (GraphEdge(process, effect, f"{spec.model_name}.process", case.failure_mode),)
        if state == effect:
            return (GraphEdge(effect, process, f"{spec.model_name}.{variant}", case.failure_mode),)
        if state == final:
            return (GraphEdge(final, done, f"{spec.model_name}.finish", case.failure_mode),)
        return ()

    return variant, LoopCheckConfig(
        initial_states=(start,),
        transition_fn=transition,
        is_terminal=lambda state: state.phase == "done",
        is_success=lambda state: state.phase == "done",
        required_success=True,
    )


def _loop_findings(report: LoopCheckReport) -> tuple[str, ...]:
    findings: list[str] = []
    if report.stuck_states:
        findings.append("stuck_state")
    if report.non_terminating_components:
        findings.append("non_terminating_component")
    if report.unreachable_success:
        findings.append("unreachable_success")
    if report.terminal_with_outgoing_edges:
        findings.append("terminal_with_outgoing_edges")
    return tuple(findings)


def _progress_findings(report: ProgressCheckReport) -> tuple[str, ...]:
    return report.finding_names()


def _progress_config_from_loop_config(config: LoopCheckConfig) -> ProgressCheckConfig:
    return ProgressCheckConfig(
        initial_states=config.initial_states,
        transition_fn=config.transition_fn,
        is_terminal=config.is_terminal,
        is_success=config.is_success,
        max_states=config.max_states,
        max_depth=config.max_depth,
    )


def _base_metadata(
    case: ProblemCase,
    spec: DomainModelSpec,
    variant: DomainVariantSpec,
    structural_category: str,
    bug_class: str | None = None,
) -> tuple[tuple[str, object], ...]:
    return tuple(case.metadata) + (
        ("model_binding_kind", "real_domain_model"),
        ("generic_fallback", "false"),
        ("model_family", spec.workflow_family),
        ("model_name", spec.model_name),
        ("model_variant", variant.variant_id),
        ("variant_id", f"{spec.workflow_family}:{variant.variant_id}"),
        ("variant_title", variant.title),
        ("bug_class", bug_class or structural_category),
        ("structural_category", structural_category),
        ("variant_assignment", "family_round_robin_depth_balanced"),
        ("domain_block_names", "|".join(spec.block_names)),
        ("domain_state_slots", "|".join(spec.state_slots)),
    )


def _scenario_case_result(case: ProblemCase) -> ExecutableCaseResult:
    base_spec = MODEL_SPECS[case.workflow_family]
    variant = select_variant_for_case(case)
    spec = variant.to_model_spec(base_spec)
    category = classify_failure_mode(case.failure_mode)
    scenario = build_real_model_scenario(case)
    review_result: OracleReviewResult = review_scenario(scenario)
    run = review_result.scenario_run
    final_state = run.final_states[0] if run is not None and run.final_states else scenario.initial_state
    contract_trace = review_result.counterexample_trace
    if contract_trace is None and run is not None and run.traces:
        contract_trace = run.traces[0]
    evidence = tuple(review_result.evidence) + _structural_evidence(final_state, category) + (
        "execution_kind=real_model_workflow",
        f"real_checker=RealWorkflow:{spec.model_name}",
        f"model_family={spec.workflow_family}",
        f"variant_id={spec.workflow_family}:{variant.variant_id}",
        f"model_variant={variant.variant_id}",
        f"structural_category={category}",
    ) + _contract_evidence(contract_trace, spec)
    return ExecutableCaseResult(
        case_id=case.case_id,
        title=case.title,
        case_kind=case.case_kind,
        workflow_family=case.workflow_family,
        failure_mode=case.failure_mode,
        oracle_type=case.oracle_type,
        expected_status=scenario.expected.expected_status,
        expected_violation_names=scenario.expected.expected_violation_names,
        observed_status=run.observed_status if run is not None else review_result.observed_summary,
        observed_violation_names=run.observed_violation_names if run is not None else (),
        status=review_result.status,
        execution_kind="real_model_workflow",
        mapped_checker=f"RealWorkflow:{spec.model_name}",
        evidence=evidence,
        counterexample_trace=review_result.counterexample_trace,
        metadata=_base_metadata(case, spec, variant, category)
        + (("input_sequence_length", len(scenario.external_input_sequence)),),
    )


def _loop_case_result(case: ProblemCase) -> ExecutableCaseResult:
    base_spec = MODEL_SPECS[case.workflow_family]
    variant_spec = select_variant_for_case(case)
    spec = variant_spec.to_model_spec(base_spec)
    variant, config = _loop_config(case, spec)
    report = check_loops(config)
    progress_report = check_progress(_progress_config_from_loop_config(config))
    findings = tuple(dict.fromkeys(_loop_findings(report) + _progress_findings(progress_report)))
    pressure_expected = _metadata_value(case, "pressure_expected_status")
    if pressure_expected == "known_limitation":
        status = "expected_violation_observed" if findings else "missing_expected_violation"
        expected_status = "violation"
        expected_names = ("potential_nontermination", "missing_progress_guarantee")
        observed_status = "violation" if findings else "ok"
        observed_names = findings
        limitation_reason = ""
    else:
        status = "expected_violation_observed" if findings else "missing_expected_violation"
        expected_status = "violation"
        expected_names = findings or (case.failure_mode,)
        observed_status = "violation" if findings else "ok"
        observed_names = findings
        limitation_reason = ""
    evidence = (
        f"loop_variant={variant}",
        f"findings={','.join(findings) if findings else 'none'}",
        f"progress_findings={','.join(progress_report.finding_names()) if progress_report.findings else 'none'}",
        f"states={report.graph_summary.get('states', 0)}",
        f"edges={report.graph_summary.get('edges', 0)}",
        f"pressure_expected_status={pressure_expected or 'none'}",
        "execution_kind=real_model_loop",
        f"real_checker=RealLoopCheck:{spec.model_name}",
        f"model_family={spec.workflow_family}",
        f"variant_id={spec.workflow_family}:{variant_spec.variant_id}",
        f"model_variant={variant_spec.variant_id}",
        f"structural_category={variant}",
    )
    return ExecutableCaseResult(
        case_id=case.case_id,
        title=case.title,
        case_kind=case.case_kind,
        workflow_family=case.workflow_family,
        failure_mode=case.failure_mode,
        oracle_type=case.oracle_type,
        expected_status=expected_status,
        expected_violation_names=expected_names,
        observed_status=observed_status,
        observed_violation_names=observed_names,
        status=status,
        execution_kind="real_model_loop",
        mapped_checker=f"RealLoopCheck:{spec.model_name}",
        evidence=evidence,
        graph_evidence={
            "loop_report": report.to_dict(),
            "progress_report": progress_report.to_dict(),
            "graph_summary": report.to_dict()["graph_summary"],
        },
        limitation_reason=limitation_reason,
        metadata=_base_metadata(case, spec, variant_spec, variant, classify_failure_mode(case.failure_mode)),
    )


def execute_real_model_case(case: ProblemCase) -> ExecutableCaseResult:
    """Run one ProblemCase through its workflow-family-specific real model."""

    if case.workflow_family not in MODEL_SPECS:
        return ExecutableCaseResult(
            case_id=case.case_id,
            title=case.title,
            case_kind=case.case_kind,
            workflow_family=case.workflow_family,
            failure_mode=case.failure_mode,
            oracle_type=case.oracle_type,
            expected_status="unknown",
            expected_violation_names=(),
            observed_status="not_executable_yet",
            observed_violation_names=(),
            status="not_executable_yet",
            execution_kind="none",
            mapped_checker="none",
            evidence=("no real model spec is registered for this workflow family",),
            not_executable_reason="missing real model spec",
            metadata=tuple(case.metadata)
            + (("model_binding_kind", "generic_fallback"), ("generic_fallback", "true")),
        )
    if case.case_kind in LOOP_KINDS:
        return _loop_case_result(case)
    if case.case_kind in SCENARIO_PASS_KINDS | SCENARIO_VIOLATION_KINDS:
        return _scenario_case_result(case)
    return ExecutableCaseResult(
        case_id=case.case_id,
        title=case.title,
        case_kind=case.case_kind,
        workflow_family=case.workflow_family,
        failure_mode=case.failure_mode,
        oracle_type=case.oracle_type,
        expected_status="unknown",
        expected_violation_names=(),
        observed_status="not_executable_yet",
        observed_violation_names=(),
        status="not_executable_yet",
        execution_kind="none",
        mapped_checker="none",
        evidence=("no real model checker is registered for this case kind",),
        not_executable_reason="missing real model case-kind binding",
        metadata=tuple(case.metadata)
        + (("model_binding_kind", "generic_fallback"), ("generic_fallback", "true")),
    )


def execute_real_model_cases(cases: Iterable[ProblemCase]) -> tuple[ExecutableCaseResult, ...]:
    return tuple(execute_real_model_case(case) for case in cases)


def review_real_model_corpus(corpus: ProblemCorpus | None = None) -> ExecutableCorpusReport:
    corpus = corpus or build_problem_corpus()
    return build_executable_corpus_report(
        execute_real_model_cases(corpus.cases),
        total_cases=len(corpus.cases),
        summary=(
            "Phase 11 real-model corpus review: every ProblemCase must bind "
            "to a workflow-family-specific real domain model, not a generic fallback."
        ),
    )


__all__ = [
    "MODEL_SPECS",
    "VARIANT_SPECS",
    "DomainModelSpec",
    "DomainVariantSpec",
    "DomainState",
    "DomainSourceBlock",
    "DomainProcessBlock",
    "DomainEffectBlock",
    "DomainFinalizeBlock",
    "build_real_model_scenario",
    "classify_failure_mode",
    "execute_real_model_case",
    "execute_real_model_cases",
    "input_sequence_for_case",
    "review_real_model_corpus",
    "select_variant_for_case",
    "validate_model_specs",
]
