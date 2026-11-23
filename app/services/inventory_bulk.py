from fastapi import HTTPException
from sqlalchemy import select
from app.models import Ingredient, Inventory


def update_ingredient_stocks(db, entries):
    ids = [entry.ingredient_id for entry in entries]
    if len(set(ids)) != len(ids):
        raise HTTPException(400, "No se puede repetir un ingrediente.")
    statement = (select(Inventory).join(Ingredient, Ingredient.id == Inventory.ingredient_id)
                 .where(Inventory.ingredient_id.in_(ids)).order_by(Inventory.ingredient_id)
                 .with_for_update(of=(Inventory, Ingredient)))
    stocks = {stock.ingredient_id: stock for stock in db.scalars(statement).unique()}
    for entry in entries:
        stock = stocks.get(entry.ingredient_id)
        if stock is None:
            raise HTTPException(404, "Inventario no encontrado.")
        if not stock.ingredient.active:
            raise HTTPException(400, f"El ingrediente {stock.ingredient.name} está inactivo.")
        if stock.current_stock != entry.expected_stock:
            raise HTTPException(409, f"El stock de {stock.ingredient.name} cambió. Cancela la edición y vuelve a intentarlo.")
    for entry in entries:
        stocks[entry.ingredient_id].current_stock = entry.current_stock
    db.commit()
    return [stocks[ident] for ident in ids]
