"""Persist forecasts with idempotent product/date/model keys."""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "forecasts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False
        ),
        sa.Column("forecast_date", sa.Date(), nullable=False),
        sa.Column("predicted_quantity", sa.Numeric(18, 3), nullable=False),
        sa.Column("model_version", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("predicted_quantity >= 0", name="ck_forecast_nonnegative"),
        sa.UniqueConstraint(
            "product_id",
            "forecast_date",
            "model_version",
            name="uq_forecast_product_date_version",
        ),
    )
    op.create_index("ix_forecasts_product_id", "forecasts", ["product_id"])
    op.create_index(
        "ix_forecasts_date_product", "forecasts", ["forecast_date", "product_id"]
    )


def downgrade():
    op.drop_table("forecasts")
