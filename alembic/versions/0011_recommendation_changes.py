"""Record administrative edits to recommendations."""
from alembic import op
import sqlalchemy as sa

revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('recommendation_changes', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('recommendation_item_id', sa.Integer(), sa.ForeignKey('recommendation_items.id', ondelete='CASCADE'), nullable=False), sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False), sa.Column('previous_units', sa.Integer(), nullable=False), sa.Column('new_units', sa.Integer(), nullable=False), sa.Column('reason', sa.String(500), nullable=False), sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index('ix_recommendation_changes_recommendation_item_id', 'recommendation_changes', ['recommendation_item_id'])


def downgrade():
    op.drop_table('recommendation_changes')
