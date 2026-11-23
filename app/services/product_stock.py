from fastapi import HTTPException
from app.repositories.sale_transactions import TransactionRepository


def update_product_stocks(db, entries):
    ids = [entry.product_id for entry in entries]
    if len(set(ids)) != len(ids):
        raise HTTPException(400, 'No se puede repetir un producto.')
    repo = TransactionRepository(db)
    products = repo.lock_products(ids)
    for entry in entries:
        product = products.get(entry.product_id)
        if product is None:
            raise HTTPException(404, 'Producto no encontrado.')
        if not product.active:
            raise HTTPException(400, f'El producto {product.name} está inactivo.')
        if product.stock_quantity != entry.expected_stock:
            raise HTTPException(409, f'El stock de {product.name} cambió. Cancela la edición y vuelve a intentarlo.')
    for entry in entries:
        products[entry.product_id].stock_quantity = entry.stock_quantity
    db.commit()
    return [products[ident] for ident in ids]
