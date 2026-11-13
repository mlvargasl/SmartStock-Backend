"""Allow clearly labeled synthetic sales for development."""

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("ck_transaction_source", "sale_transactions", type_="check")
    op.create_check_constraint(
        "ck_transaction_source",
        "sale_transactions",
        "source IN ('MANUAL', 'IMPORT', 'EXTERNAL', 'LEGACY', 'SYNTHETIC')",
    )


def downgrade():
    raise RuntimeError(
        "No se puede quitar el origen SYNTHETIC mientras existan registros de demostración"
    )
