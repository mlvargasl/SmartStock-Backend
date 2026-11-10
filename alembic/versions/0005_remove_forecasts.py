"""Retire predictive tables, archiving them if they contain data."""

from pathlib import Path
import runpy
from alembic import op
from sqlalchemy import text

revision = "0005"
down_revision = "0004"
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
ARCHIVE = "retired_forecasting"


def upgrade():
    connection = op.get_bind()
    has_data = any(
        connection.execute(text(f"SELECT EXISTS (SELECT 1 FROM {table})")).scalar()
        for table in TABLES
    )
    if has_data:
        # Move the whole connected set together: foreign keys continue to refer to the same tables.
        for table in TABLES:
            if connection.execute(
                text("SELECT to_regclass(:name)"), {"name": f"{ARCHIVE}.{table}"}
            ).scalar():
                raise RuntimeError(
                    f"Archive table {ARCHIVE}.{table} already exists; refusing to overwrite it"
                )
        op.execute(f"CREATE SCHEMA IF NOT EXISTS {ARCHIVE}")
        for table in TABLES:
            op.execute(f"ALTER TABLE {table} SET SCHEMA {ARCHIVE}")
    else:
        for table in TABLES:
            op.drop_table(table)


def downgrade():
    connection = op.get_bind()
    archived = connection.execute(
        text("SELECT to_regclass(:name)"), {"name": f"{ARCHIVE}.forecasts"}
    ).scalar()
    if archived:
        target = connection.dialect.identifier_preparer.quote(
            connection.execute(text("SELECT current_schema()")).scalar()
        )
        for table in reversed(TABLES):
            op.execute(f"ALTER TABLE {ARCHIVE}.{table} SET SCHEMA {target}")
    else:
        folder = Path(__file__).parent
        for name in (
            "0002_forecasts.py",
            "0003_recommendations.py",
            "0004_production_plan.py",
        ):
            runpy.run_path(str(folder / name))["upgrade"]()
