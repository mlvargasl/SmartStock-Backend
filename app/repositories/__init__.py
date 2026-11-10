from datetime import date
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from app.models import (
    Ingredient,
    Inventory,
    Product,
    Recipe,
    Sale,
    SaleTransaction,
    User,
)


class Repository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, model, ident: int, lock: bool = False):
        query = select(model).where(model.id == ident)
        if lock:
            query = query.with_for_update()
        return self.db.scalar(query)

    def all(self, model):
        return list(self.db.scalars(select(model).order_by(model.id)))

    def by_email(self, email: str):
        return self.db.scalar(select(User).where(User.email == email.lower()))

    def add(self, obj):
        self.db.add(obj)
        self.db.flush()
        return obj

    def save(self):
        self.db.commit()

    def products(self, active: bool | None = None):
        stmt = select(Product).order_by(Product.id)
        if active is not None:
            stmt = stmt.where(Product.active == active)
        return list(self.db.scalars(stmt))

    def product_by_name(self, name: str):
        return self.db.scalar(select(Product).where(Product.name == name))

    def get_or_create_product(self, name: str):
        stmt = (
            insert(Product)
            .values(name=name, active=True)
            .on_conflict_do_nothing(index_elements=[Product.name])
            .returning(Product.id)
        )
        created_id = self.db.scalar(stmt)
        if created_id is not None:
            return self.get(Product, created_id), True
        return self.product_by_name(name), False

    def get_or_create_ingredient(self, name, unit, minimum_stock):
        stmt = (
            insert(Ingredient)
            .values(name=name, unit=unit, minimum_stock=minimum_stock, active=True)
            .on_conflict_do_nothing(index_elements=[Ingredient.name])
            .returning(Ingredient.id)
        )
        created_id = self.db.scalar(stmt)
        if created_id is not None:
            ingredient = self.get(Ingredient, created_id)
            self.add(Inventory(ingredient_id=created_id, current_stock=0))
            return ingredient, True
        return self.db.scalar(select(Ingredient).where(Ingredient.name == name)), False

    def recipe_by_product(self, product_id: int):
        return self.db.scalar(select(Recipe).where(Recipe.product_id == product_id))

    def stock(self, ingredient_id: int, lock: bool = False):
        stmt = select(Inventory).where(Inventory.ingredient_id == ingredient_id)
        if lock:
            stmt = stmt.with_for_update(of=Inventory)
        return self.db.scalar(stmt)

    def low_stock(self):
        return list(
            self.db.execute(
                select(Ingredient, Inventory)
                .join(Inventory)
                .where(Inventory.current_stock <= Ingredient.minimum_stock)
                .order_by(Ingredient.id)
            )
        )

    def sales(self, product_id: int | None, start: date | None, end: date | None):
        stmt = (
            select(Sale)
            .join(SaleTransaction)
            .where(SaleTransaction.status == "COMPLETED")
        )
        if product_id is not None:
            stmt = stmt.where(Sale.product_id == product_id)
        if start is not None:
            stmt = stmt.where(Sale.sale_date >= start)
        if end is not None:
            stmt = stmt.where(Sale.sale_date <= end)
        return list(self.db.scalars(stmt.order_by(Sale.id)))

    def sales_for_export(
        self, product_id: int | None, start: date | None, end: date | None
    ):
        stmt = (
            select(Sale, Product.name)
            .join(Product, Sale.product_id == Product.id)
            .join(SaleTransaction)
            .where(SaleTransaction.status == "COMPLETED")
        )
        if product_id is not None:
            stmt = stmt.where(Sale.product_id == product_id)
        if start is not None:
            stmt = stmt.where(Sale.sale_date >= start)
        if end is not None:
            stmt = stmt.where(Sale.sale_date <= end)
        return list(self.db.execute(stmt.order_by(Sale.id)))

    def count_active(self, model):
        return self.db.scalar(
            select(func.count()).select_from(model).where(model.active.is_(True))
        )

    def daily_sales(self, start: date, end: date):
        statement = (
            select(Sale.sale_date, func.coalesce(func.sum(Sale.quantity), 0))
            .join(SaleTransaction)
            .where(
                SaleTransaction.status == "COMPLETED",
                Sale.sale_date >= start,
                Sale.sale_date <= end,
            )
            .group_by(Sale.sale_date)
            .order_by(Sale.sale_date)
        )
        return dict(self.db.execute(statement).all())

    def sum_sales(self, start: date, end: date):
        return self.db.scalar(
            select(func.coalesce(func.sum(Sale.quantity), 0))
            .join(SaleTransaction)
            .where(
                SaleTransaction.status == "COMPLETED",
                Sale.sale_date >= start,
                Sale.sale_date <= end,
            )
        )
