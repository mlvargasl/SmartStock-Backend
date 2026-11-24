"""Store daily holiday and festivity features for demand training."""

from alembic import op
import sqlalchemy as sa

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "calendar_observations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("observation_date", sa.Date(), nullable=False),
        sa.Column("is_holiday", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("is_festivity", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.CheckConstraint(
            "source IN ('SYNTHETIC', 'api.restart.cl')",
            name="ck_calendar_observation_source",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("observation_date", name="uq_calendar_observation_date"),
    )
    op.create_index(
        op.f("ix_calendar_observations_observation_date"),
        "calendar_observations",
        ["observation_date"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        op.f("ix_calendar_observations_observation_date"),
        table_name="calendar_observations",
    )
    op.drop_table("calendar_observations")
