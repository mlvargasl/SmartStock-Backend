"""Preserve product quantities at production confirmation."""
from alembic import op
import sqlalchemy as sa

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("production_confirmations", sa.Column("products", sa.JSON(), nullable=True))

def downgrade():
    op.drop_column("production_confirmations", "products")
