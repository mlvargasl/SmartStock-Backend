from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import Product, Sale, SaleTransaction


class TransactionRepository:
    def __init__(self, db: Session):
        self.db = db

    def list(self, product_id=None, start=None, end=None):
        stmt = select(SaleTransaction).order_by(
            SaleTransaction.sale_date.desc(), SaleTransaction.id.desc()
        )
        if product_id is not None:
            stmt = stmt.where(SaleTransaction.items.any(Sale.product_id == product_id))
        if start is not None:
            stmt = stmt.where(SaleTransaction.sale_date >= start)
        if end is not None:
            stmt = stmt.where(SaleTransaction.sale_date <= end)
        return list(self.db.scalars(stmt).unique())

    def get(self, ident, lock=False):
        stmt = select(SaleTransaction).where(SaleTransaction.id == ident)
        if lock:
            stmt = stmt.with_for_update(of=SaleTransaction)
        return self.db.scalars(stmt).unique().one_or_none()

    def lock_products(self, product_ids):
        stmt = select(Product).where(Product.id.in_(product_ids)).order_by(Product.id).with_for_update()
        return {product.id: product for product in self.db.scalars(stmt)}

    def save(self, obj):
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj
