"""Record confirmed production once per date."""
from alembic import op
import sqlalchemy as sa

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("production_confirmations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("production_date", sa.Date(), nullable=False, unique=True),
        sa.Column("recommendation_id", sa.Integer(), sa.ForeignKey("recommendations.id"), nullable=False),
        sa.Column("confirmed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("ingredients", sa.JSON(), nullable=False),
    )

def downgrade():
    op.drop_table("production_confirmations")
