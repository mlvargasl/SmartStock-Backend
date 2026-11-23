"""Track available finished products and identify stock-deducting sales."""
from alembic import op
import sqlalchemy as sa

revision = '0012'
down_revision = '0011'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('products', sa.Column('stock_quantity', sa.Integer(), nullable=False, server_default='0'))
    op.create_check_constraint('ck_product_stock_nonnegative', 'products', 'stock_quantity >= 0')
    op.add_column('sale_transactions', sa.Column('stock_deducted', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    op.drop_column('sale_transactions', 'stock_deducted')
    op.drop_constraint('ck_product_stock_nonnegative', 'products', type_='check')
    op.drop_column('products', 'stock_quantity')
