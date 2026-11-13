"""Store daily historical weather observations with their source."""

from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "weather_observations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("observation_date", sa.Date(), nullable=False),
        sa.Column("temperature_max_c", sa.Numeric(6, 2), nullable=True),
        sa.Column("temperature_min_c", sa.Numeric(6, 2), nullable=True),
        sa.Column("precipitation_mm", sa.Numeric(7, 2), nullable=False),
        sa.Column("precipitation_probability_percent", sa.Numeric(5, 2), nullable=True),
        sa.Column("weather_code", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(16), nullable=False),
        sa.CheckConstraint(
            "precipitation_mm >= 0", name="ck_weather_precipitation_nonnegative"
        ),
        sa.CheckConstraint(
            "precipitation_probability_percent IS NULL OR "
            "precipitation_probability_percent BETWEEN 0 AND 100",
            name="ck_weather_probability_range",
        ),
        sa.CheckConstraint(
            "source IN ('SYNTHETIC', 'Open-Meteo')", name="ck_weather_source"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("observation_date", name="uq_weather_observation_date"),
    )
    op.create_index(
        op.f("ix_weather_observations_observation_date"),
        "weather_observations",
        ["observation_date"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        op.f("ix_weather_observations_observation_date"),
        table_name="weather_observations",
    )
    op.drop_table("weather_observations")
