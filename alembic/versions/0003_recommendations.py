"""Persist editable production recommendations and their adjustment history."""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "production_recommendations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "forecast_id", sa.Integer(), sa.ForeignKey("forecasts.id"), nullable=False
        ),
        sa.Column(
            "product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False
        ),
        sa.Column("recommendation_date", sa.Date(), nullable=False),
        sa.Column("predicted_quantity", sa.Numeric(18, 3), nullable=False),
        sa.Column("model_version", sa.String(64), nullable=False),
        sa.Column("recommended_quantity", sa.Integer(), nullable=False),
        sa.Column("adjusted_quantity", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("forecast_id", name="uq_recommendation_forecast"),
        sa.UniqueConstraint(
            "product_id", "recommendation_date", name="uq_recommendation_product_date"
        ),
        sa.CheckConstraint(
            "recommended_quantity >= 0 AND adjusted_quantity >= 0",
            name="ck_recommendation_nonnegative",
        ),
    )
    op.create_index(
        "ix_production_recommendations_forecast_id",
        "production_recommendations",
        ["forecast_id"],
    )
    op.create_table(
        "recommendation_adjustments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "recommendation_id",
            sa.Integer(),
            sa.ForeignKey("production_recommendations.id"),
            nullable=False,
        ),
        sa.Column("previous_quantity", sa.Integer(), nullable=False),
        sa.Column("new_quantity", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "previous_quantity >= 0 AND new_quantity >= 0",
            name="ck_recommendation_adjustment_nonnegative",
        ),
    )
    op.create_index(
        "ix_recommendation_adjustments_recommendation_id",
        "recommendation_adjustments",
        ["recommendation_id"],
    )


def downgrade():
    op.drop_table("recommendation_adjustments")
    op.drop_table("production_recommendations")
