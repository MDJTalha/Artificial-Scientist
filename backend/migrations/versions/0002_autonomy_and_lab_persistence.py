"""Add PostgreSQL tables for autonomy journals and controlled-lab persistence.

Revision ID: 0002_autonomy_and_lab_persistence
Revises: 0001_postgresql_core
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_autonomy_and_lab_persistence"
down_revision = "0001_postgresql_core"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Autonomy workflow state is mutable; its transition and checkpoint journals
    # are append-only. Tenant ownership stays nullable for explicit legacy handling.
    op.create_table(
        "autonomy_workflows",
        sa.Column("workflow_id", sa.String(255), primary_key=True),
        sa.Column("state", sa.String(80), nullable=False),
        sa.Column("consequential", sa.Boolean(), nullable=False),
        sa.Column("approval_token_hash", sa.String(128)),
        sa.Column("tenant_id", sa.String(255)),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
    )
    op.create_index(
        "idx_autonomy_workflows_tenant_state",
        "autonomy_workflows", ["tenant_id", "state", "updated_at"],
    )
    op.create_table(
        "autonomy_transitions",
        sa.Column("event_id", sa.String(36), primary_key=True),
        sa.Column("workflow_id", sa.String(255), sa.ForeignKey(
            "autonomy_workflows.workflow_id", ondelete="RESTRICT"
        ), nullable=False),
        sa.Column("from_state", sa.String(80), nullable=False),
        sa.Column("to_state", sa.String(80), nullable=False),
        sa.Column("actor", sa.String(255), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("tenant_id", sa.String(255)),
        sa.Column("occurred_at", sa.Text(), nullable=False),
    )
    op.create_index(
        "idx_autonomy_transitions_tenant_time",
        "autonomy_transitions", ["tenant_id", sa.text("occurred_at DESC")],
    )
    op.create_index(
        "idx_autonomy_transitions_workflow",
        "autonomy_transitions", ["workflow_id", "occurred_at"],
    )
    op.create_table(
        "autonomy_checkpoints",
        sa.Column("checkpoint_id", sa.String(36), primary_key=True),
        sa.Column("workflow_id", sa.String(255), sa.ForeignKey(
            "autonomy_workflows.workflow_id", ondelete="RESTRICT"
        ), nullable=False),
        sa.Column("digest", sa.String(128), nullable=False),
        sa.Column("tenant_id", sa.String(255)),
        sa.Column("created_at", sa.Text(), nullable=False),
    )
    op.create_index(
        "idx_autonomy_checkpoints_tenant_workflow",
        "autonomy_checkpoints", ["tenant_id", "workflow_id", "created_at"],
    )
    op.create_table(
        "autonomy_memory",
        sa.Column("memory_id", sa.String(36), primary_key=True),
        sa.Column("key_name", sa.String(255), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(80), nullable=False),
        sa.Column("value_json", sa.Text(), nullable=False),
        sa.Column("evidence_json", sa.Text(), nullable=False),
        sa.Column("digest", sa.String(128), nullable=False),
        sa.Column("supersedes_version", sa.Integer()),
        sa.Column("tenant_id", sa.String(255)),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.UniqueConstraint(
            "key_name", "version", "tenant_id",
            name="uq_autonomy_memory_key_version_tenant",
        ),
        sa.CheckConstraint("version > 0", name="ck_autonomy_memory_version_positive"),
    )
    op.create_index(
        "idx_autonomy_memory_key",
        "autonomy_memory", ["tenant_id", "key_name", "version"],
    )

    # Lab runs are retained/deleted by the retention workflow. Their artifacts
    # are immutable and are removed only through the run's explicit retention path.
    op.create_table(
        "lab_runs",
        sa.Column("run_id", sa.String(36), primary_key=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("configuration_sha256", sa.String(64), nullable=False),
        sa.Column("result_sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("tenant_id", sa.String(255)),
        sa.CheckConstraint("status IN ('completed','failed')", name="ck_lab_runs_status"),
        sa.CheckConstraint("length(configuration_sha256) = 64", name="ck_lab_runs_config_sha"),
        sa.CheckConstraint("length(result_sha256) = 64", name="ck_lab_runs_result_sha"),
    )
    op.create_index("idx_lab_runs_created_at", "lab_runs", [sa.text("created_at DESC")])
    op.create_index(
        "idx_lab_runs_tenant_created", "lab_runs",
        ["tenant_id", sa.text("created_at DESC")],
    )
    op.create_table(
        "lab_execution_attempts",
        sa.Column("run_id", sa.String(36), primary_key=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("configuration_sha256", sa.String(64), nullable=False),
        sa.Column("started_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.Column("finished_at", sa.Text()),
        sa.Column("failure_reason", sa.Text()),
        sa.Column("result_sha256", sa.String(64)),
        sa.Column("request_json", sa.Text(), nullable=False),
        sa.Column("tenant_id", sa.String(255)),
        sa.CheckConstraint(
            "status IN ('running','completed','failed','interrupted')",
            name="ck_lab_attempt_status",
        ),
        sa.CheckConstraint(
            "length(configuration_sha256) = 64", name="ck_lab_attempt_config_sha"
        ),
    )
    op.create_index(
        "idx_lab_attempts_tenant_status",
        "lab_execution_attempts", ["tenant_id", "status", "updated_at"],
    )
    op.create_index(
        "idx_lab_execution_attempts_status",
        "lab_execution_attempts", ["status", "updated_at"],
    )
    op.create_table(
        "lab_artifacts",
        sa.Column("artifact_id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey(
            "lab_runs.run_id", ondelete="CASCADE"
        ), nullable=False),
        sa.Column("artifact_type", sa.String(40), nullable=False),
        sa.Column("content_type", sa.String(120), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("provenance_json", sa.Text(), nullable=False),
        sa.Column("content_json", sa.LargeBinary(), nullable=False),
        sa.CheckConstraint("artifact_type = 'run-result-json'", name="ck_lab_artifact_type"),
        sa.CheckConstraint("content_type = 'application/json'", name="ck_lab_artifact_content_type"),
        sa.CheckConstraint("length(sha256) = 64", name="ck_lab_artifact_sha"),
        sa.CheckConstraint("size_bytes BETWEEN 0 AND 1048576", name="ck_lab_artifact_size"),
    )
    op.create_index("idx_lab_artifacts_run_id", "lab_artifacts", ["run_id"])
    op.create_table(
        "lab_binary_artifacts",
        sa.Column("artifact_id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey(
            "lab_runs.run_id", ondelete="CASCADE"
        ), nullable=False),
        sa.Column("filename", sa.String(180), nullable=False),
        sa.Column("content_type", sa.String(120), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("provenance_json", sa.Text(), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.CheckConstraint("length(filename) BETWEEN 1 AND 180", name="ck_lab_binary_filename"),
        sa.CheckConstraint("length(content_type) BETWEEN 1 AND 120", name="ck_lab_binary_content_type"),
        sa.CheckConstraint("length(sha256) = 64", name="ck_lab_binary_sha"),
        sa.CheckConstraint("size_bytes BETWEEN 1 AND 10485760", name="ck_lab_binary_size"),
    )
    op.create_index("idx_lab_binary_artifacts_run_id", "lab_binary_artifacts", ["run_id"])
    op.create_table(
        "lab_run_retention_events",
        sa.Column("run_id", sa.String(36), primary_key=True),
        sa.Column("result_sha256", sa.String(64), nullable=False),
        sa.Column("configuration_sha256", sa.String(64), nullable=False),
        sa.Column("deleted_at", sa.Text(), nullable=False),
        sa.Column("retention_cutoff", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("artifacts_deleted", sa.Integer(), nullable=False),
        sa.CheckConstraint("length(result_sha256) = 64", name="ck_lab_retention_result_sha"),
        sa.CheckConstraint("length(configuration_sha256) = 64", name="ck_lab_retention_config_sha"),
        sa.CheckConstraint("artifacts_deleted >= 0", name="ck_lab_retention_artifact_count"),
    )

    # Database-level append-only enforcement protects journals and artifact evidence
    # even when a future application path bypasses the Python store contract.
    for table in (
        "autonomy_transitions", "autonomy_checkpoints", "autonomy_memory",
        "lab_artifacts", "lab_binary_artifacts", "lab_run_retention_events",
    ):
        op.execute(
            f"""
            CREATE TRIGGER {table}_append_only
            BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION asds_reject_immutable_mutation()
            """
        )


def downgrade() -> None:
    for table in (
        "lab_run_retention_events", "lab_binary_artifacts", "lab_artifacts",
        "autonomy_memory", "autonomy_checkpoints", "autonomy_transitions",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS {table}_append_only ON {table}")
    op.drop_table("lab_run_retention_events")
    op.drop_index("idx_lab_binary_artifacts_run_id", table_name="lab_binary_artifacts")
    op.drop_table("lab_binary_artifacts")
    op.drop_index("idx_lab_artifacts_run_id", table_name="lab_artifacts")
    op.drop_table("lab_artifacts")
    op.drop_index("idx_lab_execution_attempts_status", table_name="lab_execution_attempts")
    op.drop_index("idx_lab_attempts_tenant_status", table_name="lab_execution_attempts")
    op.drop_table("lab_execution_attempts")
    op.drop_index("idx_lab_runs_tenant_created", table_name="lab_runs")
    op.drop_index("idx_lab_runs_created_at", table_name="lab_runs")
    op.drop_table("lab_runs")
    op.drop_index("idx_autonomy_memory_key", table_name="autonomy_memory")
    op.drop_table("autonomy_memory")
    op.drop_index("idx_autonomy_checkpoints_tenant_workflow", table_name="autonomy_checkpoints")
    op.drop_table("autonomy_checkpoints")
    op.drop_index("idx_autonomy_transitions_workflow", table_name="autonomy_transitions")
    op.drop_index("idx_autonomy_transitions_tenant_time", table_name="autonomy_transitions")
    op.drop_table("autonomy_transitions")
    op.drop_index("idx_autonomy_workflows_tenant_state", table_name="autonomy_workflows")
    op.drop_table("autonomy_workflows")
