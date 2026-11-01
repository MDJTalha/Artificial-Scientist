"""Create initial PostgreSQL persistence schema.

Revision ID: 0001_postgresql_core
Revises:
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_postgresql_core"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "research_records",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=255), nullable=True),
        sa.Column("record_type", sa.String(length=64), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.CheckConstraint("length(content_sha256) = 64", name="ck_research_records_sha256"),
    )
    op.create_index(
        "idx_research_records_type_created",
        "research_records",
        ["record_type", sa.text("created_at DESC")],
    )
    op.create_index(
        "idx_research_records_tenant_type_created",
        "research_records",
        ["tenant_id", "record_type", sa.text("created_at DESC")],
    )

    op.create_table(
        "audit_events",
        sa.Column("event_id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=255), nullable=True),
        sa.Column("occurred_at", sa.Text(), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("actor", sa.String(length=128), nullable=False),
        sa.Column("record_id", sa.String(length=36), sa.ForeignKey(
            "research_records.id", ondelete="RESTRICT"
        ), nullable=False),
        sa.Column("record_type", sa.String(length=64), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.CheckConstraint("action = 'record.created'", name="ck_audit_events_action"),
        sa.CheckConstraint("actor = 'local-api-client'", name="ck_audit_events_actor"),
    )
    op.create_index(
        "idx_audit_events_occurred",
        "audit_events",
        [sa.text("occurred_at DESC")],
    )
    op.create_index(
        "idx_audit_events_tenant_occurred",
        "audit_events",
        ["tenant_id", sa.text("occurred_at DESC")],
    )

    op.create_table(
        "source_identity",
        sa.Column("identity_key", sa.Text(), primary_key=True),
        sa.Column("tenant_id", sa.String(length=255), nullable=True),
        sa.Column("record_id", sa.String(length=36), sa.ForeignKey(
            "research_records.id", ondelete="RESTRICT"
        ), nullable=False, unique=True),
    )

    op.create_table(
        "asds_principals",
        sa.Column("principal_id", sa.String(length=36), primary_key=True),
        sa.Column("issuer", sa.String(length=512), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.UniqueConstraint("issuer", "subject", name="uq_asds_principals_issuer_subject"),
    )
    op.create_table(
        "asds_tenants",
        sa.Column("tenant_id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.CheckConstraint("length(name) BETWEEN 1 AND 120", name="ck_asds_tenant_name"),
    )
    op.create_table(
        "asds_memberships",
        sa.Column("principal_id", sa.String(length=36), sa.ForeignKey(
            "asds_principals.principal_id", ondelete="CASCADE"
        ), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey(
            "asds_tenants.tenant_id", ondelete="CASCADE"
        ), primary_key=True),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.CheckConstraint(
            "role IN ('tenant_admin','researcher','viewer','auditor')",
            name="ck_asds_membership_role",
        ),
    )
    op.create_index(
        "idx_asds_memberships_tenant",
        "asds_memberships",
        ["tenant_id", "active"],
    )
    op.create_table(
        "asds_security_audit",
        sa.Column("event_id", sa.String(length=36), primary_key=True),
        sa.Column("occurred_at", sa.Text(), nullable=False),
        sa.Column("principal_id", sa.String(length=36), nullable=True),
        sa.Column("tenant_id", sa.String(length=36), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("target_type", sa.String(length=40), nullable=False),
        sa.Column("target_id", sa.String(length=255), nullable=True),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("correlation_id", sa.String(length=128), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "outcome IN ('allowed','denied','failed')",
            name="ck_asds_security_audit_outcome",
        ),
    )
    op.create_index(
        "idx_asds_audit_tenant_time",
        "asds_security_audit",
        ["tenant_id", sa.text("occurred_at DESC")],
    )

    op.execute(
        """
        CREATE FUNCTION asds_reject_immutable_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION '% is append-only', TG_TABLE_NAME
                USING ERRCODE = '55000';
        END;
        $$
        """
    )
    for table in ("research_records", "audit_events", "source_identity"):
        op.execute(
            f"""
            CREATE TRIGGER {table}_append_only
            BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION asds_reject_immutable_mutation()
            """
        )


def downgrade() -> None:
    for table in ("source_identity", "audit_events", "research_records"):
        op.execute(f"DROP TRIGGER IF EXISTS {table}_append_only ON {table}")
    op.execute("DROP FUNCTION IF EXISTS asds_reject_immutable_mutation()")
    op.drop_table("asds_security_audit")
    op.drop_index("idx_asds_memberships_tenant", table_name="asds_memberships")
    op.drop_table("asds_memberships")
    op.drop_table("asds_tenants")
    op.drop_table("asds_principals")
    op.drop_index("idx_audit_events_tenant_time", table_name="asds_security_audit") if False else None
    op.drop_table("source_identity")
    op.drop_index("idx_audit_events_tenant_occurred", table_name="audit_events")
    op.drop_index("idx_audit_events_occurred", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("idx_research_records_tenant_type_created", table_name="research_records")
    op.drop_index("idx_research_records_type_created", table_name="research_records")
    op.drop_table("research_records")
