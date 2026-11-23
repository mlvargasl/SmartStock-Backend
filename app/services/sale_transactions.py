from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from app.core.config import get_settings
from app.models import Product, Sale, SaleTransaction
from app.repositories.sale_transactions import TransactionRepository
from app.schemas.sale_transaction import TransactionIn


class TransactionService:
    def __init__(self, repository: TransactionRepository):
        self.repo = repository

    def create(self, data: TransactionIn):
        products = self.repo.lock_products([item.product_id for item in data.items])
        for item in data.items:
            product = products.get(item.product_id)
            if product is None:
                raise HTTPException(404, "Product not found")
            if not product.active:
                raise HTTPException(400, "Product is inactive")
            if product.stock_quantity < item.quantity:
                raise HTTPException(400, f"Stock insuficiente para {product.name}. Disponible: {product.stock_quantity}.")
        for item in data.items:
            products[item.product_id].stock_quantity -= item.quantity
        day = data.sold_at.astimezone(ZoneInfo(get_settings().weather_timezone)).date()
        transaction = SaleTransaction(
            source=data.source,
            stock_deducted=True,
            external_id=data.external_id,
            sold_at=data.sold_at,
            sale_date=day,
            items=[
                Sale(product_id=item.product_id, quantity=item.quantity, sale_date=day)
                for item in data.items
            ],
        )
        return self.repo.save(transaction)

    def cancel(self, ident: int, user_id: int):
        obj = self.repo.get(ident, lock=True)
        if obj is None:
            raise HTTPException(404, "Sale transaction not found")
        if obj.source == "LEGACY":
            raise HTTPException(
                409, "Historical records cannot be cancelled as transactions"
            )
        if obj.status == "CANCELLED":
            raise HTTPException(409, "Sale transaction is already cancelled")
        if obj.stock_deducted:
            products = self.repo.lock_products([item.product_id for item in obj.items])
            for item in obj.items:
                product = products[item.product_id]
                if product.stock_quantity > 2147483647 - item.quantity:
                    raise HTTPException(400, "La devolución excede el máximo permitido para el stock.")
                product.stock_quantity += item.quantity
        obj.status = "CANCELLED"
        obj.cancelled_at = datetime.now(timezone.utc)
        obj.cancelled_by = user_id
        return self.repo.save(obj)
