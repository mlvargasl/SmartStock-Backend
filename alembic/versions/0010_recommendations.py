"""Store reviewed forecasts as recommendations."""
from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("recommendations", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("forecast_date", sa.Date(), nullable=False), sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_recommendations_forecast_date", "recommendations", ["forecast_date"])
    op.create_table("recommendation_items", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("recommendation_id", sa.Integer(), sa.ForeignKey("recommendations.id", ondelete="CASCADE"), nullable=False), sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False), sa.Column("product_name", sa.String(150), nullable=False), sa.Column("predicted_units", sa.Integer(), nullable=False), sa.Column("final_units", sa.Integer(), nullable=False), sa.Column("reason", sa.String(500)), sa.UniqueConstraint("recommendation_id", "product_id", name="uq_recommendation_product"), sa.CheckConstraint("predicted_units >= 0 AND final_units >= 0", name="ck_recommendation_quantities"))
    op.create_index("ix_recommendation_items_recommendation_id", "recommendation_items", ["recommendation_id"])


def downgrade():
    op.drop_table("recommendation_items")
    op.drop_table("recommendations")
