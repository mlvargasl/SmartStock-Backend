"""Confirmed production plans and snapshots of required ingredients."""

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "production_plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("production_date", sa.Date(), nullable=False, unique=True),
        sa.Column(
            "confirmed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column(
            "confirmed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_table(
        "production_plan_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "plan_id",
            sa.Integer(),
            sa.ForeignKey("production_plans.id"),
            nullable=False,
        ),
        sa.Column(
            "recommendation_id",
            sa.Integer(),
            sa.ForeignKey("production_recommendations.id"),
            nullable=False,
        ),
        sa.Column("product_name", sa.String(150), nullable=False),
        sa.Column("predicted_quantity", sa.Numeric(18, 3), nullable=False),
        sa.Column("recommended_quantity", sa.Integer(), nullable=False),
        sa.Column("final_quantity", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column("model_version", sa.String(64), nullable=False),
        sa.UniqueConstraint(
            "plan_id", "recommendation_id", name="uq_plan_recommendation"
        ),
    )
    op.create_table(
        "production_plan_ingredients",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "plan_id",
            sa.Integer(),
            sa.ForeignKey("production_plans.id"),
            nullable=False,
        ),
        sa.Column(
            "ingredient_id",
            sa.Integer(),
            sa.ForeignKey("ingredients.id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("unit", sa.String(10), nullable=False),
        sa.Column("current_stock", sa.Numeric(18, 3), nullable=False),
        sa.Column("required_quantity", sa.Numeric(18, 3), nullable=False),
        sa.Column("missing_quantity", sa.Numeric(18, 3), nullable=False),
        sa.Column("remaining_quantity", sa.Numeric(18, 3), nullable=False),
        sa.UniqueConstraint("plan_id", "ingredient_id", name="uq_plan_ingredient"),
    )


def downgrade():
    op.drop_table("production_plan_ingredients")
    op.drop_table("production_plan_items")
    op.drop_table("production_plans")
