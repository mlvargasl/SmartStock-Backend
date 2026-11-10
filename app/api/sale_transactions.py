from datetime import date
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from app.api.deps import Db, allow, current_user
from app.models import Role, User
from app.repositories.sale_transactions import TransactionRepository
from app.schemas.sale_transaction import TransactionIn, TransactionOut
from app.services.sale_transactions import TransactionService

router = APIRouter(prefix="/api/sale-transactions", tags=["Sales"])
roles = Depends(allow(Role.ADMIN, Role.PRODUCTION_MANAGER))


def serialize(t):
    return {
        "id": t.id,
        "source": t.source,
        "external_id": t.external_id,
        "sold_at": t.sold_at,
        "sale_date": t.sale_date,
        "status": t.status,
        "created_at": t.created_at,
        "cancelled_at": t.cancelled_at,
        "items": [
            {
                "id": i.id,
                "product_id": i.product_id,
                "product_name": i.product.name,
                "quantity": i.quantity,
            }
            for i in t.items
        ],
    }


@router.get("", response_model=list[TransactionOut], dependencies=[roles])
def list_transactions(
    db: Db,
    product_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(400, "Start date must not be after end date")
    return [
        serialize(t)
        for t in TransactionRepository(db).list(product_id, start_date, end_date)
    ]


@router.get("/{ident}", response_model=TransactionOut, dependencies=[roles])
def get_transaction(ident: int, db: Db):
    obj = TransactionRepository(db).get(ident)
    if obj is None:
        raise HTTPException(404, "Sale transaction not found")
    return serialize(obj)


@router.post("", response_model=TransactionOut, status_code=201, dependencies=[roles])
def create_transaction(data: TransactionIn, db: Db):
    return serialize(TransactionService(TransactionRepository(db)).create(data))


@router.patch("/{ident}/cancel", response_model=TransactionOut, dependencies=[roles])
def cancel_transaction(
    ident: int, db: Db, user: Annotated[User, Depends(current_user)]
):
    return serialize(
        TransactionService(TransactionRepository(db)).cancel(ident, user.id)
    )
