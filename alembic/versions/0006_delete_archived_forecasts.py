"""Permanently remove the retired forecast and production tables."""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

TABLES = (
    "production_plan_ingredients",
    "production_plan_items",
    "production_plans",
    "recommendation_adjustments",
    "production_recommendations",
    "forecasts",
)


def upgrade():
    for table in TABLES:
        op.execute(f"DROP TABLE IF EXISTS retired_forecasting.{table}")
    # RESTRICT is the default: do not delete unrelated objects if the schema is not empty.
    op.execute("DROP SCHEMA IF EXISTS retired_forecasting")


def downgrade():
    raise RuntimeError(
        "Cannot restore deleted forecasting data; restore a database backup if needed"
    )
