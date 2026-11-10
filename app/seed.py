"""Development-only sample data. Run after migrations in a disposable database."""

from datetime import date, timedelta
from pydantic import ValidationError
from app.core.seed_config import SeedSettings
from sqlalchemy import select
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import (
    Ingredient,
    Inventory,
    Product,
    Recipe,
    RecipeIngredient,
    Role,
    Sale,
    SaleTransaction,
    User,
)


def seed(settings: SeedSettings | None = None, session_factory=SessionLocal):
    settings = settings or SeedSettings()
    accounts = [
        (
            settings.seed_admin_name,
            settings.seed_admin_email.lower(),
            Role.ADMIN,
            settings.seed_admin_password,
        ),
        (
            settings.seed_production_name,
            settings.seed_production_email.lower(),
            Role.PRODUCTION_MANAGER,
            settings.seed_production_password,
        ),
        (
            settings.seed_inventory_name,
            settings.seed_inventory_email.lower(),
            Role.INVENTORY_MANAGER,
            settings.seed_inventory_password,
        ),
    ]
    with session_factory() as db:
        for name, email, role, password in accounts:
            if not db.scalar(select(User).where(User.email == email)):
                db.add(
                    User(
                        name=name,
                        email=email,
                        role=role,
                        password_hash=hash_password(password.get_secret_value()),
                    )
                )
        products = []
        for name in ("Torta Chocolate", "Cheesecake"):
            obj = db.scalar(select(Product).where(Product.name == name))
            if obj is None:
                obj = Product(name=name)
                db.add(obj)
                db.flush()
            products.append(obj)
        ingredients = []
        for name, unit, minimum, stock in [
            ("Harina", "g", 1000, 5000),
            ("Azúcar", "g", 500, 2000),
        ]:
            obj = db.scalar(select(Ingredient).where(Ingredient.name == name))
            if obj is None:
                obj = Ingredient(
                    name=name,
                    unit=unit,
                    minimum_stock=minimum,
                    inventory=Inventory(current_stock=stock),
                )
                db.add(obj)
                db.flush()
            ingredients.append(obj)
        for product in products:
            if not db.scalar(select(Recipe).where(Recipe.product_id == product.id)):
                db.add(
                    Recipe(
                        product_id=product.id,
                        ingredients=[
                            RecipeIngredient(
                                ingredient_id=ingredients[0].id, quantity_per_unit=150
                            ),
                            RecipeIngredient(
                                ingredient_id=ingredients[1].id, quantity_per_unit=20
                            ),
                        ],
                    )
                )
        if not db.scalar(select(Sale.id).limit(1)):
            db.add_all(
                [
                    Sale(
                        product_id=products[0].id,
                        quantity=5,
                        sale_date=date.today(),
                        transaction=SaleTransaction(
                            source="LEGACY", sale_date=date.today()
                        ),
                    ),
                    Sale(
                        product_id=products[1].id,
                        quantity=3,
                        sale_date=date.today() - timedelta(days=1),
                        transaction=SaleTransaction(
                            source="LEGACY", sale_date=date.today() - timedelta(days=1)
                        ),
                    ),
                ]
            )
        db.commit()


if __name__ == "__main__":
    try:
        seed()
    except ValidationError as exc:
        fields = ", ".join(
            ".".join(str(part) for part in error["loc"]) or "seed"
            for error in exc.errors()
        )
        raise SystemExit(
            f"Configuración del seed incompleta o inválida: {fields}. Revisa las variables SEED_* en .env."
        ) from None
