from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from app.core.config import get_settings
from decimal import Decimal
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.security import generate_password, hash_password, verify_password
from app.models import (
    Ingredient,
    Inventory,
    Product,
    Recipe,
    RecipeIngredient,
    Sale,
    SaleTransaction,
    User,
)
from app.repositories import Repository
from app.schemas import ProductIn, SaleIn, UserCreate
from app.utils.sales_files import read_sales_file, normalize_sale_row, render_sales_csv
from app.services.product_import import import_products


class Service:
    def __init__(self, db: Session):
        self.repo = Repository(db)

    def get(self, model, ident):
        obj = self.repo.get(model, ident)
        if obj is None:
            raise HTTPException(404, f"{model.__name__} not found")
        return obj

    def create(self, model, data):
        values = data.model_dump()
        if model is User:
            values["email"] = values["email"].lower()
            values["password_hash"] = hash_password(values.pop("password"))
        obj = model(**values)
        if model is Ingredient:
            obj.inventory = Inventory(current_stock=0)
        self.repo.add(obj)
        self.repo.save()
        return obj

    def create_generated_user(self, data):
        password = generate_password()
        user = self.create(
            User,
            UserCreate(
                name=data.name, email=data.email, role=data.role, password=password
            ),
        )
        return {"user": user, "initial_password": password}

    def change_password(self, user_id, current_password, new_password):
        user = self.repo.get(User, user_id, lock=True)
        if user is None or not user.active:
            raise HTTPException(401, "Invalid or expired credentials")
        if not verify_password(current_password, user.password_hash):
            raise HTTPException(400, "Current password is incorrect")
        if current_password == new_password:
            raise HTTPException(400, "New password must be different")
        user.password_hash = hash_password(new_password)
        self.repo.save()

    def update(self, model, ident, data):
        obj = self.get(model, ident)
        values = data.model_dump(exclude_unset=True)
        if "email" in values:
            values["email"] = values["email"].lower()
        if values.get("password") is not None:
            values["password_hash"] = hash_password(values["password"])
        values.pop("password", None)
        for key, value in values.items():
            setattr(obj, key, value)
        self.repo.save()
        return obj

    def recipe(self, data, ident=None):
        self.get(Product, data.product_id)
        for item in data.ingredients:
            self.get(Ingredient, item.ingredient_id)
        existing = self.repo.recipe_by_product(data.product_id)
        if existing and existing.id != ident:
            raise HTTPException(409, "Product already has a recipe")
        if ident is None:
            obj = Recipe(product_id=data.product_id)
            self.repo.add(obj)
        else:
            obj = self.get(Recipe, ident)
            obj.product_id = data.product_id
            obj.updated_at = func.now()
            obj.ingredients.clear()
            self.repo.db.flush()
        obj.ingredients = [
            RecipeIngredient(**item.model_dump()) for item in data.ingredients
        ]
        self.repo.save()
        return obj

    def update_recipe_quantity(self, recipe_id: int, ingredient_id: int, quantity):
        recipe = self.repo.get(Recipe, recipe_id, lock=True)
        if recipe is None:
            raise HTTPException(404, "Recipe not found")
        item = next(
            (
                item
                for item in recipe.ingredients
                if item.ingredient_id == ingredient_id
            ),
            None,
        )
        if item is None:
            raise HTTPException(404, "Ingredient not found in recipe")
        item.quantity_per_unit = quantity
        recipe.updated_at = func.now()
        self.repo.save()
        return recipe

    def recipe_for_product(self, product_id):
        self.get(Product, product_id)
        obj = self.repo.recipe_by_product(product_id)
        if obj is None:
            raise HTTPException(404, "Recipe not found")
        return obj

    def stock(self, ingredient_id, value=None, adjust=False):
        obj = self.repo.stock(ingredient_id, lock=value is not None)
        if obj is None:
            raise HTTPException(404, "Inventory not found")
        if value is not None:
            new_stock = obj.current_stock + value if adjust else value
            if new_stock < 0:
                raise HTTPException(400, "Stock cannot be negative")
            obj.current_stock = new_stock
            self.repo.save()
        return obj

    def low_stock(self):
        return [
            dict(
                ingredient_id=i.id,
                name=i.name,
                current_stock=s.current_stock,
                minimum_stock=i.minimum_stock,
                unit=i.unit,
            )
            for i, s in self.repo.low_stock()
        ]

    def sale(self, data, commit=True, source="MANUAL"):
        product = self.get(Product, data.product_id)
        if not product.active:
            raise HTTPException(400, "Product is inactive")
        transaction = SaleTransaction(source=source, sale_date=data.sale_date)
        obj = self.repo.add(Sale(**data.model_dump(), transaction=transaction))
        if commit:
            self.repo.save()
        return obj

    def import_sales(
        self, filename: str, content: bytes, can_create_products: bool = False
    ):
        rows = read_sales_file(filename, content)
        if rows and "sale_id" in rows[0][1]:
            return self.import_grouped_sales(rows, can_create_products)
        errors = []
        imported = 0
        created_products = []
        for number, row, row_error in rows:
            try:
                if row_error:
                    raise ValueError(row_error)
                raw_date, name, quantity = normalize_sale_row(row)
                # Validate the entire row before creating any related product.
                name = ProductIn(name=name).name
                valid_sale = SaleIn(product_id=1, quantity=quantity, sale_date=raw_date)
                product = self.repo.product_by_name(name)
                # Restore protected formula-like names from exports.
                if (
                    not product
                    and name.startswith("'")
                    and name[1:].lstrip().startswith(("=", "+", "-", "@"))
                ):
                    product = self.repo.product_by_name(name[1:])
                if product is None:
                    if not can_create_products:
                        raise ValueError(
                            "Producto no encontrado; un administrador debe crearlo"
                        )
                    product, created = self.repo.get_or_create_product(name)
                    if created:
                        created_products.append(
                            {"id": product.id, "name": product.name}
                        )
                if not product.active:
                    raise ValueError("Producto inactivo")
                valid_sale.product_id = product.id
                self.sale(valid_sale, commit=False, source="IMPORT")
                imported += 1
            except (ValueError, ValidationError) as exc:
                errors.append({"row": number, "detail": str(exc)})
        self.repo.save()
        return {
            "total_rows": len(rows),
            "imported_rows": imported,
            "rejected_rows": len(errors),
            "errors": errors,
            "created_products": created_products,
        }

    def import_grouped_sales(self, rows, can_create_products):
        groups = {}
        for number, row, row_error in rows:
            raw_id = row.get("sale_id")
            if isinstance(raw_id, bool) or raw_id is None:
                key = ""
            else:
                key = str(raw_id).strip()
            groups.setdefault(key, []).append((number, row, row_error))
        errors, imported, created_products = [], 0, []
        for external_id, group in groups.items():
            try:
                if not external_id or len(external_id) > 150:
                    raise ValueError("ID de venta obligatorio, máximo 150 caracteres")
                prepared = []
                for _, row, row_error in group:
                    if row_error:
                        raise ValueError(row_error)
                    raw_date, name, quantity = normalize_sale_row(row)
                    name = ProductIn(name=name).name
                    valid = SaleIn(product_id=1, quantity=quantity, sale_date=raw_date)
                    raw_time = row["time"]
                    if isinstance(raw_time, datetime):
                        raw_time = raw_time.timetz()
                    if isinstance(raw_time, time):
                        time_value = raw_time
                    elif isinstance(raw_time, str):
                        time_value = time.fromisoformat(raw_time.strip())
                    else:
                        raise ValueError("Hora inválida")
                    moment = datetime.combine(valid.sale_date, time_value)
                    if moment.tzinfo is None:
                        zone = ZoneInfo(get_settings().weather_timezone)
                        first, second = moment.replace(
                            tzinfo=zone, fold=0
                        ), moment.replace(tzinfo=zone, fold=1)
                        if first.utcoffset() != second.utcoffset():
                            raise ValueError(
                                "Hora ambigua o inexistente; agrega el desfase horario"
                            )
                        moment = first
                    local_day = moment.astimezone(
                        ZoneInfo(get_settings().weather_timezone)
                    ).date()
                    if local_day != valid.sale_date:
                        raise ValueError(
                            "Fecha y zona horaria no coinciden con la sucursal"
                        )
                    prepared.append((moment, name, valid.quantity))
                if any(moment != prepared[0][0] for moment, _, _ in prepared):
                    raise ValueError("El mismo ID debe tener fecha y hora iguales")
                if len({name for _, name, _ in prepared}) != len(prepared):
                    raise ValueError("La venta repite un producto")
                added = []
                with self.repo.db.begin_nested():
                    if self.repo.db.scalar(
                        select(SaleTransaction.id).where(
                            SaleTransaction.source == "IMPORT",
                            SaleTransaction.external_id == external_id,
                        )
                    ):
                        raise ValueError("ID de venta ya importado")
                    items = []
                    for _, name, quantity in prepared:
                        product = self.repo.product_by_name(name)
                        if product is None:
                            if not can_create_products:
                                raise ValueError(
                                    "Producto no encontrado; un administrador debe crearlo"
                                )
                            product, created = self.repo.get_or_create_product(name)
                            if created:
                                added.append({"id": product.id, "name": product.name})
                        if not product.active:
                            raise ValueError("Producto inactivo")
                        items.append(
                            Sale(
                                product_id=product.id,
                                quantity=quantity,
                                sale_date=prepared[0][0]
                                .astimezone(ZoneInfo(get_settings().weather_timezone))
                                .date(),
                            )
                        )
                    transaction = SaleTransaction(
                        source="IMPORT",
                        external_id=external_id,
                        sold_at=prepared[0][0],
                        sale_date=items[0].sale_date,
                        items=items,
                    )
                    self.repo.db.add(transaction)
                    self.repo.db.flush()
                imported += len(group)
                created_products.extend(added)
            except (ValueError, ValidationError, IntegrityError) as exc:
                detail = (
                    "ID de venta duplicado o datos en conflicto"
                    if isinstance(exc, IntegrityError)
                    else str(exc)
                )
                errors.extend(
                    {"row": number, "detail": detail} for number, _, _ in group
                )
        self.repo.save()
        return {
            "total_rows": len(rows),
            "imported_rows": imported,
            "rejected_rows": len(errors),
            "errors": errors,
            "created_products": created_products,
        }

    def import_products(self, filename: str, content: bytes):
        return import_products(self.repo, filename, content)

    def export_sales(self, product_id, start, end):
        if start and end and start > end:
            raise HTTPException(400, "Start date must not be after end date")
        return render_sales_csv(self.repo.sales_for_export(product_id, start, end))

    def sales_trend(self, days: int):
        today = datetime.now(ZoneInfo(get_settings().weather_timezone)).date()
        start = today - timedelta(days=days - 1)
        totals = self.repo.daily_sales(start, today)
        return [
            {
                "date": start + timedelta(days=i),
                "quantity": int(totals.get(start + timedelta(days=i), 0)),
            }
            for i in range(days)
        ]

    def dashboard(self):
        today = datetime.now(ZoneInfo(get_settings().weather_timezone)).date()
        return {
            "active_products": self.repo.count_active(Product),
            "active_ingredients": self.repo.count_active(Ingredient),
            "low_stock_ingredients": len(self.low_stock()),
            "sales_today": self.repo.sum_sales(today, today),
            "sales_last_7_days": self.repo.sum_sales(today - timedelta(days=6), today),
        }
