"""Create facilities and bookings with a database-enforced overlap invariant."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.create_table(
        "facilities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, unique=True),
        sa.Column("sport", sa.String(24), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("capacity > 0", name="positive_capacity"),
        sa.CheckConstraint(
            "sport IN ('tennis','football','basketball','badminton')", name="valid_sport"
        ),
    )
    op.create_table(
        "bookings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "facility_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("facilities.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("customer_ref", sa.String(64), nullable=False),
        sa.Column("participants", sa.Integer(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("participants > 0", name="positive_participants"),
        sa.CheckConstraint("ends_at > starts_at", name="valid_interval"),
        sa.CheckConstraint("status IN ('confirmed','cancelled')", name="valid_status"),
        sa.CheckConstraint(
            "(status = 'cancelled') = (cancelled_at IS NOT NULL)", name="consistent_cancellation"
        ),
    )
    op.create_index("ix_bookings_facility_start", "bookings", ["facility_id", "starts_at"])
    op.create_index("ix_bookings_customer", "bookings", ["customer_ref"])
    op.execute("""
        ALTER TABLE bookings ADD CONSTRAINT no_overlapping_confirmed_bookings
        EXCLUDE USING gist (
            facility_id WITH =,
            tstzrange(starts_at, ends_at, '[)') WITH &&
        ) WHERE (status = 'confirmed')
    """)


def downgrade():
    op.drop_table("bookings")
    op.drop_table("facilities")
