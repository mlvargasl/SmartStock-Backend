"""Group sales into transactions without inventing historical timestamps."""

from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("products", sa.Column("external_code", sa.String(100), nullable=True))
    op.create_unique_constraint(
        "uq_products_external_code", "products", ["external_code"]
    )
    op.create_table(
        "sale_transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("external_id", sa.String(150), nullable=True),
        sa.Column("sold_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sale_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(16), server_default="COMPLETED", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "cancelled_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column("legacy_sale_id", sa.Integer(), nullable=True),
        sa.UniqueConstraint("source", "external_id", name="uq_sale_source_external_id"),
        sa.CheckConstraint(
            "source IN ('MANUAL', 'IMPORT', 'EXTERNAL', 'LEGACY')",
            name="ck_transaction_source",
        ),
        sa.CheckConstraint(
            "status IN ('COMPLETED', 'CANCELLED')", name="ck_transaction_status"
        ),
    )
    op.create_index(
        "ix_sale_transactions_sale_date", "sale_transactions", ["sale_date"]
    )
    op.add_column("sales", sa.Column("transaction_id", sa.Integer(), nullable=True))
    op.execute(
        "INSERT INTO sale_transactions (source, sale_date, created_at, legacy_sale_id) SELECT 'LEGACY', sale_date, created_at, id FROM sales"
    )
    op.execute(
        "UPDATE sales SET transaction_id = t.id FROM sale_transactions t WHERE t.legacy_sale_id = sales.id"
    )
    op.drop_column("sale_transactions", "legacy_sale_id")
    op.alter_column("sales", "transaction_id", nullable=False)
    op.create_foreign_key(
        "fk_sale_transaction", "sales", "sale_transactions", ["transaction_id"], ["id"]
    )
    op.create_index("ix_sales_transaction_id", "sales", ["transaction_id"])


def downgrade():
    raise RuntimeError(
        "La migración de ventas no se puede revertir sin decidir cómo preservar transacciones y anulaciones"
    )
